#!/usr/bin/env python3
"""R68: source-only audit of DSOUND page pool's zero head after valid allocation.

R66 XDK hardware:
  A5309 -> A2E38 -> A2AA1:
    A2E38 input region=024901D4 -> page=02490000; pages=1
    A2AA1 pool object=01B5C5B4, pool+0x18=01B5C5CC -> 0
    A2AA1 returns 0; A5309 explicitly returns 0x8007000E
  R62 FF54 returned 01B5C554 (ExAllocatePoolWithTag, 1348 bytes).
    01B5C554 + 0x60 = 01B5C5B4, i.e., page pool lives IN
    this live DSOUND allocation, not random/unmapped memory.
R67 identifies sub_002A2A16 as a producer of list+0x18 through A2977,
but does not establish whether it executed for this pool object.
Inspect initializer, seed count/range, all direct callers and cleanup
paths. No patch/compile/no forged guest pointers.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGETS = (
  (0x002A2A16,"POOL SEEDER - primary R67 field +0x18 writer"),
  (0x002A2977,"POOL ENTRY INSERTION - return EAX identity"),
  (0x002A2AA1,"POOL ALLOCATION - read +0x18 and early exit"),
  (0x002A2C9D,"RESOURCE REINSERT - list +0x18 update"),
  (0x002A2D21,"RESOURCE RELEASE - may clear/repopulate +0x18"),
  (0x002A2EC7,"RESOURCE REINSERT - list +0x18 update"),
  (0x002A2F3E,"RESOURCE TRANSFER - list +0x18 update"),
  (0x002A5309,"ACTUAL AUDIO CALLER - pool object+0x60"),
  (0x002A41EE,"DSOUND initializer following F4BF"),
  (0x002A545F,"A4238 -> A5309 failure caller"),
)
CALL = re.compile(r"\bsub_([0-9a-fA-F]{8})\(\)")
MARK = re.compile(r"(?i)(sub_002A2A16|sub_002A2D21|sub_002A2977|"
  r"sub_002A2AA1|phase6ch_apu_write32|phase6ch_apu_read32|"
  r"0x18|0x1C|0x60|0x1000|0x2BB16|0x2DBE60|0x2DBE5C|"
  r"0x8007000E|if \(|goto |return)")

def scan_calls(rows):
    callers={}
    for row in rows:
        src=row["body"]
        for va in {int(v,16) for v in CALL.findall(src)}:
            callers.setdefault(va,[]).append(row["va"])
    return callers

def dump(row,label,limit=220):
    arr=row["body"].splitlines()
    print("="*108)
    print(f"[Phase6R68] {label}: sub_{row['va']:08X} lines={len(arr)}")
    if len(arr)<=limit:
        selected=list(range(len(arr)))
    else:
        chosen=set(range(min(len(arr),45)))|set(range(max(0,len(arr)-32),len(arr)))
        for i,l in enumerate(arr):
            if MARK.search(l):
                chosen.update(range(max(0,i-3),min(len(arr),i+4)))
        selected=sorted(chosen)
    last=-1
    for i in selected:
        if i>last+1:
            print(f"[Phase6R68] ... {i-last-1} intervening source lines omitted ...")
        print(f"[Phase6R68] {i+1:04d}: {arr[i]}")
        last=i
    print(f"[Phase6R68] END sub_{row['va']:08X}")

def call_sites(rows,needle,cap=40):
    found=[]
    for row in rows:
        if row["va"]==needle:continue
        arr=row["body"].splitlines()
        for i,line in enumerate(arr):
            if f"sub_{needle:08X}();" in line:
                found.append((row,i))
    print(f"[Phase6R68] DIRECT_CALLERS target={needle:08X} total={len(found)}")
    for row,i in found[:cap]:
        arr=row["body"].splitlines()
        print(f"[Phase6R68] CALLER sub_{row['va']:08X} call_line={i+1}")
        for j in range(max(0,i-15),min(len(arr),i+13)):
            print(f"[Phase6R68] {j+1:04d}: {arr[j]}")
    if len(found)>cap:
        print(f"[Phase6R68] OMITTED_CALLERS={len(found)-cap}")
    return [r["va"] for r,i in found]

def main():
    cli=argparse.ArgumentParser()
    cli.add_argument("--source",type=Path,required=True)
    a=cli.parse_args()
    if not a.source.is_file():
        raise SystemExit(f"[Phase6R68] R59 source missing: {a.source}")
    src=a.source.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in src:
        raise SystemExit("[Phase6R68] Missing exact R59 ABI marker; wrong source")
    rows=functions(src)
    byva={r["va"]:r for r in rows}
    missing=[f"{va:08X}" for va,_ in TARGETS if va not in byva]
    if missing:
        raise SystemExit("[Phase6R68] One or more required source bodies missing: "+", ".join(missing))
    graph=scan_calls(rows)
    print("[Phase6R68] =================================================================")
    print("[Phase6R68]  DIRECTSOUND PAGE POOL CONSTRUCTOR AND NULL-HEAD PROVENANCE")
    print("[Phase6R68] =================================================================")
    print(f"[Phase6R68] source={a.source} translated_functions={len(rows)}")
    print("[Phase6R68] Hardware: FF54 result 01B5C554; pool=FF54+0x60=01B5C5B4")
    print("[Phase6R68] Hardware: pool.head[01B5C5CC] = 0; request base 02490000 count 1")
    print("[Phase6R68] Hardware: A2AA1=0 -> A2E38=0 -> A5309=8007000E")
    print("[Phase6R68] R67: A2A16 seeds pool+0x18 via A2977; not proven executed")
    print("[Phase6R68] No XDK build, runtime patch, guest pointer fabrication or memory writes")
    print("[Phase6R68] SECTION 1/3 SEEDER AND LIST HELPERS")
    for va,label in TARGETS[:8]:
        dump(byva[va],label)
    print("[Phase6R68] SECTION 2/3 SEEDER CALLER CHAINS (DIRECT AND PARENTS)")
    seeds=(0x002A2A16,0x002A2977,0x002A2C9D,0x002A2D21,0x002A2EC7,0x002A2F3E)
    for seed in seeds:
        immediate=call_sites(rows,seed,cap=18)
        print(f"[Phase6R68] SEEDER {seed:08X} one-hop={','.join(f'{x:08X}' for x in immediate)}")
        for parent in immediate[:8]:
            supers=graph.get(parent,[])
            print(f"[Phase6R68] SEEDER {seed:08X} caller={parent:08X} "
                  f"upstream={','.join(f'{x:08X}' for x in supers[:16])}")
    print("[Phase6R68] SECTION 3/3 INITIALIZER AND ERROR-PATH CALLERS")
    for va,label in TARGETS[8:]:
        dump(byva[va],label)
    for va in (0x002A41EE,0x002A5309):
        call_sites(rows,va,cap=16)
    print("[Phase6R68] NEXT: determine whether A2A16 seeded pool 01B5C5B4,")
    print("[Phase6R68] or whether A2D21 / A2C9D later emptied it before A2AA1.")
    print("[Phase6R68] Keep genuine memory/guest ABI and MMIO hard fences intact.")
    print("[Phase6R68] AUDIT COMPLETE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
