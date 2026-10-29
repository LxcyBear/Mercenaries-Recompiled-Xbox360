#!/usr/bin/env python3
"""R74: zero-build pinpoint of FE80200C APU XGSCNT guest READ32 ownership.

R72 hardware stopped at READ32 FE80200C after successful R72 pool repair.
R73 established read32 wrapper, fallback and register identity, but its
source dump did not prove the failing instruction uses that wrapper.
Only after proving the path may we install a narrow XGSCNT read model.
Reference xemu: NV_PAPU_XGSCNT=0x200C; read=ep_frame_div*32.
No source mutation, no constant-zero return, no unrelated MMIO changes.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

TARGET=0xFE80200C
TARGET_SIGNED=TARGET-(1<<32)
VARIANTS=(
 "FE80200C","fe80200c","4269809676","-25157620",
 "0x200C","0x200c","0x0200C","0x0200c",
)
NUMERIC_PATTERN=re.compile(
 r"(?i)(0xFE80200C\\b|4269809676\\b|-25157620\\b|"
 r"0xFE802000\\b|0x200C\\b|0x0200C\\b)")
MEM_PATTERN=re.compile(r"(?i)(GUEST_READ32|recomp_guest_read32|phase6ch_apu_read32|"
 r"PHASE6.*READ32|\\bMEM32\\s*\\(|0xFE8020|-25157620)")
MAIN_NAMES=(
 "phase6ch_apu_core_range",
 "phase6ch_apu_shadow_read",
 "phase6ch_apu_read32",
 "recomp_guest_read32",
 "GUEST_READ32",
 "phase6ch_apu_write32",
)
def context(lines,idx,before=9,after=15,prefix=""):
    a=max(0,idx-before)
    b=min(len(lines),idx+after+1)
    for j in range(a,b):
        print(f"[Phase6R74] {prefix}{j+1:05d}: {lines[j]}")

def cached_main(text):
    lines=text.splitlines()
    print("[Phase6R74] SECTION 2/3: router and read helpers (exact cached main)")
    for name in MAIN_NAMES:
        hits=[i for i,s in enumerate(lines) if name in s]
        print(f"[Phase6R74] SYMBOL {name} total_text_hits={len(hits)}")
        # Locate definitions first, otherwise nearby macro declarations.
        if name=="GUEST_READ32":
            definitions=[i for i,s in enumerate(lines)
                         if re.search(r"#\\s*define\\s+GUEST_READ32\\b",s)]
        else:
            definitions=[i for i,s in enumerate(lines)
                         if re.search(r"(?:bool|uint\\d+_t|DWORD|int|void)\\s+"+
                            re.escape(name)+r"\\s*\\(",s)]
        if definitions:
            for i in definitions[:2]:
                print(f"[Phase6R74] DEFINITION {name} at line={i+1}")
                # 64 lines sufficient for source routing / branching;
                # show 140 for 32-bit MMIO read implementation.
                context(lines,i,before=6,after=138 if name=="phase6ch_apu_read32" else 78,
                        prefix="MAIN ")
        else:
            print(f"[Phase6R74] SYMBOL {name}: no direct definition in cached main")
            if hits and name not in ("phase6ch_apu_shadow_read","GUEST_READ32"):
                context(lines,hits[0],before=3,after=12,prefix="MAIN ")
    print("[Phase6R74] SECTION 3/3: exact main references to FE80200C and core address space")
    matched=[i for i,l in enumerate(lines) if NUMERIC_PATTERN.search(l)]
    print(f"[Phase6R74] MAIN explicit numeric register matches={len(matched)}")
    for i in matched[:24]:
        context(lines,i,before=3,after=5,prefix="MAIN ")
    print(f"[Phase6R74] main_extra_matches_omitted={max(0,len(matched)-24)}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",required=True,type=Path)
    ap.add_argument("--cached-main",required=True,type=Path)
    a=ap.parse_args()
    for p in (a.source,a.cached_main):
        if not p.is_file():raise SystemExit(f"[Phase6R74] required file missing: {p}")
    source=a.source.read_text(encoding="utf-8",errors="replace")
    maintext=a.cached_main.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in source:
        raise SystemExit("[Phase6R74] wrong R59 source marker")
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in maintext:
        raise SystemExit("[Phase6R74] wrong TrueTU main identity marker")
    rows=functions(source)
    print("[Phase6R74] ===============================================================")
    print("[Phase6R74]   EXACT FE80200C READ PROVENANCE / MMIO ROUTING (ZERO BUILD)")
    print("[Phase6R74] ===============================================================")
    print(f"[Phase6R74] source_functions={len(rows)}")
    print(f"[Phase6R74] physical_apu_address=0x{TARGET:08X} signed={TARGET_SIGNED} offset=0x200C")
    print("[Phase6R74] R72 XACT init SUCCESS; R72 stopped guest READ32 FE80200C")
    print("[Phase6R74] R73 xemu hardware name: NV_PAPU_XGSCNT, audio sample counter")
    print("[Phase6R74] No Xbox build, shard regeneration, source mutations or MMIO overrides")
    print("[Phase6R74] SECTION 1/3: translated function numeric references")
    matches=[]
    for row in rows:
        ls=row["body"].splitlines()
        for i,l in enumerate(ls):
            if NUMERIC_PATTERN.search(l):
                matches.append((row["va"],i,ls))
    print(f"[Phase6R74] translated numeric hardware references={len(matches)}")
    for va,i,ls in matches[:60]:
        print(f"[Phase6R74] CANDIDATE sub_{va:08X} line={i+1} "
              f"source={ls[i].strip()[:190]}")
        context(ls,i,before=7,after=10,prefix=f"sub_{va:08X} ")
    print(f"[Phase6R74] candidate_matches_omitted={max(0,len(matches)-60)}")
    if not matches:
        print("[Phase6R74] NO LITERAL ADDRESS: likely computed dynamic MMIO read")
        print("[Phase6R74] A read path may require guest READ32 trap rather than one function substitution")
    cached_main(maintext)
    print("[Phase6R74] NEXT: patch ONLY verified route (raw guest trap OR APU wrapper)")
    print("[Phase6R74] XGSCNT must be clock/frame driven, not fixed zero")
    print("[Phase6R74] Keep all other APU/VP/unknown MMIO reads hard-fenced.")
    print("[Phase6R74] AUDIT COMPLETE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
