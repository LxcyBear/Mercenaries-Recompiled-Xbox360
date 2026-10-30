#!/usr/bin/env python3
"""K1D read-only XACTENG source extraction regression; no Xbox or game data."""
import hashlib
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory

path=Path(__file__).with_name("Inspect-K1D-XactWriteSite.py")
spec=importlib.util.spec_from_file_location("k1d",path)
m=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(m)

def reject(fn,why):
    try:fn()
    except ValueError:return
    raise AssertionError("K1D accepted drift: "+why)

with TemporaryDirectory(prefix="k1d-source-proof-") as temp:
    root=Path(temp)
    shards=root/"frozen-shards"
    shards.mkdir()
    main=root/"k1c"/"main.cpp"
    main.parent.mkdir()
    main.write_text(
        "/* "+m.K1C+" */\n"+
        ('trace("K1C WRITE SITE:");\n'*5),
        encoding="utf-8")
    runtime=shards/"translated_runtime.h"
    runtime.write_text("/* synthetic runtime header */\n")
    for n in range(64):
        path=shards/f"translated_{n:03d}.cpp"
        path.write_text("/* empty synthetic TU */\n")
    target=shards/"translated_026.cpp"
    target.write_text(
        "void sub_0027DB5C(void)\n{\n"
        "loc_0027DD0C: ;\n"
        "    PHASE4C_BUDGET_TICK(0x0027DD0Cu);\n"
        "    eax = ecx;\n"
        "    GUEST_WRITE32(ebx, eax);\n"
        "}\n")
    source_hash={f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                 for f in [main,runtime,*shards.glob("translated_*.cpp")]}
    report=m.inspect(main,shards)
    assert "loc_0027DD0C:" in report
    assert "GUEST_WRITE32(ebx, eax);" in report
    assert "translated_026.cpp:" in report
    assert "Exact label/tick candidates=2" in report
    assert "VA lexical hits=2" in report
    out=root/"reports"/"k1d-xact-site.txt"
    m.run(main,shards,out)
    assert out.read_text()==report
    assert source_hash=={f.name:hashlib.sha256(f.read_bytes()).hexdigest()
                         for f in [main,runtime,*shards.glob("translated_*.cpp")]}
    reject(lambda:m.run(main,shards,target),"source overwrite")
    main.write_text("/* WRONG */\n"+"K1C WRITE SITE:\n"*5)
    reject(lambda:m.inspect(main,shards),"K1C boot identity absent")
    main.write_text("/* "+m.K1C+" */\n"+"K1C WRITE SITE:\n"*5)
    (shards/"translated_063.cpp").unlink()
    reject(lambda:m.inspect(main,shards),"64 TrueTU identity")

print("[K1D-SOURCE] SYNTHETIC PASS: VA 0027DD0C label, tick, original store context")
print("[K1D-SOURCE] SYNTHETIC PASS: 64 TrueTUs, no original file mutation, fail closed")
print("[K1D-SOURCE] No XDK build and no game assets")
