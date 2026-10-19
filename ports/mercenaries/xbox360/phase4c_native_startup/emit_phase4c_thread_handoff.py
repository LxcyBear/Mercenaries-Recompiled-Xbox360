#!/usr/bin/env python3
"""Phase 4C-C: capture the first real startup-thread handoff.

4C-B already proved the exact retail entry reaches kernel ordinal 255 on real
Xbox 360 hardware. 4C-C deliberately does *not* pre-pack a guessed thread
routine. It reuses the hardware-proven 40-body entry closure, decodes the live
PsCreateSystemThreadEx frame, records the actual StartRoutine/contexts, and
stops successfully at a THREAD_TARGET evidence boundary.

The next phase can then package only the routine hardware actually reported.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("phase4c_b_emitter", path)
    if spec is None or spec.loader is None:
        raise SystemExit("[Phase4C-C] could not load Phase 4C-B emitter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def phase4c_c_boundary(base):
    text = base.boundary_support()

    old_enum = """    PHASE4C_BOUNDARY_DEBUGBREAK = 7,
    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8
};"""
    new_enum = """    PHASE4C_BOUNDARY_DEBUGBREAK = 7,
    PHASE4C_BOUNDARY_HEAP_EXHAUSTED = 8,
    PHASE4C_BOUNDARY_THREAD_TARGET = 9,
    PHASE4C_BOUNDARY_KERNEL_FRAME = 10
};"""
    if old_enum not in text:
        raise SystemExit("[Phase4C-C] boundary enum marker changed")
    text = text.replace(old_enum, new_enum)

    old_macro = r'''#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    phase4c_escape( \
        PHASE4C_BOUNDARY_ICALL_SAFE, \
        (DWORD)(xbox_va), \
        (DWORD)(saved_esp)); \
} while (0)'''

    new_macro = r'''#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do { \
    uint32_t _phase4c_target = (uint32_t)(xbox_va); \
    if (_phase4c_target == 0x800000FFu) { \
        phase4c_capture_ps_create_system_thread_ex((uint32_t)(saved_esp)); \
    } else { \
        phase4c_escape( \
            PHASE4C_BOUNDARY_ICALL_SAFE, \
            _phase4c_target, \
            (DWORD)(saved_esp)); \
    } \
} while (0)'''

    if old_macro not in text:
        raise SystemExit("[Phase4C-C] RECOMP_ICALL_SAFE marker changed")
    text = text.replace(old_macro, new_macro)

    text += r'''

static void phase4c_capture_ps_create_system_thread_ex(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    const uint32_t expectedDelta = 44u;
    uint32_t handlePtr;
    uint32_t threadExtra;
    uint32_t kernelStack;
    uint32_t tlsSize;
    uint32_t threadIdPtr;
    uint32_t context1;
    uint32_t context2;
    uint32_t createSuspended;
    uint32_t debugStack;
    uint32_t startRoutine;
    char line[448];

    /*
     * 4C-B hardware observed:
     *   callEsp  = 0x008BFF98
     *   savedEsp = 0x008BFFC4
     *   delta    = 0x2C
     *
     * PsCreateSystemThreadEx has ten 32-bit stdcall arguments. The remaining
     * four bytes are the translated synthetic CALL return slot.
     */
    if (savedEsp != callEsp + expectedDelta) {
        sprintf(
            line,
            "KERNEL FRAME MISMATCH: target=800000FF esp=%08X saved_esp=%08X delta=%u expected=%u",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp),
            (unsigned int)expectedDelta);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000FFu,
            savedEsp);
    }

    /*
     * Do not mutate ESP in this discovery gate. The arguments begin one dword
     * above callEsp because callEsp points at the synthetic return slot.
     */
    handlePtr = GUEST_READ32(callEsp + 4u);
    threadExtra = GUEST_READ32(callEsp + 8u);
    kernelStack = GUEST_READ32(callEsp + 12u);
    tlsSize = GUEST_READ32(callEsp + 16u);
    threadIdPtr = GUEST_READ32(callEsp + 20u);
    context1 = GUEST_READ32(callEsp + 24u);
    context2 = GUEST_READ32(callEsp + 28u);
    createSuspended = GUEST_READ32(callEsp + 32u);
    debugStack = GUEST_READ32(callEsp + 36u);
    startRoutine = GUEST_READ32(callEsp + 40u);

    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000FFu,
            savedEsp);
    }

    sprintf(
        line,
        "PsCreateSystemThreadEx LIVE FRAME: handle_ptr=%08X extra=%u kstack=%u tls=%u tid_ptr=%08X ctx1=%08X ctx2=%08X suspended=%u debug=%u routine=%08X",
        (unsigned int)handlePtr,
        (unsigned int)threadExtra,
        (unsigned int)kernelStack,
        (unsigned int)tlsSize,
        (unsigned int)threadIdPtr,
        (unsigned int)context1,
        (unsigned int)context2,
        (unsigned int)createSuspended,
        (unsigned int)debugStack,
        (unsigned int)startRoutine);
    trace(line);

    sprintf(
        line,
        "PASS: ordinal 255 frame shape is exact; captured live StartRoutine=%08X ctx1=%08X ctx2=%08X",
        (unsigned int)startRoutine,
        (unsigned int)context1,
        (unsigned int)context2);
    trace(line);

    /*
     * THREAD_TARGET is a successful evidence boundary for 4C-C. We stop here
     * intentionally so the next phase packages the routine actually observed
     * on hardware instead of a guessed/static candidate closure.
     */
    phase4c_escape(
        PHASE4C_BOUNDARY_THREAD_TARGET,
        startRoutine,
        savedEsp);
}
'''
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--closure-report", type=Path, required=True)
    ap.add_argument("--phase3n-template", type=Path, required=True)
    ap.add_argument("--phase2e-source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load_base(args.base_emitter)

    report = json.loads(args.closure_report.read_text(encoding="utf-8-sig"))
    if report.get("phase") != "4C-A" or report.get("structural_pass") is not True:
        raise SystemExit("[Phase4C-C] Phase 4C-A report is not a structural PASS")

    root_va = int(str(report["entry"]), 0)
    if root_va != 0x0022964A:
        raise SystemExit(
            f"[Phase4C-C] unexpected XBE entry 0x{root_va:08X}"
        )

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    # Preserve exactly the direct translated body set that passed 4C-B.
    member_vas = [
        int(str(row["address"]), 0)
        for row in report["closure"]["members"]
    ]

    missing_generated = [va for va in member_vas if va not in generated]
    if missing_generated:
        raise SystemExit(
            "[Phase4C-C] generated body missing for base closure member(s): "
            + ", ".join(f"0x{va:08X}" for va in missing_generated)
        )

    root_row = by_va.get(root_va)
    if root_row is None:
        raise SystemExit("[Phase4C-C] XBE entry absent from function inventory")
    root_name = root_row["name"]

    bodies = []
    rendered_by_va = {}
    forward_decls = []
    closure_names = set()

    for va in member_vas:
        row = generated[va]
        name = row["name"]
        closure_names.add(name)
        forward_decls.append(f"static void {name}(void);")
        rendered = base.localize_and_instrument(row["source"], name)
        rendered_by_va[va] = rendered
        bodies.append(rendered)

    template = args.phase3n_template.read_text(encoding="utf-8")
    marker = "/*__P3NB_FORWARD_DECLS__*/"
    marker_index = template.find(marker)
    if marker_index < 0:
        raise SystemExit("[Phase4C-C] Phase-3N support donor marker missing")

    support = template[:marker_index]
    replacements = {
        "__P3NB_ROOT_VA__": f"0x{root_va:08X}u",
        "__P3NB_MEMBER_COUNT__": str(len(member_vas)),
        "__P3NB_DEPTH__": str(int(report["closure"]["max_direct_depth"])),
        "__P3NB_SCALE_COUNT__": str(len(member_vas)),
        "__P3NB_SCALE_GUEST_BYTES__": str(int(report["closure"]["guest_bytes"])),
        "__P3NB_SCALE_SOURCE_BYTES__": str(int(report["closure"]["source_bytes"])),
        "__P3NB_MEMBER_VAS__": ", ".join(
            f"0x{va:08X}u" for va in member_vas
        ),
    }
    for token, value in replacements.items():
        support = support.replace(token, value)

    support = support.replace("[Merc360:P3N]", "[Merc360:P4C]")

    boundary = phase4c_c_boundary(base)

    supplied = base.support_symbols(support + boundary)
    supplied.update(closure_names)
    supplied.update({
        "sub_0022B150",
        "sub_0022B178",
        "sub_0022DDA4",
        "sub_0022E51F",
        "phase4c_capture_ps_create_system_thread_ex",
    })

    unknown = {}
    for va in member_vas:
        row = generated[va]
        rendered = rendered_by_va[va]
        calls = set(base.CALL_RE.findall(base.mask_noncode(rendered)))
        calls.discard(row["name"])
        local_supplied = set(supplied)
        local_supplied.update(base.DEFINE_RE.findall(rendered))
        missing = sorted(
            name for name in calls
            if name not in local_supplied and name not in base.STANDARD_CALLS
        )
        if missing:
            unknown[f"0x{va:08X} {row['name']}"] = missing

    args.out_dir.mkdir(parents=True, exist_ok=True)

    manifest = {
        "phase": "4C-C",
        "build_tag": "P4C-THREAD-20261019-B",
        "entry": f"0x{root_va:08X}",
        "root_name": root_name,
        "pack_members": len(member_vas),
        "policy": "capture-live-pscreatesystemthreadex-start-routine",
        "expected_kernel_target": "0x800000FF",
        "expected_kernel_ordinal": 255,
        "expected_frame_bytes": 44,
        "unknown_direct_helpers": unknown,
        "members": [f"0x{va:08X}" for va in member_vas],
    }
    (args.out_dir / "phase4c-c-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    if unknown:
        print("[Phase4C-C] unsupported direct helper calls found:")
        for owner, names in unknown.items():
            print(f"[Phase4C-C]   {owner}: {', '.join(names)}")
        raise SystemExit(
            "[Phase4C-C] base 4C-B closure unexpectedly gained unresolved "
            "direct helper dependencies"
        )

    env_source = base.build_env_source(
        args.phase2e_source.read_text(encoding="utf-8")
    ).replace("PHASE 4C-B", "PHASE 4C-C")

    driver = base.driver_source(root_name, root_va, len(member_vas))
    driver = driver.replace(
        "P4C-STARTUP-20261019-A",
        "P4C-THREAD-20261019-B",
    )
    driver = driver.replace(
        "Policy: execute the real retail entry and stop at the first live dynamic/indirect boundary",
        "Policy: decode the live PsCreateSystemThreadEx frame and capture the actual StartRoutine",
    )
    driver = driver.replace("PHASE 4C-B", "PHASE 4C-C")
    driver = driver.replace(
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";',
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";\n'
        '    case PHASE4C_BOUNDARY_THREAD_TARGET: return "THREAD_TARGET";\n'
        '    case PHASE4C_BOUNDARY_KERNEL_FRAME: return "KERNEL_FRAME";',
    )

    old_pass = """        boundedPass =
            s_phase4cBoundaryKind >= PHASE4C_BOUNDARY_ICALL &&
            s_phase4cBoundaryKind <= PHASE4C_BOUNDARY_ITAIL_SAFE &&
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x%08Xu;""" % root_va

    new_pass = """        boundedPass =
            (
                (s_phase4cBoundaryKind >= PHASE4C_BOUNDARY_ICALL &&
                 s_phase4cBoundaryKind <= PHASE4C_BOUNDARY_ITAIL_SAFE) ||
                s_phase4cBoundaryKind == PHASE4C_BOUNDARY_THREAD_TARGET
            ) &&
            !s_accessFault &&
            s_traceCount > 0u &&
            s_trace[0] == 0x%08Xu;""" % root_va

    if old_pass not in driver:
        raise SystemExit("[Phase4C-C] bounded PASS policy marker changed")
    driver = driver.replace(old_pass, new_pass)

    driver = driver.replace(
        "PHASE 4C-C BOUNDED REAL STARTUP RESULT",
        "PHASE 4C-C LIVE THREAD-HANDOFF CAPTURE RESULT",
    )

    generated_main = (
        support
        + "\n"
        + boundary
        + "\n\n/* Phase 4C-C: hardware-proven entry closure only */\n"
        + "\n".join(forward_decls)
        + "\n\n#pragma optimize(\"\", off)\n"
        + "\n\n".join(bodies)
        + "\n#pragma optimize(\"\", on)\n"
        + driver
    )

    (args.out_dir / "main.cpp").write_text(generated_main, encoding="utf-8")
    (args.out_dir / "phase4c_env.cpp").write_text(env_source, encoding="utf-8")

    print("[Phase4C-C] LIVE THREAD-HANDOFF CAPTURE PACKAGE READY")
    print(
        f"[Phase4C-C] Preserved 4C-B translated body set: "
        f"{len(member_vas)} bodies"
    )
    print(
        "[Phase4C-C] No guessed thread routine is packed in this gate."
    )
    print(f"[Phase4C-C] main: {args.out_dir / 'main.cpp'}")
    print(f"[Phase4C-C] env:  {args.out_dir / 'phase4c_env.cpp'}")
    print(
        "[Phase4C-C] Runtime policy: validate the 44-byte ordinal-255 frame, "
        "log the actual StartRoutine/contexts, and stop successfully at "
        "THREAD_TARGET."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
