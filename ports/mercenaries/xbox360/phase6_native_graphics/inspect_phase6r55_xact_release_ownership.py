#!/usr/bin/env python3
"""Phase 6R55 zero-build audit: XACT AddRef/Release ownership, indirect dispatch.

Hardware R51:
  XACT engine root 01B5C320 created with field8(refcount)=1
  release 0027F2C2 entered field8=1 -> wrote field8=0
  destructor 0027F194 cleared global 0028836C; heap freed root
  subsequent stream 00280C39 dereferenced global 0 and propagated
  invalid .text-derived pointer 00041D90 -> 00041D88.
R54 identified direct release wrappers 00280062 and 00282A9B,
but hardware release telemetry reported site=0; exact indirect caller
is NOT proven. Do not patch refcounts or bypass a freed root.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

FOCUS=(
 (0x0027F2C2,"XACT Release entry, decrement/zero and destructor"),
 (0x0027F282,"XACT final destructor wrapper"),
 (0x0027F194,"XACT root global clear and actual destruction"),
 (0x0027DB5C,"XACT root initialization (refcount=1)"),
 (0x00280062,"one direct Release wrapper"),
 (0x00282A9B,"second direct Release wrapper"),
 (0x00280141,"post-release hardware writes to freed root VA"),
 (0x0027EE17,"XACT streaming API reads global then calls 0027ED57"),
 (0x0027F3DC,"XACT root accessor with explicit nonzero guard"),
 (0x0023A3CE,"instrumentation frequently attributes root dispatch here"),
)
TOKENS=(
 "0x27F2C2", "0x0027F2C2",
 "0x27F282", "0x0027F282",
 "0x27F194", "0x0027F194",
 "0x27F2A", "0x0027F2A",
 "0x30266C", "0x0030266C",
)
MAX=165
MAX_CONTEXTS=10

def show(row,only=None):
  ls=row["body"].splitlines()
  if only is None:
    lo=0;hi=min(len(ls),MAX)
  else:
    lo=max(0,only-20);hi=min(len(ls),only+22)
  print("="*104)
  print(f"[Phase6R55] FUNCTION owner={row['name']} va={row['va']:08X} lines={len(ls)} shown={lo+1}..{hi}")
  for j in range(lo,hi):
    print(f"[Phase6R55] {'>>' if j==only else '  '} {j+1:04d}: {ls[j]}")
  if hi<len(ls):
    print(f"[Phase6R55] ... trailing lines omitted={len(ls)-hi}")

def main()->int:
  ap=argparse.ArgumentParser()
  ap.add_argument("--source",type=Path,required=True)
  args=ap.parse_args()
  if not args.source.is_file():
    raise SystemExit(f"[Phase6R55] missing generated source {args.source}")
  data=args.source.read_text(encoding="utf-8",errors="replace")
  rows=functions(data)
  byva={r["va"]:r for r in rows}
  print("[Phase6R55] XACT RELEASE REFCOUNT / INDIRECT CALLER FORENSIC AUDIT")
  print(f"[Phase6R55] source={args.source} translated_functions={len(rows)}")
  print("[Phase6R55] HARDWARE refcount root=01B5C320 initial=1 -> Release(after)=0")
  print("[Phase6R55] HARDWARE root global 0028836C changed 01B5C320 -> 00000000")
  print("[Phase6R55] HARDWARE root heap allocation=01B5C320 was freed")
  print("[Phase6R55] HARDWARE later sub_00280C39 reads [00000010]=00041D90")
  print("[Phase6R55] HARDWARE release telemetry site=0, so no direct wrapper identified")
  print("[Phase6R55] NO REFCOUNT MUTATION / NO DESTROY SKIP / NO FREED ROOT REINSERTION")
  print("[Phase6R55] No Xbox run, no XEX build, no source modifications")

  print("[Phase6R55] 1/4 RELEASE/ADDREF/OWNER FUNCTION BODIES")
  for addr,purpose in FOCUS:
    print(f"[Phase6R55] focus={addr:08X} purpose={purpose}")
    row=byva.get(addr)
    if row is None:
      label="loc_"+f"{addr:08X}"
      row=next((r for r in rows if label in r["body"]),None)
      if row:print(f"[Phase6R55] interior VA owner={row['name']}")
    if row is None:print(f"[Phase6R55] NO OWNER for {addr:08X}")
    else:show(row)

  print("[Phase6R55] 2/4 RELEASE AND DESTRUCTOR CROSS REFERENCES")
  by_token={token:[] for token in TOKENS}
  for row in rows:
    ls=row["body"].splitlines()
    for j,line in enumerate(ls):
      for token in TOKENS:
        if token in line:
          by_token[token].append((row,j,line))
  for token in TOKENS:
    found=by_token[token]
    print(f"[Phase6R55] token={token} occurrence_count={len(found)} unique_owners={len({r['va'] for r,_,_ in found})}")
    for row,j,_ in found[:MAX_CONTEXTS]:
      show(row,j)

  print("[Phase6R55] 3/4 DIRECT RELEASE/DESTRUCTOR CALLS")
  for symbol in ("sub_0027F2C2();","sub_0027F282();","sub_0027F194();"):
    calls=[]
    for row in rows:
      for j,line in enumerate(row["body"].splitlines()):
        if symbol in line:
          calls.append((row,j))
    print(f"[Phase6R55] direct_symbol={symbol} sites={len(calls)}")
    for row,j in calls[:MAX_CONTEXTS]:
      show(row,j)

  print("[Phase6R55] 4/4 ADDREF AND LIFETIME CANDIDATES")
  # Inspect neighboring function entries to expose the root vtable methods
  # and any increment of object+8 without assuming its ABI.
  neighbor=[r for r in rows if 0x0027F170<=r["va"]<=0x0027F370]
  for row in neighbor:
    if row["va"] in (0x0027F194,0x0027F282,0x0027F2C2):continue
    ls=row["body"].splitlines()
    refs=[j for j,line in enumerate(ls) if
          (" + 8" in line or "+8" in line or "0x8" in line) and
          any(x in line for x in ("WRITE32","READ32","write32","read32"))]
    if refs:
      print(f"[Phase6R55] potential_refcount_method={row['name']} refs={len(refs)}")
      show(row)
  print("[Phase6R55] Audit complete. Decide whether missing AddRef or an invalid Release caller is actually proven.")
  return 0

if __name__=="__main__":
  raise SystemExit(main())
