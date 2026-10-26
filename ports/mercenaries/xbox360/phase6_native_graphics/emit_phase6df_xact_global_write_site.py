#!/usr/bin/env python3
r"""Phase 6DF: exact translated write-site attribution for XACT global 0x0028836C.

6DE hardware proved a complete lifecycle:
  1) 0x0028836C is initialized to XACT root 0x01B5C320.
  2) later, 0x0028836C is explicitly written to zero.
  3) immediately afterward, 0x01B5C320 is freed.
  4) much later sub_00280C39 reads 0x0028836C == 0, then [0x10] yields
     0x00041D90 and the old CCCCCCD0 fault follows.

The central WRITE32 watcher cannot identify the exact translated source site
because support dispatch attribution collapses to 0x0023A3CE.

6DF therefore tags every translated GUEST_WRITE32 expansion with its owning
function VA and compiler source line. Runtime logging occurs only when the
resolved address is exactly 0x0028836C.

Diagnostic only:
  * no value substitution
  * no write suppression
  * no fault suppression
  * no address widening
  * inherited 64M watchdog and all hard fences preserved
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DE-XACT-GLOBAL-0028836C-PROVENANCE-20261026-A"
BUILD_TAG = "P6DF-XACT-GLOBAL-0028836C-WRITE-SITE-20261026-A"
COOKIE_OLD = "phase6de_env_build_cookie"
COOKIE_NEW = "phase6df_env_build_cookie"
EMITTER_REVISION = "6DF-R1"

GLOBAL_VA = 0x0028836C
TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
WRITE32_RE = re.compile(r"\bGUEST_WRITE32\s*\(")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DF] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def translated_bounds(text: str) -> tuple[int, int]:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off = text.find(off_marker)
    if off < 0:
        raise SystemExit("[Phase6DF] optimize-off marker missing")
    start = off + len(off_marker)
    end = text.find(on_marker, start)
    if end < 0:
        raise SystemExit("[Phase6DF] optimize-on marker missing")
    return start, end


def install_support(text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DF] support insertion marker missing")

    block = r'''
static DWORD s_phase6dfWriteSiteReports = 0u;
static DWORD s_phase6dfLastFunction = 0u;
static DWORD s_phase6dfLastLine = 0u;
static DWORD s_phase6dfLastValue = 0u;
static DWORD s_phase6dfRootWrites = 0u;
static DWORD s_phase6dfZeroWrites = 0u;

static void phase6df_write32_site(
    DWORD functionVa,
    DWORD sourceLine,
    uint32_t address,
    uint32_t value)
{
    if (address == 0x0028836Cu)
    {
        char line[512];

        ++s_phase6dfWriteSiteReports;
        s_phase6dfLastFunction = functionVa;
        s_phase6dfLastLine = sourceLine;
        s_phase6dfLastValue = value;

        if (value == 0u)
            ++s_phase6dfZeroWrites;
        else
            ++s_phase6dfRootWrites;

        sprintf(
            line,
            "P6DF XACT GLOBAL WRITE SITE: func=%08X line=%u address=%08X value=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X reports=%u root_writes=%u zero_writes=%u",
            (unsigned int)functionVa,
            (unsigned int)sourceLine,
            (unsigned int)address,
            (unsigned int)value,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)esp,
            (unsigned int)s_phase6dfWriteSiteReports,
            (unsigned int)s_phase6dfRootWrites,
            (unsigned int)s_phase6dfZeroWrites);
        trace(line);
    }

    /* Preserve the inherited checked WRITE32 semantics exactly. */
    recomp_guest_write32(address, value);
}

'''
    return text[:pos] + block + text[pos:]


def instrument_translated_write32(text: str, base) -> tuple[str, int, int]:
    body_start, body_end = translated_bounds(text)
    body = text[body_start:body_end]
    masked = base.mask_noncode(body)
    funcs = list(base.FUNC_RE.finditer(masked))
    if not funcs:
        raise SystemExit("[Phase6DF] translated body contains no functions")

    insertions: list[tuple[int, str]] = []
    total_writes = 0

    for match in funcs:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6DF] translated function opening brace missing")
        func_end = base.closing_brace(masked, brace)
        func_masked = masked[match.start():func_end]
        write_count = len(WRITE32_RE.findall(func_masked))
        total_writes += write_count

        trace_match = TRACE_RE.search(func_masked)
        if trace_match:
            va = int(trace_match.group(1), 16)
        else:
            name = match.group(1)
            m = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
            if not m:
                raise SystemExit(
                    f"[Phase6DF] translated function has no recoverable VA: {name}"
                )
            va = int(m.group(1), 16)

        insertions.append(
            (
                brace + 1,
                f"\n    const DWORD phase6df_function_va = 0x{va:08X}u;"
            )
        )

    if total_writes == 0:
        raise SystemExit("[Phase6DF] no translated GUEST_WRITE32 sites found")

    pieces: list[str] = []
    cursor = 0
    for pos, payload in sorted(insertions):
        if pos < cursor:
            raise SystemExit("[Phase6DF] overlapping function-VA insertions")
        pieces.append(body[cursor:pos])
        pieces.append(payload)
        cursor = pos
    pieces.append(body[cursor:])
    body = "".join(pieces)

    prefix = (
        "#undef GUEST_WRITE32\n"
        "#define GUEST_WRITE32(addr, value) "
        "phase6df_write32_site(phase6df_function_va, (DWORD)__LINE__, "
        "(uint32_t)(addr), (uint32_t)(value))\n"
    )
    suffix = (
        "\n#undef GUEST_WRITE32\n"
        "#define GUEST_WRITE32(addr, value) "
        "recomp_guest_write32((uint32_t)(addr), (uint32_t)(value))\n"
    )
    body = prefix + body + suffix
    return text[:body_start] + body + text[body_end:], total_writes, len(funcs)


def insert_summary(text: str, site_count: int, function_count: int) -> str:
    marker = "P6DE XACT GLOBAL 0028836C:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DF] inherited 6DE global summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DF] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DF XACT GLOBAL WRITE SITE SUMMARY: reports=%u last_func=%08X last_line=%u last_value=%08X root_writes=%u zero_writes=%u instrumented_sites={site_count} instrumented_functions={function_count}",\n'
        f'{indent}    (unsigned int)s_phase6dfWriteSiteReports,\n'
        f'{indent}    (unsigned int)s_phase6dfLastFunction,\n'
        f'{indent}    (unsigned int)s_phase6dfLastLine,\n'
        f'{indent}    (unsigned int)s_phase6dfLastValue,\n'
        f'{indent}    (unsigned int)s_phase6dfRootWrites,\n'
        f'{indent}    (unsigned int)s_phase6dfZeroWrites);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DF] expected one 6DE build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DE", "PHASE 6DF")
        .replace("Phase 6DE", "Phase 6DF")
        .replace('"P6DE ', '"P6DF ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DF] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DE", "PHASE 6DF")
        .replace("Phase 6DE", "Phase 6DF")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6df_base")
    p6bl = load(args.phase6bl_emitter, "phase6df_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6de-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6DF] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DE" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DF] cached 6DE identity mismatch")

    de = manifest.get("phase6de_xact_global_0028836c", {})
    if (
        de.get("central_write_watch") is not True
        or de.get("probe_only") is not True
        or de.get("guest_memory_semantics_changed") is not False
        or de.get("value_fabrication") is not False
        or de.get("fault_suppression") is not False
        or de.get("address_range_widened") is not False
        or de.get("execution_budget_inherited") != 64000000
        or de.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DF] inherited 6DE policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DE XACT GLOBAL WRITE32:",
        "P6DE XACT GLOBAL 0028836C:",
        "P6DE 280C39 READ32:",
        "P6DE PREFAULT ROUTER READ32:",
        "PASS: Phase 6DE ExFreePool ITAIL",
        "PASS: Phase 6DE manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DF] inherited marker missing: {marker}")

    main_text = install_support(main_text)
    main_text, site_count, function_count = instrument_translated_write32(
        main_text, base
    )
    main_text = insert_summary(main_text, site_count, function_count)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DF XACT GLOBAL WRITE SITE:",
        "P6DF XACT GLOBAL WRITE SITE SUMMARY:",
        "phase6df_write32_site(phase6df_function_va",
        "P6DF XACT GLOBAL WRITE32:",
        "P6DF XACT GLOBAL 0028836C:",
        "P6DF 280C39 READ32:",
        "P6DF PREFAULT ROUTER READ32:",
        "PASS: Phase 6DF ExFreePool ITAIL",
        "PASS: Phase 6DF manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DF] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DF",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6df_xact_global_write_site"] = {
        "source_phase": "6DE",
        "phase6de_hardware": {
            "global_address": "0x0028836C",
            "first_value": "0x01B5C320",
            "second_value": "0x00000000",
            "freed_object": "0x01B5C320",
            "downstream_read_va": "0x00280CD2",
            "downstream_global_value": "0x00000000",
            "fault_address": "0xCCCCCCD0",
        },
        "instrumented_write32_sites": site_count,
        "instrumented_functions": function_count,
        "probe_only": True,
        "guest_memory_semantics_changed": False,
        "value_fabrication": False,
        "write_suppression": False,
        "fault_suppression": False,
        "address_range_widened": False,
        "execution_budget_inherited": 64000000,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6df-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DF] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6DF] instrumented translated WRITE32 sites={site_count} "
        f"functions={function_count}"
    )
    print("[Phase6DF] exact target: guest WRITE32 0028836C")
    print("[Phase6DF] expected hardware lifecycle: 01B5C320 then 00000000")
    print("[Phase6DF] no value fabrication; no write/fault suppression")
    print("[Phase6DF] money line:")
    print("[Phase6DF]   P6DF XACT GLOBAL WRITE SITE: func=... line=... value=00000000")
    print("[Phase6DF] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
