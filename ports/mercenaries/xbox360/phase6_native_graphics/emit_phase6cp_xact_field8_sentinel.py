#!/usr/bin/env python3
"""Phase 6CP: batch XACT field+8 writer provenance and sentinel-exit repair.

6CO hardware proved the complete downstream failure:
  * live XACT root ESI=01B5C320, table=0030266C;
  * [ESI+8] is 00000000 on visit 1, then FFFFFFFF on visit 2;
  * generated retail code uses the decoded unsigned jb/jae comparisons;
  * with FFFFFFFF as the bound/state, the walk advances 2/1 -> 6/5 ->
    14/13 -> 28/27 and reads adjacent string bytes as object pointers;
  * final fault is READ32(782E657F).

6CP deliberately batches two questions in one hardware build:
  1. wrap the global guest WRITE32 path and log the exact translated VA that
     writes FFFFFFFF to the live XACT root + 8;
  2. at the proven loop entry 002832E0 only, treat the exact FFFFFFFF
     sentinel on the exact live XACT root/table as the same no-walk exit used
     by the zero-state path (00283334), then continue the full 32M run.

No allocator, APU, IRQL, graphics, null/SEH or hard-fence policy is widened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CO-XACT-LOOP-BRANCH-AUDIT-20261025-A"
BUILD_TAG = "P6CP-XACT-FIELD8-SENTINEL-20261025-A"
COOKIE_OLD = "phase6co_env_build_cookie"
COOKIE_NEW = "phase6cp_env_build_cookie"
EMITTER_REVISION = "6CP-R1"

ROOT_VA = 0x002832E0
EXIT_VA = 0x00283334
TABLE_VA = 0x0030266C


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CP] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    in_string = False
    quote = ""
    escape = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise SystemExit("[Phase6CP] unterminated function body")


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6coLoopProbeLastPrevValue = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CP] expected one 6CO state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6cpField8WriteCalls = 0u;
static DWORD s_phase6cpField8FfffffffWrites = 0u;
static DWORD s_phase6cpField8LastWriterVa = 0u;
static DWORD s_phase6cpField8LastValue = 0u;
static DWORD s_phase6cpField8LastRoot = 0u;
static DWORD s_phase6cpSentinelChecks = 0u;
static DWORD s_phase6cpSentinelExits = 0u;
static DWORD s_phase6cpSentinelLastRoot = 0u;
static DWORD s_phase6cpSentinelLastField8 = 0u;
static DWORD s_phase6cpSentinelLastTable = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def wrap_write32(text: str) -> str:
    definition_re = re.compile(
        r"(?m)^(?P<prefix>(?:static\s+)?void\s+)"
        r"recomp_guest_write32\s*\(\s*uint32_t\s+address\s*,\s*"
        r"uint32_t\s+value\s*\)\s*\{"
    )
    matches = list(definition_re.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6CP] expected one recomp_guest_write32 definition, found {len(matches)}"
        )

    m = matches[0]
    open_pos = text.find("{", m.start(), m.end() + 1)
    close_pos = matching_brace(text, open_pos)
    original = text[m.start():close_pos + 1]

    renamed = original.replace(
        "recomp_guest_write32",
        "phase6cp_inherited_guest_write32",
        1,
    )

    wrapper = r"""
