#!/usr/bin/env python3
"""Phase6R77: zero-build audit of new kernel thunk 80000080.

Hardware R76 run:
  startup watermark P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029
  XGSCNT guest READ32(FE80200C) returns shadow 0 (previous fault cleared)
  next ICALL_SAFE hard stop: target 80000080 at tick 26720251.
Xbox kernel ordinal 128: KeQuerySystemTime(PLARGE_INTEGER SystemTime),
a guest-output-pointer function whose 8-byte result is 100ns intervals
since 1601-01-01 UTC. Do not fabricate an address or return time 0.
Inspect caller/bridge/dispatch code and the existing kernel time model
before applying an ABI-accurate ordinal-128 continuation.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

R76_MARKER="P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029"
TERMS=(
 "KeQuerySystemTime","KeQueryInterruptTime","KeQueryPerformanceCounter",
 "KeQueryPerformanceFrequency","KeTickCount","KeSystemTime",
 "recomp_guest_indirect","ICALL_SAFE","icall_safe","kernel_ordinal",
 "kernel_export","kernel_thunk","xboxkrnl","QueryPerformanceCounter",
 "QueryPerformanceFrequency","GetSystemTimeAsFileTime",
 "KeQueryTimeIncrement","recomp_guest_read32","recomp_guest_write32",
)
HEX=re.compile(r"(?i)\b(?:0x)?80000080\b|\b0x(?:80|0080|00000080)\b")
SOURCE_HITS=re.compile(r"(?i)(0x80000080|80000080|0x002DBCE0|0x2DBCE0|"
    r"sub_002A5293|KeQuerySystemTime|GUEST_READ32|GUEST_WRITE32|"
    r"ICALL_SAFE|icall_safe|kernel_thunk|0x80\b)")
DECL=re.compile(r"(?i)\b(?:static\s+)?(?:inline\s+)?(?:bool|void|"
    r"uint32_t|uint64_t|DWORD|int|ULONG|LARGE_INTEGER|"
    r"XBOXAPI|NTSTATUS)\s+(\w+)\s*\(")

def dump(lines,items,prefix,before=8,after=22,limit=52):
    print(f"[Phase6R77] {prefix} hits={len(items)} shown={min(len(items),limit)}")
    # Show context around unique matching lines, capped to keep report useful.
    wanted=set()
    for index in items[:limit]:
        wanted.update(range(max(0,index-before),min(len(lines),index+after+1)))
    last=-1
    for i in sorted(wanted):
        if i!=last+1:
            print(f"[Phase6R77] {prefix} ... {i-last-1} source lines omitted")
        print(f"[Phase6R77] {prefix} {i+1:06d} {lines[i]}")
        last=i

def cached_main(source):
    lines=source.splitlines()
    print("[Phase6R77] SECTION 1/4: cached main ordinal/clock symbols")
    for token in TERMS:
        matching=[i for i,line in enumerate(lines) if token.lower() in line.lower()]
        if not matching:
            print(f"[Phase6R77] SYMBOL {token}: 0 matches")
            continue
        print(f"[Phase6R77] SYMBOL {token}: text_hits={len(matching)}")
        focused=[i for i in matching if re.search(
            r"(?i)(case\s+128|case\s+0x80|0x80000080|"
            r"if\s*\(|(?:void|uint32_t|uint64_t|bool|DWORD|int)\s+\w+\s*\(|"
            r"#define|switch\s*\(|target|ordinal|KeQuerySystemTime)",lines[i])]
        dump(lines,focused if focused else matching,
             "MAIN "+token,before=8,after=23,limit=8)
    print("[Phase6R77] SECTION 2/4: hard target constants/ordinal switch")
    exact=[i for i,line in enumerate(lines) if HEX.search(line)]
    dump(lines,exact,"MAIN target_80000080",before=10,after=30,limit=28)
    ordinal=[i for i,line in enumerate(lines) if re.search(
        r"(?i)\bcase\s+(?:128|0x80|0x0080|0x00000080)\s*:",line)]
    dump(lines,ordinal,"MAIN ordinal_128",before=15,after=34,limit=16)
    print("[Phase6R77] SECTION 3/4: indirect dispatch and guest stack ABI")
    needle=re.compile(r"(?i)(ICALL_SAFE|kernel.?import|recomp_kernel|"
        r"kernel.?thunk|s_phase6dq_.*(?:time|qpc)|"
        r"KeQuerySystemTime|KeQueryPerformanceCounter)")
    matches=[i for i,line in enumerate(lines) if needle.search(line)]
    # Favor code definitions, target tests and kernel import implementations.
    ranked=sorted(matches,key=lambda i: (
       0 if re.search(r"(?i)(KeQuerySystemTime|80000080|case\s+128)",lines[i]) else
       1 if re.search(r"(?i)(kernel|icall_safe|dispatch)",lines[i]) else 2,
       i))
    dump(lines,ranked,"MAIN dispatch",before=10,after=32,limit=24)

def guest_source(text):
    rows=functions(text)
    byva={r["va"]:r for r in rows}
    print(f"[Phase6R77] R59 translated functions={len(rows)}")
    print("[Phase6R77] SECTION 4/4: guest callsite and 128 target provenance")
    for va in (0x002A5293,0x002A52AD,0x0029EABE,0x0029F78F,0x0023A3CE):
        r=byva.get(va)
        if r is None:
            print(f"[Phase6R77] OPTIONAL source sub_{va:08X} unavailable")
            continue
        arr=r["body"].splitlines()
        print(f"[Phase6R77] GUEST sub_{va:08X} source_lines={len(arr)}")
        if len(arr)<=180:
            indices=list(range(len(arr)))
        else:
            marked=set(range(min(35,len(arr))))|set(range(max(0,len(arr)-22),len(arr)))
            for i,line in enumerate(arr):
                if SOURCE_HITS.search(line):
                    marked.update(range(max(0,i-8),min(len(arr),i+15)))
            indices=sorted(marked)
        last=-1
        for i in indices[:420]:
            if i!=last+1:
                print(f"[Phase6R77] sub_{va:08X} ... omitted {i-last-1} lines")
            print(f"[Phase6R77] sub_{va:08X} {i+1:05d} {arr[i]}")
            last=i
        if len(indices)>420:
            print(f"[Phase6R77] sub_{va:08X} omitted {len(indices)-420} extra context lines")
    direct=[(r["va"],i+1,l.strip()[:200])
      for r in rows for i,l in enumerate(r["body"].splitlines())
      if "80000080" in l or "KeQuerySystemTime" in l]
    print(f"[Phase6R77] GUEST literal KeQuerySystemTime / 80000080 hits={len(direct)}")
    for row in direct[:25]:
        print(f"[Phase6R77] GUEST LITERAL function={row[0]:08X} line={row[1]} text={row[2]}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--cached-main",type=Path,required=True)
    p.add_argument("--source",type=Path,required=True)
    a=p.parse_args()
    for f in (a.cached_main,a.source):
        if not f.is_file():
            raise SystemExit(f"[Phase6R77] required source missing: {f}")
    main_source=a.cached_main.read_text(encoding="utf-8",errors="replace")
    guest=a.source.read_text(encoding="utf-8",errors="replace")
    if R76_MARKER not in main_source:
        raise SystemExit("[Phase6R77] R76 tested source watermark missing")
    if "P6DQ R59 FC4A ABI RESTORE:" not in guest:
        raise SystemExit("[Phase6R77] R59 guest-source marker absent")
    print("[Phase6R77] =================================================================")
    print("[Phase6R77]  EXACT 80000080 KERNEL IMPORT / KeQuerySystemTime ABI AUDIT")
    print("[Phase6R77] =================================================================")
    print("[Phase6R77] R76 Xbox: guest FE80200C routed; old read fault eliminated")
    print("[Phase6R77] R76 new boundary ICALL_SAFE 80000080 at tick=26720251")
    print("[Phase6R77] Ordinal 128 = KeQuerySystemTime(PLARGE_INTEGER CurrentTime)")
    print("[Phase6R77] SystemTime = 100ns ticks since 1601 UTC. Not a fake HRESULT.")
    print("[Phase6R77] Source-only. No Xbox build, no guest clock modification.")
    cached_main(main_source)
    guest_source(guest)
    print("[Phase6R77] NEXT: choose guest time source and exact stack output pointer.")
    print("[Phase6R77] AUDIT COMPLETE")

if __name__=="__main__":
    raise SystemExit(main())
