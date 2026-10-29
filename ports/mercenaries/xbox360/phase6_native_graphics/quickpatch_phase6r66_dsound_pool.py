#!/usr/bin/env python3
"""R66: hardware proof of the actual DirectSound E_OUTOFMEMORY producer.

R63 Xbox: A5770 -> 8007000E, A4238/A5309 not yet separated.
R65 source: A0F98 only emits 00000000 or 88780032; A5309 explicitly
emits 8007000E when A2E38 returns zero. A2E38 first searches its
resource list then calls A2AA1 (pool free-list allocator).
Capture BOTH status paths and the pool-head/return values; do not
synthesize success, alter registers, guest memory, or MMIO policy.

Uses R59 TrueTU cached 64 files with the R62 and R63 hash-verified
overlays already applied. Target shard owners are discovered, not
guessed. Verify original manifest, original R62/R63 backup hashes,
and ALL currently installed shard hashes before modifying anything.
Back up the exact R63-state shard bytes; re-runs are idempotent.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

TAG="P6DQ R66 DSOUND POOL:"
REV="R66-CACHED-TU-POOL-PROVENANCE-20261029"
TARGETS=(0x002A545F,0x002A5309,0x002A2E38,0x002A2AA1)
TARGET_RX=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})\(void\)\s*\{")

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def trace(site:str)->str:
    return (
        "\n    {\n"
        "        static unsigned int r66_hits = 0u;\n"
        "        ++r66_hits;\n"
        "        if (r66_hits <= 8u)\n"
        "        {\n"
        "            char r66_line[260];\n"
        "            sprintf(r66_line,\n"
        f'                "P6DQ R66 DSOUND POOL: {site} n=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",\n'
        "                (unsigned int)r66_hits, (unsigned int)eax, (unsigned int)ecx,\n"
        "                (unsigned int)edx, (unsigned int)ebx, (unsigned int)esi,\n"
        "                (unsigned int)edi, (unsigned int)esp);\n"
        "            trace(r66_line);\n"
        "        }\n"
        "    }\n"
    )

def after(line:str,site:str):
    return line,line+trace(site)

ANCHORS={
    0x002A545F:[
        after("    PUSH32(esp, 0); sub_002A4238(); /* call 0x002A4238 */","A545F_AFTER_A4238"),
        after("    PUSH32(esp, 0); sub_002A5309(); /* call 0x002A5309 */","A545F_AFTER_A5309"),
    ],
    0x002A5309:[
        after("    PUSH32(esp, 0); sub_002A2E38(); /* call 0x002A2E38 */","A5309_AFTER_A2E38"),
        after("    edi = 0x8007000Eu;","A5309_EXPLICIT_8007000E"),
    ],
    0x002A2E38:[
        after("    esi = esi >> 0xC;","A2E38_REQUEST_PAGES"),
        after("    PUSH32(esp, 0); sub_002A2AA1(); /* call 0x002A2AA1 */","A2E38_AFTER_A2AA1"),
        after("    eax = edi;","A2E38_RETURN_RESOURCE"),
    ],
    0x002A2AA1:[
        after("    eax = phase6ch_apu_read32(edi + 0x18);","A2AA1_POOL_HEAD"),
        after("    PUSH32(esp, 0); sub_002A2977(); /* call 0x002A2977 */","A2AA1_AFTER_A2977"),
        after("    eax = esi;","A2AA1_FINAL_RESOURCE"),
    ],
}

def edit_function(src:str,va:int)->str:
    matches=[m for m in TARGET_RX.finditer(src) if int(m.group(1),16)==va]
    if len(matches)!=1:
        raise RuntimeError(f"sub_{va:08X}: expected one definition, got {len(matches)}")
    m=matches[0]
    brace=src.find("{",m.start(),m.end())
    end=closing_brace(src,brace)
    body=src[m.start():end]
    if TAG in body:
        raise RuntimeError(f"sub_{va:08X}: R66 marker already exists; inconsistent patch state")
    for needle,replacement in ANCHORS[va]:
        count=body.count(needle)
        if count!=1:
            raise RuntimeError(f"sub_{va:08X}: anchor match count={count}, expected=1: {needle!r}")
        body=body.replace(needle,replacement,1)
    if body.count(TAG)!=len(ANCHORS[va]):
        raise RuntimeError(f"sub_{va:08X}: resulting probe count mismatch")
    return src[:m.start()]+body+src[end:]

def read_record(folder:Path,expected_rev:str):
    path=folder/"quick-shard-overlay.json"
    if not path.is_file():
        raise RuntimeError(f"missing patch record: {path}")
    record=json.loads(path.read_text(encoding="utf-8"))
    if record.get("revision")!=expected_rev:
        raise RuntimeError(f"patch revision mismatch: {path}")
    rows=record.get("patched")
    if not isinstance(rows,list) or not rows or any(
        not isinstance(item.get("name"),str)
        or not isinstance(item.get("original_sha256"),str)
        or not isinstance(item.get("modified_sha256"),str) for item in rows
    ):
        raise RuntimeError(f"malformed patch record: {path}")
    return rows

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--tu-dir",type=Path,required=True)
    p.add_argument("--r62-dir",type=Path,required=True)
    p.add_argument("--r63-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    tu=args.tu_dir
    shards=tu/"translated_shards"
    mpath=tu/"phase6tu-manifest.json"
    if not mpath.is_file():
        raise RuntimeError(f"R59 manifest missing: {mpath}")
    m=json.loads(mpath.read_text(encoding="utf-8"))
    source_rows=m.get("shards",[])
    if (m.get("phase")!="6TU" or m.get("shard_count")!=64
            or len(source_rows)!=64 or len({x["name"] for x in source_rows})!=64
            or sum(x["functions"] for x in source_rows)!=m.get("translated_functions")):
        raise RuntimeError("TrueTU baseline manifest malformed")
    main_cpp=tu/"main.cpp"
    if not main_cpp.is_file() or "P6DQ-R51-MM173-FRAME-20261029-A" not in main_cpp.read_text(encoding="utf-8",errors="replace"):
        raise RuntimeError("R59 generated main build tag is missing")
    expected={item["name"]:item["sha256"] for item in source_rows}
    files=sorted(shards.glob("translated_*.cpp"))
    if len(files)!=64 or set(f.name for f in files)!=set(expected):
        raise RuntimeError("Expected exactly 64 original TrueTU shard filenames")
    r62=read_record(args.r62_dir,"R62-QUICK-TU-AUDIO-20261029")
    r63=read_record(args.r63_dir,"R63-FAST-BRANCH-PROVENANCE-20261029")
    if {item["name"] for item in r62}!={"translated_022.cpp","translated_042.cpp"}:
        raise RuntimeError("R62 expected shard owners missing")
    if {item["name"] for item in r63}!={"translated_022.cpp","translated_055.cpp"}:
        raise RuntimeError("R63 expected shard owners missing")
    for row in r62:
        name=row["name"]
        backup=args.r62_dir/"original_r59_shards"/name
        if expected[name]!=row["original_sha256"] or not backup.is_file() or sha(backup.read_bytes())!=row["original_sha256"]:
            raise RuntimeError(f"R62 original backup/manifest identity failed: {name}")
        expected[name]=row["modified_sha256"]
    for row in r63:
        name=row["name"]
        backup=args.r63_dir/"original_r62_shards"/name
        if expected[name]!=row["original_sha256"] or not backup.is_file() or sha(backup.read_bytes())!=row["original_sha256"]:
            raise RuntimeError(f"R63 original backup/manifest identity failed: {name}")
        expected[name]=row["modified_sha256"]
    out=args.out_dir
    ownpath=out/"quick-shard-overlay.json"
    backupdir=out/"original_r63_shards"
    previous=None
    if ownpath.exists():
        previous=read_record(out,REV)
        for row in previous:
            name=row["name"]
            prev=backupdir/name
            if expected[name]!=row["original_sha256"] or not prev.is_file() or sha(prev.read_bytes())!=row["original_sha256"]:
                raise RuntimeError(f"R66 original shard backup changed: {name}")
            expected[name]=row["modified_sha256"]
    # Validate the complete emitted corpus before target discovery or mutation.
    current={}
    for f in files:
        raw=f.read_bytes()
        if sha(raw)!=expected[f.name]:
            raise RuntimeError(f"R66 cached corpus changed unexpectedly: {f.name} expected {expected[f.name]} got {sha(raw)}")
        current[f.name]=raw
    if previous is not None:
        print("[Phase6R66] REUSE PASS: 64/64 original and R62/R63/R66 overlay hashes match",flush=True)
        print(f"[Phase6R66] patched_shards={len(previous)} untouched_shards={64-len(previous)}",flush=True)
        return 0

    owner={}
    for name,raw in current.items():
        text=raw.decode("utf-8")
        for match in TARGET_RX.finditer(text):
            va=int(match.group(1),16)
            if va in TARGETS:
                if va in owner:
                    raise RuntimeError(f"duplicate translated function owner sub_{va:08X}")
                owner[va]=name
    if set(owner)!=set(TARGETS):
        raise RuntimeError("R66 missing exact translated function(s): "+
                           ",".join(f"{va:08X}" for va in sorted(set(TARGETS)-set(owner))))
    grouped={}
    for va,name in owner.items():
        grouped.setdefault(name,[]).append(va)
    staged={}
    for name,vas in grouped.items():
        raw=current[name]
        text=raw.decode("utf-8")
        for va in vas:
            text=edit_function(text,va)
        staged[name]=(raw,text.encode("utf-8"))
    backupdir.mkdir(parents=True,exist_ok=True)
    for name,(raw,_) in staged.items():
        target=backupdir/name
        if target.exists() and target.read_bytes()!=raw:
            raise RuntimeError(f"R66 pre-existing backup mismatch: {name}")
        if not target.exists():
            target.write_bytes(raw)
    record=[]
    for name,(raw,modified) in sorted(staged.items()):
        (shards/name).write_bytes(modified)
        record.append({"name":name,"original_sha256":sha(raw),"modified_sha256":sha(modified)})
    out.mkdir(parents=True,exist_ok=True)
    ownpath.write_text(json.dumps({"revision":REV,"patched":record,
        "translated_functions":m["translated_functions"],"r63":"R63-FAST-BRANCH-PROVENANCE-20261029"},indent=2)+"\n",encoding="utf-8")
    print("[Phase6R66] CACHED TRUE-TU DSOUND RESOURCE POOL PROBE PATCH PASS",flush=True)
    for va in TARGETS:
        print(f"[Phase6R66] sub_{va:08X} owner={owner[va]} probes={len(ANCHORS[va])}")
    print(f"[Phase6R66] patched_shards={len(staged)} untouched_shards={64-len(staged)}")
    print("[Phase6R66] Full source/emitter/sharder not run, no XEX mutated")
    print("[Phase6R66] Markers: P6DQ R66 DSOUND POOL:")
    print("[Phase6R66] R59, R62 and R63 published XEX files remain intact")
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R66] PREBUILD FAILURE: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
