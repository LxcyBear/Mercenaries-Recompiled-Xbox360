#!/usr/bin/env python3
"""K1 V7B: offline five-function recomp/XBE translation input bundle.

Recovers complete original retail x86 disassembly for every missing V7 batch
function, cross-checks SHA-pinned retail bytes, and captures relevant proven
recompiler SIMD/x87 source patterns (instead of guessing implementations).
No XEX, no guest patches, no synthesized/stub implementation.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
D=ROOT/"build/phase6_integration_map/k1_batch_recomp_recovery_v7"
REPORT=D/"v7_batch_gap_report.json"
OUT=D/"v7b_five_function_recomp_inputs.txt"
JSON=D/"v7b_five_function_recomp_inputs.json"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGETS={0x0022F5A7,0x0022F49E,0x0022F51C,0x0022F6A5,0x0022F7C6}
SAMPLES=("addps","movaps","mulps","shufps","movhlps","movlps","movhps",
         "movss","unpckhps","unpcklps","fsincos","fchs")
def need(ok,msg):
    if not ok:raise ValueError(msg)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    need(spec is not None and spec.loader is not None,"Missing module: "+str(path))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def execute():
    import capstone
    j=json.loads(REPORT.read_text(encoding="utf-8-sig"))
    need(j["stage"]=="V7_ORIGINAL_XBOXRECOMP_AND_RETAIL_XBE_BATCH_GAP_ANALYSIS_ONLY"
         and j["retail_sha256"]==SHA and j["hardware_frontier"]=="0x0022F5A7"
         and j["safe_to_build_xex"] is False,
         "V7 batch provenance changed")
    missing={int(x["entry"],16):x for x in j["functions"] if not x["already_compiled"]}
    need(set(missing)==TARGETS,"V7 missing-function set changed; refuse partial/stale report")
    xbes=[p for p in [Path.home()/"OneDrive/Desktop/My Xbox/default.xbe",
                      Path.home()/"Desktop/My Xbox/default.xbe"]
          if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest().upper()==SHA]
    need(xbes,"Pinned retail default.xbe is missing")
    v7=load(K1/"Plan-K1V7RecompXbeBatch.py","v7b_decoder")
    auditor=load(K1/"Audit-K1D3DSwitchCases.py","v7b_sections")
    blob,sects=auditor.get_retail_sections(xbes[0])
    full=[]
    lines=["[K1-V7B] EXACT RETAIL XBE FIVE-FUNCTION RECOMP INPUTS",
           "RETAIL SHA256: "+SHA,
           "HARDWARE ROOT: 0x0022F5A7 / tick 61948814",
           "This is source analysis, NOT a native-compilation or hardware proof."]
    union_ops=set()
    for va in sorted(missing):
        row=missing[va]
        end=int(row["end_exclusive"],16)
        data=auditor.bytes_at(blob,sects,va,end-va)
        need(hashlib.sha256(data).hexdigest()==row["retail_function_sha256"],
             "Original retail bytes changed at %08X"%va)
        cfg=v7.decode(capstone,auditor,blob,sects,va,end)
        need(not cfg["hazards"] and
             cfg["decoded_instructions"]==row["decoded_instruction_count"] and
             cfg["unmapped_function_bytes"]==row["unmapped_bytes"] and
             cfg["x87_instructions"]==row["x87_instruction_count"],
             "Recomp function/instruction audit drift at %08X"%va)
        union_ops.update(x["mnemonic"] for x in cfg["instructions"])
        full.append({"entry":"0x%08X"%va,
                     "end":"0x%08X"%end,
                     "retail_bytes_sha256":hashlib.sha256(data).hexdigest(),
                     "instructions":cfg["instructions"],"edges":cfg["edges"],
                     "ret_abi":row["ret_abi"],"x87_count":cfg["x87_instructions"],
                     "requires_original_translation":True})
        lines+=["","== 0x%08X..0x%08X (%d bytes, %d instructions) =="%
                (va,end,len(data),len(cfg["instructions"])),
                "RET: "+repr(row["ret_abi"]),
                "DIRECT CALLS: "+repr(row["direct_calls"]),
                "X87: "+str(cfg["x87_instructions"])]
        for ins in cfg["instructions"]:
            lines.append("%s %-20s %-9s %s"%
                         (ins["va"],ins["bytes"],ins["mnemonic"],ins["operands"]))
    # Collect *actual* original generated code examples to guide a faithful
    # offline lift of the same instruction families. No guessing host macros.
    generated=ROOT/"build/phase3n_final_abi_scale/runtime/gen"
    need(generated.is_dir(),"Original xboxrecomp generated source corpus missing")
    sample={k:[] for k in SAMPLES}
    counts={k:0 for k in SAMPLES}
    for p in sorted(generated.glob("recomp_*.c")):
        if p.name in ("recomp_dispatch.c","recomp_stubs_unresolved.c"):continue
        raw=p.read_text(encoding="utf-8",errors="replace").splitlines()
        for n,line in enumerate(raw):
            low=line.lower()
            if "/*" not in low and "recomp_xmm" not in low and "fp_" not in low:continue
            for k in SAMPLES:
                if not re.search(r"\b"+re.escape(k)+r"\b",low):continue
                counts[k]+=1
                if len(sample[k])<4:
                    sample[k].append({"file":p.name,"line":n+1,
                                      "source":"\n".join(raw[max(0,n-1):min(len(raw),n+2)])})
    lines+=["","== EXISTING XBOXRECOMP GENERATED INSTRUCTION TEMPLATES =="]
    for mnemonic in SAMPLES:
        lines.append("%s: original generated occurrences=%d"%(mnemonic,counts[mnemonic]))
        for example in sample[mnemonic]:
            lines.append("  %s:%d %s"%(example["file"],example["line"],
                                      example["source"].replace("\n","\n    ")))
    data={"stage":"V7B_FIVE_FUNCTION_EXACT_XBE_AND_RECOMP_TEMPLATE_EVIDENCE",
          "retail_sha256":SHA,"hardware_root":"0x0022F5A7",
          "source_gaps":full,"source_template_counts":counts,
          "source_templates":sample,
          "missing_opcode_families_without_corpus_templates":[x for x in SAMPLES if
              x in union_ops and counts[x]==0],
          "xdk_invoked":False,"guest_source_modified":False,
          "safe_to_build_xex":False}
    D.mkdir(parents=True,exist_ok=True)
    OUT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    JSON.write_text(json.dumps(data,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7B] FIVE-FUNCTION ORIGINAL XBE SOURCE BUNDLE PASS")
    for item in full:
        print("[K1-V7B] %s: %d original instructions, ret%s, x87=%d"%
              (item["entry"],len(item["instructions"]),repr(item["ret_abi"]),
               item["x87_count"]))
    print("[K1-V7B] EXISTING RECOMP TEMPLATES: "+", ".join("%s=%d"%(k,counts[k]) for k in SAMPLES))
    print("[K1-V7B] TEXT REPORT: "+str(OUT))
    print("[K1-V7B] JSON REPORT: "+str(JSON))
    print("[K1-V7B] NO XDK. NO GUEST CODE MODIFIED.")
if __name__=="__main__":
    try:execute()
    except Exception as e:
        print("[K1-V7B] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
