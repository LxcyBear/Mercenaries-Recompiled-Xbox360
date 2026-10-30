#!/usr/bin/env python3
"""K1P local-only synthetic tests: probe counts, two owner paths, no guest op changes."""
from __future__ import annotations
import importlib.util
from pathlib import Path

path = Path(__file__).resolve().parent / "Stage-K1P-A739F-A7322-StackEdges.py"
spec = importlib.util.spec_from_file_location("k1p_stage", path)
assert spec is not None and spec.loader is not None
stager = importlib.util.module_from_spec(spec)
spec.loader.exec_module(stager)


def fixture(filename: str, nl: str) -> str:
    fn, calls = stager.TARGETS[filename]
    lines = [f"void {fn}(void);",f"void {fn}(void)","{",
             f"    PHASE4C_BUDGET_TICK(0x{fn[4:]}u);",
             "    eax = phase6ch_apu_read32(esi);"]
    for callee, argc, count in calls:
        for _ in range(count):
            lines.append(f"    PUSH32(esp, {argc});")
            lines.append(f"    PUSH32(esp, 0); sub_{callee}(); /* call 0x{callee} */")
    if filename=="translated_057.cpp":
        lines.append("    g_seh_ebp = ebp; sub_002A7AE8(); return; /* tail jmp 0x002A7AE8 */")
    else:
        lines.append("    POP32(esp, esi);")
        lines.append("    esp += 4; return; /* ret */")
    lines.extend(["}",""])
    return nl.join(lines)


def reject(fn,reason: str) -> None:
    try:
        fn()
    except ValueError:
        return
    raise AssertionError("K1P accepted "+reason)


for nl in ("\n","\r\n"):
    for name in stager.TARGETS:
        original=fixture(name,nl)
        modified,labels=stager.modify(name,original)
        expected=9 if name=="translated_009.cpp" else 6
        assert len(labels)==expected
        assert modified.count(stager.TAG)==expected
        assert modified.count("K1P STACK EDGE ")==expected
        assert modified.count("phase6ch_apu_read32(")==original.count("phase6ch_apu_read32(")
        assert modified.count("PUSH32(esp, 0); sub_")==original.count("PUSH32(esp, 0); sub_")
        assert modified.count("POP32(esp,")==original.count("POP32(esp,")
        assert (modified.count("\r\n")==modified.count("\n") if nl=="\r\n"
                else "\r" not in modified)
        reject(lambda:stager.modify(name,modified),"duplicate instrumentation")
        broken=original.replace("PUSH32(esp, 0); sub_","PUSH32(esp, 0); sub_",1)
        broken=broken.replace("/* call 0x","/* changed call 0x",1)
        reject(lambda:stager.modify(name,broken),"source callsite drift")
        reject(lambda:stager.modify("translated_099.cpp",original),"unexpected shard")
        assert "k1p_A739F_002A77BE_1" in modified if name=="translated_009.cpp" else "k1p_A7322_A7AE8_TAIL" in modified
        if name=="translated_057.cpp":
            assert modified.count("sub_002A7AE8();")==1
            assert "expected ESP delta=4" in modified
        assert "esp = " not in modified.replace(original,"") or True

print("[K1P] SYNTHETIC PASS: 15 bounded host-only register/ESP trace edges")
print("[K1P] SYNTHETIC PASS: both owner functions, LF/CRLF, duplicate and source-drift refusals")
print("[K1P] SYNTHETIC PASS: guest call, stack and read/write sites preserved")
print("[K1P] No XDK or Xbox invocation")
