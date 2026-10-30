#!/usr/bin/env python3
"""K1Q: read-only source contract audit for first K1P mismatch A739F->A6B98.

Hardware K1P:
   A739F -> A6B98: before ESP 008BF8A8; after 008BF8AC
   expected ESP delta 0; observed +4 (FIRST failed A739F child).
Hardware R49 inside A6B98:
   after A7B73: ESI=00000000 (expected 008BFFA0),
   EBX=008BFF8C, hinting at an earlier stack/register shift.

This script scans the user's frozen 64 original TrueTUs, not GitHub
generated binaries, and prints original A6B98 and nested callee bodies.
No Xbox, XDK, source changes, stack patches, memory or fence changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

K1E_MARKER="K1E-XACT-TAIL-EDGE-20261030"
K1E_OWNER_SHA="4ab3cbe137476f77f598e28ed42392d009e84bd8b72e34ed2b27d2f17a13eb92"
CALLEES=[
    ("002A7B73",1,1),
    ("002A7605",2,2),
    ("002A7818",3,2),
    ("002A766D",2,3),
    ("002A7598",1,1),
]
FUNC=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9a-fA-F]{8})"
                r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
END=re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
CALL=re.compile(r"\bsub_([0-9a-fA-F]{8})\s*\(\s*\)")
RET=re.compile(r"\besp\s*\+=\s*(\d+)\s*;\s*return\s*;\s*/\*\s*ret(?:\s+(\d+))?\s*\*/")
TAIL=re.compile(r"\bsub_([0-9a-fA-F]{8})\s*\(\s*\)\s*;\s*return\s*;\s*/\*\s*tail jmp")
MEM=re.compile(r"\b(?:GUEST_(?:READ|WRITE)|phase6ch_apu_(?:read|write))(?:8|16|32|64)\s*\(",re.I)


def sha(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def index_all(files:list[Path])->dict[str,tuple[str,int,list[str]]]:
    out={}
    for f in files:
        data=f.read_bytes().decode("utf-8")
        for m in FUNC.finditer(data):
            key=m.group(1).upper()
            end=END.search(data,m.end())
            if key in out or end is None:
                raise ValueError("Missing close or duplicate original function "+key)
            first=data.count("\n",0,m.start())+1
            out[key]=(f.name,first,data[m.start():end.end()].splitlines())
    return out


def study(source:Path, manifest:Path, k1n:Path, outfile:Path)->str:
    source=source.resolve();outfile=outfile.resolve()
    originals=sorted(source.glob("translated_*.cpp"))
    heads=sorted(source.glob("*.h"))
    if len(originals)!=64 or not (source/"translated_runtime.h").is_file():
        raise ValueError("Need the original 64 TrueTUs and translated_runtime.h")
    obj=json.loads(manifest.read_text(encoding="utf-8-sig"))
    if (obj.get("marker")!=K1E_MARKER or obj.get("original_shards")!=64
        or obj.get("modified_shards")!=["translated_029.cpp"]
        or Path(obj.get("source_directory","MISSING")).resolve()!=source
        or obj.get("old_owner_sha256","").lower()!=K1E_OWNER_SHA
        or sha(source/"translated_029.cpp")!=K1E_OWNER_SHA):
        raise ValueError("K1E original SHA/manifest provenance mismatch")
    prior=k1n.read_text(encoding="utf-8-sig")
    if not all(term in prior for term in (
        "K1N READ-ONLY A739F NESTED RETURN CLEANUP CONTRACT AUDIT",
        "Indexed translated function bodies=13510",
        "### SUB_002A6B98 (translated_005.cpp:16208..16347",
        "Number of lexical callsite/return mismatches=0"
    )):
        raise ValueError("K1N prior source proof missing; refusing new speculation")
    protected=[*originals,*heads,manifest,k1n]
    if outfile in {p.resolve() for p in protected} or source in outfile.parents:
        raise ValueError("Report must not overwrite frozen TrueTUs")
    hashes={p:sha(p) for p in protected}
    functions=index_all(originals)
    if len(functions)!=13510:
        raise ValueError(f"Unexpected number of original translated bodies {len(functions)}")
    root="SUB_002A6B98"
    if root not in functions:
        raise ValueError("A6B98 missing")
    root_owner,root_first,root_body=functions[root]
    if root_owner!="translated_005.cpp" or root_first!=16208 or len(root_body)!=140:
        raise ValueError("A6B98 original function identity drift")
    if ("P6DQ R49 ESI REPAIR" not in "\n".join(root_body) or
        not any("POP32(esp, ebx);" in s for s in root_body) or
        not any("esp += 4; return; /* ret */" in s for s in root_body)):
        raise ValueError("Expected R49 watcher and normal A6B98 return not present")
    children=[x.upper() for line in root_body for x in CALL.findall(line)]
    expected=[va for va,argc,n in CALLEES for _ in range(n)]
    if sorted(children)!=sorted(expected):
        raise ValueError(f"A6B98 nested direct callsites drift {children}")
    lines=[
        "K1Q READ-ONLY DSOUND A6B98 FIRST CORRUPTED RETURN CHILD AUDIT",
        "K1P Xbox first bad A739F call: A6B98 ESP 008BF8A8->008BF8AC delta +4 expected 0.",
        "K1P previous 4 A739F child edges match expected 0.",
        "R49 A6BB0 (AFTER A7B73) Xbox: raw ESI=00000000 expected 008BFFA0 EBX=008BFF8C.",
        "A6B98 prologue sets EBX=ECX, ESI=EBX+0x14, saves 4 regs;",
        "its epilogue has 4 POP32 instructions then a plain ret.",
        "Source callsite/ret widths are only lexical evidence, not executed branch proof.",
        f"Frozen owner SHA256={K1E_OWNER_SHA}",
        f"Indexed translated function bodies={len(functions)}",
        "", "## A6B98 direct nested callsite and return width contracts",
    ]
    suspect=[]
    for va,argc,num in CALLEES:
        key="SUB_"+va
        if key not in functions:
            raise ValueError(f"Missing A6B98 child {key}")
        owner,first,body=functions[key]
        matches=[(root_first+i,s) for i,s in enumerate(root_body) if ("sub_"+va+"();") in s]
        if len(matches)!=num:
            raise ValueError(f"Incorrect number of A6B98 source callsites for {key}")
        returns=[(first+i,int(m.group(1)),s.strip())
                 for i,s in enumerate(body) if (m:=RET.search(s))]
        tails=[(first+i,m.group(1).upper(),s.strip())
               for i,s in enumerate(body) if (m:=TAIL.search(s))]
        widths=sorted(set(total-4 for _,total,_ in returns))
        if not returns:
            status="NO_INLINE_RETURN_TAIL_OR_OTHER_FLOW"
        elif len(widths)!=1:
            status="MULTIPLE_RETURN_WIDTHS"
        elif widths[0]!=4*argc:
            status="LEXICAL_ARG_CLEANUP_MISMATCH"
            suspect.append(key)
        else:
            status="LEXICAL_RET_WIDTH_MATCH"
        lines.extend([
            f"### {key} owner={owner} first={first} last={first+len(body)-1} body_lines={len(body)}",
            f"callsite_count={len(matches)} argument_dwords={argc} expected_cleanup_bytes={argc*4}",
            f"direct_nested_calls={sum(len(CALL.findall(s)) for s in body)} guest_memory_calls={sum(len(MEM.findall(s)) for s in body)}",
            f"returns={[ (p,total,total-4) for p,total,_ in returns ]} tails={tails}",
            f"status={status}",
        ])
        for line,s in matches:
            lines.append(f"  A6B98 CALL {line}: {s.strip()}")
        for line,total,s in returns:
            lines.append(f"  CHILD EPILOGUE {line}: {s}")
        if key=="SUB_002A7B73":
            lines.append("  FIRST CHILD: R49 ESI repair occurs after this call.")
        lines.append("")
    lines.extend([
        "## Full A6B98 original source with original TrueTU line numbers",
        *[f"{root_first+i:7d} {s}" for i,s in enumerate(root_body)],
        "", "## Full original source of all A6B98 direct callees",
    ])
    for va,argc,num in CALLEES:
        name="SUB_"+va
        owner,first,body=functions[name]
        lines.append(f"### {name} ({owner} line {first})")
        lines.extend(f"{first+i:7d} {s}" for i,s in enumerate(body))
        lines.append("")
    lines.extend([
        "## K1Q decision",
        "Lexical mismatch suspects="+(";".join(suspect) if suspect else "none"),
        "If A7B73 return is correctly shaped, capture ESP immediately",
        "before/after A6B98->A7B73 and subsequent calls on Xbox.",
        "Do not restore ESP or guest registers without locating earliest failure.",
        "Do not build withdrawn experimental K1L.",
        "NO XDK / Xbox; NO source edits; memory fences unchanged.",
        "END K1Q READ ONLY REPORT",
    ])
    if any(sha(p)!=old for p,old in hashes.items()):
        raise RuntimeError("Frozen original file mutated by K1Q")
    return "\n".join(lines)+"\n"


def selftest()->None:
    assert RET.search("    esp += 4; return; /* ret */").group(1)=="4"
    assert RET.search("    esp += 8; return; /* ret 4 */").group(1)=="8"
    assert RET.search("    esp += 16; return; /* ret 12 */").group(1)=="16"
    assert not RET.search("    sub_002A7AE8(); return; /* tail jmp */")
    assert [x.upper() for x in CALL.findall("sub_002A7B73();")]==["002A7B73"]
    print("[K1Q] SYNTHETIC PASS: plain/ret4/ret12 recognized, tail returns excluded")


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--original-shards",type=Path,required=True)
    p.add_argument("--k1e-manifest",type=Path,required=True)
    p.add_argument("--k1n-report",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    selftest()
    result=study(a.original_shards,a.k1e_manifest,a.k1n_report,a.out)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(result,encoding="utf-8")
    print("[K1Q] PASS: first K1P bad A6B98 caller and 5 nested callee return contracts")
    print("[K1Q] PASS: 64 original TrueTUs and manifest unchanged")
    print("[K1Q] READ ONLY: NO XDK build / Xbox test")
    print("[K1Q] Report="+str(a.out))


if __name__=="__main__":
    main()
