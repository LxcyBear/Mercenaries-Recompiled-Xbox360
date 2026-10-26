#!/usr/bin/env python3
r"""Phase 6DB: identify the direct producer of DSOUND FBE2 arg1=0x00041D90.

6DA hardware proved:
  sub_0029F992 entry arg1 = 0x00041D88
  then unchanged through 0029EBEA -> 0029EA79 -> 002A41EE
  where [0x00041D88] = 0xCCCCCCCC and [eax+4] faults at 0xCCCCCCD0.

Static generated source proves sub_0029FBE2 calls sub_0029F992 with:
  F992.arg1 = FBE2.arg1 ? (FBE2.arg1 - 8) : 0
and forwards FBE2 args 2..4 unchanged.

Therefore the failing FBE2 invocation must have:
  arg1 = 0x00041D90
  arg2 = 0x008BF924
  arg3 = 0x01B5DE7C
  arg4 = 0

6DB instruments every direct call site to sub_0029FBE2 immediately before the
translated dummy return is pushed, logging owner/call-site identity plus the
four already-pushed arguments.  It also logs FBE2 entry for cross-checking.

No pointer is substituted and no fault is suppressed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DA-DSOUND-ARG-LINEAGE-00041D88-20261026-A"
BUILD_TAG = "P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A"
COOKIE_OLD = "phase6da_env_build_cookie"
COOKIE_NEW = "phase6db_env_build_cookie"
EMITTER_REVISION = "6DB-R1"

TARGET_NAME = "sub_0029FBE2"
TARGET_VA = 0x0029FBE2


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DB] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def function_defs(text: str, base):
    masked = base.mask_noncode(text)
    rows = []
    for m in base.FUNC_RE.finditer(masked):
        name = m.group(1)
        open_pos = masked.find("{", m.start(), m.end())
        if open_pos < 0:
            continue
        end = base.closing_brace(masked, open_pos)
        va = 0
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if vm:
            va = int(vm.group(1), 16)
        rows.append({
            "name": name,
            "va": va,
            "start": m.start(),
            "open": open_pos,
            "end": end,
        })
    return rows


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6daArgLineageReports = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DB] expected one 6DA state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6dbFbe2CallerReports = 0u;
static DWORD s_phase6dbFbe2LastCaller = 0u;
static DWORD s_phase6dbFbe2LastSite = 0u;
static DWORD s_phase6dbFbe2LastArg1 = 0u;
static DWORD s_phase6dbFbe2LastArg2 = 0u;
static DWORD s_phase6dbFbe2LastArg3 = 0u;
static DWORD s_phase6dbFbe2LastArg4 = 0u;
static DWORD s_phase6dbFbe2EntryReports = 0u;
static DWORD s_phase6dbFbe2EntryArg1 = 0u;

"""
    return text.replace(anchor, state + anchor, 1)


def patch_fbe2_entry(text: str) -> str:
    pat = re.compile(
        r"(?m)^\s*(?:static\s+)?void\s+sub_0029FBE2\(void\)\s*\{"
    )
    matches = list(pat.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6DB] expected one FBE2 body, found {len(matches)}"
        )
    start = matches[0].start()
    trace_marker = "    RECOMP_TRACE_FUNC(0x0029FBE2u);\n"
    pos = text.find(trace_marker, matches[0].end())
    if pos < 0 or pos - start > 4096:
        raise SystemExit("[Phase6DB] FBE2 entry trace marker missing")

    block = r'''    {
        DWORD phase6dbArg1 = GUEST_READ32(esp + 4u);
        DWORD phase6dbArg2 = GUEST_READ32(esp + 8u);
        DWORD phase6dbArg3 = GUEST_READ32(esp + 12u);
        DWORD phase6dbArg4 = GUEST_READ32(esp + 16u);
        char phase6dbLine[448];

        ++s_phase6dbFbe2EntryReports;
        s_phase6dbFbe2EntryArg1 = phase6dbArg1;
        sprintf(
            phase6dbLine,
            "P6DB FBE2 ENTRY: esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X eax=%08X ecx=%08X edx=%08X esi=%08X reports=%u",
            (unsigned int)esp,
            (unsigned int)phase6dbArg1,
            (unsigned int)phase6dbArg2,
            (unsigned int)phase6dbArg3,
            (unsigned int)phase6dbArg4,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)esi,
            (unsigned int)s_phase6dbFbe2EntryReports);
        trace(phase6dbLine);
    }
'''
    return text[:pos] + block + text[pos:]


