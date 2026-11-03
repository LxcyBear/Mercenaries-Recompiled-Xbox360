#!/usr/bin/env python3
"""Stage a bounded NV2A PRMDIO DAC palette write-index/data handler.

Original Xbox retail XBE disassembly has now proven the exact x86 store:
0028ED54 mov byte ptr [ecx + 0x6813c8], 0
and the subsequent 0x6813C9 RGB streaming instructions.
Parent: previously hardware-proven K1NV2A main-only diagnostic.
ONE additional main-only C++ edit. No TU/header changes, no other MMIO.
This is an indexed DAC register shadow; it does NOT render or present pixels.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

PARENT = "P6K1NV2A-PRMDIO-WRITE8-20261103"
MARK = "P6K1NV2A-DAC-PALETTE-20261103"
PROBE = "K1NV2A EXACT WRITE8:"
# Reuse the exact supported multiline signature accepted by the previously
# hardware-proven K1NV2A probe stage. One declared function is required.
WRITE8_SIGNATURE = re.compile(
    r"(?m)^[ \t]*void[ \t]+recomp_guest_write8[ \t]*\(\s*"
    r"uint32_t[ \t]+address[ \t]*,\s*uint8_t[ \t]+value\s*"
    r"\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
ANCHOR = "        trace(k1nv2aLine);\n    }\n"
# Insert after the hardware-proven diagnostic, before the original generic
# write8 MMIO fence. Index must precede data. Shadow stores raw 8-bit RGB,
# since DAC bit depth / palette presentation is not established for this game.
HANDLER = '''
    /* K1NV2A: Xbox PRMDIO DAC palette register pair ONLY.
     * Retail XBE 0028ED54: mov byte ptr [ecx+6813C8],0.
     * Retail 0028ED77/7F/8C: streaming byte writes to +6813C9.
     * No palette -> Xenos display translation is claimed or performed.
     * Unknown/uninitialized MMIO still enters the ORIGINAL hard fence.
     */
    /* Volatile preserves real guest palette writes even under Release LTO. */
    static volatile uint8_t k1DacPalette[256][3] = {{0}};
    static uint8_t k1DacStagingRGB[3] = {0};
    static uint8_t k1DacWriteIndex = 0u;
    static uint8_t k1DacSubIndex = 0u;
    static bool k1DacWriteArmed = false;
    static unsigned int k1DacIndexWrites = 0u;
    static unsigned int k1DacDataWrites = 0u;
    static unsigned int k1DacPaletteCommits = 0u;
    if (address == 0xFD6813C8u)
    {
        k1DacWriteIndex = value;
        k1DacSubIndex = 0u;
        k1DacWriteArmed = true;
        ++k1DacIndexWrites;
        char k1DacStartLine[220];
        sprintf(k1DacStartLine,
            "K1NV2A DAC WRITE INDEX: index=%u count=%u guest_block=%08X",
            (unsigned int)k1DacWriteIndex, k1DacIndexWrites,
            (unsigned int)k1c_read_guest_va());
        trace(k1DacStartLine);
        return;
    }
    if (address == 0xFD6813C9u && k1DacWriteArmed)
    {
        k1DacStagingRGB[k1DacSubIndex] = value;
        ++k1DacSubIndex;
        ++k1DacDataWrites;
        if (k1DacSubIndex == 3u)
        {
            const uint8_t k1DacCompletedIndex = k1DacWriteIndex;
            k1DacPalette[k1DacCompletedIndex][0] = k1DacStagingRGB[0];
            k1DacPalette[k1DacCompletedIndex][1] = k1DacStagingRGB[1];
            k1DacPalette[k1DacCompletedIndex][2] = k1DacStagingRGB[2];
            k1DacWriteIndex = (uint8_t)(k1DacWriteIndex + 1u);
            k1DacSubIndex = 0u;
            ++k1DacPaletteCommits;
            /* First entry and every 64th: observability without 768 logs. */
            if (k1DacPaletteCommits == 1u ||
                (k1DacPaletteCommits & 63u) == 0u)
            {
                char k1DacProgress[280];
                sprintf(k1DacProgress,
                    "K1NV2A DAC PALETTE COMMIT: entries=%u bytes=%u last_index=%u rgb=%02X,%02X,%02X next_index=%u guest_block=%08X",
                    k1DacPaletteCommits, k1DacDataWrites,
                    (unsigned int)k1DacCompletedIndex,
                    (unsigned int)k1DacStagingRGB[0],
                    (unsigned int)k1DacStagingRGB[1],
                    (unsigned int)k1DacStagingRGB[2],
                    (unsigned int)k1DacWriteIndex,
                    (unsigned int)k1c_read_guest_va());
                trace(k1DacProgress);
            }
        }
        return;
    }
'''


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def patch(text: str) -> str:
    if MARK in text or "K1NV2A DAC PALETTE COMMIT:" in text:
        raise ValueError("Already staged DAC palette patch; refusing duplicate")
    if text.count(PARENT) != 1 or text.count(PROBE) != 1:
        raise ValueError("Missing unique hardware-proven PRMDIO parent/probe")
    matches = list(WRITE8_SIGNATURE.finditer(text))
    if len(matches) != 1:
        raise ValueError(
            "Expected exactly one central multiline guest WRITE8 definition, "
            f"found {len(matches)}"
        )
    if "static DWORD k1c_read_guest_va(void);" not in text:
        raise ValueError("Missing guest basic-block tracking function")
    if "FAULT ACCESS IMMEDIATE:" not in text or "P6DQ ROCKET HARD STOP" not in text:
        raise ValueError("Original MMIO hard fence absent")
    if "\r" in text.replace("\r\n", ""):
        raise ValueError("Unexpected mixed line endings")
    nl = "\r\n" if "\r\n" in text else "\n"
    source_anchor = ANCHOR.replace("\n", nl)
    if text.count(source_anchor) != 1:
        raise ValueError("Exact original diagnostic insertion anchor drift")
    # The diagnostic was inserted immediately after the WRITE8 opening brace.
    # Do not latch onto an unrelated trace(k1nv2aLine) or a second function.
    anchor_at = text.index(source_anchor)
    if not (matches[0].end() < anchor_at < matches[0].end() + 1400):
        raise ValueError("Diagnostic anchor is not within central WRITE8 preamble")
    handler = HANDLER.replace("\n", nl)
    new = text.replace(source_anchor, source_anchor + handler, 1)
    new = new.replace(PARENT, PARENT + " | " + MARK, 1)
    # Exact reversal proves no other inherited code/headers/palette paths changed.
    back = new.replace(source_anchor + handler, source_anchor, 1)
    back = back.replace(PARENT + " | " + MARK, PARENT, 1)
    if back != text:
        raise ValueError("Unrelated original runtime changes detected")
    if new.count(MARK) != 1 or new.count("K1NV2A DAC PALETTE COMMIT:") != 1:
        raise ValueError("New runtime tag/probe count drift")
    if any(key not in new for key in (
        "if (address == 0xFD6813C8u)",
        "if (address == 0xFD6813C9u && k1DacWriteArmed)",
        "k1DacPalette[k1DacCompletedIndex][2] = k1DacStagingRGB[2];",
        "k1DacWriteIndex = (uint8_t)(k1DacWriteIndex + 1u);",
        "P6DQ ROCKET HARD STOP",
    )):
        raise ValueError("One of the mandatory bounded DAC state transitions is missing")
    return new


class DacReference:
    """Test oracle for documented VGA 0x3C8/0x3C9 indexed RGB protocol."""

    def __init__(self):
        self.palette = [[0, 0, 0] for _ in range(256)]
        self.index = 0
        self.staged = [0, 0, 0]
        self.component = 0
        self.armed = False
        self.commits = 0
        self.data = 0

    def write8(self, address: int, value: int):
        if not (0 <= value <= 255):
            raise ValueError("Must be one byte")
        if address == 0xFD6813C8:
            self.index = value
            self.component = 0
            self.armed = True
            return
        if address != 0xFD6813C9 or not self.armed:
            raise ValueError("ORIGINAL HARD FENCE: unsupported or unarmed MMIO")
        self.staged[self.component] = value
        self.component += 1
        self.data += 1
        if self.component == 3:
            self.palette[self.index] = self.staged.copy()
            self.index = (self.index + 1) & 0xFF
            self.component = 0
            self.commits += 1


def selftest():
    original = """static DWORD k1c_read_guest_va(void);
