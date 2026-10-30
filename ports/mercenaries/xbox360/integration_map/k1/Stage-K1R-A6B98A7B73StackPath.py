#!/usr/bin/env python3
"""K1R host-only Xbox stack-edge witnesses for the first K1P DSOUND bad return.

K1P: A739F -> A6B98 ESP=008BF8A8->008BF8AC (+4, expected 0).
K1Q: All five direct A6B98 callee return widths match their arguments.
R49: A6B98 AFTER A7B73 has unexpected ESI=0 despite expectation EBX+0x14.
Precisely log A6B98's 9 direct child call edges, A7B73's 4 direct calls,
5 indirect calls, and 3 branch/return checkpoints. Do not "fix" ESP/ESI:
the earliest live divergence is not yet proven.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG="K1R-A6B98-A7B73-STACK-PATH-20261030"
BASE="K1P-DSOUND-STACK-EDGE-20261030"
TARGETS={"translated_005.cpp":"sub_002A6B98",
         "translated_044.cpp":"sub_002A7B73"}
# A6B98 declared stack arguments, as verified by the K1Q user source audit.
A6B98_CALLS=(("002A7B73",1,1),("002A7605",2,2),
             ("002A7818",3,2),("002A766D",2,3),("002A7598",1,1))
# A7B73's return contracts NOT yet audited; trace, do not assume cleanup.
A7B73_CALLS=(("002A7440",0,1),("002A74C1",0,1),("002A74A4",2,2))
ENTRY=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9a-fA-F]{8})"
                 r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
END=re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
ICALL_BLOCK=re.compile(r"(?m)^    \{ uint32_t _icall_esp = g_esp;\r?\n"
                       r"(?P<inner>[\s\S]*?)^    \}")
MEM=re.compile(r"\b(?:phase6ch_apu_(?:read|write)|GUEST_(?:READ|WRITE))(?:8|16|32|64|128)\s*\(",re.I)
CALLS=re.compile(r"\bsub_[0-9A-Fa-f]{8}\(\)")
PUSHPOP=re.compile(r"\b(?:PUSH32|POP32)\s*\(")
ICALLS=re.compile(r"\bPHASE6DJ_ICALL_SAFE\s*\(")
ESI_SHAPE=("    PUSH32(esp, ebx);","    PUSH32(esp, ebp);",
           "    PUSH32(esp, esi);","    PUSH32(esp, edi);",
           "    POP32(esp, edi);","    POP32(esp, esi);",
           "    POP32(esp, ebp);","    POP32(esp, ebx);")
CHECKPOINTS={
    "A7B73_BEFORE_POP_ESI": "    POP32(esp, esi);",
    "A7B73_BEFORE_POP_EDI": "    POP32(esp, edi);",
    "A7B73_BEFORE_RET4": "    esp += 8; return; /* ret 4 */",
}


def sha(file:Path)->str:
    return hashlib.sha256(file.read_bytes()).hexdigest()


def function_span(source:str,name:str)->tuple[int,int]:
    matches=[m for m in ENTRY.finditer(source) if m.group(1)==name]
    if len(matches)!=1:
        raise ValueError(f"Expected exactly one implementation of {name}; found {len(matches)}")
    close=END.search(source,matches[0].end())
    if close is None:
        raise ValueError("Unterminated translated function "+name)
    return matches[0].start(),close.end()


def line_ending(source:str)->str:
    crlf=source.count("\r\n")
    if source.count("\r")!=crlf or (crlf and crlf!=source.count("\n")):
        raise ValueError("Original source has mixed line endings")
    return "\r\n" if crlf else "\n"


def call_probe(site:str,statement:str,expected:int|None,nl:str)->str:
    token="k1r_"+site
    # One per-site static visit counter and bounded output; no guest mutation.
    should_log=(f"({token}_n <= 3u || ({token}_delta != {expected}u && {token}_n <= 12u))"
                if expected is not None else f"({token}_n <= 3u)")
    expected_text=f"{expected:08X}" if expected is not None else "UNKNOWN"
    code=[
        "    {",
        f"        /* {TAG}: {site} */",
        f"        const uint32_t {token}_before=esp;",
        f"        const uint32_t {token}_esi_before=esi;",
        f"        const uint32_t {token}_ebx_before=ebx;",
        "        "+statement.strip(),
        f"        const uint32_t {token}_after=esp;",
        f"        const uint32_t {token}_delta={token}_after-{token}_before;",
        f"        static uint32_t {token}_n=0u;",
        f"        ++{token}_n;",
        f"        if {should_log}",
        "        {",
        "            char k1r_line[320];",
        "            sprintf(k1r_line,",
        f'                "K1R CALL {site}: n=%u before=%08X after=%08X delta=%08X expected={expected_text} esi_before=%08X esi_after=%08X ebx_before=%08X ebx_after=%08X edi=%08X",',
        f"                (unsigned){token}_n, (unsigned){token}_before,",
        f"                (unsigned){token}_after, (unsigned){token}_delta,",
        f"                (unsigned){token}_esi_before,(unsigned)esi,",
        f"                (unsigned){token}_ebx_before,(unsigned)ebx,(unsigned)edi);",
        "            trace(k1r_line);",
        "        }",
        "    }",
    ]
    return nl.join(code)


def checkpoint(site:str,nl:str)->str:
    code=[
        "    {",
        f"        /* {TAG}: {site} */",
        f"        static uint32_t k1r_{site}_n=0u;",
        f"        ++k1r_{site}_n;",
        f"        if (k1r_{site}_n <= 4u)",
        "        {",
        "            char k1r_line[252];",
        "            sprintf(k1r_line,",
        f'                "K1R PATH {site}: n=%u esp=%08X ebp=%08X ebx=%08X esi=%08X edi=%08X eax=%08X",',
        f"                (unsigned)k1r_{site}_n, (unsigned)esp,",
        "                (unsigned)ebp, (unsigned)ebx, (unsigned)esi,",
        "                (unsigned)edi, (unsigned)eax);",
        "            trace(k1r_line);",
        "        }",
        "    }",
    ]
    return nl.join(code)


def indirect_probe(site:str,block:str,nl:str)->str:
    """Instrument one original _icall_esp block; don't touch indirect dispatch."""
    if block.count("PHASE6DJ_ICALL_SAFE(")!=1 or block.count("_icall_esp = g_esp")!=1:
        raise ValueError(f"Unexpected indirect call block for {site}")
    token="k1r_"+site
    start="    { uint32_t _icall_esp = g_esp;"
    after="    }"
    if not block.startswith(start) or not block.endswith(after):
        raise ValueError(f"Malformed indirect call block for {site}")
    prefix=[start, f"      /* {TAG}: {site} */",
            f"      const uint32_t {token}_before=esp;",
            f"      const uint32_t {token}_esi_before=esi;",
            f"      const uint32_t {token}_ebx_before=ebx;"]
    suffix=[
        f"      const uint32_t {token}_after=esp;",
        f"      const uint32_t {token}_delta={token}_after-{token}_before;",
        f"      static uint32_t {token}_n=0u;",
        f"      ++{token}_n;",
        f"      if ({token}_n <= 4u)",
        "      {",
        "          char k1r_line[320];",
        "          sprintf(k1r_line,",
        f'              "K1R ICALL {site}: n=%u before=%08X after=%08X delta=%08X esi_before=%08X esi_after=%08X ebx_before=%08X ebx_after=%08X edi=%08X",',
        f"              (unsigned){token}_n,(unsigned){token}_before,",
        f"              (unsigned){token}_after,(unsigned){token}_delta,",
        f"              (unsigned){token}_esi_before,(unsigned)esi,",
        f"              (unsigned){token}_ebx_before,(unsigned)ebx,(unsigned)edi);",
        "          trace(k1r_line);",
        "      }",
    ]
    # Retain original block interior exactly, including guest stack operations.
    return nl.join(prefix)+block[len(start): -len(after)]+nl.join(suffix+[after])


