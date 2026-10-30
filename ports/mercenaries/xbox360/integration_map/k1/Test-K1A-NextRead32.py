#!/usr/bin/env python3
"""Synthetic regression for read-only K1A hardware-fault source investigator."""
import importlib.util
from pathlib import Path
p=Path(__file__).with_name("Investigate-K1A-NextRead32.py")
spec=importlib.util.spec_from_file_location("merc_k1_nextread",p)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)
source="""/* P6DQ R59 FC4A ABI RESTORE: */
static void sub_002A6600(void)
{
loc_002A6607: ;
    esi = GUEST_READ32(edi + 8);
loc_002A6617: ;
    PHASE4C_BUDGET_TICK(0x002A6617u);
loc_002A6624: ;
    eax = GUEST_READ32(esi + 4);
}
"""
result=m.analyze(source)
assert "VA 002A6624 line" in result
assert "GUEST_READ32(esi + 4)" in result
assert "esi = GUEST_READ32(edi + 8)" in result
assert "EFEE0EC4 remains" not in result  # never claim runtime repaired
assert "NOT YET PROVEN" in result
for bad in (source.replace(m.R59_IDENTITY,"X"),""):
    try:m.analyze(bad)
    except ValueError:pass
    else:raise AssertionError("accepted source without exact original identity")
print("[K1A-READ32] PASS: synthetic source VA, ESI ancestry, data boundaries and identity refusal")
print("[K1A-READ32] NO guest bytes modified, NO Xbox build")
