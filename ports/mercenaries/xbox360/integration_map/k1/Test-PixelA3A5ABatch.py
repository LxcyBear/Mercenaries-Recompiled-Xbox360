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
    # Exact regression for the real generated file's reported 0 definitions:
    # generated function names retain a lowercase 'sub_' prefix. Confirm
    # upper/lowercase normalization on the actual 231-line source, not only
    # a synthetic one-line C function.
    extracted=stage.find_body(
        "/* uncompromised original generated source */\n"
        +original+"\nvoid sub_002A0000(void)\n{\n}\n",
        stage.NAME)
    assert extracted.strip()==original.strip()
    assert extracted.count("loc_002A3A5A: ;")==1
    must_refuse(stage.find_body,
        "void sub_002A0000(void)\n{\n}\n",stage.NAME)
    must_refuse(stage.find_body,original+"\n"+original,stage.NAME)
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
        # Regression for the exact 2026-10-30 failure: a new direct
        # caller's forward declaration is never a duplicate BODY.
        assert updated.count(stage.PROTOTYPE)==1
        with_predeclaration=dummy.replace(
            '#include "translated_runtime.h"',
            '#include "translated_runtime.h"'+nl+stage.PROTOTYPE)
        predeclared,predeclared_edges=stage.patch_tu(
            with_predeclaration,True,new)
        assert predeclared_edges==1
        assert predeclared.count(stage.PROTOTYPE)==1
        assert predeclared.count("PIXEL A3A5A ENTRY")==1
        existing_definition=dummy+(
            nl+"void sub_002A3A5A(void)"+nl+"{"+nl+"}"+nl)
        must_refuse(stage.patch_tu,existing_definition,True,new)
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
        assert main_new.count("case 0x002A3A5Au:")==0
        assert main_new.count(stage.PROTOTYPE)==1
        assert main_new.count(stage.TAG)==1
        assert "sub_002A3A5A();" in main_new
        assert main_new.count("phase4c_lookup_pack_func")==1
        must_refuse(stage.patch_main,main_new)
        # Real K1C host main is a TrueTU bootstrap and need not own
        # the old Phase6DQ pack lookup. Direct restore must work even
        # when the lookup function is completely absent.
        no_lookup=dummy_main.replace(
            "phase4c_lookup_pack_func","phase4c_lookup_wrong")
        no_lookup_new,no_lookup_count=stage.patch_main(no_lookup)
        assert no_lookup_count==1
        assert "sub_002A3A5A();" in no_lookup_new
        assert "case 0x002A3A5Au:" not in no_lookup_new
        # If there is no DIRECT frontier in host main, it remains
        # byte-identical, and the TrueTU owners alone restore calls.
        no_host_edge=dummy_main.replace(stage.FRONTIER,"phase4c_direct_frontier(0x002A3A58u);")
        untouched,num=stage.patch_main(no_host_edge)
        assert num==0 and untouched==no_host_edge
        # Duplicate body and internal-only declarations remain refused.
        must_refuse(stage.patch_main,no_lookup+
            nl+"static void sub_002A3A5A(void);"+nl)
        must_refuse(stage.patch_main,no_lookup+
            nl+"void sub_002A3A5A(void)"+nl+"{"+nl+"}"+nl)
    print("[PIXEL-BUILD] REAL ORIGINAL SOURCE PASS: complete 231-line original A3A5A")
    print("[PIXEL-BUILD] APU PASS: one real poll + five real VP writes routed to existing helpers")
    print("[PIXEL-BUILD] CONTROL PASS: 3 original direct calls, original ret8 and all POP/PUSH preserved")
    print("[PIXEL-BUILD] WIRING PASS: original host/TrueTU direct edges (legacy lookup optional); LF/CRLF")
    print("[PIXEL-BUILD] SAFETY PASS: changed targets, stale stage and orphan lookup rejected")
    print("[PIXEL-BUILD] NO XDK or Xbox invocation")


if __name__=="__main__":
    main()
