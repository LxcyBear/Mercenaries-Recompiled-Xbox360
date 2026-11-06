#!/usr/bin/env python3
"""K1 V7: batch original-XBE recompiler/decomp gap scan. ZERO Xbox builds.

Reuses original xboxrecomp function inventory and generated recomp_*.c first.
Examines SHA256-verified original default.xbe for only absent translated bodies
in the 22F000..22FB1F startup graphics/math neighborhood. Follows real direct
x86 CALL destinations and inventories the neighborhood in ONE offline pass.
Refuses to invent C, direct tails, ABI, or executable-ready status.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys
from collections import deque
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
BASE=ROOT/"build/phase3n_final_abi_scale"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
V6Z=ROOT/"build/phase6_integration_map/k1_pixel_retail_22f9bc_v6z"
OUT=ROOT/"build/phase6_integration_map/k1_batch_recomp_recovery_v7"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
ROOT_VA=0x0022F5A7
LOW,HIGH=0x0022F000,0x0022FB1F
MAX_FUNCS=160
MAX_DEPTH=3
XBES=[Path.home()/"OneDrive/Desktop/My Xbox/default.xbe",
      Path.home()/"Desktop/My Xbox/default.xbe"]
def need(c,m):
    if not c:raise ValueError(m)
def sha(b):return hashlib.sha256(b).hexdigest()
def load(p,n):
    spec=importlib.util.spec_from_file_location(n,p)
    need(spec is not None and spec.loader is not None,"Missing maintained component: "+str(p))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def decode(cap,audit,blob,sects,va,end):
    cs=cap.Cs(cap.CS_ARCH_X86,cap.CS_MODE_32);cs.detail=True
    q=deque([va]);seen={};occupied={};edges=[];issues=[]
    while q and len(seen)<4096:
        pc=q.popleft()
        if pc in seen:continue
        if not(va<=pc<end):
            issues.append("CFG leaves declared function at 0x%08X"%pc);continue
        try:raw=audit.bytes_at(blob,sects,pc,min(15,end-pc))
        except Exception as ex:issues.append("unmapped instruction at %08X: %s"%(pc,ex));continue
        ins=list(cs.disasm(raw,pc,count=1))
        if not ins or ins[0].address!=pc:
            issues.append("undecodable instruction 0x%08X"%pc);continue
        x=ins[0]
        nxt=pc+x.size
        if nxt>end:issues.append("cross-function instruction 0x%08X"%pc);continue
        for b in range(pc,nxt):
            if b in occupied and occupied[b]!=pc:
                issues.append("overlapping decoded instruction at 0x%08X"%b)
            occupied[b]=pc
        seen[pc]={"va":"0x%08X"%pc,"size":x.size,
                  "mnemonic":x.mnemonic,"operands":x.op_str,
                  "bytes":x.bytes.hex().upper()}
        if x.group(cap.CS_GRP_RET):continue
        if x.mnemonic in ("int3","ud2","hlt"):
            issues.append("trap reached at 0x%08X"%pc);continue
        if x.group(cap.CS_GRP_JUMP):
            if x.operands and x.operands[0].type==cap.CS_OP_IMM:
                target=x.operands[0].imm&0xFFFFFFFF
                edges.append({"type":"jump","from":"0x%08X"%pc,
                              "target":"0x%08X"%target})
                if va<=target<end:q.append(target)
                else:issues.append("jump outside owner from 0x%08X to 0x%08X"%(pc,target))
            else:
                issues.append("indirect jump at 0x%08X"%pc)
            if x.mnemonic not in ("jmp","ljmp"):
                if nxt<end:q.append(nxt)
                else:issues.append("branch fallthrough beyond function")
            continue
        if x.group(cap.CS_GRP_CALL):
            target=x.operands[0].imm&0xFFFFFFFF if x.operands and x.operands[0].type==cap.CS_OP_IMM else None
            edges.append({"type":"direct_call" if target is not None else "indirect_call",
                          "from":"0x%08X"%pc,
                          "target":"0x%08X"%target if target is not None else None})
            if target is None:issues.append("indirect CALL needs ABI proof at 0x%08X"%pc)
        if nxt<end:q.append(nxt)
        else:issues.append("fallthrough exits function at 0x%08X"%pc)
    if q:issues.append("instruction bound 4096 exceeded")
    return {"instructions":[seen[a] for a in sorted(seen)],
            "edges":edges,"hazards":sorted(set(issues)),
            "decoded_instructions":len(seen),
            "x87_instructions":sum(1 for v in seen.values() if v["mnemonic"].startswith("f")),
            "return_instructions":[v for v in seen.values() if v["mnemonic"].startswith("ret")],
            "unmapped_function_bytes":end-va-len(occupied),
            "function_bytes":end-va}
def execute(args):
    import capstone as cap
    base=load(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py","v7_base")
    planner=load(K1/"Plan-K1NextICallBatch.py","v7_planner")
    audit=load(K1/"Audit-K1D3DSwitchCases.py","v7_xbe")
    valid=[p for p in XBES if p.is_file() and sha(p.read_bytes()).upper()==SHA]
    need(valid,"Retail default.xbe not found with exact pinned SHA256")
    blob,sects=audit.get_retail_sections(valid[0])
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    generated=base.load_generated(BASE/"runtime/gen",by_name)
    need(ROOT_VA in by_va,"New Xbox hard-stop 0x0022F5A7 not exact original function")
    need(LOW<=ROOT_VA<HIGH,"Boundary address outside requested batch neighborhood")
    main=V6Z/"main.cpp"
    pm=json.loads((V6Z/"v6z-manifest.json").read_text(encoding="utf-8-sig"))
    main_bytes=main.read_bytes()
    need(pm["source_sha256"]==sha(main_bytes) and
         pm["stage"]=="V6Z_ORIGINAL_RETAIL_22F9BC_X87_SOURCE_UNTESTED" and
         pm["native_summary_preserved"] and
         pm["seven_async_reads_preserved_in_source"],
         "V6z hardware baseline source hash/manifest drift")
    owners,compiled_meta=planner.owner_inventory(main_bytes.decode("utf-8",errors="replace"),SHARDS)
    need(len(compiled_meta["parent_64_true_tu_sha256"])==64 and
         compiled_meta["parent_64_true_tu_sha256"]==pm["true_tu_sha256"],
         "64 TrueTU hashes drifted")
    candidates=sorted(v for v in by_va if LOW<=v<HIGH)
    work=deque([(ROOT_VA,0,"hardware"),*[(v,0,"proximity") for v in candidates]])
    found={};crosses=set()
    while work and len(found)<MAX_FUNCS:
        va,depth,reason=work.popleft()
        if va in found:continue
        owner=planner.classify(va,by_va,generated)
        row=by_va.get(va)
        if not row or not(0x00011000<=va<row["end"]<=0x00255620):
            crosses.add(va);continue
        compiled=va in compiled_meta["compiled_in_64_or_main"]
        routed=va in compiled_meta["main_pack_lookup_vas"]
        item={"entry":"0x%08X"%va,"end_exclusive":"0x%08X"%row["end"],
              "depth":depth,"source":reason,"classification":owner["kind"],
              "already_compiled":compiled,"already_routed":routed,
              "generated_c_file":generated.get(va,{}).get("file")}
        if not compiled:
            raw=audit.bytes_at(blob,sects,va,row["end"]-va)
            cfg=decode(cap,audit,blob,sects,va,row["end"])
            item.update({
                "retail_function_sha256":sha(raw),
                "opcode_mnemonics":sorted({r["mnemonic"] for r in cfg["instructions"]}),
                "unsupported_or_ambiguous":cfg["hazards"],
                "decoded_instruction_count":cfg["decoded_instructions"],
                "x87_instruction_count":cfg["x87_instructions"],
                "ret_abi":[r["operands"] for r in cfg["return_instructions"]],
                "unmapped_bytes":cfg["unmapped_function_bytes"],
                "direct_calls":[e["target"] for e in cfg["edges"] if e["type"]=="direct_call"],
                "indirect_call_count":sum(e["type"]=="indirect_call" for e in cfg["edges"]),
                "candidate_kind":"already_generated_not_integrated" if va in generated
                    else "retail_x86_source_recovery_required",
                "abi_proven":False if va not in generated else None,
                "eligible_for_build":False,
                "first_instructions":cfg["instructions"][:10],
            })
            for edge in cfg["edges"]:
                if edge["type"]=="direct_call":
                    target=int(edge["target"],16)
                    if target in by_va and depth<MAX_DEPTH:
                        work.append((target,depth+1,"direct_call_from_%08X"%va))
                    else:crosses.add(target)
        found[va]=item
    missing=[x for x in found.values() if not x["already_compiled"]]
    result={
       "stage":"V7_ORIGINAL_XBOXRECOMP_AND_RETAIL_XBE_BATCH_GAP_ANALYSIS_ONLY",
       "retail_sha256":SHA,
       "hardware_frontier":"0x0022F5A7",
       "hardware_ticks":61948814,
       "neighborhood":["0x%08X"%LOW,"0x%08X"%HIGH],
       "original_compiled_corpus_count":len(generated),
       "real_64_true_tus_preserved":True,
       "functions_analyzed":len(found),
       "missing_function_count":len(missing),
       "missing_generated_c_count":sum(x["generated_c_file"] is None for x in missing),
       "generated_but_not_integrated_count":sum(x["generated_c_file"] is not None for x in missing),
       "not_traversed_or_outside_inventory":["0x%08X"%x for x in sorted(crosses)],
       "functions":[found[va] for va in sorted(found)],
       "safe_to_build_xex":False,
       "next_step":"Batch-lift all supported missing source functions offline, prove their ABI and cross-calls, then do ONE controlled XDK build for the closed batch.",
    }
    OUT.mkdir(parents=True,exist_ok=True)
    path=OUT/"v7_batch_gap_report.json"
    path.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7] VERIFIED RETAIL XBE: "+SHA)
    print("[K1-V7] HARDWARE TARGET: 0022F5A7 at tick 61948814")
    print("[K1-V7] ORIGINAL INVENTORY: %d functions in bounded cluster, %d examined"%
          (len(candidates),len(found)))
    print("[K1-V7] SOURCE GAPS: %d missing compiled; %d missing generated; %d generated but not staged"%
          (len(missing),result["missing_generated_c_count"],
           result["generated_but_not_integrated_count"]))
    for item in missing[:80]:
        kinds=",".join(item["opcode_mnemonics"][:8])
        print("[K1-V7] %s %s x87=%s ret=%s hazards=%s ins=%s op=%s"%
              (item["entry"],item["candidate_kind"],item["x87_instruction_count"],
               item["ret_abi"],len(item["unsupported_or_ambiguous"]),
               item["decoded_instruction_count"],kinds))
    if len(missing)>80:print("[K1-V7] More gaps listed in JSON, avoiding verbose console")
    print("[K1-V7] OUTPUT: "+str(path))
    print("[K1-V7] BATCH PLAN ONLY, NO XDK, NO GUEST SOURCE MODIFIED.")
if __name__=="__main__":
    ap=argparse.ArgumentParser()
    args=ap.parse_args()
    try:execute(args)
    except Exception as ex:
        print("[K1-V7] HARD FENCE: "+str(ex),file=sys.stderr)
        sys.exit(1)
