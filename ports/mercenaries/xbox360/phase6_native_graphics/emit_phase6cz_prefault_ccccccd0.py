#!/usr/bin/env python3
r"""Phase 6CZ: pre-fault CCCCCCD0 read provenance.

6CY reproduced the hardware fault exactly:
  READ32 guest=0xCCCCCCD0
  eax=0xCCCCCCCC
  ticks=27,021,609 trace=1,071,691
after the post-DSOUND 40-byte pool allocation/query.

6CY's translated READ32 wrapper attempted to report the site after calling the
checked guest router. The current router escapes immediately on invalid access,
so that post-call report is unreachable for the faulting read.

6CZ corrects that diagnostic mistake without changing guest semantics:
  * translated wrapper logs BEFORE a read of exactly 0xCCCCCCD0;
  * maintained/manual/support GUEST_READ32 and direct recomp_guest_read32 calls
    are wrapped and log BEFORE the same address;
  * the checked router still handles the fault normally immediately afterward;
  * the final DSOUND VA-ring addresses 0x002A41EE/0x002A41F7 are resolved
    against the local generated-source inventory and printed during emission.

No value is fabricated and no address range is widened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CY-READ32-CCCCCCD0-SITE-20261026-A"
BUILD_TAG = "P6CZ-PREFAULT-CCCCCCD0-PROVENANCE-20261026-A"
COOKIE_OLD = "phase6cy_env_build_cookie"
COOKIE_NEW = "phase6cz_env_build_cookie"
EMITTER_REVISION = "6CZ-R1"

FAULT_ADDRESS = 0xCCCCCCD0
FINAL_VAS = (0x002A41EE, 0x002A41F7)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CZ] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def translated_bounds(text: str) -> tuple[int, int]:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off = text.find(off_marker)
    if off < 0:
        raise SystemExit("[Phase6CZ] optimize-off marker missing")
    start = off + len(off_marker)
    end = text.find(on_marker, start)
    if end < 0:
        raise SystemExit("[Phase6CZ] optimize-on marker missing")
    return start, end


def function_range(text: str, signature: str, base) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6CZ] function signature missing: {signature}")
    masked = base.mask_noncode(text)
    brace = masked.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6CZ] opening brace missing: {signature}")
    end = base.closing_brace(masked, brace)
    return start, end


def patch_translated_prefault(text: str) -> str:
    signature = "static uint32_t phase6cy_read32_site("
    start = text.find(signature)
    if start < 0:
        raise SystemExit("[Phase6CZ] inherited 6CY translated READ32 wrapper missing")

    needle = """    /* Direct call preserves the existing checked guest-memory semantics. */
    value = recomp_guest_read32(address);
"""
    pos = text.find(needle, start)
    if pos < 0:
        raise SystemExit("[Phase6CZ] 6CY wrapper call site changed")

    block = r'''    /*
     * The checked router longjmps immediately on invalid access.  Report the
     * exact poisoned address before entering it so the provenance survives.
     */
    if (address == 0xCCCCCCD0u)
    {
        char preline[448];
        ++s_phase6czTranslatedPrefaultReports;
        s_phase6czTranslatedPrefaultFunction = functionVa;
        s_phase6czTranslatedPrefaultLine = sourceLine;
        sprintf(
            preline,
            "P6CZ PREFAULT TRANSLATED READ32: func=%08X line=%u address=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X reports=%u",
            (unsigned int)functionVa,
            (unsigned int)sourceLine,
            (unsigned int)address,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)esp,
            (unsigned int)s_phase6czTranslatedPrefaultReports);
        trace(preline);
    }

    /* Direct call preserves the existing checked guest-memory semantics. */
    value = recomp_guest_read32(address);
'''
    return text[:pos] + block + text[pos + len(needle):]


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6cyFaultSiteReports = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CZ] expected one 6CY fault-report state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6czTranslatedPrefaultReports = 0u;
static DWORD s_phase6czTranslatedPrefaultFunction = 0u;
static DWORD s_phase6czTranslatedPrefaultLine = 0u;
static DWORD s_phase6czSupportPrefaultReports = 0u;
static DWORD s_phase6czSupportPrefaultLine = 0u;
static DWORD s_phase6czSupportPrefaultAddress = 0u;
static const char* s_phase6czSupportPrefaultFunction = "";

"""
    return text.replace(anchor, anchor + state, 1)


