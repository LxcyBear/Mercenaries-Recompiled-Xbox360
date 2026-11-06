#!/usr/bin/env python3
"""V7N: classify five verified XBE functions for a single source recovery batch.

Uses V7M local evidence + original V7L proof, disassembles exact-SHA retail bytes,
resolves direct/indirect transfers, ret-ESP immediates, original-range callees,
and excludes already staged V7I functions. Never creates translated game code.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,struct,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_GRP_CALL,CS_GRP_JUMP,CS_GRP_RET
from capstone.x86_const import X86_OP_IMM
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGETS=(0x0022B150,0x0022B178,0x0022DDA4,0x0022E51F,0x00288F80)
def need(v,m):
    if not v:raise ValueError(m)
def h(v):return "0x%08X"%v
def load(p,n):
    spec=importlib.util.spec_from_file_location(n,p)
    need(spec and spec.loader,"reader missing")
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj
def main():
    p=argparse.ArgumentParser()
    for n in ("xbe","v7m","v7l","ranges","emitter","v7i_main","v7i_manifest","out"):
        p.add_argument("--"+n.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    xbe=a.xbe.read_bytes()
    need(hashlib.sha256(xbe).hexdigest().upper()==SHA,"Wrong retail XBE")
    v7m=json.loads(a.v7m.read_text(encoding="utf-8-sig"))
    v7l=json.loads(a.v7l.read_text(encoding="utf-8-sig"))
    need(v7m.get("status")=="K1_V7M_RETAIL_FIVE_LOCAL_CONTROL_FLOW_ABI_DOSSIER" and
         v7l.get("status")=="K1_V7L_EXACT_RETAIL_FIVE_FUNCTION_X86_WITNESS_SOURCE_ONLY" and
         v7m.get("v7l_report_sha256")==hashlib.sha256(a.v7l.read_bytes()).hexdigest(),
         "V7M/V7L provenance invalid")
    main=a.v7i_main.read_bytes()
    manifest=json.loads(a.v7i_manifest.read_text(encoding="utf-8-sig"))
    need(manifest.get("source_sha256")==hashlib.sha256(main).hexdigest()==v7m["v7i_source_sha256"],
         "V7I source changed")
    base=load(Path(__file__).with_name("Audit-K1V7LRetailFiveX86.py"),"v7n_base")
    reader=load(a.emitter,"v7n_reader")
    ranges,_=reader.load_ranges(a.ranges)
    need(len(ranges)>=13000,"Source range inventory missing")
    summary={int(x["address"],16):x for x in v7l["targets"]}
    need(set(summary)==set(TARGETS),"Changed candidate set")
    d=Cs(CS_ARCH_X86,CS_MODE_32);d.detail=True
    sections=base.sections(xbe)
    rows=[]
    for va in TARGETS:
        r=ranges[va]
        blob=base.extract(xbe,sections,va,r["end"]-va)
        need(hashlib.sha256(blob).hexdigest()==summary[va]["retail_function_sha256"],
             "Function retail bytes drift "+h(va))
        ins=list(d.disasm(blob,va))
        need(sum(x.size for x in ins)==len(blob),"Partial disasm "+h(va))
        immediates=[]
        direct=[]
        indirect_calls=[]
        indirect_jumps=[]
        internal_jumps=[]
        external_jumps=[]
        for i in ins:
            if i.group(CS_GRP_RET):
                n=struct.unpack("<H",i.bytes[-2:])[0] if i.mnemonic=="ret" and i.size==3 else 0
                immediates.append(n)
            if i.group(CS_GRP_CALL) or i.group(CS_GRP_JUMP):
                direct_target=i.operands[0].imm&0xffffffff if i.operands and i.operands[0].type==X86_OP_IMM else None
                if direct_target is None:
                    (indirect_calls if i.group(CS_GRP_CALL) else indirect_jumps).append(h(i.address))
                elif i.group(CS_GRP_CALL):
                    direct.append({"site":h(i.address),"target":h(direct_target),
                                   "exact_original_entry":direct_target in ranges})
                else:
                    (internal_jumps if va<=direct_target<r["end"] else external_jumps).append(
                        {"site":h(i.address),"target":h(direct_target)})
        # original range ownership and source presence are separate concepts.
        disasm_sites=v7m["functions"][[int(x["va"],16) for x in v7m["functions"]].index(va)]
        need(len(direct)==len(disasm_sites["direct_calls"]),"V7M direct call count drift")
        rows.append({
            "va":h(va),"original_size":len(blob),"ret_esp_values":sorted(set(immediates)),
            "ret_esp_consistent":len(set(immediates))==1,
            "return_sites":len(immediates),"original_direct_calls":direct,
            "non_original_direct_callees":sorted({c["target"] for c in direct if not c["exact_original_entry"]}),
            "indirect_calls":indirect_calls,"indirect_jumps":indirect_jumps,
            "internal_jumps":len(internal_jumps),"external_jumps":external_jumps,
            "generated_c_available":summary[va]["original_generated_source"],
            "compilation_candidate":summary[va]["stage_candidate"],
            "abi_proven":False,
            "integration_gate":"generated_source_dependency_and_ABI_review" if summary[va]["stage_candidate"]
              else "retail_x86_to_C_recovery_and_stack_ABI_review",
        })
    out={
        "status":"K1_V7N_RET_ABI_AND_INDIRECT_BRANCH_BATCH_PLAN",
        "retail_sha256":SHA,"v7i_source_sha256":v7m["v7i_source_sha256"],
        "v7m_sha256":hashlib.sha256(a.v7m.read_bytes()).hexdigest(),
        "functions":rows,
        "batch_decision":"NOT_BUILD_READY",
        "blockers":["Exact call frame and register lifetimes unverified",
                    "Four absent original generated-C function implementations",
                    "No reviewed source-stage integration for 0x00288F80",
                    "Retail NtReadFile Event/APC path must remain fenced"],
        "xdk_build":False,"xbox_run":False}
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7N] EXACT RETAIL 5-FUNCTION ABI/TRANSFER TRIAGE")
    for r in rows:
        print("[K1-V7N] %s ret_esp=%s consistent=%s direct=%d indirect_calls=%d indirect_jumps=%d out_jumps=%d source=%s"%
              (r["va"],",".join(map(str,r["ret_esp_values"])),r["ret_esp_consistent"],
               len(r["original_direct_calls"]),len(r["indirect_calls"]),
               len(r["indirect_jumps"]),len(r["external_jumps"]),
               r["generated_c_available"]))
    print("[K1-V7N] NOT BUILD READY; REPORT "+str(a.out))
    print("[K1-V7N] NO GAME SOURCE / NO XDK / NO XBOX")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7N] HARD FENCE "+str(e),file=sys.stderr);sys.exit(1)
