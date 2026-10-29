#!/usr/bin/env python3
"""Phase 6R50: inspect the new hardware-proven ordinal-173 kernel-frame boundary.

R49 hardware fixed two channel pointers and crossed WRITE8 DEA8510B.
It stopped at ticks=26712896 kind=KERNEL_FRAME target=800000AD.
This is source-only: do not patch guest registers or widen hard-stop policy.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGET_VAS = (
    0x002A6F15,  # last A41EE ownership; may be merely provenance
    0x002A6DF3,  # recent VA ring
    0x002A6D7C,  # recent VA ring
    0x002A64C3,  # recent VA ring
    0x002A6468,  # recent VA ring
    0x002A6D1A,  # upstream 002A6B98 audio caller
    0x002A6B98,  # proven channel initialization
    0x0029CC2C,  # recent ring and last ICALL target
)
NEEDLES = (
    "800000AD", "0x800000AD",
    "MmGetPhysicalAddress", "mmgetphysicaladdress",
    "KERNEL_FRAME", "kernel_frame",
)
MAX_OWNER_LINES = 170
MAX_TEXT_OCCURRENCES = 24

def show_body(row: dict, target: int) -> None:
    lines = row["body"].splitlines()
    print("=" * 100)
    print(f"[Phase6R50] VA={target:08X} owner={row['name']} start={row['va']:08X} lines={len(lines)}")
    labels = [i for i,line in enumerate(lines)
              if re.search(r"^\s*loc_" + f"{target:08X}" + r":\s*;", line, re.I)]
    anchor = labels[0] if labels else None
    if anchor is None:
        lo,hi = 0,min(len(lines),MAX_OWNER_LINES)
    else:
        lo=max(0,anchor-28)
        hi=min(len(lines),anchor+MAX_OWNER_LINES-28)
    for i in range(lo,hi):
        mark=">>" if i==anchor else "  "
        print(f"[Phase6R50] {mark} {i+1:04d}: {lines[i]}")
    if hi < len(lines):
        print(f"[Phase6R50] ... omitted {len(lines)-hi} lines in owner")

def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R50] SOURCE MISSING: {args.source}")
    text=args.source.read_text(encoding="utf-8",errors="replace")
    rows=functions(text)
    by_va={row["va"]:row for row in rows}
    ordered=sorted(rows,key=lambda row:row["va"])
    print("[Phase6R50] KERNEL ORDINAL 173 FRAME / DSOUND CALLSITE AUDIT")
    print("[Phase6R50] source=",args.source)
    print("[Phase6R50] hardware target=800000AD ordinal=173")
    print("[Phase6R50] hardware stop kind=KERNEL_FRAME ticks=26712896 esp=008BF820")
    print("[Phase6R50] latest VA ring includes 002A6D7C/002A6DF3")
    print("[Phase6R50] earlier ordinal-173 calls succeeded; do NOT auto-bypass")
    print("[Phase6R50] source_mutation=0 build=0 hardware_run=0")
    print("[Phase6R50] translated_bodies=",len(rows))

    for va in TARGET_VAS:
        row=by_va.get(va)
        if row is None:
            # This VA may be an interior label. Choose the nearest matching
            # owner only if its generated body actually contains that label.
            label=f"loc_{va:08X}: ;"
            row=next((r for r in ordered if label in r["body"]),None)
        if row is None:
            print(f"[Phase6R50] OWNER NOT FOUND for VA={va:08X}")
            continue
        show_body(row,va)

    print("=" * 100)
    print("[Phase6R50] LITERAL REFERENCES TO ORDINAL 173 / FRAME DISPATCH")
    lines=text.splitlines()
    for needle in NEEDLES:
        matches=[i for i,line in enumerate(lines) if needle.lower() in line.lower()]
        print(f"[Phase6R50] needle={needle} occurrences={len(matches)}")
        for k in matches[:MAX_TEXT_OCCURRENCES]:
            lo=max(0,k-4)
            hi=min(len(lines),k+5)
            for j in range(lo,hi):
                print(f"[Phase6R50] {j+1:06d}: {lines[j]}")
            print("[Phase6R50] ---")
        if len(matches)>MAX_TEXT_OCCURRENCES:
            print(f"[Phase6R50] omitted={len(matches)-MAX_TEXT_OCCURRENCES} matches")

    print("[Phase6R50] AUDIT COMPLETE. Confirm exact ordinal-173 frame shape before patching.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
