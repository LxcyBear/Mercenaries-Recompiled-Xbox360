#!/usr/bin/env python3
"""Phase6R76: exact XGSCNT direct-read catch at central guest-memory boundary.

Hardware R75 upload: same FE80200C guest READ32 fault, same 26,720,229 ticks,
XACT SUCCESS, zero display calls, and NO R75 site marker in entire log.
R74 proved sub_002DA923's isolated direct read, but not that the executed
fault was in that function. This patches the shared READ32 boundary instead.
Only 0xFE80200C is routed to the already-existing APU CORE shadow handler.
All other addresses, VP, NV2A and unknown MMIO remain on their existing path.
No fabricated sample advance or forced HRESULT.
A distinct startup watermark proves that the new XEX was deployed.
Only cached main.cpp changes; no shard emits/sharding or clean build.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import sys
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

REV="R76-GUEST-READ32-XGSCNT-ROUTE-20261029"
TAG="P6DQ R76 XGSCNT ROUTER:"
WATERMARK="P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029"
INTRO="PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START"
CHAIN=(
 ("r62","R62-QUICK-TU-AUDIO-20261029","original_r59_shards",{"translated_022.cpp","translated_042.cpp"}),
 ("r63","R63-FAST-BRANCH-PROVENANCE-20261029","original_r62_shards",{"translated_022.cpp","translated_055.cpp"}),
 ("r66","R66-CACHED-TU-POOL-PROVENANCE-20261029","original_r63_shards",{"translated_032.cpp","translated_034.cpp","translated_036.cpp","translated_056.cpp"}),
 ("r69","R69-CACHED-TU-SEED-LINEAGE-SAFE-20261029","original_r66_shards",{"translated_008.cpp","translated_042.cpp"}),
 ("r71","R71-FC4A-A19FC-GUEST-OBJECT-ABI-20261029","original_r69_shards",{"translated_053.cpp"}),
 ("r72","R72-A19FC-ESI-NESTED-CALLEE-20261029","original_r71_shards",{"translated_008.cpp"}),
 ("r75","R75-XGSCNT-EXACT-READ-20261029","original_r72_shards",None),
)

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def overlay(folder:Path,revision:str):
    p=folder/"quick-shard-overlay.json"
    if not p.is_file():
        raise RuntimeError(f"Overlay missing: {p}")
    doc=json.loads(p.read_text(encoding="utf-8"))
    rows=doc.get("patched")
    if doc.get("revision")!=revision or not isinstance(rows,list) or not rows:
        raise RuntimeError(f"Overlay revision or records wrong: {p}")
    if len({r["name"] for r in rows})!=len(rows):
        raise RuntimeError(f"Duplicate shards in {p}")
    return rows

def verify_64_shards(args,tu:Path):
    manifest=json.loads((tu/"phase6tu-manifest.json").read_text(encoding="utf-8"))
    rows=manifest.get("shards",[])
    if (manifest.get("phase")!="6TU" or manifest.get("shard_count")!=64 or
        manifest.get("translated_functions")!=13510 or len(rows)!=64 or
        sum(r["functions"] for r in rows)!=13510 or
        len({r["name"] for r in rows})!=64):
        raise RuntimeError("R59 TrueTU 64-shard manifest identity changed")
    directory=tu/"translated_shards"
    paths=sorted(directory.glob("translated_*.cpp"))
    expected={r["name"]:r["sha256"] for r in rows}
    if len(paths)!=64 or {p.name for p in paths}!=set(expected):
        raise RuntimeError("TrueTU exact 64-shard filenames not found")
    r75_name=None
    for key,rev,backup_sub,owners in CHAIN:
        folder=getattr(args,key+"_dir")
        records=overlay(folder,rev)
        if owners is not None and {r["name"] for r in records}!=owners:
            raise RuntimeError(f"{key}: modified-owner set does not match baseline")
        if key=="r75":
            if len(records)!=1:
                raise RuntimeError("Expected exactly one R75 site repair")
            r75_name=records[0]["name"]
        for item in records:
            name=item["name"]
            original=folder/backup_sub/name
            if (expected[name]!=item["original_sha256"] or
                not original.is_file() or
                sha(original.read_bytes())!=item["original_sha256"]):
                raise RuntimeError(f"{key}: source backup or SHA mismatch {name}")
            expected[name]=item["modified_sha256"]
    for p in paths:
        data=p.read_bytes()
        if sha(data)!=expected[p.name]:
            raise RuntimeError(f"Current TrueTU hash drift in {p.name}")
        if p.name==r75_name and b"P6DQ R75 APU XGSCNT ROUTED:" not in data:
            raise RuntimeError("R75 patched source marker missing")
    print("[Phase6R76] TrueTU CHECK PASS: all 64 shards and R62/R63/R66/R69/R71/R72/R75 overlays")
    print(f"[Phase6R76] R75 source owner={r75_name}; not modifying any shard")

def verify_apu_model(text:str):
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in text:
        raise RuntimeError("Cached main.cpp identity marker missing")
    if not re.search(r"#define\s+PHASE6CH_APU_XGSCNT\s+0x0000200Cu",text):
        raise RuntimeError("Core XGSCNT register definition not found")
    declaration="uint32_t phase6ch_apu_read32(uint32_t address)"
    if text.count(declaration)!=1:
        raise RuntimeError("Expected one APU read32 handler definition")
    pos=text.index(declaration)
    braces=text.index("{",pos)
    handler=text[pos:closing_brace(text,braces)]
    for token in (
        "phase6ch_apu_core_range(address, 4u, &offset)",
        "phase6ch_apu_shadow_read(address, 4u)",
        "return value;"):
        if token not in handler:
            raise RuntimeError(f"APU read32 router contract changed: {token}")
    print("[Phase6R76] Existing FE800000 APU core range + 0x200C shadow read validated")

def patch_main(text:str)->str:
    verify_apu_model(text)
    if TAG in text or WATERMARK in text:
        raise RuntimeError("Unexpected R76 marker already present in pre-patch source")
    if text.count(INTRO)!=1:
        raise RuntimeError("Startup banner not uniquely found; cannot watermark XEX safely")
    # Alter only the startup log string; preserves the recognized prefix.
    text=text.replace(INTRO,INTRO+" | "+WATERMARK,1)
    prototype="uint32_t recomp_guest_read32(uint32_t address);"
    if text.count(prototype)!=1:
        raise RuntimeError("Guest read32 prototype count unexpected")
    text=text.replace(
        prototype,
        prototype+"\nuint32_t phase6ch_apu_read32(uint32_t address); /* R76 exact XGSCNT forward declaration */",
        1)
    anchor="uint32_t recomp_guest_read32(uint32_t address)\n{\n    if (address == 0xCCCCCCD0u)"
    if text.count(anchor)!=1:
        raise RuntimeError(f"Guest read32 definition anchor count={text.count(anchor)}")
    replacement="""uint32_t recomp_guest_read32(uint32_t address)
{
    /* R76: retail DSOUND/XACT may use a direct x86 MMIO read instead of
       phase6ch_apu_read32. Handle ONLY the documented NV_PAPU_XGSCNT
       address here. Unknown MMIO keeps the hard fence unchanged. */
    if (address == 0xFE80200Cu)
    {
        const uint32_t value = phase6ch_apu_read32(address);
        static unsigned int r76_xgscnt_reads = 0u;
        ++r76_xgscnt_reads;
        if (r76_xgscnt_reads <= 8u)
        {
            char r76_line[224];
            sprintf(r76_line,
                "P6DQ R76 XGSCNT ROUTER: count=%u address=%08X value=%08X via=guest_read32",
                (unsigned int)r76_xgscnt_reads,
                (unsigned int)address, (unsigned int)value);
            trace(r76_line);
        }
        return value;
    }

    if (address == 0xCCCCCCD0u)"""
    text=text.replace(anchor,replacement,1)
    if (text.count(TAG)!=1 or text.count(WATERMARK)!=1 or
        text.count("if (address == 0xFE80200Cu)")!=1):
        raise RuntimeError("R76 expected exactly one central MMIO interception")
    return text

def main():
    parser=argparse.ArgumentParser()
    for key in ("tu-dir","r62-dir","r63-dir","r66-dir","r69-dir",
                "r71-dir","r72-dir","r75-dir","out-dir"):
        parser.add_argument("--"+key,type=Path,required=True)
    args=parser.parse_args()
    tu=args.tu_dir
    verify_64_shards(args,tu)
    mainpath=tu/"main.cpp"
    original=mainpath.read_bytes()
    out=args.out_dir
    rec=out/"main-overlay.json"
    backup=out/"original_r75_main.cpp"
    if rec.is_file():
        doc=json.loads(rec.read_text(encoding="utf-8"))
        if doc.get("revision")!=REV or not backup.is_file():
            raise RuntimeError("R76 source replay manifest/backup absent or mismatched")
        if sha(backup.read_bytes())!=doc.get("original_sha256"):
            raise RuntimeError("R76 original main backup SHA mismatch")
        if sha(original)!=doc.get("modified_sha256"):
            raise RuntimeError("R76 modified main hash differs from manifest")
        if WATERMARK not in original.decode("utf-8"):
            raise RuntimeError("R76 reuse watermark missing")
        print("[Phase6R76] REUSE PASS: main overlay and all 64 translated shards hash clean")
        print("[Phase6R76] patched_main=1 patched_shards=0 untouched_shards=64")
        return 0
    updated=patch_main(original.decode("utf-8")).encode("utf-8")
    out.mkdir(parents=True,exist_ok=True)
    if backup.exists() and sha(backup.read_bytes())!=sha(original):
        raise RuntimeError("R76 backup collision: wrong cached main revision")
    if not backup.exists():
        backup.write_bytes(original)
    mainpath.write_bytes(updated)
    rec.write_text(json.dumps({
        "revision":REV,
        "original_sha256":sha(original),
        "modified_sha256":sha(updated),
        "source":"build/phase6_native_graphics/r51_mm173_true_tu_xdk/main.cpp",
        "watermark":WATERMARK,
        "patched_shards":0,
    },indent=2)+"\n",encoding="utf-8")
    print("[Phase6R76] =============================================================")
    print("[Phase6R76] CENTRAL READ32 EXACT XGSCNT MMIO ROUTING PATCH PASS")
    print("[Phase6R76] =============================================================")
    print("[Phase6R76] central guest READ32 FE80200C -> existing APU core shadow")
    print("[Phase6R76] startup watermark: "+WATERMARK)
    print("[Phase6R76] all other MMIO/VP/NV2A reads retain existing hard fences")
    print("[Phase6R76] main.cpp only; patched_shards=0 untouched_shards=64")
    print("[Phase6R76] Marker: "+TAG)
    return 0

if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R76] PREBUILD FAIL: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
