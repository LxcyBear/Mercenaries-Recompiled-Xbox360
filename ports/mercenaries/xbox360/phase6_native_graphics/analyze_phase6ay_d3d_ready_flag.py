#!/usr/bin/env python3
from __future__ import annotations
import argparse, importlib.util, json, re
from pathlib import Path

OFFSETS = ["0x3214","0x2400","0x3220","0x2100","0x400100","0x0100","0x100"]
FOCUS_NAMES = {"sub_00291B30","sub_002915C0","sub_00294DB0","sub_00291BE0","sub_00292271"}

def load_module(path: Path, name: str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AY] could not load {path}")
    mod=importlib.util.module_from_spec(spec); spec.loader.exec_module(mod); return mod

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--phase4-emitter",type=Path,required=True)
    ap.add_argument("--functions",type=Path,required=True)
    ap.add_argument("--generated-root",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()

    base=load_module(a.phase4_emitter,"phase6ay_base")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated_root,by_name)

    out=[]
    out.append("[Phase6AY] D3D READY-FLAG PRODUCER AUDIT")
    out.append("[Phase6AY] Proven stuck gate: *(device+0x3214) & 0x10 == 0")
    out.append("")

    # Exact focus function dumps.
    for name in sorted(FOCUS_NAMES):
        va=by_name.get(name)
        out.append("="*96)
        if va is None:
            out.append(f"[Phase6AY] FOCUS {name}: absent from inventory")
            continue
        row=by_va[va]; gen=generated.get(va)
        out.append(f"[Phase6AY] FOCUS {name} 0x{va:08X}-0x{int(row['end']):08X} generated={'yes' if gen else 'no'}")
        if not gen: continue
        for i,line in enumerate(gen["source"].splitlines(),1):
            out.append(f"{i:05d}: {line}")
        out.append("")

    out.append("="*96)
    out.append("[Phase6AY] GLOBAL OFFSET REFERENCES")
    patterns={off:re.compile(re.escape(off),re.I) for off in OFFSETS}
    for va in sorted(generated):
        gen=generated[va]; src=gen["source"]; hits=[]
        for i,line in enumerate(src.splitlines(),1):
            matched=[off for off,pat in patterns.items() if pat.search(line)]
            if matched:
                kind="WRITE" if "GUEST_WRITE" in line else ("READ" if "GUEST_READ" in line else "OTHER")
                hits.append((i,kind,matched,line))
        if not hits: continue
        row=by_va.get(va,{})
        out.append(f"[Phase6AY] FUNCTION {gen['name']} 0x{va:08X}-0x{int(row.get('end',va)):08X} file={gen['file']}")
        for i,kind,matched,line in hits:
            out.append(f"{i:05d}: {kind:<5} {','.join(matched):<28} {line}")

    out.append("")
    out.append("="*96)
    out.append("[Phase6AY] 0x3214 WRITERS ONLY")
    writers=0
    for va in sorted(generated):
        gen=generated[va]
        for i,line in enumerate(gen["source"].splitlines(),1):
            if "0x3214" in line.lower() and "GUEST_WRITE" in line:
                row=by_va.get(va,{})
                out.append(f"[Phase6AY] WRITER {gen['name']} 0x{va:08X}-0x{int(row.get('end',va)):08X} line={i}: {line}")
                writers+=1
    out.append(f"[Phase6AY] 0x3214 writer count={writers}")

    a.out.parent.mkdir(parents=True,exist_ok=True)
    payload="\n".join(out)+"\n"; a.out.write_text(payload,encoding="utf-8")
    print(payload)
    print(f"[Phase6AY] REPORT: {a.out}")
    print("[Phase6AY] PRODUCER AUDIT RESULT: PASS")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
