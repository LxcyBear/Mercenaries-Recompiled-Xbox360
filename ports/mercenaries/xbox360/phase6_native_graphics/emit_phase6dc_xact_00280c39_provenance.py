#!/usr/bin/env python3
r"""Phase 6DC: trace the XACT-side producer sub_00280C39.

6DB hardware proved the exact failing chain:
    sub_00280C39
      -> sub_0029FBE2(arg1=0x00041D90, arg2=0x008BF924,
                      arg3=0x01B5DE7C, arg4=0)
      -> sub_0029F992(arg1=0x00041D88)
      -> 0029EBEA -> 0029EA79 -> 002A41EE
      -> [0x00041D88] = 0xCCCCCCCC
      -> [0xCCCCCCCC + 4] = fault 0xCCCCCCD0

6DC does not change the bad value.  It:
  * emits a static source audit of the complete generated sub_00280C39 body,
  * records every literal reference to 00280C39 in the generated source,
  * probes sub_00280C39 entry args/registers,
  * probes each direct call site to sub_00280C39 before the dummy return push.

No pointer substitution, zeroing, fault suppression, or address widening.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A"
BUILD_TAG = "P6DC-XACT-00280C39-PROVENANCE-20261026-A"
COOKIE_OLD = "phase6db_env_build_cookie"
COOKIE_NEW = "phase6dc_env_build_cookie"
EMITTER_REVISION = "6DC-R1"
TARGET_NAME = "sub_00280C39"
TARGET_VA = 0x00280C39


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DC] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def all_defs(text: str, base):
    masked = base.mask_noncode(text)
    out = []
    for m in base.FUNC_RE.finditer(masked):
        name = m.group(1)
        open_pos = masked.find("{", m.start(), m.end())
        if open_pos < 0:
            continue
        end = base.closing_brace(masked, open_pos)
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        va = int(vm.group(1), 16) if vm else 0
        out.append({
            "name": name,
            "va": va,
            "start": m.start(),
            "open": open_pos,
            "end": end,
        })
    return out


def locate_target(text: str, base):
    rows = [r for r in all_defs(text, base) if r["name"] == TARGET_NAME]
    if len(rows) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one {TARGET_NAME} body, found {len(rows)}"
        )
    return rows[0]


def source_audit(text: str, row):
    body = text[row["start"]:row["end"] + 1]
    lines = body.splitlines()
    if len(lines) > 260:
        raise SystemExit(
            f"[Phase6DC] {TARGET_NAME} unexpectedly large ({len(lines)} lines)"
        )
    return lines


def reference_audit(text: str, row):
    refs = []
    lines = text.splitlines()
    for idx, line in enumerate(lines, 1):
        if "00280C39" not in line:
            continue
        refs.append({
            "line": idx,
            "text": line.strip()[:500],
        })
        if len(refs) >= 128:
            break
    return refs


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6dbFbe2CallerReports = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one 6DB state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6dcEntryReports = 0u;
static DWORD s_phase6dcEntryArg1 = 0u;
static DWORD s_phase6dcEntryArg2 = 0u;
static DWORD s_phase6dcEntryArg3 = 0u;
static DWORD s_phase6dcEntryArg4 = 0u;
static DWORD s_phase6dcEntryArg5 = 0u;
static DWORD s_phase6dcEntryArg6 = 0u;
static DWORD s_phase6dcDirectCallerReports = 0u;
static DWORD s_phase6dcLastDirectCaller = 0u;
static DWORD s_phase6dcLastDirectSite = 0u;
static DWORD s_phase6dcLastDirectArg1 = 0u;

"""
    return text.replace(anchor, state + anchor, 1)


