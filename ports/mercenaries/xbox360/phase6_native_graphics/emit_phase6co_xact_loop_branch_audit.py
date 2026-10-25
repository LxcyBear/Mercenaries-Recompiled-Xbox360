#!/usr/bin/env python3
"""Phase 6CO: XACT loop termination/source audit after 6CN.

6CN hardware proved:
  * the 6CM ESI continuity repair remains 2/2 successful;
  * 002832F2 walks adjacent dwords from table base 0030266C;
  * live index pairs progress 2/1, 6/5, 14/13, then 28/27;
  * ESI+8 remains FFFFFFFF at the loop checks;
  * slots 28/27 are string bytes 782E6567 / 616D4965 and are then treated
    as object pointers by 00282BC2, causing READ32 782E657F.

6CO makes no semantic repair. It embeds the exact generated source blocks for
00283325/002832E7/002832F2/00282BC2 into the runtime log and adds bounded live
loop probes showing registers, ESI+8, table base, and the current/previous
dword selected by EBX.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CN-XACT-OBJECT-READ32-20261025-A"
BUILD_TAG = "P6CO-XACT-LOOP-BRANCH-AUDIT-20261025-A"
COOKIE_OLD = "phase6cn_env_build_cookie"
COOKIE_NEW = "phase6co_env_build_cookie"
EMITTER_REVISION = "6CO-R1"

PROBE_VAS = (
    0x00283325,
    0x002832E7,
    0x002832F2,
    0x00282BC2,
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CO] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CO] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def block_window(text: str, va: int) -> str:
    marker = f"loc_{va:08X}: ;\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"[Phase6CO] source label missing: {marker.strip()}")
    next_match = re.search(r"\nloc_[0-9A-Fa-f]{8}: ;\n", text[start + len(marker):])
    if next_match:
        end = start + len(marker) + next_match.start() + 1
    else:
        end = min(len(text), start + 12000)
    return text[start:end]


def c_escape(line: str) -> str:
    return (
        line.replace("\\", "\\\\")
        .replace('"', '\\"')
        .replace("\t", "    ")
    )


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6cnReadTraceFaultAddr = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CO] expected one 6CN trace-state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6coLoopProbeHits = 0u;
static DWORD s_phase6coLoopProbeLastVa = 0u;
static DWORD s_phase6coLoopProbeLastEbx = 0u;
static DWORD s_phase6coLoopProbeLastEdi = 0u;
static DWORD s_phase6coLoopProbeLastField8 = 0u;
static DWORD s_phase6coLoopProbeLastTable = 0u;
static DWORD s_phase6coLoopProbeLastCurAddr = 0u;
static DWORD s_phase6coLoopProbeLastCurValue = 0u;
static DWORD s_phase6coLoopProbeLastPrevAddr = 0u;
static DWORD s_phase6coLoopProbeLastPrevValue = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def probe_code(va: int) -> str:
    return f'''
    ++s_phase6coLoopProbeHits;
    s_phase6coLoopProbeLastVa = 0x{va:08X}u;
    s_phase6coLoopProbeLastEbx = ebx;
    s_phase6coLoopProbeLastEdi = edi;
    s_phase6coLoopProbeLastField8 = 0xDEAD0008u;
    s_phase6coLoopProbeLastTable = 0u;
    s_phase6coLoopProbeLastCurAddr = 0u;
    s_phase6coLoopProbeLastCurValue = 0u;
    s_phase6coLoopProbeLastPrevAddr = 0u;
    s_phase6coLoopProbeLastPrevValue = 0u;

    if (esi <= 0x03FFFFF4u)
    {{
        uint32_t phase6coTable = GUEST_READ32(esi);
        uint32_t phase6coField8 = GUEST_READ32(esi + 8u);
        uint32_t phase6coCurAddr = 0u;
        uint32_t phase6coPrevAddr = 0u;
        uint32_t phase6coCurValue = 0u;
        uint32_t phase6coPrevValue = 0u;

        s_phase6coLoopProbeLastField8 = phase6coField8;
        s_phase6coLoopProbeLastTable = phase6coTable;

        if (phase6coTable <= 0x03FFFFFCu && ebx <= 0x0000FFFFu)
        {{
            uint64_t phase6coWide = (uint64_t)phase6coTable + ((uint64_t)ebx * 4ull);
            if (phase6coWide <= 0x03FFFFFCull)
            {{
                phase6coCurAddr = (uint32_t)phase6coWide;
                phase6coCurValue = GUEST_READ32(phase6coCurAddr);
            }}

            if (ebx != 0u)
            {{
                phase6coWide = (uint64_t)phase6coTable + (((uint64_t)ebx - 1ull) * 4ull);
                if (phase6coWide <= 0x03FFFFFCull)
                {{
                    phase6coPrevAddr = (uint32_t)phase6coWide;
                    phase6coPrevValue = GUEST_READ32(phase6coPrevAddr);
                }}
            }}
        }}

        s_phase6coLoopProbeLastCurAddr = phase6coCurAddr;
        s_phase6coLoopProbeLastCurValue = phase6coCurValue;
        s_phase6coLoopProbeLastPrevAddr = phase6coPrevAddr;
        s_phase6coLoopProbeLastPrevValue = phase6coPrevValue;

        if (s_phase6coLoopProbeHits <= 24u)
        {{
            char phase6coLine[880];
            sprintf(
                phase6coLine,
                "P6CO LOOP va={va:08X} hit=%u eax=%08X ecx=%08X edx=%08X ebx=%u edi=%u esi=%08X esp=%08X field8=%08X field8_s=%d table=%08X cur_addr=%08X cur=%08X prev_addr=%08X prev=%08X",
                (unsigned int)s_phase6coLoopProbeHits,
                (unsigned int)eax,
                (unsigned int)ecx,
                (unsigned int)edx,
                (unsigned int)ebx,
                (unsigned int)edi,
                (unsigned int)esi,
                (unsigned int)esp,
                (unsigned int)phase6coField8,
                (int32_t)phase6coField8,
                (unsigned int)phase6coTable,
                (unsigned int)phase6coCurAddr,
                (unsigned int)phase6coCurValue,
                (unsigned int)phase6coPrevAddr,
                (unsigned int)phase6coPrevValue);
            trace(phase6coLine);
        }}
    }}
'''


def instrument_blocks(text: str) -> str:
    for va in PROBE_VAS:
        marker = f"loc_{va:08X}: ;\n"
        if text.count(marker) != 1:
            raise SystemExit(
                f"[Phase6CO] expected one probe label {marker.strip()}, "
                f"found {text.count(marker)}"
            )
        text = text.replace(marker, marker + probe_code(va), 1)
    return text


def inject_static_source_traces(text: str, blocks: dict[int, str]) -> str:
    policy_marker = 'trace("Policy:'
    policy_start = text.find(policy_marker)
    if policy_start < 0 or text.find(policy_marker, policy_start + 1) >= 0:
        raise SystemExit("[Phase6CO] expected exactly one runtime policy trace")
    policy_end = text.find("\n", policy_start)
    if policy_end < 0:
        raise SystemExit("[Phase6CO] runtime policy line is unterminated")
    insert_pos = policy_end + 1

    rows = []
    rows.append('    trace("P6CO STATIC SOURCE AUDIT BEGIN");')
    for va in PROBE_VAS:
        block = blocks[va]
        lines = [ln.rstrip() for ln in block.splitlines() if ln.strip()]
        if len(lines) > 16:
            lines = lines[:16]
        for idx, line in enumerate(lines, 1):
            safe = c_escape(line)
            rows.append(
                f'    trace("P6CO SRC {va:08X} {idx:02d}: {safe}");'
            )
    rows.append('    trace("P6CO STATIC SOURCE AUDIT END");')
    rows.append("")
    return text[:insert_pos] + "\n".join(rows) + "\n" + text[insert_pos:]


def insert_summary(text: str) -> str:
    marker = "P6CN XACT READ32:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CO] inherited 6CN XACT summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 9000:
        raise SystemExit("[Phase6CO] summary insertion point not found")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CO LOOP AUDIT: hits=%u last_va=%08X ebx=%u edi=%u field8=%08X table=%08X cur_addr=%08X cur=%08X prev_addr=%08X prev=%08X",\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeHits,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastVa,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastEbx,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastEdi,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastField8,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastTable,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastCurAddr,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastCurValue,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastPrevAddr,\n'
        f'{indent}    (unsigned int)s_phase6coLoopProbeLastPrevValue);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_policy(text: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0 or text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CO] expected exactly one runtime policy trace")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    policy = (
        "Phase 6CO preserves the hardware-proven 6CM ESI continuity repair and "
        "6CN XACT READ32 tracer, adds source/live audit only for 00283325/002832E7/"
        "002832F2/00282BC2, and changes no XACT branch, allocator, APU, IRQL, "
        "graphics, null/SEH or hard-fence semantics"
    )
    return text[:line_start] + indent + f'trace("Policy: {policy}");' + text[line_end:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CN", "PHASE 6CO")
        .replace("Phase 6CN", "Phase 6CO")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CO] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6co_base")
    p6bl = load(args.phase6bl_emitter, "phase6co_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cn-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CO] missing cached 6CN input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CN" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CO] cached Phase 6CN identity mismatch")

    cn = manifest.get("phase6cn_xact_object_read32", {})
    if (
        cn.get("xact_esi_repair_preserved") is not True
        or cn.get("translated_membership_changed") is not False
        or cn.get("hard_fences_changed") is not False
        or cn.get("execution_budget_inherited") != 32000000
    ):
        raise SystemExit("[Phase6CO] inherited 6CN policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6CN XACT READ32 TRACE ARMED",
        "P6CN XACT READ32:",
        "PASS: Phase 6CN restored XACT ESI at 002832CA",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CO] inherited marker missing: {marker}")

    blocks = {}
    for va in PROBE_VAS:
        block = block_window(main_text, va)
        blocks[va] = block
        print(f"[Phase6CO] SOURCE BLOCK {va:08X} BEGIN")
        for line in block.splitlines():
            print(f"[Phase6CO] | {line}")
        print(f"[Phase6CO] SOURCE BLOCK {va:08X} END")

    main_text = install_state(main_text)
    main_text = instrument_blocks(main_text)
    main_text = insert_summary(main_text)
    main_text = patch_policy(main_text)
    main_text = inject_static_source_traces(main_text, blocks)

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CN", "PHASE 6CO")
        .replace("Phase 6CN", "Phase 6CO")
        .replace('"P6CN ', '"P6CO ')
    )
    env_text = patch_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CO STATIC SOURCE AUDIT BEGIN",
        "P6CO SRC 00283325",
        "P6CO SRC 002832E7",
        "P6CO SRC 002832F2",
        "P6CO SRC 00282BC2",
        "P6CO LOOP va=002832F2",
        "P6CO LOOP AUDIT:",
        "PASS: Phase 6CO restored XACT ESI at 002832CA",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CO] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    source_report = args.out_dir / "phase6co-xact-loop-source.txt"
    report_rows = []
    for va in PROBE_VAS:
        report_rows.append(f"===== loc_{va:08X} =====")
        report_rows.append(blocks[va])
    source_report.write_text("\n".join(report_rows) + "\n", encoding="utf-8")

    manifest["phase"] = "6CO"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6co_xact_loop_branch_audit"] = {
        "source_phase": "6CN",
        "phase6cn_hardware": {
            "esi_restore_successes": 2,
            "xact_root": "0x01B5C320",
            "field8": "0xFFFFFFFF",
            "index_pairs": [
                [2, 1],
                [6, 5],
                [14, 13],
                [28, 27],
            ],
            "table_base": "0x0030266C",
            "bad_slot_28_address": "0x003026DC",
            "bad_slot_28_value": "0x782E6567",
            "bad_slot_27_address": "0x003026D8",
            "bad_slot_27_value": "0x616D4965",
            "fault_va": "0x00282BC2",
            "fault_address": "0x782E657F",
            "ticks": 26711680,
        },
        "probe_vas": [f"0x{x:08X}" for x in PROBE_VAS],
        "semantic_repair": False,
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "apu_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "graphics_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_changed": False,
        "execution_budget_inherited": 32000000,
        "source_report": source_report.name,
        "source_layout": layout,
    }

    (args.out_dir / "phase6co-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CO] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CO] embedded exact source for four XACT loop/comparator blocks")
    print("[Phase6CO] bounded live loop/table probes armed")
    print("[Phase6CO] no XACT branch or subsystem semantics changed")
    print("[Phase6CO] 32M execution budget preserved")
    print("[Phase6CO] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
