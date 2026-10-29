#!/usr/bin/env python3
"""R60: zero-build audit for the *real* DirectSound 8007000E result.

R59 hardware proves:
  002A19FC corrupted callee-saved EBX (8007000E -> 01B5C554).
  R59 restored the caller state without changing the nested return value.
  0029F992 returned EAX=00000000.
  0029F495 returned EAX=8007000E, propagated from 0029FC4A to
  0029FD83 to XACT; final fault remains EC83F0E4 at tick 27027014.
0x8007000E is E_OUTOFMEMORY, but that does NOT prove true exhaustion.
This report examines F495 branch/returns/callees and local allocation
paths without synthesizing objects, changing HRESULTs or rebuilding.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGETS=[
 (0x0029F495,"DirectSound negative status producer"),
 (0x0029F992,"Immediately preceding successful helper"),
 (0x0029FC4A,"Parent: receives status, controls return"),
 (0x0029FD83,"Caller: propagates failure to XACT"),
 (0x0029FF54,"Previously successful buffer allocation"),
]
FAIL="8007000E"
INTEREST=re.compile(r"(?i)(0x8007000E|8007000E|0x800700|0xC0000017|RtlAllocateHeap|MmAllocate|ExAllocatePool|GUEST_READ32|GUEST_WRITE32|phase6ch_apu_read32|phase6ch_apu_write32|PHASE6DJ_ICALL_SAFE|phase4c_direct_frontier|sub_[0-9a-f]{8}\(\)|goto loc_|if \()")
def print_body(row,center=None,pre=10,post=13,limit=360):
    lines=row["body"].splitlines()
    lo,hi=(0,min(len(lines),limit)) if center is None else (
        max(0,center-pre),min(len(lines),center+post+1))
    print("="*110)
    print(f"[Phase6R60] owner={row['name']} va={row['va']:08X} lines={len(lines)} shown={lo+1}..{hi}")
    for j in range(lo,hi):
        print(f"[Phase6R60] {'>>' if j==center else '  '} {j+1:04d}: {lines[j]}")
    if hi<len(lines):print(f"[Phase6R60] omitted={len(lines)-hi}")

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    args=p.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R60] R59 source missing: {args.source}")
    data=args.source.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in data:
        raise SystemExit("[Phase6R60] Expected R59 overlay, not an R51/R58 source")
    rows=functions(data)
    byva={row["va"]:row for row in rows}
    print("[Phase6R60] REAL DIRECTSOUND 8007000E FAILURE PRODUCER")
    print(f"[Phase6R60] source={args.source} functions={len(rows)}")
    print("[Phase6R60] R59 confirmed: A19FC EBX 8007000E->01B5C554; restored")
    print("[Phase6R60] R59 confirmed: F992 result=00000000; F495 result=8007000E")
    print("[Phase6R60] R59 confirmed: XACT stage1/final=8007000E; ticks=27027014")
    print("[Phase6R60] Treat 8007000E as error-code, NOT proof of real memory exhaustion")
    print("[Phase6R60] No guest fix, no memory-policy change, no XEX build")
    print("[Phase6R60] 1/4 EXACT F495/F992/F C4A / FD83 FUNCTION BODIES")
    for va,purpose in TARGETS:
        print(f"[Phase6R60] TARGET={va:08X} purpose={purpose}")
        row=byva.get(va)
        if row:print_body(row)
        else:print(f"[Phase6R60] MISSING sub_{va:08X}")
    print("[Phase6R60] 2/4 F495 CALLEES AND RETURN/ALLOCATION GUARDS")
    root=byva.get(0x0029F495)
    if root:
        children=[]
        for a,b in re.findall(r"(?:sub_([0-9a-fA-F]{8})\(\)|phase4c_direct_frontier\(0x([0-9a-fA-F]{8})u?\))",root["body"]):
            v=int(a or b,16)
            if v not in children and v!=0x0029F495:children.append(v)
        print(f"[Phase6R60] F495 direct_callees={len(children)} addresses={','.join(f'{x:08X}' for x in children)}")
        for v in children[:20]:
            row=byva.get(v)
            if row is None:
                print(f"[Phase6R60] callee {v:08X}: NOT TRANSLATED")
                continue
            print(f"[Phase6R60] CALLEE sub_{v:08X}")
            lines=row["body"].splitlines()
            if len(lines)<=125:print_body(row,limit=125)
            else:
                for i,line in enumerate(lines):
                    if INTEREST.search(line) and ("0x800700" in line or
                       "0xC0000017" in line or "Allocate" in line or
                       "PHASE6DJ_ICALL_SAFE" in line):
                        print_body(row,i,pre=8,post=11)
    print("[Phase6R60] 3/4 F495 CALLERS / STATUS CONSTANT ASSIGNMENTS")
    calls=0
    for row in rows:
        if row["va"]==0x0029F495:continue
        lines=row["body"].splitlines()
        for i,line in enumerate(lines):
            if "sub_0029F495();" in line or "0x0029F495" in line:
                calls+=1
                print(f"[Phase6R60] F495_CALLER {row['name']} line={i+1} {line.strip()}")
                if calls<=9:print_body(row,i,pre=11,post=18)
    print(f"[Phase6R60] F495 callsites={calls}")
    const_refs=[]
    for row in rows:
        lines=row["body"].splitlines()
        for i,line in enumerate(lines):
            if FAIL in line:
                const_refs.append((row,i,line))
    print(f"[Phase6R60] 8007000E literal occurrences={len(const_refs)}")
    for row,i,line in const_refs[:18]:
        print(f"[Phase6R60] STATUS_CONST {row['name']} line={i+1}: {line.strip()}")
        if row["va"] in (0x0029F495,0x0029FC4A):
            print_body(row,i,pre=11,post=18)
    print("[Phase6R60] 4/4 NEXT HARDWARE PROBE LOCATIONS")
    print("[Phase6R60] Determine EXACT F495 failure branch and status source first")
    print("[Phase6R60] If actual failed allocator: log size, alignment, availability, status, input pointer")
    print("[Phase6R60] If allocation succeeded: investigate caller ABI / stack and status propagation")
    print("[Phase6R60] DO NOT fake successful allocations or suppress XACT cleanup")
    print("[Phase6R60] AUDIT COMPLETE")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
