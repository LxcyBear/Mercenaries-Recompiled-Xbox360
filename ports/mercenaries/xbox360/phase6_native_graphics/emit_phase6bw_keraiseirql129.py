#!/usr/bin/env python3
"""Phase 6BW: KeRaiseIrqlToDpcLevel guest-IRQL continuation.

6BV hardware proved that the diagnostic FILE_OBJECT sentinel 0x04000000 was
accepted by retail without any guest dereference before the next kernel call.
Execution advanced fault-free to 0x80000081, Xbox kernel ordinal 129
KeRaiseIrqlToDpcLevel@0, with a canonical 4-byte frame.

Emulate guest IRQL only. Do not alter the real Xenon processor IRQL. Return the
previous guest KIRQL in EAX and raise the maintained guest level to
DISPATCH_LEVEL (2). Keep matching lower-IRQL exports fenced until hardware
actually reaches them.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BV-FILEOBJECT-FIRST-DEREF-20261024-A"
BUILD_TAG = "P6BW-KERAISEIRQL129-20261024-A"
COOKIE_OLD = "phase6bv_env_build_cookie"
COOKIE_NEW = "phase6bw_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BW] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BW] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6BW] RECOMP_ICALL_SAFE macro start missing")
    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6BW] RECOMP_ITAIL anchor missing")

    macro = text[macro_start:next_macro]
    if "_phase4c_target == 0x80000081u" in macro:
        raise SystemExit("[Phase6BW] ordinal 129 already dispatched")

    bs = chr(92)
    inherited = "if (_phase4c_target == 0x800000F6u) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6BW] inherited ordinal-246 dispatch head missing")

    replacement = (
        "if (_phase4c_target == 0x80000081u) { " + bs + "\n"
        "        phase6bw_ke_raise_irql_to_dpc_level((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x800000F6u) { " + bs
    )
    macro = macro[:pos] + replacement + macro[pos + len(inherited):]
    if macro.count("_phase4c_target == 0x80000081u") != 1:
        raise SystemExit("[Phase6BW] ordinal-129 dispatch insertion failed")

    return text[:macro_start] + macro + text[next_macro:]


def install_support(text: str) -> str:
    anchor = "static uint32_t s_phase6bvObRefContinuationCount = 0u;"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6BW] expected one 6BV ObRef state anchor, found {text.count(anchor)}"
        )

    support = r'''static uint32_t s_phase6bwGuestIrql = 0u;
static uint32_t s_phase6bwKeRaiseIrqlCallCount = 0u;
static uint32_t s_phase6bwKeRaiseIrqlSuccessCount = 0u;
static uint32_t s_phase6bwKeRaiseIrqlLastOld = 0u;
static uint32_t s_phase6bwKeRaiseIrqlLastNew = 0u;

static void phase6bw_ke_raise_irql_to_dpc_level(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t oldIrql;
    char line[512];

    if (savedEsp != callEsp + 4u)
    {
        sprintf(
            line,
            "KeRaiseIrqlToDpcLevel FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=4",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000081u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000081u,
            savedEsp);
        return;
    }

    ++s_phase6bwKeRaiseIrqlCallCount;
    oldIrql = s_phase6bwGuestIrql;

    sprintf(
        line,
        "KeRaiseIrqlToDpcLevel LIVE FRAME: ret=%08X old_guest_irql=%u requested_guest_irql=2 esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)oldIrql,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || oldIrql > 2u)
    {
        trace("KeRaiseIrqlToDpcLevel REJECTED: nonzero return slot or guest IRQL already above DISPATCH_LEVEL");
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x80000081u,
            savedEsp);
        return;
    }

    /*
     * Xbox KIRQL levels: PASSIVE=0, APC=1, DISPATCH=2. This is a guest-only
     * scheduling state model. Do not raise the real Xenon/XDK processor IRQL:
     * translated title execution must not hold host interrupts masked across
     * arbitrary guest code.
     */
    s_phase6bwGuestIrql = 2u;
    ++s_phase6bwKeRaiseIrqlSuccessCount;
    s_phase6bwKeRaiseIrqlLastOld = oldIrql;
    s_phase6bwKeRaiseIrqlLastNew = s_phase6bwGuestIrql;

    g_eax = oldIrql;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6BW KeRaiseIrqlToDpcLevel guest continuation old=%u new=%u calls=%u successes=%u new_esp=%08X",
        (unsigned int)oldIrql,
        (unsigned int)s_phase6bwGuestIrql,
        (unsigned int)s_phase6bwKeRaiseIrqlCallCount,
        (unsigned int)s_phase6bwKeRaiseIrqlSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

'''
    return text.replace(anchor, support + anchor, 1)


def insert_arm_trace(text: str) -> str:
    marker = '    trace("PASS: Phase 6BV ordinal 246 ObReferenceObjectByHandle live-frame probe armed");\n'
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6BW] expected one inherited ordinal-246 arm trace, found {text.count(marker)}"
        )
    return text.replace(
        marker,
        marker
        + '    trace("PASS: Phase 6BW ordinal 129 KeRaiseIrqlToDpcLevel guest-IRQL continuation armed");\n',
        1,
    )


def insert_summary(text: str) -> str:
    marker = "P6BV OBREF246 SENTINEL:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BW] inherited 6BV ObRef sentinel summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BW] could not locate inherited summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BV KERAISEIRQL129: calls=%u successes=%u old=%u new=%u current=%u",\n'
        f'{indent}    (unsigned int)s_phase6bwKeRaiseIrqlCallCount,\n'
        f'{indent}    (unsigned int)s_phase6bwKeRaiseIrqlSuccessCount,\n'
        f'{indent}    (unsigned int)s_phase6bwKeRaiseIrqlLastOld,\n'
        f'{indent}    (unsigned int)s_phase6bwKeRaiseIrqlLastNew,\n'
        f'{indent}    (unsigned int)s_phase6bwGuestIrql);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6bw_base")
    p6bl = load(args.phase6bl_emitter, "phase6bw_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bv-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BW] cached Phase 6BV input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BV" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BW] cached Phase 6BV identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BW] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x800000F6u",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "PASS: Phase 6BV ObReferenceObjectByHandle diagnostic continuation",
        "P6BV OBREF246 SENTINEL:",
        "P6BV KEDELAY99:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BW] inherited 6BV marker missing: {marker}")

    main_text = install_support(main_text)
    main_text = patch_icall_dispatch(main_text)
    main_text = insert_arm_trace(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BW ordinal-129 KeRaiseIrqlToDpcLevel guest-only IRQL continuation; 6BV proved FILE_OBJECT sentinel survives without dereference; preserve sentinel, file/delay/GPU semantics, allocator geometry, 8M budget and hard MMIO fences",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BV", "PHASE 6BW")
        .replace("Phase 6BV", "Phase 6BW")
        .replace('"P6BV ', '"P6BW ')
    )
    env_text = (
        env_text.replace("PHASE 6BV", "PHASE 6BW")
        .replace("Phase 6BV", "Phase 6BW")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x80000081u",
        "KeRaiseIrqlToDpcLevel LIVE FRAME:",
        "PASS: Phase 6BW KeRaiseIrqlToDpcLevel guest continuation",
        "P6BW KERAISEIRQL129:",
        "P6BW OBREF246 SENTINEL:",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BW] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BW",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bw_ke_raise_irql_to_dpc_level"] = {
        "source_phase": "6BV",
        "phase6bv_hardware": {
            "obref246_continuation_calls": 1,
            "handle": "0x48000001",
            "object_type": "0x80000047",
            "returned_sentinel": "0x04000000",
            "sentinel_guest_dereference_observed_before_next_boundary": False,
            "next_boundary_target": "0x80000081",
            "next_boundary_ordinal": 129,
            "next_boundary_name": "KeRaiseIrqlToDpcLevel",
            "frame_bytes": 4,
            "fault": 0,
        },
        "continuation": {
            "guest_irql_initial": 0,
            "dispatch_level": 2,
            "returns_previous_irql_in_eax": True,
            "changes_native_xenon_irql": False,
            "matching_lower_irql_exports_remain_fenced": True,
        },
        "translated_membership_changed": False,
        "file_object_sentinel_preserved": True,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bw-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BW] 6BV hardware: FILE_OBJECT sentinel accepted without dereference")
    print("[Phase6BW] next boundary: 80000081 = ordinal 129 KeRaiseIrqlToDpcLevel@0")
    print("[Phase6BW] frame: canonical 4 bytes, fault=0")
    print("[Phase6BW] guest IRQL continuation: old level -> EAX, current level -> DISPATCH_LEVEL(2)")
    print("[Phase6BW] real Xenon/XDK processor IRQL is not changed")
    print("[Phase6BW] lower-IRQL paths remain fenced pending hardware evidence")
    print("[Phase6BW] translated membership unchanged")
    print("[Phase6BW] all 6BV file/sentinel/delay/GPU/allocator/8M-budget invariants inherited")
    print("[Phase6BW] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
