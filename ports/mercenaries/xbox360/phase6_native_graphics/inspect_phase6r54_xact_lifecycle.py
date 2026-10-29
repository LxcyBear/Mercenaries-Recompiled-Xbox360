#!/usr/bin/env python3
"""Phase 6R54: XACT engine lifecycle, global 0x0028836C (zero-build).

R51 *hardware* timeline:
  1. 0028836C <- 01B5C320 (heap-allocated XACT root);
  2. 0028836C <- 00000000, root 01B5C320 later freed;
  3. 00280C39 reads [0028836C]=0, then [0x10]=00041D90;
  4. 0029FBE2 subtracts 8 => 00041D88, eventually READ32 EC83F0E4.
This audit identifies genuine init/teardown/reinit callsites; it never
restores a freed pointer or suppresses the original guest fault.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

ROOT_GLOBAL=0x0028836C
FOCUS=(
    0x0027DB5C,  # XACT init
    0x0027F194,  # earlier Phase 6DG teardown suspect
    0x00282C68,  # XACT sentinel handling before release in R51
    0x00283334,  # XACT field8 write during teardown
    0x00280C39,  # next XACT stream request; explicit null-root read
    0x0027ED57,  # direct caller of stream request
    0x0029FBE2,  # descriptor offset -8
    0x0029F78F,  # read from DSOUND object and code address
)
TEXT_MARKERS=(
    "0x28836C", "0x0028836C", "0x288380", "0x00288380",
)
CALL_MARKERS=(
    "sub_0027F194();",
    "sub_0027DB5C();",
    "sub_00280C39();",
)
MAXLINES=190
MAX_CALLERS=12
MAX_GLOBAL_OWNERS=35

def block(row, center=None, pre=25, post=27, limit=MAXLINES):
    lines=row["body"].splitlines()
    lo,hi=(0,min(len(lines),limit)) if center is None else (
        max(0,center-pre),min(len(lines),center+post+1))
    print("="*110)
    print(f"[Phase6R54] OWNER {row['name']} VA={row['va']:08X} body_lines={len(lines)} shown={hi-lo}")
    if lo: print(f"[Phase6R54] ... {lo} preceding lines omitted")
    for i in range(lo,hi):
        print(f"[Phase6R54] {'>>' if i==center else '  '} {i+1:04d}: {lines[i]}")
    if hi<len(lines):print(f"[Phase6R54] ... {len(lines)-hi} trailing lines omitted")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R54] MISSING SOURCE {args.source}")
    data=args.source.read_text(encoding="utf-8",errors="replace")
    rows=functions(data)
    byva={r["va"]:r for r in rows}

    print("[Phase6R54] XACT ENGINE ROOT LIFECYCLE / NULL-ROOT USE AUDIT")
    print(f"[Phase6R54] source={args.source} translated_bodies={len(rows)}")
    print("[Phase6R54] HARDWARE write[1]: [0028836C]=01B5C320")
    print("[Phase6R54] HARDWARE write[2]: [0028836C]=00000000")
    print("[Phase6R54] HARDWARE after clear: RtlFreeHeap allocation=01B5C320 result=1")
    print("[Phase6R54] HARDWARE read[0028836C]=0 then read[00000010]=00041D90")
    print("[Phase6R54] HARDWARE XACT->FBE2->F992->F78F->A52AD->A41EE fault EC83F0E4")
    print("[Phase6R54] Safety: NO root reinsertion, NO freed-pointer reuse, NO fault bypass")
    print("[Phase6R54] source_mutation=0 XDK_build=0 Xbox_run=0")

    print("[Phase6R54] 1/4 TARGET FUNCTION BODIES")
    for va in FOCUS:
        row=byva.get(va)
        if row is None:
            print(f"[Phase6R54] Missing generated sub_{va:08X}")
        else:
            block(row)

    print("[Phase6R54] 2/4 GUEST XACT GLOBAL DIRECT REFERENCES")
    owners=[]
    for row in rows:
        ln=row["body"].splitlines()
        matches=[(i,line) for i,line in enumerate(ln)
                 if any(token in line for token in TEXT_MARKERS)]
        if matches:
            owners.append((row,matches))
    print(f"[Phase6R54] owners_with_literal_global_refs={len(owners)}")
    for idx,(row,matches) in enumerate(owners):
        print(f"[Phase6R54] GLOBAL OWNER {row['name']} occurrences={len(matches)}")
        if idx<MAX_GLOBAL_OWNERS:
            for site,_ in matches[:6]:
                block(row,site,pre=13,post=13)
        else:
            print("[Phase6R54] further owner contexts elided")

    print("[Phase6R54] 3/4 INIT, TEARDOWN AND STREAM DIRECT CALLERS")
    for call in CALL_MARKERS:
        calls=[]
        for row in rows:
            ls=row["body"].splitlines()
            calls.extend((row,i) for i,line in enumerate(ls) if call in line)
        print(f"[Phase6R54] call={call} owner_count={len(calls)}")
        for row,i in calls[:MAX_CALLERS]:
            block(row,i,pre=28,post=30)
        if len(calls)>MAX_CALLERS:
            print(f"[Phase6R54] {len(calls)-MAX_CALLERS} caller contexts omitted")

    print("[Phase6R54] 4/4 ANY TRANSLATED DIRECT WRITES / READS OF 0x28836C")
    n=0
    for row,matches in owners:
        for i,line in matches:
            if "0x28836C" not in line and "0x0028836C" not in line:continue
            op=("WRITE" if re.search(r"(?:write32|WRITE32)\(",line)
                else "READ" if re.search(r"(?:read32|READ32)\(",line)
                else "OTHER")
            n+=1
            print(f"[Phase6R54] {op}: {row['name']} line={i+1}: {line.strip()[:240]}")
    print(f"[Phase6R54] literal_global_access_count={n}; dynamic-address writers NOT exhaustively covered")
    print("[Phase6R54] AUDIT COMPLETE: establish why stream creation follows root destruction before a patch")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
