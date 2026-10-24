#!/usr/bin/env python3
"""Phase 6BS: native ordinal-226 NtSetInformationFile position continuation.

6BR hardware proved exact translated root 0x00209A70, then advanced into the
0x00229Fxx title path and stopped at a fault-free ICALL_SAFE to kernel token
0x800000E2 (ordinal 226, NtSetInformationFile). The observed frame is already
canonical: savedEsp-callEsp == 24 bytes, matching return slot + five arguments.

The maintained Xbox implementation supports several information classes. This
phase deliberately implements only XboxFilePositionInformation (class 14,
8-byte CurrentByteOffset), using the already-proven Xenon tagged-handle table
and phase5h_seek_absolute helper. Every other information class remains fenced.
No translated membership, ABI repair, GPU/MMIO/VRAM policy, allocator geometry
or execution budget is changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BR-POST-PBL-FRONTIER-00209A70-20261024-A"
BUILD_TAG = "P6BS-NTSETINFO226-POSITION-20261024-A"
COOKIE_OLD = "phase6br_env_build_cookie"
COOKIE_NEW = "phase6bs_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BS] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BS] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6BS] RECOMP_ICALL_SAFE macro start missing")

    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6BS] RECOMP_ITAIL anchor missing after RECOMP_ICALL_SAFE")

    macro = text[macro_start:next_macro]
    if "PHASE4C_BOUNDARY_ICALL_SAFE" not in macro or "_phase4c_target" not in macro:
        raise SystemExit("[Phase6BS] RECOMP_ICALL_SAFE macro shape is not the expected kernel-dispatch form")

    if "_phase4c_target == 0x800000E2u" in macro:
        raise SystemExit("[Phase6BS] ordinal 226 is already dispatched by RECOMP_ICALL_SAFE")

    # Later phases accumulated many maintained kernel continuations here.
    # Avoid matching the entire historical macro body. Insert immediately
    # before the final fallback else that escapes unknown ICALL_SAFE targets.
    fallback = "} else { \\\"
    fallback_pos = macro.rfind(fallback)
    if fallback_pos < 0:
        raise SystemExit("[Phase6BS] final RECOMP_ICALL_SAFE fallback else not found")

    fallback_tail = macro[fallback_pos:]
    if "PHASE4C_BOUNDARY_ICALL_SAFE" not in fallback_tail:
        raise SystemExit("[Phase6BS] final RECOMP_ICALL_SAFE else is not the ICALL_SAFE escape")

    branch = (
        "} else if (_phase4c_target == 0x800000E2u) { \\\n"
        "        phase6bs_nt_set_information_file((uint32_t)(saved_esp)); \\\n"
        "    "
    )
    patched_macro = macro[:fallback_pos] + branch + macro[fallback_pos:]
    if patched_macro.count("_phase4c_target == 0x800000E2u") != 1:
        raise SystemExit("[Phase6BS] ordinal-226 dispatch insertion did not produce exactly one branch")

    return text[:macro_start] + patched_macro + text[next_macro:]

def install_ntsetinfo_support(text: str) -> str:
    # Insert immediately before the translated-pack lookup definition. This
    # point is deliberately late in the support section: the tagged-handle,
    # path, status-mapping and absolute-seek helpers are already defined, while
    # all translated bodies that expand RECOMP_ICALL_SAFE come afterwards.
    # Do not anchor this stage to a phase-specific NtQueryInformationFile
    # helper name; that helper has been renamed/re-emitted by later phases.
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6BS] expected one translated-pack lookup definition anchor, found {text.count(anchor)}"
        )

    support = r'''static uint32_t s_phase6bsNtSetInformationFileCallCount = 0u;
static uint32_t s_phase6bsNtSetInformationFileSuccessCount = 0u;
static uint32_t s_phase6bsNtSetInformationFileLastClass = 0u;
static uint32_t s_phase6bsNtSetInformationFileLastPositionLow = 0u;
static uint32_t s_phase6bsNtSetInformationFileLastPositionHigh = 0u;

static void phase6bs_nt_set_information_file(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t handleToken;
    uint32_t ioStatusVa;
    uint32_t infoVa;
    uint32_t length;
    uint32_t infoClass;
    uint32_t positionLow = 0u;
    uint32_t positionHigh = 0u;
    uint32_t status = 0u;
    DWORD error = ERROR_SUCCESS;
    HANDLE nativeHandle;
    BYTE* ioStatusPtr;
    BYTE* infoPtr;
    const char* nativePath;
    char line[768];

    if (savedEsp != callEsp + 24u)
    {
        sprintf(
            line,
            "NtSetInformationFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000E2u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    handleToken = GUEST_READ32(callEsp + 4u);
    ioStatusVa = GUEST_READ32(callEsp + 8u);
    infoVa = GUEST_READ32(callEsp + 12u);
    length = GUEST_READ32(callEsp + 16u);
    infoClass = GUEST_READ32(callEsp + 20u);

    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000E2u,
            savedEsp);
        return;
    }

    nativeHandle = phase5c_read_native_handle(handleToken);
    nativePath = phase5b_read_handle_path(handleToken);
    ioStatusPtr = ioStatusVa ? guest_ptr((DWORD)ioStatusVa, 8u) : NULL;
    infoPtr = infoVa ? guest_ptr((DWORD)infoVa, length ? (DWORD)length : 1u) : NULL;

    sprintf(
        line,
        "NtSetInformationFile LIVE FRAME: ret=%08X handle=%08X iosb=%08X info=%08X len=%u class=%u path=%s esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)handleToken,
        (unsigned int)ioStatusVa,
        (unsigned int)infoVa,
        (unsigned int)length,
        (unsigned int)infoClass,
        nativePath ? nativePath : "<unknown>",
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u ||
        nativeHandle == NULL ||
        ioStatusPtr == NULL ||
        infoPtr == NULL)
    {
        trace("NtSetInformationFile REJECTED: invalid return slot, tagged handle, IOSB or information buffer");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000E2u,
            savedEsp);
        return;
    }

    /*
     * XboxFilePositionInformation == 14 and contains one LARGE_INTEGER
     * CurrentByteOffset. This matches the maintained xbox_NtSetInformationFile
     * implementation and is the only class enabled in this hardware stage.
     */
    if (infoClass != 14u || length != 8u)
    {
        sprintf(
            line,
            "NtSetInformationFile UNSUPPORTED: class=%u len=%u (6BS permits only FilePositionInformation class=14 len=8)",
            (unsigned int)infoClass,
            (unsigned int)length);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_FILE_INFORMATION,
            0x800000E2u,
            savedEsp);
        return;
    }

    positionLow = GUEST_READ32(infoVa + 0u);
    positionHigh = GUEST_READ32(infoVa + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000E2u,
            savedEsp);
        return;
    }

    if ((positionHigh & 0x80000000u) != 0u)
    {
        sprintf(
            line,
            "NtSetInformationFile UNSUPPORTED: negative file position %08X%08X",
            (unsigned int)positionHigh,
            (unsigned int)positionLow);
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_FILE_INFORMATION,
            0x800000E2u,
            savedEsp);
        return;
    }

    SetLastError(ERROR_SUCCESS);
    if (!phase5h_seek_absolute(nativeHandle, positionLow, positionHigh))
    {
        error = GetLastError();
        status = phase5b_open_status_from_error(error);
    }

    GUEST_WRITE32(ioStatusVa + 0u, status);
    GUEST_WRITE32(ioStatusVa + 4u, 0u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000E2u,
            savedEsp);
        return;
    }

    ++s_phase6bsNtSetInformationFileCallCount;
    if (status == 0u)
        ++s_phase6bsNtSetInformationFileSuccessCount;
    s_phase6bsNtSetInformationFileLastClass = infoClass;
    s_phase6bsNtSetInformationFileLastPositionLow = positionLow;
    s_phase6bsNtSetInformationFileLastPositionHigh = positionHigh;

    g_eax = status;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6BS NtSetInformationFile position continuation handle=%08X path=%s position=%08X%08X status=%08X error=%u calls=%u successes=%u new_esp=%08X",
        (unsigned int)handleToken,
        nativePath ? nativePath : "<unknown>",
        (unsigned int)positionHigh,
        (unsigned int)positionLow,
        (unsigned int)status,
        (unsigned int)error,
        (unsigned int)s_phase6bsNtSetInformationFileCallCount,
        (unsigned int)s_phase6bsNtSetInformationFileSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

'''
    return text.replace(anchor, support + anchor, 1)


def insert_arm_trace(text: str) -> str:
    marker = '    trace("PASS: Phase 6BR ordinal 218 NtQueryVolumeInformationFile native continuation armed");\n'
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6BS] expected one ordinal-218 arm trace, found {text.count(marker)}"
        )
    addition = (
        marker
        + '    trace("PASS: Phase 6BR ordinal 226 NtSetInformationFile class-14 position continuation armed");\n'
    )
    return text.replace(marker, addition, 1)


def insert_summary(text: str) -> str:
    marker = "P6BR POST-PBL FRONTIER 00209A70:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BS] inherited 6BR summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BS] could not locate inherited 6BR summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BR NTSETINFO226: calls=%u successes=%u class=%u position=%08X%08X",\n'
        f'{indent}    (unsigned int)s_phase6bsNtSetInformationFileCallCount,\n'
        f'{indent}    (unsigned int)s_phase6bsNtSetInformationFileSuccessCount,\n'
        f'{indent}    (unsigned int)s_phase6bsNtSetInformationFileLastClass,\n'
        f'{indent}    (unsigned int)s_phase6bsNtSetInformationFileLastPositionHigh,\n'
        f'{indent}    (unsigned int)s_phase6bsNtSetInformationFileLastPositionLow);\n'
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

    base = load(args.base_emitter, "phase6bs_base")
    p6bl = load(args.phase6bl_emitter, "phase6bs_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6br-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BS] cached Phase 6BR input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BR" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BS] cached Phase 6BR identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BS] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6BR POST-PBL FRONTIER 00209A70:",
        "P6BR PBL CHECKPOINT:",
        "static HANDLE phase5c_read_native_handle(uint32_t token)",
        "static int phase5h_seek_absolute(HANDLE handle, uint32_t lowPart, uint32_t highPart)",
        "static uint32_t phase5b_open_status_from_error(DWORD error)",
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BS] inherited 6BR marker missing: {marker}")

    if "_phase4c_target == 0x800000E2u" in main_text or "phase6bs_nt_set_information_file" in main_text:
        raise SystemExit(
            "[Phase6BS] ordinal 226 dispatch/support already appears in inherited source; inspect before adding duplicate handling"
        )

    main_text = install_ntsetinfo_support(main_text)
    main_text = patch_icall_dispatch(main_text)
    main_text = insert_arm_trace(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BS ordinal-226 NtSetInformationFile canonical 24-byte frame; class-14/8-byte absolute position only; preserve both 6BQ ABI repairs and all 6BR GPU semantics/hard fences",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BR", "PHASE 6BS")
        .replace("Phase 6BR", "Phase 6BS")
        .replace('"P6BR ', '"P6BS ')
    )
    env_text = (
        env_text.replace("PHASE 6BR", "PHASE 6BS")
        .replace("Phase 6BR", "Phase 6BS")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x800000E2u",
        "phase6bs_nt_set_information_file((uint32_t)(saved_esp))",
        "NtSetInformationFile LIVE FRAME:",
        "infoClass != 14u || length != 8u",
        "phase5h_seek_absolute(nativeHandle, positionLow, positionHigh)",
        "PASS: Phase 6BS NtSetInformationFile position continuation",
        "P6BS NTSETINFO226:",
        "PASS: Phase 6BS ordinal 226 NtSetInformationFile class-14 position continuation armed",
        "P6BS POST-PBL FRONTIER 00209A70:",
        "P6BS PBL CHECKPOINT:",
        "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
        "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BS] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BS",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bs_ntsetinfo226_position"] = {
        "source_phase": "6BR",
        "phase6br_hardware": {
            "post_pbl_root_00209a70_entries": 1,
            "pbl_checkpoint_calls": 3,
            "pbl_checkpoint_phase1": 1,
            "pbl_checkpoint_phase2": 1,
            "pbl_checkpoint_last_value": "0x48000001",
            "boundary_kind": "ICALL_SAFE",
            "kernel_target": "0x800000E2",
            "kernel_ordinal": 226,
            "kernel_name": "NtSetInformationFile",
            "caller": "0x0023A3CE",
            "call_esp": "0x008BF878",
            "saved_esp": "0x008BF890",
            "observed_frame_bytes": 24,
            "canonical_frame_bytes": 24,
            "fault": 0,
            "ticks": 689257,
        },
        "continuation": {
            "accepted_information_class": 14,
            "accepted_information_name": "XboxFilePositionInformation",
            "accepted_length": 8,
            "position_semantics": "absolute FILE_BEGIN through phase5h_seek_absolute",
            "requires_zero_return_slot": True,
            "requires_live_tagged_handle": True,
            "requires_guest_iosb_8_bytes": True,
            "requires_guest_info_8_bytes": True,
            "negative_positions_fenced": True,
            "all_other_information_classes_fenced": True,
        },
        "translated_membership_changed": False,
        "all_phase6bq_abi_repairs_inherited": True,
        "all_phase6br_gpu_bridges_inherited": True,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bs-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BS] 6BR hardware: translated root 00209A70 entered")
    print("[Phase6BS] next boundary: ICALL_SAFE 800000E2 ordinal 226 NtSetInformationFile fault=0")
    print("[Phase6BS] observed frame: 24 bytes, exactly canonical return + five arguments")
    print("[Phase6BS] continuation: class 14 FilePositionInformation, len=8, absolute seek only")
    print("[Phase6BS] all other NtSetInformationFile classes remain fenced")
    print("[Phase6BS] translated membership unchanged")
    print("[Phase6BS] both ABI repairs, GPU semantics, allocator geometry and 8M budget inherited unchanged")
    print("[Phase6BS] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
