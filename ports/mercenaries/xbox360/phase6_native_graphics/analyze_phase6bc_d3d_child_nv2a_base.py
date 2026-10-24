#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, re
from pathlib import Path

FOCUS = [
    "sub_00291F31",
    "sub_00291F5C",
    "sub_00291F9D",
    "sub_00292020",
    "sub_002920B8",
]

def load_module(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BC] could not load {path}")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase4-emitter",type=Path,required=True)
    ap.add_argument("--functions",type=Path,required=True)
    ap.add_argument("--generated-root",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    base=load_module(a.phase4_emitter,"phase6bc_base")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated_root,by_name)

    out=[]
    out.append("[Phase6BC] D3D CHILD FIRST-DWORD / NV2A-BASE AUDIT")
    out.append("[Phase6BC] Goal: identify who initializes *(D3DState+0x1C28)")
    out.append("[Phase6BC] 6BB evidence: sub_00292112 uses that first dword as base for +0x700000-style writes")
    out.append("")

    for name in FOCUS:
        va=by_name.get(name)
        out.append("="*100)
        if va is None:
            out.append(f"[Phase6BC] {name}: missing from function inventory")
            continue
        gen=generated.get(va)
        row=by_va[va]
        out.append(f"[Phase6BC] {name} 0x{va:08X}-0x{int(row['end']):08X} generated={'yes' if gen else 'no'}")
        if not gen:
            continue
        for i,line in enumerate(gen["source"].splitlines(),1):
            out.append(f"{i:05d}: {line}")

    out.append("")
    out.append("="*100)
    out.append("[Phase6BC] FIRST-DWORD WRITE CANDIDATES")
    first_re = re.compile(
        r"GUEST_WRITE(?:8|16|32|64)\(\s*(?:ecx|esi|edi|ebx|edx|eax)\s*(?:,|\+\s*0(?:x0+)?)",
        re.I,
    )
    for name in FOCUS:
        va=by_name.get(name)
        gen=generated.get(va) if va is not None else None
        if not gen: continue
        for i,line in enumerate(gen["source"].splitlines(),1):
            if first_re.search(line):
                out.append(f"[Phase6BC] {name} L{i}: {line}")

    out.append("")
    out.append("="*100)
    out.append("[Phase6BC] NV2A / MMIO-LIKE LITERALS AND OFFSETS")
    mmio_re = re.compile(
        r"(0xF[CD E][0-9A-F]{6}|0xFD[0-9A-F]{6}|0xFE[0-9A-F]{6}|0x700000|0x70000|0x400000|0x100000|0x100410|0x400100)",
        re.I,
    )
    for name in FOCUS:
        va=by_name.get(name)
        gen=generated.get(va) if va is not None else None
        if not gen: continue
        for i,line in enumerate(gen["source"].splitlines(),1):
            if mmio_re.search(line):
                out.append(f"[Phase6BC] {name} L{i}: {line}")

    out.append("")
    out.append("="*100)
    out.append("[Phase6BC] CALL GRAPH FROM CONSTRUCTOR HELPERS")
    call_re=re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)")
    for name in FOCUS:
        va=by_name.get(name)
        gen=generated.get(va) if va is not None else None
        if not gen: continue
        calls=[]
        for m in call_re.finditer(gen["source"]):
            callee=m.group(1)
            if callee not in calls:
                calls.append(callee)
        out.append(f"[Phase6BC] {name}: " + (", ".join(calls) if calls else "<no direct calls>"))

    out.append("")
    out.append("="*100)
    out.append("[Phase6BC] GLOBAL WRITES OF LITERAL 0xFD000000 / 0xFE000000 / 0xF0000000-STYLE VALUES")
    lit_re=re.compile(r"GUEST_WRITE(?:8|16|32|64)\([^\n]*0xF[0-9A-F]{7}",re.I)
    hits=0
    for va in sorted(generated):
        gen=generated[va]
        for i,line in enumerate(gen["source"].splitlines(),1):
            if lit_re.search(line):
                out.append(f"[Phase6BC] {gen['name']} 0x{va:08X} L{i}: {line}")
                hits+=1
    out.append(f"[Phase6BC] high-literal write count={hits}")

    a.out.parent.mkdir(parents=True,exist_ok=True)
    payload="\n".join(out)+"\n"
    a.out.write_text(payload,encoding="utf-8")
    print(payload)
    print(f"[Phase6BC] REPORT: {a.out}")
    print("[Phase6BC] NV2A-BASE AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
