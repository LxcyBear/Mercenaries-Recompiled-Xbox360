#!/usr/bin/env python3
"""R59: repair specifically proven x86 callee-saved register clobbers in FC4A.

R58 *hardware*: sub_0029FC4A expects EBX=8007000E; EDI=7FF8FFF2,
ESI=008C1104. After sub_002A19FC ESI=008BFF8C and EDI=008C1104;
after sub_0029FF54 EDI=008BF918. A successful FF54 allocation
024901D4 was followed by failure status 81AEC546, exactly
(7FF8FFF2 + 01B5C554) mod 2**32 (nested object pointer from A0E9D).
Hypothesis: EBX was clobbered to 01B5C554 by a nested callee.
This overlay preserves EBX/ESI/EDI at TWO exact guest call boundaries in
sub_0029FC4A only, as required by x86's callee-saved ABI.
No guest memory writes are skipped or emulated, no status is forced,
no pointer is synthesized, no memory fence changed. First 6 instances
log before/after to verify runtime register provenance.
R58 logging remains intact, baseline R51 Rocket/manifest remain read-only.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

BUILD_TAG="P6DQ-R51-MM173-FRAME-20261029-A"
R58_TAG="P6DQ R58 DSOUND STATUS:"
R59_TAG="P6DQ R59 FC4A ABI RESTORE:"

def patch_one(text:str,func_va:int,needle:str,replacement:str)->str:
    signature=f"static void sub_{func_va:08X}(void)"
    patt=re.compile(r"(?m)^\s*static void sub_"+f"{func_va:08X}"+r"\(void\)\s*\{")
    matches=list(patt.finditer(text))
    if len(matches)!=1:
        raise SystemExit(f"[Phase6R59] required single function missing: {signature} count={len(matches)}")
    m=matches[0]
    brace=text.find("{",m.start(),m.end())
    end=closing_brace(text,brace)
    body=text[m.start():end]
    if body.count(needle)!=1:
        raise SystemExit(f"[Phase6R59] expected one {needle.strip()} in {signature}, found {body.count(needle)}")
    body=body.replace(needle,replacement,1)
    return text[:m.start()]+body+text[end:]

def wrapped_call(callname:str,kind:str)->str:
    old=f"    PUSH32(esp, 0); {callname}(); /* call 0x{callname[4:]} */"
    return (
        "    {\n"
        "        /* R59: guest x86 callee must preserve EBX, ESI and EDI. */\n"
        "        const uint32_t r59_saved_ebx = ebx;\n"
        "        const uint32_t r59_saved_esi = esi;\n"
        "        const uint32_t r59_saved_edi = edi;\n"
        +old+"\n"
        "        const uint32_t r59_after_ebx = ebx;\n"
        "        const uint32_t r59_after_esi = esi;\n"
        "        const uint32_t r59_after_edi = edi;\n"
        "        static unsigned int r59_calls = 0u;\n"
        "        ++r59_calls;\n"
        "        if (r59_calls <= 6u)\n"
        "        {\n"
        "            char r59_line[320];\n"
        "            sprintf(r59_line,\n"
        f'                "P6DQ R59 FC4A ABI RESTORE: {kind} n=%u ebx=%08X->%08X esi=%08X->%08X edi=%08X->%08X eax=%08X esp=%08X",\n'
        "                (unsigned int)r59_calls,\n"
        "                (unsigned int)r59_saved_ebx, (unsigned int)r59_after_ebx,\n"
        "                (unsigned int)r59_saved_esi, (unsigned int)r59_after_esi,\n"
        "                (unsigned int)r59_saved_edi, (unsigned int)r59_after_edi,\n"
        "                (unsigned int)eax, (unsigned int)esp);\n"
        "            trace(r59_line);\n"
        "        }\n"
        "        ebx = r59_saved_ebx;\n"
        "        esi = r59_saved_esi;\n"
        "        edi = r59_saved_edi;\n"
        "    }"
    )

def main()->int:
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if not args.source.is_file():raise SystemExit("[Phase6R59] Missing R58 mono overlay source")
    text=args.source.read_text(encoding="utf-8",errors="replace")
    if BUILD_TAG not in text or R58_TAG not in text:
        raise SystemExit("[Phase6R59] R51-tagged R58 provenance source required")
    if R59_TAG in text:
        raise SystemExit("[Phase6R59] duplicate R59 overlay rejected")
    if (0x7FF8FFF2+0x01B5C554)&0xffffffff!=0x81AEC546:
        raise SystemExit("[Phase6R59] fatal status arithmetic proof failed")
    for callee,label in (
        ("sub_002A19FC","A19FC"),
        ("sub_0029FF54","FF54"),
    ):
        orig=f"    PUSH32(esp, 0); {callee}(); /* call 0x{callee[4:]} */"
        text=patch_one(text,0x0029FC4A,orig,wrapped_call(callee,label))
    if text.count(R59_TAG)!=2:
        raise SystemExit("[Phase6R59] bounded ABI diagnostic sites missing/duplicated")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    encoded=text.encode("utf-8")
    if args.out.is_file() and args.out.read_bytes()==encoded:
        print("[Phase6R59] Content-stable R59 source unchanged")
    else:
        args.out.write_bytes(encoded)
        print("[Phase6R59] R59 overlay generated without changing R51/R58 sources")
    print("[Phase6R59] R58 proof: 0x7FF8FFF2 + 0x01B5C554 = 0x81AEC546")
    print("[Phase6R59] Target=0029FC4A, boundaries=002A19FC and 0029FF54")
    print("[Phase6R59] ABI=restore caller EBX/ESI/EDI only; EAX/ECX/EDX/ESP retained")
    print("[Phase6R59] No forced success, fake object, XACT lifetime mutation, or memory-fence changes")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
