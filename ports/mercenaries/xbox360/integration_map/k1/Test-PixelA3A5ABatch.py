#!/usr/bin/env python3
"""PIXEL A3A5A tests against user's real proof report, no XDK or Xbox."""
from __future__ import annotations
import argparse
import importlib.util
import re
from pathlib import Path

STAGE=Path(__file__).with_name("Stage-PixelA3A5ABatch.py")
spec=importlib.util.spec_from_file_location("pixel_a3a5a_stage",STAGE)
assert spec and spec.loader
stage=importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def original_from_proof(data:str)->str:
    source={}
    for line in data.splitlines():
        m=re.match(r"^\s*(\d{5}) (.*)$",line)
        if m and 42763<=int(m.group(1))<=42993:
            n=int(m.group(1))
            if n in source:raise AssertionError("Duplicate source line in proof")
            source[n]=m.group(2)
    if len(source)!=231 or any(n not in source for n in range(42763,42994)):
        raise AssertionError("Original A3A5A report incomplete")
    return "\n".join(source[n] for n in range(42763,42994))+"\n"


def must_refuse(function,*args)->None:
    try:
        function(*args)
    except ValueError:
        return
    raise AssertionError("Expected source/provenance refusal")


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--proof",required=True,type=Path)
    args=parser.parse_args()
    proof=args.proof.read_text(encoding="utf-8-sig")
    original=original_from_proof(proof)
    assert original.startswith("void sub_002A3A5A(void)")
    assert original.rstrip().endswith("}")
    for nl in ("\n","\r\n"):
        new,metric=stage.budgeted_body(original,nl)
        assert "PIXEL A3A5A ENTRY" in new
        assert metric["replaced_apu_read32"]==1
        assert metric["replaced_apu_write32"]==5
        assert metric["budget_tick_sites"]>=8
        assert "recomp_apu_read32" not in new
        assert "recomp_apu_write32" not in new
        assert "phase6ch_apu_read32((uint32_t)-25034736)" in new
        assert "phase6ch_apu_write32(0xFE820160u, eax)" in new
        assert "phase6ch_apu_write32(ebx, edx)" in new
        assert new.count("esp += 12; return; /* ret 8 */")==1
        assert all(new.count(name+"();")==1 for name in stage.EXACT_CALLS)
        assert (new.count("\r\n")==new.count("\n") if nl=="\r\n"
                else "\r" not in new)
        must_refuse(stage.budgeted_body,original.replace(
            "0xFE82043Cu","0xFE820440u"),nl)
        must_refuse(stage.budgeted_body,original.replace(
            "recomp_apu_read32((uint32_t)-25034736)",
            "recomp_apu_read32((uint32_t)-25034732)"),nl)
        must_refuse(stage.budgeted_body,original.replace(
            "esp += 12; return; /* ret 8 */",
            "esp += 8; return; /* ret 4 */"),nl)
        include='#include "translated_runtime.h"'+nl
        dummy=('#include "translated_runtime.h"\n'
               'void sub_002A3B00(void)\n{\n'
               '    PUSH32(esp, 0); '+stage.FRONTIER+
               ' /* call 0x002A3A5A */\n}\n').replace("\n",nl)
        updated,edge=stage.patch_tu(dummy,True,new)
        assert edge==1
        assert "sub_002A3A5A(); /* call 0x002A3A5A */" in updated
        assert updated.count("PIXEL A3A5A ENTRY")==1
        assert updated.count(stage.TAG)==1
        assert all("void "+name+"(void);" in updated for name in stage.EXACT_CALLS)
        assert "phase4c_direct_frontier(0x002A3A5Au)" not in updated
        must_refuse(stage.patch_tu,updated,True,new)
        must_refuse(stage.patch_tu,dummy.replace(include,""),True,new)
        dummy_main=("P6DQ-R51-MM173-FRAME-20261029-A"+nl+
            "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)"+nl+
            "{"+nl+"    switch(xbox_va)"+nl+"    {"+nl+
            "    default: return (recomp_func_t)0;"+nl+"    }"+nl+"}"+nl+
            "void some_owner(void)"+nl+"{"+nl+
            "    PUSH32(esp, 0); "+stage.FRONTIER+nl+"}"+nl)
        main_new,main_edges=stage.patch_main(dummy_main)
        assert main_edges==1
        assert main_new.count("case 0x002A3A5Au:")==1
        assert main_new.count(stage.PROTOTYPE)==1
        assert main_new.count(stage.TAG)==1
        assert "sub_002A3A5A();" in main_new
        must_refuse(stage.patch_main,main_new)
        must_refuse(stage.patch_main,dummy_main.replace(
            "phase4c_lookup_pack_func","phase4c_lookup_wrong"))
    print("[PIXEL-BUILD] REAL ORIGINAL SOURCE PASS: complete 231-line original A3A5A")
    print("[PIXEL-BUILD] APU PASS: one real poll + five real VP writes routed to existing helpers")
    print("[PIXEL-BUILD] CONTROL PASS: 3 original direct calls, original ret8 and all POP/PUSH preserved")
    print("[PIXEL-BUILD] WIRING PASS: caller TrueTU/host lookup and exact direct edge; LF/CRLF")
    print("[PIXEL-BUILD] SAFETY PASS: changed targets, stale stage and orphan lookup rejected")
    print("[PIXEL-BUILD] NO XDK or Xbox invocation")


if __name__=="__main__":
    main()
