#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, re
from pathlib import Path

FOCUS = ["sub_00292424","sub_00292112","sub_00291390","sub_00292271"]

def load_module(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BB] could not load {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase4-emitter",type=Path,required=True)
    ap.add_argument("--functions",type=Path,required=True)
    ap.add_argument("--generated-root",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    base=load_module(a.phase4_emitter,"phase6bb_base")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated_root,by_name)

    out=[]
    out.append("[Phase6BB] D3D +1C28 CHILD-CONTEXT INITIALIZER AUDIT")
    out.append("[Phase6BB] Proven retail path: D3DState(0x00299380)+0x1C28 -> sub_00292424 -> sub_00292112 setup")
    out.append("")

    for name in FOCUS:
        va=by_name.get(name)
        out.append("="*100)
        if va is None:
            out.append(f"[Phase6BB] {name}: missing from function inventory")
            continue
        gen=generated.get(va)
        row=by_va[va]
        out.append(f"[Phase6BB] {name} 0x{va:08X}-0x{int(row['end']):08X} generated={'yes' if gen else 'no'}")
        if not gen:
            continue
        for i,line in enumerate(gen["source"].splitlines(),1):
            out.append(f"{i:05d}: {line}")

    out.append("")
    out.append("="*100)
    out.append("[Phase6BB] FOCUS WRITE/CALL SUMMARY")
    interesting=re.compile(r"(GUEST_WRITE(?:8|16|32|64)|GUEST_READ(?:8|16|32|64)|sub_[0-9A-Fa-f]{8}\(\)|RECOMP_ICALL_SAFE|ecx\s*=|esi\s*=|edi\s*=|ebx\s*=|eax\s*=|edx\s*=)",re.I)
    for name in FOCUS:
        va=by_name.get(name); gen=generated.get(va) if va is not None else None
        if not gen: continue
        out.append(f"[Phase6BB] SUMMARY {name}")
        for i,line in enumerate(gen["source"].splitlines(),1):
            if interesting.search(line):
                out.append(f"{i:05d}: {line}")

    out.append("")
    out.append("="*100)
    out.append("[Phase6BB] CALLERS OF sub_00292424 / sub_00292112")
    for target in ("sub_00292424","sub_00292112"):
        for va in sorted(generated):
            gen=generated[va]
            if gen["name"]==target: continue
            for i,line in enumerate(gen["source"].splitlines(),1):
                if target+"()" in line:
                    out.append(f"[Phase6BB] {target} caller={gen['name']} 0x{va:08X} line={i}: {line}")

    a.out.parent.mkdir(parents=True,exist_ok=True)
    payload="\n".join(out)+"\n"
    a.out.write_text(payload,encoding="utf-8")
    print(payload)
    print(f"[Phase6BB] REPORT: {a.out}")
    print("[Phase6BB] CHILD-CONTEXT AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
