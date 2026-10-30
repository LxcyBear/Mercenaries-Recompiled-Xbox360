#!/usr/bin/env python3
"""K1R source-driven preflight against the REAL user's K1Q original function text.

Unlike a guessed synthetic call-site fixture, this test extracts all original
source lines for A6B98 and A7B73 from K1Q's frozen-TrueTU report and runs
the EXACT K1R stager on those real function bodies. Tests LF/CRLF, altered
callsite refusal, duplicate refusal, and original guest op retention.
"""
from __future__ import annotations
import argparse
import importlib.util
import re
from pathlib import Path

p=Path(__file__).resolve().parent/"Stage-K1R-A6B98A7B73StackPath.py"
spec=importlib.util.spec_from_file_location("k1r_stage",p)
assert spec and spec.loader
stage=importlib.util.module_from_spec(spec)
spec.loader.exec_module(stage)


def parse_report(data:str, section:str, start:int, end:int)->str:
    index=data.find(section)
    if index<0:
        raise ValueError("K1Q expected source heading absent: "+section)
    # The report includes both numbered nonblank code and blank lines.
    # Assign numbered lines by their original source line number.
    collected={}
    for line in data[index+len(section):].splitlines():
        if line.startswith("## ") or (line.startswith("### ") and collected):
            break
        m=re.match(r"^\s*(\d{5}) (.*)$",line)
        if m:
            n=int(m.group(1))
            if n<start or n>end:
                if collected:
                    break
                continue
            if n in collected:
                raise ValueError("Duplicate K1Q line in source fixture")
            collected[n]=m.group(2)
    if len(collected)<(end-start)*0.6 or start not in collected or end not in collected:
        raise ValueError(f"K1Q source fixture incomplete: {section}, {len(collected)} lines")
    return "\n".join(collected.get(n,"") for n in range(start,end+1))+"\n"


def must_reject(filename:str,source:str,label:str)->None:
    try:
        stage.modify(filename,source)
    except ValueError:
        return
    raise AssertionError("K1R accepted invalid source: "+label)


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--k1q-report",required=True,type=Path)
    args=parser.parse_args()
    text=args.k1q_report.read_text(encoding="utf-8-sig")
    inputs={
        "translated_005.cpp":parse_report(
            text,"## Full A6B98 original source with original TrueTU line numbers",16208,16347
        ),
        "translated_044.cpp":parse_report(
            text,"### SUB_002A7B73 (translated_044.cpp line 21121)",21121,21290
        ),
    }
    sites_total=0
    for filename,raw in inputs.items():
        for nl in ("\n","\r\n"):
            source=raw.replace("\n",nl)
            new,names=stage.modify(filename,source)
            expected=9 if filename=="translated_005.cpp" else 12
            sites_total+=len(names)
            if len(names)!=expected or new.count(stage.TAG)!=expected:
                raise AssertionError(f"{filename} wrong probe count {len(names)}")
            if len(names)!=len(set(names)):
                raise AssertionError("Duplicate per-callsite K1R probe labels")
            if stage.MEM.findall(source)!=stage.MEM.findall(new):
                raise AssertionError("Inserted guest memory call")
            if stage.CALLS.findall(source)!=stage.CALLS.findall(new):
                raise AssertionError("Direct-call sequence changed")
            if stage.PUSHPOP.findall(source)!=stage.PUSHPOP.findall(new):
                raise AssertionError("Guest stack operation changed")
            if stage.ICALLS.findall(source)!=stage.ICALLS.findall(new):
                raise AssertionError("Guest indirect-call sequence changed")
            if nl=="\r\n" and new.count("\r\n")!=new.count("\n"):
                raise AssertionError("Lost CRLF line ending")
            must_reject(filename,new,"double instrumentation")
            must_reject(filename,source.replace(
                "PUSH32(esp, 0); sub_","PUSH32(esp, 0); sub_00",1
            ),"original call target drift")
            if filename=="translated_044.cpp":
                if new.count("K1R ICALL ")!=5:
                    raise AssertionError("Expected 5 raw indirect-call trace sites")
                for suffix in ("BEFORE_POP_ESI","BEFORE_POP_EDI","BEFORE_RET4"):
                    if new.count("K1R PATH A7B73_"+suffix)!=1:
                        raise AssertionError("Missing original conditional epilogue path")
                if new.count("K1R CALL 002A7B73_002A74A4_1")!=1 or new.count(
                    "K1R CALL 002A7B73_002A74A4_2"
                )!=1:
                    raise AssertionError("Repeated A74A4 source callsites not independent")
            if filename=="translated_005.cpp":
                if new.count("K1R CALL 002A6B98_002A7B73_1")!=1:
                    raise AssertionError("First A6B98 child not traced")
    assert sites_total==42 # 21 sites tested in both LF and CRLF
    print("[K1R] REAL-SOURCE PASS: 21 distinct call/path probes extracted from K1Q")
    print("[K1R] REAL-SOURCE PASS: A6B98 9 direct call edges; A7B73 4 direct, 5 indirect, 3 epilogues")
    print("[K1R] REAL-SOURCE PASS: original guest calls, memory accesses and PUSH/POP preserved")
    print("[K1R] REAL-SOURCE PASS: LF/CRLF and hostile source drift / duplicate probes rejected")
    print("[K1R] NO XDK build or Xbox run")


if __name__=="__main__":
    main()