def patch_direct_callers(text: str, base):
    needle = "PUSH32(esp, 0); sub_0029FBE2(); /* call 0x0029FBE2 */"
    defs = function_defs(text, base)
    sites = []

    # Find occurrences in actual translated function bodies.
    for row in defs:
        cursor = row["open"]
        while True:
            pos = text.find(needle, cursor, row["end"])
            if pos < 0:
                break
            line_start = text.rfind("\n", row["open"], pos) + 1
            line_end = text.find("\n", pos, row["end"])
            if line_end < 0:
                line_end = row["end"]
            line = text[line_start:line_end]
            indent = line[:len(line) - len(line.lstrip())]
            sites.append({
                "owner_name": row["name"],
                "owner_va": row["va"],
                "pos": pos,
                "line_start": line_start,
                "line_end": line_end,
                "indent": indent,
            })
            cursor = pos + len(needle)

    if not sites:
        raise SystemExit("[Phase6DB] no direct call sites to sub_0029FBE2 found")

    # Apply from end so offsets remain valid.
    for index, site in reversed(list(enumerate(sites, 1))):
        indent = site["indent"]
        owner_va = site["owner_va"]
        owner_name = site["owner_name"]
        block = (
            f'{indent}{{\n'
            f'{indent}    DWORD phase6dbArg1 = GUEST_READ32(esp);\n'
            f'{indent}    DWORD phase6dbArg2 = GUEST_READ32(esp + 4u);\n'
            f'{indent}    DWORD phase6dbArg3 = GUEST_READ32(esp + 8u);\n'
            f'{indent}    DWORD phase6dbArg4 = GUEST_READ32(esp + 12u);\n'
            f'{indent}    char phase6dbLine[512];\n'
            f'{indent}    ++s_phase6dbFbe2CallerReports;\n'
            f'{indent}    s_phase6dbFbe2LastCaller = 0x{owner_va:08X}u;\n'
            f'{indent}    s_phase6dbFbe2LastSite = {index}u;\n'
            f'{indent}    s_phase6dbFbe2LastArg1 = phase6dbArg1;\n'
            f'{indent}    s_phase6dbFbe2LastArg2 = phase6dbArg2;\n'
            f'{indent}    s_phase6dbFbe2LastArg3 = phase6dbArg3;\n'
            f'{indent}    s_phase6dbFbe2LastArg4 = phase6dbArg4;\n'
            f'{indent}    sprintf(\n'
            f'{indent}        phase6dbLine,\n'
            f'{indent}        "P6DB FBE2 CALLER: site={index} caller={owner_va:08X} name={owner_name} esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X eax=%08X ecx=%08X edx=%08X esi=%08X edi=%08X reports=%u",\n'
            f'{indent}        (unsigned int)esp,\n'
            f'{indent}        (unsigned int)phase6dbArg1,\n'
            f'{indent}        (unsigned int)phase6dbArg2,\n'
            f'{indent}        (unsigned int)phase6dbArg3,\n'
            f'{indent}        (unsigned int)phase6dbArg4,\n'
            f'{indent}        (unsigned int)eax,\n'
            f'{indent}        (unsigned int)ecx,\n'
            f'{indent}        (unsigned int)edx,\n'
            f'{indent}        (unsigned int)esi,\n'
            f'{indent}        (unsigned int)edi,\n'
            f'{indent}        (unsigned int)s_phase6dbFbe2CallerReports);\n'
            f'{indent}    trace(phase6dbLine);\n'
            f'{indent}}}\n'
            f'{indent}{needle}'
        )
        text = text[:site["line_start"]] + block + text[site["line_end"]:]

    audit = [
        {
            "site": i,
            "caller_name": s["owner_name"],
            "caller_va": f"0x{s['owner_va']:08X}",
        }
        for i, s in enumerate(sites, 1)
    ]
    return text, audit


