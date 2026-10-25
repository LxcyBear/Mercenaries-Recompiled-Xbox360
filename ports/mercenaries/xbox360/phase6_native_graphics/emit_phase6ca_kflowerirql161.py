#!/usr/bin/env python3
"""Phase 6CA: ordinal-161 KfLowerIrql guest-only IRQL continuation.

6BZ hardware validated the direct IdexChannelObject/KDEVICE_QUEUE model and
then reached 0x800000A1 (ordinal 161 KfLowerIrql) with a canonical 4-byte
frame. The boundary had ECX=0x0087E000; KIRQL is byte-sized under FASTCALL,
so the live argument is CL=0. Restore only the maintained guest IRQL state.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BZ-IDEX357-DEVICEQUEUE-20261024-A"
BUILD_TAG = "P6CA-KFLOWERIRQL161-20261024-A"
COOKIE_OLD = "phase6bz_env_build_cookie"
COOKIE_NEW = "phase6ca_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CA] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CA] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6CA] RECOMP_ICALL_SAFE macro start missing")
    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6CA] RECOMP_ITAIL anchor missing")
    macro = text[macro_start:next_macro]
    if "_phase4c_target == 0x800000A1u" in macro:
        raise SystemExit("[Phase6CA] ordinal 161 already dispatched")
    bs = chr(92)
    inherited = "if (_phase4c_target == 0x80000081u) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6CA] inherited ordinal-129 dispatch head missing")
    replacement = (
        "if (_phase4c_target == 0x800000A1u) { " + bs + "\n"
        "        phase6ca_kf_lower_irql((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x80000081u) { " + bs
    )
    macro = macro[:pos] + replacement + macro[pos + len(inherited):]
    return text[:macro_start] + macro + text[next_macro:]


def install_support(text: str) -> str:
    anchor = "static uint32_t s_phase6bvObRefContinuationCount = 0u;"
    if text.count(anchor) != 1:
        raise SystemExit(f"[Phase6CA] expected one ObRef state anchor, found {text.count(anchor)}")
    support = r"""static uint32_t s_phase6caKfLowerIrqlCallCount = 0u;
static uint32_t s_phase6caKfLowerIrqlSuccessCount = 0u;
static uint32_t s_phase6caKfLowerIrqlLastOld = 0u;
static uint32_t s_phase6caKfLowerIrqlLastNew = 0u;
static uint32_t s_phase6caKfLowerIrqlLastRawEcx = 0u;

