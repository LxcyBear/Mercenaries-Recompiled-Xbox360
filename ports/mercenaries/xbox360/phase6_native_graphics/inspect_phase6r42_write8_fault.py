#!/usr/bin/env python3
r"""Phase 6R42 zero-build WRITE8 fault-site audit.

R41 crossed the AC97 PCM BDBAR frontier and then faulted on WRITE8
guest=DEA85111 with guest registers:
  eax=DFE85006 ecx=008BF802 edx=00001000 ebx=8007000E
  esi=00040000 edi=00000000

This audit scans the already-generated monolithic source.  It does not mutate
generated code and does not build.  It inventories DSOUND WRITE8 callsites,
maps each call to its nearest translated VA, highlights expressions capable of
producing DEA85111 from the R41 register snapshot, and inventories every
reference/write to the AC97 channel-offset table at 002BA9C0/002BA9C4.
"""
from __future__ import annotations
import argparse, re
from pathlib import Path

DSOUND_LO=0x0029CB80
DSOUND_HI=0x002BB274
FAULT=0xDEA85111
REGS={
    "eax":0xDFE85006,
    "ecx":0x008BF802,
    "edx":0x00001000,
    "ebx":0x8007000E,
    "esi":0x00040000,
    "edi":0x00000000,
}
FUNC_RE=re.compile(r"(?m)^\s*(?:static\s+)?void\s+(sub_([0-9A-Fa-f]{8}))\(void\)\s*\{")
CALL_RE=re.compile(r"phase6ch_apu_write8\s*\((?P<args>[^;]+)\)\s*;")
TICK_RE=re.compile(r"PHASE4C_BUDGET_TICK\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
TABLE_ADDRS=("0x2BA9C0","0x2BA9C4","0x002BA9C0","0x002BA9C4")
REG_CONST_RE=re.compile(
    r"^\s*(eax|ecx|edx|ebx|esi|edi)\s*([+-])\s*(0x[0-9A-Fa-f]+|\d+)[uUlL]*\s*$"
)
CONST_REG_RE=re.compile(
    r"^\s*(0x[0-9A-Fa-f]+|\d+)[uUlL]*\s*\+\s*(eax|ecx|edx|ebx|esi|edi)\s*$"
)

def closing_brace(text, brace):
    depth=0; i=brace; ins=False; q=""; esc=False; lc=False; bc=False
    while i<len(text):
        c=text[i]; n=text[i+1] if i+1<len(text) else ""
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
        if c in ("'", '"'): ins=True; q=c; i+=1; continue
        if c=="{": depth+=1
        elif c=="}":
            depth-=1
            if depth==0: return i+1
        i+=1
    raise RuntimeError("unterminated function")

def parse_int(s):
    s=re.sub(r"[uUlL]+$","",s.strip())
    return int(s,0)&0xffffffff

def eval_simple(expr):
    expr=expr.strip()
    if expr in REGS: return REGS[expr]
    m=REG_CONST_RE.match(expr)
    if m:
        r,op,k=m.groups(); k=parse_int(k)
        return ((REGS[r]+k) if op=="+" else (REGS[r]-k))&0xffffffff
    m=CONST_REG_RE.match(expr)
    if m:
        k,r=m.groups()
        return (parse_int(k)+REGS[r])&0xffffffff
    try:
        return parse_int(expr)
    except Exception:
        return None

def line_no(text,pos): return text.count("\n",0,pos)+1

def context(lines, idx, before=6, after=9):
    lo=max(0,idx-before); hi=min(len(lines),idx+after+1)
    return "\n".join(
        f"[Phase6R42] {'>>' if j==idx else '  '} {j+1:04d}: {lines[j]}"
        for j in range(lo,hi)
    )

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.exists():
        raise SystemExit(f"[Phase6R42] source missing: {args.source}")
    text=args.source.read_text(encoding="utf-8",errors="replace")

    funcs=[]
    for m in FUNC_RE.finditer(text):
        va=int(m.group(2),16)
        brace=text.find("{",m.start(),m.end()+2)
        end=closing_brace(text,brace)
        funcs.append((va,m.group(1),m.start(),end,text[m.start():end]))

    print("[Phase6R42] WRITE8 FAULT ZERO-BUILD AUDIT")
    print("[Phase6R42] R41 fault=DEA85111")
    print("[Phase6R42] regs "+" ".join(f"{k}={v:08X}" for k,v in REGS.items()))
    print("[Phase6R42] source="+str(args.source))

    calls=[]
    suspects=[]
    for va,name,start,end,body in funcs:
        if not (DSOUND_LO <= va < DSOUND_HI):
            continue
        blines=body.splitlines()
        # Track the most recent translated tick for callsite VA.
        last_tick=None
        for idx,line in enumerate(blines):
            tm=TICK_RE.search(line)
            if tm: last_tick=int(tm.group(1),16)
            for cm in CALL_RE.finditer(line):
                args_text=cm.group("args")
                # split only first comma; current generated calls use simple addr,value args
                addr_expr=args_text.split(",",1)[0].strip()
                value=eval_simple(addr_expr)
                row=(va,name,last_tick or va,idx,addr_expr,value,blines)
                calls.append(row)
                if value==FAULT:
                    suspects.append(row)

    print(f"[Phase6R42] DSOUND WRITE8 callsites={len(calls)} exact_snapshot_matches={len(suspects)}")
    for i,(fva,name,site,idx,expr,value,lines) in enumerate(suspects,1):
        print("="*100)
        print(f"[Phase6R42] EXACT MATCH {i}: function={name} function_va={fva:08X} site={site:08X}")
        print(f"[Phase6R42] expr={expr} snapshot_value={(value or 0):08X}")
        print(context(lines,idx,10,14))

    # Highlight all callsites using the snapshot's unusual EAX value or AC97 constants.
    interesting=[]
    for row in calls:
        expr=row[4].lower()
        if ("eax" in expr or "fec001" in expr or "-209712" in expr or "209712" in expr):
            interesting.append(row)
    print(f"[Phase6R42] interesting WRITE8 callsites={len(interesting)}")
    for i,(fva,name,site,idx,expr,value,lines) in enumerate(interesting,1):
        print(f"[Phase6R42] WRITE8[{i}] func={fva:08X} site={site:08X} expr={expr} eval={'--------' if value is None else f'{value:08X}'}")

    # Exact table references and nearby context.
    refs=[]
    for needle in TABLE_ADDRS:
        pos=0
        while True:
            pos=text.find(needle,pos)
            if pos<0: break
            refs.append((pos,needle))
            pos+=len(needle)
    refs=sorted(set(refs))
    print(f"[Phase6R42] AC97 offset-table textual refs={len(refs)}")
    tlines=text.splitlines()
    seen_lines=set()
    for pos,needle in refs:
        ln=line_no(text,pos)
        if ln in seen_lines: continue
        seen_lines.add(ln)
        idx=ln-1
        print("="*100)
        print(f"[Phase6R42] TABLE REF line={ln} needle={needle}")
        print(context(tlines,idx,9,12))

    # Find writes whose address expression directly names the table.
    write_patterns=[
        re.compile(r"(?:phase6ch_apu_write32|GUEST_WRITE32)\s*\(\s*(0x0*2BA9C[04])[^;]*;"),
        re.compile(r"(?:phase6ch_apu_write8|GUEST_WRITE8)\s*\(\s*(0x0*2BA9C[0-7])[^;]*;"),
    ]
    table_writes=[]
    for pat in write_patterns:
        for m in pat.finditer(text):
            table_writes.append((m.start(),m.group(0)))
    print(f"[Phase6R42] direct table-write sites={len(table_writes)}")
    for pos,stmt in sorted(table_writes):
        ln=line_no(text,pos); idx=ln-1
        print("="*100)
        print(f"[Phase6R42] TABLE WRITE line={ln} stmt={stmt}")
        print(context(tlines,idx,8,12))

    # Dump sub_002A7B73 because R38 proved it owns the reset loop.
    target=next((f for f in funcs if f[0]==0x002A7B73),None)
    if target:
        va,name,start,end,body=target
        print("="*100)
        print("[Phase6R42] OWNER BODY sub_002A7B73")
        for i,line in enumerate(body.splitlines(),1):
            print(f"[Phase6R42] {i:04d}: {line}")

    print("[Phase6R42] AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
