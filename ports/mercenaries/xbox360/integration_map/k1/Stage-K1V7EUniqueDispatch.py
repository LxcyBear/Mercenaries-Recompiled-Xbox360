#!/usr/bin/env python3
"""K1-V7E: source-only repair of the proven V7D packed-dispatch collision.

V6h already routes retail 0x0022F51C to a legacy vec3 helper. V7D also
translated the same retail function and inserted a second switch case.
Keep both source bodies intact; switch exactly once to the V7D translation.
Audit ALL case labels numerically within the single pack dispatcher.
No XDK or Xbox execution, no mutation of V7D or any earlier source.
"""
from __future__ import annotations
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT=Path.cwd()
OLD=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7d"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7e"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
DISPATCH_SIGNATURE="recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)"
LEGACY="    case 0x0022F51Cu: return phase6v6h_retail_vec3_0022f51c;\n"
NEW="    case 0x0022F51Cu: return sub_0022F51C;\n"
TARGETS=(0x0022F49E,0x0022F51C,0x0022F5A7,0x0022F6A5,0x0022F7C6)
CASE_RE=re.compile(r'\bcase\s+(0[xX][0-9a-fA-F]+|[0-9]+)(?:[uUlL]*)\s*:')
MARK="K1-V7E-DISPATCH-DEDUP-22F51C"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def dispatch_body(src):
    need(src.count(DISPATCH_SIGNATURE)==1,"Expected a single original pack dispatcher")
    start=src.index(DISPATCH_SIGNATURE)
    open_brace=src.find("{",start+len(DISPATCH_SIGNATURE))
    need(open_brace>=0,"Dispatcher opening brace missing")
    depth=0
    for i in range(open_brace,len(src)):
        if src[i]=="{":depth+=1
        if src[i]=="}":
            depth-=1
            if depth==0:return src[open_brace:i+1]
    raise ValueError("Dispatcher closing brace missing")
def numeric_cases(body):
    found={}
    for m in CASE_RE.finditer(body):
        val=int(m.group(1),0)
        found.setdefault(val,[]).append(m.start())
    return found
def run():
    p=OLD/"v7d-manifest.json"
    m=json.loads(p.read_text(encoding="utf-8-sig"))
    before=(OLD/"main.cpp").read_bytes()
    need(m["stage"]=="V7D_FIVE_RETAIL_FUNCTIONS_SOURCE_ONLY_UNTESTED" and
         m["retail_xbe_sha256"]==SHA and
         m["source_sha256"]==sha(before) and
         m["native_summary_preserved"] and m["seven_async_reads_preserved_in_source"] and
         m["unknown_frontiers_fenced"],
         "V7D source provenance drift")
    need(m["functions"]==["0x%08X"%x for x in TARGETS] and
         sum(m["original_opcode_counts"].values())==197 and
         len(m["true_tu_sha256"])==64,
         "V7D five-function inventory / original 197 opcodes / TrueTUs changed")
    newline="\r\n" if b"\r\n" in before else "\n"
    src=before.decode("utf-8").replace("\r\n","\n")
    old_body=dispatch_body(src)
    before_cases=numeric_cases(old_body)
    duplicate={k:v for k,v in before_cases.items() if len(v)>1}
    need(duplicate=={0x0022F51C:before_cases[0x0022F51C]} and
         len(before_cases[0x0022F51C])==2,
         "Other numeric switch collision(s) or expected V6h/V7D collision absent: "+
         repr({hex(k):len(v) for k,v in duplicate.items()}))
    need(src.count(LEGACY)==1 and src.count(NEW)==1 and
         old_body.count(LEGACY)==1 and old_body.count(NEW)==1,
         "Could not uniquely identify both exact V6h and V7D case routes")
    # Modify only the exact old dispatcher case, not the legacy function body.
    fixed=src.replace(LEGACY,"",1)
    body=dispatch_body(fixed)
    after_cases=numeric_cases(body)
    need(all(len(v)==1 for v in after_cases.values()),
         "Duplicate numerical case values survive V7E fix")
    for va in TARGETS:
        line="    case 0x%08Xu: return sub_%08X;\n"%(va,va)
        need(body.count(line)==1 and len(after_cases.get(va,[]))==1,
             "Five original retail entries not uniquely routed: 0x%08X"%va)
    need("phase6v6h_retail_vec3_0022f51c" in fixed,
         "V6h legacy implementation body must remain untouched")
    need(src.replace(LEGACY,"",1)==fixed,
         "Unexpected modification outside the legacy dispatch case")
    need(MARK not in fixed,"Marker unexpectedly already exists")
    fixed="/* "+MARK+" */\n"+fixed
    result=fixed.replace("\n",newline).encode("utf-8")
    meta=dict(m)
    meta.update({
        "stage":"V7E_FIVE_RETAIL_FUNCTIONS_UNIQUE_DISPATCH_SOURCE_ONLY",
        "source_sha256":sha(result),
        "parent_v7d_sha256":sha(before),
        "previous_duplicate_va":"0x0022F51C",
        "previous_duplicate_cases":2,
        "remaining_duplicate_cases":0,
        "retained_legacy_v6h_function_body":True,
        "selected_22f51c_route":"sub_0022F51C",
        "original_197_opcodes_preserved":True,
        "xdk_compiled":False,"hardware_verified":False,
    })
    output_files=[
        (OUT/"main.cpp",result),
        (OUT/"v7e-manifest.json",(json.dumps(meta,indent=2)+"\n").encode()),
    ]
    for path,data in output_files:
        need(not path.exists() or path.read_bytes()==data,
             "Existing V7E output mismatch; refuse overwrite: "+str(path))
    OUT.mkdir(parents=True,exist_ok=True)
    for path,data in output_files:
        if not path.exists():path.write_bytes(data)
    need((OLD/"main.cpp").read_bytes()==before,"V7D source mutated")
    print("[K1-V7E] SOURCE FIX PASS: 0x0022F51C legacy V6h dispatcher case removed")
    print("[K1-V7E] Legacy V6h function body preserved; new 5-function batch retained")
    print("[K1-V7E] NUMERIC CASE AUDIT PASS: all %d cases unique"%len(after_cases))
    print("[K1-V7E] 197 retail instructions / 64 TrueTUs unchanged")
    print("[K1-V7E] SOURCE ONLY; XDK/HARDWARE NOT TESTED")
    print("[K1-V7E] OUTPUT: "+str(OUT/"main.cpp"))
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("[K1-V7E] HARD FENCE: "+str(e),file=sys.stderr)
        sys.exit(1)