void recomp_guest_write8(uint32_t address, uint8_t value)
{
    if (address == 0xFD6813C8u)
    {
        char k1nv2aLine[360];
        sprintf(k1nv2aLine, "K1NV2A EXACT WRITE8: addr=%08X", (unsigned int)address);
        trace(k1nv2aLine);
    }
    if (address > 0x04000000u) trace("FAULT ACCESS IMMEDIATE:");
    trace("P6DQ ROCKET HARD STOP");
}
void boot() { trace("P6K1NV2A-PRMDIO-WRITE8-20261103"); }
"""
    for old in (original, original.replace("\n", "\r\n")):
        new = patch(old)
        assert new.count("K1NV2A DAC PALETTE COMMIT:") == 1
        assert new.index("K1NV2A EXACT WRITE8:") < new.index("K1NV2A DAC WRITE INDEX:")
        assert new.index("K1NV2A DAC PALETTE COMMIT:") < new.index("FAULT ACCESS IMMEDIATE:")
        assert new.count("P6DQ ROCKET HARD STOP") == 1
        for invalid in (new, old.replace("P6DQ ROCKET HARD STOP", "NO FENCE")):
            try:
                patch(invalid)
                raise AssertionError("Accepted duplicate or unsafe parent")
            except ValueError:
                pass
    # Match the real source generator's multiline entry declaration.
    multiline = original.replace(
        "void recomp_guest_write8(uint32_t address, uint8_t value)\n{",
        "void recomp_guest_write8(\n    uint32_t address, uint8_t value)\n{",
    )
    # Also ensure varying whitespace cannot cause a false declaration count.
    assert patch(multiline).count("K1NV2A DAC PALETTE COMMIT:") == 1
    for bad in (
        original.replace("void recomp_guest_write8", "void another_write8"),
        original.replace("void recomp_guest_write8", "void recomp_guest_write8(")
    ):
        try:
            patch(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid WRITE8 signature accepted")
    s = DacReference()
    for invalid_addr in (0xFD6813C9, 0xFD6813CA, 0xFD6813C7, 0xFD6813D0, 0xFE820010):
        try:
            s.write8(invalid_addr, 0)
            raise AssertionError(f"Unarmed or unsupported MMIO accepted {invalid_addr:08X}")
        except ValueError:
            pass
    s.write8(0xFD6813C8, 0)
    for n in range(256):
        for channel in range(3):
            s.write8(0xFD6813C9, (n + channel * 37) & 0xFF)
    assert s.commits == 256 and s.data == 768 and s.index == 0
    for n in range(256):
        assert s.palette[n] == [n, (n + 37) & 0xFF, (n + 74) & 0xFF]
    # Incomplete RGB stages must not commit to the visible cache.
    s.write8(0xFD6813C8, 200)
    s.write8(0xFD6813C9, 99)
    assert s.palette[200] == [200, (200 + 37) & 0xFF, (200 + 74) & 0xFF]
    s.write8(0xFD6813C8, 255)
    for val in (10, 20, 30, 11, 21, 31):
        s.write8(0xFD6813C9, val)
    assert s.palette[255] == [10, 20, 30]
    assert s.palette[0] == [11, 21, 31]
    assert s.index == 1 and s.commits == 258
    print("[K1DAC] SELFTEST PASS: exact x86-source ancestry, reversible main patch, indexed RGB 256x3, wrap, partial stage, unsupported MMIO remains fenced")


def stage(a):
    main = a.parent.resolve()
    out = a.out.resolve()
    if main == out or main.parent == out.parent:
        raise ValueError("Refusing to overwrite original K1NV2A diagnostic")
    before = main.read_bytes()
    after = patch(before.decode("utf-8")).encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        if out.read_bytes() != after:
            raise ValueError("Existing DAC output differs; refusing silent overwrite")
    else:
        out.write_bytes(after)
    if main.read_bytes() != before:
        raise ValueError("Original diagnostic changed during staging")
    info = {
        "marker": MARK,
        "status": "NV2A_DAC_PALETTE_SOURCE_STAGED_NO_XDK",
        "parent_main": str(main),
        "parent_main_sha256": digest(before),
        "new_main": str(out),
        "new_main_sha256": digest(after),
        "original_xbe_instruction": "0028ED54 mov byte ptr [ecx+0x6813c8],0",
        "original_xbe_next_writes": ["0028ED77", "0028ED7F", "0028ED8C"],
        "target_index_register": "FD6813C8",
        "target_data_register": "FD6813C9",
        "raw_color_bits": 8,
        "palette_entries": 256,
        "channels_per_entry": 3,
        "unknown_mmio_hard_fence": True,
        "unarmed_palette_data_hard_fence": True,
        "transl_tus_modified": 0,
        "runtime_headers_modified": 0,
        "synthetic_pixels": False,
        "hardware_test_verified": False,
    }
    record = (json.dumps(info, indent=2) + "\n").encode("utf-8")
    a.manifest.parent.mkdir(parents=True, exist_ok=True)
    if a.manifest.exists():
        if a.manifest.read_bytes() != record:
            raise ValueError("Existing DAC manifest differs; refusing silent overwrite")
    else:
        a.manifest.write_bytes(record)
    print("[K1DAC] STAGE PASS: exact known original x86 VGA DAC write-index/data pair")
    print("[K1DAC] INDEX+RGB: record 256 entries, 3 channels, autoincrement every 3 writes")
    print("[K1DAC] FENCE: all unrelated/unknown NV2A MMIO + unarmed data still hard-stop")
    print("[K1DAC] No TrueTU/header edits, no dummy colors, no guest Swap/pixels injected")
    print("[K1DAC] SOURCE ONLY: XDK/Xbox not yet verified")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--parent", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--manifest", type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    if a.parent is None or a.out is None or a.manifest is None:
        p.error("--parent, --out, --manifest required")
    stage(a)


if __name__ == "__main__":
    main()