def modify(filename:str,source:str)->tuple[str,list[str]]:
    if filename not in TARGETS or TAG in source:
        raise ValueError("Unexpected or already-staged K1R source "+filename)
    nl=line_ending(source)
    name=TARGETS[filename]
    begin,end=function_span(source,name)
    original=source[begin:end]
    new=original
    sites=[]
    calls=A6B98_CALLS if filename=="translated_005.cpp" else A7B73_CALLS
    for callee,argc,count in calls:
        statement=f"PUSH32(esp, 0); sub_{callee}(); /* call 0x{callee} */"
        if new.count(statement)!=count:
            raise ValueError(f"{name}->{callee}: original callsite identity/count changed")
        visits=iter(range(1,count+1))
        def instrument(m:re.Match)->str:
            n=next(visits)
            label=f"{name[4:].upper()}_{callee}_{n}"
            sites.append(label)
            return call_probe(label,statement,argc*4 if filename=="translated_005.cpp" else None,nl)
        new=re.sub(re.escape(statement),instrument,new)
    if filename=="translated_005.cpp":
        if not all(x in original for x in ESI_SHAPE):
            raise ValueError("A6B98 exact saved-register prologue/epilogue missing")
        if original.count("P6DQ R49 ESI REPAIR: site=002A6BB0")!=1:
            raise ValueError("A6B98 original R49 hardware witness missing")
    else:
        blocks=list(ICALL_BLOCK.finditer(new))
        if len(blocks)!=5:
            raise ValueError(f"A7B73 expected 5 indirect call blocks, got {len(blocks)}")
        positions=iter(range(1,6))
        def instrument_indirect(m:re.Match)->str:
            n=next(positions)
            label=f"A7B73_ICALL_{n}"
            sites.append(label)
            return indirect_probe(label,m.group(0),nl)
        new=ICALL_BLOCK.sub(instrument_indirect,new)
        for label,anchor in CHECKPOINTS.items():
            exact=anchor.replace("\n",nl)
            if new.count(exact)!=1:
                raise ValueError(f"A7B73 epilogue checkpoint anchor drift: {label}")
            new=new.replace(exact,checkpoint(label,nl)+nl+exact,1)
            sites.append(label)
    if new.count(TAG)!=len(sites):
        raise ValueError("Wrong number of source-only K1R markers")
    # Compare ordered guest memory operations, callsites, stack instructions
    # and translated guest register updates against untouched original body.
    for expr,kind in ((MEM,"memory"),(CALLS,"direct-call"),
                      (PUSHPOP,"PUSH/POP"),(ICALLS,"indirect-call")):
        if expr.findall(new)!=expr.findall(original):
            raise ValueError("K1R modified original guest "+kind+" sequence")
    if original.count("esp += 8; return; /* ret 4 */") != new.count("esp += 8; return; /* ret 4 */"):
        raise ValueError("A7B73 return cleanup altered")
    if original.count("esp += 4; return; /* ret */") != new.count("esp += 4; return; /* ret */"):
        raise ValueError("A6B98 return cleanup altered")
    return source[:begin]+new+source[end:],sites


