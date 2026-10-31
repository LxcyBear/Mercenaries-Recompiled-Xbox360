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
    for modifier in ("", "static ", "__forceinline ",
                     "static __forceinline "):
        input_src=sample.replace("void sub_002D5574(void)",modifier+"void sub_002D5574(void)",1)
        normal=x.normalize_generated_header(input_src,x.TARGET)
        assert normal.startswith("void sub_002D5574(void)\n{")
        assert normal.partition("{")[2]==sample.partition("{")[2]
        adjusted,labels=x.source_prelude(input_src,x.TARGET,TinyBase)
        assert labels==1 and "PHASE4C_BUDGET_TICK(0x002D5574u)" in adjusted
        assert adjusted.startswith("void sub_002D5574(void)\n{")
    refused(x.normalize_generated_header,sample.replace(
        "void sub_002D5574(void)", "int sub_002D5574(void)",1),x.TARGET)
    refused(x.normalize_generated_header,sample.replace(
        "void sub_002D5574(void)", "void sub_002D5574(int)",1),x.TARGET)
    # Synthetic documentation prelude + exact semantic wrapper SHAPE.
    # This is not the game's proprietary original function body/bytes.
    bridge=(
        "\n/** synthetic test metadata, not retail source */\n"
        "void sub_002D5574(void)\n"
        "{\n"
        "    RECOMP_TRACE_FUNC(0x002D5574u);\n"
        "    recomp_xinput_init_devices();\n"
        "    esp += 12u;\n"
        "    return;\n"
        "}\n"
    )
    assert x.is_exact_xinput_bridge(bridge,x.TARGET,TinyBase)
    assert not x.is_exact_xinput_bridge(bridge.replace(
        "esp += 12u;","esp += 8u;"),x.TARGET,TinyBase)
    assert not x.is_exact_xinput_bridge(bridge,x.TARGET+5,TinyBase)
    normal_bridge=x.normalize_generated_header(bridge,x.TARGET)
    assert "synthetic test metadata" in normal_bridge
    assert "recomp_xinput_init_devices();" in normal_bridge
    xinput_instrumented,bridge_entries=x.source_prelude(bridge,x.TARGET,TinyBase)
    assert bridge_entries==1
    assert "PHASE4C_BUDGET_TICK(0x002D5574u)" in xinput_instrumented
    assert xinput_instrumented.count("XPP D5574 ENTRY")==1
    assert "recomp_xinput_init_devices();" in xinput_instrumented
    assert "esp += 12u;\n    return;" in xinput_instrumented
    refused(x.source_prelude,bridge.replace(
        "recomp_xinput_init_devices();","recomp_unsupported();"),x.TARGET,TinyBase)
    assert x.sha_bytes(bridge.encode("utf-8"))!=x.XINPUT_D5574_SOURCE_SHA256
    # Real native pad enumeration must live in exactly one owner TU and must
    # never be replaced by a no-op or fabricated connected mask.
    owner_test=x.HEADER+"\n\nvoid sub_0023A3CE(void)\n{\n}\n"
    bridge_owner=x.inject_xinput_bridge(owner_test,{"translated_000.cpp":owner_test})
    assert bridge_owner.count(x.XINPUT_BRIDGE_MARKER)==1
    assert bridge_owner.count("XInputGetState(")==1
    assert "for (port=0u; port<4u; ++port)" in bridge_owner
    assert "connected_mask|=(1u<<port)" in bridge_owner
    assert bridge_owner.count("static void recomp_xinput_init_devices(void)")==1
    assert "XPP D5574 ENTRY" not in bridge_owner
    assert x.HEADER in bridge_owner
    refused(x.inject_xinput_bridge,bridge_owner,{"translated_000.cpp":owner_test})
    prior_impl=owner_test+"\nvoid recomp_xinput_init_devices(void)\n{\n}\n"
    refused(x.inject_xinput_bridge,owner_test,{"translated_000.cpp":prior_impl})
    refused(x.inject_xinput_bridge,owner_test,{
        "translated_000.cpp":prior_impl.replace("\n","\r\n")})
    refused(x.inject_xinput_bridge,owner_test,{
        "translated_000.cpp":prior_impl.replace("(void)\n{","(void) {")})
    refused(x.inject_xinput_bridge,owner_test,{
        "translated_000.cpp":prior_impl.replace(
            "void recomp_xinput_init_devices", "static void recomp_xinput_init_devices")})
    prototype_only=owner_test+"\nvoid recomp_xinput_init_devices(void);\n"
    assert x.inject_xinput_bridge(owner_test,{
        "translated_000.cpp":prototype_only}).count(x.XINPUT_BRIDGE_MARKER)==1
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
    print("[XPP] SYNTHETIC PASS: native XDK 4-port input init, no duplicate definitions or synthetic devices")
    print("[XPP] SYNTHETIC PASS: no-label XInput bridge, exact stack cleanup, negative shape checks")
    print("[XPP] SYNTHETIC PASS: static/forceinline original header normalized, guest body preserved")
    print("[XPP] SYNTHETIC PASS: true direct caller, exact XPP entry and unchanged ret")
    print("[XPP] SYNTHETIC PASS: 64-TU owner placement, LF/CRLF, no duplicate compiled bodies")
    print("[XPP] SYNTHETIC PASS: absent label/trace/include fail closed")
    print("[XPP] SOURCE-ONLY — no XDK build, guest patches or fake display calls")

if __name__=="__main__":
    main()
