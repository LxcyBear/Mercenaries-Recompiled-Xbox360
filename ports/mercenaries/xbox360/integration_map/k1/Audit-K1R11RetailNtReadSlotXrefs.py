#!/usr/bin/env python3
"""K1-R11: source-only retail NtReadFile slot address xrefs and pointer chain."""
import argparse,hashlib,json,struct
from pathlib import Path

SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"

def u32(b,o):
    if o<0 or o+4>len(b): raise ValueError("XBE u32 out of bounds")
    return struct.unpack_from("<I",b,o)[0]

def xbe_sections(b):
    base,n,table=u32(b,0x104),u32(b,0x11c),u32(b,0x120)
    if base!=0x10000 or not 1<=n<=64: raise ValueError("XBE section metadata invalid")
    table-=base
    if table<0 or table+56*n>len(b): raise ValueError("XBE section table not mapped")
    out=[]
    for i in range(n):
        h=table+56*i
        va,virtual,raw,size=(u32(b,h+x) for x in (4,8,12,16))
        if raw+size>len(b): raise ValueError("XBE section file range invalid")
        out.append(dict(id=i,va=va,virtual=virtual,raw=raw,size=size))
    return out

def find_literal(b,ss,target):
    needle=struct.pack("<I",target)
    out=[]
    for s in ss:
        area=b[s["raw"]:s["raw"]+s["size"]]
        at=0
        while True:
            pos=area.find(needle,at)
            if pos<0: break
            out.append({"va":"%08X"%(s["va"]+pos),"section":s["id"],
                        "raw_offset":s["raw"]+pos,
                        "aligned":pos%4==0})
            at=pos+1
    return out

def instruction_refs(b,ss,slot):
    from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_INVALID
    d=Cs(CS_ARCH_X86,CS_MODE_32)
    d.detail=True
    hits=[]; count=0
    for s in ss:
        lo=max(0x11000,s["va"])
        hi=min(0x255620,s["va"]+min(s["size"],s["virtual"]))
        if lo>=hi: continue
        start=s["raw"]+lo-s["va"]
        insns=list(d.disasm(b[start:start+hi-lo],lo))
        count+=len(insns)
        for j,i in enumerate(insns):
            reasons=[]
            for op in i.operands:
                if op.type==X86_OP_IMM and (op.imm&0xffffffff)==slot:
                    reasons.append("immediate_slot_address")
                elif op.type==X86_OP_MEM and op.mem.base==X86_REG_INVALID and op.mem.index==X86_REG_INVALID and (op.mem.disp&0xffffffff)==slot:
                    reasons.append("absolute_memory_slot")
            if reasons:
                hits.append({"va":"%08X"%i.address,"insn":i.mnemonic+" "+i.op_str,"reasons":reasons,
                  "context":[{"va":"%08X"%x.address,"insn":x.mnemonic+" "+x.op_str}
                  for x in insns[max(0,j-12):j+5]]})
    return {"instructions_scanned":count,"total":len(hits),"hits":hits[:24]}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--retail-xbe",required=True,type=Path)
    p.add_argument("--r10-report",required=True,type=Path)
    p.add_argument("--output",required=True,type=Path)
    a=p.parse_args()
    b=a.retail_xbe.read_bytes()
    if hashlib.sha256(b).hexdigest().upper()!=SHA: raise ValueError("Retail SHA256 mismatch")
    r=json.loads(a.r10_report.read_text(encoding="utf-8-sig"))
    if r.get("retail_sha256")!=SHA or r.get("status")!="K1_R10_READONLY_RETAIL_IMPORT_REFERENCE_AUDIT":
        raise ValueError("Wrong or unverified R10 report")
    slots=r["results"]["iat_slots"]
    if len(slots)!=1: raise ValueError("Expected one proven ordinal-219 IAT slot; stop without guessing")
    slot=int(slots[0],16)
    ss=xbe_sections(b)
    result={
      "status":"K1_R11_RETAIL_NTREAD_SLOT_ADDRESS_XREF_ONLY",
      "retail_sha256":SHA,"import_slot":"%08X"%slot,
      "literal_slot_address_occurrences":find_literal(b,ss,slot),
      "literal_thunk_value_occurrences":find_literal(b,ss,0x800000DB),
      "x86_slot_address_references":instruction_refs(b,ss,slot),
      "limits":["Callsite not proven without instruction context and runtime provenance",
                "Register-indirect and generated dispatch aliases can evade static literal scan",
                "Linear disassembly can miss valid instruction streams",
                "No kernel ABI or stack accounting modified"],
      "abi_proven":False,"xdk_build":False,"xbox_run":False}
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("[K1-R11] RETAIL VERIFIED, READ-ONLY XREF PASS")
    print("[K1-R11] NtReadFile IAT slot:",result["import_slot"])
    print("[K1-R11] Literal slot address occurrences:",len(result["literal_slot_address_occurrences"]))
    print("[K1-R11] x86 slot references:",result["x86_slot_address_references"]["total"])
    print("[K1-R11] Literal thunk value occurrences:",len(result["literal_thunk_value_occurrences"]))
    for hit in result["x86_slot_address_references"]["hits"][:5]:
        print("[K1-R11] candidate",hit["va"],hit["insn"])
    print("[K1-R11] Report:",a.output)
    print("[K1-R11] NO XDK, NO XEX, NO HARDWARE RUN, NO ABI CHANGE")
if __name__=="__main__": main()
