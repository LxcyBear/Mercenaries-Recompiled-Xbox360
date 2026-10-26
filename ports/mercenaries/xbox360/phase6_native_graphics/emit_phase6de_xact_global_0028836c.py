#!/usr/bin/env python3
r"""Phase 6DE: prove the initialization provenance of XACT global 0x0028836C.

6DD hardware isolated the producer of the bad DSOUND pointer:
  * sub_00280C39 entered with ordinary arguments.
  * at VA 0x00280CD2 it read guest global 0x0028836C and got zero.
  * at VA 0x00280CF5, READ32 site 10 accessed guest address 0x00000010
    and received 0x00041D90.
  * 0x00041D90 then flowed through FBE2 -> 0x00041D88 -> [CCCCCCCC+4].

The live register ring shows EAX is zero entering 0x00280CF5, strongly
suggesting the zero global supplies a null base for the +0x10 read.

6DE does not repair or bypass that behavior. It:
  * reads 6DD's exact target-source/read-site audit and prints the source
    around the 0x00280CD2 / 0x00280CF5 transition;
  * scans the full local generated-source inventory for literal references to
    0x0028836C and reports every reader/writer candidate;
  * wraps the central guest WRITE32 router and logs every write to exactly
    0x0028836C before the inherited write executes.

No value is fabricated, the CCCCCCD0 hard fault remains active, and no guest
address range is widened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DD-XACT-280C39-ARG1-INTERNAL-20261026-A"
BUILD_TAG = "P6DE-XACT-GLOBAL-0028836C-PROVENANCE-20261026-A"
COOKIE_OLD = "phase6dd_env_build_cookie"
COOKIE_NEW = "phase6de_env_build_cookie"
EMITTER_REVISION = "6DE-R2"

GLOBAL_VA = 0x0028836C
READ_BLOCK_VA = 0x00280CD2
NULL_BLOCK_VA = 0x00280CF5


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DE] could not load helper {path}")
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
    raise SystemExit("[Phase6DE] unterminated function body")


def install_state(text: str) -> str:
    # The WRITE32 watch is emitted very early in main_monolithic.cpp.  Keep
    # its telemetry state immediately before the central router definition so
    # MSVC sees the declarations before the wrapper uses them.
    anchor = "void recomp_guest_write32(uint32_t address, uint32_t value)"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DE] expected one central WRITE32 state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6deGlobalWriteReports = 0u;
static DWORD s_phase6deGlobalLastCaller = 0u;
static DWORD s_phase6deGlobalLastValue = 0u;
static DWORD s_phase6deGlobalLastEsp = 0u;

"""
    return text.replace(anchor, state + anchor, 1)


def install_write32_watch(text: str) -> str:
    signature = "void recomp_guest_write32(uint32_t address, uint32_t value)"
    definition_re = re.compile(
        r"(?m)^void\s+recomp_guest_write32\(uint32_t address, uint32_t value\)\s*\{"
    )
    matches = list(definition_re.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6DE] expected one central WRITE32 definition, found {len(matches)}"
        )

    start = matches[0].start()
    open_pos = text.find("{", matches[0].start(), matches[0].end() + 1)
    if open_pos < 0:
        raise SystemExit("[Phase6DE] WRITE32 definition brace missing")
    close_pos = matching_brace(text, open_pos)
    original = text[start:close_pos + 1]

    renamed = original.replace(
        signature,
        "static void phase6de_inherited_guest_write32(uint32_t address, uint32_t value)",
        1,
    )
    if signature in renamed:
        raise SystemExit("[Phase6DE] WRITE32 router rename failed")

    wrapper = r'''
void recomp_guest_write32(uint32_t address, uint32_t value)
{
    if (address == 0x0028836Cu)
    {
        DWORD caller = 0u;
        char line[448];

        ++s_phase6deGlobalWriteReports;
        s_phase6deGlobalLastValue = value;
        s_phase6deGlobalLastEsp = esp;

        if (s_traceCount != 0u)
        {
            DWORD index = s_traceCount - 1u;
            if (index >= TRACE_CAPACITY)
                index = TRACE_CAPACITY - 1u;
            caller = s_trace[index];
        }
        s_phase6deGlobalLastCaller = caller;

        sprintf(
            line,
            "P6DE XACT GLOBAL WRITE32: caller=%08X address=%08X value=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X writes=%u",
            (unsigned int)caller,
            (unsigned int)address,
            (unsigned int)value,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)esp,
            (unsigned int)s_phase6deGlobalWriteReports);
        trace(line);
    }

    phase6de_inherited_guest_write32(address, value);
}
'''
    return text[:start] + renamed + "\n\n" + wrapper + text[close_pos + 1:]


