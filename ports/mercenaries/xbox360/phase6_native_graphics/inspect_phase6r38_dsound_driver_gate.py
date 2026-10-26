#!/usr/bin/env python3
r"""Phase 6R38 zero-build DirectSound driver-present gate audit.

R36 proved XACT init fails because sub_0029FDF0 returns 0x88780078.
R37 proved the only literal construction of that HRESULT is at 0x002A7B89.
This audit finds the function owning 0x002A7B89, reconstructs a direct-call
path from sub_0029FC4A to that owner where possible, and dumps both bodies plus
the exact branch context that selects DSERR_NODRIVER.

No source mutation, no build, no runtime changes.
"""
from __future__ import annotations
import argparse
import collections
import re
from pathlib import Path

START = "sub_0029FC4A"
ERROR_LITERAL = "0x88780078"
ERROR_LABEL = "loc_002A7B89"
FUNC_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*void\s*\)\s*\{"
)
TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
CALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)\s*;")
FRONTIER_RE = re.compile(r"phase4c_direct_frontier\s*\(\s*(0x[0-9A-Fa-f]+)u?\s*\)")


def closing_brace(text: str, brace: int) -> int:
    depth=0; i=brace; ins=False; q=""; esc=False; lc=False; bc=False
    while i < len(text):
        c=text[i]; n=text[i+1] if i+1 < len(text) else ""
        if lc:
            if c=="\n": lc=False
            i+=1; continue
        if bc:
            if c=="*" and n=="/": bc=False; i+=2
            else: i+=1
            continue
        if ins:
            if esc: esc=False
            elif c=="\\": esc=True
            elif c==q: ins=False
            i+=1; continue
        if c=="/" and n=="/": lc=True; i+=2; continue
        if c=="/" and n=="*": bc=True; i+=2; continue
        if c in ('"', "'"): ins=True; q=c; i+=1; continue
        if c=="{": depth+=1
        elif c=="}":
            depth-=1
            if depth==0: return i+1
        i+=1
    raise RuntimeError("unterminated function")


def parse_functions(text: str):
    out=[]
    for m in FUNC_RE.finditer(text):
        b=text.find("{",m.start(),m.end())
        e=closing_brace(text,b)
        body=text[m.start():e]
        tm=TRACE_RE.search(body)
        va=int(tm.group(1),16) if tm else None
        if va is None:
            mm=re.fullmatch(r"sub_([0-9A-Fa-f]{8})",m.group(1))
            if mm: va=int(mm.group(1),16)
        out.append({"name":m.group(1),"va":va,"body":body})
    return out


def calls_of(body: str):
    out=[]
    for m in CALL_RE.finditer(body):
        out.append(m.group(1))
    for m in FRONTIER_RE.finditer(body):
        out.append("sub_"+m.group(1).upper().zfill(8))
    return out


def dump_body(tag: str, f):
    lines=f["body"].splitlines()
    print("="*100)
    print(f"[Phase6R38] {tag} name={f['name']} va={(f['va'] or 0):08X} lines={len(lines)}")
    for i,line in enumerate(lines,1):
        print(f"[Phase6R38] {i:04d}: {line}")


def dump_context(lines, hit, before=14, after=22):
    lo=max(0,hit-before); hi=min(len(lines),hit+after+1)
    for j in range(lo,hi):
        mark=">>" if j==hit else "  "
        print(f"[Phase6R38] {mark} {j+1:04d}: {lines[j]}")


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.exists():
        raise SystemExit(f"[Phase6R38] source missing: {args.source}")

    text=args.source.read_text(encoding="utf-8",errors="replace")
    funcs=parse_functions(text)
    by_name={f["name"]:f for f in funcs}

    start=by_name.get(START)
    if not start:
        raise SystemExit(f"[Phase6R38] missing start function {START}")

    owners=[f for f in funcs if ERROR_LITERAL.lower() in f["body"].lower()]
    if len(owners)!=1:
        raise SystemExit(f"[Phase6R38] expected one DSERR_NODRIVER literal owner, found {len(owners)}")
    owner=owners[0]

    print("[Phase6R38] DSOUND DRIVER-PRESENT GATE ZERO-BUILD AUDIT")
    print(f"[Phase6R38] start={START} va={(start['va'] or 0):08X}")
    print(f"[Phase6R38] nodriver_owner={owner['name']} va={(owner['va'] or 0):08X}")
    print("[Phase6R38] Proven R37 literal site: 002A7B89 -> 88780078")

    graph={f["name"]:[c for c in calls_of(f["body"]) if c in by_name] for f in funcs}
    prev={START:None}
    q=collections.deque([START])
    while q and owner["name"] not in prev:
        cur=q.popleft()
        for nxt in graph.get(cur,[]):
            if nxt not in prev:
                prev[nxt]=cur
                q.append(nxt)

    if owner["name"] in prev:
        path=[]
        cur=owner["name"]
        while cur is not None:
            path.append(cur)
            cur=prev[cur]
        path.reverse()
        print("[Phase6R38] direct-call path: "+" -> ".join(path))
    else:
        path=[START,owner["name"]]
        print("[Phase6R38] direct-call path: not statically connected through ordinary direct calls")
        print("[Phase6R38] note: an ICALL/vtable edge may connect the two; bodies still dumped below")

    dump_body("START BODY",start)

    # Dump bodies along any discovered path, excluding already printed start.
    for name in path[1:-1]:
        dump_body("PATH BODY",by_name[name])

    dump_body("NODRIVER OWNER BODY",owner)

    olines=owner["body"].splitlines()
    hits=[i for i,l in enumerate(olines)
          if ERROR_LABEL in l or "88780078" in l or "002A7B85" in l or "002A7B93" in l]
    print(f"[Phase6R38] driver-gate context hits={len(hits)}")
    for idx,hit in enumerate(hits,1):
        print(f"[Phase6R38] DRIVER GATE CONTEXT {idx}: line={hit+1}")
        dump_context(olines,hit)

    # Inventory every call in the no-driver owner and dump compact context.
    owner_calls=[]
    for i,line in enumerate(olines):
        for m in CALL_RE.finditer(line):
            owner_calls.append((i,m.group(1)))
        for m in FRONTIER_RE.finditer(line):
            owner_calls.append((i,"sub_"+m.group(1).upper().zfill(8)))

    print(f"[Phase6R38] nodriver-owner calls={len(owner_calls)}")
    for idx,(hit,target) in enumerate(owner_calls,1):
        print(f"[Phase6R38] OWNER CALL {idx}: line={hit+1} target={target}")
        dump_context(olines,hit,5,8)

    # Dump direct callee bodies from the owner. Usually this is enough to identify
    # the hardware/device-present probe feeding the branch.
    seen=set()
    for _,target in owner_calls:
        if target in seen or target not in by_name:
            continue
        seen.add(target)
        dump_body("OWNER CALLEE BODY",by_name[target])

    print("[Phase6R38] AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