def patch_entry(text: str) -> str:
    definition_re = re.compile(
        r"(?m)^\s*(?:static\s+)?void\s+sub_00280C39\(void\)\s*\{"
    )
    ms = list(definition_re.finditer(text))
    if len(ms) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one {TARGET_NAME} body, found {len(ms)}"
        )
    body_open = text.find("{", ms[0].start(), ms[0].end() + 1)
    marker = "    RECOMP_TRACE_FUNC(0x00280C39u);\n"
    pos = text.find(marker, body_open)
    if pos < 0 or pos - body_open > 4096:
        raise SystemExit("[Phase6DC] target entry trace marker missing")

    probe = r'''    {
        DWORD phase6dcArg1 = GUEST_READ32(esp + 4u);
        DWORD phase6dcArg2 = GUEST_READ32(esp + 8u);
        DWORD phase6dcArg3 = GUEST_READ32(esp + 12u);
        DWORD phase6dcArg4 = GUEST_READ32(esp + 16u);
        DWORD phase6dcArg5 = GUEST_READ32(esp + 20u);
        DWORD phase6dcArg6 = GUEST_READ32(esp + 24u);
        char phase6dcLine[640];

        ++s_phase6dcEntryReports;
        s_phase6dcEntryArg1 = phase6dcArg1;
        s_phase6dcEntryArg2 = phase6dcArg2;
        s_phase6dcEntryArg3 = phase6dcArg3;
        s_phase6dcEntryArg4 = phase6dcArg4;
        s_phase6dcEntryArg5 = phase6dcArg5;
        s_phase6dcEntryArg6 = phase6dcArg6;

        sprintf(
            phase6dcLine,
            "P6DC XACT 00280C39 ENTRY: esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X arg5=%08X arg6=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X reports=%u",
            (unsigned int)esp,
            (unsigned int)phase6dcArg1,
            (unsigned int)phase6dcArg2,
            (unsigned int)phase6dcArg3,
            (unsigned int)phase6dcArg4,
            (unsigned int)phase6dcArg5,
            (unsigned int)phase6dcArg6,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)s_phase6dcEntryReports);
        trace(phase6dcLine);
    }
'''
    return text[:pos] + probe + text[pos:]


