#!/usr/bin/env python3
"""K1B: stage a central, overlap-only guest WRITE8/16/32/64/128 trace.

The 64 TrueTU files and their original staged runtime header are never
modified. This patches a *new copy* of the known K1A+DSINDEX+DSOBJECT main.
Only central recomp_guest_write* definitions are wrapped, without changing
the underlying write, memory mapping, or existing hard fences.

Runtime evidence: the original retail XBE has DWORD[00041D70]=00041D59,
while the same live Xbox address is 01B672D8 before DSOUND page indexing.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

MARK="P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030"
BASE_MARK="P6K1A-BOOT-CLOCK128-304-305-20261029"
DSOBJECT_MARK="P6K1A-DSOUND-OBJECT-WRITER-WATCH-20261030"
BOOT="PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START"
CENTER=0x00041D70
END=0x00041D78

SPECS=(
    ("recomp_guest_write8","uint8_t",1),
    ("recomp_guest_write16","uint16_t",2),
    ("recomp_guest_write32","uint32_t",4),
    ("recomp_guest_write64","uint64_t",8),
    ("recomp_guest_write128","const uint32_t words[4]",16),
)

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def function_pattern(name:str, typ:str)->re.Pattern[str]:
    if name=="recomp_guest_write128":
        sig=(r"(?m)^[ \t]*void[ \t]+recomp_guest_write128[ \t]*"
             r"\([ \t]*(?:\r?\n[ \t]*)?uint32_t[ \t]+address[ \t]*,[ \t]*"
             r"(?:\r?\n[ \t]*)?const[ \t]+uint32_t[ \t]+words\[4\][ \t]*"
             r"\)[ \t]*(?:\r?\n[ \t]*)?\{")
    else:
        sig=(r"(?m)^[ \t]*void[ \t]+"+re.escape(name)
             +r"[ \t]*\([ \t]*uint32_t[ \t]+address[ \t]*,[ \t]*"
             +re.escape(typ)
             +r"[ \t]+value[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
    return re.compile(sig)

def patch(source:str)->str:
    if source.count(BASE_MARK)!=1:
        raise ValueError("missing or duplicate original three-clock K1A marker")
    if source.count(DSOBJECT_MARK)!=3:
        raise ValueError("missing or duplicate earlier APU helper watch")
    if MARK in source:
        raise ValueError("already has K1B central-writer watch")
    if source.count(BOOT)!=1:
        raise ValueError("exact Xbox boot log text missing or duplicated")
    caller_definition="static DWORD phase4c_current_caller(void)"
    if source.count(caller_definition)!=1:
        raise ValueError("required existing caller tracker definition absent/duplicated")
    crlf=source.count("\r\n")
    if crlf and crlf!=source.count("\n"):
        raise ValueError("mixed C++ source line endings")
    newline="\r\n" if crlf else "\n"
    # These five central stores are defined before the pre-existing static
    # caller-tracking function. Declare it before the first store so MSVC
    # 2017 can resolve the forensic log call (C3861 otherwise).
    first=list(function_pattern("recomp_guest_write8","uint8_t").finditer(source))
    if len(first)!=1 or source.index(caller_definition)<=first[0].start():
        raise ValueError("unexpected caller definition/order; refuse speculative C3861 repair")
    declaration="static DWORD phase4c_current_caller(void);"
    if declaration in source:
        raise ValueError("caller already forward declared; unexpected baseline")
    source=source[:first[0].start()]+declaration+newline+source[first[0].start():]
    for name,typ,width in SPECS:
        matches=list(function_pattern(name,typ).finditer(source))
        if len(matches)!=1:
            raise ValueError(f"source drift: exact {name} implementation count={len(matches)}")
        at=matches[0].end()
        # All buffers are initialized *before* the existing guest write;
        # this is a forensic pre-write observation, never a store bypass.
        value_expr="words[0]" if width==16 else "value"
        high_expr="words[3]" if width==16 else ("(uint32_t)(value >> 32)" if width==8 else "0u")
        body=(
            newline+f"    /* {MARK}: {name}, read-only pre-store witness. */"+newline
            +f"    if ((uint64_t)address < 0x{END:08X}u &&"+newline
            +f"        (uint64_t)address + {width}u > 0x{CENTER:08X}u)"+newline
            +"    {"+newline
            +"        static uint32_t k1b_hit_count = 0u;"+newline
            +"        ++k1b_hit_count;"+newline
            +"        if (k1b_hit_count <= 16u)"+newline
            +"        {"+newline
            +"            char k1b_line[360];"+newline
            +"            sprintf(k1b_line,"+newline
            +'                "K1B CENTRAL WRITE: width=%u hit=%u address=%08X value_lo=%08X value_hi=%08X before0=%08X before4=%08X caller=%08X budget=%u esp=%08X",'+newline
            +f"                {width}u, (unsigned)k1b_hit_count,"+newline
            +f"                (unsigned)address, (unsigned)({value_expr}),"+newline
            +f"                (unsigned)({high_expr}),"+newline
            +"                (unsigned)recomp_guest_read32(0x00041D70u),"+newline
            +"                (unsigned)recomp_guest_read32(0x00041D74u),"+newline
            +"                (unsigned)phase4c_current_caller(),"+newline
            +"                (unsigned)s_execBudget, (unsigned)g_esp);"+newline
            +"            trace(k1b_line);"+newline
            +"        }"+newline
            +"    }"+newline
        )
        source=source[:at]+body+source[at:]
    # The first boot log tells us *this actual new main.cpp* was deployed,
    # even in runs where no watched write happens. No new game-side activity.
    source=source.replace(BOOT,BOOT+" | "+MARK,1)
    if source.count(MARK)!=6 or source.count(declaration)!=1:
        raise ValueError("five writers, one boot tag and one caller declaration required")
    return source

def stage(baseline:Path,shard_dir:Path,out:Path)->dict:
    baseline=baseline.resolve()
    shard_dir=shard_dir.resolve()
    out=out.resolve()
    if baseline==out or baseline.parent==out.parent:
        raise ValueError("new staged K1B main must not overwrite earlier K1A source")
    if out.parent in shard_dir.parents or shard_dir==out.parent:
        raise ValueError("cannot stage K1B inside frozen TrueTU input directory")
    original=baseline.read_bytes()
    patched=patch(original.decode("utf-8")).encode("utf-8")
    shards=sorted(shard_dir.glob("translated_*.cpp"))
    if len(shards)!=64:
        raise ValueError(f"expected 64 frozen TrueTU shards, got {len(shards)}")
    headers=sorted(shard_dir.glob("*.h"))
    if "translated_runtime.h" not in {p.name for p in headers}:
        raise ValueError("generated translated_runtime.h absent")
    # The next build can use *exactly* the same previously proven TrueTU
    # sources; stage only a changed main, avoiding huge shard copy/rebuild.
    originals={p.name:sha(p.read_bytes()) for p in [*shards,*headers]}
    if out.exists():
        if sha(out.read_bytes())!=sha(patched):
            raise ValueError("K1B existing staged main differs: refusing overwrite")
        print("[K1B-WRITE] REUSE PASS: staged main SHA identical")
    else:
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(patched)
    if sha(baseline.read_bytes())!=sha(original):
        raise RuntimeError("K1A source changed during K1B stage")
    for f in [*shards,*headers]:
        if sha(f.read_bytes())!=originals[f.name]:
            raise RuntimeError("source changed during K1B stage: "+f.name)
    record={
        "status":"STAGED_ONLY_NO_XDK_BUILD",
        "marker":MARK,"runtime_boot_marker":BOOT+" | "+MARK,
        "old_main_sha256":sha(original),"new_main_sha256":sha(patched),
        "old_main":str(baseline),"new_main":str(out),
        "frozen_shards":str(shard_dir),"shard_count":64,
        "header_count":len(headers),"source_header_shas":{p.name:originals[p.name] for p in headers},
        "instrumented_guest_writer_widths":[1,2,4,8,16],
        "guest_memory_range":"00041D70..00041D77",
        "guest_memory_writes_added":0,"hard_fence_policy":"UNCHANGED",
    }
    manifest=out.parent/"k1b-central-writer-manifest.json"
    manifest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",required=True,type=Path)
    p.add_argument("--shards",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    a=p.parse_args()
    doc=stage(a.main,a.shards,a.out)
    print("[K1B-WRITE] STAGE PASS: 5 central guest writers, one visible Xbox boot tag")
    print("[K1B-WRITE] 64 TrueTU shards + all generated headers UNCHANGED")
    print("[K1B-WRITE] Guest memory and MMIO hard fences UNCHANGED; no XDK build yet")
    print("[K1B-WRITE] manifest="+str(a.out.parent/"k1b-central-writer-manifest.json"))

if __name__=="__main__":main()
