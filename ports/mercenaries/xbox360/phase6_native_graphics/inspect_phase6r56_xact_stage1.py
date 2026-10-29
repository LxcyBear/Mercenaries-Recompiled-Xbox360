#!/usr/bin/env python3
"""Phase 6R56: zero-build proof for XACT stage-one 0x81AEC546 failure.

Hardware R51: XACT stage1 sub_0029FDF0 reported 0x81AEC546. The
sub_0027DC5B initializer propagates a negative stage-one result; the
sub_0027F3DC creation wrapper then runs its explicit cleanup branch
and releases the one-ref XACT root. The Release may be CORRECT.
This script audits production of that status without changing runtime.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGETS=(
    0x0027F3DC,
    0x0027DC5B,
    0x0029FDF0,
    0x0027F2C2,
)
STAGE_MARKERS=(
    "sub_0029FDF0();",
    "phase4c_direct_frontier(0x0029FDF0u)",
    "s_phase6dqXactInitStage1Result",
    "loc_0027DD2C",
)
MAX_CALLEES=15
MAX_LINES=420

def show(row,around=None,pre=14,post=18):
    lines=row["body"].splitlines()
    lo=0 if around is None else max(0,around-pre)
    hi=min(len(lines),MAX_LINES) if around is None else min(len(lines),around+post+1)
    print("="*101)
    print(f"[Phase6R56] owner={row['name']} va={row['va']:08X} total_lines={len(lines)} displayed={lo+1}..{hi}")
    for j in range(lo,hi):
        print(f"[Phase6R56] {'>>' if j==around else '  '} {j+1:04d}: {lines[j]}")
    if hi<len(lines):
        print(f"[Phase6R56] remaining_lines={len(lines)-hi}")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R56] Missing source: {args.source}")
    text=args.source.read_text(encoding="utf-8",errors="replace")
    rows=functions(text)
    byva={r["va"]:r for r in rows}
    print("[Phase6R56] XACT STAGE-ONE FAILURE / CLEANUP PROVENANCE")
    print(f"[Phase6R56] source={args.source} bodies={len(rows)}")
    print("[Phase6R56] R51 hardware XACT init stage1_29FDF0=81AEC546")
    print("[Phase6R56] stage2_28345A=00000000 event_count=0 alloc=0 final=81AEC546")
    print("[Phase6R56] after failure: Release(01B5C320) refcount 1->0; root freed")
    print("[Phase6R56] focus is why stage one FAILS, not patching refcount")
    print("[Phase6R56] NO code mutation / NO XEX compilation / NO Xbox run")
    print("[Phase6R56] 1/4 STATUS PRODUCER AND LIFETIME CALL CHAIN")
    for va in TARGETS:
        row=byva.get(va)
        if row is None:
            print(f"[Phase6R56] MISSING GENERATED BODY sub_{va:08X}")
        else:
            show(row)
    print("[Phase6R56] 2/4 STAGE-ONE DIRECT CALLS AND EXIT GATES")
    found=0
    for row in rows:
        matches=[(j,line) for j,line in enumerate(row["body"].splitlines())
                 if any(token in line for token in STAGE_MARKERS)]
        if matches:
            found+=len(matches)
            for j,line in matches[:7]:
                print(f"[Phase6R56] stage_ref={row['name']} line={j+1}: {line.strip()}")
                if row["va"] not in TARGETS:
                    show(row,around=j)
    print(f"[Phase6R56] matching stage refs={found}")

    print("[Phase6R56] 3/4 IMMEDIATE CALLEES OF 0029FDF0")
    stage=byva.get(0x0029FDF0)
    if stage:
        callers=re.findall(
            r"(?:sub_([0-9A-Fa-f]{8})\(\)|phase4c_direct_frontier\(0x([0-9A-Fa-f]{8})u?\))",
            stage["body"])
        ordered=[]
        for a,b in callers:
            val=int(a or b,16)
            if val not in ordered and val!=0x0029FDF0:
                ordered.append(val)
        print(f"[Phase6R56] stage1 direct callees={len(ordered)}")
        for addr in ordered[:MAX_CALLEES]:
            row=byva.get(addr)
            if row:
                print(f"[Phase6R56] STAGE1 CALLEE sub_{addr:08X}")
                show(row)
            else:
                print(f"[Phase6R56] MISSING STAGE1 CALLEE sub_{addr:08X}")
        if len(ordered)>MAX_CALLEES:
            print(f"[Phase6R56] elided callees={len(ordered)-MAX_CALLEES}")

    print("[Phase6R56] 4/4 STATUS CONSTANT / RETURN PATHS")
    patt=re.compile(r"81AEC546|0x8007|0x8000|0x81AE|0xC000|0xFFFFFFFF")
    for va in (0x0029FDF0,0x0027DC5B):
        row=byva.get(va)
        if row is None: continue
        for j,line in enumerate(row["body"].splitlines()):
            if patt.search(line):
                print(f"[Phase6R56] status_candidate={row['name']} line={j+1}: {line.strip()}")
    print("[Phase6R56] AUDIT COMPLETE: verify exact failing status producer / source before patching")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
