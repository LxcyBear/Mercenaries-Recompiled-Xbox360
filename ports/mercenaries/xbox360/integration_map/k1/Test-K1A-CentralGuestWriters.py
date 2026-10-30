#!/usr/bin/env python3
"""Synthetic regression for exact K1A central write-site source context.

This test contains no retail game bytes and performs no XDK build.
"""
from pathlib import Path
import importlib.util
import tempfile

file=Path(__file__).with_name("Inspect-K1A-CentralGuestWriters.py")
spec=importlib.util.spec_from_file_location("k1a_central_write",file)
mod=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(mod)

def expect_error(fn,label):
    try:fn()
    except ValueError:pass
    else:raise AssertionError("accepted invalid source: "+label)

with tempfile.TemporaryDirectory(prefix="k1a-write-sites-") as tmp:
    root=Path(tmp)
    main=root/"main.cpp"
    folder=root/"translated_shards"
    folder.mkdir()
    main.write_text(
        "// "+mod.CLOCK+"\n"
        "static void recomp_guest_write32(uint32_t address,uint32_t value)\n"
        "{\n  // a synthetic body, not the real Xbox guest write router\n}\n"
        "#define GUEST_WRITE32(a,b) recomp_guest_write32((a),(b))\n"
        "GUEST_WRITE32(1,2);\n"
        +("// "+mod.WATCH+"\n")*3,
        encoding="utf-8")
    header=folder/"translated_runtime.h"
    header.write_text(
        "#define GUEST_WRITE16(a,b) recomp_guest_write16((a),(b))\n"
        "static inline void phase6ch_apu_write32(uint32_t address,uint32_t value)\n"
        "{\n  GUEST_WRITE32(address,value);\n}\n",encoding="utf-8")
    for i in range(64):
        text=f"/* synthetic translated shard {i} */\n"
        if i==4:text+="loc_00041D70: ;\nGUEST_WRITE32(eax,edx);\n"
        if i==26:text+="if (ecx == 0x00041D70u) goto loc_0029A100;\n"
        (folder/f"translated_{i:03d}.cpp").write_text(text,encoding="utf-8")
    before={p.name:p.read_bytes() for p in folder.iterdir()}
    actual=mod.analyze(main,folder)
    assert "translated_004.cpp:2" in actual
    assert "translated_026.cpp:2" in actual
    assert "Total literal references = 2" in actual
    assert "GUEST_WRITE32" in actual
    assert "recomp_guest_write32" in actual
    assert "Source hashes" not in actual
    assert before=={p.name:p.read_bytes() for p in folder.iterdir()}
    # No mutated guest code and fail-closed on partial 64-TU sets.
    (folder/"translated_063.cpp").unlink()
    expect_error(lambda:mod.analyze(main,folder),"missing shard")
    (folder/"translated_063.cpp").write_text("/* fixture */")
    main.write_text("no clock boot marker")
    expect_error(lambda:mod.analyze(main,folder),"missing clock identity")
    main.write_text("// "+mod.CLOCK+"\n")
    expect_error(lambda:mod.analyze(main,folder),"missing writer watch stage")
print("[K1A-WRITESITE] PASS: two literal source sites, central macro/helper contexts")
print("[K1A-WRITESITE] PASS: 64 TrueTU source identity, no source edits, fail-closed")
print("[K1A-WRITESITE] No retail XBE data and no Xbox build")
