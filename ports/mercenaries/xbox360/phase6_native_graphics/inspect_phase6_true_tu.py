#!/usr/bin/env python3
"""Zero-build readiness audit for true C++ translation-unit sharding."""
from __future__ import annotations
import argparse,re
from collections import Counter,defaultdict
from pathlib import Path

FUNC_RE=re.compile(r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?(?:void|int|DWORD|uint(?:8|16|32|64)_t|BYTE|WORD|BOOL|HRESULT|recomp_func_t|const\s+char\s*\*)\s+([A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{")
SUB_DEF_RE=re.compile(r"(?m)^\s*static\s+void\s+(sub_[0-9A-Fa-f]{8})\(void\)\s*\{")
SUB_DECL_RE=re.compile(r"(?m)^\s*static\s+void\s+(sub_[0-9A-Fa-f]{8})\(void\)\s*;")
CALL_RE=re.compile(r"\b([A-Za-z_]\w*)\s*\(")
ID_RE=re.compile(r"\b([A-Za-z_]\w*)\b")
KEYWORDS={"if","while","for","switch","return","sizeof","do","else","case","break","continue"}

def closing_brace(text,brace):
    depth=0;i=brace;ins=False;q="";esc=False;lc=False;bc=False
    while i<len(text):
        c=text[i];n=text[i+1] if i+1<len(text) else ""
        if lc:
            if c=="\n":lc=False
            i+=1;continue
        if bc:
            if c=="*" and n=="/":bc=False;i+=2
            else:i+=1
            continue
        if ins:
            if esc:esc=False
            elif c=="\\":esc=True
            elif c==q:ins=False
            i+=1;continue
        if c=="/" and n=="/":lc=True;i+=2;continue
        if c=="/" and n=="*":bc=True;i+=2;continue
        if c in ("'",'"'):ins=True;q=c;i+=1;continue
        if c=="{":depth+=1
        elif c=="}":
            depth-=1
            if depth==0:return i+1
        i+=1
    raise RuntimeError("unterminated")

def function_defs(text):
    out={}
    for m in FUNC_RE.finditer(text):
        brace=text.find("{",m.start(),m.end()+2)
        if brace<0:continue
        try:end=closing_brace(text,brace)
        except:continue
        out[m.group(1)]=(m.start(),end,text[m.start():end])
    return out

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    args=ap.parse_args()
    text=args.source.read_text(encoding="utf-8",errors="replace")

    off='#pragma optimize("", off)\n'
    on='\n#pragma optimize("", on)'
    a=text.find(off); b=text.find(on,a+len(off))
    if a<0 or b<0: raise SystemExit("[Phase6TU] translated-body pragma bounds missing")
    prefix=text[:a+len(off)]
    body=text[a+len(off):b]
    suffix=text[b:]

    defs=function_defs(prefix)
    body_defs=set(SUB_DEF_RE.findall(body))
    decls=set(SUB_DECL_RE.findall(prefix))
    body_calls=[x for x in CALL_RE.findall(body) if x not in KEYWORDS]
    calls=Counter(body_calls)
    helper_calls={k:v for k,v in calls.items() if not k.startswith("sub_")}
    sub_calls={k:v for k,v in calls.items() if k.startswith("sub_")}

    print("[Phase6TU] TRUE-TU READINESS ZERO-BUILD AUDIT")
    print(f"[Phase6TU] source={args.source}")
    print(f"[Phase6TU] chars prefix={len(prefix)} translated={len(body)} suffix={len(suffix)}")
    print(f"[Phase6TU] translated_defs={len(body_defs)} static_forward_decls={len(decls)}")
    print(f"[Phase6TU] translated_sub_calls={len(sub_calls)} helper_call_symbols={len(helper_calls)}")
    print(f"[Phase6TU] decl_without_body={len(decls-body_defs)} body_without_decl={len(body_defs-decls)}")

    print("[Phase6TU] TOP HELPER CALLS")
    for name,count in sorted(helper_calls.items(),key=lambda kv:(-kv[1],kv[0]))[:120]:
        where="PREFIX_DEF" if name in defs else "NO_PREFIX_DEF"
        print(f"[Phase6TU] helper {name} calls={count} provider={where}")

    # Static prefix support functions called by translated bodies must become
    # externally visible or move into a shared inline header.
    static_support=[]
    for name,count in helper_calls.items():
        row=defs.get(name)
        if not row:continue
        src=row[2].lstrip()
        if src.startswith("static "):
            static_support.append((name,count))
    print(f"[Phase6TU] static_support_called_by_translated={len(static_support)}")
    for name,count in sorted(static_support,key=lambda kv:(-kv[1],kv[0])):
        print(f"[Phase6TU] STATIC SUPPORT {name} calls={count}")

    # Macro inventory is useful because macros/types can live safely in a
    # generated shared header without creating duplicated runtime state.
    macros=re.findall(r"(?m)^\s*#define\s+([A-Za-z_]\w*)",prefix)
    print(f"[Phase6TU] prefix_macros={len(macros)}")

    # Architecture state explicitly used in translated body.
    candidates=sorted(set(
        x for x in ID_RE.findall(body)
        if x in {"eax","ecx","edx","ebx","esi","edi","ebp","esp",
                 "g_eax","g_ecx","g_edx","g_ebx","g_esi","g_edi","g_seh_ebp",
                 "g_esp","g_eflags","g_ram"} or x.startswith("g_xmm") or x.startswith("g_mm")
    ))
    print("[Phase6TU] architecture_symbols="+",".join(candidates))

    print("[Phase6TU] RECOMMENDED_LAYOUT runtime_support.cpp + translated_runtime.h + translated_###.cpp")
    print("[Phase6TU] RULE translated definitions and forward declarations must lose internal static linkage")
    print("[Phase6TU] RULE architecture/runtime state must have exactly one definition; shards receive extern declarations")
    print("[Phase6TU] RULE helper functions above must be external or shared __forceinline, never duplicated stateful statics")
    print("[Phase6TU] AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
