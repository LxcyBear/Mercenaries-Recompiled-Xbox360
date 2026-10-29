#!/usr/bin/env python3
"""Phase 6R70: zero-build source provenance for R69's wrong pool seed address.

Observed 2026-10-29 Xbox R69:
  R62 FF54_FINAL_RETURN = 01B5C554 (new DirectSound object backing)
  A19FC_AFTER_A739F: ESI=0, EDI=01B5C554
  A2A16_AFTER_FF54: ESI=00000060, new backing=01B5CAA4
  A2A16_STORED_HEAD: head=01B5CAA4 from [ESI+0x18] = [00000078]
  A19FC_AFTER_A2A16: ESI=0, head=01B5CAA4 from [ESI+0x78]=[00000078]
  R66 A2AA1_POOL_HEAD: EDI=01B5C5B4; [EDI+0x18]=[01B5C5CC]=0
Potential root cause: object-relative 0x60 passed as literal, or an
ABI/frame/reg preservation fault causing the object base to be NULL.
No corrective patch is safe until the exact source expressions show
the intended object and the stack/calling-convention sequence.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

REQUIRED=(
 (0x002A19FC,"A19FC - init: object-base register, A739F and A2A16 calls"),
 (0x002A2A16,"A2A16 - page pool seeder: input args, FF54, A2977, +0x18 writes"),
 (0x002A739F,"A739F - early init/possible register destruction"),
 (0x002A2977,"A2977 - construct head node from backing allocation"),
 (0x002A2AA1,"A2AA1 - later allocator: pool base in EDI"),
)
OPTIONAL=(
 (0x0029FC4A,"FC4A - DSOUND outer caller"),
 (0x002A0E9D,"A0E9D - DSOUND outer initialization"),
 (0x002A41EE,"A41EE - object downstream"),
)
SUSPECT=re.compile(r"(?i)(0x60\\b|0x78\\b|\\+ 96\\b|\\+ 120\\b|sub_002A19FC|sub_002A2A16|"
    r"sub_002A739F|sub_002A2977|\\b(?:esi|edi|ecx|ebx)\\s*=|PUSH32|"
    r"phase6ch_apu_(?:read32|write32)|GUEST_(?:READ32|WRITE32)|0x18\\b)")

def dump(row,label,max_lines=400):
    arr=row["body"].splitlines()
    print("="*105)
    print(f"[Phase6R70] {label}: sub_{row['va']:08X} lines={len(arr)}")
    if len(arr)<=max_lines:
        selected=list(range(len(arr)))
    else:
        want=set(range(min(80,len(arr))))|set(range(max(0,len(arr)-50),len(arr)))
        for i,line in enumerate(arr):
            if SUSPECT.search(line):
                want.update(range(max(0,i-7),min(len(arr),i+12)))
        selected=sorted(want)
    last=-1
    for i in selected:
        if i>last+1:
            print(f"[Phase6R70] ... OMITTED {i-last-1} source lines ...")
        print(f"[Phase6R70] {i+1:04d}: {arr[i]}")
        last=i
    print(f"[Phase6R70] END sub_{row['va']:08X}")

def direct_callers(rows,target,max_output=16):
    found=[]
    needle=f"sub_{target:08X}();"
    for r in rows:
        lines=r["body"].splitlines()
        for i,line in enumerate(lines):
            if needle in line:
                found.append((r,i,lines))
    print(f"[Phase6R70] DIRECT_CALLER target={target:08X} count={len(found)}")
    for row,i,lines in found[:max_output]:
        print(f"[Phase6R70] CALLER sub_{row['va']:08X} line={i+1}")
        for j in range(max(0,i-24),min(len(lines),i+18)):
            print(f"[Phase6R70] {j+1:04d}: {lines[j]}")
    return found

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R70] Cached R59 source missing: {args.source}")
    data=args.source.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in data:
        raise SystemExit("[Phase6R70] Missing R59 exact ABI marker; wrong source")
    rows=functions(data)
    byva={r["va"]:r for r in rows}
    missing=[f"{a:08X}" for a,_ in REQUIRED if a not in byva]
    if missing:
        raise SystemExit("[Phase6R70] Missing required translated function(s): "+", ".join(missing))
    print("[Phase6R70] =======================================================================")
    print("[Phase6R70]  R69 PROVEN MISMATCH: INITIALIZER WRITES [00000078], LATER READS [01B5C5CC]")
    print("[Phase6R70] =======================================================================")
    print(f"[Phase6R70] cached_source={args.source} bodies={len(rows)}")
    print("[Phase6R70] Hardware A19FC after A739F: ESI=00000000 EDI=01B5C554")
    print("[Phase6R70] Hardware A2A16 at head store: ESI=00000060 EAX=01B5CAA4")
    print("[Phase6R70] Hardware A19FC after A2A16: ESI=00000000; R69 read [0x78]")
    print("[Phase6R70] Hardware A2AA1: EDI=01B5C5B4; read [01B5C5CC]=0")
    print("[Phase6R70] R69 head=01B5CAA4 at [00000078] DOES NOT prove true pool seeded")
    print("[Phase6R70] Do not coerce registers/pointers or zero-page memory; verify source.")
    print("[Phase6R70] No emission, TrueTU mutation, Xbox build, or XEX deployment")
    print("[Phase6R70] SECTION 1/3 CRITICAL INITIALIZER AND RESOURCE FUNCTIONS")
    for va,label in REQUIRED:
        dump(byva[va],label)
    print("[Phase6R70] SECTION 2/3 CALLSITE INPUTS / REGISTER SETUP")
    for va in (0x002A19FC,0x002A2A16,0x002A739F):
        direct_callers(rows,va,max_output=16)
    print("[Phase6R70] SECTION 3/3 OPTIONAL UPSTREAM / DOWNSTREAM CONTEXT")
    for va,label in OPTIONAL:
        row=byva.get(va)
        if row is None:
            print(f"[Phase6R70] OPTIONAL sub_{va:08X} not present; skipping")
            continue
        dump(row,label,max_lines=180)
    print("[Phase6R70] INSPECT: A19FC entry ECX/EDI/ESI, the LEA +0x60 and A2A16 stack input.")
    print("[Phase6R70] INSPECT: any ABI repair needed at preceding call/return; target pool 01B5C5B4.")
    print("[Phase6R70] AUDIT COMPLETE")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
