#!/usr/bin/env python3
"""Inspect staged R8 NtReadFile bridge and translated TrueTU callsites, read-only."""
import argparse, re, hashlib
from pathlib import Path

def emit_excerpt(path, lines, idx, before=16, after=6):
    lo=max(0,idx-before); hi=min(len(lines),idx+after+1)
    print(f"  {path.name}:{idx+1}")
    for j in range(lo,hi):
        print(f"    {j+1}: {lines[j][:230]}")

def inspect(main, shards):
    if not main.is_file():raise ValueError("R8 generated main.cpp not found")
    files=sorted(shards.glob("translated_???.cpp"))
    if len(files)!=64:raise ValueError(f"Expected 64 original TrueTU shards, got {len(files)}")
    print("[K1-BRIDGE] READ-ONLY R8 NtReadFile call/stack audit")
    ml=main.read_text(encoding="utf-8").splitlines()
    for label,pattern,limit in (
        ("native handler",r"^\s*(?:static\s+)?void\s+phase5h_nt_read_file\(",1),
        ("kernel thunk dispatch",r"_phase4c_target\s*==\s*0x800000DBu",2),
        ("icall macro definition",r"^\s*#define\s+RECOMP_ICALL_SAFE\(",1),
    ):
        hits=[i for i,line in enumerate(ml) if re.search(pattern,line,re.I)]
        print(f"[K1-BRIDGE] main {label} matches={len(hits)}")
        for i in hits[:limit]:
            emit_excerpt(main,ml,i,9,24 if label=="native handler" else 13)
    literal=re.compile(r"(?:0x)?0*2dbd64\b",re.I)
    call=re.compile(r"RECOMP_ICALL_SAFE\s*\(",re.I)
    targets=[]
    direct=[]
    total_calls=0
    for file in files:
        lines=file.read_text(encoding="utf-8").splitlines()
        for i,line in enumerate(lines):
            if literal.search(line):targets.append((file,lines,i))
            if call.search(line):
                total_calls+=1
                context="\n".join(lines[max(0,i-22):i+1])
                if literal.search(context):direct.append((file,lines,i))
    print(f"[K1-BRIDGE] shards={len(files)} all_indirect_calls={total_calls}")
    print(f"[K1-BRIDGE] retail slot 002DBD64 literal references in shards={len(targets)}")
    print(f"[K1-BRIDGE] indirect calls with slot literal in previous 22 source lines={len(direct)}")
    for file,lines,i in targets[:12]:
        print("[K1-BRIDGE] SLOT LITERAL:")
        emit_excerpt(file,lines,i,9,7)
    for file,lines,i in direct[:12]:
        print("[K1-BRIDGE] CALL NEAR SLOT:")
        emit_excerpt(file,lines,i,24,5)
    if not targets:
        print("[K1-BRIDGE] No literal in generated TrueTUs. This is not evidence of missing code: inspect lowered indirect target.")
    print("[K1-BRIDGE] READ ONLY; NO XDK, NO XEX, NO HARDWARE, NO STACK PATCH")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--shards",type=Path,required=True)
    a=p.parse_args()
    inspect(a.main,a.shards)
if __name__=="__main__":main()