def patch_direct_callers(text: str, base):
    needle = "PUSH32(esp, 0); sub_00280C39(); /* call 0x00280C39 */"
    defs = all_defs(text, base)
    sites = []

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
                "line_start": line_start,
                "line_end": line_end,
                "indent": indent,
            })
            cursor = pos + len(needle)

    for site_index, site in reversed(list(enumerate(sites, 1))):
        indent = site["indent"]
        owner_va = site["owner_va"]
        owner_name = site["owner_name"]
        block = (
            f'{indent}{{\n'
            f'{indent}    DWORD phase6dcArg1 = GUEST_READ32(esp);\n'
            f'{indent}    DWORD phase6dcArg2 = GUEST_READ32(esp + 4u);\n'
            f'{indent}    DWORD phase6dcArg3 = GUEST_READ32(esp + 8u);\n'
            f'{indent}    DWORD phase6dcArg4 = GUEST_READ32(esp + 12u);\n'
            f'{indent}    DWORD phase6dcArg5 = GUEST_READ32(esp + 16u);\n'
            f'{indent}    DWORD phase6dcArg6 = GUEST_READ32(esp + 20u);\n'
            f'{indent}    char phase6dcLine[640];\n'
            f'{indent}    ++s_phase6dcDirectCallerReports;\n'
            f'{indent}    s_phase6dcLastDirectCaller = 0x{owner_va:08X}u;\n'
            f'{indent}    s_phase6dcLastDirectSite = {site_index}u;\n'
            f'{indent}    s_phase6dcLastDirectArg1 = phase6dcArg1;\n'
            f'{indent}    sprintf(phase6dcLine,\n'
            f'{indent}        "P6DC XACT 00280C39 CALLER: site={site_index} caller={owner_va:08X} name={owner_name} esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X arg5=%08X arg6=%08X eax=%08X ecx=%08X edx=%08X esi=%08X edi=%08X reports=%u",\n'
            f'{indent}        (unsigned int)esp, (unsigned int)phase6dcArg1,\n'
            f'{indent}        (unsigned int)phase6dcArg2, (unsigned int)phase6dcArg3,\n'
            f'{indent}        (unsigned int)phase6dcArg4, (unsigned int)phase6dcArg5,\n'
            f'{indent}        (unsigned int)phase6dcArg6, (unsigned int)eax,\n'
            f'{indent}        (unsigned int)ecx, (unsigned int)edx,\n'
            f'{indent}        (unsigned int)esi, (unsigned int)edi,\n'
            f'{indent}        (unsigned int)s_phase6dcDirectCallerReports);\n'
            f'{indent}    trace(phase6dcLine);\n'
            f'{indent}}}\n'
            f'{indent}{needle}'
        )
        text = (
            text[:site["line_start"]]
            + block
            + text[site["line_end"]:]
        )

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
    marker = "P6DB FBE2 PROVENANCE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DC] inherited 6DB provenance summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DC] summary insertion point changed")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DC XACT 00280C39 PROVENANCE: entry_reports=%u arg1=%08X arg2=%08X arg3=%08X arg4=%08X arg5=%08X arg6=%08X direct_reports=%u last_direct_site=%u last_direct_caller=%08X last_direct_arg1=%08X",\n'
        f'{indent}    (unsigned int)s_phase6dcEntryReports,\n'
        f'{indent}    (unsigned int)s_phase6dcEntryArg1,\n'
        f'{indent}    (unsigned int)s_phase6dcEntryArg2,\n'
        f'{indent}    (unsigned int)s_phase6dcEntryArg3,\n'
        f'{indent}    (unsigned int)s_phase6dcEntryArg4,\n'
        f'{indent}    (unsigned int)s_phase6dcEntryArg5,\n'
        f'{indent}    (unsigned int)s_phase6dcEntryArg6,\n'
        f'{indent}    (unsigned int)s_phase6dcDirectCallerReports,\n'
        f'{indent}    (unsigned int)s_phase6dcLastDirectSite,\n'
        f'{indent}    (unsigned int)s_phase6dcLastDirectCaller,\n'
        f'{indent}    (unsigned int)s_phase6dcLastDirectArg1);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one 6DB build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DB", "PHASE 6DC")
        .replace("Phase 6DB", "Phase 6DC")
        .replace('"P6DB ', '"P6DC ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DC] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DB", "PHASE 6DC")
        .replace("Phase 6DB", "Phase 6DC")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dc_base")
    p6bl = load(args.phase6bl_emitter, "phase6dc_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6db-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6DC] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DB" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DC] cached 6DB identity mismatch")

    db = manifest.get("phase6db_dsound_fbe2_caller", {})
    if (
        db.get("probe_only") is not True
        or db.get("guest_memory_semantics_changed") is not False
        or db.get("value_fabrication") is not False
        or db.get("fault_suppression") is not False
        or db.get("address_range_widened") is not False
        or db.get("execution_budget_inherited") != 64000000
        or db.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DC] inherited 6DB policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DB FBE2 CALLER:",
        "P6DB FBE2 ENTRY:",
        "P6DB FBE2 PROVENANCE:",
        "P6DB PREFAULT ROUTER READ32:",
        "PASS: Phase 6DB ExFreePool ITAIL",
        "PASS: Phase 6DB manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DB APU CORE:",
        "P6DB AV/DISPLAY SUMMARY:",
        "sub_00280C39",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DC] inherited marker missing: {marker}")

    target = locate_target(main_text, base)
    body_audit = source_audit(main_text, target)
    ref_audit = reference_audit(main_text, target)

    main_text = install_state(main_text)
    main_text = patch_entry(main_text)
    main_text, direct_audit = patch_direct_callers(main_text, base)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DC XACT 00280C39 ENTRY:",
        "P6DC XACT 00280C39 PROVENANCE:",
        "P6DC FBE2 CALLER:",
        "P6DC PREFAULT ROUTER READ32:",
        "PASS: Phase 6DC ExFreePool ITAIL",
        "PASS: Phase 6DC manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DC APU CORE:",
        "P6DC AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DC] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DC",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6dc_xact_00280c39_provenance"] = {
        "source_phase": "6DB",
        "hardware_proof": {
            "fbe2_caller": "0x00280C39",
            "fbe2_arg1": "0x00041D90",
            "fbe2_arg2": "0x008BF924",
            "fbe2_arg3": "0x01B5DE7C",
            "fbe2_arg4": "0x00000000",
            "fault_address": "0xCCCCCCD0",
            "ticks": 27021609,
        },
        "target": "0x00280C39",
        "target_name": TARGET_NAME,
        "target_source_lines": body_audit,
        "literal_reference_audit": ref_audit,
        "direct_caller_audit": direct_audit,
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
    (args.out_dir / "phase6dc-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DC] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DC] hardware producer: 00280C39 -> FBE2 arg1=00041D90")
    print("[Phase6DC] TARGET SOURCE AUDIT BEGIN")
    for i, line in enumerate(body_audit, 1):
        print(f"[Phase6DC] SRC {i:03d}: {line}")
    print("[Phase6DC] TARGET SOURCE AUDIT END")
    print(f"[Phase6DC] literal 00280C39 references: {len(ref_audit)}")
    for row in ref_audit:
        print(f"[Phase6DC] REF line={row['line']}: {row['text']}")
    print(f"[Phase6DC] direct caller sites: {len(direct_audit)}")
    for row in direct_audit:
        print(
            f"[Phase6DC] CALLER site={row['site']} "
            f"va={row['caller_va']} name={row['caller_name']}"
        )
    print("[Phase6DC] no pointer substitution; no fault suppression")
    print("[Phase6DC] money line: P6DC XACT 00280C39 ENTRY: ...")
    print("[Phase6DC] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
