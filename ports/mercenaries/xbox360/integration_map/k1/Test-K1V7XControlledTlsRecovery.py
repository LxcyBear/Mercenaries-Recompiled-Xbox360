#!/usr/bin/env python3
"""V7X synthetic exactness and reject-on-drift tests."""
from __future__ import annotations
import importlib.util
from pathlib import Path
base=Path(__file__).parent
def load(name,path):
    s=importlib.util.spec_from_file_location(name,base/path)
    assert s and s.loader
    m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
    return m
u=load("v7u","Stage-K1V7URetailTlsPair.py")
x=load("v7x","Stage-K1V7XControlledTlsRecovery.py")
baseline="""void sub_0022B150(void)
{
    __PLACEHOLDER_GET__
}
void sub_0022B178(void)
{
    __PLACEHOLDER_SET__
}
void launch(void)
{
    trace("PASS: exact retail XBE data + Phase-2E TIB/TLS/stack environment active");
}
"""
baseline=baseline.replace("void sub_0022B150(void)\n{\n    __PLACEHOLDER_GET__\n}",u.OLD_GET)
baseline=baseline.replace("void sub_0022B178(void)\n{\n    __PLACEHOLDER_SET__\n}",u.OLD_SET)
retail="/* "+u.MARK+" */\n"+baseline.replace(u.OLD_GET,u.NEW_GET).replace(u.OLD_SET,u.NEW_SET)
stamped=x.patch(retail,u,baseline)
assert stamped.replace('\n    trace("'+x.MARK+' BOOT");',"")==baseline
for bad in (retail.replace("GUEST_READ8(0x24u)","GUEST_READ8(0x25u)",1),
            retail.replace("/* "+u.MARK+" */\n","",1),
            retail.replace("trace(","TRACE(",1),
            retail.replace(u.NEW_SET,"",1)):
    try:x.patch(bad,u,baseline)
    except ValueError:pass
    else:raise AssertionError("V7X accepted drift")
print("[K1-V7X] SELFTEST PASS: exact byte-for-byte V7I reconstruction plus unique marker")
print("[K1-V7X] Missing, mutated, or non-TLS V7U source mutations HARD FENCE")