def install_support_probe(text: str, base) -> tuple[str, int, int]:
    macro = "#define GUEST_READ32(addr) recomp_guest_read32((uint32_t)(addr))\n"
    macro_pos = text.find(macro)
    if macro_pos < 0:
        raise SystemExit("[Phase6CZ] canonical GUEST_READ32 macro missing")
    support_start = macro_pos + len(macro)

    body_start, _ = translated_bounds(text)
    pragma_pos = text.rfind('#pragma optimize("", off)\n', 0, body_start)
    if pragma_pos < 0 or pragma_pos <= support_start:
        raise SystemExit("[Phase6CZ] support instrumentation range invalid")

    cy_start, cy_end = function_range(
        text, "static uint32_t phase6cy_read32_site(", base
    )

    support = text[support_start:pragma_pos]
    masked = base.mask_noncode(support)

    patterns = (
        ("GUEST_READ32(", "phase6cz_support_read32(__FUNCTION__, (DWORD)__LINE__, "),
        ("recomp_guest_read32(", "phase6cz_support_read32(__FUNCTION__, (DWORD)__LINE__, "),
    )
    replacements: list[tuple[int, int, str]] = []
    guest_macro_sites = 0
    direct_sites = 0

    for needle, replacement in patterns:
        cursor = 0
        while True:
            rel = masked.find(needle, cursor)
            if rel < 0:
                break
            absolute = support_start + rel

            # Do not wrap the inherited translated-site wrapper's own direct
            # router call; that path is handled by patch_translated_prefault().
            if not (cy_start <= absolute < cy_end):
                replacements.append((rel, rel + len(needle), replacement))
                if needle.startswith("GUEST_"):
                    guest_macro_sites += 1
                else:
                    direct_sites += 1
            cursor = rel + len(needle)

    if not replacements:
        raise SystemExit("[Phase6CZ] found no support-side READ32 calls to instrument")

    # Reject overlapping replacements and apply from the end.
    replacements.sort()
    for i in range(1, len(replacements)):
        if replacements[i][0] < replacements[i - 1][1]:
            raise SystemExit("[Phase6CZ] overlapping support READ32 replacements")

    for start, end, replacement in reversed(replacements):
        support = support[:start] + replacement + support[end:]

    prototype = (
        "static uint32_t phase6cz_support_read32("
        "const char* functionName, DWORD sourceLine, uint32_t address);\n"
    )
    text = text[:support_start] + prototype + support + text[pragma_pos:]

    # Insert the implementation immediately before translated code, after all
    # support functions that now reference the forward declaration.
    pragma_pos = text.find('#pragma optimize("", off)\n')
    if pragma_pos < 0:
        raise SystemExit("[Phase6CZ] translated pragma missing after support patch")

    helper = r'''
static uint32_t phase6cz_support_read32(
    const char* functionName,
    DWORD sourceLine,
    uint32_t address)
{
    if (address == 0xCCCCCCD0u)
    {
        char line[512];
        ++s_phase6czSupportPrefaultReports;
        s_phase6czSupportPrefaultFunction = functionName;
        s_phase6czSupportPrefaultLine = sourceLine;
        s_phase6czSupportPrefaultAddress = address;
        sprintf(
            line,
            "P6CZ PREFAULT SUPPORT READ32: func=%s line=%u address=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X reports=%u",
            functionName ? functionName : "<null>",
            (unsigned int)sourceLine,
            (unsigned int)address,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)esp,
            (unsigned int)s_phase6czSupportPrefaultReports);
        trace(line);
    }

    /*
     * Preserve the existing checked router exactly. If the address is invalid,
     * that router performs the established immediate boundary escape.
     */
    return recomp_guest_read32(address);
}

'''
    text = text[:pragma_pos] + helper + text[pragma_pos:]
    return text, guest_macro_sites, direct_sites


def resolve_final_va_source(
    generated_root: Path,
    functions_path: Path,
    base,
) -> dict:
    by_va, by_name = base.load_ranges(functions_path)
    generated = base.load_generated(generated_root, by_name)
    rows = []

    for va in FINAL_VAS:
        owner = None
        for start, row in by_va.items():
            if int(row["start"]) <= va < int(row["end"]):
                owner = (start, row)
                break
        if owner is None:
            raise SystemExit(f"[Phase6CZ] final VA 0x{va:08X} absent from function inventory")

        start, row = owner
        source_row = generated.get(start)
        if source_row is None:
            rows.append({
                "va": f"0x{va:08X}",
                "owner_start": f"0x{start:08X}",
                "owner_name": row["name"],
                "generated": False,
                "context": [],
            })
            continue

        source = source_row["source"]
        lines = source.splitlines()
        tokens = (
            f"loc_{va:08X}:",
            f"0x{va:08X}u",
            f"0x{va:08X}",
        )
        hit = -1
        for index, line in enumerate(lines):
            if any(token.lower() in line.lower() for token in tokens):
                hit = index
                break

        context = []
        if hit >= 0:
            lo = max(0, hit - 5)
            hi = min(len(lines), hit + 9)
            context = lines[lo:hi]

        rows.append({
            "va": f"0x{va:08X}",
            "owner_start": f"0x{start:08X}",
            "owner_name": row["name"],
            "generated": True,
            "context": context,
        })

    return {"rows": rows}


