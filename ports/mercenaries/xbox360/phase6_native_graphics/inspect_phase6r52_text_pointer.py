#!/usr/bin/env python3
"""R52 zero-build audit: R51 DSOUND EC83F0E4 poison pointer provenance.

Facts from R51 Xbox trace:
 * F78F reads [edi+8] at 02490364 -> 00041D88
 * F78F subsequently reads [ecx+0xC] at 00041D94 -> EC83F0E4
 * 00041D88 / 00041D94 reside inside the retail .text section.
 * A52AD receives EC83F0E4; A4622/A41EE then READ32 fault there.
This script does not assume that .text pointers are wrong: functions,
vtables and trampoline data can have unusual layouts. Confirm source.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGET_VAS=(
  0x0029F78F,  # immediate pointer-producing read, priority 1
  0x002A52AD,  # first poisoned target
  0x002A4622,  # downstream caller
  0x002A41EE,  # final READ32
  0x0029FBE2,  # upstream XACT call
  0x0029F992,  # DSOUND stage 1
  0x0029EBEA,  # DSOUND stage 2
  0x0029EA79,  # DSOUND stage 3
  0x00280C39,  # XACT entry
  0x0027ED57,  # XACT caller
)
RELEVANT=(
  "phase6dq_f78f_read32", "phase6ch_apu_read32",
  "phase6ch_apu_write32", "GUEST_READ32", "GUEST_WRITE32",
  "sub_002A52AD", "sub_002A4622", "sub_002A41EE",
  "sub_0029F78F", "sub_0029F992", "sub_0029EBEA",
  "sub_0029EA79", "0x41D88", "0x41D90", "0x41D94",
  "00041D88", "00041D90", "00041D94",
  "ecx = esi", "esi = ecx", "edi + 8",
)
GLOBAL_NEEDLES=(
 "sub_00041D88", "sub_00041D90",
 "loc_00041D88", "loc_00041D90",
 "0x41D88", "0x41D90", "0x41D94",
 "00041D88", "00041D90", "00041D94",
)
PRE=13
POST=10
MAX_LINES_PER_BODY=245

def show_body(row:dict, detailed:bool=False):
  lines=row["body"].splitlines()
  marked={i for i,line in enumerate(lines) if any(term in line for term in RELEVANT)}
  if detailed:
    selected=set(range(min(len(lines), MAX_LINES_PER_BODY)))
  else:
    selected=set(range(min(len(lines), 34)))
    for pos in marked:
      selected.update(range(max(0,pos-PRE),min(len(lines),pos+POST+1)))
    if len(selected)>MAX_LINES_PER_BODY:
      selected=set(sorted(selected)[:MAX_LINES_PER_BODY])
  print("="*104)
  print(f"[Phase6R52] BODY owner={row['name']} va={row['va']:08X} lines={len(lines)} displayed={len(selected)}")
  last=-2
  for i in sorted(selected):
    if i>last+1:
      print(f"[Phase6R52] ... skipped {i-last-1} lines ...")
    marker=">>" if i in marked else "  "
    print(f"[Phase6R52] {marker} {i+1:04d}: {lines[i]}")
    last=i
  if len(selected)<len(lines):
    print(f"[Phase6R52] remaining lines omitted={len(lines)-len(selected)}")

def main()->int:
  ap=argparse.ArgumentParser()
  ap.add_argument("--source",type=Path,required=True)
  args=ap.parse_args()
  if not args.source.is_file():
    raise SystemExit(f"[Phase6R52] missing generated source: {args.source}")
  data=args.source.read_text(encoding="utf-8",errors="replace")
  rows=functions(data)
  by_va={r["va"]:r for r in rows}
  print("[Phase6R52] R51 POISON POINTER / TEXT-SECTION ZERO-BUILD AUDIT")
  print(f"[Phase6R52] source={args.source} functions={len(rows)}")
  print("[Phase6R52] XBE .text range=00011000..0025561C")
  print("[Phase6R52] source pointer: [02490364] -> 00041D88")
  print("[Phase6R52] poison read: [00041D94] -> EC83F0E4")
  print("[Phase6R52] first downstream consumer: sub_002A52AD")
  print("[Phase6R52] final fault: READ32 EC83F0E4 at tick=27026295")
  print("[Phase6R52] no mutation / no XDK compilation / no Xbox run")
  for va in TARGET_VAS:
    row=by_va.get(va)
    if row is None:
      print(f"[Phase6R52] MISSING BODY sub_{va:08X}")
    else:
      show_body(row, detailed=(va==0x0029F78F))
  print("="*104)
  print("[Phase6R52] OBJECT-VS-CODE POINTER CROSS-REFERENCES")
  matches={token:[] for token in GLOBAL_NEEDLES}
  counts={token:0 for token in GLOBAL_NEEDLES}
  for i,line in enumerate(data.splitlines(),1):
    for token in GLOBAL_NEEDLES:
      if token in line:
        counts[token]+=1
        if len(matches[token])<14:
          matches[token].append((i,line.strip()))
  for token in GLOBAL_NEEDLES:
    print(f"[Phase6R52] literal={token} count={counts[token]}")
    for line_no,line in matches[token]:
      print(f"[Phase6R52]   line={line_no}: {line[:240]}")
  # Treat address membership as a clue, not proof of data or code semantics.
  ftext=[r for r in rows if 0x11000 <= r["va"] < 0x25561C]
  closest=[r for r in ftext if r["va"] <= 0x41D94]
  for va in (0x41D88,0x41D90,0x41D94):
    exact=by_va.get(va)
    owner=max((r for r in closest if r["va"]<=va),key=lambda r:r["va"],default=None)
    print(f"[Phase6R52] text_va={va:08X} exact_translated_function={exact['name'] if exact else 'NO'} preceding_function={owner['name'] if owner else 'UNKNOWN'}")
  print("[Phase6R52] AUDIT COMPLETE. Do not replace poison with a fabricated pointer.")
  return 0

if __name__=="__main__":
  raise SystemExit(main())
