#!/usr/bin/env python3
"""Phase 6R61: source-only, full DirectSound sub_0029F0C6 status provenance.

R60 isolated F495 as an argument-shuffling wrapper:
    0029FC4A -> 0029F495 -> 0029F0C6
R59 hardware showed F495 returning EAX=8007000E after F992=00000000.
That HRESULT is E_OUTOFMEMORY but no failed allocation has been proven.
This bounded static report focuses on F0C6's complete translated body,
its first-hop dependencies, and every status/return/branch/call gate. It
does not modify generated source, overwrite binaries or perform an XDK build.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

FOCUS=0x0029F0C6
CHILD_LIMIT=20
SOURCE_TAG="P6DQ R59 FC4A ABI RESTORE:"
INTEREST=re.compile(
    r"(?i)(0x8007000E|0x80004005|0xC0000017|0x7FF8FFF2|"
    r"Allocate|Free|QueryPool|PUSH32|POP32|sub_[0-9a-f]{8}\(\)|"
    r"PHASE6DJ_ICALL_SAFE|phase4c_direct_frontier|GUEST_READ|GUEST_WRITE|"
    r"phase6ch_apu_(?:read|write)|if \(|goto |eax =|ebx =|esi =|edi =)"
)

def dump(row, *, center=None, pre=9, post=15, max_lines=175):
    lines=row["body"].splitlines()
    lo,hi=(0,min(len(lines),max_lines)) if center is None else (
        max(0,center-pre),min(len(lines),center+post+1))
    print("="*104)
    print(f"[Phase6R61] BODY {row['name']} va={row['va']:08X} lines={len(lines)} shown={lo+1}..{hi}")
    for j in range(lo,hi):
        print(f"[Phase6R61] {'>>' if j==center else '  '} {j+1:04d}: {lines[j]}")
    if hi<len(lines):
        print(f"[Phase6R61] omitted_lines={len(lines)-hi}")

def children(row):
    out=[]
    for a,b in re.findall(
        r"(?:sub_([0-9a-fA-F]{8})\(\)|phase4c_direct_frontier\(0x([0-9a-fA-F]{8})u?\))",
        row["body"]
    ):
        va=int(a or b,16)
        if va!=row["va"] and va not in out:
            out.append(va)
    return out

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",required=True,type=Path)
    args=parser.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R61] source missing: {args.source}")
    src=args.source.read_text(encoding="utf-8",errors="replace")
    if SOURCE_TAG not in src:
        raise SystemExit("[Phase6R61] expected R59/TrueTU monolithic overlay")
    rows=functions(src)
    byva={r["va"]:r for r in rows}
    mainrow=byva.get(FOCUS)
    if not mainrow:
        raise SystemExit("[Phase6R61] No translated sub_0029F0C6 body")
    print("[Phase6R61] ==================================================")
    print("[Phase6R61]     REAL F495->F0C6 NEGATIVE STATUS AUDIT")
    print("[Phase6R61] ==================================================")
    print(f"[Phase6R61] source={args.source} translated={len(rows)}")
    print("[Phase6R61] R59 hardware: F992=00000000 F495=8007000E; ticks=27027014")
    print("[Phase6R61] R60: sub_0029F495 wrapper only calls sub_0029F0C6")
    print("[Phase6R61] 8007000E is not proof of real memory exhaustion")
    print("[Phase6R61] 0 source changes, 0 translated regeneration, 0 XDK/XEX build")
    print("[Phase6R61] 1/4 COMPLETE 0029F0C6 FUNCTION")
    dump(mainrow,max_lines=300)
    print("[Phase6R61] 2/4 F0C6 IMMEDIATE CHILDREN")
    direct=children(mainrow)
    print(f"[Phase6R61] direct_callees={len(direct)} " +
          " ".join(f"sub_{x:08X}" for x in direct))
    for va in direct[:CHILD_LIMIT]:
        row=byva.get(va)
        if not row:
            print(f"[Phase6R61] CHILD sub_{va:08X}: NOT TRANSLATED")
            continue
        lines=row["body"].splitlines()
        print(f"[Phase6R61] CHILD sub_{va:08X} body_lines={len(lines)} " +
              f"second_hop={','.join(f'{v:08X}' for v in children(row)[:10])}")
        if len(lines)<=115:
            dump(row,max_lines=115)
            continue
        selected=[
            i for i,l in enumerate(lines) if
            "0x8007000E" in l or "0xC0000017" in l or "0x80004005" in l or
            "Allocate" in l or "PHASE6DJ_ICALL_SAFE" in l or
            "ExAllocatePool" in l or "MmAllocate" in l
        ]
        for i in selected[:9]:
            dump(row,center=i,pre=7,post=11)
        if not selected:
            print(f"[Phase6R61] CHILD sub_{va:08X} no obvious allocator/status literal")
    if len(direct)>CHILD_LIMIT:
        print(f"[Phase6R61] elided_child_count={len(direct)-CHILD_LIMIT}")
    print("[Phase6R61] 3/4 REGISTER / RETURN PROVENANCE IN F0C6")
    lines=mainrow["body"].splitlines()
    for i,line in enumerate(lines):
        if INTEREST.search(line):
            print(f"[Phase6R61] F0C6 {i+1:04d}: {line.strip()}")
    print("[Phase6R61] 4/4 ORIGINAL CALLSITE 0029F495")
    wrapper=byva.get(0x0029F495)
    if wrapper:
        dump(wrapper,max_lines=75)
    else:
        print("[Phase6R61] Missing F495 wrapper")
    print("[Phase6R61] NEXT: choose the single negative-result producer/branch to instrument on hardware.")
    print("[Phase6R61] Do not force success, suppress teardown, fake allocations or defeat guest memory fences.")
    print("[Phase6R61] AUDIT COMPLETE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
