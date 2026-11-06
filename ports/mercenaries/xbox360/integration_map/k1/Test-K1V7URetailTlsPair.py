#!/usr/bin/env python3
"""V7U regression for actual V7I maintained Get/SetLastError function layout."""
from __future__ import annotations
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location(
    "stage_v7u",Path(__file__).with_name("Stage-K1V7URetailTlsPair.py"))
assert spec and spec.loader
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)

fixture="""uint32_t g_eflags, g_eax, g_ecx, g_esp;
#define GUEST_READ8(x) read8(x)
#define GUEST_READ32(x) read32(x)
#define GUEST_WRITE32(x,y) write32(x,y)
#define RECOMP_TRACE_FUNC(x) do_trace(x)
const char* untouched = "APC stream graphics native preserved";
""" + v.OLD_GET + "\n\n" + v.OLD_SET + """
recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)
{
    switch(xbox_va) {
    case 0x0022B150u: return sub_0022B150;
    case 0x0022B178u: return sub_0022B178;
    case 0x0022F51Cu: return sub_0022F51C;
    }
    return 0;
}
"""
after=v.patch(fixture)
assert after.startswith("/* "+v.MARK+" */\n")
assert v.NEW_GET in after and v.NEW_SET in after
assert v.OLD_GET not in after and v.OLD_SET not in after
assert after.replace("/* "+v.MARK+" */\n","",1).replace(
    v.NEW_GET,v.OLD_GET,1).replace(v.NEW_SET,v.OLD_SET,1)==fixture
for addr,advance in (("0022B150","4u"),("0022B178","8u")):
    body=v.fetch_func(after,"sub_"+addr)
    assert "g_esp += "+advance in body
    assert "g_eflags = (oldflags & ~0x08D5u) | flags;" in body
    assert "RECOMP_TRACE_FUNC(0x"+addr+"u);" in body
    assert "GUEST_READ8(0x24u)" in body
    assert "if (selector < 2u) g_eax = GUEST_READ32(0x28u);" in body
    assert after.count("case 0x"+addr+"u: return sub_"+addr+";")==1
assert after.count("APC stream graphics native preserved")==1
assert after.count("case 0x0022F51Cu: return sub_0022F51C;")==1

for broken in (
    after,
    fixture+v.OLD_GET,
    fixture.replace("g_eax = s_phase4cLastError;","g_eax = 123u;"),
    fixture.replace("case 0x0022B150u: return sub_0022B150;",
                    "case 0x0022B150u: return unknown_function;"),
    fixture.replace("case 0x0022B150u: return sub_0022B150;",
                    "case 0x0022B150u: return sub_0022B150;\n"
                    "    case 0x0022B150u: return sub_0022B150;"),
):
    try:v.patch(broken)
    except ValueError:pass
    else:raise AssertionError("V7U must reject changed/duplicate original TLS layout")
print("[K1-V7U] SELFTEST PASS: exact maintained V7I bodies replaced, original routes/other functions preserved")
print("[K1-V7U] FS24/FS28, flags, EAX/ECX, stack ret0/ret4 checks PASS; NO XDK / NO XBOX")
