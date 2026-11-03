#!/usr/bin/env python3
"""One-main-only XDK diagnostic for first real PRMDIO WRITE8 boundary.

It does not repair, emulate or permit this MMIO address. It observes the
actual byte at recomp_guest_write8's entry BEFORE the unchanged hard stop,
then captures the last tracked guest block VA (which is NOT necessarily the
precise x86 instruction address). No translated TU or header is changed.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

MARK = "P6K1NV2A-PRMDIO-WRITE8-20261103"
BOOT = "PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START"
K1C = "P6K1C-EXACT-WRITE-SITE-VA-20261030"
SIGNATURE = re.compile(
    r"(?m)^[ \t]*void[ \t]+recomp_guest_write8[ \t]*\([ \t]*"
    r"uint32_t[ \t]+address[ \t]*,[ \t]*uint8_t[ \t]+value[ \t]*"
    r"\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
PROBE = '''
    /* Observation ONLY. The original 8-bit guest write and MMIO fence follow. */
    if (address == 0xFD6813C8u)
    {
        char k1nv2aLine[360];
        sprintf(k1nv2aLine,
            "K1NV2A EXACT WRITE8: addr=%08X value=%02X last_guest_block_va=%08X esp=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X",
            (unsigned int)address, (unsigned int)value,
            (unsigned int)k1c_read_guest_va(), (unsigned int)g_esp,
            (unsigned int)eax, (unsigned int)ecx, (unsigned int)edx,
            (unsigned int)ebx, (unsigned int)esi, (unsigned int)edi);
        trace(k1nv2aLine);
    }
'''


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def patch(src: str) -> str:
    if MARK in src or "K1NV2A EXACT WRITE8:" in src:
        raise ValueError("Already instrumented; do not double-patch")
    if src.count(BOOT) != 1 or src.count(K1C) != 1:
        raise ValueError("Unexpected original K1C runtime boot identity")
    if "static DWORD k1c_read_guest_va(void);" not in src:
        raise ValueError("Missing proven last-guest-block-VA helper declaration")
    if src.count("return s_phase6cpCurrentVa;") != 1:
        raise ValueError("Missing original tracker reader; NO XDK")
    if "FAULT ACCESS IMMEDIATE:" not in src or "P6DQ ROCKET HARD STOP" not in src:
        raise ValueError("Original access-fault handler/hard stop missing")
    matches = list(SIGNATURE.finditer(src))
    if len(matches) != 1:
        raise ValueError("Expected exactly one central write8 body, found " + str(len(matches)))
    if "\r" in src.replace("\r\n", ""):
        raise ValueError("Unexpected non-CRLF line ending")
    nl = "\r\n" if "\r\n" in src else "\n"
    m = matches[0]
    injection = PROBE.replace("\n", nl)
    output = src[:m.end()] + injection + src[m.end():]
    output = output.replace(BOOT, BOOT + " | " + MARK, 1)
    if output.count(MARK) != 1 or output.count("K1NV2A EXACT WRITE8:") != 1:
        raise ValueError("Diagnostic source watermark/probe count drift")
    original = output.replace(BOOT + " | " + MARK, BOOT, 1)
    original = original.replace(injection, "", 1)
    if original != src:
        raise ValueError("Non-observational C++ source edit detected")
    return output


def selftest() -> None:
    f = '''static DWORD k1c_read_guest_va(void);
void recomp_guest_write8(uint32_t address, uint8_t value)
{
    if (address > 0x04000000u) { trace("FAULT ACCESS IMMEDIATE:"); }
    trace("P6DQ ROCKET HARD STOP");
}
static DWORD s_phase6cpCurrentVa = 0u;
static DWORD k1c_read_guest_va(void)
{
    return s_phase6cpCurrentVa;
}
void boot() { trace("PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START | P6K1C-EXACT-WRITE-SITE-VA-20261030"); }
'''
    for s in (f, f.replace("\n", "\r\n")):
        r = patch(s)
        assert r.count("K1NV2A EXACT WRITE8:") == 1
        assert r.index("K1NV2A EXACT WRITE8:") < r.index("FAULT ACCESS IMMEDIATE:")
        assert r.count("P6DQ ROCKET HARD STOP") == 1
        assert "if (address == 0xFD6813C8u)" in r
        assert "(unsigned int)value" in r
        try:
            patch(r)
        except ValueError:
            pass
        else:
            raise AssertionError("Double instrumentation accepted")
        try:
            patch(s.replace("return s_phase6cpCurrentVa;", "return 0u;"))
        except ValueError:
            pass
        else:
            raise AssertionError("Untracked guest-VA path accepted")
    print("[K1NV2A] SELFTEST PASS: CRLF/LF, unique write8 entry, exact value, unchanged hard stop, protected guest tracker")


def stage(args) -> None:
    source = args.main.resolve()
    out = args.out.resolve()
    if source == out or source.parent == out.parent:
        raise ValueError("Refusing to overwrite original native K1NT207 main")
    raw = source.read_bytes()
    new = patch(raw.decode("utf-8")).encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        if out.read_bytes() != new:
            raise ValueError("Existing K1NV2A output drift; refusing overwrite")
        print("[K1NV2A] REUSE PASS: output identical to verified new diagnostic")
    else:
        out.write_bytes(new)
    if source.read_bytes() != raw:
        raise ValueError("Original K1NT207 source changed during staging")
    meta = {
        "marker": MARK,
        "status": "MAIN_ONLY_DIAGNOSTIC_STAGED_NO_XDK",
        "source_main": str(source),
        "source_main_sha256": sha(raw),
        "new_main": str(out),
        "new_main_sha256": sha(new),
        "target": "WRITE8 FD6813C8",
        "candidate_gpu_block": "NV2A PRMDIO +0x3C8 (VGA DAC write-index candidate; unverified for Xbox)",
        "value_probe": "actual uint8_t value argument at central recomp_guest_write8 BEFORE hard-stop",
        "guest_va_probe": "last recorded guest basic-block VA (not guaranteed exact x86 instruction)",
        "translated_tus_changed": 0,
        "runtime_headers_changed": 0,
        "access_fences_changed": False,
        "unknown_nv2a_address_handled": False,
        "graphics_output_injected": False,
    }
    doc = (json.dumps(meta, indent=2) + "\n").encode("utf-8")
    if args.manifest.is_file():
        if args.manifest.read_bytes() != doc:
            raise ValueError("Existing K1NV2A manifest drift; refusing overwrite")
    else:
        args.manifest.parent.mkdir(parents=True, exist_ok=True)
        args.manifest.write_bytes(doc)
    print("[K1NV2A] STAGE PASS: exact write8 value + guest block VA logged BEFORE unchanged NV2A MMIO fence")
    print("[K1NV2A] 64 TrueTUs + runtime headers reused; ONLY new main.cpp differs")
    print("[K1NV2A] NO XDK / NO Xbox. No memory/register emulation or forced pixels.")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--main", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--manifest", type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    if not (a.main and a.out and a.manifest):
        p.error("--main, --out, and --manifest required")
    stage(a)


if __name__ == "__main__":
    main()
