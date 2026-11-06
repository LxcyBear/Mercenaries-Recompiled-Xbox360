#!/usr/bin/env python3
"""Read-only retail x86 and recompiled C candidate mapping for NtReadFile."""
import argparse, hashlib, json, re
from pathlib import Path
from Audit_K1R11RetailNtReadSlotXrefs import xbe_sections

SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
LABEL=re.compile(r"(?m)^\s*(?:loc|sub)_([0-9A-Fa-f]{8})\s*(?::|\()")

def need(condition, message):
    if not condition: raise ValueError(message)

def source_index(paths):
    idx={}
    for path in paths:
        lines=path.read_text(encoding="utf-8-sig").splitlines()
        for n,line in enumerate(lines):
            m=LABEL.match(line)
            if m:
                va=int(m.group(1),16)
                idx.setdefault(va,[]).append({
                    "source":str(path),"line":n+1,
                    "excerpt":"\n".join("%5d %s"%(j+1,lines[j])
                        for j in range(max(0,n-4),min(len(lines),n+15)))
                })
    return idx

def disassembly(blob,parts,va):
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    sec=next((s for s in parts if s["va"]<=va<s["va"]+min(s["size"],s["virtual"])),None)
    need(sec is not None,"Unmapped retail VA %08X"%va)
    lo=max(sec["va"],va-96)
    hi=min(sec["va"]+min(sec["size"],sec["virtual"]),va+96)
    offset=sec["raw"]+lo-sec["va"]
    raw=blob[offset:offset+hi-lo]
    need(len(raw)==hi-lo,"Retail x86 window not backed by XBE bytes")
    d=Cs(CS_ARCH_X86,CS_MODE_32)
    return {"note":"Linear decoding; initial instruction boundary NOT proven",
            "instructions":[{"va":"%08X"%i.address,"bytes":i.bytes.hex().upper(),
                             "asm":i.mnemonic+" "+i.op_str,
                             "overlaps_candidate":i.address<=va<i.address+i.size}
                            for i in d.disasm(raw,lo)]}

def run(a):
    b=a.retail_xbe.read_bytes()
    need(hashlib.sha256(b).hexdigest().upper()==SHA,"Original retail XBE SHA mismatch")
    r=json.loads(a.r11_report.read_text(encoding="utf-8-sig"))
    need(r.get("status")=="K1_R11_RETAIL_NTREAD_SLOT_ADDRESS_XREF_ONLY" and
         r.get("retail_sha256")==SHA,"Unverified original R11 report")
    xrefs=r["x86_slot_address_references"]
    hits=xrefs["hits"]
    need(len(hits)>0 and len(hits)==xrefs["total"],
         "Retail R11 candidate list absent or truncated")
    shards=sorted(a.shards.glob("translated_*.cpp"))
    need(len(shards)==64,"Expected 64 original translation-unit shards")
    need(a.main_cpp.is_file(),"Missing generated V7Z C source")
    index=source_index([a.main_cpp]+shards)
    sections=xbe_sections(b)
    candidates=[]
    for hit in hits:
        va=int(hit["va"],16)
        prior=[n for n in index if 0<=va-n<=512]
        nearest=max(prior) if prior else None
        candidates.append({
            "reference_va":hit["va"],"retail_instruction":hit["insn"],
            "reference_reasons":hit.get("reasons",[]),
            "original_x86_window":disassembly(b,sections,va),
            "exact_generated_labels":index.get(va,[]),
            "closest_prior_generated_label":"%08X"%nearest if nearest is not None else None,
            "distance_to_prior_label":va-nearest if nearest is not None else None,
            "generated_c_context":index.get(nearest,[]) if nearest is not None else [],
            "real_runtime_caller_proven":False
        })
    out={"stage":"K1_ORIGINAL_X86_TO_RECOMP_C_READ_ONLY",
         "retail_sha256":SHA,"retail_import_slot":r.get("import_slot"),
         "candidates_count":len(candidates),"true_tu_count":64,
         "candidates":candidates,
         "limitations":["IAT slot xref is not a proven dynamic NtReadFile caller",
                        "Linear x86 window decoding may start mid-instruction",
                        "Nearby C labels do not establish real function ownership",
                        "No callback ABI extension or guest behavior change"],
         "no_xdk":True,"no_hardware":True,"no_guest_patch":True}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("[K1-RECOMP] SHA PASS: original retail XBE")
    print("[K1-RECOMP] MAPPED %d retail NtReadFile references against 64 TrueTUs"%len(candidates))
    for c in candidates:
        print("[K1-RECOMP] %s %s exact_C=%s nearby_C=%s"%
            (c["reference_va"],c["retail_instruction"],bool(c["exact_generated_labels"]),
             c["closest_prior_generated_label"]))
    print("[K1-RECOMP] REPORT "+str(a.output))
    print("[K1-RECOMP] NO XDK / XBOX / ABI OR CALLBACK CHANGES")

def main():
    p=argparse.ArgumentParser()
    for name in ("retail-xbe","r11-report","main-cpp","shards","output"):
        p.add_argument("--"+name,required=True,type=Path)
    run(p.parse_args())
if __name__=="__main__":
    main()
