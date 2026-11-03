#!/usr/bin/env python3
"""Read-only original Xbox PRMDIO WRITE8 source/disassembly candidate audit.

Uses xboxrecomp-generated 64 TrueTU C++ files and, when available, the
user's own verified retail Mercenaries XBE (Capstone optional). Does not
write or redistribute game bytes; does not pretend a basic block is an exact
instruction PC. Outputs short source witnesses and candidate assembly.
"""
from __future__ import annotations
import argparse
import hashlib
import re
import struct
from pathlib import Path

EXPECTED_XBE = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGET = 0xFD6813C8
BLOCK = re.compile(r"PHASE4C_BUDGET_TICK\(0x([0-9A-Fa-f]{6,8})u\)")
FUNC = re.compile(r"\b(?:void|uint32_t)\s+sub_([0-9A-Fa-f]{8})\s*\(")
WRITE = re.compile(r"\bGUEST_WRITE8\s*\(|\brecomp_guest_write8\s*\(")
LITERALS = re.compile(r"(?:FD6813C8|006813C8|6813C8|681000|0x3C8|0X3C8|6813|FD000000)", re.I)


def inspect(shards: Path):
    cpp = sorted(shards.glob("translated_???.cpp"))
    if len(cpp) != 64:
        raise ValueError(f"Expected exactly 64 original TrueTUs, got {len(cpp)}")
    candidates = []
    for file in cpp:
        lines = file.read_text(encoding="utf-8").splitlines()
        current_block = None
        current_func = None
        for i, line in enumerate(lines):
            f = FUNC.search(line)
            if f:
                current_func = int(f.group(1), 16)
            b = BLOCK.search(line)
            if b:
                current_block = int(b.group(1), 16)
            if not WRITE.search(line) or line.lstrip().startswith("#define"):
                continue
            lo = max(0, i - 22)
            hi = min(len(lines), i + 5)
            context = "\n".join(lines[lo:hi])
            function_d3d = current_func is not None and 0x00288640 <= current_func < 0x0029CB80
            block_d3d = current_block is not None and 0x00288640 <= current_block < 0x0029CB80
            score = 0
            if function_d3d: score += 3
            if block_d3d: score += 4
            if LITERALS.search(context): score += 8
            if re.search(r"\becx\b", context, re.I): score += 1
            if re.search(r"\bedx\b", context, re.I): score += 1
            if re.search(r"\bmov\b.*\b(?:byte|al|dl)\b", context, re.I): score += 1
            # 0xFD6813C8 may be assembled from FD000000 + offsets in registers,
            # so literal-free sites are kept, not ruled out.
            candidates.append((score, file.name, i + 1, current_func, current_block,
                               "\n".join(f"{j+1:6d} {lines[j]}" for j in range(max(0, i - 4), hi))))
    return sorted(candidates, key=lambda x: (-x[0], x[1], x[2]))


def guest_to_offset(data: bytes, addr: int):
    base = struct.unpack_from("<I", data, 0x104)[0]
    count = struct.unpack_from("<I", data, 0x11C)[0]
    headers = struct.unpack_from("<I", data, 0x120)[0]
    if not (1 <= count <= 40) or headers < base:
        raise ValueError("Bad XBE section directory")
    start = headers - base
    for i in range(count):
        at = start + i * 56
        if at + 20 > len(data):
            break
        # section layout: flags, VA, virtual size, raw address, raw size
        va, vsize, raw, size = struct.unpack_from("<IIII", data, at + 4)
        if va <= addr < va + min(vsize, size) and raw + addr - va < len(data):
            return raw + addr - va, raw + size
    return None


def disassemble(data: bytes, guest_va: int) -> list[str]:
    try:
        from capstone import Cs, CS_ARCH_X86, CS_MODE_32
    except ImportError:
        return ["Capstone unavailable; run with the installed xboxrecomp Python environment"]
    off = guest_to_offset(data, guest_va)
    if off is None:
        return ["VA not inside a raw-backed original XBE section"]
    where, upper = off
    decoder = Cs(CS_ARCH_X86, CS_MODE_32)
    result = []
    for inst in decoder.disasm(data[where:min(upper, where + 96)], guest_va):
        result.append(f"  {inst.address:08X}  {inst.mnemonic} {inst.op_str}".rstrip())
        if len(result) >= 22:
            break
    return result


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--shards", required=True, type=Path)
    p.add_argument("--xbe", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--max", type=int, default=32)
    a = p.parse_args()
    findings = inspect(a.shards)
    assembly = None
    if a.xbe:
        raw = a.xbe.read_bytes()
        digest = hashlib.sha256(raw).hexdigest().upper()
        if digest != EXPECTED_XBE:
            raise ValueError("Retail XBE SHA256 unexpected; refusing disassembly of wrong title")
        assembly = raw
    out = ["K1NV2A PRMDIO WRITE8 SOURCE AUDIT — READ ONLY",
           f"Target 0x{TARGET:08X}: NV2A +0x6813C8, PRMDIO +0x3C8",
           f"Generated TrueTU WRITE8 call-site count: {len(findings)}",
           "IMPORTANT: candidate function/block VA != exact faulting instruction PC.",
           "Write8 may compute its target at runtime; no literal is required.",
           "No original XBE bytes copied; code extraction limited to local audit.", ""]
    for n, (score, file, line, func, block, source) in enumerate(findings[:a.max], 1):
        out += [f"CANDIDATE {n:02d} score={score} {file}:{line} function={func or 0:08X} block={block or 0:08X}", source]
        if assembly is not None and block is not None and n <= 8:
            out += ["Original XBE x86 from *candidate* basic block (not necessarily actual failing instruction):",
                    *disassemble(assembly, block)]
        out += [""]
    report = "\n".join(out) + "\n"
    if a.out:
        a.out.parent.mkdir(parents=True, exist_ok=True)
        a.out.write_text(report, encoding="utf-8")
    print(report[:18000])
    if a.out:
        print("Full candidate report:", a.out)


if __name__ == "__main__":
    main()
