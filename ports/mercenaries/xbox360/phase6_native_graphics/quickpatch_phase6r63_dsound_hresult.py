#!/usr/bin/env python3
"""Phase6R63: instrument F03A/F0C6 error flow in only 2 cached R62 TrueTU shards.

R62 Xbox evidence:
 - F495->F0C6 returned EAX=8007000E.
 - FF54 primary allocation did return zero once, but ExAllocatePoolWithTag
   fallback succeeded (EAX=01B5CAA0).
 - No R62 F03A_BEFORE_FF54 / AFTER_FF54 marker appeared, despite the
   R62 FF54 probes operating. Therefore that particular F03A callsite
   was not observed; trace F03A's nonalloc branches and F0C6's result.
 - 27,027,014 ticks, unchanged EC83F0E4 fault. No new graphics pixels.

Requires R62 quick-shard patch manifest and validates both R62 modified
hashes and original R59 backups. R63 modifies only translated_022.cpp and
translated_055.cpp, backing up their previous exact bytes. All other shards
remain untouched. Re-running verifies R63 hashes. No success coercion,
guest memory reads, stack changes, or hard-fence bypass.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

TAG="P6DQ R63 DSOUND HRESULT:"
REV="R63-FAST-BRANCH-PROVENANCE-20261029"
TARGETS={0x0029F03A:"translated_022.cpp",0x0029F0C6:"translated_055.cpp"}

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def probe(name:str)->str:
    return (
        "\n    {\n"
        "        static unsigned int r63_count = 0u;\n"
        "        ++r63_count;\n"
        "        if (r63_count <= 6u)\n"
        "        {\n"
        "            char r63_line[248];\n"
        "            sprintf(r63_line,\n"
        f'                "P6DQ R63 DSOUND HRESULT: {name} n=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",\n'
        "                (unsigned int)r63_count, (unsigned int)eax, (unsigned int)ecx,\n"
        "                (unsigned int)edx, (unsigned int)ebx, (unsigned int)esi,\n"
        "                (unsigned int)edi, (unsigned int)esp);\n"
        "            trace(r63_line);\n"
        "        }\n"
        "    }\n"
    )

def after(s:str,tag:str)->tuple[str,str]:
    return s,s+probe(tag)

def before(s:str,tag:str)->tuple[str,str]:
    return s,probe(tag)+s

def patch_body(source:str,va:int,edits:list[tuple[str,str]])->str:
    pat=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_"+f"{va:08X}"+r"\(void\)\s*\{")
    ms=list(pat.finditer(source))
    if len(ms)!=1:
        raise RuntimeError(f"sub_{va:08X}: expected one translated body, found {len(ms)}")
    m=ms[0]
    brace=source.find("{",m.start(),m.end())
    end=closing_brace(source,brace)
    original=source[m.start():end]
    if TAG in original:
        raise RuntimeError(f"sub_{va:08X}: existing R63 marker; incompatible state")
    body=original
    for needle,replacement in edits:
        count=body.count(needle)
        if count!=1:
            raise RuntimeError(f"sub_{va:08X}: anchor count {count} instead of 1: {needle!r}")
        body=body.replace(needle,replacement,1)
    if body.count(TAG)!=len(edits):
        raise RuntimeError(f"sub_{va:08X}: missing R63 probes")
    return source[:m.start()]+body+source[end:]

def patch(source:str,va:int)->str:
    if va==0x0029F03A:
        return patch_body(source,va,[
            after("    esi = ecx;","F03A_ENTRY_THIS"),
            after("loc_0029F068: ;","F03A_AT_F068"),
            after("loc_0029F075: ;","F03A_AT_F075"),
            after("loc_0029F087: ;","F03A_AT_F087"),
            after("loc_0029F0AE: ;","F03A_AT_F0AE"),
            after("    eax = phase6ch_apu_read32(ebp + -4);","F03A_LOCAL_STATUS"),
        ])
    if va==0x0029F0C6:
        return patch_body(source,va,[
            after("    ebx = phase6ch_apu_read32(ebp + 0xC);","F0C6_INITIAL_OPTIONS"),
            after("    PUSH32(esp, 0); sub_002A58C0(); /* call 0x002A58C0 */","F0C6_AFTER_A58C0"),
            after("    PUSH32(esp, 0); sub_0029F03A(); /* call 0x0029F03A */","F0C6_AFTER_F03A"),
            after("    PUSH32(esp, 0); sub_002A5770(); /* call 0x002A5770 */","F0C6_AFTER_A5770"),
            after("    eax = edi;","F0C6_FINAL_STATUS"),
        ])
    raise RuntimeError("unexpected function")

def validate_record(record:dict,shards:Path,backups:Path,*,label:str)->None:
    if not isinstance(record.get("patched"),list) or not record["patched"]:
        raise RuntimeError(f"{label}: malformed patch record")
    for item in record["patched"]:
        name=item["name"]
        actual=shards/name
        saved=backups/name
        if not actual.is_file() or digest(actual.read_bytes())!=item["modified_sha256"]:
            raise RuntimeError(f"{label}: modified shard hash mismatch: {name}")
        if not saved.is_file() or digest(saved.read_bytes())!=item["original_sha256"]:
            raise RuntimeError(f"{label}: original backup hash mismatch: {name}")

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--tu-dir",required=True,type=Path)
    ap.add_argument("--r62-dir",required=True,type=Path)
    ap.add_argument("--out-dir",required=True,type=Path)
    args=ap.parse_args()
    shards=args.tu_dir/"translated_shards"
    r62=args.r62_dir
    out=args.out_dir
    source_manifest=args.tu_dir/"phase6tu-manifest.json"
    if not source_manifest.is_file():
        raise RuntimeError("R59 TrueTU manifest missing")
    manifest=json.loads(source_manifest.read_text(encoding="utf-8"))
    records={row["name"]:row for row in manifest.get("shards",[])}
    if manifest.get("phase")!="6TU" or manifest.get("shard_count")!=64 or len(records)!=64:
        raise RuntimeError("R59 64-shard manifest does not validate")
    counts=sum(row["functions"] for row in records.values())
    if counts!=manifest.get("translated_functions") or counts<13000:
        raise RuntimeError(f"R59 TrueTU translated count inconsistent: {counts}")
    allshards=list(shards.glob("translated_*.cpp"))
    if len(allshards)!=64:
        raise RuntimeError(f"expected 64 compiled units, got {len(allshards)}")
    originalR62Record=r62/"quick-shard-overlay.json"
    if not originalR62Record.is_file():
        raise RuntimeError("R62 record missing; prepare and build R62 before R63")
    r62record=json.loads(originalR62Record.read_text(encoding="utf-8"))
    if r62record.get("revision")!="R62-QUICK-TU-AUDIO-20261029":
        raise RuntimeError("R62 record revision mismatch")
    originalBackup=r62/"original_r59_shards"
    namesR62={item["name"] for item in r62record["patched"]}
    if namesR62!={"translated_022.cpp","translated_042.cpp"}:
        raise RuntimeError(f"unexpected R62 shard owners: {namesR62}")
    for item in r62record["patched"]:
        baseline=records[item["name"]]["sha256"]
        if baseline!=item["original_sha256"]:
            raise RuntimeError(f"R62 backup mismatch R59 manifest: {item['name']}")
    recordPath=out/"quick-shard-overlay.json"
    backups=out/"original_r62_shards"
    if recordPath.exists():
        own=json.loads(recordPath.read_text(encoding="utf-8"))
        if own.get("revision")!=REV:
            raise RuntimeError("Incompatible R63 record revision")
        validate_record(own,shards,backups,label="R63 reuse")
        for item in r62record["patched"]:
            # R63 modifies only shard 022; R62's shard 042 remains byte-stable.
            if item["name"]=="translated_042.cpp" and digest((shards/item["name"]).read_bytes())!=item["modified_sha256"]:
                raise RuntimeError("R62 original shard 042 drift after R63")
        print("[Phase6R63] REUSE PASS: exact hashes and backups verified",flush=True)
        print("[Phase6R63] patched_shards=2 untouched_shards=62 (no regenerate)",flush=True)
        return 0

    validate_record(r62record,shards,originalBackup,label="R62 baseline")
    expected={"translated_022.cpp":next(i["modified_sha256"] for i in r62record["patched"] if i["name"]=="translated_022.cpp"),
              "translated_055.cpp":records["translated_055.cpp"]["sha256"]}
    staged={}
    for va,name in TARGETS.items():
        target=shards/name
        raw=target.read_bytes()
        if digest(raw)!=expected[name]:
            raise RuntimeError(f"R63 target drift: {name} expected={expected[name]} got={digest(raw)}")
        text=raw.decode("utf-8")
        compiled=patch(text,va)
        if TAG not in compiled:
            raise RuntimeError(f"R63 target {name} missing probes")
        staged[name]=(raw,compiled.encode("utf-8"))
    # Stage and validate all source edits before writing ANY shards.
    backup=out/"original_r62_shards"
    backup.mkdir(parents=True,exist_ok=True)
    for name,(raw,_) in staged.items():
        path=backup/name
        if path.exists():
            if path.read_bytes()!=raw:
                raise RuntimeError(f"R63 preexisting backup mismatch: {path}")
        else:
            path.write_bytes(raw)
    items=[]
    for name,(raw,modified) in staged.items():
        (shards/name).write_bytes(modified)
        items.append({"name":name,"original_sha256":digest(raw),"modified_sha256":digest(modified)})
    out.mkdir(parents=True,exist_ok=True)
    recordPath.write_text(json.dumps({"revision":REV,"patched":items,
        "translated_functions":counts,"r62_revision":r62record["revision"]},indent=2)+"\n",encoding="utf-8")
    print("[Phase6R63] TWO-SHARD BRANCH PROVENANCE: PATCH PASS",flush=True)
    print("[Phase6R63] touched: translated_022.cpp (F03A), translated_055.cpp (F0C6)")
    print("[Phase6R63] unchanged: translated_042.cpp (R62 FF54) + other 61 shards")
    print("[Phase6R63] No reparse/reshard, no allocator behavioral change, no HRESULT coercion")
    return 0

if __name__=="__main__":
    import sys
    try:
        raise SystemExit(main())
    except Exception as err:
        print(f"[Phase6R63] PREBUILD FAILURE {type(err).__name__}: {err}",file=sys.stderr,flush=True)
        raise
