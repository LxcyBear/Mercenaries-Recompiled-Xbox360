#!/usr/bin/env python3
"""V7M: offline multi-function retail x86 control-flow/ABI dossier.

All disassembled original instructions and generated C excerpts stay in a
LOCAL-ONLY text file under build/. Shareable JSON has address/count/ABI metadata
without original game bytes. No auto-lift, guest source patch, XDK, Xbox.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys
from collections import deque
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32,CS_GRP_JUMP,CS_GRP_CALL,CS_GRP_RET
from capstone.x86_const import X86_OP_IMM
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGETS=(0x0022B150,0x0022B178,0x0022DDA4,0x0022E51F,0x00288F80)
def fail(x,msg):
    if not x:raise ValueError(msg)
def hx(x):return "0x%08X"%x
def plugin(p,name):
    s=importlib.util.spec_from_file_location(name,p)
    fail(s and s.loader,"Missing source reader: "+str(p))
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m
def main():
    a=argparse.ArgumentParser()
    for n in ("xbe","v7l","ranges","generated","emitter","v7i_main","v7i_manifest","metadata","local_dossier"):
        a.add_argument("--"+n.replace("_","-"),required=True,type=Path)
    v=a.parse_args()
    fail(v.metadata.resolve()!=v.local_dossier.resolve(),"Local code and shareable metadata paths must differ")
    xbe=v.xbe.read_bytes()
    fail(hashlib.sha256(xbe).hexdigest().upper()==RETAIL,"Retail XBE SHA mismatch")
    prior=json.loads(v.v7l.read_text(encoding="utf-8-sig"))
    fail(prior.get("status")=="K1_V7L_EXACT_RETAIL_FIVE_FUNCTION_X86_WITNESS_SOURCE_ONLY" and
         prior.get("retail_sha256")==RETAIL and
         prior.get("count")==5,"Wrong V7L input")
    prior_by_va={int(x["address"],16):x for x in prior["targets"]}
    fail(set(prior_by_va)==set(TARGETS),"Unexpected V7L function set")
    v7i_hash=hashlib.sha256(v.v7i_main.read_bytes()).hexdigest()
    manifest=json.loads(v.v7i_manifest.read_text(encoding="utf-8-sig"))
    fail(manifest.get("source_sha256")==v7i_hash and
         prior.get("v7i_source_sha256")==v7i_hash,"V7I source identity changed")
    base=plugin(Path(__file__).with_name("Audit-K1V7LRetailFiveX86.py"),"v7m_retail")
    reader=plugin(v.emitter,"v7m_emitter")
    sections=base.sections(xbe)
    ranges,byname=reader.load_ranges(v.ranges)
    sources=reader.load_generated(v.generated,byname)
    fail(len(sources)>10000,"Incomplete original generated C")
    engine=Cs(CS_ARCH_X86,CS_MODE_32)
    engine.detail=True
    results=[]
    private=["LOCAL-ONLY ORIGINAL RETAIL X86 AND GENERATED SOURCE","DO NOT COMMIT; PRIVATE DISASSEMBLY AND SOURCE",""]
    for va in TARGETS:
        rec=ranges.get(va)
        fail(rec and rec["end"]>va,"Missing original range "+hx(va))
        data=base.extract(xbe,sections,va,rec["end"]-va)
        fail(hashlib.sha256(data).hexdigest()==prior_by_va[va]["retail_function_sha256"],
             "XBE slice does not match earlier V7L proof "+hx(va))
        seq=list(engine.disasm(data,va))
        fail(sum(i.size for i in seq)==len(data),"Incomplete linear decoding "+hx(va))
        starts={i.address for i in seq}
        direct_calls=[]
        internal_branches=[]
        external_branches=[]
        indirection=[]
        exits=[]
        for i in seq:
            if i.group(CS_GRP_RET):
                exits.append({"address":hx(i.address),"instruction":i.mnemonic+" "+i.op_str})
            if i.group(CS_GRP_JUMP) or i.group(CS_GRP_CALL):
                immediate=(i.operands[0].imm & 0xffffffff) if i.operands and i.operands[0].type==X86_OP_IMM else None
                if immediate is None:
                    indirection.append({"address":hx(i.address),"opcode":i.mnemonic})
                elif i.group(CS_GRP_CALL):
                    direct_calls.append({"site":hx(i.address),"target":hx(immediate),
                                         "target_is_original_range":immediate in ranges})
                elif va<=immediate<rec["end"]:
                    internal_branches.append({"site":hx(i.address),"target":hx(immediate),
                        "target_on_linear_instruction_start":immediate in starts})
                else:
                    external_branches.append({"site":hx(i.address),"target":hx(immediate)})
        source=sources.get(va,{}).get("source","")
        masked=reader.mask_noncode(source)
        direct_source_calls=sorted(set(re.findall(r"\bsub_([0-9A-Fa-f]{8})\s*\(",masked)))
        result={
            "va":hx(va),"original_bytes":len(data),"instruction_count":len(seq),
            "source_generated":bool(source),"source_file":sources.get(va,{}).get("file"),
            "compiled_in_v7i":False if va!=0x00288F80 else False,
            "ret_sites":exits,"direct_calls":direct_calls,
            "internal_branches":internal_branches,
            "external_branches":external_branches,
            "indirect_control_transfer_sites":indirection,
            "branch_to_non_linear_start_count":sum(not t["target_on_linear_instruction_start"] for t in internal_branches),
            "generated_source_direct_callees":["0x"+x.upper() for x in direct_source_calls],
            "manual_abi_gate_required":True,
            "raw_original_bytes_exported":False,
        }
        results.append(result)
        private.append("======== "+hx(va)+" ORIGINAL X86 ("+str(len(seq))+" linear insns) ========")
        private.extend("%08X  %-10s %s"%(i.address,i.mnemonic,i.op_str) for i in seq)
        if source:
            private.append("======== "+hx(va)+" ORIGINAL GENERATED C ========")
            private.append(source)
        private.append("")
    out={
        "status":"K1_V7M_RETAIL_FIVE_LOCAL_CONTROL_FLOW_ABI_DOSSIER",
        "retail_sha256":RETAIL,"v7i_source_sha256":v7i_hash,
        "v7l_report_sha256":hashlib.sha256(v.v7l.read_bytes()).hexdigest(),
        "functions":results,
        "limits":["Linear instruction sweep is not proof of full CFG",
                  "Callsite recognition and return immediates are offline candidates, not runtime ABI proof",
                  "No direct automatic source lifting or unsafe callback admission",
                  "Original x86 listings are intentionally local-only"],
        "xdk_build":False,"xbox_run":False}
    for path in (v.metadata,v.local_dossier):path.parent.mkdir(parents=True,exist_ok=True)
    v.metadata.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    v.local_dossier.write_text("\n".join(private)+"\n",encoding="utf-8")
    print("[K1-V7M] VERIFIED retail XBE + V7L five spans + V7I source SHA")
    for x in results:
        print("[K1-V7M] %s insns=%d calls=%d internal_branches=%d invalid_linear_branch_sites=%d return_sites=%d indirect=%d generated=%s"%
              (x["va"],x["instruction_count"],len(x["direct_calls"]),
               len(x["internal_branches"]),x["branch_to_non_linear_start_count"],
               len(x["ret_sites"]),len(x["indirect_control_transfer_sites"]),x["source_generated"]))
    print("[K1-V7M] SHAREABLE METADATA: "+str(v.metadata))
    print("[K1-V7M] LOCAL-ONLY SOURCE/DISASSEMBLY: "+str(v.local_dossier))
    print("[K1-V7M] NO XDK / NO XBOX / NO GAME BYTES IN SHAREABLE JSON")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7M] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
