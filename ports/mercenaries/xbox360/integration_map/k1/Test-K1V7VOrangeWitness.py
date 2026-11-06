#!/usr/bin/env python3
"""V7V synthetic fail-closed test: only three trace witnesses added."""
from __future__ import annotations
import importlib.util
from pathlib import Path
spec=importlib.util.spec_from_file_location(
    "v7v",Path(__file__).with_name("Stage-K1V7VOrangeWitness.py"))
assert spec and spec.loader
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
fixture="""/* K1-V7U-RETAIL-TLS-X86-PAIR-20261106 */
void sub_0022B150(void)
{
    RECOMP_TRACE_FUNC(0x0022B150u);
    const uint8_t selector = GUEST_READ8(0x24u);
}
void sub_0022B178(void)
{
    RECOMP_TRACE_FUNC(0x0022B178u);
    const uint8_t selector = GUEST_READ8(0x24u);
}
void run(void)
{
    trace("PASS: exact retail XBE data + Phase-2E TIB/TLS/stack environment active");
}
recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)
{
    switch(xbox_va){
      case 0x0022B150u: return sub_0022B150;
      case 0x0022B178u: return sub_0022B178;
    }
    trace("P6DQ ROCKET HARD STOP");
    trace("P6DQ ASYNC STREAM READ");
}
"""
res=m.patch(fixture)
assert res.count(m.MARK)==3
assert "TLS_GET_ENTER" in res and "TLS_SET_ENTER" in res and ' BOOT"' in res
assert res.count("case 0x0022B150u: return sub_0022B150;")==1
assert res.count("case 0x0022B178u: return sub_0022B178;")==1
for wrong in (fixture.replace("K1-V7U-RETAIL-TLS-X86-PAIR-20261106","no-v7u"),
              fixture.replace("    const uint8_t selector = GUEST_READ8(0x24u);",""),
              fixture.replace("    RECOMP_TRACE_FUNC(0x0022B150u);\n",""),
              fixture+fixture,
              res):
    try:m.patch(wrong)
    except ValueError:pass
    else:raise AssertionError("Fail-closed V7V stage accepted altered source")
print("[K1-V7V] SELFTEST PASS: one unique BOOT + TLS GET/SET first-entry witnesses")
print("[K1-V7V] Existing source and dispatch unchanged; NO XDK / NO XBOX")
