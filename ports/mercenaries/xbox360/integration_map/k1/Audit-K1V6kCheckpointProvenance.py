#!/usr/bin/env python3
"""V6k root provenance audit. Does not modify, compile, or run game code.

Reports full generated sub_002033E0, the redscene checkpoint call context, helper
helper definitions, and SHA-pinned retail bytes/disassembly. The goal is to
identify precisely which code was added for PC recompilation versus which
retail x86 operations must be preserved on Xbox 360.
"""
from pathlib import Path
import hashlib, re, struct, sys
ROOT=Path.cwd()
TAG="[K1-V6k-REDSCENE]"
GEN=ROOT/"build/phase3n_final_abi_scale/runtime/gen"
XBE=ROOT/"game_files/mercenaries-retail/default.xbe"
REPORT=ROOT/"build/phase6_integration_map/k1_v6k_002033e0_checkpoint_audit.txt"
EXPECTED="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGET=0x002033E0
HELPERS=(
"recomp_redscene_checkpoint",
)
FUNC_RE=re.compile(r"(?m)^void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{.*?^\}",re.S|re.M)

def sha(data): return hashlib.sha256(data).hexdigest()
def require(ok,msg):
    if not ok: raise RuntimeError(msg)

def retail_map(b,va,n):
    require(b[:4]==b"XBEH","not an XBE")
    d=lambda i:struct.unpack_from("<I",b,i)[0]
    base=d(0x104); count=d(0x11C); table=d(0x120)-base
    require(0<count<64 and 0<=table and table+count*0x38<=len(b),"bad XBE sections")
    matching=[]
    for i in range(count):
        h=table+i*0x38
        address,virt,off,raw=d(h+4),d(h+8),d(h+12),d(h+16)
        if address<=va and va+n<=address+min(virt,raw):
            start=off+(va-address)
            if start+n<=len(b):matching.append((i,start))
    require(len(matching)==1,"expected unique raw .text section for 002033E0")
    return matching[0]

def main():
    lines=[]
    def add(*items):lines.extend(str(x) for x in items)
    b=XBE.read_bytes()
    require(sha(b).upper()==EXPECTED,"retail SHA-256 mismatch")
    add("V6K 002033E0 CHECKPOINT PROVENANCE AUDIT","RET: "+EXPECTED,
        "No source/XEX/guest state modified.")
    files=sorted(GEN.glob("recomp_*.c"))
    require(files,"missing generated C corpus")
    owners=[]
    corpus={}
    for p in files:
        s=p.read_text(encoding="utf-8-sig",errors="replace").replace("\r\n","\n")
        corpus[p.name]=s
        for m in FUNC_RE.finditer(s):
            if m.group(1)=="sub_002033E0":
                owners.append((p.name,s[:m.start()].count("\n")+1,m.group(0)))
    require(len(owners)==1,"expected exactly one generated 002033E0 function")
    name,start,body=owners[0]
    add("","GENERATED FUNCTION OWNER: %s:%d"%(name,start),
        "Source SHA-256: "+sha((GEN/name).read_bytes()),
        "Function lines: "+str(len(body.splitlines())),
        "=== FULL TRANSLATED FUNCTION (LINE NUMBERED) ===")
    bodylines=body.splitlines()
    for i,line in enumerate(bodylines):
        add("%6d | %s"%(start+i,line))
    add("","=== CHECKPOINT CALL SITES AND CONTEXT ===")
    for helper in HELPERS:
        hits=[i for i,line in enumerate(bodylines) if re.search(r"\b"+helper+r"\s*\(",line)]
        add(helper+": "+str(len(hits))+" occurrence(s)")
        for i in hits:
            lo=max(0,i-12);hi=min(len(bodylines),i+13)
            add("-- %s:%d context --"%(name,start+i))
            for k in range(lo,hi):add("%6d | %s"%(start+k,bodylines[k]))
    add("","=== ORIGINAL SOURCE CALL/RETURN SITES ===")
    for i,line in enumerate(bodylines):
        if re.search(r"\b(sub_[0-9A-Fa-f]{8}|PHASE4C_BUDGET_TICK|GUEST_READ|GUEST_WRITE)\s*\(",line):
            add("%6d | %s"%(start+i,line))
    add("","=== HELPER DEFINITIONS OR DECLARATIONS (TEXT SEARCH) ===")
    for helper in HELPERS:
        add("-- "+helper+" --")
        count=0
        for filename,source in corpus.items():
            for i,line in enumerate(source.splitlines(),1):
                if helper in line:
                    add("%s:%d %s"%(filename,i,line.strip()[:250]))
                    count+=1
                    if count>=40:break
            if count>=40:break
        add("occurrences shown: "+str(count))
    index,offset=retail_map(b,TARGET,512)
    raw=b[offset:offset+512]
    add("","=== SHA-PINNED RETAIL XBE BYTES ===",
        "section=%d file_offset=0x%08X"%(index,offset))
    for i in range(0,len(raw),16):
        add("0x%08X: %s"%(TARGET+i," ".join("%02X"%x for x in raw[i:i+16])))
    try:
        from capstone import Cs,CS_ARCH_X86,CS_MODE_32
        md=Cs(CS_ARCH_X86,CS_MODE_32)
        add("","=== RETAIL x86 DISASSEMBLY (UP TO 512 BYTES; MAY CROSS FUNCTION BOUNDARY) ===")
        for ins in md.disasm(raw,TARGET):
            add("0x%08X: %-9s %s"%(ins.address,ins.mnemonic,ins.op_str))
            if ins.mnemonic.startswith("ret"):break
    except ImportError:
        add("","Capstone absent: optional retail disasm via 'python -m pip install capstone'.",
            "Raw SHA-verified bytes above remain authoritative.")
    REPORT.parent.mkdir(parents=True,exist_ok=True)
    REPORT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print(TAG+" PASS; retail SHA verified; root found at %s:%d"%(name,start))
    print(TAG+" REPORT: "+str(REPORT))
    print(TAG+" Checkpoint context must be audited before any removal or implementation.")
    print(TAG+" READ-ONLY. NO XDK COMPILE/HARDWARE RUN.")
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print(TAG+" BLOCKED: "+str(exc),file=sys.stderr)
        sys.exit(1)
