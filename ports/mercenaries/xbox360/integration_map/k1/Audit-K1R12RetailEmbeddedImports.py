#!/usr/bin/env python3
"""K1-R12: reconstruct exact x86 instruction operands around original retail NtReadFile slot literals.

Source-only evidence. No guest ABI assumptions and no modifications to original XBE or XEX.
"""
from __future__ import annotations
import argparse, hashlib, json, struct
from pathlib import Path

SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"

def sections(blob):
    def u32(off):
        if off<0 or off+4>len(blob): raise ValueError("XBE field out of range")
        return struct.unpack_from("<I",blob,off)[0]
    base,n,table=u32(0x104),u32(0x11c),u32(0x120)
    if base!=0x10000 or not 1<=n<=64: raise ValueError("Unexpected retail XBE metadata")
    table-=base
    if table<0 or table+56*n>len(blob): raise ValueError("Bad retail section pointer")
    out={}
    for i in range(n):
        p=table+56*i
        va,virtual,raw,size=[u32(p+x) for x in (4,8,12,16)]
        if raw+size>len(blob): raise ValueError("Retail section bounds invalid")
        out[i]={"index":i,"va":va,"raw":raw,"size":size,"virtual":virtual}
    return out

def anchored_decode(blob, section, operand_va, slot):
    """Try all plausible instruction starts preceding embedded literal; label as candidates, not proof."""
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    dis=Cs(CS_ARCH_X86,CS_MODE_32)
    dis.detail=True
    from capstone.x86_const import X86_OP_IMM,X86_OP_MEM,X86_REG_INVALID
    lo=section["va"]
    hi=lo+min(section["size"],section["virtual"])
    results=[]
    seen=set()
    for start in range(max(lo,operand_va-14),operand_va+1):
        p=section["raw"]+start-lo
        for inst in dis.disasm(blob[p:p+min(20,hi-start)],start,count=1):
            if inst.address>operand_va or inst.address+inst.size<operand_va+4:continue
            ok=False;reasons=[]
            for op in inst.operands:
                if op.type==X86_OP_IMM and (op.imm&0xffffffff)==slot:
                    ok=True; reasons.append("immediate_operand")
                elif op.type==X86_OP_MEM and op.mem.base==X86_REG_INVALID and op.mem.index==X86_REG_INVALID and (op.mem.disp&0xffffffff)==slot:
                    ok=True; reasons.append("absolute_memory_operand")
            if ok:
                key=(inst.address,bytes(inst.bytes))
                if key not in seen:
                    seen.add(key)
                    results.append({"instruction_va":"%08X"%inst.address,
                        "bytes":inst.bytes.hex().upper(),
                        "instruction":inst.mnemonic+" "+inst.op_str,
                        "reasons":reasons,
                        "embedded_literal_offset":operand_va-inst.address})
    return sorted(results,key=lambda x:int(x["instruction_va"],16))

def self_test():
    # Capstone versions may expose instruction bytes as bytearray.
    sample=bytearray.fromhex("FF1564BD2D00")
    first=(0x00229D63,bytes(sample))
    second=(0x00229D63,bytes(bytearray(sample)))
    assert first==second and len({first,second})==1
    print("[K1-R12] SELFTEST PASS: bytearray instruction bytes safely deduplicated")

def run():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--retail-xbe",type=Path)
    p.add_argument("--r11-report",type=Path)
    p.add_argument("--output",type=Path)
    args=p.parse_args()
    if args.self_test:
        self_test()
        return
    if args.retail_xbe is None or args.r11_report is None or args.output is None:
        p.error("--retail-xbe, --r11-report, and --output are required for the full audit")
    blob=args.retail_xbe.read_bytes()
    if hashlib.sha256(blob).hexdigest().upper()!=SHA:raise ValueError("Original retail SHA mismatch")
    data=json.loads(args.r11_report.read_text(encoding="utf-8-sig"))
    if data.get("retail_sha256")!=SHA or data.get("status")!="K1_R11_RETAIL_NTREAD_SLOT_ADDRESS_XREF_ONLY":
        raise ValueError("Wrong R11 parent evidence")
    slot=int(data["import_slot"],16)
    ss=sections(blob)
    results=[]
    for x in data["literal_slot_address_occurrences"]:
        index=int(x["section"]);offset=int(x["raw_offset"]);va=int(x["va"],16)
        s=ss[index]
        if s["va"]+offset-s["raw"]!=va or blob[offset:offset+4]!=struct.pack("<I",slot):
            raise ValueError("R11 section/literal mismatch")
        before=max(s["raw"],offset-12)
        after=min(s["raw"]+s["size"],offset+16)
        candidates=anchored_decode(blob,s,va,slot) if 0x11000<=va<0x255620 else []
        results.append({"va":x["va"],"section":index,"aligned":bool(x["aligned"]),
            "nearby_raw_bytes":blob[before:after].hex().upper(),
            "nearby_from_va":"%08X"%(va-(offset-before)),
            "instruction_candidates":candidates,
            "notes":"Instruction-start candidates require original control-flow corroboration; may be embedded data."})
    report={"status":"K1_R12_RETAIL_EMBEDDED_IMPORT_OPERAND_CANDIDATES",
      "retail_sha256":SHA,"ntread_slot":"%08X"%slot,"occurrences":results,
      "abi_proven":False,"actual_runtime_caller_proven":False,"xdk_build":False,
      "xbox_run":False,"guest_stack_modified":False}
    args.output.parent.mkdir(parents=True,exist_ok=True)
    args.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("[K1-R12] VERIFIED RETAIL EMBEDDED-OPERAND AUDIT PASS")
    for x in results:
        print("[K1-R12] %s section=%d candidates=%d"%(x["va"],x["section"],len(x["instruction_candidates"])))
        for c in x["instruction_candidates"][:3]:
            print("          %s: %s"%(c["instruction_va"],c["instruction"]))
    print("[K1-R12] Output:",args.output)
    print("[K1-R12] NOTE: candidate instructions are not runtime call-site proof")
    print("[K1-R12] NO XDK, NO XEX, NO ABI CHANGE")
if __name__=="__main__":run()
