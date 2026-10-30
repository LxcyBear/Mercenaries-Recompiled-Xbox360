#!/usr/bin/env python3
"""Synthetic no-game regression for K1A DSOUND page-table index audit."""
from pathlib import Path
import importlib.util
p=Path(__file__).with_name("Audit-K1A-DsoundTableIndex.py")
spec=importlib.util.spec_from_file_location("merc_k1_ds_index",p)
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)
source="""/* P6DQ R59 FC4A ABI RESTORE: */
static void sub_002A6595(void)
{
loc_002A6607: ;
    ecx = phase6ch_apu_read32(ebp + -4);
    edx = phase6ch_apu_read32(ebp + -12);
    esi = ecx + edx * 8;
loc_002A6617: ;
    PHASE6DJ_ICALL_SAFE(phase6df_function_va, phase6ch_apu_read32(0x2DBE5C), _icall_esp);
loc_002A6624: ;
    phase6ch_apu_write32(esi + 4, phase6ch_apu_read32(esi + 4) & 0);
}
static void sub_002A0AE0(void)
{
loc_002A0AF1: ;
    sub_002A6595();
}
"""
s=module.analyze(source)
for x in ("signed_EDX=-38563368","024A8000","EFEE0EC0",
          "loc_002A6607","loc_002A6617","loc_002A6624",
          "sub_002A6595();","upstream","[EBP-12]"):
    assert x.lower() in s.lower(),x
for bad in (source.replace(module.MARKER,"NOT VERIFIED"),
            source.replace("esi = ecx + edx * 8;","esi = ecx + edx * 4;"),
            source.replace("sub_002A6595(void)","sub_002A9999(void)")):
    try:module.analyze(bad)
    except ValueError:pass
    else:raise AssertionError("K1A DSOUND audit accepted unverified/changed source")
print("[K1A-DSOUND] PASS: exact function, 8-byte stride, hardware arithmetic, upstream caller")
print("[K1A-DSOUND] PASS: fail closed on wrong watermark/changed instructions")
print("[K1A-DSOUND] No guest bytes, Xbox build or MMIO mappings were modified")
