#!/usr/bin/env python3
"""Phase 6R57: zero-build DirectSound stage-one exact return-producer audit.

R51 hardware: XACT sub_0027DC5B receives 0x81AEC546 from sub_0029FDF0
and aborts init. R56 proved FDF0 passes through the result from FD83.
FD83 has two paths: existing global 002BB098 -> A41EE; or allocate
a 0x2C-byte object -> CF0B -> FC4A, returning ESI from this path.
This audit displays the producer bodies and callsite contexts. It cannot
establish which runtime branch ran and does NOT modify Xbox behavior.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGETS=(
 (0x0029FD83, "DirectSound stage-one result owner / existing vs new branch"),
 (0x002A41EE, "Existing audio object call"),
 (0x0029CB9F, "0x2C-byte object allocator"),
 (0x0029CF0B, "New audio object constructor"),
 (0x0029FC4A, "New audio object initialization / negative status candidate"),
 (0x0029FDF0, "Caller propagates FD83 result to XACT"),
)
CALLEE_SOURCE=(0x0029FC4A,0x0029CF0B)
MAXBODY=420
MAXCALLEES=14
KEYWORDS=("0x2BB098", "0x002BB098", "81AEC546", "0x81AEC546")
CONTROL=("if (","goto ","eax =","esi =","edi =","PHASE6DJ_ICALL_SAFE","GUEST_READ32","phase6ch_apu_read32")

def print_body(row,center=None,pre=17,post=23,cap=MAXBODY):
    lines=row["body"].splitlines()
    if center is None:
        lo,hi=0,min(len(lines),cap)
    else:
        lo,hi=max(0,center-pre),min(len(lines),center+post+1)
    print("="*112)
    print(f"[Phase6R57] FUNCTION {row['name']} va={row['va']:08X} lines={len(lines)} shown={lo+1}..{hi}")
    for i in range(lo,hi):
        marker=">>" if i==center else "  "
        print(f"[Phase6R57] {marker} {i+1:04d}: {lines[i]}")
    if hi<len(lines):
        print(f"[Phase6R57] remaining_lines={len(lines)-hi}")

def main()->int:
    parser=argparse.ArgumentParser()
    parser.add_argument("--source",type=Path,required=True)
    args=parser.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R57] MISSING GENERATED SOURCE: {args.source}")
    src=args.source.read_text(encoding="utf-8",errors="replace")
    rows=functions(src)
    byva={r["va"]:r for r in rows}
    print("[Phase6R57] DIRECTSOUND STAGE-ONE / 81AEC546 RETURN-PRODUCER AUDIT")
    print(f"[Phase6R57] source={args.source} translated_functions={len(rows)}")
    print("[Phase6R57] R51: XACT stage1 result 81AEC546; stage2 never reached")
    print("[Phase6R57] R56: sub_0029FDF0 delegates status to sub_0029FD83")
    print("[Phase6R57] Candidate paths: global 002BB098 existing object vs new allocation 0x2C")
    print("[Phase6R57] STATUS VALUE IS NOT PROVEN TO BE A VALID HRESULT")
    print("[Phase6R57] SAFE: no code mutation, no XDK build, no guest fault bypass")
    print("[Phase6R57] 1/4 EXACT PRODUCER FUNCTION BODIES")
    for va,label in TARGETS:
        print(f"[Phase6R57] TARGET sub_{va:08X}: {label}")
        row=byva.get(va)
        if row is None:
            print(f"[Phase6R57] NOT GENERATED: sub_{va:08X}")
        else:
            print_body(row)
    print("[Phase6R57] 2/4 SECOND-HOP CALLEES WITH STATUS/ERROR BRANCHES")
    for va in CALLEE_SOURCE:
        row=byva.get(va)
        if not row:continue
        children=[]
        for a,b in re.findall(r"(?:sub_([0-9a-fA-F]{8})\(\)|phase4c_direct_frontier\(0x([0-9a-fA-F]{8})u?\))",row["body"]):
            value=int(a or b,16)
            if value not in children and value!=va:
                children.append(value)
        print(f"[Phase6R57] parent=sub_{va:08X} child_count={len(children)} child_VAs={','.join(f'{x:08X}' for x in children)}")
        for child in children[:MAXCALLEES]:
            row2=byva.get(child)
            if row2 is None:
                print(f"[Phase6R57] child_sub_{child:08X}=MISSING")
                continue
            lines=row2["body"].splitlines()
            candidates=[(i,line) for i,line in enumerate(lines) if
                        ("0x8007" in line or "0x81AE" in line or "0xC000" in line or
                         ("return;" in line and "ret" in line))]
            print(f"[Phase6R57] child={row2['name']} body_lines={len(lines)} status_or_return_sites={len(candidates)}")
            if len(lines)<=115:print_body(row2)
            else:
                for i,_ in candidates[:6]:
                    print_body(row2,i,pre=14,post=12)
    print("[Phase6R57] 3/4 GLOBAL 002BB098 / EXACT FAILURE VALUE REFERENCERS")
    tally={word:0 for word in KEYWORDS}
    matches={word:[] for word in KEYWORDS}
    for row in rows:
        for i,line in enumerate(row["body"].splitlines()):
            for word in KEYWORDS:
                if word in line:
                    tally[word]+=1
                    if len(matches[word])<13:
                        matches[word].append((row,i,line))
    for word in KEYWORDS:
        print(f"[Phase6R57] needle={word} count={tally[word]}")
        for row,i,line in matches[word]:
            print(f"[Phase6R57]   owner={row['name']} line={i+1}: {line.strip()[:200]}")
            if row["va"] not in {x for x,_ in TARGETS}:
                print_body(row,i,pre=10,post=12)
    print("[Phase6R57] 4/4 SUMMARY: INSTRUMENTATION SITES TO PROVE ON HARDWARE")
    print("[Phase6R57] probe A: enter FD83; global 002BB098 value")
    print("[Phase6R57] probe B: return from A41EE on existing-object branch")
    print("[Phase6R57] probe C: return from CB9F allocator; CF0B constructor")
    print("[Phase6R57] probe D: return from FC4A initialization; FD83 final status")
    print("[Phase6R57] Do NOT force status success, fake an audio object, or defeat guest memory hard fences")
    print("[Phase6R57] AUDIT COMPLETE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
