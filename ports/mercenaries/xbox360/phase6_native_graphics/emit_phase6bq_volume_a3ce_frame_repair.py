#!/usr/bin/env python3
"""Phase 6BQ: caller-local NtQueryVolumeInformationFile 28->24 frame repair.

6BP hardware proved the RtlInitAnsiString A3CE repair and advanced sub_00209810
far enough to open d:\\xesrb.tga, open d:\\, and reach PBL checkpoint phase 1.
The next boundary is ordinal 218 NtQueryVolumeInformationFile with caller
0x0023A3CE, callEsp=0x008BF8C4, savedEsp=0x008BF8E0, delta=28 vs canonical
24, fault=0.

This phase preserves all translated membership and graphics semantics. It
repairs only the exact 28-byte caller-0023A3CE frame after validating the
canonical ordinal-218 arguments and guest pointer/handle shapes, then resumes
at savedEsp-4.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

BASE_TAG="P6BP-RTLANSI-A3CE-REPAIR-20261024-A"
BUILD_TAG="P6BQ-VOLUME-A3CE-FRAME-REPAIR-20261024-A"
COOKIE_OLD="phase6bp_env_build_cookie"
COOKIE_NEW="phase6bq_env_build_cookie"

def load(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BQ] could not load {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def replace_unique(text,old,new,label):
    n=text.count(old)
    if n!=1: raise SystemExit(f"[Phase6BQ] expected one {label}, found {n}")
    return text.replace(old,new,1)

def patch_volume_frame(text):
    old=r'''    if (savedEsp != callEsp + 24u)
    {
        sprintf(
            line,
            "NtQueryVolumeInformationFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DAu,
            savedEsp);
        return;
    }
'''
    new=r'''    if (savedEsp == callEsp + 28u &&
        phase4c_current_caller() == 0x0023A3CEu)
    {
        uint32_t probeReturn = GUEST_READ32(callEsp + 0u);
        uint32_t probeHandle = GUEST_READ32(callEsp + 4u);
        uint32_t probeIoStatus = GUEST_READ32(callEsp + 8u);
        uint32_t probeInfo = GUEST_READ32(callEsp + 12u);
        uint32_t probeLength = GUEST_READ32(callEsp + 16u);
        uint32_t probeClass = GUEST_READ32(callEsp + 20u);
        uint32_t probeExtra = GUEST_READ32(callEsp + 24u);
        HANDLE probeNativeHandle = phase5c_read_native_handle(probeHandle);
        BYTE* probeIoStatusPtr =
            probeIoStatus ? guest_ptr((DWORD)probeIoStatus, 8u) : NULL;
        BYTE* probeInfoPtr =
            probeInfo ? guest_ptr((DWORD)probeInfo, 24u) : NULL;

        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x800000DAu,
                savedEsp);
            return;
        }

        sprintf(
            line,
            "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE: caller=%08X ret=%08X handle=%08X iosb=%08X info=%08X len=%u class=%u extra=%08X esp=%08X saved_esp=%08X",
            (unsigned int)phase4c_current_caller(),
            (unsigned int)probeReturn,
            (unsigned int)probeHandle,
            (unsigned int)probeIoStatus,
            (unsigned int)probeInfo,
            (unsigned int)probeLength,
            (unsigned int)probeClass,
            (unsigned int)probeExtra,
            (unsigned int)callEsp,
            (unsigned int)savedEsp);
        trace(line);

        if (probeReturn != 0u ||
            probeNativeHandle == NULL ||
            probeIoStatusPtr == NULL ||
            probeInfoPtr == NULL ||
            probeLength < 24u ||
            probeClass != 3u)
        {
            trace("NtQueryVolumeInformationFile SAVEDESP REPAIR REJECTED: caller 0023A3CE did not match canonical ordinal-218 size-information arguments");
            phase4c_escape(
                PHASE4C_BOUNDARY_KERNEL_FRAME,
                0x800000DAu,
                savedEsp);
            return;
        }

        savedEsp -= 4u;
        sprintf(
            line,
            "PASS: Phase 6BQ NtQueryVolumeInformationFile caller 0023A3CE saved-ESP repair extra=%08X restores 24-byte ordinal-218 frame new_saved_esp=%08X",
            (unsigned int)probeExtra,
            (unsigned int)savedEsp);
        trace(line);
    }

    if (savedEsp != callEsp + 24u)
    {
        sprintf(
            line,
            "NtQueryVolumeInformationFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=24",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000DAu,
            savedEsp);
        return;
    }
'''
    if text.count(old)!=1:
        raise SystemExit(f"[Phase6BQ] expected one ordinal-218 frame gate, found {text.count(old)}")
    return text.replace(old,new,1)

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-dir",type=Path,required=True)
    ap.add_argument("--base-emitter",type=Path,required=True)
    ap.add_argument("--phase6bl-emitter",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    a=ap.parse_args()

    base=load(a.base_emitter,"phase6bq_base")
    p6bl=load(a.phase6bl_emitter,"phase6bq_p6bl")

    main_path=a.base_dir/"main_monolithic.cpp"
    env_path=a.base_dir/"phase5_env.cpp"
    manifest_path=a.base_dir/"phase6bp-manifest.json"
    for p in (main_path,env_path,manifest_path):
        if not p.exists(): raise SystemExit(f"[Phase6BQ] cached 6BP input missing: {p}")

    main_text=main_path.read_text(encoding="utf-8")
    env_text=env_path.read_text(encoding="utf-8")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase")!="6BP" or manifest.get("build_tag")!=BASE_TAG:
        raise SystemExit("[Phase6BQ] cached 6BP identity mismatch")

    members=list(manifest.get("members",[]))
    pack_count=int(manifest.get("pack_members",0))
    if not members or pack_count!=len(members):
        raise SystemExit("[Phase6BQ] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,COOKIE_OLD,
        "P6BP POST-XGRPH FRONTIER 00209810:",
        "P6BP PBL CHECKPOINT:",
        "static void phase5c_query_volume_information(uint32_t savedEsp)",
        "NtQueryVolumeInformationFile FRAME MISMATCH:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u"
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BQ] inherited 6BP marker missing: {marker}")

    main_text=patch_volume_frame(main_text)
    main_text=p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BQ caller-0023A3CE ordinal-218 saved-ESP repair; canonical size-information argument validation required; preserve all 6BP GPU semantics and hard fences")
    main_text=replace_unique(main_text,BASE_TAG,BUILD_TAG,"build tag")
    main_text=main_text.replace(COOKIE_OLD,COOKIE_NEW)
    env_text=env_text.replace(COOKIE_OLD,COOKIE_NEW)
    main_text=(main_text.replace("PHASE 6BP","PHASE 6BQ")
                         .replace("Phase 6BP","Phase 6BQ")
                         .replace('"P6BP ','"P6BQ '))
    env_text=(env_text.replace("PHASE 6BP","PHASE 6BQ")
                     .replace("Phase 6BP","Phase 6BQ"))

    for marker in (
        BUILD_TAG,COOKIE_NEW,
        "phase4c_current_caller() == 0x0023A3CEu",
        "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
        "PASS: Phase 6BQ NtQueryVolumeInformationFile caller 0023A3CE saved-ESP repair",
        "probeLength < 24u",
        "probeClass != 3u",
        "savedEsp -= 4u;",
        "P6BQ POST-XGRPH FRONTIER 00209810:",
        "P6BQ PBL CHECKPOINT:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u"
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BQ] generated source lost marker: {marker}")

    a.out_dir.mkdir(parents=True,exist_ok=True)
    layout=p6bl.write_sharded_main(a.out_dir,main_text,base)
    (a.out_dir/"phase5_env.cpp").write_text(env_text,encoding="utf-8")

    manifest.update({"phase":"6BQ","build_tag":BUILD_TAG,"pack_members":pack_count,"members":members})
    manifest["phase6bq_volume_a3ce_frame_repair"]={
        "source_phase":"6BP",
        "phase6bp_hardware":{
            "post_xgrph_root_00209810_entries":1,
            "pbl_checkpoint_calls":1,
            "pbl_checkpoint_phase1":1,
            "pbl_checkpoint_phase2":0,
            "boundary_kind":"KERNEL_FRAME",
            "kernel_target":"0x800000DA",
            "kernel_name":"NtQueryVolumeInformationFile",
            "caller":"0x0023A3CE",
            "call_esp":"0x008BF8C4",
            "saved_esp":"0x008BF8E0",
            "observed_frame_bytes":28,
            "canonical_frame_bytes":24,
            "fault":0,
            "ticks":689165
        },
        "repair":{
            "caller":"0x0023A3CE",
            "observed_frame_bytes":28,
            "resume_adjustment_bytes":-4,
            "result_frame_bytes":24,
            "requires_zero_return_slot":True,
            "requires_live_tagged_handle":True,
            "requires_guest_iosb_8_bytes":True,
            "requires_guest_info_24_bytes":True,
            "requires_length_at_least_24":True,
            "requires_info_class_3":True
        },
        "translated_membership_changed":False,
        "all_phase6bp_gpu_bridges_inherited":True,
        "nv2a_mmio_vram_policy_changed":False,
        "allocator_changed":False,
        "execution_budget":8000000,
        "source_layout":layout
    }
    (a.out_dir/"phase6bq-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")

    print("[Phase6BQ] 6BP hardware: RtlInitAnsi A3CE repair PASS; PBL phase1 reached")
    print("[Phase6BQ] next boundary: NtQueryVolumeInformationFile caller=0023A3CE delta=28 expected=24 fault=0")
    print("[Phase6BQ] repair: exact caller/frame + canonical class-3 size-information validation; resume savedEsp-4")
    print("[Phase6BQ] translated membership unchanged")
    print("[Phase6BQ] all 6BP GPU semantics, allocator geometry and 8M budget inherited unchanged")
    print("[Phase6BQ] EMIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
