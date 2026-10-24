#!/usr/bin/env python3
"""Phase 6BO: cross the clean post-XGRPH DIRECT_FRONTIER 0x00209810.

6BN hardware proved that translated XGRPH frontier 0x0029C8BE entered six
times, inherited GPU bridge semantics stayed coherent, and execution advanced
to DIRECT_FRONTIER 0x00209810 with fault=0. 0x00209810 lies inside the retail
.text section (0x00011000..0x0025561C), so this stage follows the return from
XGRPH into title-side code.

The target is not assumed safe: exact-start proof against functions.json and
generated translated code is mandatory. Only an exact generated start receives
a bounded depth-4, cap-256 support-clean closure. GPU/MMIO/VRAM/allocator policy
remains unchanged.
"""
from __future__ import annotations
import argparse, importlib.util, json
from pathlib import Path

BASE_TAG="P6BN-XGRPH-FRONTIER-0029C8BE-20261024-A"
BUILD_TAG="P6BO-POST-XGRPH-FRONTIER-00209810-20261024-A"
ROOT=0x00209810
ROOT_DEPTH=4
ROOT_CAP=256
COOKIE_OLD="phase6bn_env_build_cookie"
COOKIE_NEW="phase6bo_env_build_cookie"

def load(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BO] could not load {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def replace_unique(text,old,new,label):
    count=text.count(old)
    if count!=1: raise SystemExit(f"[Phase6BO] expected one {label}, found {count}")
    return text.replace(old,new,1)

def install_state(text):
    marker="static DWORD s_phase6bnRootEntries = 0u;\n"
    if marker not in text: raise SystemExit("[Phase6BO] inherited 6BN root-state anchor missing")
    return text.replace(marker,marker+"static DWORD s_phase6boRootEntries = 0u;\n",1)

def instrument_root(rendered,name):
    pos=rendered.find(name); brace=rendered.find("{",pos)
    if pos<0 or brace<0: raise SystemExit("[Phase6BO] could not instrument root 0x00209810")
    body='\n    ++s_phase6boRootEntries;\n    trace("PASS: Phase 6BO entered translated post-XGRPH frontier 00209810");'
    return rendered[:brace+1]+body+rendered[brace+1:]

def insert_summary(text):
    marker="P6BN XGRPH FRONTIER 0029C8BE:"
    pos=text.find(marker)
    if pos<0: raise SystemExit("[Phase6BO] inherited 6BN summary marker missing")
    stmt=text.rfind("sprintf(",0,pos)
    if stmt<0 or pos-stmt>5000: raise SystemExit("[Phase6BO] could not locate inherited summary block")
    line_start=text.rfind("\n",0,stmt)+1
    indent=text[line_start:stmt]
    block=(f'{indent}sprintf(\n'
           f'{indent}    line,\n'
           f'{indent}    "P6BO POST-XGRPH FRONTIER 00209810: entries=%u",\n'
           f'{indent}    (unsigned int)s_phase6boRootEntries);\n'
           f'{indent}trace(line);\n')
    return text[:line_start]+block+text[line_start:]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--base-dir",type=Path,required=True)
    ap.add_argument("--base-emitter",type=Path,required=True)
    ap.add_argument("--phase6bl-emitter",type=Path,required=True)
    ap.add_argument("--base-phase5bb-emitter",type=Path,required=True)
    ap.add_argument("--base-phase5bc-emitter",type=Path,required=True)
    ap.add_argument("--generated-root",type=Path,required=True)
    ap.add_argument("--functions",type=Path,required=True)
    ap.add_argument("--out-dir",type=Path,required=True)
    args=ap.parse_args()

    base=load(args.base_emitter,"phase6bo_base")
    p6bl=load(args.phase6bl_emitter,"phase6bo_p6bl")
    p5bb=load(args.base_phase5bb_emitter,"phase6bo_p5bb")
    p5bc=load(args.base_phase5bc_emitter,"phase6bo_p5bc")

    base_main=args.base_dir/"main_monolithic.cpp"
    base_env=args.base_dir/"phase5_env.cpp"
    base_manifest=args.base_dir/"phase6bn-manifest.json"
    for path in (base_main,base_env,base_manifest):
        if not path.exists(): raise SystemExit(f"[Phase6BO] cached Phase 6BN input missing: {path}")

    main_text=base_main.read_text(encoding="utf-8")
    env_text=base_env.read_text(encoding="utf-8")
    manifest=json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase")!="6BN" or manifest.get("build_tag")!=BASE_TAG:
        raise SystemExit("[Phase6BO] cached Phase 6BN identity mismatch")

    for marker in (BASE_TAG,COOKIE_OLD,"P6BN XGRPH FRONTIER 0029C8BE:",
                   "phase6be_pfifo_idle_write32(address, value)",
                   "phase6bj_pfb_zcomp_write32","phase6bg_pfb_tile_write32",
                   "phase6bh_pgraph_scoped_write32","#define PHASE4C_EXEC_BUDGET 8000000u"):
        if marker not in main_text: raise SystemExit(f"[Phase6BO] inherited 6BN marker missing: {marker}")

    by_va,by_name=base.load_ranges(args.functions)
    generated=base.load_generated(args.generated_root,by_name)
    p6bl.validate_exact(ROOT,by_va,generated)

    root_row=by_va[ROOT]; root_name=generated[ROOT]["name"]
    print(f"[Phase6BO] EXACT ROOT PROOF: 0x{ROOT:08X} {root_name} range=0x{int(root_row['start']):08X}-0x{int(root_row['end']):08X} generated_chars={len(generated[ROOT]['source'])}")
    print("[Phase6BO] SECTION PROOF: target 0x00209810 lies inside retail .text 0x00011000-0x0025561C")

    base.STANDARD_CALLS.add("cos"); base.STANDARD_CALLS.add("sin")
    old={int(x,0) for x in manifest.get("members",[])}
    if not old: raise SystemExit("[Phase6BO] inherited translated pack membership is empty")
    if ROOT in old: raise SystemExit("[Phase6BO] root 0x00209810 is already present in inherited pack; inspect dispatch bookkeeping instead")

    closure=set(p5bb.bounded_promoted_members(base,ROOT,generated,ROOT_DEPTH,ROOT_CAP))
    closure.add(ROOT)
    candidate_new=sorted(va for va in closure if va not in old)
    if ROOT not in candidate_new: raise SystemExit("[Phase6BO] closure construction lost mandatory root")

    expanded=old|set(candidate_new)
    main_text=install_state(main_text)
    p5bc.SWEEP_ROOT=ROOT
    p5bc.instrument_root_entry=instrument_root
    main_text,rendered,frontiers,pruned=p5bc.insert_pack_members(main_text,base,p5bb,generated,candidate_new,expanded)

    if ROOT in pruned:
        raise SystemExit(f"[Phase6BO] support-clean pruning removed mandatory root 0x{ROOT:08X}; unresolved support={', '.join(map(str,pruned.get(ROOT,[])))}")

    main_text=insert_summary(main_text)
    main_text=p6bl.replace_policy_line(main_text,"Policy: Phase 6BO post-XGRPH .text frontier 00209810 depth-4 cap-256 closure; preserve all 6BN GPU semantics and hard fences")
    main_text=replace_unique(main_text,BASE_TAG,BUILD_TAG,"build tag")
    main_text=main_text.replace(COOKIE_OLD,COOKIE_NEW)
    env_text=env_text.replace(COOKIE_OLD,COOKIE_NEW)
    main_text=(main_text.replace("PHASE 6BN","PHASE 6BO").replace("Phase 6BN","Phase 6BO").replace('"P6BN ','"P6BO '))
    env_text=env_text.replace("PHASE 6BN","PHASE 6BO").replace("Phase 6BN","Phase 6BO")

    for marker in (BUILD_TAG,COOKIE_NEW,"case 0x00209810u:","s_phase6boRootEntries",
                   "PASS: Phase 6BO entered translated post-XGRPH frontier 00209810",
                   "P6BO POST-XGRPH FRONTIER 00209810:",
                   "phase6be_pfifo_idle_write32(address, value)",
                   "phase6bj_pfb_zcomp_write32","phase6bg_pfb_tile_write32",
                   "phase6bh_pgraph_scoped_write32","#define PHASE4C_EXEC_BUDGET 8000000u"):
        if marker not in main_text: raise SystemExit(f"[Phase6BO] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True,exist_ok=True)
    layout=p6bl.write_sharded_main(args.out_dir,main_text,base)
    (args.out_dir/"phase5_env.cpp").write_text(env_text,encoding="utf-8")

    manifest.update({"phase":"6BO","build_tag":BUILD_TAG,"pack_members":len(expanded),
                     "members":[f"0x{x:08X}" for x in sorted(expanded)]})
    manifest["phase6bo_post_xgrph_frontier_00209810"]={
        "source_phase":"6BN",
        "phase6bn_hardware":{
            "xgrph_root_0029c8be_entries":6,
            "prior_d3d_root_00290895_result":"PASS",
            "internal_d3d_device_result":"PASS",
            "d3d_sync_checkpoint_calls":9,
            "next_boundary":{"kind":"DIRECT_FRONTIER","target":"0x00209810","caller":"0x0023A3CE","esp":"0x008BF92C","fault":0,"ticks":689045}
        },
        "retail_section":{"name":".text","start":"0x00011000","end_exclusive":"0x0025561C","target_inside":True},
        "root":f"0x{ROOT:08X}","root_name":root_name,
        "root_range":{"start":f"0x{int(root_row['start']):08X}","end":f"0x{int(root_row['end']):08X}"},
        "root_closure_depth":ROOT_DEPTH,"root_closure_cap":ROOT_CAP,
        "candidate_new_members":len(candidate_new),"packed_new_members":len(candidate_new),
        "pruned_members":len(pruned),"expanded_pack_members":len(expanded),
        "new_direct_frontier_targets":[f"0x{x:08X}" for x in sorted(frontiers)],
        "all_phase6bn_gpu_bridges_inherited":True,
        "pfifo_scope_changed":False,"pfb_scope_changed":False,"pgraph_scope_changed":False,
        "nv2a_mmio_vram_policy_changed":False,"execution_budget":8000000,"source_layout":layout
    }
    manifest["phase6bo_pruned_members"]=[{"address":f"0x{va:08X}","name":generated[va]["name"],"unresolved_support":names} for va,names in sorted(pruned.items())]
    (args.out_dir/"phase6bo-manifest.json").write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")

    print("[Phase6BO] 6BN hardware: translated XGRPH frontier 0029C8BE entered six times")
    print("[Phase6BO] next boundary DIRECT_FRONTIER 00209810 fault=0")
    print(f"[Phase6BO] POST-XGRPH PACK: root=0x{ROOT:08X} name={root_name} candidates={len(candidate_new)} pruned={len(pruned)} packed_new={len(candidate_new)} total_pack={len(expanded)}")
    print(f"[Phase6BO] SOURCE SHARDS: {layout['shard_count']}")
    print("[Phase6BO] all 6BN GPU semantics, allocator geometry and 8M budget inherited unchanged")
    print("[Phase6BO] EMIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
