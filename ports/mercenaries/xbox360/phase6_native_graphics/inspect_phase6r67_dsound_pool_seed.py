#!/usr/bin/env python3
"""R67 no-build: track the DSOUND page-pool free-list head's initialization.

Hardware proof R66 (not a hypothesis):
  A545F_AFTER_A4238 = 00000000
  A2E38_REQUEST_PAGES: ESI=1, EBX=024901D4
  A2AA1_POOL_HEAD: EAX=00000000, EDI=01B5C5B4, EBX=02490000
  A2AA1_FINAL_RESOURCE = 0
  A5309_EXPLICIT_8007000E executed
  XACT init = 8007000E; 27,027,014 ticks, no guest pixels.
R65 source: A2AA1 checks [EDI+0x18] (runtime 01B5C5CC);
a zero head makes it skip the free-list allocation path entirely.
Find which guest function should seed that field and from which Mm
reservation, without faking a resource pointer or modifying any code.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

ROOTS = (
  (0x002A2AA1,"A2AA1 POOL FREE-LIST ALLOCATOR"),
  (0x002A2977,"A2977 SPLIT/CREATE RESOURCE"),
  (0x002A2B93,"A2B93 POOL HARDWARE/RESOURCE MAP"),
  (0x002A2E38,"A2E38 MATCH/ALLOC/RELEASE"),
  (0x002A3260,"A3260 INIT HELPER FROM A4238"),
  (0x002A3311,"A3311 INIT HELPER FROM A4238"),
  (0x002A3565,"A3565 INIT HELPER FROM A4238"),
)
TARGETS={0x002A2AA1,0x002A2977,0x002A2B93,0x002A2E38,0x002A5309,0x002A4238}
WRITE=re.compile(
 r"phase6ch_apu_write(?:8|16|32)\s*\(\s*(?:\w+\s*\+\s*(?:0x18|24)|"
 r"\w+\s*\+\s*\(?\s*0x18\s*\)?|\w+),",
 re.I)
READ_HEAD=re.compile(r"phase6ch_apu_read32\s*\(\s*\w+\s*\+\s*0x18\s*\)",re.I)
CALL=re.compile(r"\bsub_([0-9A-Fa-f]{8})\(\)")
ALLOC=re.compile(r"(?i)(MmAllocate|0x2DBE60|0x2DBE5C|0x002A2AA1|0x002A2977|"
                 r"0x8007000E|0x88780032|0x02490000|02490000|0x18)")

def dump(row,label,limit=320):
    lines=row["body"].splitlines()
    print("="*112)
    print(f"[Phase6R67] {label} sub_{row['va']:08X} lines={len(lines)}")
    if len(lines)<=limit:
        selected=list(range(len(lines)))
    else:
        indices=set(range(min(90,len(lines))))|set(range(max(0,len(lines)-65),len(lines)))
        for i,line in enumerate(lines):
            if ALLOC.search(line):
                indices.update(range(max(0,i-3),min(len(lines),i+6)))
        selected=sorted(indices)
    last=-1
    for i in selected:
        if i>last+1:print(f"[Phase6R67]  ... omitted {i-last-1} lines ...")
        print(f"[Phase6R67] {i+1:04d} {lines[i]}")
        last=i

def callers(byva,needle,tag):
    matches=[]
    for row in byva.values():
        ls=row["body"].splitlines()
        for i,line in enumerate(ls):
            if needle in line:
                matches.append((row,i))
    print(f"[Phase6R67] {tag} total_callsites={len(matches)}")
    for row,i in matches[:50]:
        ls=row["body"].splitlines()
        print(f"[Phase6R67] {tag} OWNER=sub_{row['va']:08X} line={i+1}")
        for j in range(max(0,i-10),min(len(ls),i+10)):
            print(f"[Phase6R67] {j+1:04d}: {ls[j]}")
    return matches

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    x=ap.parse_args()
    if not x.source.is_file():
        raise SystemExit(f"[Phase6R67] No R59 source: {x.source}")
    src=x.source.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in src:
        raise SystemExit("[Phase6R67] Source not the validated R59 ABI overlay")
    items=functions(src)
    byva={item["va"]:item for item in items}
    missing=[f"{va:08X}" for va,_ in ROOTS if va not in byva]
    if missing:
        raise SystemExit("[Phase6R67] Missing translated bodies: "+",".join(missing))
    print("[Phase6R67] ================================================================")
    print("[Phase6R67]  WHY IS DSOUND POOL +0x18 ZERO? INIT/OWNER/XREF AUDIT")
    print("[Phase6R67] ================================================================")
    print(f"[Phase6R67] R59 cached_source={x.source} function_bodies={len(items)}")
    print("[Phase6R67] PROVEN Xbox: A2AA1 read pool[01B5C5CC]=0, pages=1, request 02490000")
    print("[Phase6R67] PROVEN Xbox: A2AA1 returns NULL and A5309 sets 8007000E")
    print("[Phase6R67] R66 Xbox: 02490000 had an actual successful 4096-byte Mm allocation")
    print("[Phase6R67] 0 source changes, 0 TrueTU operations, 0 XEX builds")
    print("[Phase6R67] SECTION 1/4 pool allocator, pool initializer helpers")
    for va,label in ROOTS:
        dump(byva[va],label)
    print("[Phase6R67] SECTION 2/4 WHO CALLS RESOURCE ALLOC/POOL INITIALIZER?")
    for va in sorted(TARGETS):
        callers(byva,f"sub_{va:08X}();",f"TARGET_{va:08X}")
    print("[Phase6R67] SECTION 3/4 DSOUND +0x18 FIELD WRITES / INITIALIZERS")
    matched=[]
    for row in items:
        if not (0x0029CB80<=row["va"]<0x002BB280):
            continue
        lines=row["body"].splitlines()
        for i,line in enumerate(lines):
            if ("phase6ch_apu_write32" in line and
                (re.search(r"\+\s*0x18\s*[,)]",line,re.I) or
                 re.search(r"write32\s*\(\s*[^,]*\+\s*24\s*,",line,re.I))):
                matched.append((row,i))
    print(f"[Phase6R67] DSOUND field+0x18 candidate_writes={len(matched)}")
    for row,i in matched[:75]:
        lines=row["body"].splitlines()
        print(f"[Phase6R67] WRITE owner=sub_{row['va']:08X} line={i+1} text={lines[i].strip()}")
        for j in range(max(0,i-13),min(len(lines),i+13)):
            print(f"[Phase6R67] {j+1:04d}: {lines[j]}")
    if len(matched)>75:
        print(f"[Phase6R67] WRITE other_candidates={len(matched)-75}")
    print("[Phase6R67] SECTION 4/4 FREE-LIST HEAD READERS / PAGE MANAGEMENT")
    headread=[]
    for row in items:
        if not (0x0029CB80<=row["va"]<0x002BB280):
            continue
        lines=row["body"].splitlines()
        for i,line in enumerate(lines):
            if READ_HEAD.search(line):
                headread.append((row,i))
    print(f"[Phase6R67] DSOUND +0x18 readsites={len(headread)}")
    for row,i in headread[:75]:
        print(f"[Phase6R67] READ owner=sub_{row['va']:08X} line={i+1} {row['body'].splitlines()[i].strip()}")
    print("[Phase6R67] NEXT: inspect field initializer against the known 02490000 Mm allocation.")
    print("[Phase6R67] Never set an arbitrary free-list head, fake guest allocation or bypass fences.")
    print("[Phase6R67] AUDIT COMPLETE")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
