#!/usr/bin/env python3
"""V7H: read-only provenance investigation of existing ordinal-99 routes.

No changes to source, no build, no Xbox. Reports the exact code paths for
KeDelayExecutionThread in V7E and the distinction between ITAIL, ICALL_SAFE,
direct kernel bridges, and generic STORAGE_IO escape.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
BASE=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7e"
OUT=ROOT/"build/phase6_integration_map/k1_kernel99_routes_v7h"
TARGETS=("0x80000063","80000063","phase6bt_ke_delay_execution_thread",
         "PHASE4C_BOUNDARY_STORAGE_IO","PHASE4C_BOUNDARY_ICALL_SAFE",
         "STORAGE_IO","phase4c_escape")
def die(msg):raise ValueError(msg)
def segment(lines,needle,before=6,after=12,limit=16):
    ids=[i for i,x in enumerate(lines) if needle.casefold() in x.casefold()]
    return {"occurrences":len(ids),"matches":[{"line":i+1,
             "context":"\n".join("%5d %s"%(j+1,lines[j])
                 for j in range(max(0,i-before),min(len(lines),i+after+1)))}
             for i in ids[:limit]]}
def macro(lines,name):
    pat=re.compile(r'^\s*#define\s+'+re.escape(name)+r'\s*\(')
    matches=[i for i,l in enumerate(lines) if pat.search(l)]
    if len(matches)!=1:return {"definition_count":len(matches),"error":"expected one macro"}
    start=matches[0];end=start+1
    while end<len(lines) and lines[end-1].rstrip().endswith("\\"):end+=1
    body=lines[start:end]
    return {"start_line":start+1,"end_line":end,
            "contains_kernel99":any("0x80000063" in l for l in body),
            "contains_delay_handler":any("phase6bt_ke_delay_execution_thread" in l for l in body),
            "line_count":len(body),"text":"\n".join("%5d %s"%(i+1,lines[i]) for i in range(start,end))}
def main():
    srcp=BASE/"main.cpp"
    mp=BASE/"v7e-manifest.json"
    raw=srcp.read_bytes()
    manifest=json.loads(mp.read_text(encoding="utf-8-sig"))
    actual=hashlib.sha256(raw).hexdigest()
    if manifest.get("source_sha256")!=actual:die("V7E manifest / source hash drift")
    lines=raw.decode("utf-8-sig",errors="replace").splitlines()
    macros={name:macro(lines,name) for name in
            ("RECOMP_ICALL_SAFE","RECOMP_ITAIL","RECOMP_CALL","RECOMP_JMP")}
    excerpts={v:segment(lines,v,limit=12) for v in TARGETS}
    # Anchor to actual function definitions and collect a bounded body
    defs=[]
    patt=re.compile(r'^\s*(?:static\s+)?void\s+phase6bt_ke_delay_execution_thread\s*\(')
    for i,l in enumerate(lines):
        if patt.search(l):
            block=lines[i:i+125]
            defs.append({"line":i+1,"body_excerpt":"\n".join("%5d %s"%(j+i+1,x) for j,x in enumerate(block))})
    report={"stage":"V7H_KERNEL99_DISPATCH_PROVENANCE_READ_ONLY",
            "source_sha256":actual,
            "retail_xbe_sha256":manifest.get("retail_xbe_sha256"),
            "macros":macros,"handler_definitions":defs,
            "references":excerpts,
            "observed_v7e_stop":{"target":"0x80000063","caller":"0x0023A3CE",
                                 "kind":17,"boundary":"STORAGE_IO","tick":62777793},
            "no_changes":True,"xdk_invoked":False,"xbox_invoked":False}
    OUT.mkdir(parents=True,exist_ok=True)
    out=OUT/"v7h_kernel99_dispatch_routes.json"
    out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7H] V7E source SHA PASS "+actual)
    for n,m in macros.items():
        print("[K1-V7H] %-17s definitions=%s kernel99=%s handler=%s lines=%s"%
              (n,m.get("definition_count",1),m.get("contains_kernel99","?"),
               m.get("contains_delay_handler","?"),m.get("line_count","?")))
    print("[K1-V7H] handler definitions/declarations=%d"%len(defs))
    for n in ("0x80000063","phase6bt_ke_delay_execution_thread","STORAGE_IO"):
        print("[K1-V7H] reference %s occurrences=%d"%
              (n,excerpts[n]["occurrences"]))
    print("[K1-V7H] OUTPUT "+str(out))
    print("[K1-V7H] NO BUILD / NO XBOX / NO SOURCE PATCH")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7H] AUDIT STOP: "+str(e),file=sys.stderr)
        sys.exit(1)
