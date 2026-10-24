#!/usr/bin/env python3
"""Phase 6BP: caller-specific RtlInitAnsiString saved-ESP repair."""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

BASE_TAG="P6BO-POST-XGRPH-FRONTIER-00209810-20261024-A"
BUILD_TAG="P6BP-RTLANSI-A3CE-REPAIR-20261024-A"
COOKIE_OLD="phase6bo_env_build_cookie"
COOKIE_NEW="phase6bp_env_build_cookie"

def load(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BP] could not load {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def replace_unique(text,old,new,label):
    n=text.count(old)
    if n!=1: raise SystemExit(f"[Phase6BP] expected one {label}, found {n}")
    return text.replace(old,new,1)

def patch_rtlansi_a3ce(text):
    anchor="static DWORD s_phase6boPblCheckpointCalls = 0u;\n"
    if anchor not in text: raise SystemExit("[Phase6BP] 6BO state anchor missing")
    text=text.replace(anchor,anchor+"static DWORD s_phase6bpRtlInitAnsiA3ceRepairCount = 0u;\n",1)

    start_marker="    if (frameBytes == 16u && caller == 0x0022A7A4u)\n    {"
    end_marker="\n    if (frameBytes != 12u)\n    {"
    start=text.find(start_marker)
    end=text.find(end_marker,start)
    if start<0 or end<0: raise SystemExit("[Phase6BP] inherited ordinal-289 repair block changed")
    if text.find(start_marker,start+1)>=0: raise SystemExit("[Phase6BP] multiple ordinal-289 repair blocks found")

    block=r'''    if (frameBytes == 16u &&
        (caller == 0x0022A7A4u || caller == 0x0023A3CEu))
    {
        uint32_t probeReturn = GUEST_READ32(callEsp + 0u);
        uint32_t probeDestination = GUEST_READ32(callEsp + 4u);
        uint32_t probeSource = GUEST_READ32(callEsp + 8u);
        uint32_t probeExtra = GUEST_READ32(callEsp + 12u);
        BYTE* probeDestinationPtr =
            probeDestination ? guest_ptr((DWORD)probeDestination, 8u) : NULL;
        BYTE* probeSourcePtr =
            probeSource ? guest_ptr((DWORD)probeSource, 1u) : (BYTE*)1;

        if (s_accessFault)
        {
            phase4c_escape(
                PHASE4C_BOUNDARY_GUEST_FAULT,
                0x80000121u,
                savedEsp);
            return;
        }

        sprintf(
            line,
            "RtlInitAnsiString SAVEDESP REPAIR PROBE: caller=%08X ret=%08X destination=%08X source=%08X extra=%08X esp=%08X saved_esp=%08X",
            (unsigned int)caller,
            (unsigned int)probeReturn,
            (unsigned int)probeDestination,
            (unsigned int)probeSource,
            (unsigned int)probeExtra,
            (unsigned int)callEsp,
            (unsigned int)savedEsp);
        trace(line);

        if (probeReturn != 0u ||
            probeDestination == 0u ||
            probeDestinationPtr == NULL ||
            probeSourcePtr == NULL)
        {
            sprintf(
                line,
                "RtlInitAnsiString SAVEDESP REPAIR REJECTED: caller=%08X did not match canonical ordinal-289 arguments",
                (unsigned int)caller);
            trace(line);
            phase4c_escape(
                PHASE4C_BOUNDARY_KERNEL_FRAME,
                0x80000121u,
                savedEsp);
            return;
        }

        resumeEsp = savedEsp - 4u;
        frameBytes = 12u;
        ++s_phase5ayRtlInitAnsiSavedEspRepairCount;
        s_phase5ayRtlInitAnsiSavedEspRepairExtra = probeExtra;
        s_phase5ayRtlInitAnsiSavedEspRepairLastResumeEsp = resumeEsp;

        if (caller == 0x0023A3CEu)
            ++s_phase6bpRtlInitAnsiA3ceRepairCount;

        sprintf(
            line,
            "PASS: Phase 6BP RtlInitAnsiString caller %08X saved-ESP repair extra=%08X %08X->%08X restores 12-byte ordinal-289 frame",
            (unsigned int)caller,
            (unsigned int)probeExtra,
            (unsigned int)savedEsp,
            (unsigned int)resumeEsp);
        trace(line);
    }
'''
    text=text[:start]+block+text[end:]

    summary_anchor='"P6BO PBL CHECKPOINT: calls=%u phase1=%u phase2=%u object=%08X value=%08X",'
    p=text.find(summary_anchor)
    if p<0: raise SystemExit("[Phase6BP] PBL summary anchor missing")
    t=text.find("trace(line);",p)
    if t<0: raise SystemExit("[Phase6BP] PBL summary trace missing")
    le=text.find("\n",t)
    if le<0: le=len(text)
    summary=r'''
    sprintf(
        line,
        "P6BP RTLANSI A3CE REPAIR: count=%u",
        (unsigned int)s_phase6bpRtlInitAnsiA3ceRepairCount);
    trace(line);
'''
    return text[:le+1]+summary+text[le+1:]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-dir",type=Path,required=True)
    ap.add_argument("--base-emitter",type=Path,required=True)
    ap.add_argument("--phase6bl-emitter",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    a=ap.parse_args()
    base=load(a.base_emitter,"phase6bp_base")
    p6bl=load(a.phase6bl_emitter,"phase6bp_p6bl")

    main_path=a.base_dir/"main_monolithic.cpp"
    env_path=a.base_dir/"phase5_env.cpp"
    manifest_path=a.base_dir/"phase6bo-manifest.json"
    for p in (main_path,env_path,manifest_path):
        if not p.exists(): raise SystemExit(f"[Phase6BP] cached 6BO input missing: {p}")

    main_text=main_path.read_text(encoding="utf-8")
    env_text=env_path.read_text(encoding="utf-8")
    manifest=json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase")!="6BO" or manifest.get("build_tag")!=BASE_TAG:
        raise SystemExit("[Phase6BP] cached 6BO identity mismatch")

    members=list(manifest.get("members",[]))
    pack_count=int(manifest.get("pack_members",0))
    if not members or pack_count!=len(members):
        raise SystemExit("[Phase6BP] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,COOKIE_OLD,"P6BO POST-XGRPH FRONTIER 00209810:",
        "P6BO PBL CHECKPOINT:",
        "if (frameBytes == 16u && caller == 0x0022A7A4u)",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32","phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32","#define PHASE4C_EXEC_BUDGET 8000000u"
    ):
        if marker not in main_text: raise SystemExit(f"[Phase6BP] inherited marker missing: {marker}")

    main_text=patch_rtlansi_a3ce(main_text)
    main_text=p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BP caller-0023A3CE ordinal-289 saved-ESP repair; canonical-argument validation required; preserve all 6BO GPU semantics and hard fences")
    main_text=replace_unique(main_text,BASE_TAG,BUILD_TAG,"build tag")
    main_text=main_text.replace(COOKIE_OLD,COOKIE_NEW)
    env_text=env_text.replace(COOKIE_OLD,COOKIE_NEW)
    main_text=(main_text.replace("PHASE 6BO","PHASE 6BP")
                         .replace("Phase 6BO","Phase 6BP")
                         .replace('"P6BO ','"P6BP '))
    env_text=(env_text.replace("PHASE 6BO","PHASE 6BP")
                     .replace("Phase 6BO","Phase 6BP"))

    for marker in (
        BUILD_TAG,COOKIE_NEW,"caller == 0x0023A3CEu",
        "s_phase6bpRtlInitAnsiA3ceRepairCount",
        "PASS: Phase 6BP RtlInitAnsiString caller %08X saved-ESP repair",
        "P6BP RTLANSI A3CE REPAIR: count=%u",
        "P6BP POST-XGRPH FRONTIER 00209810:","P6BP PBL CHECKPOINT:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32","phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32","#define PHASE4C_EXEC_BUDGET 8000000u"
    ):
        if marker not in main_text: raise SystemExit(f"[Phase6BP] generated source lost marker: {marker}")

    a.out_dir.mkdir(parents=True,exist_ok=True)
    layout=p6bl.write_sharded_main(a.out_dir,main_text,base)
    (a.out_dir/"phase5_env.cpp").write_text(env_text,encoding="utf-8")

    manifest.update({"phase":"6BP","build_tag":BUILD_TAG,"pack_members":pack_count,"members":members})
    manifest["phase6bp_rtlansi_a3ce_repair"]={
        "source_phase":"6BO",
        "phase6bo_hardware":{
            "post_xgrph_root_00209810_entries":1,
            "boundary_kind":"KERNEL_FRAME",
            "kernel_target":"0x80000121",
            "kernel_name":"RtlInitAnsiString",
            "caller":"0x0023A3CE",
            "call_esp":"0x008BF8C4",
            "saved_esp":"0x008BF8D4",
            "observed_frame_bytes":16,
            "canonical_frame_bytes":12,
            "fault":0,
            "ticks":689115
        },
        "repair":{
            "caller":"0x0023A3CE",
            "observed_frame_bytes":16,
            "resume_adjustment_bytes":-4,
            "result_frame_bytes":12,
            "canonical_argument_validation":True,
            "preserves_existing_0022A7A4_repair":True
        },
        "translated_membership_changed":False,
        "all_phase6bo_gpu_bridges_inherited":True,
        "nv2a_mmio_vram_policy_changed":False,
        "allocator_changed":False,
        "execution_budget":8000000,
        "source_layout":layout
    }
    (a.out_dir/"phase6bp-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")

    print("[Phase6BP] 6BO hardware: post-XGRPH root 00209810 entered")
    print("[Phase6BP] 6BO boundary: RtlInitAnsiString caller=0023A3CE delta=16 expected=12 fault=0")
    print("[Phase6BP] repair: exact caller/frame + canonical argument validation; resume savedEsp-4")
    print("[Phase6BP] translated membership unchanged")
    print("[Phase6BP] all 6BO GPU semantics, allocator geometry and 8M budget inherited unchanged")
    print("[Phase6BP] EMIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
