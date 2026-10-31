#!/usr/bin/env python3
"""Package existing xboxrecomp JSON into predictive Merc360 function report.

No second disassembly pass. No source-game binary, game .s bytes, or runtime.
Reads tool's actual tools/disasm/output/functions.json and abi_functions.json.
"""
from __future__ import annotations

import argparse
import collections
import csv
import hashlib
import json
import re
import zipfile
from pathlib import Path

ORIGINAL_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
FRONTIER=0x002D5574
SECTIONS={"XMV","XACTENG","D3D","XGRPH","DSOUND","WMADEC","XPP"}
PRIORITIES=(0x002D5574,0x002A3A5A,0x0023A3CE,0x00280C39,
            0x0028E700,0x00290895,0x0029C8BE,0x0027DB5C)
DECL=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})"
                r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")

def digest(path:Path)->str:
    h=hashlib.sha256()
    with path.open("rb") as stream:
        for part in iter(lambda:stream.read(65536),b""):
            h.update(part)
    return h.hexdigest().upper()

def load_json(path:Path):
    return json.loads(path.read_text(encoding="utf-8-sig"))

def value(row,term,default=None):
    return row.get(term,default)

def address(x):
    return int(str(x),0)

def present_shards(folder:Path)->tuple[set[int],int]:
    files=list(folder.glob("translated_*.cpp")) if folder.exists() else []
    if files and len(files)!=64:
        raise ValueError("Existing Pixel batch is incomplete: need 64 TrueTUs")
    compiled=set()
    for p in files:
        for m in DECL.finditer(p.read_text(encoding="utf-8",errors="replace")):
            compiled.add(int(m.group(1),16))
    return compiled,len(files)

