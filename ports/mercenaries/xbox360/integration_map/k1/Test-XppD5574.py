#!/usr/bin/env python3
"""Synthetic XPP direct-frontier staging gates, no game code or XDK."""
import importlib.util
from pathlib import Path

p=Path(__file__).with_name("Stage-XppD5574.py")
s=importlib.util.spec_from_file_location("xpp_d5574",p)
assert s and s.loader
x=importlib.util.module_from_spec(s)
s.loader.exec_module(x)

def refused(callback,*args):
    try:
        callback(*args)
    except ValueError:
        return
    raise AssertionError("Fail-closed source guard not triggered")

class TinyBase:
    @staticmethod
    def mask_noncode(t):
        import re
        return re.sub(r"/\*.*?\*/|//[^\n]*"," ",t,flags=re.S)

def main():
    assert x.TARGET==0x002D5574
    assert x.XPP_FIRST <= x.TARGET < x.XPP_END
    assert x.direct_calls(
        "void sub_002D5574(void) { /* sub_002D9999(); */ "
        "sub_002D4320(); sub_002D4320(); }",TinyBase
    )==["SUB_002D4320"] # definition with (void) is not a call
    sample=(
        "void sub_002D5574(void)\n"
        "{\n"
        "  RECOMP_TRACE_FUNC(0x002D5574u);\n"
        "loc_002D5574: ;\n"
        "  __debugbreak();\n"
        "  esp += 4; return; /* ret 0 */\n"
        "}\n"
    )
    body,count=x.source_prelude(sample,x.TARGET,TinyBase)
    assert count==1
    assert "XPP D5574 ENTRY" in body
    assert "PHASE4C_BUDGET_TICK(0x002D5574u)" in body
    assert "__debugbreak()" not in body
    assert "PHASE4C_DEBUGBREAK()" in body
    assert "esp += 4; return; /* ret 0 */" in body
    refused(x.source_prelude,sample.replace(
        "loc_002D5574: ;","loc_002D5575: ;"),x.TARGET,TinyBase)
    refused(x.source_prelude,sample.replace(
        "RECOMP_TRACE_FUNC(0x002D5574u);",""),x.TARGET,TinyBase)
    for nl in ("\n","\r\n"):
        src=(x.HEADER+"\n"+
             "void sub_0023A3CE(void)\n{\n"
             "    "+x.FENCE+" /* call 0x002D5574 */\n}\n").replace("\n",nl)
        update,edges=x.patch_direct(src,[x.NAME],True)
        assert edges==1
        assert x.CALL+" /* call 0x002D5574 */" in update
        assert update.count(x.PROTOTYPE)==1
        assert x.FENCE not in update
        no_call,zero=x.patch_direct(src.replace(
            x.FENCE,"phase4c_direct_frontier(0x002D5570u);"),
            [x.NAME],True)
        assert zero==0 and no_call!=update
        refused(x.patch_direct,src.replace(x.HEADER,""),
                [x.NAME],True)
        nohost=("P6DQ-R51-MM173-FRAME-20261029-A"+nl+
                "void function() {}"+nl)
        unchanged,none=x.patch_host(nohost)
        assert unchanged==nohost and none==0
        host,nh=x.patch_host(nohost+x.FENCE+nl)
        assert nh==1 and x.CALL in host and x.PROTOTYPE in host
        assert "P6DQ-R51-MM173-FRAME-20261029-A" in host
        defs=x.compiled_defs({"translated_002.cpp":src})
        assert defs["SUB_0023A3CE"][0]=="translated_002.cpp"
        refused(x.compiled_defs,{"translated_002.cpp":src,
                "translated_003.cpp":src})
        owner=x.add_guest_bodies(src,{x.TARGET:sample},TinyBase,defs,
                                 "translated_002.cpp")
        assert owner.count("XPP D5574 ENTRY")==1
        assert owner.count("void sub_002D5574(void)")==2 # prototype and body
        assert owner.count(x.HEADER)==1
        # No old hard fence relaxed, and no synthetic display call.
        assert "display_calls" not in owner
        assert "phase6dq_note_vp_unknown_read" not in owner
    print("[XPP] SYNTHETIC PASS: true direct caller, exact XPP entry and unchanged ret")
    print("[XPP] SYNTHETIC PASS: 64-TU owner placement, LF/CRLF, no duplicate compiled bodies")
    print("[XPP] SYNTHETIC PASS: absent label/trace/include fail closed")
    print("[XPP] SOURCE-ONLY — no XDK build, guest patches or fake display calls")

if __name__=="__main__":
    main()
