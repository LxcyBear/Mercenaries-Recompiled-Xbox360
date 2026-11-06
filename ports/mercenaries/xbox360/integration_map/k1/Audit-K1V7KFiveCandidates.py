#!/usr/bin/env python3
"""V7K no-build candidate ownership and caller evidence from a completed V7J scan.

Reads only existing V7J report, local original range metadata and source, and
the current SHA-verified V7I main. Emits metadata; no original source snippets,
no XBE bytes, no XDK, and no Xbox.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys
from pathlib import Path
FOCUS={0x00288F80,0x0022B150,0x0022B178,0x0022DDA4,0x0022E51F}
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
def h(x):return "0x%08X"%x
def need(ok,msg):
    if not ok:raise ValueError(msg)
def load_reader(path):
    spec=importlib.util.spec_from_file_location("v7k_original_reader",path)
    need(spec and spec.loader,"Missing original generated source reader")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def main():
    parser=argparse.ArgumentParser()
    for name in ("report","ranges","generated","emitter","current_main","current_manifest"):
        parser.add_argument("--"+name.replace("_","-"),required=True,type=Path)
    parser.add_argument("--output",required=True,type=Path)
    a=parser.parse_args()
    scan=json.loads(a.report.read_text(encoding="utf-8-sig"))
    need(scan.get("phase")=="K1_V7J_RETAIL_XBOXRECOMP_TRUE_TU_SOURCE_BATCH_READ_ONLY" and
         scan.get("retail_sha256")==RETAIL and scan.get("true_tus")==64,
         "V7J report identity drift")
    data=a.current_main.read_bytes()
    digest=hashlib.sha256(data).hexdigest()
    manifest=json.loads(a.current_manifest.read_text(encoding="utf-8-sig"))
    need(manifest.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY" and
         manifest.get("source_sha256")==digest and
         scan.get("v7i_main_sha256")==digest,
         "V7I source/report identity drift")
    reader=load_reader(a.emitter)
    ranges,byname=reader.load_ranges(a.ranges)
    sources=reader.load_generated(a.generated,byname)
    need(len(ranges)>=13000 and len(sources)>=10000,"Original source/ranges incomplete")
    found={int(row["va"],16):row for row in scan["candidate_priority"]}
    need(FOCUS.issubset(found),"V7J depth-five candidates incomplete; rerun -Depth 5 -Cap 1200")
    current=data.decode("utf-8",errors="replace")
    result=[]
    for at in sorted(FOCUS):
        row=found[at];inv=ranges.get(at,{})
        body=sources.get(at,{}).get("source","")
        masked=reader.mask_noncode(body)
        # Describe direct calls but do not upload source itself.
        direct=sorted({int(x,16) for x in re.findall(r'\bsub_([0-9a-fA-F]{8})\s*\(',masked)}-{at})
        predecessors=[entry for entry in scan["candidate_priority"]
                      if row["va"] in entry.get("actual_generated_direct_calls",[])]
        source_candidate=bool(body) and not row.get("already_compiled",False)
        result.append({
            "address":h(at),"kind":"generated_C_unstaged" if source_candidate
                else "missing_generated_body_needs_retail_xbe_disassembly",
            "original_range": {"start":h(inv["start"]),"end":h(inv["end"]),
                 "size":inv["end"]-inv["start"]} if inv else None,
            "original_source_file":sources.get(at,{}).get("file"),
            "original_generated_sha256":hashlib.sha256(body.encode()).hexdigest() if body else None,
            "source_calls":[h(x) for x in direct],
            "source_has_itail":bool(re.search(r'\bRECOMP_ITAIL\s*\(',masked)),
            "source_has_icall":bool(re.search(r'\bRECOMP_ICALL_SAFE\s*\(',masked)),
            "source_uses_guest_stack":bool(re.search(r'\b(PUSH32|POP32|g_esp|esp)\b',masked)),
            "source_has_x87":bool(re.search(r'\b(fld|fstp|fadd|fsub|fmul|fdiv)\b',masked,re.I)),
            "observed_graph_callers":[{"va":p["va"],"depth":p["depth"]} for p in predecessors],
            "compilation_status":"already_compiled" if row.get("already_compiled") else "not_found_in_compiled_coverage",
            "original_retail_bytes_verified":False,
            "abi_verified":False,
            "source_only_candidate":source_candidate,
        })
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps({
        "stage":"V7K_FIVE_FUNCTION_TARGETED_METADATA_ONLY",
        "parent_v7j_sha256":hashlib.sha256(a.report.read_bytes()).hexdigest(),
        "parent_v7i_sha256":digest,
        "candidates":result,"xdk_build":False,"xbox_run":False,
        "note":"Missing generated C does NOT mean missing retail function or safe to stub. Source candidate is not ABI-approved."
    },indent=2)+"\n",encoding="utf-8")
    print("[K1-V7K] VERIFIED V7I + V7J, offline candidate ownership")
    for row in result:
        print("[K1-V7K] %s %-44s size=%s caller_count=%u x87=%s" % (
            row["address"],row["kind"],
            row["original_range"]["size"] if row["original_range"] else "?",
            len(row["observed_graph_callers"]),row["source_has_x87"]))
    print("[K1-V7K] REPORT "+str(a.output))
    print("[K1-V7K] NO XDK / NO XBOX / NO GUEST SOURCE OUTPUT")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7K] HARD FENCE "+str(e),file=sys.stderr);sys.exit(1)
