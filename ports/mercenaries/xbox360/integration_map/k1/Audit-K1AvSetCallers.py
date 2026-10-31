#!/usr/bin/env python3
"""Source-only local review of 2 verified AvSetDisplayMode D3D thunk callsites.

The saved xboxrecomp xrefs show ordinal 3 at 0x0028A61D (D3D 0x0028A530)
and 0x0028B48F (D3D 0x0028B430). Both caller bodies are compiled.
This produces metadata and a SEPARATE PRIVATE original source excerpt.
Never publishes game source, patches display_calls, or runs the XDK.
"""
from __future__ import annotations
import argparse
import importlib.util
import json
import re
from pathlib import Path

SITES=((0x0028A61D,0x0028A530),(0x0028B48F,0x0028B430))
THUNK=0x002DBE70
DECL=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?(?:__forceinline[ \t]+)?"
                r"void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")

def number(v):
    return int(str(v),0)

def audit(a):
    for field in ("xrefs","ranges","generated","emitter","shards"):
        if not getattr(a,field).exists():
            raise ValueError("Missing already generated local evidence: "+field)
    shards=list(a.shards.glob("translated_???.cpp"))
    if len(shards)!=64 or not (a.shards/"translated_runtime.h").exists():
        raise ValueError("Expected 64 known-good TrueTUs and original shared header")
    spec=importlib.util.spec_from_file_location("av_original_translator",str(a.emitter))
    if not spec or not spec.loader:
        raise ValueError("Original generated-source reader missing")
    base=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(base)
    ranges,by_name=base.load_ranges(a.ranges)
    generated=base.load_generated(a.generated,by_name)
    compiled={}
    for file in shards:
        text=file.read_text(encoding="utf-8")
        for match in DECL.finditer(text):
            compiled[int(match.group(1),16)]=file.name
    xrefs=json.loads(a.xrefs.read_text(encoding="utf-8-sig"))
    if not isinstance(xrefs,list) or len(xrefs)<100:
        raise ValueError("Missing cached xboxrecomp xrefs")
    call_to={}
    for x in xrefs:
        if x.get("type")=="call":
            try: call_to.setdefault(number(x["to"]),[]).append(number(x["from"]))
            except (ValueError,KeyError,TypeError): pass
    summary=[
        "[AVSET] ORIGINAL D3D KERNEL ORDINAL-3 CALLER AUDIT",
        "Target thunk=0x002DBE70, display_calls=0, real hardware",
        "No XDK, no guest patch, no fake display calls, local sources only",
        ""
    ]
    excerpts=[
        "PRIVATE USER-LOCAL ORIGINAL D3D SOURCE - DO NOT COMMIT TO GITHUB",
        ""
    ]
    for callsite,owner in SITES:
        matches=[
            x for x in xrefs if x.get("type")=="kernel_call"
            and x.get("kernel_name","").lower()=="avsetdisplaymode"
            and number(x.get("from","0"))==callsite
            and number(x.get("to","0"))==THUNK
        ]
        if len(matches)!=1:
            raise ValueError("Expected exactly one confirmed AvSetDisplayMode xref for 0x%08X"%callsite)
        span=ranges.get(owner)
        if not span or not span["start"]<=callsite<span["end"]:
            raise ValueError("Kernel callsite is outside verified original D3D source function")
        obj=generated.get(owner)
        if obj is None or owner not in compiled:
            raise ValueError("AvSetDisplayMode caller source missing or not compiled")
        src=obj["source"]
        lines=src.splitlines()
        relevant=[i for i,line in enumerate(lines)
            if re.search(r"AvSetDisplayMode|002DBE70|0028A61D|0028B48F|ordinal.?3|xboxkrnl",line,re.I)]
        callers=sorted(call_to.get(owner,[]))
        summary.extend([
            "owner=0x%08X AvSet callsite=0x%08X TrueTU=%s"%
                (owner,callsite,compiled[owner]),
            "  original_generated=%s source_lines=%d"%(obj["file"],len(lines)),
            "  source_nearby_matches=%s"%(",".join(str(i+1) for i in relevant[:40])),
            "  static_direct_callers=%d"%(len(callers)),
            "  caller_instructions=%s"%(",".join("0x%08X"%v for v in callers[:30])),
            ""
        ])
        excerpts.append("== Original D3D sub_%08X (AvSet at %08X) =="%(owner,callsite))
        keep=set()
        if relevant:
            for index in relevant[:40]:
                keep.update(range(max(0,index-22),min(len(lines),index+25)))
        else:
            keep.update(range(min(len(lines),140)))
        for i in sorted(keep):
            excerpts.append("%4d %s"%(i+1,lines[i]))
        excerpts.append("")
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.private.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text("\n".join(summary)+"\n",encoding="utf-8")
    a.private.write_text("\n".join(excerpts)+"\n",encoding="utf-8")
    print("\n".join(summary))
    print("[AVSET] LOCAL PRIVATE SOURCE: "+str(a.private))

def main():
    p=argparse.ArgumentParser()
    for name in ("xrefs","ranges","generated","emitter","shards","report","private"):
        p.add_argument("--"+name,required=True,type=Path)
    audit(p.parse_args())

if __name__=="__main__":
    main()
