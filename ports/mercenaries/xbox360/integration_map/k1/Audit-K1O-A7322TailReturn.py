#!/usr/bin/env python3
"""K1O: source-only inspect first A739F child A7322's tail-jump return chain.

Prior facts:
  K1N seven ordinary A739F callees have matching lexical return widths.
  A7322 has no inline return, tail jumps into A7AE8 after POP32 ESI.
  Xbox R72: A19FC -> A739F returns +4 ESP, unexpectedly.
This script DOES NOT prove where the shift originates, and changes no
guest code, registers, memory, source shards, or hardware fences.
"""
from __future__ import annotations
import argparse
import hashlib
import re
from pathlib import Path

FUNC = re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9a-fA-F]{8})"
                  r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
CLOSE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
TAIL = re.compile(r"\bsub_(?P<va>[0-9a-fA-F]{8})\(\);\s*return;\s*/\*\s*tail jmp\s+0x[0-9a-fA-F]+\s*\*/")
RET = re.compile(r"\besp\s*\+=\s*(\d+)\s*;\s*return;\s*/\*\s*ret(?:\s+(\d+))?\s*\*/")
CALL = re.compile(r"\bsub_([0-9a-fA-F]{8})\s*\(\s*\)")
ESP = re.compile(r"\b(?:g_)?esp\s*(?:=|\+=|-=)|\b(?:PUSH32|POP32)\s*\(")
ORIG_SHA = "4ab3cbe137476f77f598e28ed42392d009e84bd8b72e34ed2b27d2f17a13eb92"


def sha(p: Path) -> str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def parse_cpp(files: list[Path]) -> dict[str, tuple[str,int,list[str]]]:
    result: dict[str,tuple[str,int,list[str]]] = {}
    for path in files:
        source = path.read_bytes().decode("utf-8")
        for m in FUNC.finditer(source):
            name = m.group(1).upper()
            end = CLOSE.search(source, m.end())
            if end is None or name in result:
                raise ValueError("Duplicate or unterminated translated function: " + name)
            first = source.count("\n",0,m.start())+1
            result[name] = path.name, first, source[m.start():end.end()].splitlines()
    return result