static void phase6ca_kf_lower_irql(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t oldIrql;
    uint32_t newIrql;
    uint32_t rawEcx;
    char line[640];

    if (savedEsp != callEsp + 4u)
    {
        sprintf(line,
            "KfLowerIrql FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=4",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x800000A1u, savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x800000A1u, savedEsp);
        return;
    }

    ++s_phase6caKfLowerIrqlCallCount;
    oldIrql = s_phase6bwGuestIrql;
    rawEcx = g_ecx;
    newIrql = rawEcx & 0xFFu;

    sprintf(line,
        "KfLowerIrql LIVE FRAME: ret=%08X raw_ecx=%08X new_guest_irql=%u old_guest_irql=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)rawEcx,
        (unsigned int)newIrql,
        (unsigned int)oldIrql,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || oldIrql > 2u || newIrql > 2u || newIrql > oldIrql)
    {
        trace("KfLowerIrql REJECTED: invalid guest IRQL lowering transition");
        phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE, 0x800000A1u, savedEsp);
        return;
    }

    /* KfLowerIrql is FASTCALL; KIRQL is byte-sized, so only CL is semantic. */
    s_phase6bwGuestIrql = newIrql;
    ++s_phase6caKfLowerIrqlSuccessCount;
    s_phase6caKfLowerIrqlLastOld = oldIrql;
    s_phase6caKfLowerIrqlLastNew = newIrql;
    s_phase6caKfLowerIrqlLastRawEcx = rawEcx;

    /* VOID FASTCALL: preserve guest EAX and clean no stack arguments. */
    g_esp = savedEsp;

    sprintf(line,
        "PASS: Phase 6CA KfLowerIrql guest continuation old=%u new=%u raw_ecx=%08X calls=%u successes=%u new_esp=%08X",
        (unsigned int)oldIrql,
        (unsigned int)newIrql,
        (unsigned int)rawEcx,
        (unsigned int)s_phase6caKfLowerIrqlCallCount,
        (unsigned int)s_phase6caKfLowerIrqlSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

"""
    return text.replace(anchor, support + anchor, 1)


def insert_arm_trace(text: str) -> str:
    marker = '    trace("PASS: Phase 6BZ ordinal 129 KeRaiseIrqlToDpcLevel guest-IRQL continuation armed");\n'
    if text.count(marker) != 1:
        raise SystemExit("[Phase6CA] inherited ordinal-129 arm trace missing")
    return text.replace(
        marker,
        marker + '    trace("PASS: Phase 6CA ordinal 161 KfLowerIrql guest-IRQL continuation armed");\n',
        1,
    )


def insert_summary(text: str) -> str:
    marker = "P6BZ KERAISEIRQL129:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CA] inherited IRQL summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CA] could not locate inherited IRQL summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CA KFLOWERIRQL161: calls=%u successes=%u old=%u new=%u raw_ecx=%08X current=%u",\n'
        f'{indent}    (unsigned int)s_phase6caKfLowerIrqlCallCount,\n'
        f'{indent}    (unsigned int)s_phase6caKfLowerIrqlSuccessCount,\n'
        f'{indent}    (unsigned int)s_phase6caKfLowerIrqlLastOld,\n'
        f'{indent}    (unsigned int)s_phase6caKfLowerIrqlLastNew,\n'
        f'{indent}    (unsigned int)s_phase6caKfLowerIrqlLastRawEcx,\n'
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

    base = load(args.base_emitter, "phase6ca_base")
    p6bl = load(args.phase6bl_emitter, "phase6ca_p6bl")
    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bz-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CA] cached Phase 6BZ input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6BZ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CA] cached Phase 6BZ identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6CA] inherited membership accounting mismatch")

    queue = manifest.get("phase6bz_idex357_devicequeue", {}).get("device_queue_model", {})
    if (queue.get("object_base") != "0x0087E0A0" or
        queue.get("device_list_head_va") != "0x0087E0C8" or
        queue.get("empty_circular_list") is not True):
        raise SystemExit("[Phase6CA] inherited 6BZ DeviceQueue identity mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x80000081u",
        "static uint32_t s_phase6bwGuestIrql = 0u;",
        "PASS: Phase 6BZ KeRaiseIrqlToDpcLevel guest continuation",
        "P6BZ KERAISEIRQL129:",
        "P6BZ IDEX QUEUE HEAD:",
        "PHASE4C_BUDGET_TICK(0x0022ACE1u)",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CA] inherited 6BZ marker missing: {marker}")

    main_text = install_support(main_text)
    main_text = patch_icall_dispatch(main_text)
    main_text = insert_arm_trace(main_text)
    main_text = insert_summary(main_text)
    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6CA ordinal-161 KfLowerIrql FASTCALL guest-only IRQL continuation using CL; 6BZ validated direct IdexChannelObject/KDEVICE_QUEUE; preserve low-KSEG fence, FILE_OBJECT sentinel, file/delay/GPU semantics, allocator geometry and 8M budget",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (main_text.replace("PHASE 6BZ", "PHASE 6CA")
        .replace("Phase 6BZ", "Phase 6CA")
        .replace('"P6BZ ', '"P6CA '))
    env_text = (env_text.replace("PHASE 6BZ", "PHASE 6CA")
        .replace("Phase 6BZ", "Phase 6CA"))

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x800000A1u",
        "phase6ca_kf_lower_irql",
        "KfLowerIrql LIVE FRAME:",
        "PASS: Phase 6CA KfLowerIrql guest continuation",
        "P6CA KFLOWERIRQL161:",
        "P6CA KERAISEIRQL129:",
        "P6CA IDEX QUEUE HEAD:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CA] generated source lost marker: {marker}")

    expected_env = (env_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6BZ", "PHASE 6CA")
        .replace("Phase 6BZ", "Phase 6CA"))
    if env_text != expected_env:
        raise SystemExit("[Phase6CA] phase5_env.cpp changed beyond tag/cookie renames")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6CA", "build_tag": BUILD_TAG,
                     "pack_members": pack_count, "members": members})
    manifest["phase6ca_kf_lower_irql"] = {
        "source_phase": "6BZ",
        "phase6bz_hardware": {
            "guest_irql_before_boundary": 2,
            "last_local_va": "0x0022ACE1",
            "next_boundary_target": "0x800000A1",
            "next_boundary_ordinal": 161,
            "next_boundary_name": "KfLowerIrql",
            "boundary_esp": "0x008BF8F8",
            "boundary_saved_esp": "0x008BF8FC",
            "frame_bytes": 4,
            "boundary_raw_ecx": "0x0087E000",
            "boundary_cl": "0x00",
            "fault": 0,
            "xapi_return": 0,
        },
        "continuation": {
            "calling_convention": "FASTCALL",
            "argument_source": "CL",
            "argument_mask": "0xFF",
            "expected_first_old_irql": 2,
            "expected_first_new_irql": 0,
            "void_return_preserves_guest_eax": True,
            "changes_native_xenon_irql": False,
            "rejects_raise_through_lower_api": True,
        },
        "translated_membership_changed": False,
        "low_kseg_fence_changed": False,
        "file_object_sentinel_preserved": True,
        "phase5_env_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }
    (args.out_dir / "phase6ca-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8")

    print("[Phase6CA] 6BZ hardware: direct IdexChannelObject/KDEVICE_QUEUE PASS")
    print("[Phase6CA] next boundary: 800000A1 = ordinal 161 KfLowerIrql FASTCALL")
    print("[Phase6CA] ECX=0087E000 -> CL=00; expected guest IRQL 2 -> 0")
    print("[Phase6CA] real Xenon/XDK processor IRQL remains unchanged")
    print("[Phase6CA] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
