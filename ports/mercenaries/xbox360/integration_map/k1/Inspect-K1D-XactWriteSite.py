#!/usr/bin/env python3
"""K1D: read-only exact source context for the K1C 00041D70 write witness.

Real Xbox: K1C central write32 address=00041D70 before=00041D59,
value=01B672D8, guest_va=0027DD0C, then READ32 EFEE0EC4
at tick 27029593. The recorded VA is a last-tick location, not
necessarily the exact store instruction. Do NOT guess a pointer repair.

This inspects the already-generated 64 true translation units,
without rebuilding or writing any source file.
"""
from __future__ import annotations
import argparse
import hashlib
import re
from pathlib import Path

K1C="P6K1C-EXACT-WRITE-SITE-VA-20261030"
VA="0027DD0C"
HEX="0x"+VA
LABEL=re.compile(r"(?im)^[ \t]*loc_0*27DD0C[ \t]*:")
TICK=re.compile(r"(?i)\bPHASE4C_BUDGET_TICK\s*\(\s*0x0*27DD0Cu?\s*\)")
TARGET=re.compile(r"(?i)(?<![0-9a-f])(?:loc_|0x)?0*27DD0C(?:u|ul)?(?![0-9a-f])")
FUNCTION=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_[0-9A-Fa-f]{8}\s*\(")
OP=re.compile(r"\b(?:GUEST_WRITE(?:8|16|32|64|128)|recomp_guest_write(?:8|16|32|64|128)|phase6ch_apu_write(?:8|16|32)|GUEST_READ(?:8|16|32))\s*\(")
ADDR=re.compile(r"(?i)(?:\b0x0*41D70u?\b|\bloc_0*41D70\b)")
OTHER_TAGS=("RtlAllocateHeap", "DSOUND", "XACTENG")


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def context(lines:list[str], hit:int, before:int, after:int)->list[str]:
    start=max(0,hit-before)
    end=min(len(lines),hit+after+1)
    return [f"{i+1:7d}: {lines[i]}" for i in range(start,end)]


def inspect(main:Path,shards:Path)->str:
    main=main.resolve()
    shards=shards.resolve()
    cpp=sorted(shards.glob("translated_*.cpp"))
    runtime=shards/"translated_runtime.h"
    if len(cpp)!=64 or not runtime.is_file() or not main.is_file():
        raise ValueError("requires K1C main, generated runtime header and exactly 64 TrueTU .cpp files")
    header=main.read_text(encoding="utf-8",errors="replace")
    if header.count(K1C)!=1 or header.count("K1C WRITE SITE:")!=5:
        raise ValueError("K1C staged main identity incorrect or duplicated")
    output=[
        "K1D READ-ONLY TRANSLATED SOURCE PROVENANCE",
        "Evidence: K1C Xbox: WRITE32 guest[00041D70] from 00041D59 to 01B672D8",
        "Heap: RtlAllocateHeap size=2400 returned 01B672B0; new value = heap+0x28",
        "K1C last-tick guest_va=0027DD0C; broad trace_caller=0023A3CE",
        "Hard stop READ32 EFEE0EC4 at ticks=27029593, trace=1072569",
        "Retail XBE .text VA 00011000 through 0025561B includes 00041D70.",
        "K1C VA 0027DD0C is in XACTENG 0027D5C0..0028862F.",
        "Caution: last-tick VA is not a proven exact instruction PC.",
        "Do not overwrite pointers, fake APU/MMIO, or bypass the memory hard fence.",
        "Source main: "+str(main),
        "Translated shards: "+str(shards),
        "",
        "## EXACT guest VA occurrences in generated 64 TrueTU sources",
    ]
    va_hits=[]
    label_hits=[]
    nearest=[]
    for path in cpp:
        lines=path.read_text(encoding="utf-8",errors="replace").splitlines()
        for index,line in enumerate(lines):
            if TARGET.search(line) or LABEL.search(line) or TICK.search(line):
                va_hits.append((path.name,index+1,line.strip()))
                if LABEL.search(line) or TICK.search(line):
                    label_hits.append((path.name,index+1))
                output.extend([
                    "",
                    f"--- {path.name}:{index+1} {line.strip()} ---",
                    *context(lines,index,65,110),
                ])
                start=max(0,index-140)
                recent=[(j,lines[j].strip()) for j in range(start,index) if FUNCTION.match(lines[j])]
                if recent:
                    nearest.append((path.name,index+1,recent[-1][0]+1,recent[-1][1]))
        # Include source explicit pointers to address 00041D70 in the same shard.
        explicit=[(i,line.strip()) for i,line in enumerate(lines) if ADDR.search(line)]
        if explicit:
            output.extend(["",f"## Code/data address 00041D70 references in {path.name}"])
            for index,line in explicit[:6]:
                output.extend([f"{path.name}:{index+1} {line}",*context(lines,index,6,10)])
    output.extend(["",f"VA lexical hits={len(va_hits)}",f"Exact label/tick candidates={len(label_hits)}"])
    for hit in nearest: output.append("Nearby function declaration (heuristic): "+repr(hit))
    if not va_hits:
        output.extend(["NO EXACT MATCH to 0027DD0C in generated shards.",
                       "The tracker might be stale or the generated source VA shape differs.",
                       "Search all generated sources for nearby VA 0027DDxx without changing code."])
    output.extend(["",
                   "## Interpretation / what to return",
                   "Provide the source window around loc_0027DD0C / PHASE4C_BUDGET_TICK",
                   "and the closest GUEST_WRITE32 instruction/related register arithmetic.",
                   "An executed writer is confirmed, but source correlation is STILL REQUIRED.",
                   "The 64 compiled shards and runtime header must not be modified."])
    return "\n".join(output)+"\n"


def run(main:Path,shards:Path,out:Path):
    all_paths=[main.resolve(),(shards/"translated_runtime.h").resolve(),
              *(f.resolve() for f in sorted(shards.glob("translated_*.cpp")))]
    if out.resolve() in all_paths:
        raise ValueError("refuse to overwrite original source")
    if len(all_paths)!=66:
        raise ValueError("source count mismatch: expected main + header + 64 shards")
    hashes={f:sha(f) for f in all_paths}
    result=inspect(main,shards)
    out.parent.mkdir(parents=True,exist_ok=True)
    out.write_text(result,encoding="utf-8")
    for f,old in hashes.items():
        if sha(f)!=old:
            raise RuntimeError(f"source mutated while auditing: {f}")
    print("[K1D-SOURCE] PASS: 64 TrueTU files + runtime checked, no guest/XDK mutation")
    print("[K1D-SOURCE] Exact K1C 0027DD0C guest VA contexts extracted.")
    print("[K1D-SOURCE] Report="+str(out))


def main_cli():
    ap=argparse.ArgumentParser()
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--shards",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    run(a.main,a.shards,a.out)


if __name__=="__main__":
    main_cli()
