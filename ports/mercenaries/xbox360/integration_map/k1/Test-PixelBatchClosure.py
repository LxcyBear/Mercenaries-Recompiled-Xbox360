#!/usr/bin/env python3
"""No-XDK tests of source-rooted batch selection and negative cases."""
from __future__ import annotations
import importlib.util
from pathlib import Path

path=Path(__file__).with_name("Audit-PixelBatchClosure.py")
spec=importlib.util.spec_from_file_location("pixel_batch_audit",path)
assert spec is not None and spec.loader is not None
tool=importlib.util.module_from_spec(spec)
spec.loader.exec_module(tool)

def row(name:str,calls:list[int])->dict:
    body="\n".join("  PUSH32(esp, 0); sub_%08X(); /* call 0x%08X */"%(c,c)
                   for c in calls)
    return {"name":name,"source":"void "+name+"(void)\n{\n"+body+"\n}",
            "file":"recomp_test.c"}

source="PUSH32(esp, 0); sub_002A3A5A(); /* call 0x002A3A5A */"
assert tool.parse_targets(source)==[0x002A3A5A]
assert tool.parse_targets("sub_002A3A5A(); sub_002A3A5A();")==[0x002A3A5A]
assert tool.parse_targets("PHASE6DJ_ICALL_SAFE(esp);")==[]
assert tool.parse_targets("/* call 0x002A3A5A */")==[0x002A3A5A]
generated={
    0x002A3A5A:row("sub_002A3A5A",[0x002A3B00,0x002A3C00]),
    0x002A3B00:row("sub_002A3B00",[0x002A3D00]),
    0x002A3C00:row("sub_002A3C00",[]),
    0x002A3D00:row("sub_002A3D00",[]),
}
walk=tool.breadth_first(0x002A3A5A,10,generated,set())
assert walk=={
    0x002A3A5A:0,0x002A3B00:1,0x002A3C00:1,0x002A3D00:2}
assert len(tool.breadth_first(0x002A3A5A,2,generated,set()))==2
assert tool.breadth_first(0x11111111,2,generated,set())=={0x11111111:0}
ranges={0x002A3000:{"start":0x002A3000,"end":0x002A4000,"name":"sub_002A3000"}}
assert tool.find_enclosing(0x002A3A5A,[0x002A3000],ranges)==ranges[0x002A3000]
assert tool.find_enclosing(0x002A4000,[0x002A3000],ranges) is None
assert tool.find_enclosing(0x00111111,[0x002A3000],ranges) is None
assert tool.MARKER.startswith("PIXEL-BATCH")
assert tool.LIVE==0x002A3A5A
assert len({name for name,va,budget in tool.ROOTS})==len(tool.ROOTS)
print("[PIXEL] SYNTHETIC PASS: nested direct call closure and byte-exact live frontier")
print("[PIXEL] SYNTHETIC PASS: budget, missing bodies, mid-function range boundaries")
print("[PIXEL] SYNTHETIC PASS: indirect target not invented as a direct call")
print("[PIXEL] SOURCE-ONLY; NO XDK build, no guest patch or MMIO change")
