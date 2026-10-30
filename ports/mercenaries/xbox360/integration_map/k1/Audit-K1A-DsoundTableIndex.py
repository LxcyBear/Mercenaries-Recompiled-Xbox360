#!/usr/bin/env python3
"""Read-only K1A DSOUND page-table pointer ancestry, frozen R59 translator.

Observed K1A Xbox READ32 at 002A6624, guest EFEE0EC4. Only emit source
evidence; do not synthesize memory values, accept unknown addresses, or alter
generated game code. Designed for locally retained R59 translation source.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

MARKER="P6DQ R59 FC4A ABI RESTORE:"
FUNCTION="sub_002A6595"
REQUIRED_LABELS=("loc_002A6607: ;","loc_002A6617: ;","loc_002A6624: ;")
EXPECTED_STMTS=(
    "ecx = phase6ch_apu_read32(ebp + -4);",
    "edx = phase6ch_apu_read32(ebp + -12);",
    "esi = ecx + edx * 8;",
    "phase6ch_apu_write32(esi + 4, phase6ch_apu_read32(esi + 4) & 0);",
)
LOCAL_PATTERNS=(
    re.compile(r"ebp\s*\+\s*-?(?:4|8|12)(?:\b|\s*\))"),
    re.compile(r"\b(?:esi|ecx|edx|ebp)\s*="),
    re.compile(r"PHASE6DJ_ICALL_SAFE|0x2DBE5C|sub_002A6595|002A0AF1"),
)

def function_body(source:str, name:str)->tuple[int,list[str]]:
    lines=source.splitlines()
    pattern=re.compile(r'^\s*(?:static\s+)?void\s+'+re.escape(name)+r'\s*\(\s*void\s*\)\s*(?:\{.*)?$')
    matches=[]
    for i,line in enumerate(lines):
        if not pattern.match(line):continue
        if '{' in line:matches.append(i)
        elif i+1<len(lines) and lines[i+1].lstrip().startswith('{'):
            matches.append(i)
    if len(matches)!=1:
        raise ValueError(f"{name}: require exactly one definition, found {len(matches)}")
    first=matches[0]
    depth=0;opened=False
    for j in range(first,min(first+3000,len(lines))):
        depth+=lines[j].count('{')-lines[j].count('}')
        if '{' in lines[j]:opened=True
        if opened and depth==0:
            return first+1,lines[first:j+1]
    raise ValueError(f"{name}: unbalanced function body")

def analyze(source:str)->str:
    if MARKER not in source:
        raise ValueError("wrong R59 identity; refusing unknown generated source")
    base,body=function_body(source,FUNCTION)
    scope="\n".join(body)
    for text in REQUIRED_LABELS+EXPECTED_STMTS:
        if scope.count(text)!=1:
            raise ValueError(f"exact source expression missing/duplicated: {text}")
    ecx=0x024A8000
    edx=0xFDB471D8
    esi=0xEFEE0EC0
    assert (ecx + edx * 8)&0xffffffff == esi
    edx_signed=edx-(1<<32) if edx&(1<<31) else edx
    output=[
        "# K1A READ32: complete DSOUND table setup and index provenance",
        "HARDWARE: tick=27029593 VA=002A6624 read=EFEE0EC4 ESI=EFEE0EC0.",
        f"HARDWARE POST-CALL: ECX={ecx:08X} EDX={edx:08X} signed_EDX={edx_signed}.",
        f"Arithmetic check: (ECX + EDX*8) & FFFFFFFF = {((ecx+edx*8)&0xffffffff):08X}.",
        "CRITICAL CAVEAT: these are hard-stop register values AFTER the",
        "MmGetPhysicalAddress indirect call. Matching them to the prior LEA",
        "is consistent but does NOT prove their pre-call values were identical.",
        "Guest base 024A8000 appeared as previous MmGetPhysicalAddress input;",
        "01B6DA10 was the latest successful physical-address return.",
        "",
        "## Entire R59 sub_002A6595 (all source, no truncation)",
        f"Starts at source line {base}, total {len(body)} lines.",
    ]
    output.extend(f"{base+i:07d}: {v}" for i,v in enumerate(body))
    output+=["","## EBP locals / index / indirect call references within function"]
    for i,line in enumerate(body):
        if any(p.search(line) for p in LOCAL_PATTERNS):
            output.append(f"{base+i:07d}: {line.strip()}")
    lines=source.splitlines()
    output+=["","## Upstream translated caller references"]
    caller_needles=("sub_002A6595();","0x002A6595u","loc_002A0AF1:")
    for needle in caller_needles:
        hits=[i for i,line in enumerate(lines) if needle in line]
        output.append(f"{needle}: {len(hits)} occurrence(s)")
        for i in hits[:5]:
            lo=max(0,i-14);hi=min(len(lines),i+20)
            output.append(f"--- source lines {lo+1}..{hi} ---")
            output.extend(f"{k+1:07d}: {lines[k]}" for k in range(lo,hi))
    output+=["","## Interpretation / next gate",
             "The index in [EBP-12] is suspect. Inspect how the function",
             "initializes that local and whether an intervening host callback",
             "or stack-repair mutates it. Compare register + EBP-local values",
             "immediately BEFORE the multiplication and before the MM173 call.",
             "Do not normalize, clamp, or whitelist the resulting guest address.",
             "This is a read-only source investigation, not a compatibility fix."]
    return "\n".join(output)+"\n"

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if a.source.resolve()==a.out.resolve():
        p.error("refusing in-place source mutation")
    if not a.source.is_file():
        p.error("local R59 generated source not found: "+str(a.source))
    out=analyze(a.source.read_text(encoding="utf-8",errors="replace"))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(out,encoding="utf-8")
    print("[K1A-DSOUND] PASS: exact sub_002A6595 and callers extracted; no source mutation")
    print("[K1A-DSOUND] FAULT EFEE0EC4 remains HARD FENCED")
    print("[K1A-DSOUND] report="+str(a.out))

if __name__=="__main__":main()
