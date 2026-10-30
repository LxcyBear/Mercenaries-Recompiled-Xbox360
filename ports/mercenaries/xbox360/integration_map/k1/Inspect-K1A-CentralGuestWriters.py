#!/usr/bin/env python3
"""K1A: read-only central guest-writer and two exact code-address source sites.

Does not edit, patch, stage, compile, rebuild or execute guest code. The
original Xbox log showed live [00041D70]=01B672D8 vs retail 00041D59,
while a watch on phase6ch_apu_write* recorded no overlap. This extracts
the exact source surrounding two literal references to that guest address
and the actual central writer signatures/macros in the staged translation.

The report is source evidence, NOT proof a write happened at runtime.
"""
from __future__ import annotations
import argparse
import hashlib
import re
from pathlib import Path

CLOCK="P6K1A-BOOT-CLOCK128-304-305-20261029"
WATCH="P6K1A-DSOUND-OBJECT-WRITER-WATCH-20261030"
ADDRESS=re.compile(r"(?i)\b(?:0x)?0*41D7[0-7]\b")
DEFINITION=re.compile(
    r"(?i)^\s*(?:#\s*define\s+)?(?:"
    r"GUEST_WRITE(?:8|16|32)\b|recomp_guest_write(?:8|16|32)\b|"
    r"guest_write(?:8|16|32)\b|phase6ch_apu_write(?:8|16|32)\b)"
)
FUNCTION_SIGNATURE=re.compile(
    r"(?i)^\s*(?:(?:static|inline|extern|__forceinline|"
    r"__inline|constexpr)\s+){0,4}"
    r"(?:void|uint8_t|uint16_t|uint32_t|DWORD|BOOL)\s+"
    r"(?:recomp_guest_write|guest_write|phase6ch_apu_write)"
    r"(?:8|16|32)\s*\("
)
MACRO=re.compile(r"(?i)^\s*#\s*define\s+(?:GUEST_WRITE|recomp_guest_write)(?:8|16|32)\b")
LIKELY_BASE=re.compile(
    r"(?i)^\s*(?:static\s+)?(?:inline\s+)?(?:void|uint32_t|bool)\s+"
    r"(?:recomp_guest_write|guest_write|phase6ch_apu_write)"
)
LABEL=re.compile(r"(?i)^\s*(?:loc_|PHASE4C_BUDGET_TICK\()0*[0-9a-f]{6,8}")
USAGE=re.compile(
    r"(?i)\b(?:GUEST_WRITE|recomp_guest_write|guest_write)"
    r"(?:8|16|32)\s*\("
)

def excerpt(lines:list[str],index:int,before:int,after:int)->list[str]:
    first=max(0,index-before)
    end=min(len(lines),index+after+1)
    return [f"{i+1:7d}: {lines[i].rstrip()}" for i in range(first,end)]

def digest(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()

def analyze(main:Path,shards:Path)->str:
    main=main.resolve()
    shards=shards.resolve()
    runtime=shards/"translated_runtime.h"
    owners=sorted(shards.glob("translated_*.cpp"))
    if len(owners)!=64:
        raise ValueError(f"expected exactly 64 TrueTU shards, found {len(owners)}")
    if not runtime.is_file() or not main.is_file():
        raise ValueError("missing staged K1A main or translated_runtime.h")
    source=main.read_text(encoding="utf-8",errors="replace")
    if source.count(CLOCK)!=1:
        raise ValueError("K1A clock boot identity missing or duplicated")
    combined=source+runtime.read_text(encoding="utf-8",errors="replace")
    if combined.count(WATCH)!=3:
        raise ValueError("writer-watch source identity missing or duplicated")
    lines=[
        "K1A CENTRAL WRITE SOURCE PROVENANCE — OFFLINE, READ ONLY",
        f"main={main}",f"runtime={runtime}",f"shards={shards}",
        "Expected retail text DWORD[00041D70]=00041D59;",
        "previous observed live DWORD[00041D70]=01B672D8.",
        "NOTE: lexical references are NOT proof of an executed write.",
        "",
        "## Explicit 00041D70–00041D77 references in 64 TrueTU files",
    ]
    explicit=[]
    files=[(f,f.read_text(encoding="utf-8",errors="replace").splitlines()) for f in owners]
    for path,content in files:
        for j,line in enumerate(content):
            if ADDRESS.search(line):
                explicit.append((path,j))
                lines.extend(["",f"--- {path.name}:{j+1} ---",
                              *excerpt(content,j,16,20)])
    lines.append(f"\nTotal literal references = {len(explicit)}")
    lines.append("Expected original coverage audit count = 2 (file data may differ).")
    lines.append("\n## Main and runtime: central writer declarations/definitions/macros")
    main_content=source.splitlines()
    runtime_content=runtime.read_text(encoding="utf-8",errors="replace").splitlines()
    for name,content in (("main.cpp",main_content),
                         ("translated_runtime.h",runtime_content)):
        hits=[]
        for i,line in enumerate(content):
            if MACRO.match(line) or FUNCTION_SIGNATURE.match(line) or LIKELY_BASE.match(line):
                hits.append(i)
        lines.extend(["",f"--- {name}: {len(hits)} potential definition sites ---"])
        for i in hits[:60]:
            lines.extend([f"\n{name}:{i+1}",*excerpt(content,i,4,25)])
        if not hits:
            lines.append("No matched definition; broader signatures follow.")
            broad=[i for i,line in enumerate(content)
                   if "GUEST_WRITE32" in line or "recomp_guest_write32" in line]
            for i in broad[:7]:
                lines.extend([f"\n{name}:{i+1}",*excerpt(content,i,3,9)])
    lines.extend(["","## Writer invocation distributions (lexical)",
                  "Only lexical call sites. Macro expansions may route differently."])
    for label,pattern in (("GUEST_WRITE/recomp_guest_write",USAGE),
                          ("APU helpers",re.compile(
                              r"\bphase6ch_apu_write(?:8|16|32)\s*\("))):
        for name,content in (("main.cpp",main_content),
                             ("translated_runtime.h",runtime_content)):
            count=sum(len(pattern.findall(s)) for s in content)
            lines.append(f"{label} {name}: {count}")
    lines.extend(["","NEXT DECISION: identify the exact shared GUEST_WRITE implementation",
                  "and the two 00041D70 source contexts before adding a narrow",
                  "pre-write runtime watch. Do NOT guess an MMIO alias,",
                  "whitelist EFEE0EC4, or patch game memory to force progress."])
    return "\n".join(lines)+"\n"

def main_cli()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--shards",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    paths=[args.main.resolve(),(args.shards/"translated_runtime.h").resolve(),
           *(f.resolve() for f in args.shards.glob("translated_*.cpp"))]
    if args.out.resolve() in paths:
        p.error("refusing source-file overwrite")
    originals={p:digest(p) for p in paths}
    report=analyze(args.main,args.shards)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(report,encoding="utf-8")
    if any(digest(f)!=h for f,h in originals.items()):
        raise RuntimeError("source hashes changed unexpectedly")
    print("[K1A-WRITESITE] PASS: 64 TrueTU files + central runtime analyzed")
    print("[K1A-WRITESITE] NO source mutation and NO Xbox build")
    print("[K1A-WRITESITE] Report="+str(args.out))

if __name__=="__main__":main_cli()