def compute(files: list[Path], k1n_text: str, k1m_text: str) -> str:
    if ("K1N READ-ONLY A739F NESTED RETURN CLEANUP CONTRACT AUDIT" not in k1n_text
        or "Number of lexical callsite/return mismatches=0" not in k1n_text
        or "SUB_002A7322 | translated_057.cpp" not in k1n_text
        or "status=NO_INLINE_RETURN_OR_MANUAL_CONTROL" not in k1n_text
        or "========== sub_002A739F ==========" not in k1m_text
        or "sub_002A7322();" not in k1m_text):
        raise ValueError("K1N/K1M source evidence gates failed")
    if len(files)!=64 or sha(next(p for p in files if p.name=="translated_029.cpp"))!=ORIG_SHA:
        raise ValueError("Frozen original TrueTU files or SHA do not match K1E")
    funcs = parse_cpp(files)
    parent = "SUB_002A7322"
    if parent not in funcs or funcs[parent][0] != "translated_057.cpp":
        raise ValueError("A7322 owner does not match K1N")
    _, _, lines = funcs[parent]
    tail_calls = [TAIL.search(line) for line in lines if TAIL.search(line)]
    if len(tail_calls)!=1 or tail_calls[0].group("va").upper()!="002A7AE8":
        raise ValueError("Expected exactly one A7322 tail jump to A7AE8")
    result = [
        "K1O READ-ONLY A7322 -> A7AE8 TAIL RETURN CONTRACT",
        "Xbox R72: A19FC->A739F entry-exit ESP 008BF8B4 -> 008BF8B8, abnormal +4.",
        "K1N: seven standard A739F child returns match lexical argument cleanup.",
        "A7322 is the first A739F child; its return is a tail jump to A7AE8.",
        "K1O inspects original tail chain and source, not a live-branch execution proof.",
        f"Frozen owner translated_029.cpp SHA256={sha(next(p for p in files if p.name=='translated_029.cpp'))}",
        f"Indexed bodies={len(funcs)}",
        "",
        "## Tail transfer chain (max 8 nodes; no inferred runtime branches)",
    ]
    seen=set()
    current=parent
    for depth in range(8):
        if current in seen:
            result.append("CYCLE DETECTED at "+current)
            break
        seen.add(current)
        if current not in funcs:
            result.append("MISSING TRANSLATED BODY "+current)
            break
        owner, first, body = funcs[current]
        tails=[(first+i,TAIL.search(line).group("va").upper(),line.strip())
               for i,line in enumerate(body) if TAIL.search(line)]
        returns=[(first+i,int(m.group(1)),(m.group(2) or "plain"),line.strip())
                 for i,line in enumerate(body) if (m:=RET.search(line))]
        result.append(f"### {current} {owner}:{first}..{first+len(body)-1}")
        for addr,total,native,line in returns:
            result.append(f"  INLINE_RETURN line={addr} esp_increment={total} "
                          f"arg_cleanup={total-4} native_comment_ret={native}: {line}")
        for addr,target,line in tails:
            result.append(f"  TAIL_TRANSFER line={addr} next=SUB_{target}: {line}")
        if not tails:
            result.append("  TERMINAL: no generated tail-jump source marker")
            break
        if len(tails)!=1:
            result.append("  MULTIPLE TAIL TRANSFERS: runtime branch unresolved")
            break
        current="SUB_"+tails[0][1]
    else:
        result.append("Tail chain cap 8 reached; further resolution required")
    result.extend(["","## Original unmodified source: tail chain and nested calls"])
    for name in seen:
        if name not in funcs:
            continue
        owner,first,body=funcs[name]
        result.append(f"### {name} {owner}:{first}")
        for i,line in enumerate(body):
            result.append(f"{first+i:7d} {line}")
        result.append("")
    if "SUB_002A7AE8" not in funcs:
        raise ValueError("Missing A7AE8 target translated body")
    # Include direct nested calls of first helper for subsequent stack-contract proof.
    result.extend(["## Original A7322 nested direct callsites"])
    for i,line in enumerate(lines):
        if CALL.search(line):
            result.append(f"{funcs[parent][1]+i:7d} {line}")
    result.extend([
        "", "Next: assess whether A7AE8 epilogue consumes an unexpected word.",
        "If terminal width is correct, instrument A739F's first child boundary",
        "versus its remaining children before applying any ESP adjustment.",
        "A lexical tail return contract does NOT by itself prove the first",
        "hardware ESP +4 occurred at this exact call.",
        "NO XDK build / NO guest changes / NO hard fence relaxation.",
        "END K1O"
    ])
    return "\n".join(result)+"\n"


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-shards",type=Path,required=True)
    p.add_argument("--k1n-report",type=Path,required=True)
    p.add_argument("--k1m-report",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    source_dir=args.original_shards.resolve()
    files=sorted(source_dir.glob("translated_*.cpp"))
    paths=[*files,args.k1n_report.resolve(),args.k1m_report.resolve()]
    out=args.out.resolve()
    if out in {p.resolve() for p in paths} or source_dir in out.parents:
        raise ValueError("K1O cannot replace frozen original sources or audit inputs")
    identities={p:sha(p) for p in paths}
    result=compute(
        files,
        args.k1n_report.read_text(encoding="utf-8-sig"),
        args.k1m_report.read_text(encoding="utf-8-sig")
    )
    if any(sha(p)!=prior for p,prior in identities.items()):
        raise RuntimeError("K1O frozen audit inputs changed while reading")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(result,encoding="utf-8")
    print("[K1O] PASS: frozen 64 TrueTUs, A7322->A7AE8 tail body and return contract")
    print("[K1O] SOURCE ONLY; NO XDK build, Xbox boot, or guest/fence changes")
    print("[K1O] Report="+str(args.out))


if __name__=="__main__":
    main()
