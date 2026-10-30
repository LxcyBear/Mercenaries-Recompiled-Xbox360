#!/usr/bin/env python3
"""K1A DirectSound guest writer provenance: stage the true owner of APU helpers.

In the frozen 64-TrueTU build, helper definitions can live in the shared
translated_runtime.h rather than main.cpp. Match exactly one definition
per width in ONE owner, copy all TrueTUs and headers without changing source
bytes, and instrument that owner only.

No guest writes are removed, no MMIO values are fabricated, no hard fences
relaxed, and no local translated registers are referenced from runtime helpers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

K1A_MARK="P6K1A-BOOT-CLOCK128-304-305-20261029"
MARK="P6K1A-DSOUND-OBJECT-WRITER-WATCH-20261030"
WATCH_BEGIN=0x00041D70
WATCH_END=0x00041D78
SPEC=(
    ("phase6ch_apu_write8", "uint8_t", 1),
    ("phase6ch_apu_write16", "uint16_t", 2),
    ("phase6ch_apu_write32", "uint32_t", 4),
)

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def definition(name:str, typ:str)->re.Pattern[str]:
    # Both emitter's "static void" and TrueTU's "static inline void"
    # are supported. Require the exact value parameter widths and a brace;
    # prototypes and function-call expressions are NOT definition matches.
    return re.compile(
        r"(?m)^[ \t]*(?:(?:static|inline|__forceinline)[ \t]+){0,3}"
        r"void[ \t]+"+re.escape(name)
        +r"[ \t]*\([ \t]*uint32_t[ \t]+address[ \t]*,[ \t]*"
        +re.escape(typ)+r"[ \t]+value[ \t]*\)[ \t]*"
        +r"(?:\r?\n[ \t]*)?\{"
    )

def signatures(text:str)->list[int]:
    return [len(list(definition(n,t).finditer(text))) for n,t,_ in SPEC]

def patch(text:str, require_k1a:bool=True)->str:
    if require_k1a and text.count(K1A_MARK)!=1:
        raise ValueError("requires exactly one K1A clock boot marker")
    if MARK in text:
        raise ValueError("object writer watch is already present")
    lf=text.count("\n")
    crlf=text.count("\r\n")
    if crlf and crlf!=lf:
        raise ValueError("mixed source line endings; refusing to alter owner")
    newline="\r\n" if crlf else "\n"
    for name,typ,width in SPEC:
        found=list(definition(name,typ).finditer(text))
        if len(found)!=1:
            raise ValueError(f"{name}: exact body definition count={len(found)}, expected 1")
        pos=found[0].end()
        # Runtime helper scope has no access to per-function local EAX/EBX/etc.
        # Only guest memory, the generic caller context, and g_esp are read.
        watch=(
            newline+f"    /* {MARK} {name}: pre-write forensic witness. */"+newline
            +f"    if (address < 0x{WATCH_END:08X}u &&"+newline
            +f"        (uint64_t)address + {width}u > 0x{WATCH_BEGIN:08X}u)"+newline
            +"    {"+newline
            +"        static uint32_t k1a_ds_writes = 0u;"+newline
            +"        ++k1a_ds_writes;"+newline
            +"        if (k1a_ds_writes <= 32u)"+newline
            +"        {"+newline
            +"            char k1a_ds_line[256];"+newline
            +"            sprintf(k1a_ds_line,"+newline
            +'                "K1A DSOBJECT WRITE: width=%u n=%u guest=%08X value=%08X before0=%08X before4=%08X caller=%08X esp=%08X",'+newline
            +f"                {width}u, (unsigned)k1a_ds_writes,"+newline
            +"                (unsigned)address, (unsigned)value,"+newline
            +"                (unsigned)GUEST_READ32(0x00041D70u),"+newline
            +"                (unsigned)GUEST_READ32(0x00041D74u),"+newline
            +"                (unsigned)phase4c_current_caller(), (unsigned)g_esp);"+newline
            +"            trace(k1a_ds_line);"+newline
            +"        }"+newline
            +"    }"+newline
        )
        text=text[:pos]+watch+text[pos:]
    if text.count(MARK)!=3:
        raise ValueError("expected exactly one instrumentation per guest write width")
    return text

def stage(main:Path, shards:Path, out:Path)->dict:
    main=main.resolve()
    shards=shards.resolve()
    out=out.resolve()
    output_dir=out.parent
    output_shards=output_dir/"translated_shards"
    if main==out or shards==output_shards:
        raise ValueError("refuse in-place patch of K1A main or TrueTU inputs")
    if main in output_dir.parents or shards in output_dir.parents or output_dir==shards:
        raise ValueError("refuse nested source/output directory")
    files=sorted(shards.glob("translated_*.cpp"))
    if len(files)!=64:
        raise ValueError(f"require 64 TrueTU .cpp inputs; got {len(files)}")
    headers=sorted(shards.glob("*.h"))
    candidates=[h for h in headers if h.name=="translated_runtime.h"]
    if len(candidates)!=1:
        raise ValueError("missing exact original translated_runtime.h")
    header=candidates[0]
    main_bytes=main.read_bytes()
    main_text=main_bytes.decode("utf-8")
    if main_text.count(K1A_MARK)!=1:
        raise ValueError("existing main missing unique K1A clock boot watermark")
    header_bytes=header.read_bytes()
    header_text=header_bytes.decode("utf-8")
    main_counts=signatures(main_text)
    header_counts=signatures(header_text)
    if main_counts==[1,1,1] and header_counts==[0,0,0]:
        owner="main.cpp"
        patched_main=patch(main_text,require_k1a=True).encode("utf-8")
        patched_header=header_bytes
    elif main_counts==[0,0,0] and header_counts==[1,1,1]:
        owner="translated_runtime.h"
        patched_main=main_bytes
        patched_header=patch(header_text,require_k1a=False).encode("utf-8")
    else:
        def hints(data:str)->list[str]:
            return [line.strip()[:180] for line in data.splitlines()
                    if re.search(r"phase6ch_apu_write(?:8|16|32)\s*\(", line)][:12]
        raise ValueError(
            "APU writer ownership not unique. "
            f"main.cpp definitions={main_counts}, translated_runtime.h={header_counts}; "
            f"main.cpp signatures={hints(main_text)}; "
            f"header signatures={hints(header_text)}. "
            "Refusing speculative patch.")
    dest_hashes={f.name:sha(f.read_bytes()) for f in files}
    header_hashes={f.name:sha(f.read_bytes()) for f in headers}
    expected={f.name:sha(patched_header if f==header else f.read_bytes())
              for f in headers}
    expected.update(dest_hashes)
    if output_shards.exists() and any(output_shards.iterdir()):
        names={f.name for f in output_shards.iterdir()}
        if names!=set(expected):
            raise ValueError("existing staged TrueTU directory contains missing/foreign files")
        for filename,digest in expected.items():
            if sha((output_shards/filename).read_bytes())!=digest:
                raise ValueError(f"existing staged TrueTU byte mismatch: {filename}")
        if not out.is_file() or sha(out.read_bytes())!=sha(patched_main):
            raise ValueError("existing staged main mismatch")
        print("[K1A-DSOBJECT] REUSE PASS: exact 64 TrueTU + generated header hashes")
    else:
        output_shards.mkdir(parents=True,exist_ok=True)
        for f in files:
            shutil.copy2(f,output_shards/f.name)
        for f in headers:
            if f==header and owner=="translated_runtime.h":
                (output_shards/f.name).write_bytes(patched_header)
            else:
                shutil.copy2(f,output_shards/f.name)
        out.write_bytes(patched_main)
    for f in files:
        if sha(f.read_bytes())!=dest_hashes[f.name]:
            raise RuntimeError(f"original TrueTU changed unexpectedly: {f.name}")
        if sha((output_shards/f.name).read_bytes())!=dest_hashes[f.name]:
            raise RuntimeError(f"staged TrueTU changed unexpectedly: {f.name}")
    for f in headers:
        if sha(f.read_bytes())!=header_hashes[f.name]:
            raise RuntimeError(f"original header changed unexpectedly: {f.name}")
        if sha((output_shards/f.name).read_bytes())!=expected[f.name]:
            raise RuntimeError(f"staged header hash mismatch: {f.name}")
    if sha(main.read_bytes())!=sha(main_bytes):
        raise RuntimeError("source K1A clock main changed unexpectedly")
    if sha(out.read_bytes())!=sha(patched_main):
        raise RuntimeError("staged main hash mismatch")
    doc={
        "status":"STAGED_ONLY_NO_XDK_BUILD",
        "marker":MARK,
        "writer_owner":owner,
        "main_definition_counts":main_counts,
        "header_definition_counts":header_counts,
        "main_original_sha256":sha(main_bytes),
        "main_staged_sha256":sha(patched_main),
        "runtime_header_original_sha256":sha(header_bytes),
        "runtime_header_staged_sha256":sha(patched_header),
        "generated_header_count":len(headers),
        "generated_cpp_count":64,
        "changed_cpp_count":0,
        "watch_widths":[1,2,4],
        "watch_guest_start":"00041D70",
        "watch_guest_end_exclusive":"00041D78",
        "guest_write_semantics":"PRESERVED",
        "unknown_memory_fences":"PRESERVED",
        "original_main":str(main),
        "staged_main":str(out),
        "source_shards":str(shards),
        "staged_shards":str(output_shards),
    }
    manifest=output_dir/"k1a-dsound-writer-watch-manifest.json"
    manifest.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
    return doc

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",required=True,type=Path)
    p.add_argument("--shards",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    result=stage(a.main,a.shards,a.out)
    print("[K1A-DSOBJECT] STAGE PASS: real writer owner="+result["writer_owner"])
    print("[K1A-DSOBJECT] 64 TrueTU .cpp files identical; all generated headers verified")
    print("[K1A-DSOBJECT] 8/16/32 bit overlapping guest writes monitored; no guest mutation")
    print("[K1A-DSOBJECT] No Xbox build yet; output="+str(a.out))

if __name__=="__main__":
    main()
