#!/usr/bin/env python3
"""R73 zero-build provenance of newly-exposed Xbox APU sample-counter read.

R72 hardware:
  A2A16 seeds real DSOUND pool[01B5C5CC]=01B5CAA4
  A2AA1 returns 01B5CAA4, A5309->A545F->F0C6 return 0.
  At tick 26,720,229 the hard fence stops READ32 FE80200C.
  Earlier R72 recorded WRITE32 FE80200C=0 (not read semantics).

Cross reference for register identity:
  xemu hw/xbox/mcpx/apu/apu_regs.h: NV_PAPU_XGSCNT=0x200C
  xemu hw/xbox/mcpx/apu/apu.c: read XGSCNT = ep_frame_div * 32
  Frame-driven sample count is NOT necessarily a writeback value.

This audit must not change unknown MMIO reads or silently return 0.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGETS=[
    (0x002A52AD,"A52AD - VP producer listed in R72 hard-stop journal"),
    (0x0029F78F,"F78F - parent producer listed in R72 hard-stop journal"),
    (0x0029EABE,"EABE - APU owner cited by hard-stop journal"),
    (0x002A41EE,"A41EE - audio parent cited by journal"),
    (0x002A2E38,"A2E38 - successful resource path"),
    (0x002A2B93,"A2B93 - resource hardware setup"),
]
HIGHLIGHT=re.compile(
    r"(?i)(GUEST_READ32|GUEST_WRITE32|phase6ch_apu_read32|"
    r"phase6ch_apu_write32|FE80200C|0x200C|0x200c|"
    r"0x2000|0x200c|0x82000|0x800000|002A52AD|0029F78F|0029EABE|"
    r"sub_002A|call|PUSH32|0x0200C)")
MAIN_HIGHLIGHT=(
    "phase6ch_apu_read32","phase6ch_apu_write32",
    "phase6ch_apu_read","phase6dq_apu",
    "0xFE80200C","FE80200C","0x200Cu","0x200C",
    "0xFE820010u","FE820010",
)
def dump(row,label):
    arr=row["body"].splitlines()
    print(f"[Phase6R73] ------ {label} sub_{row['va']:08X} body_lines={len(arr)}")
    if len(arr)<=280:
        indices=list(range(len(arr)))
    else:
        marked=set(range(min(40,len(arr))))|set(range(max(0,len(arr)-30),len(arr)))
        for i,l in enumerate(arr):
            if HIGHLIGHT.search(l):
                marked.update(range(max(0,i-5),min(len(arr),i+7)))
        indices=sorted(marked)
    last=-1
    for i in indices:
        if i!=last+1:
            print(f"[Phase6R73] ... omitted {i-last-1} lines ...")
        print(f"[Phase6R73] {i+1:04d} {arr[i]}")
        last=i

def main_excerpt(text:str):
    lines=text.splitlines()
    print(f"[Phase6R73] main_cpp_lines={len(lines)}")
    hits=[i for i,l in enumerate(lines) if any(k in l for k in MAIN_HIGHLIGHT)]
    print(f"[Phase6R73] main MMIO/relevant symbol hit_lines={len(hits)}")
    indices=set()
    for i in hits[:100]:
        indices.update(range(max(0,i-16),min(len(lines),i+37)))
    last=-1
    for i in sorted(indices):
        if i!=last+1:
            print(f"[Phase6R73] MAIN ... omitted {i-last-1} lines ...")
        print(f"[Phase6R73] MAIN {i+1:06d} {lines[i]}")
        last=i

def callers(rows,va:int):
    needle=f"sub_{va:08X}();"
    hits=[]
    for row in rows:
        ls=row["body"].splitlines()
        for i,l in enumerate(ls):
            if needle in l:
                hits.append((row,i,ls))
    print(f"[Phase6R73] CALLS sub_{va:08X} count={len(hits)}")
    for row,i,ls in hits[:25]:
        print(f"[Phase6R73] caller=sub_{row['va']:08X} call_line={i+1}")
        for j in range(max(0,i-12),min(len(ls),i+13)):
            print(f"[Phase6R73] {j+1:04d} {ls[j]}")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--source",required=True,type=Path)
    p.add_argument("--cached-main",required=True,type=Path)
    args=p.parse_args()
    if not args.source.is_file() or not args.cached_main.is_file():
        raise SystemExit("[Phase6R73] Required R59 source or TrueTU main.cpp missing")
    source=args.source.read_text(encoding="utf-8",errors="replace")
    entry=args.cached_main.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in source:
        raise SystemExit("[Phase6R73] R59 ABI overlay identity mismatch")
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in entry:
        raise SystemExit("[Phase6R73] Cached main build-tag mismatch")
    rows=functions(source)
    index={r["va"]:r for r in rows}
    print("[Phase6R73] ===========================================================")
    print("[Phase6R73]  NEW FE80200C APU XGSCNT REGISTER READ / MMIO ROUTER AUDIT")
    print("[Phase6R73] ===========================================================")
    print(f"[Phase6R73] R59 source={args.source} guest_functions={len(rows)}")
    print("[Phase6R73] Xbox R72 resource pool repaired: A2A16/A2AA1 head 01B5CAA4")
    print("[Phase6R73] Xbox R72 READ32 FE80200C hard-stop tick=26720229")
    print("[Phase6R73] Xbox R72 earlier WRITE32 FE80200C=0, not enough to prove readback")
    print("[Phase6R73] Xemu: NV_PAPU_XGSCNT = 0x200C, read = ep_frame_div*32")
    print("[Phase6R73] Reference: xemu-project/xemu/hw/xbox/mcpx/apu/apu_regs.h")
    print("[Phase6R73] Reference: xemu-project/xemu/hw/xbox/mcpx/apu/apu.c")
    print("[Phase6R73] Unknown MMIO/VP reads remain HARD FENCED. Source-only audit.")
    print("[Phase6R73] SECTION 1/3 owner/source functions")
    for va,label in TARGETS:
        row=index.get(va)
        if not row:
            print(f"[Phase6R73] unavailable sub_{va:08X}; skipping optional target")
        else:dump(row,label)
    print("[Phase6R73] SECTION 2/3 direct owner callers")
    for va in (0x002A52AD,0x0029F78F,0x0029EABE):
        callers(rows,va)
    print("[Phase6R73] SECTION 3/3 cached main APU guest MMIO router")
    main_excerpt(entry)
    print("[Phase6R73] NEXT: choose explicit XGSCNT sample-counter model tied to")
    print("[Phase6R73] established guest clock/audio frame progression (not arbitrary constant).")
    print("[Phase6R73] Do not broaden to unknown APU/VP reads or disable the fence.")
    print("[Phase6R73] AUDIT COMPLETE")
    return 0
if __name__=="__main__":
    raise SystemExit(main())
