#!/usr/bin/env python3
"""Pixel batch source proof: exact A3A5A source and APU bridge identities.

This is a read-only bounded source review for the K1S frontier and the
existing phase6ch_apu_* routing, before any corrective binary is built.
No game payload copied, no C++ written, no Xbox or XDK invocation.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

TARGET="sub_002A3A5A"
HELPERS=("recomp_apu_read32","recomp_apu_write32",
         "phase6ch_apu_read32","phase6ch_apu_write32")
FUNCTION_RE=re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?(?:__forceinline[ \t]+)?"
    r"(?:void|uint32_t|DWORD|unsigned int)[ \t]+"
    r"(?P<name>[A-Za-z_][A-Za-z0-9_]*)[ \t]*"
    r"\([^;{}]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
DECL_RE=re.compile(r"(?m)^[ \t]*(?:(?:static|inline|__forceinline)[ \t]+)*"
                   r"(?:(?:void|DWORD|uint32_t|unsigned[ \t]+int))[ \t]+"
                   r"(?P<name>(?:recomp_apu|phase6ch_apu)_(?:read|write)32)"
                   r"[ \t]*\([^;\n]*\)[ \t]*(?:;|\{)")
COMMENT_RE=re.compile(r"\b(?:recomp_apu|phase6ch_apu)_(?:read|write)32\s*\(")
CALL_RE=re.compile(r"\bsub_[0-9A-Fa-f]{8}\s*\(\s*\)")


def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def mask_noncode(text:str)->str:
    # Preserve string/comment lengths to correlate source offsets.
    out=list(text)
    i=0
    n=len(text)
    while i<n:
        if text.startswith("//",i):
            j=text.find("\n",i)
            if j<0:j=n
            for k in range(i,j):out[k]=" "
            i=j
            continue
        if text.startswith("/*",i):
            j=text.find("*/",i+2)
            j=n-2 if j<0 else j
            for k in range(i,min(j+2,n)):
                if out[k]!="\n":out[k]=" "
            i=min(j+2,n)
            continue
        if text[i] in ('"',"'"):
            q=text[i]
            j=i+1
            while j<n:
                if text[j]=="\\":
                    j+=2
                    continue
                if text[j]==q:
                    j+=1
                    break
                j+=1
            for k in range(i,min(j,n)):
                if out[k]!="\n":out[k]=" "
            i=j
            continue
        i+=1
    return "".join(out)


def closing_brace(masked:str,opening:int)->int:
    depth=0
    for i in range(opening,len(masked)):
        if masked[i]=="{":depth+=1
        elif masked[i]=="}":
            depth-=1
            if depth==0:return i+1
    raise ValueError("Unterminated source definition")


def read_definition(text:str,name:str)->tuple[str,int]|None:
    masked=mask_noncode(text)
    matches=[m for m in FUNCTION_RE.finditer(masked) if m.group("name")==name]
    if not matches:return None
    if len(matches)!=1:
        raise ValueError(f"Duplicate active definition for {name}")
    m=matches[0]
    opening=masked.find("{",m.start(),m.end())
    end=closing_brace(masked,opening)
    return text[m.start():end],text.count("\n",0,m.start())+1


def excerpts(text:str,term:str,window:int=3,max_matches:int=8)->list[str]:
    arr=text.splitlines()
    matches=[]
    for i,row in enumerate(arr):
        if term in row:
            lo=max(0,i-window);hi=min(len(arr),i+window+1)
            matches.append("\n".join(f"{j+1:6d} {arr[j]}" for j in range(lo,hi)))
            if len(matches)>=max_matches:break
    return matches


def report(args:argparse.Namespace)->str:
    planpath=args.plan.resolve()
    plan=json.loads(planpath.read_text(encoding="utf-8-sig"))
    if (plan.get("marker")!="PIXEL-BATCH-ROOTED-CLOSURE-20261030"
        or plan.get("intent")!="AUTHENTIC_GUEST_DISPLAY_CALL_ONLY"
        or plan.get("hardware_seed",{}).get("first_unhandled_direct_target")!="0x002A3A5A"
        or plan.get("verified_baseline",{}).get("marker")
           !="K1S-HALGETVECTOR44-SAVED-ESI-20261030"):
        raise ValueError("Not the verified K1S pixel batch report")
    frontier=plan.get("frontier") or {}
    if frontier.get("va")!="0x002A3A5A" or frontier.get(
        "classification")!="EXACT_GENERATED_FUNCTION":
        raise ValueError("A3A5A is not the exact generated live frontier")
    source_file=frontier.get("source_file")
    if not isinstance(source_file,str) or not re.fullmatch(
            r"recomp_[A-Za-z0-9_.-]+\.c",source_file):
        raise ValueError("Unsafe or absent local original C filename")
    generated=(args.generated_root/source_file).resolve()
    root=args.generated_root.resolve()
    if root not in generated.parents or not generated.is_file():
        raise ValueError("Local A3A5A generated original file missing")
    original=generated.read_text(encoding="utf-8",errors="replace")
    item=read_definition(original,TARGET)
    if not item:raise ValueError("No exact A3A5A implementation in original C")
    body,first=item
    if len(body)>120000:
        raise ValueError("A3A5A source exceeds bounded export; investigate manually")
    main=args.main.resolve()
    runtime=args.runtime.resolve()
    for path in (main,runtime):
        if not path.is_file():raise ValueError("Missing local runtime "+str(path))
    sources={
        "main.cpp":main.read_text(encoding="utf-8",errors="replace"),
        "translated_runtime.h":runtime.read_text(encoding="utf-8",errors="replace"),
        source_file:original,
    }
    lines=[
        "PIXEL CONTRACT PROOF — 002A3A5A + GUEST APU ROUTING",
        "LIVE Xbox K1S: DIRECT_FRONTIER 002A3A5A at 27031807 ticks.",
        "Guest display_calls=0; do not synthesize display success.",
        "Offline lexical proof only: no generated guest source modified.",
        "Guest APU helper names alone do NOT prove calling signature or semantics.",
        f"Generated file={source_file} SHA256={sha(generated)}",
        f"Source original function={TARGET} line={first}",
        f"Source body length={len(body)} chars {len(body.splitlines())} lines",
        "","## Original function A3A5A (verbatim from user's locally generated source)",
    ]
    lines.extend(f"{first+i:6d} {row}" for i,row in enumerate(body.splitlines()))
    lines.extend([
        "","## APU helper callsite counts in exact original A3A5A",
    ])
    for name in HELPERS:
        lines.append(f"{name}: {len(re.findall(r'\b'+name+r'\s*\(',mask_noncode(body)))} callsites")
    lines.extend([
        f"Direct translated callees in A3A5A: {', '.join(sorted(set(CALL_RE.findall(mask_noncode(body))))) or '(none)'}",
        "","## Existing runtime helper definitions and original source slices"
    ])
    for name in HELPERS:
        lines.append(f"### {name}")
        for file,text in sources.items():
            if file==source_file and name.startswith("phase6ch_"):
                continue
            try:
                definition=read_definition(text,name)
            except ValueError as exc:
                lines.append(f"  {file}: duplicate definitions: {exc}")
                continue
            if definition:
                fn,lineno=definition
                lines.append(f"  {file}: definition line={lineno}, len={len(fn)}")
                lines.extend("    "+row for row in fn.splitlines()[:115])
                if len(fn.splitlines())>115:lines.append("    [definition truncated after 115 lines]")
            else:
                masked=mask_noncode(text)
                decls=[m.group(0) for m in DECL_RE.finditer(masked)
                       if m.group("name")==name]
                lines.append(f"  {file}: no detected function body; declarations={len(decls)}")
                for d in decls[:3]:lines.append("    "+d)
        lines.append("")
    lines.extend(["## Helper mentions in current main.cpp and translated_runtime.h"])
    for file in ("main.cpp","translated_runtime.h"):
        for name in HELPERS:
            slices=excerpts(sources[file],name,window=2,max_matches=3)
            lines.append(f"### {file} {name} first_matches={len(slices)}")
            lines.extend(slices if slices else ["NO_MATCH"])
    lines.extend([
        "","## Graphics and live-root candidates from the same planner",
    ])
    for row in plan.get("candidate_order",[])[:64]:
        lines.append(
            f"{row.get('va','?')} roots={','.join(row.get('root_reachability',[]))} "
            f"depth={row.get('min_depth','?')} class={row.get('classification','?')} "
            f"support={row.get('status','?')} enclosing={row.get('containing_function')} "
            f"unknown={','.join(row.get('unknown_helper_symbols',[]))}"
        )
    lines.extend([
        "","## Decision gate",
        "Only add A3A5A to a K1S-preserving TrueTU batch once original",
        "recomp_apu_read32/write32 semantics and the existing",
        "phase6ch_apu_read32/write32 guest-memory/fence behavior match.",
        "Mid-function/missing presentation bodies remain hard fences.",
        "A candidate count of 4 is an audit result, not 4 safe functions.",
        "Do not claim 1 display call until logged from the original guest.",
        "NO XDK BUILD. NO OTHER GUEST/MEMORY/CODE CHANGES.",
        "END PIXEL CONTRACT PROOF",
    ])
    return "\n".join(lines)+"\n"


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--plan",type=Path,required=True)
    p.add_argument("--generated-root",type=Path,required=True)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--runtime",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    output=args.out.resolve()
    if any(output==x.resolve() for x in (
        args.plan,args.main,args.runtime)):
        raise ValueError("Cannot overwrite any original build input")
    if (args.generated_root.resolve() in output.parents or
        args.runtime.resolve().parent==output):
        raise ValueError("Cannot export report over original generated code")
    text=report(args)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(text,encoding="utf-8")
    print("[PIXEL-BRIDGE] PASS: exact A3A5A and local APU helper contracts extracted")
    print("[PIXEL-BRIDGE] FULL REPORT="+str(args.out))
    print("[PIXEL-BRIDGE] NO XDK build, no guest code or MMIO changes")

if __name__=="__main__":
    main()
