#!/usr/bin/env python3
"""V7T: prove exact retail FS prefix at startup TLS access 0x2295FB.

Read-only, bound to known-good original retail SHA + V7I source identity.
Reports whether ordinary low-address guest memory matches original FS-relative
access, but never assumes the equivalence is correct without TIB evidence.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
from capstone import Cs,CS_ARCH_X86,CS_MODE_32
from capstone.x86_const import X86_REG_FS,X86_OP_MEM
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def h(x):return "0x%08X"%x
def main():
    p=argparse.ArgumentParser()
    for n in ("xbe","v7i_main","manifest","generated","out"):
        p.add_argument("--"+n.replace("_","-"),type=Path,required=True)
    a=p.parse_args()
    raw=a.xbe.read_bytes()
    need(hashlib.sha256(raw).hexdigest().upper()==SHA,"Retail XBE hash mismatch")
    vb=a.v7i_main.read_bytes()
    m=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    need(m.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY" and
         m.get("source_sha256")==hashlib.sha256(vb).hexdigest(),
         "V7I source identity mismatch")
    import importlib.util
    base=Path(__file__).with_name("Audit-K1V7LRetailFiveX86.py")
    spec=importlib.util.spec_from_file_location("v7t_xbe",base)
    need(spec and spec.loader,"V7L exact XBE reader missing")
    reader=importlib.util.module_from_spec(spec);spec.loader.exec_module(reader)
    ss=reader.sections(raw)
    va=0x002295FB
    blob=reader.extract(raw,ss,va,0x00229622-va)
    cs=Cs(CS_ARCH_X86,CS_MODE_32);cs.detail=True
    seq=list(cs.disasm(blob,va))
    need(sum(i.size for i in seq)==len(blob),"Retail TLS block failed complete decode")
    fs=[]
    for ins in seq:
        for op in ins.operands:
            if op.type==X86_OP_MEM and op.mem.segment==X86_REG_FS:
                fs.append({"address":h(ins.address),"opcode":ins.mnemonic,
                           "operand":ins.op_str,
                           "fs_displacement":h(op.mem.disp&0xffffffff)})
    src=a.generated.read_text(encoding="utf-8",errors="replace")
    expected=[
        "eax = GUEST_READ32(0x28);",
        "edi = GUEST_READ32(4);",
        "edx = GUEST_READ32(0x869118);",
        "edx = GUEST_READ32(edi + edx * 4);",
    ]
    need(all(src.count(x)>=1 for x in expected),"Generated TLS block source changed")
    need(any(x["fs_displacement"]=="0x00000028" for x in fs) and
         any(x["fs_displacement"]=="0x00000004" for x in fs),
         "Expected FS4/FS28 prefix missing in original XBE")
    out={
        "stage":"K1_V7T_EXACT_RETAIL_TLS_FS_PREFIX_WITNESS",
        "retail_sha256":SHA,
        "v7i_sha256":hashlib.sha256(vb).hexdigest(),
        "retail_block_start":h(va),"retail_block_end":h(va+len(blob)),
        "retail_instructions":len(seq),
        "fs_instructions":fs,
        "translated_low_address_reads_verified":True,
        "segment_semantics_equivalence_proven":False,
        "requires":"V7I guest low-address TIB memory initialization and segment-base equivalence check",
        "changed_source":False,"xdk":False,"xbox":False,
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(out,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7T] RETAIL SHA + V7I SHA PASS")
    for i in fs:
        print("[K1-V7T] FS PREFIX %s %s %s"%(i["address"],i["opcode"],i["operand"]))
    print("[K1-V7T] Generated source has plain GUEST_READ32(4)/GUEST_READ32(0x28)")
    print("[K1-V7T] FS-to-guest-low-memory equivalence NOT PROVEN; no patch authorized")
    print("[K1-V7T] METADATA "+str(a.out))
    print("[K1-V7T] NO XDK / NO XBOX")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7T] HARD FENCE "+str(e),file=sys.stderr);sys.exit(1)
