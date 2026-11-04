#!/usr/bin/env python3
"""K1-R10: discover retail ordinal-219 import references; no ABI modifications."""
import argparse
import hashlib
import json
import struct
from pathlib import Path

EXPECTED = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
THUNK = 0x800000DB

def word(blob, offset):
    if offset < 0 or offset + 4 > len(blob):
        raise ValueError("Original XBE access out of bounds")
    return struct.unpack_from("<I", blob, offset)[0]

def sections(blob):
    base = word(blob, 0x104)
    count = word(blob, 0x11c)
    table = word(blob, 0x120) - base
    if base != 0x10000 or not 1 <= count <= 64 or table < 0 or table + 56*count > len(blob):
        raise ValueError("Unsupported original XBE section layout")
    result=[]
    for i in range(count):
        header=table+56*i
        va,virtual,raw,size=(word(blob,header+k) for k in (4,8,12,16))
        if size and (raw+size > len(blob) or virtual > 0x20000000):
            raise ValueError("Invalid original section bounds")
        result.append(dict(index=i,va=va,virtual=virtual,raw=raw,size=size))
    return result

def audit(blob, parts):
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
        from capstone.x86_const import X86_OP_MEM, X86_REG_INVALID
    except ImportError as ex:
        raise ValueError("Install capstone: python -m pip install capstone") from ex
    slots=set()
    for s in parts:
        for delta in range(0,max(0,min(s["size"],s["virtual"])-3),4):
            if word(blob,s["raw"]+delta)==THUNK:
                slots.add(s["va"]+delta)
    dis=Cs(CS_ARCH_X86,CS_MODE_32)
    dis.detail=True
    calls=[]
    references=[]
    scanned=0
    for s in parts:
        lo=max(s["va"],0x00011000)
        hi=min(s["va"]+min(s["size"],s["virtual"]),0x00255620)
        if hi<=lo:
            continue
        start=s["raw"]+lo-s["va"]
        instructions=list(dis.disasm(blob[start:start+hi-lo],lo))
        scanned+=len(instructions)
        for idx,ins in enumerate(instructions):
            refs=[]
            for op in ins.operands:
                if (op.type==X86_OP_MEM and op.mem.base==X86_REG_INVALID
                    and op.mem.index==X86_REG_INVALID
                    and (op.mem.disp & 0xffffffff) in slots):
                    refs.append("%08X"%(op.mem.disp & 0xffffffff))
            if not refs:
                continue
            record={"va":"%08X"%ins.address,"insn":ins.mnemonic+" "+ins.op_str,
                    "iat_slots":refs,
                    "nearby":[{"va":"%08X"%x.address,"insn":x.mnemonic+" "+x.op_str}
                              for x in instructions[max(0,idx-16):idx+5]]}
            if ins.mnemonic in ("call","jmp"):
                calls.append(record)
            else:
                references.append(record)
    return {"ordinal":219,"thunk":"800000DB","iat_slots":["%08X"%x for x in sorted(slots)],
            "instructions_scanned":scanned,
            "call_candidates":calls[:40],"other_references":references[:40],
            "call_total":len(calls),"other_total":len(references),
            "proof_limits":["An import slot is not runtime callsite provenance",
                            "Register-indirect calls and ambiguous disassembly may be missed",
                            "No matching call is not proof of an alternate ABI"]}

def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--retail-xbe",type=Path,required=True)
    parser.add_argument("--output",type=Path,required=True)
    args=parser.parse_args()
    blob=args.retail_xbe.read_bytes()
    if hashlib.sha256(blob).hexdigest().upper()!=EXPECTED:
        raise ValueError("Retail XBE SHA-256 mismatch")
    result=audit(blob,sections(blob))
    report={"status":"K1_R10_READONLY_RETAIL_IMPORT_REFERENCE_AUDIT",
            "retail_sha256":EXPECTED,"results":result,
            "abi_proven":False,"xdk_build":False,"xbox_run":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("[K1-R10] RETAIL SHA PASS; READ-ONLY IMPORT AUDIT")
    print("[K1-R10] Ordinal-219 IAT slots:",len(result["iat_slots"]))
    print("[K1-R10] Direct call/jmp candidates:",result["call_total"])
    print("[K1-R10] Other instruction references:",result["other_total"])
    for record in result["call_candidates"][:5]:
        print("[K1-R10] candidate",record["va"],record["insn"])
    if result["call_total"]==0:
        print("[K1-R10] No direct callsite proven; ABI remains fenced")
    print("[K1-R10] Report:",args.output)
    print("[K1-R10] NO XDK, XEX, XBOX RUN, OR ABI CHANGE")

if __name__=="__main__":
    main()
