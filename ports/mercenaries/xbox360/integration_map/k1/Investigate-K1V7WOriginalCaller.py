#!/usr/bin/env python3
"""V7W: locate original translated caller and describe pointer reads.

A source-only witness from on-disk V7U + 64 TrueTUs + original recomp C.
Outputs private excerpts locally; no retail source or game bytes committed.
"""
from pathlib import Path
import argparse,re,hashlib,json,sys
SYM="sub_0023A3CE"
RE=re.compile(r"\b"+SYM+r"\s*\(")
DEF=re.compile(r"(?m)^\s*(?:static\s+)?(?:inline\s+)?(?:void|uint32_t|int)\s+"+SYM+r"\s*\([^;]*?\)\s*\{")
READ=re.compile(r"\b(?:GUEST_READ(?:8|16|32|64)|GUEST_WRITE(?:8|16|32|64)|RECOMP_TRACE_FUNC)\s*\(")
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--main",type=Path,required=True)
    ap.add_argument("--shards",type=Path,required=True)
    ap.add_argument("--generated",type=Path,required=True)
    ap.add_argument("--output",type=Path,required=True)
    a=ap.parse_args()
    assert a.main.is_file() and a.shards.is_dir() and a.generated.is_dir()
    files=[a.main]+sorted(a.shards.glob("translated_*.cpp"))+sorted(a.generated.glob("recomp_*.c"))
    seen=set(); excerpts=[]; summary=[]
    for path in files:
        if path.resolve() in seen:continue
        seen.add(path.resolve())
        lines=path.read_text(errors="replace").splitlines()
        matches=[i for i,x in enumerate(lines) if RE.search(x)]
        if not matches:continue
        definitions=[i for i,x in enumerate(lines) if DEF.match(x)]
        # Handle multiline function signatures without a semicolon.
        if not definitions:
            definitions=[i for i in matches if "{" in "\n".join(lines[i:i+4])
                         and ";" not in "\n".join(lines[i:i+4]).split("{",1)[0]]
        summary.append((str(path),len(matches),[i+1 for i in definitions]))
        for i in definitions[:3]:
            excerpt=lines[i:min(len(lines),i+210)]
            excerpts.append("=== DEFINITION "+str(path)+" line "+str(i+1)+" ===")
            for j,line in enumerate(excerpt,i+1):
                excerpts.append("%6d: %s"%(j,line))
        if path==a.main and not definitions:
            excerpts.append("MAIN DECLARATIONS ONLY "+str([i+1 for i in matches[:12]]))
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text("\n".join(excerpts)+"\n",encoding="utf-8")
    print("[K1-V7W] TARGET: "+SYM+" (hardware caller is NOT proven fault instruction)")
    for path,count,defs in summary[:24]:
        print("[K1-V7W] %s references=%d definition_lines=%s"%(path,count,defs))
    print("[K1-V7W] LOCAL EXCERPTS "+str(a.output))
    print("[K1-V7W] NO RETAIL XBE MODIFICATION / NO XDK / NO XBOX")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7W] HARD FENCE "+str(e),file=sys.stderr);sys.exit(1)
