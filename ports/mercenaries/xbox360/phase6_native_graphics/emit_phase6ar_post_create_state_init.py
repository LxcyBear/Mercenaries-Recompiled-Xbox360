#!/usr/bin/env python3
"""Phase 6AR-A: restore the missing retail post-CreateDevice D3D state initializer.

Forensics proved:
  * 6AN-B orange is caused by device+0x1A10 == 0, which underflows
    sub_0028BC60 and eventually dereferences 0x80000004.
  * 6AO-A found the sole +0x1A10 writer: sub_0028F9E0.
  * 6AP-A recovered retail CreateDevice sub_0028CAA0 -> 0x0028FF80.
  * 6AQ-A proved 0x0028FF80 directly calls sub_0028F9E0 with:
        ECX = guest device
        arg1 = CreateDevice presentation-parameters pointer
  * 0x0028FF80 itself contains original-Xbox writes to 0x80000000, so it must
    not be restored wholesale.

This phase keeps the proven native-Xenos CreateDevice bridge and directly calls
only sub_0028F9E0 with the exact retail ABI after publishing the internal guest
device. It validates stack balance, HRESULT, +0x1A10 count and first stack
entry before allowing translated D3D to continue.

The emitter also audits sub_0028F9E0's immediate translated helper callees and
refuses to build if any contains a literal absolute guest WRITE at >=0x80000000.
Existing KSEG/NV2A/MMIO/VRAM/guest-fault fences remain hard.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
BUILD_TAG = "P6AR-POST-CREATE-STATE-INIT-20261024-A"
COOKIE_OLD = "phase6aj_env_build_cookie"
COOKIE_NEW = "phase6ar_env_build_cookie"
SHARD_TARGET_CHARS = 750000

INIT_FUNC = "sub_0028F9E0"
HELPERS = (
    "sub_00290690",
    "sub_002907A0",
    "sub_00290E50",
    "sub_001787C0",
    "sub_0028E2D0",
    "sub_00289410",
    "sub_0028A0D0",
    "sub_0028B0F0",
    "sub_0028EB90",
)

ABS_WRITE_RE = re.compile(
    r"GUEST_WRITE(?:8|16|32|64|F32)\(\s*"
    r"(?P<addr>-?\d+|0x[0-9A-Fa-f]+)"
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AR] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AR] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AR] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AR] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


def find_definition(main_text: str, base, signature: str) -> tuple[int, int]:
    masked = base.mask_noncode(main_text)
    hits = []
    cursor = 0
    while True:
        pos = masked.find(signature, cursor)
        if pos < 0:
            break
        after = pos + len(signature)
        probe = after
        while probe < len(masked) and masked[probe].isspace():
            probe += 1
        if probe < len(masked) and masked[probe] == "{":
            hits.append((pos, probe))
        cursor = after
    if len(hits) != 1:
        raise SystemExit(
            f"[Phase6AR] expected one definition for {signature}, found {len(hits)}"
        )
    start, brace = hits[0]
    return start, base.closing_brace(masked, brace)


def parse_literal(token: str) -> int:
    token = token.strip()
    if token.lower().startswith("0x"):
        return int(token, 16)
    value = int(token, 10)
    return value & 0xFFFFFFFF


def audit_helpers(main_text: str, base) -> list[dict]:
    rows = []
    for name in HELPERS:
        start, end = find_definition(main_text, base, f"static void {name}(void)")
        body = main_text[start:end]
        dangerous = []
        for line_no, line in enumerate(body.splitlines(), start=1):
            for m in ABS_WRITE_RE.finditer(line):
                addr = parse_literal(m.group("addr"))
                if addr >= 0x80000000:
                    dangerous.append(
                        {
                            "relative_line": line_no,
                            "address": f"0x{addr:08X}",
                            "source": line.strip(),
                        }
                    )
        rows.append(
            {
                "function": name,
                "dangerous_absolute_high_writes": dangerous,
                "direct_frontier_calls": body.count("phase4c_direct_frontier("),
                "guest_writes": body.count("GUEST_WRITE"),
                "guest_reads": body.count("GUEST_READ"),
            }
        )

    bad = [r for r in rows if r["dangerous_absolute_high_writes"]]
    if bad:
        details = "; ".join(
            f"{r['function']}:{r['dangerous_absolute_high_writes'][0]['source']}"
            for r in bad
        )
        raise SystemExit(
            "[Phase6AR] direct initializer helper contains literal high-address "
            f"guest write: {details}"
        )
    return rows


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6ajD3DProbeRootCalls = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AR] inherited 6AJ state marker missing")

    state = r'''static DWORD s_phase6arInitCalls = 0u;
static DWORD s_phase6arInitPp = 0u;
static DWORD s_phase6arInitEspBefore = 0u;
static DWORD s_phase6arInitEspAfter = 0u;
static DWORD s_phase6arInitResult = 0u;
static DWORD s_phase6arCountBefore = 0u;
static DWORD s_phase6arCountAfter = 0u;
static DWORD s_phase6arSlot1Before = 0u;
static DWORD s_phase6arSlot1After = 0u;
static DWORD s_phase6arSlot2After = 0u;
static DWORD s_phase6arSlot3After = 0u;

'''
    return main_text.replace(marker, marker + state, 1)


def patch_createdevice(main_text: str) -> str:
    old = r'''    ++s_phase6aiInternalDevicePublishCount;
    s_phase6aiInternalDeviceLastValue = s_phase6afGuestDevice;

    ++s_phase6afCreateDeviceBridgeCount;
'''

    new = r'''    ++s_phase6aiInternalDevicePublishCount;
    s_phase6aiInternalDeviceLastValue = s_phase6afGuestDevice;

    /*
     * Retail sub_0028CAA0 reaches sub_0028F9E0 through 0x0028FF80 with
     * ECX=this device and one stack argument: the same D3D presentation
     * parameters pointer passed into CreateDevice. 0x0028FF80 also performs
     * original-Xbox KSEG writes, so restore only the proven guest-state
     * initializer rather than the unsafe parent routine.
     */
    s_phase6arCountBefore = GUEST_READ32(s_phase6afGuestDevice + 0x1A10u);
    s_phase6arSlot1Before = GUEST_READ32(s_phase6afGuestDevice + 0x1A14u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x0028AD90u, c);
        return;
    }

    s_phase6arInitPp = pp;
    s_phase6arInitEspBefore = g_esp;
    ++s_phase6arInitCalls;

    g_ecx = s_phase6afGuestDevice;
    PUSH32(g_esp, pp);
    PUSH32(g_esp, 0u);
    sub_0028F9E0();

    s_phase6arInitEspAfter = g_esp;
    s_phase6arInitResult = g_eax;

    if (s_accessFault)
    {
        return;
    }

    if (s_phase6arInitEspAfter != s_phase6arInitEspBefore)
    {
        trace("Phase 6AR retail D3D state init stack imbalance");
        phase4c_escape(
            PHASE4C_BOUNDARY_RENDERER_FATAL,
            s_phase6arInitEspAfter,
            s_phase6arInitEspBefore);
        return;
    }

    s_phase6arCountAfter = GUEST_READ32(s_phase6afGuestDevice + 0x1A10u);
    s_phase6arSlot1After = GUEST_READ32(s_phase6afGuestDevice + 0x1A14u);
    s_phase6arSlot2After = GUEST_READ32(s_phase6afGuestDevice + 0x1A18u);
    s_phase6arSlot3After = GUEST_READ32(s_phase6afGuestDevice + 0x1A1Cu);
    if (s_accessFault)
    {
        return;
    }

    if (((int32_t)s_phase6arInitResult < 0) ||
        s_phase6arCountAfter == 0u ||
        s_phase6arSlot1After == 0u)
    {
        char initLine[320];
        sprintf(
            initLine,
            "Phase 6AR retail D3D state init rejected: hr=%08X count=%u slot1=%08X slot2=%08X slot3=%08X",
            (unsigned int)s_phase6arInitResult,
            (unsigned int)s_phase6arCountAfter,
            (unsigned int)s_phase6arSlot1After,
            (unsigned int)s_phase6arSlot2After,
            (unsigned int)s_phase6arSlot3After);
        trace(initLine);
        phase4c_escape(
            PHASE4C_BOUNDARY_RENDERER_FATAL,
            s_phase6arInitResult,
            c);
        return;
    }

    ++s_phase6afCreateDeviceBridgeCount;
'''

    return replace_unique(
        main_text,
        old,
        new,
        "CreateDevice post-internal-publish block",
    )


def reset_state(main_text: str) -> str:
    marker = "    s_phase6ajD3DProbeStep = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AR] inherited 6AJ reset marker missing")
    extra = (
        "    s_phase6arInitCalls = 0u;\n"
        "    s_phase6arInitPp = 0u;\n"
        "    s_phase6arInitEspBefore = 0u;\n"
        "    s_phase6arInitEspAfter = 0u;\n"
        "    s_phase6arInitResult = 0u;\n"
        "    s_phase6arCountBefore = 0u;\n"
        "    s_phase6arCountAfter = 0u;\n"
        "    s_phase6arSlot1Before = 0u;\n"
        "    s_phase6arSlot1After = 0u;\n"
        "    s_phase6arSlot2After = 0u;\n"
        "    s_phase6arSlot3After = 0u;\n"
    )
    return main_text.replace(marker, extra + marker, 1)


def install_summary(main_text: str) -> str:
    marker = "P6AJ D3D SOURCE PROBE:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AR] inherited 6AJ summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 3600:
        raise SystemExit("[Phase6AR] could not locate inherited 6AJ summary")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AR POST-CREATE D3D INIT: calls=%u pp=%08X hr=%08X esp_before=%08X esp_after=%08X count_before=%u count_after=%u slot1_before=%08X slot1=%08X slot2=%08X slot3=%08X",\n'
        f'{indent}    (unsigned int)s_phase6arInitCalls,\n'
        f'{indent}    (unsigned int)s_phase6arInitPp,\n'
        f'{indent}    (unsigned int)s_phase6arInitResult,\n'
        f'{indent}    (unsigned int)s_phase6arInitEspBefore,\n'
        f'{indent}    (unsigned int)s_phase6arInitEspAfter,\n'
        f'{indent}    (unsigned int)s_phase6arCountBefore,\n'
        f'{indent}    (unsigned int)s_phase6arCountAfter,\n'
        f'{indent}    (unsigned int)s_phase6arSlot1Before,\n'
        f'{indent}    (unsigned int)s_phase6arSlot1After,\n'
        f'{indent}    (unsigned int)s_phase6arSlot2After,\n'
        f'{indent}    (unsigned int)s_phase6arSlot3After);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AR] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AR] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AR] translated body contains no functions")

    ends = []
    for match in matches:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6AR] translated function opening brace missing")
        ends.append(base.closing_brace(masked, brace))

    cuts = []
    chunk_start = 0
    last_end = 0
    for end in ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cuts.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cuts or cuts[-1] != last_end:
        cuts.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cuts):
        if end <= start:
            continue
        name = f"phase6ar_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AR] shard writer did not consume translated body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AR] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6ar_",
        "shard_count": len(shards),
        "shards": shards,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6aj-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AR] cached Phase 6AJ baseline missing: {path}")

    base = load(args.base_emitter, "phase6ar_base")
    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AR] cached Phase 6AJ baseline identity mismatch")

    aj = manifest.get("phase6aj_d3d_orange_source_probe") or {}
    if (
        aj.get("probe_only") is not True
        or aj.get("guest_semantics_changed") is not False
        or aj.get("phase6ai_hardware", {}).get("internal_device_global")
           != "0x00299380"
    ):
        raise SystemExit("[Phase6AR] inherited 6AJ model drift")

    required = (
        BASE_TAG,
        "static void sub_0028CAA0(void)",
        "static void sub_0028F9E0(void)",
        "GUEST_WRITE32(0x00299378u, s_phase6afGuestDevice);",
        "++s_phase6aiInternalDevicePublishCount;",
        "s_phase6aiInternalDeviceLastValue = s_phase6afGuestDevice;",
        "++s_phase6afCreateDeviceBridgeCount;",
        COOKIE_OLD,
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AR] inherited marker missing: {marker}")

    helper_audit = audit_helpers(main_text, base)
    print("[Phase6AR] Direct helper safety audit: PASS")
    for row in helper_audit:
        print(
            f"[Phase6AR]   {row['function']} reads={row['guest_reads']} "
            f"writes={row['guest_writes']} frontier={row['direct_frontier_calls']} "
            "high_abs_writes=0"
        )

    main_text = install_state(main_text)
    main_text = patch_createdevice(main_text)
    main_text = reset_state(main_text)
    main_text = install_summary(main_text)

    policy = (
        "Policy: inherit 6AJ/6AI native Xenos CreateDevice; restore only retail "
        "post-create sub_0028F9E0 with ECX=00299380 and arg1=pp; validate "
        "stack/count/slot; keep KSEG/NV2A/MMIO/VRAM and guest-fault fences hard"
    )
    if len(policy) > 240:
        raise SystemExit("[Phase6AR] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AJ", "PHASE 6AR")
        .replace("Phase 6AJ", "Phase 6AR")
        .replace('"P6AJ ', '"P6AR ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AJ", "PHASE 6AR")
        .replace("Phase 6AJ", "Phase 6AR")
    )

    must = (
        BUILD_TAG,
        "P6AR POST-CREATE D3D INIT:",
        "sub_0028F9E0();",
        "s_phase6arCountAfter == 0u",
        "s_phase6arSlot1After == 0u",
        COOKIE_NEW,
    )
    for marker in must:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AR] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6AR", "build_tag": BUILD_TAG})
    manifest["phase6ar_post_create_state_init"] = {
        "source_phase": "6AJ",
        "forensic_chain": {
            "6AN": "device+0x1A10 count=0 causes backward underflow",
            "6AO": "sole +0x1A10 writer is sub_0028F9E0",
            "6AP": "retail CreateDevice calls 0x0028FF80",
            "6AQ": "0x0028FF80 directly calls sub_0028F9E0",
        },
        "repair": {
            "function": "sub_0028F9E0",
            "this": "0x00299380",
            "arg1": "CreateDevice presentation parameters",
            "restore_parent_0x0028FF80": False,
            "reason_parent_not_restored": (
                "contains original-Xbox absolute writes to 0x80000000"
            ),
            "require_stack_balance": True,
            "require_nonnegative_hresult": True,
            "require_nonzero_1a10_count": True,
            "require_nonzero_1a14_slot1": True,
        },
        "direct_helper_safety_audit": helper_audit,
        "kseg_fence_relaxed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "source_layout": layout,
    }

    (args.out_dir / "phase6ar-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AR] POST-CREATE D3D STATE INIT REPAIR: READY")
    print("[Phase6AR] Retail initializer : sub_0028F9E0")
    print("[Phase6AR] ECX                : 0x00299380")
    print("[Phase6AR] arg1               : live CreateDevice pp")
    print("[Phase6AR] Parent 0028FF80    : NOT restored")
    print("[Phase6AR] KSEG/MMIO/VRAM     : unchanged / hard fenced")
    print("[Phase6AR] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
