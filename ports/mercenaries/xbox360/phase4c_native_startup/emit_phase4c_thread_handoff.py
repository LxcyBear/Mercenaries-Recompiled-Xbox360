#!/usr/bin/env python3
"""Phase 4C-C: emit the first startup-thread handoff XDK package.

This layers the proven 4C-B package machinery with one additional live kernel
path: ordinal 255 / PsCreateSystemThreadEx. The first title thread is entered
synchronously and execution stops at the next live dynamic/kernel boundary.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path


THREAD_ROOTS = (0x0022B43F, 0x002295D6)


def load_base(path: Path):
    spec = importlib.util.spec_from_file_location("phase4c_b_emitter", path)
    if spec is None or spec.loader is None:
        raise SystemExit("[Phase4C-C] could not load Phase 4C-B emitter")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def generated_direct_closure(base, roots, generated):
    name_to_va = {row["name"]: va for va, row in generated.items()}
    pending = list(roots)
    seen = set()

    while pending:
        va = pending.pop()
        if va in seen:
            continue

        row = generated.get(va)
        if row is None:
            raise SystemExit(
                f"[Phase4C-C] translated startup root/dependency "
                f"0x{va:08X} is absent from the generated tree"
            )

        seen.add(va)
        calls = set(base.CALL_RE.findall(base.mask_noncode(row["source"])))
        for name in calls:
            dep = name_to_va.get(name)
            if dep is not None and dep not in seen:
                pending.append(dep)

    return sorted(seen)


def pack_lookup_source(member_vas, generated):
    lines = [
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)",
        "{",
        "    switch (xbox_va) {",
    ]
    for va in member_vas:
        lines.append(
            f"    case 0x{va:08X}u: return {generated[va]['name']};"
        )
    lines += [
        "    default: return (recomp_func_t)0;",
        "    }",
        "}",
        "",
    ]
    return "\n".join(lines)


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
    const uint32_t _phase4c_saved_ebx = g_ebx; \
    const uint32_t _phase4c_saved_esi = g_esi; \
    const uint32_t _phase4c_saved_edi = g_edi; \
    if (_phase4c_target == 0x800000FFu) { \
        phase4c_follow_ps_create_system_thread_ex((uint32_t)(saved_esp)); \
        g_ebx = _phase4c_saved_ebx; \
        g_esi = _phase4c_saved_esi; \
        g_edi = _phase4c_saved_edi; \
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

static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va);

static void phase4c_follow_ps_create_system_thread_ex(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
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
    recomp_func_t fn;
    char line[384];

    /*
     * 4C-B hardware proved savedEsp - callEsp == 0x2C:
     * ten dword arguments plus the synthetic CALL return.
     */
    if (savedEsp != callEsp + 44u) {
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000FFu,
            savedEsp);
    }

    /* Match kernel_thunk_dispatch: pop the synthetic CALL return first. */
    g_esp += 4u;

    handlePtr = GUEST_READ32(g_esp + 0u);
    threadExtra = GUEST_READ32(g_esp + 4u);
    kernelStack = GUEST_READ32(g_esp + 8u);
    tlsSize = GUEST_READ32(g_esp + 12u);
    threadIdPtr = GUEST_READ32(g_esp + 16u);
    context1 = GUEST_READ32(g_esp + 20u);
    context2 = GUEST_READ32(g_esp + 24u);
    createSuspended = GUEST_READ32(g_esp + 28u);
    debugStack = GUEST_READ32(g_esp + 32u);
    startRoutine = GUEST_READ32(g_esp + 36u);

    sprintf(
        line,
        "PsCreateSystemThreadEx: handle_ptr=%08X extra=%u kstack=%u tls=%u tid_ptr=%08X ctx1=%08X ctx2=%08X suspended=%u debug=%u routine=%08X",
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

    if (s_accessFault) {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000FFu,
            savedEsp);
    }

    if (handlePtr != 0u)
        GUEST_WRITE32(handlePtr, 0xBEEF0001u);
    if (threadIdPtr != 0u)
        GUEST_WRITE32(threadIdPtr, 1u);

    fn = phase4c_lookup_pack_func(startRoutine);
    if (!fn) {
        phase4c_escape(
            PHASE4C_BOUNDARY_THREAD_TARGET,
            startRoutine,
            savedEsp);
    }

    sprintf(
        line,
        "PASS: ordinal 255 frame decoded; entering translated StartRoutine %08X synchronously",
        (unsigned int)startRoutine);
    trace(line);

    /*
     * Match the production bridge's first-title-thread model: push two
     * contexts and a synthetic return slot, then enter the translated routine
     * synchronously on the recompiled CPU state.
     */
    g_esp -= 4u; GUEST_WRITE32(g_esp, context2);
    g_esp -= 4u; GUEST_WRITE32(g_esp, context1);
    g_esp -= 4u; GUEST_WRITE32(g_esp, 0u);

    fn();

    /*
     * The title thread should not return during this bounded slice. If it
     * does, restore the caller-visible stdcall result exactly.
     */
    g_esp = savedEsp;
    g_eax = 0u;
    trace("PsCreateSystemThreadEx: translated StartRoutine returned");
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

    base_members = {
        int(str(row["address"]), 0)
        for row in report["closure"]["members"]
    }
    thread_members = set(
        generated_direct_closure(base, THREAD_ROOTS, generated)
    )
    member_vas = sorted(base_members | thread_members)

    for va in member_vas:
        if va not in generated:
            raise SystemExit(
                f"[Phase4C-C] generated body missing for 0x{va:08X}"
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

    pack_guest_bytes = 0
    for va in member_vas:
        raw_size = by_va.get(va, {}).get("size", 0)
        try:
            pack_guest_bytes += int(str(raw_size), 0)
        except (TypeError, ValueError):
            pass

    pack_source_bytes = sum(
        len(generated[va]["source"].encode("utf-8"))
        for va in member_vas
    )

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
        "__P3NB_SCALE_GUEST_BYTES__": str(pack_guest_bytes),
        "__P3NB_SCALE_SOURCE_BYTES__": str(pack_source_bytes),
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
        "phase4c_lookup_pack_func",
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
        "build_tag": "P4C-THREAD-20261019-A",
        "entry": f"0x{root_va:08X}",
        "root_name": root_name,
        "pack_members": len(member_vas),
        "base_entry_members": len(base_members),
        "thread_roots": [f"0x{va:08X}" for va in THREAD_ROOTS],
        "thread_root_union_members": len(thread_members),
        "pack_guest_bytes": pack_guest_bytes,
        "pack_source_bytes": pack_source_bytes,
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
            "[Phase4C-C] refusing to emit a thread-handoff XEX with "
            "unresolved direct helper dependencies"
        )

    env_source = base.build_env_source(
        args.phase2e_source.read_text(encoding="utf-8")
    ).replace("PHASE 4C-B", "PHASE 4C-C")

    driver = base.driver_source(root_name, root_va, len(member_vas))
    driver = driver.replace(
        "P4C-STARTUP-20261019-A",
        "P4C-THREAD-20261019-A",
    )
    driver = driver.replace(
        "Policy: execute the real retail entry and stop at the first live dynamic/indirect boundary",
        "Policy: follow ordinal 255 into the first translated title thread and stop at the next live boundary",
    )
    driver = driver.replace("PHASE 4C-B", "PHASE 4C-C")
    driver = driver.replace(
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";',
        '    case PHASE4C_BOUNDARY_HEAP_EXHAUSTED: return "HEAP_EXHAUSTED";\n'
        '    case PHASE4C_BOUNDARY_THREAD_TARGET: return "THREAD_TARGET";\n'
        '    case PHASE4C_BOUNDARY_KERNEL_FRAME: return "KERNEL_FRAME";',
    )

    generated_main = (
        support
        + "\n"
        + boundary
        + "\n\n/* Phase 4C-C translated startup + first-thread closure */\n"
        + "\n".join(forward_decls)
        + "\n\n"
        + pack_lookup_source(member_vas, generated)
        + "\n#pragma optimize(\"\", off)\n"
        + "\n\n".join(bodies)
        + "\n#pragma optimize(\"\", on)\n"
        + driver
    )

    (args.out_dir / "main.cpp").write_text(generated_main, encoding="utf-8")
    (args.out_dir / "phase4c_env.cpp").write_text(env_source, encoding="utf-8")

    print("[Phase4C-C] THREAD-HANDOFF XDK PACKAGE READY")
    print(
        f"[Phase4C-C] Entry: {root_name} @ 0x{root_va:08X}; "
        f"pack={len(member_vas)} bodies"
    )
    print(
        "[Phase4C-C] Startup roots packed: "
        + ", ".join(f"0x{va:08X}" for va in THREAD_ROOTS)
    )
    print(
        f"[Phase4C-C] Thread-root closure contributes "
        f"{len(thread_members)} generated bodies before union"
    )
    print(f"[Phase4C-C] main: {args.out_dir / 'main.cpp'}")
    print(f"[Phase4C-C] env:  {args.out_dir / 'phase4c_env.cpp'}")
    print(
        "[Phase4C-C] Runtime policy: decode ordinal 255, validate/log the "
        "actual StartRoutine, enter it synchronously, then escape at the "
        "next live boundary."
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