void recomp_guest_write32(uint32_t address, uint32_t value)
{
    uint32_t root = s_phase6ceXactLastEax;

    if (root != 0u &&
        root <= 0x03FFFFF4u &&
        address == root + 8u)
    {
        char line[760];
        ++s_phase6cpField8WriteCalls;
        s_phase6cpField8LastWriterVa = s_phase6cnCurrentVa;
        s_phase6cpField8LastValue = value;
        s_phase6cpField8LastRoot = root;

        if (value == 0xFFFFFFFFu)
        {
            ++s_phase6cpField8FfffffffWrites;
        }

        if (s_phase6cpField8WriteCalls <= 16u)
        {
            sprintf(
                line,
                "P6CP XACT FIELD8 WRITE call=%u va=%08X root=%08X addr=%08X value=%08X ffffffff_writes=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
                (unsigned int)s_phase6cpField8WriteCalls,
                (unsigned int)s_phase6cnCurrentVa,
                (unsigned int)root,
                (unsigned int)address,
                (unsigned int)value,
                (unsigned int)s_phase6cpField8FfffffffWrites,
                (unsigned int)g_eax,
                (unsigned int)g_ecx,
                (unsigned int)g_edx,
                (unsigned int)g_ebx,
                (unsigned int)g_esi,
                (unsigned int)g_edi,
                (unsigned int)g_esp);
            trace(line);
        }
    }

    phase6cp_inherited_guest_write32(address, value);
}
"""
    return text[:m.start()] + renamed + "\n\n" + wrapper + text[close_pos + 1:]


def install_sentinel_exit(text: str) -> str:
    marker = f"loc_{ROOT_VA:08X}: ;\n"
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6CP] expected one sentinel entry {marker.strip()}, "
            f"found {text.count(marker)}"
        )
    if f"loc_{EXIT_VA:08X}: ;\n" not in text:
        raise SystemExit(f"[Phase6CP] sentinel exit loc_{EXIT_VA:08X} missing")

    code = f'''    ++s_phase6cpSentinelChecks;
    s_phase6cpSentinelLastRoot = esi;
    s_phase6cpSentinelLastField8 = 0xDEAD0008u;
    s_phase6cpSentinelLastTable = 0u;

    if (esi != 0u &&
        esi == s_phase6ceXactLastEax &&
        (esi & 3u) == 0u &&
        esi <= 0x03FFFFF4u)
    {{
        uint32_t phase6cpTable = phase6cn_inherited_guest_read32(esi);
        uint32_t phase6cpField8 = phase6cn_inherited_guest_read32(esi + 8u);
        s_phase6cpSentinelLastField8 = phase6cpField8;
        s_phase6cpSentinelLastTable = phase6cpTable;

        if (phase6cpTable == 0x{TABLE_VA:08X}u &&
            phase6cpField8 == 0xFFFFFFFFu)
        {{
            char phase6cpLine[760];
            ++s_phase6cpSentinelExits;
            sprintf(
                phase6cpLine,
                "PASS: Phase 6CP XACT field8 sentinel exit va={ROOT_VA:08X} root=%08X table=%08X field8=%08X writer_va=%08X writer_value=%08X writes=%u ffffffff_writes=%u exits=%u",
                (unsigned int)esi,
                (unsigned int)phase6cpTable,
                (unsigned int)phase6cpField8,
                (unsigned int)s_phase6cpField8LastWriterVa,
                (unsigned int)s_phase6cpField8LastValue,
                (unsigned int)s_phase6cpField8WriteCalls,
                (unsigned int)s_phase6cpField8FfffffffWrites,
                (unsigned int)s_phase6cpSentinelExits);
            trace(phase6cpLine);
            goto loc_{EXIT_VA:08X};
        }}
    }}
'''
    return text.replace(marker, marker + code, 1)


def insert_summary(text: str) -> str:
    marker = "P6CO LOOP AUDIT:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CP] inherited 6CO loop summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 9000:
        raise SystemExit("[Phase6CP] summary insertion point not found")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CP XACT FIELD8: writes=%u ffffffff_writes=%u writer_va=%08X writer_value=%08X writer_root=%08X sentinel_checks=%u sentinel_exits=%u sentinel_root=%08X sentinel_field8=%08X sentinel_table=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cpField8WriteCalls,\n'
        f'{indent}    (unsigned int)s_phase6cpField8FfffffffWrites,\n'
        f'{indent}    (unsigned int)s_phase6cpField8LastWriterVa,\n'
        f'{indent}    (unsigned int)s_phase6cpField8LastValue,\n'
        f'{indent}    (unsigned int)s_phase6cpField8LastRoot,\n'
        f'{indent}    (unsigned int)s_phase6cpSentinelChecks,\n'
        f'{indent}    (unsigned int)s_phase6cpSentinelExits,\n'
        f'{indent}    (unsigned int)s_phase6cpSentinelLastRoot,\n'
        f'{indent}    (unsigned int)s_phase6cpSentinelLastField8,\n'
        f'{indent}    (unsigned int)s_phase6cpSentinelLastTable);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_policy(text: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0 or text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CP] expected exactly one runtime policy trace")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    policy = (
        "Phase 6CP batches the 6CO XACT field+8 investigation: globally record writes "
        "to the exact live XACT root+8 and, only at 002832E0 with root/table identity "
        "proven and field8==FFFFFFFF, take the no-walk exit 00283334; preserve 6CM ESI "
        "continuity, 6CJ allocator, APU GP/EP, guest IRQL, graphics/file/IDEX, null/SEH, "
        "32M watchdog, translated membership and every hard fence"
    )
    return text[:line_start] + indent + f'trace("Policy: {policy}");' + text[line_end:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CO", "PHASE 6CP")
        .replace("Phase 6CO", "Phase 6CP")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CP] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cp_base")
    p6bl = load(args.phase6bl_emitter, "phase6cp_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6co-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CP] missing cached 6CO input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CO" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CP] cached Phase 6CO identity mismatch")

    co = manifest.get("phase6co_xact_loop_branch_audit", {})
    if (
        co.get("semantic_repair") is not False
        or co.get("translated_membership_changed") is not False
        or co.get("hard_fences_changed") is not False
        or co.get("execution_budget_inherited") != 32000000
    ):
        raise SystemExit("[Phase6CP] inherited 6CO policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6CO LOOP AUDIT:",
        "PASS: Phase 6CO restored XACT ESI at 002832CA",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "loc_002832E0: ;",
        "loc_00283334: ;",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CP] inherited marker missing: {marker}")

    # Preserve a source extract around the repaired path for local inspection.
    src_start = main_text.find("loc_002832CA: ;")
    src_end = main_text.find("loc_00283340: ;", src_start)
    if src_start < 0 or src_end < 0:
        raise SystemExit("[Phase6CP] could not isolate XACT loop source window")
    source_window = main_text[src_start:src_end]

    main_text = install_state(main_text)
    main_text = wrap_write32(main_text)
    main_text = install_sentinel_exit(main_text)
    main_text = insert_summary(main_text)
    main_text = patch_policy(main_text)

    if main_text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CP] expected one inherited build tag, found {main_text.count(BASE_TAG)}"
        )
    main_text = main_text.replace(BASE_TAG, BUILD_TAG, 1)
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CO", "PHASE 6CP")
        .replace("Phase 6CO", "Phase 6CP")
        .replace('"P6CO ', '"P6CP ')
    )
    env_text = patch_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CP XACT FIELD8 WRITE",
        "PASS: Phase 6CP XACT field8 sentinel exit",
        "P6CP XACT FIELD8:",
        "PASS: Phase 6CP restored XACT ESI at 002832CA",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CP] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")
    (args.out_dir / "phase6cp-xact-loop-source.txt").write_text(
        source_window,
        encoding="utf-8",
    )

    manifest["phase"] = "6CP"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cp_xact_field8_sentinel"] = {
        "source_phase": "6CO",
        "phase6co_hardware": {
            "xact_root": "0x01B5C320",
            "table": "0x0030266C",
            "field8_visit1": "0x00000000",
            "field8_visit2": "0xFFFFFFFF",
            "field8_signed": -1,
            "index_pairs": [[2, 1], [6, 5], [14, 13], [28, 27]],
            "slot28": "0x782E6567",
            "slot27": "0x616D4965",
            "fault_address": "0x782E657F",
            "esi_restore_successes": 2,
        },
        "writer_probe": "global recomp_guest_write32 exact root+8",
        "sentinel_entry_va": "0x002832E0",
        "sentinel_exit_va": "0x00283334",
        "sentinel_table": "0x0030266C",
        "sentinel_value": "0xFFFFFFFF",
        "repair_scope": "exact XACT root + exact table + exact sentinel + exact loop entry",
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "apu_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "graphics_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_changed": False,
        "execution_budget_inherited": 32000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cp-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CP] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CP] global XACT root+8 WRITE32 provenance armed")
    print("[Phase6CP] exact FFFFFFFF sentinel no-walk exit armed at 002832E0")
    print("[Phase6CP] 6CM ESI continuity repair preserved")
    print("[Phase6CP] allocator/APU/IRQL/graphics/hard-fence policies preserved")
    print("[Phase6CP] 32M execution budget preserved")
    print("[Phase6CP] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
