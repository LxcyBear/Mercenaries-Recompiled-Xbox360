#!/usr/bin/env python3
r"""Phase 6CY: exact translated READ32 source-site probe for CCCCCCD0.

6CX hardware proved the ExFreePool ITAIL continuation and then advanced into
fresh post-DSOUND object setup before stopping on:
    GUEST_FAULT READ32 0xCCCCCCD0
    eax=0xCCCCCCCC
    caller=0x0023A3CE
    ticks=27,021,609 trace=1,071,691

0xCCCCCCCC is the debug/uninitialized poison pattern. 6CY does not fabricate a
value or widen guest memory. It reuses the proven Phase-6AL technique: tag every
translated GUEST_READ32 expansion with its owning translated function VA and
compiler source line, then report the exact site when the checked guest router
latches the fault.

All 6CX semantics remain intact, including the ExFreePool ITAIL continuation,
manual DSOUND decryptor, shadow-RAM alias, XACT async I/O, D3D/XGRPH/APU state,
64M watchdog and all hard fences.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CX-EXFREEPOOL-ITAIL-80000011-20261026-A"
BUILD_TAG = "P6CY-READ32-CCCCCCD0-SITE-20261026-A"
COOKIE_OLD = "phase6cx_env_build_cookie"
COOKIE_NEW = "phase6cy_env_build_cookie"
EMITTER_REVISION = "6CY-R1"

TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
READ32_RE = re.compile(r"\bGUEST_READ32\s*\(")


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CY] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def translated_bounds(text: str) -> tuple[int, int]:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off = text.find(off_marker)
    if off < 0:
        raise SystemExit("[Phase6CY] optimize-off marker missing")
    start = off + len(off_marker)
    end = text.find(on_marker, start)
    if end < 0:
        raise SystemExit("[Phase6CY] optimize-on marker missing")
    return start, end


def instrument_translated_read32(text: str, base) -> tuple[str, int, int]:
    body_start, body_end = translated_bounds(text)
    body = text[body_start:body_end]
    masked = base.mask_noncode(body)
    funcs = list(base.FUNC_RE.finditer(masked))
    if not funcs:
        raise SystemExit("[Phase6CY] translated body contains no functions")

    insertions: list[tuple[int, str]] = []
    total_reads = 0

    for match in funcs:
        brace = masked.find("{", match.start(), match.end())
        if brace < 0:
            raise SystemExit("[Phase6CY] translated function opening brace missing")
        func_end = base.closing_brace(masked, brace)
        func_masked = masked[match.start():func_end]
        read_count = len(READ32_RE.findall(func_masked))
        total_reads += read_count

        trace_match = TRACE_RE.search(func_masked)
        if trace_match:
            va = int(trace_match.group(1), 16)
        else:
            name = match.group(1)
            m = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
            if not m:
                raise SystemExit(
                    f"[Phase6CY] translated function has no recoverable VA: {name}"
                )
            va = int(m.group(1), 16)

        insertions.append(
            (
                brace + 1,
                f"\n    const DWORD phase6cy_function_va = 0x{va:08X}u;"
            )
        )

    if total_reads == 0:
        raise SystemExit("[Phase6CY] no translated GUEST_READ32 call sites found")

    pieces: list[str] = []
    cursor = 0
    for pos, payload in sorted(insertions):
        if pos < cursor:
            raise SystemExit("[Phase6CY] overlapping function-VA insertions")
        pieces.append(body[cursor:pos])
        pieces.append(payload)
        cursor = pos
    pieces.append(body[cursor:])
    body = "".join(pieces)

    prefix = (
        "#undef GUEST_READ32\n"
        "#define GUEST_READ32(addr) "
        "phase6cy_read32_site(phase6cy_function_va, (DWORD)__LINE__, "
        "(uint32_t)(addr))\n"
    )
    suffix = (
        "\n#undef GUEST_READ32\n"
        "#define GUEST_READ32(addr) recomp_guest_read32((uint32_t)(addr))\n"
    )
    body = prefix + body + suffix
    return text[:body_start] + body + text[body_end:], total_reads, len(funcs)


def install_site_support(text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CY] support insertion marker missing")

    block = r'''
static DWORD s_phase6cyRead32Function = 0u;
static DWORD s_phase6cyRead32Line = 0u;
static DWORD s_phase6cyRead32Address = 0u;
static DWORD s_phase6cyRead32Hits = 0u;
static DWORD s_phase6cyFaultSiteReports = 0u;

static uint32_t phase6cy_read32_site(
    DWORD functionVa,
    DWORD sourceLine,
    uint32_t address)
{
    uint32_t value;

    s_phase6cyRead32Function = functionVa;
    s_phase6cyRead32Line = sourceLine;
    s_phase6cyRead32Address = address;
    ++s_phase6cyRead32Hits;

    /* Direct call preserves the existing checked guest-memory semantics. */
    value = recomp_guest_read32(address);

    if (s_accessFault)
    {
        char line[384];
        ++s_phase6cyFaultSiteReports;
        sprintf(
            line,
            "P6CY READ32 FAULT SITE: func=%08X line=%u address=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X reports=%u",
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
            (unsigned int)s_phase6cyFaultSiteReports);
        trace(line);

        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            address,
            g_esp);
    }

    return value;
}

'''
    return text[:pos] + block + text[pos:]


def insert_summary(text: str, site_count: int, function_count: int) -> str:
    marker = "P6CX EXFREEPOOL ITAIL:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CY] inherited 6CX summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6CY] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CY READ32 SITE PROBE: calls=%u last_func=%08X last_line=%u last_address=%08X fault_reports=%u instrumented_sites={site_count} instrumented_functions={function_count}",\n'
        f'{indent}    (unsigned int)s_phase6cyRead32Hits,\n'
        f'{indent}    (unsigned int)s_phase6cyRead32Function,\n'
        f'{indent}    (unsigned int)s_phase6cyRead32Line,\n'
        f'{indent}    (unsigned int)s_phase6cyRead32Address,\n'
        f'{indent}    (unsigned int)s_phase6cyFaultSiteReports);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CY] expected one inherited build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6CX", "PHASE 6CY")
        .replace("Phase 6CX", "Phase 6CY")
        .replace('"P6CX ', '"P6CY ')
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cy_base")
    p6bl = load(args.phase6bl_emitter, "phase6cy_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cx-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CY] missing cached 6CX input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6CX" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CY] cached 6CX identity mismatch")

    cx = manifest.get("phase6cx_exfreepool_itail", {})
    if (
        cx.get("execution_budget_inherited") != 64000000
        or cx.get("hard_fences_weakened") is not False
        or cx.get("kernel_itail_ordinal24_preserved") is not True
        or cx.get("packed_itail_dispatch_preserved") is not True
    ):
        raise SystemExit("[Phase6CY] inherited 6CX policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "PASS: Phase 6CX ExFreePool ITAIL",
        "phase6cx_ex_free_pool_itail();",
        "PASS: Phase 6CX manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CX APU CORE:",
        "P6CX AV/DISPLAY SUMMARY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CY] inherited 6CX marker missing: {marker}")

    if "P6AL READ32 FAULT SITE:" in main_text or "phase6al_read32_site(" in main_text:
        raise SystemExit("[Phase6CY] stale Phase6AL READ32 wrapper unexpectedly present")
    if "P6CY READ32 FAULT SITE:" in main_text:
        raise SystemExit("[Phase6CY] source already instrumented")

    main_text, site_count, function_count = instrument_translated_read32(
        main_text, base
    )
    main_text = install_site_support(main_text)
    main_text = insert_summary(main_text, site_count, function_count)
    main_text = relabel(main_text)
    env_text = relabel(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CY READ32 FAULT SITE:",
        "phase6cy_read32_site(phase6cy_function_va",
        "PASS: Phase 6CY ExFreePool ITAIL",
        "PASS: Phase 6CY manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CY APU CORE:",
        "P6CY AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CY] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6CY",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6cy_read32_ccccccd0_probe"] = {
        "source_phase": "6CX",
        "phase6cx_hardware": {
            "exfreepool_itail_pass": True,
            "exfreepool_address": "0x01B5DE60",
            "exfreepool_size": 18612,
            "exfreepool_freed": True,
            "next_boundary": {
                "kind": "GUEST_FAULT",
                "access": "READ",
                "width": 4,
                "guest": "0xCCCCCCD0",
                "eax": "0xCCCCCCCC",
                "caller": "0x0023A3CE",
                "ticks": 27021609,
                "trace": 1071691,
                "fault": 1,
            },
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "probe_only": True,
        "guest_memory_semantics_changed": False,
        "boundary_timing_changed": True,
        "instrumented_read32_sites": site_count,
        "instrumented_functions": function_count,
        "execution_budget_inherited": 64000000,
        "exfreepool_itail_preserved": True,
        "manual_dsound_decrypt_preserved": True,
        "shadow_ram_alias_preserved": True,
        "graphics_semantics_changed": False,
        "apu_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6cy-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CY] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6CY] instrumented translated READ32 sites={site_count} "
        f"functions={function_count}"
    )
    print("[Phase6CY] target hardware fault: READ32 CCCCCCD0 with eax=CCCCCCCC")
    print("[Phase6CY] guest-memory semantics unchanged; probe-only immediate site report")
    print("[Phase6CY] ExFreePool ITAIL / DSOUND / shadow RAM / APU / graphics preserved")
    print("[Phase6CY] money line: P6CY READ32 FAULT SITE: func=... line=... address=CCCCCCD0")
    print("[Phase6CY] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
