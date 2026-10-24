#!/usr/bin/env python3
"""Phase 6AN-A: focused D3D device state-stack probe around sub_0028BC60.

6AL hardware identified the exact orange read:
    sub_0028BC60, generated line 1957
    ebp = GUEST_READ32(eax + 4)
with eax == 0x80000000.

6AM source forensics proved eax is loaded from the D3D device's small
+0x1A10-indexed state stack immediately before the dereference. This phase
inherits the proven 6AJ-A semantics and adds inline diagnostic state capture only:
capture +1A04/+1A08, count +1A10, entries +1A14/+1A18/+1A1C, the selected
top entry, and the exact loop slot that yields 0x80000000.

No KSEG, guest-memory, D3D, NV2A/MMIO/VRAM or ABI semantics are relaxed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
BUILD_TAG = "P6AN-D3D-STATE-STACK-PROBE-20261023-B"
COOKIE_OLD = "phase6aj_env_build_cookie"
COOKIE_NEW = "phase6an_env_build_cookie"
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AN] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AN] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AN] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AN] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


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
            f"[Phase6AN] expected one definition for {signature}, found {len(definitions)}"
        )
    start, brace = definitions[0]
    return start, base.closing_brace(masked, brace)


def install_state(main_text: str) -> str:
    marker = "static DWORD s_phase6ajD3DProbeRootCalls = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AN] inherited 6AJ probe-state marker missing")

    # State only. Keep this insertion source-order safe: the inherited 6AJ
    # probe globals live before the guest-access/trace helpers are declared.
    # All actual reads are injected inline into sub_0028BC60 below.
    state = r'''
static DWORD s_phase6anStackCalls = 0u;
static DWORD s_phase6anThis = 0u;
static DWORD s_phase6anCount = 0u;
static DWORD s_phase6anActive1A04 = 0u;
static DWORD s_phase6anDepth1A08 = 0u;
static DWORD s_phase6anField1A0C = 0u;
static DWORD s_phase6anSlot1 = 0u;
static DWORD s_phase6anSlot2 = 0u;
static DWORD s_phase6anSlot3 = 0u;
static DWORD s_phase6anTop = 0u;
static DWORD s_phase6anTop4 = 0u;
static DWORD s_phase6anTop8 = 0u;
static DWORD s_phase6anLoopCalls = 0u;
static DWORD s_phase6anSentinelHits = 0u;
static DWORD s_phase6anSentinelEdx = 0u;
static DWORD s_phase6anSentinelEdi = 0u;
static DWORD s_phase6anSentinelIndex = 0u;
static DWORD s_phase6anSentinelEax = 0u;
static DWORD s_phase6anSentinelEcx = 0u;
'''
    return main_text.replace(marker, marker + state, 1)


def instrument_target(main_text: str, base) -> str:
    signature = "static void sub_0028BC60(void)"
    start, end = find_definition(main_text, base, signature)
    body = main_text[start:end]

    old_entry = (
        "    edx = GUEST_READ32(esi + 0x1A10);\n"
        "    ecx = GUEST_READ32(esi + edx * 4 + 0x1A10);\n"
        "    eax = GUEST_READ32(ecx + 8);\n"
        "    PUSH32(esp, ebx);\n"
        "    ebx = GUEST_READ32(ecx + 4);"
    )
    new_entry = (
        "    edx = GUEST_READ32(esi + 0x1A10);\n"
        "    ecx = GUEST_READ32(esi + edx * 4 + 0x1A10);\n"
        "    eax = GUEST_READ32(ecx + 8);\n"
        "    PUSH32(esp, ebx);\n"
        "    ebx = GUEST_READ32(ecx + 4);\n"
        "    ++s_phase6anStackCalls;\n"
        "    s_phase6anThis = esi;\n"
        "    s_phase6anCount = edx;\n"
        "    s_phase6anTop = ecx;\n"
        "    s_phase6anTop4 = ebx;\n"
        "    s_phase6anTop8 = eax;\n"
        "    s_phase6anActive1A04 = GUEST_READ32(esi + 0x1A04);\n"
        "    s_phase6anDepth1A08 = GUEST_READ32(esi + 0x1A08);\n"
        "    s_phase6anField1A0C = GUEST_READ32(esi + 0x1A0C);\n"
        "    s_phase6anSlot1 = GUEST_READ32(esi + 0x1A14);\n"
        "    s_phase6anSlot2 = GUEST_READ32(esi + 0x1A18);\n"
        "    s_phase6anSlot3 = GUEST_READ32(esi + 0x1A1C);"
    )
    if body.count(old_entry) != 1:
        raise SystemExit("[Phase6AN] sub_0028BC60 entry shape drift")
    body = body.replace(old_entry, new_entry, 1)

    old_loop = (
        "    eax = GUEST_READ32(edi);\n"
        "    ebp = GUEST_READ32(eax + 4);"
    )
    new_loop = (
        "    eax = GUEST_READ32(edi);\n"
        "    ++s_phase6anLoopCalls;\n"
        "    if (eax == 0x80000000u)\n"
        "    {\n"
        "        ++s_phase6anSentinelHits;\n"
        "        s_phase6anSentinelEdx = edx;\n"
        "        s_phase6anSentinelEdi = edi;\n"
        "        s_phase6anSentinelEax = eax;\n"
        "        s_phase6anSentinelEcx = ecx;\n"
        "        if (edi >= esi + 0x1A10u)\n"
        "            s_phase6anSentinelIndex = (edi - (esi + 0x1A10u)) / 4u;\n"
        "        else\n"
        "            s_phase6anSentinelIndex = 0xFFFFFFFFu;\n"
        "    }\n"
        "    ebp = GUEST_READ32(eax + 4);"
    )
    if body.count(old_loop) != 1:
        raise SystemExit("[Phase6AN] sub_0028BC60 loop shape drift")
    body = body.replace(old_loop, new_loop, 1)

    return main_text[:start] + body + main_text[end:]


def reset_state(main_text: str) -> str:
    marker = "    s_phase6ajD3DProbeStep = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AN] inherited 6AJ reset marker missing")

    extra = (
        "    s_phase6anStackCalls = 0u;\n"
        "    s_phase6anThis = 0u;\n"
        "    s_phase6anCount = 0u;\n"
        "    s_phase6anActive1A04 = 0u;\n"
        "    s_phase6anDepth1A08 = 0u;\n"
        "    s_phase6anField1A0C = 0u;\n"
        "    s_phase6anSlot1 = 0u;\n"
        "    s_phase6anSlot2 = 0u;\n"
        "    s_phase6anSlot3 = 0u;\n"
        "    s_phase6anTop = 0u;\n"
        "    s_phase6anTop4 = 0u;\n"
        "    s_phase6anTop8 = 0u;\n"
        "    s_phase6anLoopCalls = 0u;\n"
        "    s_phase6anSentinelHits = 0u;\n"
        "    s_phase6anSentinelEdx = 0u;\n"
        "    s_phase6anSentinelEdi = 0u;\n"
        "    s_phase6anSentinelIndex = 0u;\n"
        "    s_phase6anSentinelEax = 0u;\n"
        "    s_phase6anSentinelEcx = 0u;\n"
    )
    return main_text.replace(marker, extra + marker, 1)


def install_summary(main_text: str) -> str:
    marker = "P6AJ D3D SOURCE PROBE:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AN] inherited 6AJ summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 4000:
        raise SystemExit("[Phase6AN] could not locate inherited 6AJ summary")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AN D3D STACK SUMMARY: calls=%u count=%u active=%08X depth=%08X field1A0C=%08X slot1=%08X slot2=%08X slot3=%08X top=%08X top4=%08X top8=%08X loop=%u sentinel_hits=%u sentinel_index=%u sentinel_edx=%u sentinel_ecx=%08X",\n'
        f'{indent}    (unsigned int)s_phase6anStackCalls,\n'
        f'{indent}    (unsigned int)s_phase6anCount,\n'
        f'{indent}    (unsigned int)s_phase6anActive1A04,\n'
        f'{indent}    (unsigned int)s_phase6anDepth1A08,\n'
        f'{indent}    (unsigned int)s_phase6anField1A0C,\n'
        f'{indent}    (unsigned int)s_phase6anSlot1,\n'
        f'{indent}    (unsigned int)s_phase6anSlot2,\n'
        f'{indent}    (unsigned int)s_phase6anSlot3,\n'
        f'{indent}    (unsigned int)s_phase6anTop,\n'
        f'{indent}    (unsigned int)s_phase6anTop4,\n'
        f'{indent}    (unsigned int)s_phase6anTop8,\n'
        f'{indent}    (unsigned int)s_phase6anLoopCalls,\n'
        f'{indent}    (unsigned int)s_phase6anSentinelHits,\n'
        f'{indent}    (unsigned int)s_phase6anSentinelIndex,\n'
        f'{indent}    (unsigned int)s_phase6anSentinelEdx,\n'
        f'{indent}    (unsigned int)s_phase6anSentinelEcx);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AN] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AN] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AN] translated body contains no functions")

    ends = []
    for match in matches:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6AN] translated function opening brace missing")
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
        name = f"phase6an_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AN] shard writer did not consume translated body")

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
        raise SystemExit("[Phase6AN] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6an_",
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
            raise SystemExit(f"[Phase6AN] cached Phase 6AJ-A baseline missing: {path}")

    base = load(args.base_emitter, "phase6an_base")
    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AN] cached Phase 6AJ-A baseline identity mismatch")

    aj = manifest.get("phase6aj_d3d_orange_source_probe") or {}
    if (
        aj.get("probe_only") is not True
        or aj.get("guest_semantics_changed") is not False
        or aj.get("phase6ai_hardware", {}).get("next_boundary", {}).get("guest")
           != "0x80000004"
    ):
        raise SystemExit("[Phase6AN] inherited Phase 6AJ model drift")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "static void sub_0028BC60(void)",
        "ebp = GUEST_READ32(eax + 4);",
        "P6AJ D3D FAULT PROBE: step=%u a=%08X b=%08X c=%08X",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AN] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = instrument_target(main_text, base)
    main_text = reset_state(main_text)
    main_text = install_summary(main_text)

    policy = (
        "Policy: inherit 6AJ-A; probe D3D device +1A10 state stack around "
        "0028BC60; preserve guest, KSEG, D3D, NV2A/MMIO/VRAM and ABI semantics"
    )
    if len(policy) > 240:
        raise SystemExit("[Phase6AN] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace("PHASE 6AJ", "PHASE 6AN").replace(
        "Phase 6AJ", "Phase 6AN"
    )
    env_text = env_text.replace("PHASE 6AJ", "PHASE 6AN").replace(
        "Phase 6AJ", "Phase 6AN"
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6AN D3D STACK SUMMARY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AN] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6AN", "build_tag": BUILD_TAG})
    manifest["phase6an_d3d_state_stack_probe"] = {
        "source_phase": "6AJ",
        "phase6al_hardware": {
            "fault": "READ32 0x80000004",
            "function": "0x0028BC60",
            "source": "ebp = GUEST_READ32(eax + 4)",
            "eax": "0x80000000",
        },
        "probe_only": True,
        "guest_semantics_changed": False,
        "device_offsets": [
            "0x1A04", "0x1A08", "0x1A0C",
            "0x1A10", "0x1A14", "0x1A18", "0x1A1C",
        ],
        "source_layout": layout,
    }
    (args.out_dir / "phase6an-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AN] D3D STATE-STACK PROBE: READY")
    print("[Phase6AN] Target: sub_0028BC60 / eax+4 orange read")
    print("[Phase6AN] Guest/KSEG/D3D/MMIO/VRAM semantics unchanged")
    print("[Phase6AN] Hardware money line: P6AN D3D STACK SUMMARY: ...")
    print("[Phase6AN] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
