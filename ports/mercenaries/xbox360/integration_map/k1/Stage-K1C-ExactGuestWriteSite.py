#!/usr/bin/env python3
"""K1C exact guest-write site candidate: overlay only K1B's main.cpp.

K1B hardware proved a single GUEST_WRITE32 at 00041D70 changed the
retail 00041D59 data word to the newly allocated guest heap+0x28 pointer
01B672D8. Its trace-ring 'caller=0023A3CE' is a broad context, not an
instruction address. K1C observes the existing main.cpp guest-VA tracker
s_phase6cpCurrentVa at that exact write, without modifying memory writes.
64 generated TrueTU .cpp and runtime headers are reused byte-for-byte.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

K1B="P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030"
K1C="P6K1C-EXACT-WRITE-SITE-VA-20261030"
BOOT="PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START"
TRACKER="static DWORD s_phase6cpCurrentVa = 0u;"
HELPER="k1c_read_guest_va"
HELPER_DECL="static DWORD k1c_read_guest_va(void);"
TRACKER_LINE=re.compile(r"(?m)^[ \t]*static[ \t]+DWORD[ \t]+s_phase6cpCurrentVa[ \t]*=[ \t]*0u;[ \t]*(?://[^\r\n]*)?\r?$")
WRITER_FIRST=re.compile(r"(?m)^[ \t]*void[ \t]+recomp_guest_write8[ \t]*\(")
OLD_LABEL=("K1B CENTRAL WRITE: width=%u hit=%u address=%08X value_lo=%08X "
           "value_hi=%08X before0=%08X before4=%08X caller=%08X budget=%u esp=%08X")
NEW_LABEL=("K1C WRITE SITE: width=%u hit=%u address=%08X value_lo=%08X "
           "value_hi=%08X before0=%08X before4=%08X trace_caller=%08X guest_va=%08X budget=%u esp=%08X")
OLD_ARG="                (unsigned)k1b_last_trace_va,"
NEW_ARG=("                (unsigned)k1b_last_trace_va,\n"
         "                (unsigned)k1c_read_guest_va(),")
BOOT_OLD=BOOT+" | "+K1B
BOOT_NEW=BOOT+" | "+K1C+" | "+K1B


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def patch(source:str)->str:
    if K1C in source:
        raise ValueError("K1C already installed in source")
    if source.count(K1B)!=6 or source.count(BOOT_OLD)!=1:
        raise ValueError("K1B identity drift: expected five central writers and one runtime boot tag")
    if source.count(TRACKER)!=1 or len(list(TRACKER_LINE.finditer(source)))!=1:
        raise ValueError("existing file-scope guest VA tracker missing/duplicated")
    if HELPER in source:
        raise ValueError("guest VA helper already exists in baseline")
    if source.count(OLD_LABEL)!=5 or source.count(OLD_ARG)!=5:
        raise ValueError("K1B five exact writer messages/arguments not found")
    if source.count("k1b_last_trace_va = s_trace[k1b_trace_index];")!=5:
        raise ValueError("K1B baseline guest writer trace-ring witness drift")
    crlf=source.count("\r\n")
    if crlf and crlf!=source.count("\n"):
        raise ValueError("mixed generated C++ line endings")
    eol="\r\n" if crlf else "\n"
    # The actual frozen K1B main defines the tracker *after* the generic
    # writer functions. A direct read in those earlier functions fails
    # MSVC C2065. Keep the tracker at its original file-scope location:
    # a small late-defined helper can read it, while an early forward
    # declaration lets all five earlier writers call the helper safely.
    writer_matches=list(WRITER_FIRST.finditer(source))
    if not writer_matches:
        raise ValueError("missing early central write8 declaration/body")
    helper_body=(
        eol+"static DWORD "+HELPER+"(void)"+eol
        +"{" + eol+"    return s_phase6cpCurrentVa;"+eol+"}"+eol
    )
    new_arg=NEW_ARG.replace("\n",eol)
    output=source.replace(OLD_LABEL,NEW_LABEL).replace(OLD_ARG,new_arg)
    output=output.replace(BOOT_OLD,BOOT_NEW,1)
    # Insert after tracker, without moving or redefining the existing global.
    output=output.replace(TRACKER,TRACKER+helper_body,1)
    # Insert prototype before first central writer (prototype or body).
    # Both insertions preserve the LF / Windows CRLF line-ending policy.
    match=WRITER_FIRST.search(output)
    if match is None:
        raise ValueError("central writer disappeared while patching K1C")
    output=output[:match.start()]+HELPER_DECL+eol+output[match.start():]
    if output.count(NEW_LABEL)!=5 or output.count(new_arg)!=5:
        raise ValueError("K1C message/argument count drift")
    if output.count(HELPER_DECL)!=1 or output.count("static DWORD "+HELPER+"(void)"+eol+"{")!=1:
        raise ValueError("K1C helper declaration/definition count drift")
    if output.index(HELPER_DECL)>output.index("void recomp_guest_write8("):
        raise ValueError("K1C helper prototype not before first writer")
    if output.index("return s_phase6cpCurrentVa;")<output.index(TRACKER):
        raise ValueError("K1C helper definition incorrectly precedes tracker")
    if output.count(BOOT_NEW)!=1 or output.count(K1C)!=1:
        # Single K1C boot marker; its formatted trace label is independent.
        raise ValueError("K1C runtime identity drift")
    # The real K1B main has legitimate early forward declarations of
    # recomp_guest_write8/32. Do not confuse them with function bodies.
    # K1B was already staged with exactly five verified writer bodies.
    if output.count("K1C WRITE SITE:")!=5:
        raise ValueError("expected five unchanged central writer probe bodies")
    if output.count(TRACKER)!=1:
        raise ValueError("original tracker moved, duplicated or lost")
    return output


def stage(baseline:Path,shard_dir:Path,out:Path)->dict:
    baseline=baseline.resolve()
    shard_dir=shard_dir.resolve()
    out=out.resolve()
    if out==baseline or out.parent==baseline.parent or out.parent==shard_dir:
        raise ValueError("stage must use a separate new main directory")
    original=baseline.read_bytes()
    try: text=original.decode("utf-8")
    except UnicodeDecodeError as exc:
        raise ValueError("K1B generated main not UTF-8") from exc
    changed=patch(text).encode("utf-8")
    shards=sorted(shard_dir.glob("translated_*.cpp"))
    headers=sorted(shard_dir.glob("*.h"))
    if len(shards)!=64 or "translated_runtime.h" not in {x.name for x in headers}:
        raise ValueError("missing frozen 64 TrueTU source set or runtime header")
    hashes={f.name:sha(f.read_bytes()) for f in [*shards,*headers]}
    if out.exists():
        if out.read_bytes()!=changed:
            raise ValueError("K1C staged main has drifted; never overwrite")
        print("[K1C-SITE] REUSE PASS: new main is byte-for-byte identical")
    else:
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(changed)
    if baseline.read_bytes()!=original or any(
        sha(f.read_bytes())!=hashes[f.name] for f in [*shards,*headers]
    ):
        raise RuntimeError("frozen K1B/TrueTU source mutated during K1C stage")
    manifest={
        "status":"STAGED_ONLY_NO_XDK_BUILD",
        "boot_marker":K1C,
        "original_main_sha256":sha(original),
        "staged_main_sha256":sha(changed),
        "source_main":str(baseline),"staged_main":str(out),
        "source_shards":str(shard_dir),
        "translated_cpp_count":len(shards),
        "generated_header_count":len(headers),
        "extra_guest_memory_writes":0,
        "guest_memory_hard_fence":"UNCHANGED",
        "guest_write_widths":[1,2,4,8,16],
        "watch_range":"00041D70..00041D77",
        "writer_telemetry":"K1C WRITE SITE",
        "guest_va_origin":"existing s_phase6cpCurrentVa via late-defined read helper (candidate last translated VA)",
        "unchanged_header_sha256":{f.name:hashes[f.name] for f in headers},
    }
    (out.parent/"k1c-write-site-manifest.json").write_text(
        json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--main",required=True,type=Path)
    ap.add_argument("--shards",required=True,type=Path)
    ap.add_argument("--out",required=True,type=Path)
    args=ap.parse_args()
    doc=stage(args.main,args.shards,args.out)
    print("[K1C-SITE] PASS: five guest writer probes now include existing guest VA tracker")
    print("[K1C-SITE] PASS: unique hardware boot marker, no write or hard-fence mutation")
    print("[K1C-SITE] PASS: 64 TrueTU sources and runtime headers unchanged")
    print("[K1C-SITE] Manifest="+str(args.out.parent/"k1c-write-site-manifest.json"))


if __name__=="__main__":main()
