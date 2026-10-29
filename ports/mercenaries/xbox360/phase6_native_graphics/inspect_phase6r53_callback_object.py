#!/usr/bin/env python3
"""Phase 6R53 zero-build forensic audit: 00041D88 callback vs DSOUND object.

R51: [02490364] -> 00041D88; F78F read [00041D94] -> EC83F0E4.
R52: sub_00041D90 is a real translated executable function. 00041D88
is eight bytes earlier, and one translated site sets ECX = 0x41D90.
Determine how the value entered object+8 before making any repair.
No mutation, MMIO relaxation, output poisoning, or build.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TEXT_END=0x0025561C
BASES=(0x00041C50,0x00041D90,0x0029F72A)
LITERALS=(
 "0x41D90", "0x00041D90", "0x41D88", "0x00041D88",
 "0x41D80", "0x00041D80", "0x41D94", "0x00041D94",
)
CALLS=(
 "sub_0029F72A();",
 "sub_0029F78F();",
 "sub_00041D90();",
)
MAXBODY=220
MAXOWNERS=16

def brief_body(row,center=None,before=35,after=35,limit=MAXBODY):
    lines=row["body"].splitlines()
    if center is not None:
        lo=max(0,center-before)
        hi=min(len(lines),center+after+1)
    else:
        lo=0;hi=min(len(lines),limit)
    print("="*100)
    print(f"[Phase6R53] owner={row['name']} va={row['va']:08X} total_lines={len(lines)}")
    if lo:
        print(f"[Phase6R53] ... skipped {lo} earlier lines")
    for i in range(lo,hi):
        marker=">>" if center is not None and i==center else "  "
        print(f"[Phase6R53] {marker} {i+1:04d}: {lines[i]}")
    if hi<len(lines):
        print(f"[Phase6R53] ... omitted {len(lines)-hi} following lines")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R53] source not found: {args.source}")
    data=args.source.read_text(encoding="utf-8",errors="replace")
    rows=functions(data)
    by_va={r["va"]:r for r in rows}
    print("[Phase6R53] EXACT SOURCE PROVENANCE: 00041D88 / 00041D90")
    print(f"[Phase6R53] source={args.source} translated_bodies={len(rows)}")
    print("[Phase6R53] R51: 0029F78F [edi+8]=00041D88 then [ecx+0C]=EC83F0E4")
    print("[Phase6R53] R52: sub_00041D90 exists, exact 00041D88 function absent")
    print("[Phase6R53] Distinguish valid callback/descriptor layout from guest pointer corruption")
    print("[Phase6R53] source_only=YES mutation=NO build=NO Xbox_run=NO")
    print("[Phase6R53] CANDIDATE SOURCE AND FUNCTION BODIES")
    for va in BASES:
        row=by_va.get(va)
        if row is None:
            print(f"[Phase6R53] no generated function sub_{va:08X}")
        else:
            brief_body(row)
    print("="*100)
    print("[Phase6R53] EXECUTABLE ADDRESS REFERENCE OWNERS")
    unique={}
    for row in rows:
        if row["va"] in BASES: continue
        body=row["body"]
        keys=[term for term in LITERALS if term in body]
        if not keys: continue
        unique[row["va"]]=(row,keys)
    print(f"[Phase6R53] owner_count={len(unique)}")
    for i,(va,(row,keys)) in enumerate(sorted(unique.items())):
        print(f"[Phase6R53] candidate_owner={row['name']} va={va:08X} refs={','.join(keys)}")
        if i>=MAXOWNERS:
            print("[Phase6R53] remaining candidate owner bodies not displayed")
            continue
        lines=row["body"].splitlines()
        sites=[j for j,line in enumerate(lines) if any(term in line for term in LITERALS)]
        for site in sites[:5]:
            brief_body(row,site,before=24,after=32)
    print("="*100)
    print("[Phase6R53] DIRECT CALLER CONTEXT")
    for target in CALLS:
        callers=[]
        for row in rows:
            for i,line in enumerate(row["body"].splitlines()):
                if target in line:
                    callers.append((row,i))
        print(f"[Phase6R53] target={target} direct_callers={len(callers)}")
        for row,site in callers[:9]:
            brief_body(row,site,before=17,after=15)
    print("="*100)
    print("[Phase6R53] DSOUND writes to +8 and callback-shaped fields")
    count=0
    patt=re.compile(r"(?:phase6ch_apu_write32|GUEST_WRITE32)\(([^,]+),\s*(.+)\);")
    for row in rows:
        if not (0x0029CB80<=row["va"]<0x002BB280):
            continue
        lines=row["body"].splitlines()
        for i,line in enumerate(lines):
            m=patt.search(line)
            if m and (re.search(r"\+\s*(?:8|0x8)\s*$",m.group(1)) or
                      any(term in m.group(2) for term in LITERALS)):
                count+=1
                print(f"[Phase6R53] DSOUND write owner={row['name']} line={i+1}: {line.strip()}")
                if count<=14:brief_body(row,i,before=10,after=9)
    print(f"[Phase6R53] DSOUND matched writes={count}")
    print("[Phase6R53] AUDIT COMPLETE: preserve hard fence; require producer-side proof for any runtime fix")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
