#!/usr/bin/env python3
"""V7U source-only patcher selftest (no original retail game data)."""
from __future__ import annotations
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location("stage_v7u",Path(__file__).with_name("Stage-K1V7URetailTlsPair.py"))
assert spec and spec.loader
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
fixture="""uint32_t g_eflags, g_eax, g_ecx, g_esp;
#define GUEST_READ8(x) read8(x)
#define GUEST_READ32(x) read32(x)
#define GUEST_WRITE32(x,y) write32(x,y)
const char* untouched = "APC stream graphics native preserved";
""" + v.OLD_GET + "\n" + v.OLD_SET + """
recomp_func_t phase4c_lookup_pack_func(uint32_t va)
{
switch(va) {
  case 0x0022B150u: return sub_0022B150;
  case 0x0022B178u: return sub_0022B178;
}
return 0;
}
"""
patch=v.patch(fixture)
assert patch.startswith("/* "+v.MARK+" */\n")
assert v.NEW_GET in patch and v.NEW_SET in patch
assert v.OLD_GET not in patch and v.OLD_SET not in patch
assert patch.replace("/* "+v.MARK+" */\n","",1).replace(v.NEW_GET,v.OLD_GET,1).replace(v.NEW_SET,v.OLD_SET,1)==fixture
for target,advance in (("0022B150","4u"),("0022B178","8u")):
    body=v.fetch_func(patch,"sub_"+target)
    assert "g_esp += "+advance in body
    assert "g_eflags = (oldflags & ~0x08D5u) | flags;" in body
    assert "GUEST_READ8(0x24u)" in body
    assert "if (selector < 2u) g_eax = GUEST_READ32(0x28u);" in body
assert patch.count("APC stream graphics native preserved")==1
assert patch.count("case 0x0022B150u: return sub_0022B150;")==1
assert patch.count("case 0x0022B178u: return sub_0022B178;")==1
for malformed in (fixture.replace("0x0022B150u: return sub_0022B150;","0x0022B150u: return missing;"),
                  fixture+v.OLD_GET,
                  fixture.replace("g_esp += 4u;", "g_esp += 16u;")):
    try:v.patch(malformed)
    except ValueError:pass
    else:raise AssertionError("Malformed source was not fenced")
print("[K1-V7U] SELFTEST PASS: exactly two TLS bodies, ret0/ret4 stack delta, FS24/FS28, EFLAGS, dispatch, guards")
print("[K1-V7U] SOURCE-ONLY TEST; no original retail bytes, no XDK or Xbox")
