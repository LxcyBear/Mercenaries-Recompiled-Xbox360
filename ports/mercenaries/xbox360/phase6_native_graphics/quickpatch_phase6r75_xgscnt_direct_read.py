#!/usr/bin/env python3
"""R75: route ONE previously-unhandled direct XGSCNT read through APU core.

R74 proved sub_002DA923: ebx = GUEST_READ32(-25157620);
This equals 0xFE80200C (NV_PAPU_XGSCNT), the sample counter.
Our cached runtime already has phase6ch_apu_read32: core range + shadow.
R75 changes ONLY that read site, NOT the existing MMIO routing rules.
The core shadow is a bootstrap model (XGSCNT zero absent audio frames);
it is not equivalent to a running 48kHz sample counter.
R72 repaired the actual DirectSound pool; preserve every overlay.
Do not forge data, modify other MMIO, or bypass unknown hard fences.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

REV="R75-XGSCNT-EXACT-READ-20261029"
TAG="P6DQ R75 APU XGSCNT ROUTED:"
TARGET=0x002DA923
RX=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9a-fA-F]{8})\(void\)\s*\{")
CHAIN=[
 ("r62","R62-QUICK-TU-AUDIO-20261029","original_r59_shards",{"translated_022.cpp","translated_042.cpp"}),
 ("r63","R63-FAST-BRANCH-PROVENANCE-20261029","original_r62_shards",{"translated_022.cpp","translated_055.cpp"}),
 ("r66","R66-CACHED-TU-POOL-PROVENANCE-20261029","original_r63_shards",{"translated_032.cpp","translated_034.cpp","translated_036.cpp","translated_056.cpp"}),
 ("r69","R69-CACHED-TU-SEED-LINEAGE-SAFE-20261029","original_r66_shards",{"translated_008.cpp","translated_042.cpp"}),
 ("r71","R71-FC4A-A19FC-GUEST-OBJECT-ABI-20261029","original_r69_shards",{"translated_053.cpp"}),
 ("r72","R72-A19FC-ESI-NESTED-CALLEE-20261029","original_r71_shards",{"translated_008.cpp"}),
]

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def overlay(folder:Path,rev:str):
    p=folder/"quick-shard-overlay.json"
    if not p.is_file():raise RuntimeError(f"Missing overlay {p}")
    d=json.loads(p.read_text(encoding="utf-8"))
    rows=d.get("patched")
    if d.get("revision")!=rev or not isinstance(rows,list) or not rows:
        raise RuntimeError(f"Invalid overlay revision {p}")
    if len({r.get("name") for r in rows})!=len(rows):
        raise RuntimeError(f"Duplicate patched shard names in {p}")
    return rows

def verify_apu_router(path:Path)->None:
    text=path.read_text(encoding="utf-8",errors="replace")
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in text:
        raise RuntimeError("Cached main build identity changed")
    if not re.search(r"#define\s+PHASE6CH_APU_XGSCNT\s+0x0000200Cu",text):
        raise RuntimeError("Missing documented XGSCNT 0x200C register definition")
    name="uint32_t phase6ch_apu_read32(uint32_t address)"
    if text.count(name)!=1:
        raise RuntimeError("Cached core read32 router definition not unique")
    offset=text.index(name)
    start=text.index("{",offset)
    end=closing_brace(text,start)
    handler=text[offset:end]
    if not all(term in handler for term in (
        "phase6ch_apu_core_range(address, 4u, &offset)",
        "phase6ch_apu_shadow_read(address, 4u)",
        "return value;")):
        raise RuntimeError("Expected core shadow read32 handler changed")
    if ("PHASE6CH_APU_BASE" not in text or
        "PHASE6CH_APU_CORE_SIZE" not in text):
        raise RuntimeError("APU core range constants unavailable")
    print("[Phase6R75] APU router contract PASS: XGSCNT offset 0x200C through core shadow")

def patch(text:str)->str:
    matches=[m for m in RX.finditer(text) if int(m.group(1),16)==TARGET]
    if len(matches)!=1:
        raise RuntimeError(f"sub_002DA923 definition count={len(matches)}")
    m=matches[0]
    brace=text.index("{",m.start(),m.end())
    end=closing_brace(text,brace)
    body=text[m.start():end]
    anchor="    ebx = GUEST_READ32(-25157620);"
    replacement="""    /* R75: exact NV_PAPU_XGSCNT direct MMIO read. Route through the
       existing core-shadow model; do not fake a timer or bypass MMIO. */
    ebx = phase6ch_apu_read32(0xFE80200Cu);
    {
        static unsigned int r75_xgscnt_reads = 0u;
        ++r75_xgscnt_reads;
        if (r75_xgscnt_reads <= 8u)
        {
            char r75_line[224];
            sprintf(r75_line,
                "P6DQ R75 APU XGSCNT ROUTED: count=%u addr=FE80200C value=%08X guest_va=002DA923",
                (unsigned int)r75_xgscnt_reads, (unsigned int)ebx);
            trace(r75_line);
        }
    }"""
    if TAG in body:
        raise RuntimeError("R75 marker already in the untranslated baseline")
    if body.count(anchor)!=1:
        raise RuntimeError(f"R74-proven raw XGSCNT site changed: count={body.count(anchor)}")
    if body.count("/* TODO: cli  */")!=1 or body.count("/* TODO: sti  */")!=1:
        raise RuntimeError("R74 instruction context unexpectedly changed")
    body=body.replace(anchor,replacement,1)
    if body.count(TAG)!=1 or body.count("phase6ch_apu_read32(0xFE80200Cu)")!=1:
        raise RuntimeError("Unexpected R75 replacement result")
    return text[:m.start()]+body+text[end:]

def main():
    p=argparse.ArgumentParser()
    for key in ("tu-dir","r62-dir","r63-dir","r66-dir","r69-dir","r71-dir","r72-dir","out-dir"):
        p.add_argument("--"+key,type=Path,required=True)
    x=p.parse_args()
    tu=x.tu_dir
    m=json.loads((tu/"phase6tu-manifest.json").read_text(encoding="utf-8"))
    entries=m.get("shards",[])
    if (m.get("phase")!="6TU" or m.get("shard_count")!=64
        or m.get("translated_functions")!=13510 or len(entries)!=64
        or sum(e["functions"] for e in entries)!=13510
        or len({e["name"] for e in entries})!=64):
        raise RuntimeError("Expected exact R59 TrueTU manifest with 64 shards")
    verify_apu_router(tu/"main.cpp")
    shards=tu/"translated_shards"
    paths=sorted(shards.glob("translated_*.cpp"))
    expected={r["name"]:r["sha256"] for r in entries}
    if len(paths)!=64 or {f.name for f in paths}!=set(expected):
        raise RuntimeError("Cached 64-shard filenames do not match original manifest")
    for key,rev,back_dir,owners in CHAIN:
        folder=getattr(x,key+"_dir")
        rows=overlay(folder,rev)
        if {r["name"] for r in rows}!=owners:
            raise RuntimeError(f"{key} modified-shard set differs")
        for r in rows:
            name=r["name"]
            original=folder/back_dir/name
            if (expected[name]!=r["original_sha256"] or not original.is_file()
                or sha(original.read_bytes())!=r["original_sha256"]):
                raise RuntimeError(f"{key} original hash or backup failed for {name}")
            expected[name]=r["modified_sha256"]
    out=x.out_dir
    manifest=out/"quick-shard-overlay.json"
    backup=out/"original_r72_shards"
    prev=None
    if manifest.exists():
        prev=overlay(out,REV)
        if len(prev)!=1:
            raise RuntimeError("R75 reuse: expected single patched shard")
        r=prev[0]
        b=backup/r["name"]
        if expected[r["name"]]!=r["original_sha256"] or not b.is_file() or sha(b.read_bytes())!=r["original_sha256"]:
            raise RuntimeError("R75 backup no longer matches R72 baseline")
        expected[r["name"]]=r["modified_sha256"]
    current={}
    for path in paths:
        raw=path.read_bytes()
        if sha(raw)!=expected[path.name]:
            raise RuntimeError(f"R75 64-shard SHA mismatch {path.name}: expected {expected[path.name]} got {sha(raw)}")
        current[path.name]=raw
    if prev is not None:
        if TAG not in current[prev[0]["name"]].decode("utf-8"):
            raise RuntimeError("R75 reuse marker missing from patched shard")
        print("[Phase6R75] REUSE PASS: 64/64 SHA checks and all overlay backups match")
        print("[Phase6R75] patched_shards=1 untouched_shards=63")
        return 0
    owners=[]
    for name,raw in current.items():
        if any(int(m.group(1),16)==TARGET for m in RX.finditer(raw.decode("utf-8"))):
            owners.append(name)
    if len(owners)!=1:
        raise RuntimeError(f"Expected one sub_002DA923 TrueTU owner, found {owners}")
    name=owners[0]
    before=current[name]
    after=patch(before.decode("utf-8")).encode("utf-8")
    backup.mkdir(parents=True,exist_ok=True)
    original=backup/name
    if original.exists() and original.read_bytes()!=before:
        raise RuntimeError("R75 R72-original source backup collision")
    if not original.exists():original.write_bytes(before)
    (shards/name).write_bytes(after)
    out.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps({
        "revision":REV,"patched":[{"name":name,"original_sha256":sha(before),"modified_sha256":sha(after)}],
        "translated_functions":13510,"source_revision":"R72-A19FC-ESI-NESTED-CALLEE-20261029"
    },indent=2)+"\n",encoding="utf-8")
    print("[Phase6R75] EXACT DIRECT NV_PAPU_XGSCNT READ ROUTE PATCH PASS")
    print(f"[Phase6R75] owner={name} guest_function=sub_002DA923")
    print("[Phase6R75] GUEST_READ32(-25157620) -> phase6ch_apu_read32(0xFE80200C)")
    print("[Phase6R75] No clock fabrication, no global MMIO changes, other unknowns fenced")
    print("[Phase6R75] R72 audio pool repair preserved, no emitter or re-sharding")
    print("[Phase6R75] patched_shards=1 untouched_shards=63")
    print("[Phase6R75] Marker: "+TAG)
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R75] PREBUILD FAILURE: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
