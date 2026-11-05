#!/usr/bin/env python3
"""V6h retail XBE provenance audit for 0x0022F51C; READ-ONLY, no stage/build."""
from pathlib import Path
import hashlib
import struct
import re
import sys

TAG = "[K1-V6h-RETAIL]"
ROOT = Path.cwd()
XBE = ROOT / "game_files/mercenaries-retail/default.xbe"
SOURCE = ROOT / "build/phase3n_final_abi_scale/runtime/gen"
OUT = ROOT / "build/phase6_integration_map/k1_v6h_retail_22f51c_audit.txt"
EXPECTED_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGET = 0x0022F51C

def fail(message):
    raise RuntimeError(message)

def read_u32(data, pos):
    if pos < 0 or pos + 4 > len(data):
        fail("XBE header offset out of bounds: 0x%X" % pos)
    return struct.unpack_from("<I", data, pos)[0]

def run():
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except ImportError:
        fail("Capstone missing. Run: python -m pip install capstone (source audit only)")
    data = XBE.read_bytes()
    actual = hashlib.sha256(data).hexdigest().upper()
    if actual != EXPECTED_SHA:
        fail("Retail XBE SHA-256 mismatch; no disassembly attempted: " + actual)
    if data[:4] != b"XBEH":
        fail("Not an XBE")
    base = read_u32(data, 0x104)
    count = read_u32(data, 0x11C)
    table_va = read_u32(data, 0x120)
    if not 1 <= count <= 64:
        fail("Unexpected retail section count " + str(count))
    table_off = table_va - base
    if table_off < 0 or table_off + count * 0x38 > len(data):
        fail("Section table not within XBE headers")
    sections = []
    for idx in range(count):
        off = table_off + idx * 0x38
        flags, va, vsz, raw, rawsz = (read_u32(data, off + delta)
                                      for delta in (0, 4, 8, 12, 16))
        if raw > len(data) or rawsz > len(data) - raw:
            fail("Invalid raw section index " + str(idx))
        sections.append((idx, va, vsz, raw, rawsz, flags))
    owners = [s for s in sections if s[1] <= TARGET < s[1] + min(s[2], s[4])]
    if len(owners) != 1:
        fail("Expected exactly one file-backed retail .text section owner: " + str(owners))
    idx, va, vsz, raw, rawsz, flags = owners[0]
    def get(virtual, length):
        if virtual < va or virtual + length > va + rawsz:
            fail("Disassembly request outside mapped source section")
        return data[raw + virtual - va:raw + virtual - va + length]
    md = Cs(CS_ARCH_X86, CS_MODE_32)
    md.detail = False
    lines = [
        "V6H RETAIL ORIGINAL XBE FUNCTION/THUNK AUDIT",
        "XBE: " + str(XBE),
        "Retail SHA256: " + actual,
        "Target: 0x%08X" % TARGET,
        "Section: index=%d VA=0x%08X VSIZE=0x%X RAW=0x%X RAW_SIZE=0x%X FLAGS=0x%X" %
            (idx, va, vsz, raw, rawsz, flags),
        "File offset: 0x%08X" % (raw + TARGET - va),
        "",
        "=== RAW BYTES AT TARGET (128) ===",
        get(TARGET, min(128, va + rawsz - TARGET)).hex(" ").upper(),
        "",
        "=== DISASSEMBLY EXACT TARGET (up to 64 instructions; not proven function boundary) ===",
    ]
    for inst in md.disasm(get(TARGET, min(256, va + rawsz - TARGET)), TARGET, count=64):
        lines.append("0x%08X  %-22s  %-8s %s" % (
            inst.address, inst.bytes.hex(" ").upper(), inst.mnemonic, inst.op_str))
        if inst.mnemonic in ("ret", "retf", "jmp", "int3"):
            lines.append("  --- first possible terminator (not automatically a full function) ---")
            break
    lines.extend(("", "=== EARLIER BYTES / POSSIBLE ENTRY AND ALIGNMENT ==="))
    earlier = max(va, TARGET - 64)
    lines.append("0x%08X: %s" % (earlier, get(earlier, TARGET - earlier).hex(" ").upper()))
    lines.extend(("", "=== ORIGINAL GENERATED C REFERENCE SUMMARY ==="))
    defs, refs = [], []
    for file in sorted(SOURCE.glob("recomp_*.c")):
        if file.name == "recomp_dispatch.c":
            continue
        with file.open(encoding="utf-8-sig", errors="replace") as fp:
            for num, line in enumerate(fp, 1):
                if re.search(r"^\s*void\s+sub_0022F51C\s*\(", line):
                    defs.append("%s:%d: %s" % (file.name, num, line.strip()))
                if "sub_0022F51C()" in line:
                    refs.append("%s:%d: %s" % (file.name, num, line.strip()))
    lines += ["Definitions: " + str(len(defs)), *defs,
              "Reference call sites: " + str(len(refs)), *refs[:24],
              "", "INTERPRETATION: retail x86 is authoritative; function identity,"
              " ABI, and translation ownership still need explicit evidence.",
              "NO GENERATED CODE CHANGED, NO STUB, NO XEX, NO HARDWARE TEST."]
    OUT.parent.mkdir(parents=True, exist_ok=True)
    OUT.write_text("\n".join(lines) + "\n", encoding="utf-8")
    print(TAG + " RETAIL SHA PASS: " + actual)
    print(TAG + " SECTION OWNER: " + str(idx))
    print(TAG + " CALL REFS: " + str(len(refs)))
    print(TAG + " REPORT: " + str(OUT))
    print("\n".join(lines[:35]))
if __name__ == "__main__":
    try: run()
    except Exception as err:
        print(TAG + " BLOCKED: " + str(err), file=sys.stderr)
        sys.exit(1)
