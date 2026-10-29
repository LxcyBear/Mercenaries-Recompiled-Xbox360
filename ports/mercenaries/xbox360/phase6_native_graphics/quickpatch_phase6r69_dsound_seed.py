#!/usr/bin/env python3
"""Phase6R69: trace REAL DirectSound page-pool seed, 2 cached TrueTU shards.

R66 Xbox proved A5309 emits 8007000E because A2AA1 sees head=0.
R68 source proves FC4A -> A19FC -> A2A16 -> FF54 -> A2977 seeds head,
using A19FC's 0x7FF page-entry count. The missing evidence is whether
A19FC/A2A16 ran, whether A739F was successful, whether FF54 allocated
the storage, and whether A2977 returned a valid entry to pool+0x18.
Instrumentation is observational ONLY. No status/pointer coercion,
guest write, MMIO change, or translated-function regeneration.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

TAG="P6DQ R69 DSOUND SEED:"
REV="R69-CACHED-TU-SEED-LINEAGE-20261029"
ROOTS=(0x002A19FC,0x002A2A16)
RX=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})\(void\)\s*\{")
REV_CHAIN=(
 ("r62","R62-QUICK-TU-AUDIO-20261029","original_r59_shards",{"translated_022.cpp","translated_042.cpp"}),
 ("r63","R63-FAST-BRANCH-PROVENANCE-20261029","original_r62_shards",{"translated_022.cpp","translated_055.cpp"}),
 ("r66","R66-CACHED-TU-POOL-PROVENANCE-20261029","original_r63_shards",{"translated_032.cpp","translated_034.cpp","translated_036.cpp","translated_056.cpp"}),
)

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def log(site:str,head:str="0u",backing:str="0u")->str:
    return (
      "\n    {\n"
      "        static unsigned int r69_count = 0u;\n"
      "        ++r69_count;\n"
      "        if (r69_count <= 6u)\n"
      "        {\n"
      f"            const unsigned int r69_head = (unsigned int)({head});\n"
      f"            const unsigned int r69_backing = (unsigned int)({backing});\n"
      "            char r69_line[300];\n"
      "            sprintf(r69_line,\n"
      f'                "P6DQ R69 DSOUND SEED: {site} n=%u eax=%08X ecx=%08X esi=%08X edi=%08X ebx=%08X esp=%08X head=%08X backing=%08X",\n'
      "                r69_count, (unsigned int)eax, (unsigned int)ecx,\n"
      "                (unsigned int)esi, (unsigned int)edi,\n"
      "                (unsigned int)ebx, (unsigned int)esp,\n"
      "                r69_head, r69_backing);\n"
      "            trace(r69_line);\n"
      "        }\n"
      "    }\n"
    )

def post(anchor:str,site:str,head:str="0u",backing:str="0u"):
    return anchor,anchor+log(site,head,backing)

ANCHORS={
  0x002A19FC:[
    post("    PUSH32(esp, 0); sub_002A739F(); /* call 0x002A739F */","A19FC_AFTER_A739F"),
    post("    PUSH32(esp, 0); sub_002A2A16(); /* call 0x002A2A16 */","A19FC_AFTER_A2A16",
         "phase6ch_apu_read32(esi + 0x78u)","phase6ch_apu_read32(esi + 0x74u)"),
  ],
  0x002A2A16:[
    post("    PUSH32(esp, 0); sub_0029FF54(); /* call 0x0029FF54 */","A2A16_AFTER_FF54"),
    post("    PUSH32(esp, 0); sub_002A2977(); /* call 0x002A2977 */","A2A16_AFTER_A2977",
         "phase6ch_apu_read32(esi + 0x18u)","phase6ch_apu_read32(esi + 0x14u)"),
    post("    phase6ch_apu_write32(esi + 0x18, eax);","A2A16_STORED_HEAD",
         "phase6ch_apu_read32(esi + 0x18u)","phase6ch_apu_read32(esi + 0x14u)"),
    post("    eax = ebx;","A2A16_FINAL_STATUS",
         "phase6ch_apu_read32(esi + 0x18u)","phase6ch_apu_read32(esi + 0x14u)"),
  ],
}

def patch_one(source:str,va:int)->str:
    found=[m for m in RX.finditer(source) if int(m.group(1),16)==va]
    if len(found)!=1:raise RuntimeError(f"sub_{va:08X}: expected 1 body, found {len(found)}")
    m=found[0]
    br=source.find("{",m.start(),m.end())
    end=closing_brace(source,br)
    body=source[m.start():end]
    if TAG in body:raise RuntimeError(f"sub_{va:08X}: pre-existing R69 probe")
    for original,modified in ANCHORS[va]:
        if body.count(original)!=1:
            raise RuntimeError(f"sub_{va:08X}: anchor count {body.count(original)}: {original!r}")
        body=body.replace(original,modified,1)
    if body.count(TAG)!=len(ANCHORS[va]):
        raise RuntimeError(f"sub_{va:08X}: marker count mismatch")
    return source[:m.start()]+body+source[end:]

def read_record(folder:Path,rev:str):
    path=folder/"quick-shard-overlay.json"
    if not path.is_file():raise RuntimeError(f"missing overlay record {path}")
    data=json.loads(path.read_text(encoding="utf-8"))
    rows=data.get("patched")
    if data.get("revision")!=rev or not isinstance(rows,list) or not rows:
        raise RuntimeError(f"overlay invalid revision/rows {path}")
    if len({r["name"] for r in rows})!=len(rows):
        raise RuntimeError(f"duplicate patched shard in {path}")
    return rows

def main()->int:
    p=argparse.ArgumentParser()
    for field in ("tu-dir","r62-dir","r63-dir","r66-dir","out-dir"):
        p.add_argument("--"+field,required=True,type=Path)
    x=p.parse_args()
    tu=x.tu_dir
    shards=tu/"translated_shards"
    manifest_path=tu/"phase6tu-manifest.json"
    m=json.loads(manifest_path.read_text(encoding="utf-8"))
    rows=m.get("shards",[])
    if (m.get("phase")!="6TU" or m.get("shard_count")!=64
        or len(rows)!=64 or len({i["name"] for i in rows})!=64
        or sum(i["functions"] for i in rows)!=m.get("translated_functions")
        or m["translated_functions"]!=13510):
        raise RuntimeError("R59 TrueTU manifest is inconsistent")
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in (tu/"main.cpp").read_text(encoding="utf-8",errors="replace"):
        raise RuntimeError("Expected R59/TrueTU build marker missing")
    expected={row["name"]:row["sha256"] for row in rows}
    paths=sorted(shards.glob("translated_*.cpp"))
    if len(paths)!=64 or set(p.name for p in paths)!=set(expected):
        raise RuntimeError("TrueTU shard file set changed")
    for key,rev,backup_folder,names in REV_CHAIN:
        folder=getattr(x,key+"_dir")
        overlay=read_record(folder,rev)
        if {r["name"] for r in overlay}!=names:
            raise RuntimeError(f"{key} modified shard identities differ")
        for row in overlay:
            name=row["name"]
            backup=folder/backup_folder/name
            if (expected[name]!=row["original_sha256"]
                or not backup.is_file() or sha(backup.read_bytes())!=row["original_sha256"]):
                raise RuntimeError(f"{key} baseline backup/hash mismatch: {name}")
            expected[name]=row["modified_sha256"]
    out=x.out_dir
    overlay_path=out/"quick-shard-overlay.json"
    backup_dir=out/"original_r66_shards"
    prior=None
    if overlay_path.exists():
        prior=read_record(out,REV)
        if {r["name"] for r in prior}!={"translated_008.cpp","translated_042.cpp"}:
            raise RuntimeError("R69 overlay owner mismatch")
        for row in prior:
            name=row["name"]
            b=backup_dir/name
            if expected[name]!=row["original_sha256"] or not b.is_file() or sha(b.read_bytes())!=row["original_sha256"]:
                raise RuntimeError(f"R69 previous state backup corrupt: {name}")
            expected[name]=row["modified_sha256"]
    current={}
    for f in paths:
        raw=f.read_bytes()
        if sha(raw)!=expected[f.name]:
            raise RuntimeError(f"R69 64-shard source drift: {f.name} expected={expected[f.name]} actual={sha(raw)}")
        current[f.name]=raw
    if prior is not None:
        print("[Phase6R69] REUSE PASS: 64/64 baseline/overlay hashes and backups verified")
        print("[Phase6R69] patched_shards=2 untouched_shards=62")
        return 0
    owners={}
    for name,raw in current.items():
        for match in RX.finditer(raw.decode("utf-8")):
            va=int(match.group(1),16)
            if va in ROOTS:
                if va in owners:raise RuntimeError(f"duplicate function sub_{va:08X}")
                owners[va]=name
    if set(owners)!=set(ROOTS):
        raise RuntimeError(f"missing owner(s): {set(ROOTS)-set(owners)}")
    if owners!={0x002A19FC:"translated_008.cpp",0x002A2A16:"translated_042.cpp"}:
        raise RuntimeError(f"Unexpected deterministic owners {owners}")
    staged={}
    for va,name in owners.items():
        before=current[name]
        after=patch_one(before.decode("utf-8"),va).encode("utf-8")
        staged[name]=(before,after)
    # Validate ALL changes before any guest source is overwritten.
    backup_dir.mkdir(parents=True,exist_ok=True)
    for name,(before,_) in staged.items():
        b=backup_dir/name
        if b.exists() and b.read_bytes()!=before:
            raise RuntimeError(f"R69 backup mismatch; refusing overwrite: {name}")
        if not b.exists():b.write_bytes(before)
    created=[]
    for name,(before,after) in sorted(staged.items()):
        (shards/name).write_bytes(after)
        created.append({"name":name,"original_sha256":sha(before),"modified_sha256":sha(after)})
    out.mkdir(parents=True,exist_ok=True)
    overlay_path.write_text(json.dumps({"revision":REV,"patched":created,
        "translated_functions":13510,"source_revision":"R66-CACHED-TU-POOL-PROVENANCE-20261029"},indent=2)+"\n",encoding="utf-8")
    print("[Phase6R69] CONSTRUCTOR/POOL SEED TRACE PATCH PASS")
    for va,name in sorted(owners.items()):
        print(f"[Phase6R69] probe sub_{va:08X} owner={name} sites={len(ANCHORS[va])}")
    print("[Phase6R69] patched_shards=2 untouched_shards=62")
    print("[Phase6R69] Existing R66 audio-pool probes retained in other shards")
    print("[Phase6R69] No re-emission, no re-sharding, no HRESULT/guest behavioral changes")
    print("[Phase6R69] Marker: "+TAG)
    return 0
if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R69] PREBUILD FAIL: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
