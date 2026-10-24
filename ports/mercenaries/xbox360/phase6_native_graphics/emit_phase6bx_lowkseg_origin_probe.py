#!/usr/bin/env python3
"""Phase 6BX: classify the immediate low-KSEG read after 6BW.

6BW hardware proved ordinal 129 KeRaiseIrqlToDpcLevel with a canonical @0
frame and guest IRQL transition 0 -> 2. The very next translated access was a
READ32 at 0x8000018D from retail path 0x0022AC56 -> 0x0022AC78 ->
0x0022AC89 -> 0x0022AC8F. The existing memory contract intentionally fences
0x80000000..0x80000FFF because that page is ambiguous between low KSEG0 and
kernel/import-like values.

The exact Phase-4A retail import set has no ordinal 0x18D/397, but that alone
is not sufficient to relax the fence. This stage changes no guest semantics.
It records the guest register state at the four hardware-proven retail VAs so
we can identify where 0x8000018D is formed. The low-KSEG fence remains intact.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BW-KERAISEIRQL129-20261024-A"
BUILD_TAG = "P6BX-LOWKSEG-ORIGIN-PROBE-20261024-A"
COOKIE_OLD = "phase6bw_env_build_cookie"
COOKIE_NEW = "phase6bx_env_build_cookie"

PROBE_VAS = (0x0022AC56, 0x0022AC78, 0x0022AC89, 0x0022AC8F)
FAULT_ADDRESS = 0x8000018D


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BX] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BX] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def find_function(text: str, base, name: str) -> tuple[str, int, int]:
    masked = base.mask_noncode(text)
    signature = f"static void {name}(void)"
    defs = []
    cursor = 0
    while True:
        pos = masked.find(signature, cursor)
        if pos < 0:
            break
        probe = pos + len(signature)
        while probe < len(masked) and masked[probe].isspace():
            probe += 1
        if probe < len(masked) and masked[probe] == "{":
            defs.append((pos, probe))
        cursor = pos + len(signature)
    if len(defs) != 1:
        raise SystemExit(
            f"[Phase6BX] expected one translated {name} definition, found {len(defs)}"
        )
    start, brace = defs[0]
    end = base.closing_brace(masked, brace)
    return text[start:end], start, end


def install_probe_state(text: str) -> str:
    marker = "static DWORD s_phase4cBlockTicks = 0u;\n"
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6BX] expected one budget-state anchor, found {text.count(marker)}"
        )
    block = marker + (
        "static DWORD s_phase6bxLowKsegProbeHits = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastVa = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEax = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEcx = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEdx = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEbx = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEsi = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEdi = 0u;\n"
        "static DWORD s_phase6bxLowKsegLastEsp = 0u;\n"
    )
    return text.replace(marker, block, 1)


def instrument_budget_tick(text: str) -> str:
    marker = """static void phase4c_budget_tick(DWORD va)
{
    ++s_phase4cBlockTicks;
"""
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6BX] expected one phase4c_budget_tick head, found {text.count(marker)}"
        )

    probe = """static void phase4c_budget_tick(DWORD va)
{
    ++s_phase4cBlockTicks;

    if (va == 0x0022AC56u ||
        va == 0x0022AC78u ||
        va == 0x0022AC89u ||
        va == 0x0022AC8Fu)
    {
        char p6bxLine[320];
        ++s_phase6bxLowKsegProbeHits;
        s_phase6bxLowKsegLastVa = va;
        s_phase6bxLowKsegLastEax = g_eax;
        s_phase6bxLowKsegLastEcx = g_ecx;
        s_phase6bxLowKsegLastEdx = g_edx;
        s_phase6bxLowKsegLastEbx = g_ebx;
        s_phase6bxLowKsegLastEsi = g_esi;
        s_phase6bxLowKsegLastEdi = g_edi;
        s_phase6bxLowKsegLastEsp = g_esp;
        sprintf(
            p6bxLine,
            "P6BX LOWKSEG ORIGIN: va=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X guest_irql=%u hits=%u",
            (unsigned int)va,
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_ebx,
            (unsigned int)g_esi,
            (unsigned int)g_edi,
            (unsigned int)g_esp,
            (unsigned int)s_phase6bwGuestIrql,
            (unsigned int)s_phase6bxLowKsegProbeHits);
        trace(p6bxLine);
    }
"""
    return text.replace(marker, probe, 1)


def install_summary(text: str) -> str:
    marker = "P6BW KERAISEIRQL129:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BX] inherited 6BW IRQL summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BX] could not locate inherited 6BW summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BW LOWKSEG ORIGIN: hits=%u last_va=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegProbeHits,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastVa,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEax,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEcx,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEdx,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEbx,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEsi,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEdi,\n'
        f'{indent}    (unsigned int)s_phase6bxLowKsegLastEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def write_forensic_report(out_dir: Path, body: str) -> dict:
    lines = body.splitlines()
    interesting = []
    for i, line in enumerate(lines, 1):
        s = line.strip()
        if (
            "PHASE4C_BUDGET_TICK" in s
            or "GUEST_READ" in s
            or "GUEST_WRITE" in s
            or "RECOMP_ICALL" in s
            or "RECOMP_CALL" in s
            or "800000" in s
            or "002DBD" in s
        ):
            interesting.append({"line": i, "source": s})

    report = out_dir / "phase6bx-sub_0022AC56-forensic.txt"
    payload = [
        "PHASE 6BX SUB_0022AC56 FORENSIC",
        "hardware_path=0022AC56 -> 0022AC78 -> 0022AC89 -> 0022AC8F",
        "hardware_fault=READ32 0x8000018D",
        "semantics_changed=false",
        "",
        "=== INTERESTING GENERATED LINES ===",
    ]
    for row in interesting:
        payload.append(f"{row['line']:04d}: {row['source']}")
    report.write_text("\n".join(payload) + "\n", encoding="utf-8")
    return {
        "function": "sub_0022AC56",
        "line_count": len(lines),
        "interesting_lines": interesting,
        "report": report.name,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6bx_base")
    p6bl = load(args.phase6bl_emitter, "phase6bx_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bw-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BX] cached Phase 6BW input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BW" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BX] cached Phase 6BW identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BX] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x80000081u",
        "PASS: Phase 6BW KeRaiseIrqlToDpcLevel guest continuation",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
        "MERC_SYNTH_FENCE_BASE",
        "MERC_SYNTH_FENCE_END",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BX] inherited 6BW marker missing: {marker}")

    # Static generated-source proof for the exact retail function that owns the
    # hardware path. This is diagnostic evidence only; the body is not edited.
    body, _, _ = find_function(main_text, base, "sub_0022AC56")
    args.out_dir.mkdir(parents=True, exist_ok=True)
    forensic = write_forensic_report(args.out_dir, body)

    tick_markers = {
        va: f"PHASE4C_BUDGET_TICK(0x{va:08X}u)"
        for va in PROBE_VAS
    }
    missing_ticks = [f"0x{va:08X}" for va, mark in tick_markers.items() if mark not in body]
    if missing_ticks:
        raise SystemExit(
            "[Phase6BX] translated sub_0022AC56 is missing hardware-proven block tick(s): "
            + ", ".join(missing_ticks)
        )

    main_text = install_probe_state(main_text)
    main_text = instrument_budget_tick(main_text)
    main_text = install_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BX non-mutating low-KSEG origin probe at retail VAs 0022AC56/78/89/8F; preserve the 80000000-80000FFF synthetic fence, guest IRQL model, FILE_OBJECT sentinel, all file/delay/GPU semantics, allocator geometry and 8M budget",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BW", "PHASE 6BX")
        .replace("Phase 6BW", "Phase 6BX")
        .replace('"P6BW ', '"P6BX ')
    )
    env_text = (
        env_text.replace("PHASE 6BW", "PHASE 6BX")
        .replace("Phase 6BW", "Phase 6BX")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6BX LOWKSEG ORIGIN: va=%08X",
        "P6BX LOWKSEG ORIGIN: hits=%u",
        "MERC_SYNTH_FENCE_BASE",
        "MERC_SYNTH_FENCE_END",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BX] generated source lost marker: {marker}")

    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BX",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bx_low_kseg_origin_probe"] = {
        "source_phase": "6BW",
        "phase6bw_hardware": {
            "ke_raise_irql_calls": 1,
            "ke_raise_irql_successes": 1,
            "guest_irql_old": 0,
            "guest_irql_new": 2,
            "fault_access": "READ32",
            "fault_address": "0x8000018D",
            "fault": 1,
            "retail_path": [f"0x{x:08X}" for x in PROBE_VAS],
        },
        "classification": {
            "inside_low_kseg_synthetic_fence": True,
            "phase4a_exact_import_ordinal_397_present": False,
            "do_not_route_as_kernel_export": True,
            "low_kseg_alias_not_relaxed": True,
        },
        "probe": {
            "non_mutating": True,
            "vas": [f"0x{x:08X}" for x in PROBE_VAS],
            "registers": ["eax", "ecx", "edx", "ebx", "esi", "edi", "esp"],
            "generated_source_forensic": forensic,
        },
        "translated_membership_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bx-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BX] 6BW hardware: KeRaiseIrqlToDpcLevel PASS old=0 new=2")
    print("[Phase6BX] immediate next access: READ32 guest=8000018D fault=1")
    print("[Phase6BX] 8000018D lies inside the intentionally fenced low-KSEG page")
    print("[Phase6BX] Phase-4A exact retail import set contains no ordinal 397 / 0x18D")
    print("[Phase6BX] low-KSEG fence remains unchanged")
    print("[Phase6BX] probe VAs: 0022AC56 0022AC78 0022AC89 0022AC8F")
    print(f"[Phase6BX] SOURCE FORENSIC: {args.out_dir / forensic['report']}")
    for row in forensic["interesting_lines"]:
        print(f"[Phase6BX] SRC {row['line']:04d}: {row['source']}")
    print("[Phase6BX] translated membership unchanged; guest semantics unchanged")
    print("[Phase6BX] all 6BW file/sentinel/delay/GPU/allocator/8M-budget invariants inherited")
    print("[Phase6BX] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
