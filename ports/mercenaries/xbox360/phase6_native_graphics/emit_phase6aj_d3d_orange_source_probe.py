#!/usr/bin/env python3
"""Phase 6AJ-A: pinpoint the 6AI-D orange D3D read without changing semantics.

6AI-D hardware proved the internal D3D current-device publication is correct:
  0x00299378 == 0x00299380
  sub_0028E700 this == 0x00299380
  this + 0x1C20 == 0x0029AFA0

The orange READ32 0x80000004 nevertheless remains. 6AJ adds only a host-side
source-step latch around the small sub_0028E700 region and reports that latch
from phase4c_note_access_fault. No guest memory, KSEG, D3D, MMIO, VRAM, ABI,
or synchronization semantics are changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D"
BUILD_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
COOKIE_OLD = "phase6ai_env_build_cookie"
COOKIE_NEW = "phase6aj_env_build_cookie"
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AJ] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AJ] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AJ] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AJ] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


def install_probe_state(main_text: str) -> str:
    marker = "static int s_accessFault = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AJ] access-fault state marker missing")

    block = (
        marker
        + "static DWORD s_phase6ajD3DProbeStep = 0u;\n"
        + "static DWORD s_phase6ajD3DProbeA = 0u;\n"
        + "static DWORD s_phase6ajD3DProbeB = 0u;\n"
        + "static DWORD s_phase6ajD3DProbeC = 0u;\n"
        + "static DWORD s_phase6ajD3DProbeRootCalls = 0u;\n"
    )
    return main_text.replace(marker, block, 1)


def instrument_fault_report(main_text: str) -> str:
    marker = '''        trace(line);
    }
    s_accessFault = 1;

    /*
     * Boundary kind 6 is PHASE4C_BOUNDARY_GUEST_FAULT.'''
    if marker not in main_text:
        raise SystemExit("[Phase6AJ] phase4c fault-report marker missing")

    replacement = '''        trace(line);
        if (s_phase6ajD3DProbeStep != 0u)
        {
            sprintf(
                line,
                "P6AJ D3D FAULT PROBE: step=%u a=%08X b=%08X c=%08X",
                (unsigned int)s_phase6ajD3DProbeStep,
                (unsigned int)s_phase6ajD3DProbeA,
                (unsigned int)s_phase6ajD3DProbeB,
                (unsigned int)s_phase6ajD3DProbeC);
            trace(line);
        }
    }
    s_accessFault = 1;

    /*
     * Boundary kind 6 is PHASE4C_BOUNDARY_GUEST_FAULT.'''
    return main_text.replace(marker, replacement, 1)


def find_definition(main_text: str, base, signature: str) -> tuple[int, int]:
    masked = base.mask_noncode(main_text)
    definitions = []
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
            definitions.append((pos, probe))
        cursor = after
    if len(definitions) != 1:
        raise SystemExit(
            f"[Phase6AJ] expected one definition for {signature}, found {len(definitions)}"
        )
    start, brace = definitions[0]
    return start, base.closing_brace(masked, brace)


def instrument_root(main_text: str, base) -> str:
    signature = "static void sub_0028E700(void)"
    start, end = find_definition(main_text, base, signature)
    body = main_text[start:end]

    replacements = [
        (
            "    esi = ecx;\n    phase6ai_d3d_root_checkpoint(esi);\n    eax = GUEST_READ32(esi + 8);",
            "    esi = ecx;\n"
            "    ++s_phase6ajD3DProbeRootCalls;\n"
            "    phase6ai_d3d_root_checkpoint(esi);\n"
            "    s_phase6ajD3DProbeStep = 1u; s_phase6ajD3DProbeA = esi; s_phase6ajD3DProbeB = esi + 8u; s_phase6ajD3DProbeC = 0u;\n"
            "    eax = GUEST_READ32(esi + 8);",
            "root entry/read +8",
        ),
        (
            "    edx = GUEST_READ32(esi + 0x770);",
            "    s_phase6ajD3DProbeStep = 2u; s_phase6ajD3DProbeA = esi; s_phase6ajD3DProbeB = esi + 0x770u; s_phase6ajD3DProbeC = eax;\n"
            "    edx = GUEST_READ32(esi + 0x770);",
            "root read +770",
        ),
        (
            "    edx = GUEST_READ32(esi);",
            "    s_phase6ajD3DProbeStep = 3u; s_phase6ajD3DProbeA = esi; s_phase6ajD3DProbeB = esi; s_phase6ajD3DProbeC = eax;\n"
            "    edx = GUEST_READ32(esi);",
            "root read +0",
        ),
        (
            "    ecx = GUEST_READ32(esi + 0x1C20);",
            "    s_phase6ajD3DProbeStep = 4u; s_phase6ajD3DProbeA = esi; s_phase6ajD3DProbeB = esi + 0x1C20u; s_phase6ajD3DProbeC = edx;\n"
            "    ecx = GUEST_READ32(esi + 0x1C20);",
            "root read +1c20",
        ),
        (
            "    GUEST_WRITE32(ecx + 0x40, edx);",
            "    s_phase6ajD3DProbeStep = 5u; s_phase6ajD3DProbeA = ecx; s_phase6ajD3DProbeB = ecx + 0x40u; s_phase6ajD3DProbeC = edx;\n"
            "    GUEST_WRITE32(ecx + 0x40, edx);",
            "root write field +40",
        ),
        (
            "    eax = GUEST_READ32(0x298ED0);",
            "    s_phase6ajD3DProbeStep = 6u; s_phase6ajD3DProbeA = 0x00298ED0u; s_phase6ajD3DProbeB = esi; s_phase6ajD3DProbeC = ecx;\n"
            "    eax = GUEST_READ32(0x298ED0);",
            "root read 298ed0",
        ),
        (
            "    if (TEST_Z(eax, eax)) goto loc_0028E7AE; /* je: equal / zero */",
            "    s_phase6ajD3DProbeStep = 7u; s_phase6ajD3DProbeA = eax; s_phase6ajD3DProbeB = esi; s_phase6ajD3DProbeC = 0u;\n"
            "    if (TEST_Z(eax, eax)) goto loc_0028E7AE; /* je: equal / zero */",
            "root branch after 298ed0",
        ),
        (
            "loc_0028E764: ;\n    PHASE4C_BUDGET_TICK(0x0028E764u);\n    recomp_d3d_sync_checkpoint(4u);",
            "loc_0028E764: ;\n"
            "    s_phase6ajD3DProbeStep = 8u; s_phase6ajD3DProbeA = eax; s_phase6ajD3DProbeB = esi; s_phase6ajD3DProbeC = s_accessFault;\n"
            "    PHASE4C_BUDGET_TICK(0x0028E764u);\n"
            "    recomp_d3d_sync_checkpoint(4u);",
            "root e764 entry",
        ),
        (
            "    PUSH32(esp, 0); sub_0028A060(); /* call 0x0028A060 */",
            "    s_phase6ajD3DProbeStep = 9u; s_phase6ajD3DProbeA = eax; s_phase6ajD3DProbeB = esi; s_phase6ajD3DProbeC = esp;\n"
            "    PUSH32(esp, 0); sub_0028A060(); /* call 0x0028A060 */",
            "root call 28a060",
        ),
        (
            "loc_0028E7AE: ;\n    PHASE4C_BUDGET_TICK(0x0028E7AEu);",
            "loc_0028E7AE: ;\n"
            "    s_phase6ajD3DProbeStep = 10u; s_phase6ajD3DProbeA = eax; s_phase6ajD3DProbeB = esi; s_phase6ajD3DProbeC = 0u;\n"
            "    PHASE4C_BUDGET_TICK(0x0028E7AEu);",
            "root return path",
        ),
    ]

    for old, new, label in replacements:
        count = body.count(old)
        if count != 1:
            raise SystemExit(f"[Phase6AJ] expected one {label}, found {count}")
        body = body.replace(old, new, 1)

    return main_text[:start] + body + main_text[end:]


def reset_state(main_text: str) -> str:
    marker = "    s_phase6aiInternalDevicePublishCount = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AJ] inherited 6AI reset marker missing")
    extra = (
        "    s_phase6ajD3DProbeStep = 0u;\n"
        "    s_phase6ajD3DProbeA = 0u;\n"
        "    s_phase6ajD3DProbeB = 0u;\n"
        "    s_phase6ajD3DProbeC = 0u;\n"
        "    s_phase6ajD3DProbeRootCalls = 0u;\n"
    )
    return main_text.replace(marker, extra + marker, 1)


def install_summary(main_text: str) -> str:
    marker = "P6AI INTERNAL D3D DEVICE:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AJ] inherited 6AI summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 3600:
        raise SystemExit("[Phase6AJ] could not locate inherited 6AI summary")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AJ D3D SOURCE PROBE: root_calls=%u last_step=%u a=%08X b=%08X c=%08X",\n'
        f'{indent}    (unsigned int)s_phase6ajD3DProbeRootCalls,\n'
        f'{indent}    (unsigned int)s_phase6ajD3DProbeStep,\n'
        f'{indent}    (unsigned int)s_phase6ajD3DProbeA,\n'
        f'{indent}    (unsigned int)s_phase6ajD3DProbeB,\n'
        f'{indent}    (unsigned int)s_phase6ajD3DProbeC);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AJ] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AJ] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AJ] translated body contains no functions")

    ends = []
    for match in matches:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6AJ] translated function opening brace missing")
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
        name = f"phase6aj_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({"name": name, "chars": len(payload), "lines": payload.count("\n") + 1})
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AJ] shard writer did not consume translated body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8") for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AJ] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6aj_",
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
    base_manifest = args.base_dir / "phase6ai-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AJ] cached Phase 6AI-D baseline missing: {path}")

    base = load(args.base_emitter, "phase6aj_base")
    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AI" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AJ] cached Phase 6AI-D baseline identity mismatch")

    ai = manifest.get("phase6ai_internal_d3d_device_global") or {}
    if (
        ai.get("forensic", {}).get("root") != "0x0028E700"
        or ai.get("repair", {}).get("createdevice_internal_global") != "0x00299378"
        or ai.get("repair", {}).get("published_value") != "0x00299380"
    ):
        raise SystemExit("[Phase6AJ] inherited Phase 6AI model drift")

    required = (
        BASE_TAG,
        "phase6ai_d3d_root_checkpoint(esi);",
        "GUEST_WRITE32(0x00299378u, s_phase6afGuestDevice);",
        "PHASE 6AI INTERNAL D3D DEVICE RESULT: %s",
        COOKIE_OLD,
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AJ] inherited marker missing: {marker}")

    main_text = install_probe_state(main_text)
    main_text = instrument_fault_report(main_text)
    main_text = instrument_root(main_text, base)
    main_text = reset_state(main_text)
    main_text = install_summary(main_text)

    policy = (
        "Policy: inherit 6AI-D unchanged; latch exact sub_0028E700 source step "
        "for orange guest-fault diagnosis; preserve D3D, KSEG, NV2A/MMIO/VRAM, "
        "ABI and guest-memory semantics"
    )
    if len(policy) > 240:
        raise SystemExit("[Phase6AJ] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AI", "PHASE 6AJ")
        .replace("Phase 6AI", "Phase 6AJ")
        .replace('"P6AI ', '"P6AJ ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AI", "PHASE 6AJ")
        .replace("Phase 6AI", "Phase 6AJ")
    )

    must = (
        BUILD_TAG,
        "P6AJ D3D FAULT PROBE: step=%u a=%08X b=%08X c=%08X",
        "P6AJ D3D SOURCE PROBE: root_calls=%u last_step=%u a=%08X b=%08X c=%08X",
        "s_phase6ajD3DProbeStep = 9u;",
        "phase6aj_env_build_cookie",
    )
    for marker in must:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AJ] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6AJ", "build_tag": BUILD_TAG})
    manifest["phase6aj_d3d_orange_source_probe"] = {
        "source_phase": "6AI",
        "phase6ai_hardware_pass": True,
        "phase6ai_hardware": {
            "internal_device_result": "PASS",
            "root_this": "0x00299380",
            "internal_device_global": "0x00299380",
            "field_1c20_address": "0x0029AFA0",
            "next_boundary": {
                "kind": "GUEST_FAULT",
                "access": "READ",
                "width": 4,
                "guest": "0x80000004",
                "eax": "0x80000000",
                "esi": "0x00299380",
            },
        },
        "probe_only": True,
        "guest_semantics_changed": False,
        "steps": {
            "1": "read this+8",
            "2": "read this+0x770",
            "3": "read this+0",
            "4": "read this+0x1C20",
            "5": "write *(this+0x1C20)+0x40",
            "6": "read 0x00298ED0",
            "7": "branch after 0x00298ED0 read",
            "8": "enter loc_0028E764 before budget tick/checkpoint4",
            "9": "call sub_0028A060",
            "10": "return path loc_0028E7AE",
        },
        "source_layout": layout,
    }

    (args.out_dir / "phase6aj-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AJ] D3D ORANGE SOURCE PROBE: READY")
    print("[Phase6AJ] No guest/D3D/KSEG/MMIO semantics changed")
    print("[Phase6AJ] Fault handler will report exact sub_0028E700 source step")
    print("[Phase6AJ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
