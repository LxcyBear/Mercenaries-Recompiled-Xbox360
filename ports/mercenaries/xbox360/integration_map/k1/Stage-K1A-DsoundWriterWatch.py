#!/usr/bin/env python3
"""Read-only guest-write provenance watch for the K1A DirectSound bad object.

The 2026-10-30 Xbox DSINDEX test proved [00041D70]=01B672D8,
[00041D74]=04020100 BEFORE ordinal 173. The exact retail XBE originally
contains 00041D59,04020100 there. This stages a different main.cpp which
journals any translated 8/16/32-bit write overlapping these eight bytes.

Never changes a guest register, write result, MMIO fence or source TrueTU.
Writes via host-native bulk-copy paths are not captured by these wrappers.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

K1A_MARK="P6K1A-BOOT-CLOCK128-304-305-20261029"
MARK="P6K1A-DSOUND-OBJECT-WRITER-WATCH-20261030"
WATCH_BEGIN=0x00041D70
WATCH_END=0x00041D78
SPEC=(
  ("phase6ch_apu_write8","uint8_t",1),
  ("phase6ch_apu_write16","uint16_t",2),
  ("phase6ch_apu_write32","uint32_t",4),
)

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def patch(text:str)->str:
    if text.count(K1A_MARK)!=1:
        raise ValueError("requires exactly one K1A boot marker in existing 3-clock main")
    if MARK in text:
        raise ValueError("object-write watch already staged; no duplicate")
    # In the main translation, guest write calls pass through one of these
    # three helper definitions. Log BEFORE the original helper body executes.
    for name,typ,width in SPEC:
        pattern=re.compile(
            r"(?m)^[ \t]*static[ \t]+void[ \t]+"
            +re.escape(name)
            +r"[ \t]*\([ \t]*uint32_t[ \t]+address[ \t]*,[ \t]*"
            +re.escape(typ)
            +r"[ \t]+value[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
        matches=list(pattern.finditer(text))
        if len(matches)!=1:
            raise ValueError(f"{name}: exact writer definition count={len(matches)}")
        pos=matches[0].end()
        # Preserve destination source line endings while adding host log only.
        newline="\r\n" if "\r\n" in text else "\n"
        watch=(
            f"{newline}    /* {MARK} {name}: read-only pre-write witness. */{newline}"
            f"    if (address < 0x{WATCH_END:08X}u &&{newline}"
            f"        (uint64_t)address + {width}u > 0x{WATCH_BEGIN:08X}u){newline}"
            "    {"+newline+
            "        static uint32_t k1a_ds_writes = 0u;"+newline+
            "        ++k1a_ds_writes;"+newline+
            "        if (k1a_ds_writes <= 32u)"+newline+
            "        {"+newline+
            "            char k1a_ds_line[320];"+newline+
            "            sprintf(k1a_ds_line,"+newline+
            '                "K1A DSOBJECT WRITE: width=%u n=%u guest=%08X value=%08X before0=%08X before4=%08X caller=%08X esp=%08X eax=%08X ebx=%08X ecx=%08X edx=%08X esi=%08X edi=%08X",'+newline+
            f"                {width}u, (unsigned)k1a_ds_writes, (unsigned)address, (unsigned)value,"+newline+
            "                (unsigned)GUEST_READ32(0x00041D70u),"+newline+
            "                (unsigned)GUEST_READ32(0x00041D74u),"+newline+
            "                (unsigned)phase4c_current_caller(), (unsigned)g_esp,"+newline+
            "                (unsigned)eax, (unsigned)ebx, (unsigned)ecx,"+newline+
            "                (unsigned)edx, (unsigned)esi, (unsigned)edi);"+newline+
            "            trace(k1a_ds_line);"+newline+
            "        }"+newline+
            "    }"+newline
        )
        text=text[:pos]+watch+text[pos:]
    if text.count(MARK)!=3:
        raise ValueError("expected exactly one watch insertion for each write width")
    return text

def stage(source:Path,out:Path)->dict:
    source=source.resolve()
    out=out.resolve()
    if source==out:
        raise ValueError("refusing to modify existing K1A source")
    before=source.read_bytes()
    transformed=patch(before.decode("utf-8")).encode("utf-8")
    if out.is_file():
        if sha(out.read_bytes())!=sha(transformed):
            raise ValueError("existing object-writer staged main differs; stop")
        print("[K1A-DSOBJECT] REUSE PASS: staged writer main SHA identical")
    else:
        out.parent.mkdir(parents=True,exist_ok=True)
        out.write_bytes(transformed)
    if sha(source.read_bytes())!=sha(before):
        raise RuntimeError("original 3-clock K1A main modified during stage")
    record={
      "status":"STAGED_ONLY_NO_XDK_BUILD","marker":MARK,
      "first_guest_address":"00041D70",
      "monitored_range_exclusive_end":"00041D78",
      "original_main_sha256":sha(before),
      "staged_main_sha256":sha(transformed),
      "watch_widths":[1,2,4],"original_main":str(source),
      "staged_main":str(out),"guest_write_semantics":"PRESERVED",
      "unknown_memory_fences":"PRESERVED",
    }
    manifest=out.parent/"k1a-dsound-writer-watch-manifest.json"
    manifest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    doc=stage(args.main,args.out)
    print("[K1A-DSOBJECT] PASS: captured 8/16/32 translated guest writes crossing 00041D70..00041D77")
    print("[K1A-DSOBJECT] Source K1A clock main SHA preserved: "+doc["original_main_sha256"])
    print("[K1A-DSOBJECT] NO XDK build, NO guest mutation or new MMIO mappings")
    print("[K1A-DSOBJECT] STAGED: "+str(args.out))
if __name__=="__main__":main()
