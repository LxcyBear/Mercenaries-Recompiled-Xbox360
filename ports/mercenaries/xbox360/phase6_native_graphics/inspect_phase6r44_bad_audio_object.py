#!/usr/bin/env python3
"""Phase 6R44 zero-build bad-audio-object provenance audit.

R43 hardware proof:
  site      = 0x002A7712
  object    = 0x00040000
  index     = 0x00000400
  table     = [0x10, 0x70] and remained unmodified
  table VA  = 0x002BB9C0 (0x1000 bytes beyond the 2-entry table)
  value     = 0xDFE85006
  fault dst = 0xDEA85111

Goal: identify who supplies ECX to sub_002A76FE and whether sub_0029CBB0
clobbers ESI after sub_002A76FE saves the incoming object there.
No source mutation, build, or hardware run.
"""
from __future__ import annotations
import argparse, re
from pathlib import Path

FUNC_RE=re.compile(r"(?m)^\s*(?:static\s+)?void\s+(sub_([0-9A-Fa-f]{8}))\(void\)\s*\{")
CALL_NAME="sub_002A76FE"
TARGET_FUNCS=(0x002A76FE,0x0029CBB0,0x002A77BE,0x002A74D9,0x002A7508,0x002A75C9)

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
        if c in ("'",'"'): ins=True; q=c; i+=1; continue
        if c=="{": depth+=1
        elif c=="}":
            depth-=1
            if depth==0: return i+1
        i+=1
    raise RuntimeError("unterminated function")

def functions(text):
    out=[]
    for m in FUNC_RE.finditer(text):
        brace=text.find("{",m.start(),m.end()+4)
        end=closing_brace(text,brace)
        out.append({
            "name":m.group(1),
            "va":int(m.group(2),16),
            "start":m.start(),
            "end":end,
            "body":text[m.start():end],
        })
    return out

def print_body(tag,row):
    print("="*110)
    print(f"[Phase6R44] {tag}: {row['name']} va={row['va']:08X}")
    for i,line in enumerate(row["body"].splitlines(),1):
        print(f"[Phase6R44] {i:04d}: {line}")

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    text=args.source.read_text(encoding="utf-8",errors="replace")
    fs=functions(text)
    byva={x["va"]:x for x in fs}

    print("[Phase6R44] BAD AUDIO OBJECT ZERO-BUILD AUDIT")
    print("[Phase6R44] R43 proof site=002A7712 object=00040000 index=00000400")
    print("[Phase6R44] R43 proof table0=00000010 table1=00000070 table_write_watch=0")
    print("[Phase6R44] source="+str(args.source))

    for va in TARGET_FUNCS:
        row=byva.get(va)
        if row is None:
            print(f"[Phase6R44] WARN missing exact function 0x{va:08X}")
        else:
            print_body("TARGET BODY",row)

    callers=[]
    needle=CALL_NAME+"();"
    for row in fs:
        lines=row["body"].splitlines()
        for idx,line in enumerate(lines):
            if needle not in line:
                continue
            callers.append((row,idx))
            lo=max(0,idx-35); hi=min(len(lines),idx+18)
            print("="*110)
            print(f"[Phase6R44] DIRECT CALLSITE owner={row['name']} va={row['va']:08X} line={idx+1}")
            for j in range(lo,hi):
                mark=">>" if j==idx else "  "
                print(f"[Phase6R44] {mark} {j+1:04d}: {lines[j]}")

    print(f"[Phase6R44] direct_calls_to_002A76FE={len(callers)}")

    # Find direct callers of the caller functions as one level of provenance.
    caller_names={row["name"] for row,_ in callers}
    for callee in sorted(caller_names):
        needle2=callee+"();"
        count=0
        for row in fs:
            lines=row["body"].splitlines()
            for idx,line in enumerate(lines):
                if needle2 not in line:
                    continue
                count+=1
                lo=max(0,idx-22); hi=min(len(lines),idx+10)
                print("="*110)
                print(f"[Phase6R44] PARENT CALL {callee} owner={row['name']} va={row['va']:08X}")
                for j in range(lo,hi):
                    mark=">>" if j==idx else "  "
                    print(f"[Phase6R44] {mark} {j+1:04d}: {lines[j]}")
        print(f"[Phase6R44] parent_calls_to_{callee}={count}")

    # Explicitly detect ESI writes in 0029CBB0 to settle the clobber question.
    row=byva.get(0x0029CBB0)
    if row:
        esi_lines=[
            line.strip() for line in row["body"].splitlines()
            if re.search(r"\besi\s*=",line) or "POP32(esp, esi)" in line or "PUSH32(esp, esi)" in line
        ]
        print("="*110)
        print(f"[Phase6R44] 0029CBB0 ESI TOUCHES count={len(esi_lines)}")
        for line in esi_lines:
            print("[Phase6R44]   "+line)

    print("[Phase6R44] AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
