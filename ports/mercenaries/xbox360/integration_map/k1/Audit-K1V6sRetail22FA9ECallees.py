#!/usr/bin/env python3
"""K1 V6s-DEP: exact-call ABI and compiled ownership audit for retail 22FA9E.

Read-only, reuses the SHA-verified V6s local x86 report and V6q TrueTU
provenance. Does not generate a surrogate retail function or XEX.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
BASE=ROOT/"build/phase3n_final_abi_scale"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
PARENT=ROOT/"build/phase6_integration_map/k1_native_end_summary_v6rlog"
AUDIT=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/retail_22fa9e_audit.json"
OUT=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/callee_abi_audit.json"
CALLS=(0x0022F3C1,0x0022F3F3,0x0022F364)
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(v):return hashlib.sha256(v).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    need(spec and spec.loader,"Maintained module unavailable: "+str(path))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def run():
    a=json.loads(AUDIT.read_text(encoding="utf-8-sig"))
    need(a["retail_xbe_sha256"]==RETAIL and
         a["function_entry"]=="0x0022FA9E" and
         a["original_generated_c_exists"] is False,"Retail V6s audit provenance mismatch")
    ins=a["control_flow"]["instructions"]
    targets={int(e["to"],16) for e in a["control_flow"]["edges"]
             if e["kind"]=="call" and e["to"]}
    need(targets==set(CALLS),"Original retail 22FA9E callee addresses changed: "+repr(targets))
    need(a["control_flow"]["hazards"]==[],"Root CFG is not hazard-free")
    need(any(x["mnemonic"].startswith("f") for x in ins),
         "Expected x87 instructions missing from the pinned original")
    base=module(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py",
                "v6s_dep_base")
    planner=module(K1/"Plan-K1NextICallBatch.py","v6s_dep_owner")
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    generated=base.load_generated(BASE/"runtime/gen",by_name)
    src=(PARENT/"main.cpp")
    if not src.is_file():
        src=ROOT/"build/phase6_integration_map/k1_pixel_native_watson_v6q/main.cpp"
    owners,counts=planner.owner_inventory(src.read_text(encoding="utf-8"),SHARDS)
    items=[]
    for addr in CALLS:
        ident=planner.classify(addr,by_va,generated)
        body=generated.get(addr,{}).get("source","")
        words=body.splitlines()
        items.append({
          "address":"0x%08X"%addr,
          "retail_classification":ident,
          "compiled_owner_files":owners.get(addr,[]),
          "in_main_pack_lookup":addr in counts["main_pack_lookup_vas"],
          "generated_source_sha256":sha(body.encode()) if body else None,
          "generated_source_preview":words[:18],
          "generated_source_tail":words[-12:],
          "source_contains_x87":any(t in body.lower()
              for t in ("fpu_","st0","fld","fstp","fcom","float")),
        })
    obj={
       "stage":"V6S_22FA9E_THREE_RETAIL_CALLEE_ABI_AND_COMPILED_OWNER_AUDIT",
       "retail_sha256":RETAIL,"root":"0x0022FA9E",
       "root_original_generated_c_available":False,
       "root_ends_with":"ret 8",
       "root_uses_x87":True,
       "retail_direct_callees":items,
       "all_callees_have_generated_c":all(i["retail_classification"]["kind"]=="exact_source_entry" for i in items),
       "all_callees_compiled":all(i["compiled_owner_files"] for i in items),
       "is_translation_ready":False,
       "requires":"Exact x87 semantics and every callee call/return stack ABI verified before handwritten faithful guest translation",
       "safe_to_build_xex":False,
    }
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(obj,indent=2)+"\n",encoding="utf-8")
    print("[K1-V6s-DEP] ROOT 0022FA9E: exact 129B/56-insn original CFG, FPU/x87, ret 8")
    for row in items:
        print("[K1-V6s-DEP] %s: %s; generated=%s; compiled=%s; lookup=%s"%
            (row["address"],row["retail_classification"]["kind"],
             bool(row["generated_source_sha256"]),
             ",".join(row["compiled_owner_files"]) or "NO",
             row["in_main_pack_lookup"]))
    print("[K1-V6s-DEP] REPORT: "+str(OUT))
    print("[K1-V6s-DEP] NO XDK. Original guest source/hard fences unchanged.")
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("[K1-V6s-DEP] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