def insert_summary(text: str, guest_sites: int, direct_sites: int) -> str:
    marker = "P6CY READ32 SITE PROBE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CZ] inherited 6CY summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6CZ] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CZ PREFAULT PROVENANCE: translated_reports=%u translated_func=%08X translated_line=%u support_reports=%u support_func=%s support_line=%u support_address=%08X support_guest_sites={guest_sites} support_direct_sites={direct_sites}",\n'
        f'{indent}    (unsigned int)s_phase6czTranslatedPrefaultReports,\n'
        f'{indent}    (unsigned int)s_phase6czTranslatedPrefaultFunction,\n'
        f'{indent}    (unsigned int)s_phase6czTranslatedPrefaultLine,\n'
        f'{indent}    (unsigned int)s_phase6czSupportPrefaultReports,\n'
        f'{indent}    s_phase6czSupportPrefaultFunction ? s_phase6czSupportPrefaultFunction : "<null>",\n'
        f'{indent}    (unsigned int)s_phase6czSupportPrefaultLine,\n'
        f'{indent}    (unsigned int)s_phase6czSupportPrefaultAddress);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CZ] expected one inherited build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6CY", "PHASE 6CZ")
        .replace("Phase 6CY", "Phase 6CZ")
        .replace('"P6CY ', '"P6CZ ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6CZ] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6CY", "PHASE 6CZ")
        .replace("Phase 6CY", "Phase 6CZ")
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

    base = load(args.base_emitter, "phase6cz_base")
    p6bl = load(args.phase6bl_emitter, "phase6cz_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cy-manifest.json"
    for path in (main_path, env_path, manifest_path, args.generated_root, args.functions):
        if not path.exists():
            raise SystemExit(f"[Phase6CZ] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6CY" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CZ] cached 6CY identity mismatch")

    cy = manifest.get("phase6cy_read32_ccccccd0_probe", {})
    if (
        cy.get("probe_only") is not True
        or cy.get("guest_memory_semantics_changed") is not False
        or cy.get("execution_budget_inherited") != 64000000
        or cy.get("exfreepool_itail_preserved") is not True
        or cy.get("manual_dsound_decrypt_preserved") is not True
        or cy.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6CZ] inherited 6CY policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6CY READ32 FAULT SITE:",
        "phase6cy_read32_site(phase6cy_function_va",
        "PASS: Phase 6CY ExFreePool ITAIL",
        "PASS: Phase 6CY manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CY APU CORE:",
        "P6CY AV/DISPLAY SUMMARY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CZ] inherited 6CY marker missing: {marker}")

    source_audit = resolve_final_va_source(
        args.generated_root, args.functions, base
    )

    main_text = install_state(main_text)
    main_text = patch_translated_prefault(main_text)
    main_text, guest_sites, direct_sites = install_support_probe(main_text, base)
    main_text = insert_summary(main_text, guest_sites, direct_sites)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CZ PREFAULT TRANSLATED READ32:",
        "P6CZ PREFAULT SUPPORT READ32:",
        "P6CZ PREFAULT PROVENANCE:",
        "PASS: Phase 6CZ ExFreePool ITAIL",
        "PASS: Phase 6CZ manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CZ APU CORE:",
        "P6CZ AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CZ] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6CZ",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6cz_prefault_ccccccd0_provenance"] = {
        "source_phase": "6CY",
        "phase6cy_hardware": {
            "fault_address": "0xCCCCCCD0",
            "eax": "0xCCCCCCCC",
            "ticks": 27021609,
            "trace": 1071691,
            "translated_probe_calls": 27404292,
            "translated_probe_fault_reports": 0,
            "translated_probe_fault_report_limit": (
                "post-router report was unreachable because checked router escapes immediately"
            ),
            "final_va_ring_tail": ["0x002A41EE", "0x002A41F7"],
            "last_pool_address": "0x01B5DFD0",
            "last_pool_size": 40,
        },
        "diagnostic_correction": (
            "log exact CCCCCCD0 provenance before entering checked guest router"
        ),
        "translated_prefault_probe": True,
        "support_prefault_probe": True,
        "support_guest_read32_sites": guest_sites,
        "support_direct_read32_sites": direct_sites,
        "final_va_source_audit": source_audit,
        "guest_memory_semantics_changed": False,
        "value_fabrication": False,
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
    (args.out_dir / "phase6cz-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CZ] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6CZ] support READ32 instrumentation: "
        f"GUEST_READ32={guest_sites} direct_recomp_guest_read32={direct_sites}"
    )
    print("[Phase6CZ] corrected probe logs BEFORE the checked router can longjmp")
    for row in source_audit["rows"]:
        print(
            f"[Phase6CZ] FINAL-VA SOURCE {row['va']} owner={row['owner_name']} "
            f"start={row['owner_start']} generated={int(row['generated'])}"
        )
        for line in row["context"]:
            print(f"[Phase6CZ]   {line}")
    print("[Phase6CZ] no value fabrication; CCCCCCD0 remains a hard guest fault")
    print("[Phase6CZ] money line is one of:")
    print("[Phase6CZ]   P6CZ PREFAULT TRANSLATED READ32: func=... line=... address=CCCCCCD0")
    print("[Phase6CZ]   P6CZ PREFAULT SUPPORT READ32: func=... line=... address=CCCCCCD0")
    print("[Phase6CZ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
