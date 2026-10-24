#!/usr/bin/env python3
"""Phase 6BV: ObReferenceObjectByHandle FILE_OBJECT first-dereference probe.

6BU hardware proved a canonical ordinal-246 frame:
  handle=0x48000001 (live game:\\xesrb.tga tagged native handle)
  object_type=0x80000047 (Xbox kernel ordinal 71 IoFileObjectType DATA)
  returned_object_ptr=0x008BF928
  returned_before=0x48000001
  fault=0

Do not guess the complete Xbox FILE_OBJECT layout yet. For the exact proven
IoFileObjectType + resolved tagged-file-handle class, return STATUS_SUCCESS and
write the deliberately unmapped guest sentinel 0x04000000 (exactly one byte
past the 64 MiB guest arena) to ReturnedObject*. The first retail dereference
should therefore expose FILE_OBJECT+offset through the existing checked guest
access boundary. This is diagnostic only and is not a final object model.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BU-OBREF246-PROBE-20261024-A"
BUILD_TAG = "P6BV-FILEOBJECT-FIRST-DEREF-20261024-A"
COOKIE_OLD = "phase6bu_env_build_cookie"
COOKIE_NEW = "phase6bv_env_build_cookie"

SENTINEL = 0x04000000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BV] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BV] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_probe_function(text: str) -> str:
    start_marker = "static void phase6bu_ob_reference_object_by_handle_probe(uint32_t savedEsp)\n{"
    end_marker = "\n\nstatic recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    start = text.find(start_marker)
    end = text.find(end_marker, start)
    if start < 0 or end < 0:
        raise SystemExit("[Phase6BV] could not isolate inherited 6BU ObReferenceObjectByHandle probe")

    replacement = r'''static uint32_t s_phase6bvObRefContinuationCount = 0u;
static uint32_t s_phase6bvObRefLastHandle = 0u;
static uint32_t s_phase6bvObRefLastObjectType = 0u;
static uint32_t s_phase6bvObRefLastReturnedObjectVa = 0u;
static uint32_t s_phase6bvObRefLastSentinel = 0u;

#define PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u

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

    sprintf(
        line,
        "ObReferenceObjectByHandle LIVE FRAME: ret=%08X handle=%08X native_resolved=%u path=%s object_type=%08X returned_object_ptr=%08X returned_before=%08X esp=%08X saved_esp=%08X",
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

    /*
     * 6BU hardware proved object_type=0x80000047, which is Xbox kernel export
     * ordinal 71 IoFileObjectType, and proved the handle resolves through the
     * maintained native tagged-file table. Keep this diagnostic continuation
     * restricted to that exact object class.
     */
    if (returnSlot != 0u ||
        nativeHandle == NULL ||
        returnedObjectPtr == NULL ||
        objectType != 0x80000047u)
    {
        trace("ObReferenceObjectByHandle REJECTED: frame is outside the 6BU-proven IoFileObjectType/tagged-file-handle class");
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x800000F6u,
            savedEsp);
        return;
    }

    /*
     * 64 MiB guest arena spans 0x00000000..0x03FFFFFF. 0x04000000 is the
     * exact one-past-end address and is intentionally not mapped. Returning
     * it lets the first direct retail FILE_OBJECT dereference reveal the
     * required field offset through checked guest-memory access.
     */
    GUEST_WRITE32(returnedObjectVa, PHASE6BV_FILE_OBJECT_SENTINEL);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000F6u,
            savedEsp);
        return;
    }

    ++s_phase6bvObRefContinuationCount;
    s_phase6bvObRefLastHandle = handleToken;
    s_phase6bvObRefLastObjectType = objectType;
    s_phase6bvObRefLastReturnedObjectVa = returnedObjectVa;
    s_phase6bvObRefLastSentinel = PHASE6BV_FILE_OBJECT_SENTINEL;

    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6BV ObReferenceObjectByHandle diagnostic continuation handle=%08X path=%s object_type=%08X returned_ptr=%08X sentinel=%08X calls=%u new_esp=%08X",
        (unsigned int)handleToken,
        nativePath ? nativePath : "<unknown>",
        (unsigned int)objectType,
        (unsigned int)returnedObjectVa,
        (unsigned int)PHASE6BV_FILE_OBJECT_SENTINEL,
        (unsigned int)s_phase6bvObRefContinuationCount,
        (unsigned int)g_esp);
    trace(line);
}'''

    return text[:start] + replacement + text[end:]


def insert_summary(text: str) -> str:
    marker = "P6BU OBREF246 PROBE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BV] inherited 6BU ObRef summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BV] could not locate inherited 6BU summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BU OBREF246 SENTINEL: calls=%u handle=%08X object_type=%08X returned_ptr=%08X sentinel=%08X",\n'
        f'{indent}    (unsigned int)s_phase6bvObRefContinuationCount,\n'
        f'{indent}    (unsigned int)s_phase6bvObRefLastHandle,\n'
        f'{indent}    (unsigned int)s_phase6bvObRefLastObjectType,\n'
        f'{indent}    (unsigned int)s_phase6bvObRefLastReturnedObjectVa,\n'
        f'{indent}    (unsigned int)s_phase6bvObRefLastSentinel);\n'
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

    base = load(args.base_emitter, "phase6bv_base")
    p6bl = load(args.phase6bl_emitter, "phase6bv_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bu-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BV] cached Phase 6BU input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BU" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BV] cached Phase 6BU identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BV] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
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
            raise SystemExit(f"[Phase6BV] inherited 6BU marker missing: {marker}")

    main_text = replace_probe_function(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BV ordinal-246 IoFileObjectType diagnostic continuation; return unmapped 0x04000000 FILE_OBJECT sentinel to expose first retail field dereference; preserve all 6BU file/delay/GPU semantics and hard fences",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BU", "PHASE 6BV")
        .replace("Phase 6BU", "Phase 6BV")
        .replace('"P6BU ', '"P6BV ')
    )
    env_text = (
        env_text.replace("PHASE 6BU", "PHASE 6BV")
        .replace("Phase 6BU", "Phase 6BV")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "objectType != 0x80000047u",
        "PASS: Phase 6BV ObReferenceObjectByHandle diagnostic continuation",
        "P6BV OBREF246 SENTINEL:",
        "P6BV KEDELAY99:",
        "P6BV NTSETINFO226:",
        "P6BV PBL CHECKPOINT:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BV] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BV",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bv_fileobject_first_deref"] = {
        "source_phase": "6BU",
        "phase6bu_hardware": {
            "obref246_calls": 1,
            "handle": "0x48000001",
            "handle_resolved": True,
            "path": "game:\\xesrb.tga",
            "object_type": "0x80000047",
            "object_type_export_ordinal": 71,
            "object_type_export_name": "IoFileObjectType",
            "returned_object_ptr": "0x008BF928",
            "returned_before": "0x48000001",
            "frame_bytes": 16,
            "fault": 0,
        },
        "diagnostic_continuation": {
            "status": "STATUS_SUCCESS",
            "returned_guest_pointer": "0x04000000",
            "guest_arena_bytes": 67108864,
            "sentinel_is_exact_one_past_guest_arena": True,
            "purpose": "expose first direct retail FILE_OBJECT field dereference offset",
            "final_file_object_model": False,
        },
        "translated_membership_changed": False,
        "all_phase6bu_file_delay_gpu_invariants_inherited": True,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bv-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BV] 6BU hardware: canonical ObReferenceObjectByHandle frame captured")
    print("[Phase6BV] object type: 80000047 = ordinal 71 IoFileObjectType")
    print("[Phase6BV] handle: 48000001 resolved path=game:\\xesrb.tga")
    print("[Phase6BV] diagnostic continuation: STATUS_SUCCESS + returned object sentinel 04000000")
    print("[Phase6BV] sentinel is exact one-past-end of 64 MiB guest arena")
    print("[Phase6BV] goal: first retail FILE_OBJECT dereference reveals exact required field offset")
    print("[Phase6BV] translated membership unchanged")
    print("[Phase6BV] all 6BU file/delay/GPU/allocator/8M-budget invariants inherited unchanged")
    print("[Phase6BV] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
