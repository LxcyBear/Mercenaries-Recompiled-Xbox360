#!/usr/bin/env python3
"""K1S real frozen-source regression for one-register caller-edge correction.

Generate actual K1R instrumented A7B73 from the user's verified K1Q
original source, then apply K1S. Synthetic guest-stack arithmetic must
match the K1R Xbox trace. No guest memory, other calls, or return opcode
may change. This runs without Visual Studio, XDK or Xbox.
"""
from __future__ import annotations
import argparse
import importlib.util
from pathlib import Path

ROOT=Path(__file__).resolve().parent


def load(name:str,path:Path):
    spec=importlib.util.spec_from_file_location(name,path)
    assert spec and spec.loader
    obj=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(obj)
    return obj


k1r=load("k1r_stage_for_k1s_test",ROOT/"Stage-K1R-A6B98A7B73StackPath.py")
k1r_test=load("k1r_test_for_k1s_test",ROOT/"Test-K1R-A6B98A7B73StackPath.py")
k1s=load("k1s_stage",ROOT/"Stage-K1S-HalGetVectorSavedEsi.py")


def fails(source:str,explanation:str)->None:
    try:
        k1s.modify(source)
    except ValueError:
        return
    raise AssertionError("K1S unexpectedly accepted "+explanation)


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--k1q-report",required=True,type=Path)
    opt=parser.parse_args()
    q=opt.k1q_report.read_text(encoding="utf-8-sig")
    original=k1r_test.parse_report(
        q,"### SUB_002A7B73 (translated_044.cpp line 21121)",
        21121,21290
    )
    assert original.count("PUSH32(esp, esi);")==3
    assert original.count("POP32(esp, esi);")==1
    assert original.count("phase6ch_apu_read32(0x2DBE20)")==1
    assert original.count("esp += 8; return; /* ret 4 */")==1
    for nl in ("\n","\r\n"):
        k1r_source,_=k1r.modify("translated_044.cpp",original.replace("\n",nl))
        final=k1s.modify(k1r_source)
        assert final.count(k1s.TAG)==1
        assert final.count("K1S HALGETVECTOR44 ESI SLOT:")==1
        assert final.count("esp = k1s_saved_esi_slot;")==1
        assert final.count("k1s_raw_esp == ebp - 8u")==1
        assert final.count("const uint32_t k1s_saved_esi_slot = ebp - 12u;")==1
        assert final.count("K1R ICALL ")==k1r_source.count("K1R ICALL ")
        assert final.count("K1R CALL ")==k1r_source.count("K1R CALL ")
        assert final.count("K1R PATH ")==k1r_source.count("K1R PATH ")
        assert k1s.MEM.findall(k1r_source)==k1s.MEM.findall(final)
        assert k1s.CALL.findall(k1r_source)==k1s.CALL.findall(final)
        assert k1s.ICALL.findall(k1r_source)==k1s.ICALL.findall(final)
        assert k1s.PUSHPOP.findall(k1r_source)==k1s.PUSHPOP.findall(final)
        assert final.count("esp += 8; return; /* ret 4 */")==1
        assert (final.count("\r\n")==final.count("\n")
                if nl=="\r\n" else "\r" not in final)
        assert final.index("K1R ICALL A7B73_ICALL_2") < final.index(
            "esp = k1s_saved_esi_slot;") < final.index("loc_002A7BDE: ;")
        fails(final,"second staged conditional repair")
        fails(k1r_source.replace(
            "phase6ch_apu_read32(0x2DBE20)",
            "phase6ch_apu_read32(0x2DBE24)"),"kernel ordinal drift")
        fails(k1r_source.replace(
            "    POP32(esp, esi);",
            "    POP32(esp, ebx);"),"saved ESI epilogue drift")
        fails(k1r_source.replace(
            "K1R ICALL A7B73_ICALL_2",
            "K1R ICALL A7B73_ICALL_9"),"K1R raw witness drift")
    ebp=0x008BF888
    raw=0x008BF880
    expected=ebp-12
    assert raw==ebp-8
    assert expected==0x008BF87C
    assert raw-expected==4
    assert expected+4==raw # the matching POP ESI
    assert expected+4*4+8==0x008BF894 # POP ESI/EDI/EBX/EBP; ret4
    assert 0x008BF894-0x008BF890==4 # A6B98 caller expected +4
    print("[K1S] REAL-SOURCE PASS: guarded A7BD1 ordinal-44 correction and caller return math")
    print("[K1S] REAL-SOURCE PASS: K1Q->K1R original/source, LF/CRLF, no double stage")
    print("[K1S] REAL-SOURCE PASS: original guest memory, calls, POP/PUSH and ret4 unchanged")
    print("[K1S] REAL-SOURCE PASS: raw ESP=EBP-8 -> saved ESI slot EBP-12")
    print("[K1S] NO XDK build or Xbox run")


if __name__=="__main__":
    main()