def extract_6dd_site_audit(dd: dict) -> dict:
    sites = list(dd.get("read_sites", []))
    target_lines = list(dd.get("target_source_lines", []))

    by_site = {}
    for row in sites:
        try:
            site = int(row.get("site"))
        except (TypeError, ValueError):
            continue
        by_site[site] = row

    site10 = by_site.get(10)
    if site10 is None:
        raise SystemExit("[Phase6DE] inherited 6DD site-10 audit missing")
    if str(site10.get("va", "")).lower() != "0x00280cf5":
        raise SystemExit(
            f"[Phase6DE] 6DD site 10 VA changed: {site10.get('va')}"
        )

    source_line = int(site10.get("source_line", 0))
    if source_line <= 0 or source_line > len(target_lines):
        raise SystemExit("[Phase6DE] 6DD site-10 source line outside target source")

    lo = max(1, source_line - 16)
    hi = min(len(target_lines), source_line + 12)
    context = [
        {"line": n, "text": target_lines[n - 1]}
        for n in range(lo, hi + 1)
    ]

    global_read = None
    for row in sites:
        source = str(row.get("source", "")).lower()
        va = str(row.get("va", "")).lower()
        if va == "0x00280cd2" or "28836c" in source:
            global_read = row
            if "28836c" in source:
                break

    return {
        "site10": site10,
        "global_read_site": global_read,
        "context": context,
    }


def full_generated_audit(generated_root: Path, functions_path: Path, base) -> dict:
    by_va, by_name = base.load_ranges(functions_path)
    generated = base.load_generated(generated_root, by_name)

    tokens = (
        "0x28836c",
        "0x0028836c",
    )
    rows = []

    for va in sorted(generated):
        item = generated[va]
        lines = item["source"].splitlines()
        for index, line in enumerate(lines, 1):
            low = line.lower()
            if not any(token in low for token in tokens):
                continue

            kind = "reference"
            if "guest_write" in low or "recomp_write" in low:
                kind = "write"
            elif "guest_read" in low or "recomp_read" in low:
                kind = "read"

            rows.append({
                "owner_start": f"0x{va:08X}",
                "owner_name": item["name"],
                "file": item["file"],
                "line": index,
                "kind": kind,
                "source": line.strip(),
            })

    return {
        "address": f"0x{GLOBAL_VA:08X}",
        "matches": rows,
        "match_count": len(rows),
        "writer_count": sum(1 for row in rows if row["kind"] == "write"),
        "reader_count": sum(1 for row in rows if row["kind"] == "read"),
    }


