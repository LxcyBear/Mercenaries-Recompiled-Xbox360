#!/usr/bin/env python3
"""R62: fast incremental DSOUND allocator probe, patch only existing R59 TrueTU shards.

R61 source proves: F0C6->F03A->FF54; F03A maps null FF54 result to
0x8007000E. R59 hardware proved F495 returned 0x8007000E, not whether
F03A/FF54 actually ran or what caused allocation failure.

The R59 TrueTU output is hashed against its original 6TU manifest BEFORE
any mutation. Only the already-compiled shards owning 0029F03A and
0029FF54 are modified. Original shard bytes are backed up, and a record
makes re-runs idempotent. R59 Rocket, R59 mono and published XEX are
NEVER changed. No guest registers, guest stack, return values, memory
allocators or hard fences are altered, and no extra guest memory reads
are introduced. Trace calls are bounded at six per site.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

MARKER="P6DQ R62 DSOUND ALLOC:"
VERSION="R62-QUICK-TU-AUDIO-20261029"
TARGETS=(0x0029F03A,0x0029FF54)

def h(payload:bytes)->str:
    return hashlib.sha256(payload).hexdigest()

def capture(tag:str)->str:
    return (
        "\n    {\n"
        "        static unsigned int r62_hits=0u;\n"
        "        ++r62_hits;\n"
        "        if (r62_hits <= 6u)\n"
        "        {\n"
        "            char r62_line[256];\n"
        "            sprintf(r62_line,\n"
        f'                "P6DQ R62 DSOUND ALLOC: {tag} n=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",\n'
        "                (unsigned int)r62_hits,\n"
        "                (unsigned int)eax, (unsigned int)ecx,\n"
        "                (unsigned int)edx, (unsigned int)ebx,\n"
        "                (unsigned int)esi, (unsigned int)edi,\n"
        "                (unsigned int)esp);\n"
        "            trace(r62_line);\n"
        "        }\n"
        "    }\n"
    )

def patch_function(text:str,va:int, replacements:list[tuple[str,str]])->str:
    regex=re.compile(r"(?m)^\s*(?:static\s+)?void\s+sub_"+f"{va:08X}"+r"\(void\)\s*\{")
    matches=list(regex.finditer(text))
    if len(matches)!=1:
        raise RuntimeError(f"target sub_{va:08X}: expected one body, saw {len(matches)}")
    start=matches[0].start()
    brace=text.find("{",matches[0].start(),matches[0].end())
    end=closing_brace(text,brace)
    scoped=text[start:end]
    if MARKER in scoped:
        raise RuntimeError(f"sub_{va:08X} already patched")
    for original,replacement in replacements:
        if scoped.count(original)!=1:
            raise RuntimeError(f"sub_{va:08X} expected one anchor but saw {scoped.count(original)}: {original[:100]}")
        scoped=scoped.replace(original,replacement,1)
    return text[:start]+scoped+text[end:]

def add_after(needle:str,label:str)->tuple[str,str]:
    return needle,needle+capture(label)

def patch(text:str,va:int)->str:
    if va==0x0029F03A:
        call="    PUSH32(esp, 0); sub_0029FF54(); /* call 0x0029FF54 */"
        return patch_function(text,va,[
            (call, capture("F03A_BEFORE_FF54")+call+capture("F03A_AFTER_FF54")),
        ])
    if va==0x0029FF54:
        begin="    ecx = phase6ch_apu_read32(0x2BB010);"
        return patch_function(text,va,[
            add_after(begin,"FF54_GLOBAL_ALLOCATOR"),
            add_after("    PUSH32(esp, 0); sub_002A2D21(); /* call 0x002A2D21 */","FF54_PRIMARY_ALLOC_RETURN"),
            add_after("    PUSH32(esp, 0); sub_0029FE8E(); /* call 0x0029FE8E */","FF54_FALLBACK_ALLOC_RETURN"),
            (
                "    eax = edx;\n    POP32(esp, esi);\n    esp += 16; return; /* ret 12 */",
                "    eax = edx;\n"
                + capture("FF54_FINAL_RETURN")
                + "    POP32(esp, esi);\n    esp += 16; return; /* ret 12 */",
            ),
        ])
    raise RuntimeError(f"unexpected VA: {va:08X}")

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--tu-dir",type=Path,required=True)
    p.add_argument("--out-dir",type=Path,required=True)
    args=p.parse_args()
    tu=args.tu_dir
    shards=tu/"translated_shards"
    original_manifest=tu/"phase6tu-manifest.json"
    output=args.out_dir
    records=output/"quick-shard-overlay.json"
    backup=output/"original_r59_shards"
    if not original_manifest.is_file():
        raise SystemExit("[Phase6R62] R59 TrueTU manifest missing")
    m=json.loads(original_manifest.read_text(encoding="utf-8"))
    print("[Phase6R62] baseline_manifest_phase="
          + str(m.get("phase")) + " shard_count=" + str(m.get("shard_count"))
          + " translated_functions=" + str(m.get("translated_functions")),flush=True)
    # The R59 source-level audit saw 13,517 function bodies. The TrueTU
    # emitter intentionally produces a smaller *translated* set (13,510 on
    # the user's validated R59 build), so never equate those two counts.
    # Validate the manifest against its own 64 per-shard function counts.
    translated=m.get("translated_functions")
    rows=m.get("shards")
    if (m.get("phase")!="6TU" or m.get("shard_count")!=64
            or not isinstance(translated,int) or not 13000 <= translated <= 14000
            or not isinstance(rows,list) or len(rows)!=64
            or any(not isinstance(row.get("functions"),int) for row in rows)
            or sum(row["functions"] for row in rows)!=translated):
        raise SystemExit("[Phase6R62] R59 64-shard baseline manifest inconsistent"
                         " (check phase, count, and sum of shard functions above)")
    expected={row["name"]:row["sha256"] for row in m.get("shards",[])}
    files=sorted(shards.glob("translated_*.cpp"))
    if len(files)!=64 or len(expected)!=64:
        raise SystemExit(f"[Phase6R62] Expected exactly 64 shards: files={len(files)} manifest={len(expected)}")
    main_cpp=tu/"main.cpp"
    if not main_cpp.is_file() or "P6DQ-R51-MM173-FRAME-20261029-A" not in main_cpp.read_text(encoding="utf-8",errors="replace"):
        raise SystemExit("[Phase6R62] TrueTU main build-tag mismatch")
    if not any("P6DQ R59 FC4A ABI RESTORE:" in s.read_text(encoding="utf-8",errors="replace") for s in files):
        raise SystemExit("[Phase6R62] R59 ABI fix missing; refuse patch")
    owners={}
    for path in files:
        data=path.read_text(encoding="utf-8",errors="replace")
        for addr in TARGETS:
            signature=re.compile(r"\bvoid\s+sub_"+f"{addr:08X}"+r"\(void\)\s*\{")
            if signature.search(data):
                if addr in owners:
                    raise SystemExit(f"[Phase6R62] Multiple function owners sub_{addr:08X}")
                owners[addr]=path
    if set(owners)!=set(TARGETS):
        raise SystemExit("[Phase6R62] Not all target translated functions are generated")
    unique=sorted(set(owners.values()),key=lambda x:x.name)
    print("[Phase6R62] QUICK-SHARD DIRECTSOUND NULL-ALLOC PROBE",flush=True)
    print(f"[Phase6R62] source=R59_TRUE_TU shard_total=64 target_shards={len(unique)}")
    for va in TARGETS:
        print(f"[Phase6R62] probe function sub_{va:08X} owner={owners[va].name}")
    print("[Phase6R62] NO Rocket/monolithic regeneration. NO 13,517-function sharding pass.")

    if records.exists():
        record=json.loads(records.read_text(encoding="utf-8"))
        if record.get("revision")!=VERSION:
            raise SystemExit("[Phase6R62] incompatible patch record present")
        for item in record.get("patched",[]):
            path=shards/item["name"]
            saved=backup/item["name"]
            if not path.is_file() or h(path.read_bytes())!=item["modified_sha256"]:
                raise SystemExit(f"[Phase6R62] Existing patched shard drift: {path}")
            if not saved.is_file() or h(saved.read_bytes())!=item["original_sha256"]:
                raise SystemExit(f"[Phase6R62] Existing R59 backup missing/corrupt: {saved}")
            if expected.get(item["name"])!=item["original_sha256"]:
                raise SystemExit(f"[Phase6R62] R59 manifest mismatch for {path}")
        print("[Phase6R62] REUSE: patch is already applied; verified hashes/backup")
        print("[Phase6R62] patched_shards="+str(len(record["patched"]))+" untouched_shards="+str(64-len(record["patched"])))
        return 0

    staged={}
    for path in unique:
        raw=path.read_bytes()
        if h(raw)!=expected.get(path.name):
            raise SystemExit(
                f"[Phase6R62] R59 source drift in {path.name}: "
                f"manifest_sha={expected.get(path.name)} current_sha={h(raw)}. "
                "Stop before building; obtain the full diagnostic instead of overwriting the shard."
            )
        text=raw.decode("utf-8")
        for va in TARGETS:
            if owners[va]==path:
                text=patch(text,va)
        if text.count(MARKER)!=(2 if 0x0029F03A in [x for x in TARGETS if owners[x]==path] else 0)+(4 if 0x0029FF54 in [x for x in TARGETS if owners[x]==path] else 0):
            raise SystemExit(f"[Phase6R62] trace count mismatch: {path}")
        staged[path]=(raw,text.encode("utf-8"))
    backup.mkdir(parents=True,exist_ok=True)
    for path,(raw,_) in staged.items():
        saved=backup/path.name
        if saved.exists() and saved.read_bytes()!=raw:
            raise SystemExit(f"[Phase6R62] backup mismatch: {saved}")
        if not saved.exists():
            saved.write_bytes(raw)
    items=[]
    for path,(raw,modified) in staged.items():
        path.write_bytes(modified)
        items.append({"name":path.name,"original_sha256":h(raw),"modified_sha256":h(modified)})
        print(f"[Phase6R62] PATCHED SHARD: {path.name}")
    record={"revision":VERSION,"patched":items,"total_functions":translated,"source":"R59 TrueTU cached","xex":"NOT YET BUILT"}
    output.mkdir(parents=True,exist_ok=True)
    records.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    print(f"[Phase6R62] patched_shards={len(items)} untouched_shards={64-len(items)}")
    print("[Phase6R62] R59 originals backed up; separate R62 patch manifest saved")
    print("[Phase6R62] PROBE ONLY: read register snapshots, never synthesize success or bypass memory fences")
    return 0

if __name__=="__main__":
    import sys
    try:
        raise SystemExit(main())
    except Exception as exc:
        print(f"[Phase6R62] PYTHON ERROR: {type(exc).__name__}: {exc}",file=sys.stderr,flush=True)
        raise