def insert_summary(text: str) -> str:
    marker = "P6DA DSOUND ARG LINEAGE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DB] inherited 6DA summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DB] summary insertion point changed")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DB FBE2 PROVENANCE: caller_reports=%u last_site=%u caller=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X entry_reports=%u entry_arg1=%08X",\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2CallerReports,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2LastSite,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2LastCaller,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2LastArg1,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2LastArg2,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2LastArg3,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2LastArg4,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2EntryReports,\n'
        f'{indent}    (unsigned int)s_phase6dbFbe2EntryArg1);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DB] expected one 6DA build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DA", "PHASE 6DB")
        .replace("Phase 6DA", "Phase 6DB")
        .replace('"P6DA ', '"P6DB ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DB] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DA", "PHASE 6DB")
        .replace("Phase 6DA", "Phase 6DB")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6db_base")
    p6bl = load(args.phase6bl_emitter, "phase6db_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6da-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6DB] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DA" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DB] cached 6DA identity mismatch")

    da = manifest.get("phase6da_dsound_argument_lineage", {})
    if (
        da.get("probe_only") is not True
        or da.get("guest_memory_semantics_changed") is not False
        or da.get("value_fabrication") is not False
        or da.get("address_range_widened") is not False
        or da.get("execution_budget_inherited") != 64000000
        or da.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DB] inherited 6DA policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DA DSOUND ARG: stage=1 func=0029F992",
        "P6DA PREFAULT ROUTER READ32:",
        "PASS: Phase 6DA ExFreePool ITAIL",
        "PASS: Phase 6DA manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DA APU CORE:",
        "P6DA AV/DISPLAY SUMMARY:",
        "sub_0029FBE2",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DB] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = patch_fbe2_entry(main_text)
    main_text, caller_audit = patch_direct_callers(main_text, base)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DB FBE2 ENTRY:",
        "P6DB FBE2 CALLER:",
        "P6DB FBE2 PROVENANCE:",
        "P6DB DSOUND ARG: stage=1 func=0029F992",
        "P6DB PREFAULT ROUTER READ32:",
        "PASS: Phase 6DB ExFreePool ITAIL",
        "PASS: Phase 6DB manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DB APU CORE:",
        "P6DB AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DB] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DB",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6db_dsound_fbe2_caller"] = {
        "source_phase": "6DA",
        "hardware_proof": {
            "f992_arg1": "0x00041D88",
            "f992_arg2": "0x008BF924",
            "f992_arg3": "0x01B5DE7C",
            "f992_arg4": "0x00000000",
            "fault_address": "0xCCCCCCD0",
            "ticks": 27021609,
        },
        "static_relation": {
            "fbe2_to_f992_arg1": "arg1 != 0 ? arg1 - 8 : 0",
            "expected_fbe2_arg1": "0x00041D90",
        },
        "direct_caller_audit": caller_audit,
        "probe_only": True,
        "guest_memory_semantics_changed": False,
        "value_fabrication": False,
        "fault_suppression": False,
        "address_range_widened": False,
        "execution_budget_inherited": 64000000,
        "exfreepool_itail_preserved": True,
        "manual_dsound_decrypt_preserved": True,
        "shadow_ram_alias_preserved": True,
        "graphics_semantics_changed": False,
        "apu_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6db-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DB] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DB] static relation: failing F992 arg1 00041D88 => FBE2 arg1 00041D90")
    print(f"[Phase6DB] direct FBE2 caller sites: {len(caller_audit)}")
    for row in caller_audit:
        print(
            f"[Phase6DB] CALLER site={row['site']} "
            f"va={row['caller_va']} name={row['caller_name']}"
        )
    print("[Phase6DB] no pointer substitution; no fault suppression")
    print("[Phase6DB] money line: P6DB FBE2 CALLER: ... arg1=00041D90 ...")
    print("[Phase6DB] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
