#!/usr/bin/env python3
"""Synthetic source-contract tests for the pixel APU frontier; no XDK."""
from __future__ import annotations
import importlib.util
import json
import tempfile
from pathlib import Path

script=Path(__file__).with_name("Probe-PixelApuContracts.py")
spec=importlib.util.spec_from_file_location("pixel_apu_probe",script)
assert spec and spec.loader
probe=importlib.util.module_from_spec(spec)
spec.loader.exec_module(probe)

code="""void sub_002A3A5A(void)
{
    uint32_t x = recomp_apu_read32(eax);
    recomp_apu_write32(edi,x);
    sub_002A3B22(); /* call 0x002A3B22 */
}
"""
assert probe.read_definition(code,"sub_002A3A5A")[0].strip()==code.strip()
assert probe.read_definition(code,"sub_002A3B22") is None
assert probe.read_definition("void sub_002A3A5A(void);","sub_002A3A5A") is None
assert len(probe.excerpts(code,"recomp_apu_read32"))==1
assert "recomp_apu_read32" not in probe.mask_noncode(
    "// recomp_apu_read32(eax);\n/* recomp_apu_read32(x); */")
assert probe.read_definition("""static uint32_t phase6ch_apu_read32(uint32_t address)
{
    return GUEST_READ32(address);
}
""","phase6ch_apu_read32") is not None

with tempfile.TemporaryDirectory(prefix="pixel_apu_") as td:
    root=Path(td)
    gen=root/"gen";gen.mkdir()
    (gen/"recomp_synthetic.c").write_text(code,encoding="utf-8")
    main=root/"main.cpp"
    main.write_text("static uint32_t phase6ch_apu_read32(uint32_t a)\n{\n return a;\n}\n",
                    encoding="utf-8")
    runtime=root/"translated_runtime.h"
    runtime.write_text("static void phase6ch_apu_write32(uint32_t a,uint32_t b)\n{\n GUEST_WRITE32(a,b);\n}\n",encoding="utf-8")
    plan=root/"plan.json"
    plan.write_text(json.dumps({
        "marker":"PIXEL-BATCH-ROOTED-CLOSURE-20261030",
        "intent":"AUTHENTIC_GUEST_DISPLAY_CALL_ONLY",
        "hardware_seed":{"first_unhandled_direct_target":"0x002A3A5A"},
        "verified_baseline":{"marker":"K1S-HALGETVECTOR44-SAVED-ESI-20261030"},
        "frontier":{"va":"0x002A3A5A","classification":"EXACT_GENERATED_FUNCTION",
                    "source_file":"recomp_synthetic.c"},
        "candidate_order":[{"va":"0x002A3A5A","status":"REQUIRES_SUPPORT"},
                           {"va":"0x0023AAA0","status":"NO_ORIGINAL_GENERATED_BODY"}]
    }),encoding="utf-8")
    import argparse
    args=argparse.Namespace(plan=plan,generated_root=gen,main=main,runtime=runtime)
    result=probe.report(args)
    assert "original function=sub_002A3A5A" in result
    assert "recomp_apu_read32: 1 callsites" in result
    assert "recomp_apu_write32: 1 callsites" in result
    assert "phase6ch_apu_read32" in result
    assert "phase6ch_apu_write32" in result
    assert "Guest display_calls=0" in result
    assert "NO XDK BUILD." in result
    assert "A candidate count of 4" in result
    args.plan.write_text("{}",encoding="utf-8")
    try:
        probe.report(args)
        raise AssertionError("Stale/fake planning report accepted")
    except ValueError:
        pass
print("[PIXEL-BRIDGE] SYNTHETIC PASS: exact original generated body and APU helper signatures")
print("[PIXEL-BRIDGE] SYNTHETIC PASS: bounded trace, root/report and stale plan refusal")
print("[PIXEL-BRIDGE] NO guest mutations; NO Xbox build")
