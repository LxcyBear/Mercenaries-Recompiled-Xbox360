#!/usr/bin/env python3
"""Phase 6R65: zero-build provenance of the two remaining A545F failure paths.

Hardware R63: F0C6 -> A5770 returned 8007000E; earlier F03A returned 0.
Cached source R64:
  A5770 (bit 2 clear) -> tail-call A545F
  A545F first calls A4238 and can return its negative status directly.
  Otherwise, one branch calls A5309; when A2E38 returns zero A5309
  explicitly sets EDI to 0x8007000E and calls A4CEB cleanup.
R64 does NOT establish which branch ran in hardware.
Audit A2E38, the A4238 early failure via A0F98, their first-hop
helpers and the caller's exact input-passing frame. No code mutation.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

AUDIT_ROOTS=(
    (0x002A2E38,"Resource/allocation helper that A5309 tests for null"),
    (0x002A0F98,"Earlier A4238 helper whose negative return propagates"),
    (0x002A4238,"Earlier A545F child; can propagate a negative status"),
    (0x002A5309,"Explicit 8007000E assignment when A2E38 returns zero"),
    (0x002A545F,"Parent choosing between A4238, A536E and A5309"),
    (0x002A4CEB,"Failure cleanup after A5309 null resource"),
)
NEEDLE=re.compile(r"(?i)(0x8007000E|0x80004005|0xC0000017|0x800700|"
    r"phase6ch_apu_read32|phase6ch_apu_write32|GUEST_READ|GUEST_WRITE|"
    r"Alloc|Free|Heap|Pool|sub_[0-9a-f]{8}\(\)|CALL_SAFE|if \(|"
    r"goto |return|eax =|ebx =|esi =|edi =)")
CALLS=re.compile(r"\bsub_([0-9a-fA-F]{8})\(\)")

def children(row):
    found=[]
    for t in CALLS.findall(row["body"]):
        a=int(t,16)
        if a!=row["va"] and a not in found:
            found.append(a)
    return found

def dump(row,label,max_full=420):
    lines=row["body"].splitlines()
    print("="*104)
    print(f"[Phase6R65] {label}: sub_{row['va']:08X} body_lines={len(lines)} "
          f"direct_children={','.join(f'{x:08X}' for x in children(row))}")
    if len(lines)<=max_full:
        indices=range(len(lines))
    else:
        sampled=set(range(min(120,len(lines))))|set(range(max(0,len(lines)-45),len(lines)))
        matched=[i for i,line in enumerate(lines) if NEEDLE.search(line)]
        for i in matched[:100]:
            sampled.update(range(max(0,i-2),min(len(lines),i+4)))
        indices=sorted(sampled)
    previous=-1
    for i in indices:
        if i>previous+1:print(f"[Phase6R65]  ... omitted {i-previous-1} lines ...")
        print(f"[Phase6R65] {i+1:04d}: {lines[i]}")
        previous=i
    print(f"[Phase6R65] END {label}")

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    args=p.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R65] Cached R59 source not found: {args.source}")
    data=args.source.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in data:
        raise SystemExit("[Phase6R65] R59 exact ABI overlay tag missing; refusing unrelated source")
    rows=functions(data)
    byva={row["va"]:row for row in rows}
    print("[Phase6R65] ================================================================")
    print("[Phase6R65]  A545F TWO-PATH 8007000E / NULL-RESOURCE PROVENANCE")
    print("[Phase6R65] ================================================================")
    print(f"[Phase6R65] cached_source={args.source} function_bodies={len(rows)}")
    print("[Phase6R65] R63 hardware: F03A=00000000, A5770=8007000E")
    print("[Phase6R65] R64: A545F may propagate negative A4238 OR A5309's explicit 8007000E")
    print("[Phase6R65] R64: A5309's 8007000E requires A2E38 return=00000000")
    print("[Phase6R65] No proof yet that A2E38 returned null on hardware")
    print("[Phase6R65] No source mutation, emitter, TrueTU, compiler or hardware run")
    for address,label in AUDIT_ROOTS:
        row=byva.get(address)
        if not row:
            print(f"[Phase6R65] ERROR required translated body absent sub_{address:08X}")
            return 2
        dump(row,label)
    print("[Phase6R65] FOCUSED FIRST-HOP OF A2E38 AND A0F98")
    visited={x for x,_ in AUDIT_ROOTS}
    n=0
    for parent in (0x002A2E38,0x002A0F98):
        row=byva[parent]
        for address in children(row):
            if address in visited:continue
            visited.add(address)
            child=byva.get(address)
            if child is None:
                print(f"[Phase6R65] CALLEE sub_{address:08X}: untranslated")
                continue
            print(f"[Phase6R65] ROOT={parent:08X} child={address:08X} "
                  f"child_lines={len(child['body'].splitlines())}")
            if n<16:
                dump(child,"FIRST-HOP HELPER",max_full=125)
            n+=1
    print(f"[Phase6R65] first_hop_helpers={n}")
    print("[Phase6R65] A2E38 ALL DIRECT CALLERS - bounded context")
    found=0
    for row in rows:
        if row["va"]==0x002A2E38:continue
        lines=row["body"].splitlines()
        for i,line in enumerate(lines):
            if "sub_002A2E38();" not in line:continue
            found+=1
            print(f"[Phase6R65] CALLER sub_{row['va']:08X} line={i+1}")
            if found<=12:
                for j in range(max(0,i-12),min(len(lines),i+12)):
                    print(f"[Phase6R65] CALLSITE {j+1:04d}: {lines[j]}")
    print(f"[Phase6R65] A2E38 exact callsites={found}")
    print("[Phase6R65] NEXT: distinguish A4238 negative versus A5309 null-return.")
    print("[Phase6R65] Do not fake success, relax memory fences, or suppress legitimate cleanup.")
    print("[Phase6R65] AUDIT COMPLETE")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