def stage(base:Path, base_manifest:Path, original:Path, k1q:Path, out:Path)->dict:
    base,base_manifest,original,k1q,out=(x.resolve() for x in
                                       (base,base_manifest,original,k1q,out))
    if base==out or base in out.parents or original in out.parents or
       out==original or out in {base_manifest,k1q}:
        raise ValueError("K1R cannot overwrite baseline, frozen sources or reports")
    j=json.loads(base_manifest.read_text(encoding="utf-8-sig"))
    report=k1q.read_text(encoding="utf-8-sig")
    if (j.get("marker")!=BASE or j.get("status")!="STAGED_ONLY_NO_XDK_BUILD"
        or j.get("translated_shards")!=64 or j.get("unchanged_from_k1j")!=62
        or j.get("modified_from_k1j")!=["translated_009.cpp","translated_057.cpp"]
        or j.get("preserved_k1e_k1g_k1j_watchers") is not True
        or Path(j.get("staged_directory","MISSING")).resolve()!=base
        or "K1Q READ-ONLY DSOUND A6B98 FIRST CORRUPTED RETURN CHILD AUDIT" not in report
        or "Lexical mismatch suspects=none" not in report
        or "### SUB_002A7B73 owner=translated_044.cpp first=21121 last=21290" not in report
        or "A6B98 prologue sets EBX=ECX, ESI=EBX+0x14" not in report):
        raise ValueError("K1P/K1Q provenance gates failed")
    cpp=sorted(base.glob("translated_*.cpp"))
    heads=sorted(base.glob("*.h"))
    allfiles=[*cpp,*heads]
    if len(cpp)!=64 or not any(x.name=="translated_runtime.h" for x in heads):
        raise ValueError("K1R requires 64 K1P TrueTUs and runtime header")
    hashes={p.name:sha(p) for p in allfiles}
    modified={};labels=[]
    for filename in TARGETS:
        origin=original/filename
        source=base/filename
        if not origin.is_file() or sha(origin)!=sha(source):
            raise ValueError("K1P changed an original K1R owner "+filename)
        payload,names=modify(filename,source.read_bytes().decode("utf-8"))
        modified[filename]=payload.encode("utf-8")
        labels.extend(names)
    if len(labels)!=21 or len(set(labels))!=len(labels):
        raise ValueError("K1R expected exactly 21 distinct trace labels")
    existing={p.name for p in out.iterdir()} if out.exists() else set()
    if existing and existing!={p.name for p in allfiles}:
        raise ValueError("Existing K1R output file set differs")
    out.mkdir(parents=True,exist_ok=True)
    for path in allfiles:
        dest=out/path.name
        expected=modified.get(path.name,path.read_bytes())
        if dest.exists():
            if dest.read_bytes()!=expected:
                raise ValueError("Previously staged K1R shard/header has changed: "+path.name)
        else:
            if path.name in modified:
                dest.write_bytes(expected)
            else:
                shutil.copy2(path,dest)
        if dest.read_bytes()!=expected or sha(path)!=hashes[path.name]:
            raise ValueError("K1R SHA verification failure: "+path.name)
    record={
        "marker":TAG,"status":"STAGED_ONLY_NO_XDK_BUILD",
        "baseline_directory":str(base),"staged_directory":str(out),
        "translated_shards":64,"modified_from_k1p":sorted(TARGETS),
        "unchanged_from_k1p":62,"probe_count":len(labels),
        "labels":labels,"guest_memory_ops_added":0,
        "guest_register_writes_added":0,"hard_fences":"UNCHANGED",
        "preserved_k1p_k1j_k1g_k1e_watchers":True,
        "owner_hashes":{
            name:{"original_sha256":hashes[name],
                  "staged_sha256":hashlib.sha256(content).hexdigest()}
            for name,content in modified.items()},
    }
    mp=out.parent/"k1r-a6b98-a7b73-manifest.json"
    mp.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--k1p-shards",required=True,type=Path)
    parser.add_argument("--k1p-manifest",required=True,type=Path)
    parser.add_argument("--original-shards",required=True,type=Path)
    parser.add_argument("--k1q-report",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    a=parser.parse_args()
    record=stage(a.k1p_shards,a.k1p_manifest,a.original_shards,a.k1q_report,a.out)
    print(f"[K1R] STAGING PASS: {record['probe_count']} register/ESP forensic edges")
    print("[K1R] Only translated_005.cpp and translated_044.cpp differ from K1P")
    print("[K1R] 62 unchanged TrueTUs + all headers; K1P/J/G/E witnesses preserved")
    print("[K1R] NO guest memory/register writes or changes to hard fences")
    print("[K1R] NO Xbox build performed. Manifest="+str(a.out.parent/"k1r-a6b98-a7b73-manifest.json"))

if __name__=="__main__":
    main()
