#!/usr/bin/env python3
"""Phase 6BU: probe ordinal-246 ObReferenceObjectByHandle live frame.

6BT hardware proved the ordinal-99 KeDelayExecutionThread continuation with a
canonical 16-byte frame and a 200 ms relative wait. Execution then stopped at
fault-free ICALL_SAFE target 0x800000F6, ordinal 246 ObReferenceObjectByHandle.

Do not invent an Xbox object pointer. This stage only validates/logs the live
three-argument frame (Handle, ObjectType, ReturnedObject*) and classifies the
handle through the existing tagged native-handle table. It then preserves the
ICALL_SAFE boundary so the following continuation can be based on hardware
facts instead of guessed FILE_OBJECT layout.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BT-KEDELAY99-RELATIVE-20261024-A"
BUILD_TAG = "P6BU-OBREF246-PROBE-20261024-A"
COOKIE_OLD = "phase6bt_env_build_cookie"
COOKIE_NEW = "phase6bu_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BU] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BU] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6BU] RECOMP_ICALL_SAFE macro start missing")

    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6BU] RECOMP_ITAIL anchor missing after RECOMP_ICALL_SAFE")

    macro = text[macro_start:next_macro]
    if "_phase4c_target == 0x800000F6u" in macro:
        raise SystemExit("[Phase6BU] ordinal 246 is already dispatched")

    bs = chr(92)
    inherited = "if (_phase4c_target == 0x80000063u) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6BU] inherited 6BT ordinal-99 dispatch head missing")

    replacement = (
        "if (_phase4c_target == 0x800000F6u) { " + bs + "\n"
        "        phase6bu_ob_reference_object_by_handle_probe((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x80000063u) { " + bs
    )
    patched = macro[:pos] + replacement + macro[pos + len(inherited):]
    if patched.count("_phase4c_target == 0x800000F6u") != 1:
        raise SystemExit("[Phase6BU] ordinal-246 dispatch insertion did not produce exactly one branch")

    return text[:macro_start] + patched + text[next_macro:]


def install_probe_support(text: str) -> str:
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6BU] expected one translated-pack lookup definition anchor, found {text.count(anchor)}"
        )

    support = r'''static uint32_t s_phase6buObRefProbeCount = 0u;
static uint32_t s_phase6buObRefLastHandle = 0u;
static uint32_t s_phase6buObRefLastObjectType = 0u;
static uint32_t s_phase6buObRefLastReturnedObjectVa = 0u;
static uint32_t s_phase6buObRefLastReturnedObjectBefore = 0u;
static uint32_t s_phase6buObRefLastHandleResolved = 0u;

static void phase6bu_ob_reference_object_by_handle_probe(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t objectType;
    uint32_t returnedObjectVa;
    uint32_t returnedObjectBefore = 0u;
    HANDLE nativeHandle;
    BYTE* returnedObjectPtr;
    const char* nativePath;
    char line[768];

    if (savedEsp != callEsp + 16u)
    {
        sprintf(
            line,
            "ObReferenceObjectByHandle FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=16",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000F6u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    objectType = GUEST_READ32(callEsp + 8u);
    returnedObjectVa = GUEST_READ32(callEsp + 12u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000F6u,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    nativePath = phase5b_read_handle_path(handleToken);
    returnedObjectPtr =
        returnedObjectVa ? guest_ptr((DWORD)returnedObjectVa, 4u) : NULL;

    if (returnedObjectPtr != NULL)
    {
        returnedObjectBefore = GUEST_READ32(returnedObjectVa);
        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000F6u,
                savedEsp);
            return;
        }
    }

    ++s_phase6buObRefProbeCount;
    s_phase6buObRefLastHandle = handleToken;
    s_phase6buObRefLastObjectType = objectType;
    s_phase6buObRefLastReturnedObjectVa = returnedObjectVa;
    s_phase6buObRefLastReturnedObjectBefore = returnedObjectBefore;
    s_phase6buObRefLastHandleResolved = nativeHandle ? 1u : 0u;

    sprintf(
        line,
        "ObReferenceObjectByHandle LIVE PROBE: ret=%08X handle=%08X native_resolved=%u path=%s object_type=%08X returned_object_ptr=%08X returned_before=%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        nativeHandle ? 1u : 0u,
        nativePath ? nativePath : "<unknown>",
        (unsigned int)objectType,
        (unsigned int)returnedObjectVa,
        (unsigned int)returnedObjectBefore,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || returnedObjectPtr == NULL)
    {
        trace("ObReferenceObjectByHandle PROBE REJECTED: nonzero return slot or invalid ReturnedObject pointer");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000F6u,
            savedEsp);
        return;
    }

    trace("PASS: Phase 6BU captured canonical ordinal-246 live frame; no object pointer synthesized");
    phase4c_escape(
        PHASE4C_BOUNDARY_ICALL_SAFE,
        0x800000F6u,
        savedEsp);
}

'''
    return text.replace(anchor, support + anchor, 1)


def insert_arm_trace(text: str) -> str:
    marker = '    trace("PASS: Phase 6BT ordinal 99 KeDelayExecutionThread relative-delay continuation armed");\n'
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6BU] expected one inherited ordinal-99 arm trace, found {text.count(marker)}"
        )
    return text.replace(
        marker,
        marker
        + '    trace("PASS: Phase 6BT ordinal 246 ObReferenceObjectByHandle live-frame probe armed");\n',
        1,
    )


def insert_summary(text: str) -> str:
    marker = "P6BT KEDELAY99:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BU] inherited 6BT delay summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BU] could not locate inherited 6BT summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BT OBREF246 PROBE: calls=%u handle=%08X resolved=%u object_type=%08X returned_ptr=%08X returned_before=%08X",\n'
        f'{indent}    (unsigned int)s_phase6buObRefProbeCount,\n'
        f'{indent}    (unsigned int)s_phase6buObRefLastHandle,\n'
        f'{indent}    (unsigned int)s_phase6buObRefLastHandleResolved,\n'
        f'{indent}    (unsigned int)s_phase6buObRefLastObjectType,\n'
        f'{indent}    (unsigned int)s_phase6buObRefLastReturnedObjectVa,\n'
        f'{indent}    (unsigned int)s_phase6buObRefLastReturnedObjectBefore);\n'
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

    base = load(args.base_emitter, "phase6bu_base")
    p6bl = load(args.phase6bl_emitter, "phase6bu_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bt-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BU] cached Phase 6BT input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BT" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BU] cached Phase 6BT identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BU] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x80000063u",
        "phase6bt_ke_delay_execution_thread((uint32_t)(saved_esp))",
        "PASS: Phase 6BT KeDelayExecutionThread relative continuation",
        "P6BT KEDELAY99:",
        "P6BT NTSETINFO226:",
        "P6BT POST-PBL FRONTIER 00209A70:",
        "P6BT PBL CHECKPOINT:",
        "static HANDLE phase5c_read_native_handle(uint32_t token)",
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BU] inherited 6BT marker missing: {marker}")

    if "_phase4c_target == 0x800000F6u" in main_text or "phase6bu_ob_reference_object_by_handle_probe" in main_text:
        raise SystemExit("[Phase6BU] ordinal-246 probe already appears in inherited source")

    main_text = install_probe_support(main_text)
    main_text = patch_icall_dispatch(main_text)
    main_text = insert_arm_trace(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BU ordinal-246 ObReferenceObjectByHandle canonical 16-byte live-frame probe only; synthesize no object pointer; preserve 6BT delay/file/GPU semantics and hard fences",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BT", "PHASE 6BU")
        .replace("Phase 6BT", "Phase 6BU")
        .replace('"P6BT ', '"P6BU ')
    )
    env_text = (
        env_text.replace("PHASE 6BT", "PHASE 6BU")
        .replace("Phase 6BT", "Phase 6BU")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x800000F6u",
        "ObReferenceObjectByHandle LIVE PROBE:",
        "PASS: Phase 6BU captured canonical ordinal-246 live frame; no object pointer synthesized",
        "P6BU OBREF246 PROBE:",
        "P6BU KEDELAY99:",
        "P6BU NTSETINFO226:",
        "P6BU PBL CHECKPOINT:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BU] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BU",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bu_obref246_probe"] = {
        "source_phase": "6BT",
        "phase6bt_hardware": {
            "kedelay99_calls": 1,
            "kedelay99_successes": 1,
            "wait_mode": 1,
            "alertable": 0,
            "interval": "0xFFFFFFFFFFE17B80",
            "milliseconds": 200,
            "boundary_kind": "ICALL_SAFE",
            "kernel_target": "0x800000F6",
            "kernel_ordinal": 246,
            "kernel_name": "ObReferenceObjectByHandle",
            "caller": "0x0023A3CE",
            "call_esp": "0x008BF8EC",
            "saved_esp": "0x008BF8FC",
            "observed_frame_bytes": 16,
            "canonical_frame_bytes": 16,
            "fault": 0,
            "ticks": 954273,
        },
        "probe_only": True,
        "synthesizes_object_pointer": False,
        "translated_membership_changed": False,
        "all_phase6bt_file_delay_gpu_invariants_inherited": True,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bu-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BU] 6BT hardware: KeDelayExecutionThread 200ms relative continuation PASS")
    print("[Phase6BU] next boundary: ICALL_SAFE 800000F6 ordinal 246 ObReferenceObjectByHandle fault=0")
    print("[Phase6BU] observed frame: 16 bytes, exactly canonical return + three arguments")
    print("[Phase6BU] probe only: log Handle/ObjectType/ReturnedObject*; synthesize no object pointer")
    print("[Phase6BU] translated membership unchanged")
    print("[Phase6BU] all 6BT file/delay/GPU/allocator/8M-budget invariants inherited unchanged")
    print("[Phase6BU] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
