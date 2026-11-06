#!/usr/bin/env python3
"""V7U synthetic missing-body integration regression; no original retail bytes."""
from __future__ import annotations
import importlib.util
from pathlib import Path

spec=importlib.util.spec_from_file_location(
    "v7u",Path(__file__).with_name("Stage-K1V7URetailTlsPair.py"))
assert spec and spec.loader
v=importlib.util.module_from_spec(spec)
spec.loader.exec_module(v)
fixture="""uint32_t g_eflags, g_eax, g_ecx, g_esp;
#define GUEST_READ8(x) read8(x)
#define GUEST_READ32(x) read32(x)
#define GUEST_WRITE32(x,y) write32(x,y)
const char* untouched = "APC stream graphics native preserved";
recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va);
recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)
{
    if (xbox_va == 0x0027F2C2u) return some_other_function;
    return 0;
}
"""
new=v.patch(fixture)
assert new.startswith("/* "+v.MARK+" */\n")
assert v.NEW_GET in new and v.NEW_SET in new
assert new.count("static void sub_0022B150(void)")==1
assert new.count("static void sub_0022B178(void)")==1
assert new.count("if (xbox_va == 0x0022B150u) return sub_0022B150;")==1
assert new.count("if (xbox_va == 0x0022B178u) return sub_0022B178;")==1
assert "if (xbox_va == 0x0027F2C2u) return some_other_function;" in new
for va,delta in (("0022B150","4u"),("0022B178","8u")):
    body=v.fetch_func(new,"sub_"+va)
    assert "g_esp += "+delta in body
    assert "g_eflags = (oldflags & ~0x08D5u) | flags;" in body
    assert "GUEST_READ8(0x24u)" in body
    assert "if (selector < 2u) g_eax = GUEST_READ32(0x28u);" in body
for broken in (
    new,
    fixture+v.OLD_GET,
    fixture.replace(
      "recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{",
      "recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{\n"
      "    if (xbox_va == 0x0022B150u) return unknown_function;"),
    fixture+"recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{return 0;}\n",
):
    try:v.patch(broken)
    except ValueError:pass
    else:raise AssertionError("Duplicate/malformed source was not fenced")
print("[K1-V7U] SELFTEST PASS: V7I missing-body insertion, unique lookup, FS, flags, ret0/ret4 and hard fences")
print("[K1-V7U] NO ORIGINAL GAME SOURCE / NO XDK / NO XBOX")
