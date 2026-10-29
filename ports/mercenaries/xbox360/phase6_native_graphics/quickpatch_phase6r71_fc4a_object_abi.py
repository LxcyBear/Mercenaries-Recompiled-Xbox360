#!/usr/bin/env python3
"""Phase 6R71: repair FC4A -> A19FC DirectSound object-pointer / x86 ABI.

Hardware + R60/R70 source:
- A0E9D returns valid guest object EAX=01B5C554.
- FC4A sets ECX=EAX then stores ECX into outer [ESI+0x0C].
- A19FC then runs with ESI=00000000 and seeds pool[0x78].
- The genuine pool is at 01B5C5B4; pool[01B5C5CC]=0, causing E_OUTOFMEMORY.
- R59 ABI telemetry at return: EBX,ESI,EDI overwritten by the callee.

R71 restores the intended ECX from the just-written outer field at the
call boundary, *only if that field is nonzero*, and explicitly preserves
guest x86 callee-saved EBX/ESI/EDI across A19FC. Does not touch EAX,
guest stack, allocation status, resources, VP or MMIO. Logs guest ESP
both before and after so future stack ABI faults remain visible.

R69 must have already applied the safe final-status upgrade.
No full recompilation/emitter/sharder; one exact TrueTU owner only.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

TAG="P6DQ R71 DSOUND OBJECT ABI:"
REV="R71-FC4A-A19FC-GUEST-OBJECT-ABI-20261029"
TARGET=0x0029FC4A
RX=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})\(void\)\s*\{")
CHAIN=(
 ("r62","R62-QUICK-TU-AUDIO-20261029","original_r59_shards",{"translated_022.cpp","translated_042.cpp"}),
 ("r63","R63-FAST-BRANCH-PROVENANCE-20261029","original_r62_shards",{"translated_022.cpp","translated_055.cpp"}),
 ("r66","R66-CACHED-TU-POOL-PROVENANCE-20261029","original_r63_shards",{"translated_032.cpp","translated_034.cpp","translated_036.cpp","translated_056.cpp"}),
 ("r69","R69-CACHED-TU-SEED-LINEAGE-SAFE-20261029","original_r66_shards",{"translated_008.cpp","translated_042.cpp"}),
)

def sha(raw:bytes)->str:
    return hashlib.sha256(raw).hexdigest()

def record(folder:Path,revision:str):
    path=folder/"quick-shard-overlay.json"
    if not path.is_file():
        raise RuntimeError(f"Missing overlay {path}")
    obj=json.loads(path.read_text(encoding="utf-8"))
    rows=obj.get("patched")
    if (obj.get("revision")!=revision or not isinstance(rows,list) or not rows
        or len({r["name"] for r in rows})!=len(rows)):
        raise RuntimeError(f"Unexpected or corrupt overlay {path}")
    return rows

def fix_fc4a(text:str):
    matches=[m for m in RX.finditer(text) if int(m.group(1),16)==TARGET]
    if len(matches)!=1:
        raise RuntimeError(f"Target FC4A definition count {len(matches)}")
    m=matches[0]
    start=text.find("{",m.start(),m.end())
    end=closing_brace(text,start)
    body=text[m.start():end]
    if TAG in body:
        raise RuntimeError("R71 tag already found, expected exact R69 state")
    prior='''        const uint32_t r59_saved_edi = edi;
    PUSH32(esp, 0); sub_002A19FC(); /* call 0x002A19FC */
        const uint32_t r59_after_ebx = ebx;'''
    repl='''        const uint32_t r59_saved_edi = edi;
        /* R71: FC4A just saved A0E9D's real object in [ESI+0x0C].
           R69 proves A19FC otherwise starts with ECX=0 and seeds
           low memory +0x78 instead of real object +0x78. */
        const uint32_t r71_expected_this = phase6ch_apu_read32(esi + 0xCu);
        const uint32_t r71_original_ecx = ecx;
        const uint32_t r71_before_esp = esp;
        if (r71_expected_this != 0u)
            ecx = r71_expected_this;
        {
            static unsigned int r71_count = 0u;
            ++r71_count;
            if (r71_count <= 8u)
            {
                char r71_line[320];
                sprintf(r71_line,
                    "P6DQ R71 DSOUND OBJECT ABI: PRE n=%u outer=%08X original_ecx=%08X object=%08X new_ecx=%08X esp=%08X",
                    (unsigned int)r71_count, (unsigned int)esi, (unsigned int)r71_original_ecx,
                    (unsigned int)r71_expected_this, (unsigned int)ecx,
                    (unsigned int)r71_before_esp);
                trace(r71_line);
            }
        }
    PUSH32(esp, 0); sub_002A19FC(); /* call 0x002A19FC */
        {
            const uint32_t r71_raw_ebx = ebx;
            const uint32_t r71_raw_esi = esi;
            const uint32_t r71_raw_edi = edi;
            const uint32_t r71_raw_esp = esp;
            /* Real x86 A19FC is required to preserve EBX/ESI/EDI. */
            ebx = r59_saved_ebx;
            esi = r59_saved_esi;
            edi = r59_saved_edi;
            static unsigned int r71_count = 0u;
            ++r71_count;
            if (r71_count <= 8u)
            {
                char r71_line[380];
                sprintf(r71_line,
                    "P6DQ R71 DSOUND OBJECT ABI: POST n=%u eax=%08X ebx=%08X->%08X esi=%08X->%08X edi=%08X->%08X esp=%08X->%08X",
                    (unsigned int)r71_count, (unsigned int)eax,
                    (unsigned int)r71_raw_ebx, (unsigned int)ebx,
                    (unsigned int)r71_raw_esi, (unsigned int)esi,
                    (unsigned int)r71_raw_edi, (unsigned int)edi,
                    (unsigned int)r71_before_esp, (unsigned int)r71_raw_esp);
                trace(r71_line);
            }
        }
        const uint32_t r59_after_ebx = ebx;'''
    if body.count(prior)!=1:
        raise RuntimeError(f"R71 exact FC4A ABI anchor not found uniquely: {body.count(prior)}")
    if body.count("ecx = eax;\n    goto loc_0029FCAA;")!=1:
        raise RuntimeError("FC4A A0E9D pointer -> ECX handoff unavailable")
    if body.count("phase6ch_apu_write32(esi + 0xC, ecx);")!=1:
        raise RuntimeError("FC4A stored object pointer source unavailable")
    patched=body.replace(prior,repl,1)
    if patched.count(TAG)!=2:
        raise RuntimeError("R71 trace count mismatch")
    return text[:m.start()]+patched+text[end:]

def main():
    p=argparse.ArgumentParser()
    for field in ("tu-dir","r62-dir","r63-dir","r66-dir","r69-dir","out-dir"):
        p.add_argument("--"+field,type=Path,required=True)
    x=p.parse_args()
    tu=x.tu_dir
    m=json.loads((tu/"phase6tu-manifest.json").read_text(encoding="utf8"))
    entries=m.get("shards",[])
    if (m.get("phase")!="6TU" or m.get("shard_count")!=64
        or m.get("translated_functions")!=13510 or len(entries)!=64
        or sum(e["functions"] for e in entries)!=13510
        or len({e["name"] for e in entries})!=64):
        raise RuntimeError("TrueTU R59 manifest unexpectedly changed")
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in (tu/"main.cpp").read_text(encoding="utf8",errors="replace"):
        raise RuntimeError("R59 build identity marker absent")
    srcdir=tu/"translated_shards"
    paths=sorted(srcdir.glob("translated_*.cpp"))
    expected={e["name"]:e["sha256"] for e in entries}
    if len(paths)!=64 or {f.name for f in paths}!={*expected}:
        raise RuntimeError("Expected exactly 64 original TrueTU shard filenames")
    for key,rev,backup_folder,names in CHAIN:
        folder=getattr(x,key+"_dir")
        rows=record(folder,rev)
        if {row["name"] for row in rows}!=names:
            raise RuntimeError(f"{key}: wrong modified shard ownership")
        for row in rows:
            name=row["name"]
            orig=folder/backup_folder/name
            if (expected[name]!=row["original_sha256"] or not orig.is_file()
                or sha(orig.read_bytes())!=row["original_sha256"]):
                raise RuntimeError(f"{key}: backup identity failed: {name}")
            expected[name]=row["modified_sha256"]
    out=x.out_dir
    opath=out/"quick-shard-overlay.json"
    backdir=out/"original_r69_shards"
    prior=None
    if opath.exists():
        prior=record(out,REV)
        if len(prior)!=1:
            raise RuntimeError("R71 reuse must have exactly one modified shard")
        r=prior[0]
        b=backdir/r["name"]
        if expected[r["name"]]!=r["original_sha256"] or not b.is_file() or sha(b.read_bytes())!=r["original_sha256"]:
            raise RuntimeError("R71 prior baseline backup mismatch")
        expected[r["name"]]=r["modified_sha256"]
    current={}
    for f in paths:
        raw=f.read_bytes()
        if sha(raw)!=expected[f.name]:
            raise RuntimeError(f"TrueTU corpus drift: {f.name} expected {expected[f.name]} actual {sha(raw)}")
        current[f.name]=raw
    if prior is not None:
        print("[Phase6R71] REUSE PASS: 64/64 hashes, R62/R63/R66/R69/R71 backups match")
        print("[Phase6R71] patched_shards=1 untouched_shards=63")
        return 0
    owners=[]
    for name,raw in current.items():
        if any(int(m.group(1),16)==TARGET for m in RX.finditer(raw.decode("utf-8"))):
            owners.append(name)
    if len(owners)!=1:
        raise RuntimeError(f"Expected single FC4A owner; found {owners}")
    owner=owners[0]
    before=current[owner]
    after=fix_fc4a(before.decode("utf-8")).encode("utf-8")
    backdir.mkdir(parents=True,exist_ok=True)
    b=backdir/owner
    if b.exists() and b.read_bytes()!=before:
        raise RuntimeError("R71 source backup collision")
    if not b.exists():
        b.write_bytes(before)
    (srcdir/owner).write_bytes(after)
    out.mkdir(parents=True,exist_ok=True)
    opath.write_text(json.dumps({"revision":REV,"patched":[
      {"name":owner,"original_sha256":sha(before),"modified_sha256":sha(after)}],
      "translated_functions":13510,"source_revision":"R69-CACHED-TU-SEED-LINEAGE-SAFE-20261029"
    },indent=2)+"\n",encoding="utf8")
    print("[Phase6R71] ONE-SHARD FC4A -> A19FC OBJECT POINTER AND REG ABI REPAIR PASS")
    print(f"[Phase6R71] owner={owner} function=0029FC4A")
    print("[Phase6R71] restored object ECX from [outer+0xC], only when nonzero")
    print("[Phase6R71] enforced guest EBX/ESI/EDI callee-save ABI; EAX/ESP/status untouched")
    print("[Phase6R71] patched_shards=1 untouched_shards=63")
    print("[Phase6R71] Existing R69/R66 markers remain; no regeneration or emulation bypass")
    print("[Phase6R71] Marker: "+TAG)
    return 0
if __name__=="__main__":
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R71] PREBUILD FAIL: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