def insert_summary(text: str) -> str:
    marker = "P6DD 280C39 INTERNAL:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DE] inherited 6DD internal summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DE] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DE XACT GLOBAL 0028836C: writes=%u last_caller=%08X last_value=%08X last_esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6deGlobalWriteReports,\n'
        f'{indent}    (unsigned int)s_phase6deGlobalLastCaller,\n'
        f'{indent}    (unsigned int)s_phase6deGlobalLastValue,\n'
        f'{indent}    (unsigned int)s_phase6deGlobalLastEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DE] expected one 6DD build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DD", "PHASE 6DE")
        .replace("Phase 6DD", "Phase 6DE")
        .replace('"P6DD ', '"P6DE ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DE] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DD", "PHASE 6DE")
        .replace("Phase 6DD", "Phase 6DE")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6de_base")
    p6bl = load(args.phase6bl_emitter, "phase6de_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6dd-manifest.json"
    for path in (
        main_path,
        env_path,
        manifest_path,
        args.generated_root,
        args.functions,
    ):
        if not path.exists():
            raise SystemExit(f"[Phase6DE] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DD" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DE] cached 6DD identity mismatch")

    dd = manifest.get("phase6dd_xact_280c39_internal", {})
    if (
        dd.get("probe_only") is not True
        or dd.get("guest_memory_semantics_changed") is not False
        or dd.get("value_fabrication") is not False
        or dd.get("fault_suppression") is not False
        or dd.get("address_range_widened") is not False
        or dd.get("execution_budget_inherited") != 64000000
        or dd.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DE] inherited 6DD policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DD 280C39 READ32:",
        "P6DD 280C39 INTERNAL:",
        "P6DD FBE2 CALLER:",
        "P6DD PREFAULT ROUTER READ32:",
        "PASS: Phase 6DD ExFreePool ITAIL",
        "PASS: Phase 6DD manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DD APU CORE:",
        "P6DD AV/DISPLAY SUMMARY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DE] inherited marker missing: {marker}")

    site_audit = extract_6dd_site_audit(dd)
    generated_audit = full_generated_audit(
        args.generated_root,
        args.functions,
        base,
    )

    main_text = install_state(main_text)
    main_text = install_write32_watch(main_text)

    # Compile-order gate: the early WRITE32 wrapper must never precede the
    # telemetry declarations it consumes.
    state_pos = main_text.find("static DWORD s_phase6deGlobalWriteReports = 0u;")
    wrapper_pos = main_text.find("void recomp_guest_write32(uint32_t address, uint32_t value)")
    if state_pos < 0 or wrapper_pos < 0 or state_pos > wrapper_pos:
        raise SystemExit("[Phase6DE] WRITE32 telemetry compile-order gate failed")

    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DE XACT GLOBAL WRITE32:",
        "P6DE XACT GLOBAL 0028836C:",
        "P6DE 280C39 READ32:",
        "P6DE 280C39 INTERNAL:",
        "P6DE FBE2 CALLER:",
        "P6DE PREFAULT ROUTER READ32:",
        "PASS: Phase 6DE ExFreePool ITAIL",
        "PASS: Phase 6DE manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DE APU CORE:",
        "P6DE AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DE] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DE",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6de_xact_global_0028836c"] = {
        "source_phase": "6DD",
        "hardware_proof": {
            "global_address": "0x0028836C",
            "global_read_va": "0x00280CD2",
            "global_value": "0x00000000",
            "null_read_va": "0x00280CF5",
            "null_read_address": "0x00000010",
            "null_read_value": "0x00041D90",
            "downstream_bad_object": "0x00041D88",
            "fault_address": "0xCCCCCCD0",
            "ticks": 27021609,
        },
        "site_audit": site_audit,
        "generated_reference_audit": generated_audit,
        "central_write_watch": True,
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

    (args.out_dir / "phase6de-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DE] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DE] WRITE32 telemetry compile-order gate: PASS")
    print(
        "[Phase6DE] 6DD hardware chain: "
        "READ32 0028836C -> 00000000; then READ32 00000010 -> 00041D90"
    )
    print("[Phase6DE] 00280CF5 SOURCE CONTEXT BEGIN")
    for row in site_audit["context"]:
        mark = (
            ">>"
            if row["line"] == int(site_audit["site10"]["source_line"])
            else "  "
        )
        print(f"[Phase6DE] {mark} {row['line']:03d}: {row['text']}")
    print("[Phase6DE] 00280CF5 SOURCE CONTEXT END")

    print(
        "[Phase6DE] generated 0028836C references: "
        f"matches={generated_audit['match_count']} "
        f"readers={generated_audit['reader_count']} "
        f"writers={generated_audit['writer_count']}"
    )
    for row in generated_audit["matches"]:
        print(
            "[Phase6DE] GLOBAL REF "
            f"{row['kind']} owner={row['owner_start']} {row['owner_name']} "
            f"file={row['file']} line={row['line']}: {row['source']}"
        )

    print("[Phase6DE] central WRITE32 watch armed for exact address 0028836C")
    print("[Phase6DE] no pointer substitution; no fault suppression")
    print("[Phase6DE] money line if runtime writes the global:")
    print("[Phase6DE]   P6DE XACT GLOBAL WRITE32: caller=... value=...")
    print("[Phase6DE] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