def build(a):
    if digest(a.xbe)!=ORIGINAL_SHA:
        raise ValueError("Original private Mercenaries XBE SHA256 mismatch")
    data=load_json(a.functions)
    if not isinstance(data,list) or len(data)<1000:
        raise ValueError("Disassembler's functions.json absent/incomplete or wrong schema")
    stats=load_json(a.summary)
    if stats.get("entry_point")!="0x0022964A":
        raise ValueError("Disassembler summary entry point does not match Mercenaries")
    # A successful cached Stage 2 must match the same original retail XBE.
    cachefile=a.functions.parent/".disasm_cache.json"
    if not cachefile.is_file():
        raise ValueError("Stage 2 does not have a valid output cache metadata file")
    cache=load_json(cachefile)
    if cache.get("xbe_hash","").upper()!=ORIGINAL_SHA:
        raise ValueError("Stage 2 cache XBE hash mismatch: refusing report")
    if not cache.get("opts_key") or cache.get("text_only") is True:
        raise ValueError("Stage 2 cache was text-only/incomplete")
    abi_rows=load_json(a.abi)
    if not isinstance(abi_rows,list):
        raise ValueError("Wrong ABI JSON schema")
    abi={}
    for record in abi_rows:
        try: abi[address(record["address"])]=record
        except (ValueError,TypeError,KeyError): continue
    compiled,tu_count=present_shards(a.pixel_shards)
    functions={}
    normalized=[]
    for item in data:
        try:
            key=address(item["start"]);end=address(item["end"])
            if end<=key:continue
        except (KeyError,TypeError,ValueError):continue
        if key in functions:
            raise ValueError("Duplicate disassembler function start 0x%08X"%key)
        record={
            "address":"0x%08X"%key,
            "end":"0x%08X"%end,
            "name":value(item,"name","sub_%08X"%key),
            "section":value(item,"section",""),
            "size":value(item,"size",end-key),
            "instructions":value(item,"num_instructions",0),
            "confidence":value(item,"confidence",0),
            "detection_method":value(item,"detection_method",""),
            "has_prologue":value(item,"has_prologue",False),
            "called_by":value(item,"called_by",[]),
            "calls_to":value(item,"calls_to",[]),
            "present_in_pixel_true_tus":key in compiled,
        }
        if key in abi:
            for field in ("calling_convention","estimated_params","return_hint",
                          "frame_type","stack_frame_size","heuristic_confidence"):
                if field in abi[key]:
                    record[field]=abi[key][field]
        normalized.append(record)
        functions[key]=record
    if len(functions)<1000:
        raise ValueError("Too few valid functions for whole-section Mercenaries report")
    if not any(f["section"]=="XPP" for f in normalized):
        raise ValueError("XPP section missing from recovered functions")
    target=functions.get(FRONTIER)
    containing=[f for f in normalized if address(f["address"])<=FRONTIER<address(f["end"])]
    # Allow missing exact target to be reported rather than pretending discovered.
    index=set(PRIORITIES)
    frontier_queue=collections.deque((FRONTIER,0) for _ in [0])
    visited=set()
    while frontier_queue and len(visited)<100:
        at,depth=frontier_queue.popleft()
        if at in visited:continue
        visited.add(at)
        f=functions.get(at)
        if f is None or depth>=2:continue
        for outgoing in f["calls_to"]:
            try:
                v=address(outgoing)
            except (TypeError,ValueError):
                continue
            if v in functions and v not in visited:
                frontier_queue.append((v,depth+1))
    index.update(visited)
    focus=[functions[i] for i in sorted(index) if i in functions]
    by_section=dict(sorted(collections.Counter(f["section"] for f in normalized).items()))
    no_body=[r for r in focus if not r["present_in_pixel_true_tus"]]
    summary=[
        "MERC360 XBOXRECOMP STATIC FUNCTION/ABI REPORT — NO ORIGINAL GAME BYTES",
        "Verified source: Mercenaries retail XBE, SHA256 "+ORIGINAL_SHA,
        "Stage 2 output read from SAVED DISASSEMBLY JSON — NO SPLITTER RESCAN.",
        "Sections discovered: "+", ".join("%s=%d"%x for x in by_section.items()),
        "Total detected function starts: %d"%len(normalized),
        "Heuristic ABI entries: %d"%len(abi),
        "PIXEL TrueTUs inspected: %d; compiled bodies: %d"%(tu_count,len(compiled)),
        "Hardware last stop: DIRECT 0023A3CE -> 002D5574 at 27,107,567 translated ticks",
        "Hardware fault=0, actual guest display_calls=0.",
        "Exact XPP target detected by xboxrecomp: "+str(target is not None),
        "Containing detected functions: "+(", ".join(f["address"]+".."+f["end"]
               for f in containing) or "NONE"),
        "Target source status (cross-check with original translated corpus required): "+
            ("PRESENT_IN_PIXEL_TRUE_TU" if target and target["present_in_pixel_true_tus"]
             else "MISSING_FROM_PIXEL_TRUE_TUS" if target else "NOT_IDENTIFIED_EXACTLY"),
        "Focused static graph entries: %d; not in Pixel TrueTUs: %d"%(len(focus),len(no_body)),
        "",
        "STATIC GUESSES, NOT PROVEN RUNTIME FRONTS. Check ABI and call graph against actual translated C.",
        "Static addresses can be missed or wrong; unknown indirect calls and real MMIO still require Xbox tests.",
        "Priority original XBE functions:",
    ]
    for f in focus[:80]:
        abi_name=f.get("calling_convention","UNKNOWN")
        summary.append(
            "%s [%s] bytes=%s confidence=%s ABI=%s compiled=%s outgoing=%s"%
            (f["address"],f["section"],f["size"],f["confidence"],
             abi_name,f["present_in_pixel_true_tus"],len(f["calls_to"])))
    outdir=a.out.resolve()
    outdir.mkdir(parents=True,exist_ok=True)
    path_manifest=outdir/"xboxrecomp_manifest.json"
    path_manifest.write_text(json.dumps({
        "functions":len(normalized),
        "with_abi":sum("calling_convention" in row for row in normalized),
        "sections":sorted(by_section),
        "source":"xboxrecomp saved disasm functions.json merged with abi_functions.json",
        "no_raw_game_bytes":True,
        "function_list":normalized
    },indent=2)+"\n",encoding="utf-8")
    (outdir/"merc360_frontier_focus.json").write_text(
        json.dumps({"hardware_frontier":"0x002D5574",
                    "target_exact":target,
                    "containing":containing[:5],
                    "reachable_two_hops":focus},indent=2)+"\n",encoding="utf-8")
    (outdir/"merc360_frontier_summary.txt").write_text("\n".join(summary)+"\n",encoding="utf-8")
    csv_path=outdir/"merc360_function_census.csv"
    with csv_path.open("w",newline="",encoding="utf-8-sig") as stream:
        fields=("address","end","name","section","size","confidence",
                "detection_method","calling_convention","heuristic_confidence",
                "estimated_params","frame_type","stack_frame_size",
                "present_in_pixel_true_tus","calls_to","called_by")
        writer=csv.DictWriter(stream,fieldnames=fields)
        writer.writeheader()
        for f in normalized:
            row={k:f.get(k,"") for k in fields}
            row["called_by"]=";".join(f["called_by"])
            row["calls_to"]=";".join(f["calls_to"])
            writer.writerow(row)
    zipname=a.zip.resolve()
    zipname.parent.mkdir(parents=True,exist_ok=True)
    with zipfile.ZipFile(zipname,"w",zipfile.ZIP_DEFLATED,compresslevel=6) as z:
        for name in ("xboxrecomp_manifest.json","merc360_frontier_focus.json",
                     "merc360_frontier_summary.txt","merc360_function_census.csv"):
            z.write(outdir/name,arcname=name)
    print("[XBR] REPORT PASS: %d functions, %d ABI records, XPP target exact=%s"%
          (len(normalized),len(abi),target is not None))
    print("[XBR] Pixel TrueTUs=%d, known compiled bodies=%d"%(tu_count,len(compiled)))
    print("[XBR] Focused reachable roots=%d, missing Pixel bodies=%d"%(
          len(focus),len(no_body)))
    print("[XBR] ZIP TO UPLOAD: "+str(zipname))
    print("[XBR] No private XBE, original guest instruction bytes, or generated source included")

def main():
    p=argparse.ArgumentParser()
    for name in ("xbe","functions","summary","abi","pixel-shards","out","zip"):
        p.add_argument("--"+name,type=Path,required=True)
    a=p.parse_args()
    build(a)

if __name__=="__main__":
    main()
