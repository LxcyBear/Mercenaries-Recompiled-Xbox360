#!/usr/bin/env python3
"""R72: restore DSOUND A19FC's live object ESI across nested callees.

R71 Xbox hardware proof:
 FC4A before A19FC: ECX=01B5C554, stored [outer+0xC]=01B5C554.
 R69 immediately after A739F: ESI=0, while EDI=01B5C554.
 Therefore A19FC calls A2A16 with ECX=0+0x60 and seeds guest [0x78],
 not the actual free-list [01B5C5CC]. R66 returns 8007000E.
 R71 also recorded A19FC ESP 008BF8CC -> 008BF8D0 (+4).
This repair saves original live ESI before A739F and A2A16; restores
guest x86 callee-save ESI on return, and records raw clobber and
ESP delta. No ESP correction, EAX or HRESULT change, guest write,
MMIO change, invented pointer, or whole-corpus regeneration.

Requires exact R59/R62/R63/R66/R69-safe/R71 overlays. One shard.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

REV="R72-A19FC-ESI-NESTED-CALLEE-20261029"
TAG="P6DQ R72 DSOUND NESTED ABI:"
TARGET=0x002A19FC
RX=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9a-fA-F]{8})\(void\)\s*\{")
CHAIN=[
 ("r62","R62-QUICK-TU-AUDIO-20261029","original_r59_shards",{"translated_022.cpp","translated_042.cpp"}),
 ("r63","R63-FAST-BRANCH-PROVENANCE-20261029","original_r62_shards",{"translated_022.cpp","translated_055.cpp"}),
 ("r66","R66-CACHED-TU-POOL-PROVENANCE-20261029","original_r63_shards",{"translated_032.cpp","translated_034.cpp","translated_036.cpp","translated_056.cpp"}),
 ("r69","R69-CACHED-TU-SEED-LINEAGE-SAFE-20261029","original_r66_shards",{"translated_008.cpp","translated_042.cpp"}),
 ("r71","R71-FC4A-A19FC-GUEST-OBJECT-ABI-20261029","original_r69_shards",{"translated_053.cpp"}),
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

def trace_wrapper(site:str,callee:str)->str:
    return (
        "    {\n"
        f"        /* R72: guest ESI is callee-saved; retain A19FC's live object across {callee}. */\n"
        "        const uint32_t r72_before_esi = esi;\n"
        "        const uint32_t r72_before_esp = esp;\n"
        f"        PUSH32(esp, 0); sub_{callee}(); /* call 0x{callee} */\n"
        "        const uint32_t r72_raw_esi = esi;\n"
        "        const uint32_t r72_raw_esp = esp;\n"
        "        esi = r72_before_esi;\n"
        "        static unsigned int r72_hits = 0u;\n"
        "        ++r72_hits;\n"
        "        if (r72_hits <= 8u)\n"
        "        {\n"
        "            char r72_line[320];\n"
        "            sprintf(r72_line,\n"
        f'                "P6DQ R72 DSOUND NESTED ABI: {site} n=%u before_esi=%08X raw_esi=%08X restored_esi=%08X eax=%08X esp_before=%08X esp_after=%08X",\n'
        "                (unsigned int)r72_hits, (unsigned int)r72_before_esi,\n"
        "                (unsigned int)r72_raw_esi, (unsigned int)esi,\n"
        "                (unsigned int)eax, (unsigned int)r72_before_esp,\n"
        "                (unsigned int)r72_raw_esp);\n"
        "            trace(r72_line);\n"
        "        }\n"
        "    }\n"
    )

def patch(text:str)->str:
    matches=[m for m in RX.finditer(text) if int(m.group(1),16)==TARGET]
    if len(matches)!=1:raise RuntimeError(f"A19FC translated owner definition count={len(matches)}")
    m=matches[0]
    brace=text.index("{",m.start(),m.end())
    end=closing_brace(text,brace)
    body=text[m.start():end]
    if TAG in body:raise RuntimeError("R72 markers already present: unexpected partial patch")
    if "P6DQ R69 DSOUND SEED:" not in body:
        raise RuntimeError("A19FC R69 probes missing (wrong cache baseline)")
    for callee,site in (("002A739F","AFTER_A739F"),("002A2A16","AFTER_A2A16")):
        anchor=f"    PUSH32(esp, 0); sub_{callee}(); /* call 0x{callee} */"
        if body.count(anchor)!=1:
            raise RuntimeError(f"Expected one exact {callee} call, found {body.count(anchor)}")
        body=body.replace(anchor,trace_wrapper(site,callee).rstrip("\n"),1)
    if body.count(TAG)!=2:
        raise RuntimeError("Expected two live R72 trace sites")
    return text[:m.start()]+body+text[end:]

def main():
    p=argparse.ArgumentParser()
    for key in ("tu-dir","r62-dir","r63-dir","r66-dir","r69-dir","r71-dir","out-dir"):
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
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in (tu/"main.cpp").read_text(encoding="utf-8",errors="replace"):
        raise RuntimeError("R59 main build identity mismatch")
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
    backup=out/"original_r71_shards"
    prev=None
    if manifest.exists():
        prev=overlay(out,REV)
        if len(prev)!=1 or prev[0]["name"]!="translated_008.cpp":
            raise RuntimeError("R72 prior owner mismatch")
        r=prev[0]
        b=backup/r["name"]
        if expected[r["name"]]!=r["original_sha256"] or not b.is_file() or sha(b.read_bytes())!=r["original_sha256"]:
            raise RuntimeError("R72 backup no longer matches R71 baseline")
        expected[r["name"]]=r["modified_sha256"]
    current={}
    for path in paths:
        raw=path.read_bytes()
        if sha(raw)!=expected[path.name]:
            raise RuntimeError(f"R72 64-shard SHA mismatch {path.name}: expected {expected[path.name]} got {sha(raw)}")
        current[path.name]=raw
    if prev is not None:
        print("[Phase6R72] REUSE PASS: 64/64 SHA checks and all overlay backups match")
        print("[Phase6R72] patched_shards=1 untouched_shards=63")
        return 0
    owners=[]
    for name,raw in current.items():
        if any(int(m.group(1),16)==TARGET for m in RX.finditer(raw.decode("utf-8"))):
            owners.append(name)
    if owners!=["translated_008.cpp"]:
        raise RuntimeError(f"Expected A19FC only in translated_008.cpp, found {owners}")
    name=owners[0]
    before=current[name]
    after=patch(before.decode("utf-8")).encode("utf-8")
    backup.mkdir(parents=True,exist_ok=True)
    original=backup/name
    if original.exists() and original.read_bytes()!=before:
        raise RuntimeError("R72 backup collision")
    if not original.exists():original.write_bytes(before)
    (shards/name).write_bytes(after)
    out.mkdir(parents=True,exist_ok=True)
    manifest.write_text(json.dumps({
        "revision":REV,"patched":[{"name":name,"original_sha256":sha(before),"modified_sha256":sha(after)}],
        "translated_functions":13510,"source_revision":"R71-FC4A-A19FC-GUEST-OBJECT-ABI-20261029"
    },indent=2)+"\n",encoding="utf-8")
    print("[Phase6R72] ONE-SHARD A19FC NESTED-CALL GUEST ESI ABI REPAIR PATCH PASS")
    print("[Phase6R72] owner=translated_008.cpp sub_002A19FC")
    print("[Phase6R72] ESI saved/restored across A739F and A2A16; EAX/ESP/HRESULT untouched")
    print("[Phase6R72] R71/R69/R66 probes retained. No resource forgery, no emitter or re-sharding")
    print("[Phase6R72] patched_shards=1 untouched_shards=63")
    print("[Phase6R72] Marker: "+TAG)
    return 0

if __name__=="__main__":
    try:raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R72] PREBUILD FAILURE: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
