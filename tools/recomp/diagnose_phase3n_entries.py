#!/usr/bin/env python3
"""Inspect unresolved Phase-3N direct targets in the supported retail XBE."""

from __future__ import annotations

import argparse
import json
from pathlib import Path

from capstone import Cs, CS_ARCH_X86, CS_MODE_32

from . import config


DEFAULT_TARGETS = (
    0x000E1D7A,
    0x001DE3BC,
    0x0023DA9C,
    0x0023DAA8,
    0x002DBD06,
)


def parse_address(value: str) -> int:
    return int(value, 0)


def load_functions(path: Path) -> list[dict]:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    result = []
    for row in rows:
        start = int(str(row["start"]), 16)
        end = int(str(row["end"]), 16)
        result.append({
            "start": start,
            "end": end,
            "name": row.get("name", f"sub_{start:08X}"),
            "section": row.get("section"),
        })
    return sorted(result, key=lambda row: row["start"])


def find_parent(functions: list[dict], address: int):
    for row in functions:
        if row["start"] <= address < row["end"]:
            return row
    return None


def previous_next(functions: list[dict], address: int):
    previous = None
    next_row = None
    for row in functions:
        if row["start"] <= address:
            previous = row
            continue
        next_row = row
        break
    return previous, next_row


def format_function(row):
    if row is None:
        return "-"
    section = f" section={row['section']}" if row.get("section") else ""
    return (
        f"{row['name']} "
        f"0x{row['start']:08X}:0x{row['end']:08X}{section}"
    )


def audit_entries(path: Path | None) -> dict[int, dict]:
    if not path or not path.is_file():
        return {}
    data = json.loads(path.read_text(encoding="utf-8-sig"))
    entries = data.get("unresolved_classification", {}).get("entries", [])
    result = {}
    for entry in entries:
        try:
            address = int(entry["address_hex"], 16)
        except (KeyError, TypeError, ValueError):
            continue
        result[address] = entry
    return result


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument("xbe", type=Path)
    parser.add_argument("--functions", type=Path, required=True)
    parser.add_argument("--audit", type=Path)
    parser.add_argument("--target", action="append", type=parse_address)
    parser.add_argument("--bytes", type=int, default=128)
    parser.add_argument("--instructions", type=int, default=28)
    args = parser.parse_args()

    config.configure_from_xbe(str(args.xbe))
    blob = args.xbe.read_bytes()
    functions = load_functions(args.functions)
    audit = audit_entries(args.audit)
    targets = tuple(args.target or DEFAULT_TARGETS)

    md = Cs(CS_ARCH_X86, CS_MODE_32)

    print("Phase 3N unresolved-entry retail probe")
    print(f"XBE: {args.xbe}")
    print(f"functions: {len(functions)}")

    for address in targets:
        print()
        print("=" * 78)
        print(f"TARGET 0x{address:08X}")
        print(f"code_address={config.is_code_address(address)}")
        parent = find_parent(functions, address)
        previous, next_row = previous_next(functions, address)
        print(f"parent: {format_function(parent)}")
        print(f"previous: {format_function(previous)}")
        print(f"next: {format_function(next_row)}")

        entry = audit.get(address)
        if entry:
            print(
                "classification="
                f"{entry.get('classification', 'unclassified')} "
                f"refs={entry.get('reference_count', 0)}"
            )
            for ref in entry.get("references", []):
                for site in ref.get("sites", []):
                    caller = site.get("caller_function") or "-"
                    span = ""
                    if site.get("caller_start") and site.get("caller_end"):
                        span = (
                            f" {site['caller_start']}:{site['caller_end']}"
                        )
                    print(
                        f"caller: {caller}{span} "
                        f"{Path(ref['file']).name}:{site.get('line', '-')}"
                    )
                    print(f"  {site.get('text', '')}")

        nearby = [
            row for row in functions
            if address - 0x100 <= row["start"] <= address + 0x180
        ]
        print("nearby detected starts:")
        for row in nearby:
            marker = "*" if row is parent else " "
            print(f" {marker} {format_function(row)}")

        offset = config.va_to_file_offset(address)
        if offset is None:
            print("NO FILE BYTES: target is not backed by raw XBE data")
            continue

        data = blob[offset:offset + args.bytes]
        print(f"raw[{len(data)}]: {data[:32].hex(' ').upper()}")
        print("decode:")
        count = 0
        for insn in md.disasm(data, address):
            raw = bytes(insn.bytes).hex(" ").upper()
            print(
                f"  {insn.address:08X}  {raw:<24} "
                f"{insn.mnemonic:<8} {insn.op_str}"
            )
            count += 1
            if count >= args.instructions:
                break
            # Continue a little beyond a terminal instruction only when the
            # caller may target a following shared block; otherwise one retail
            # path is enough for classification.
            if insn.mnemonic.startswith("ret") and count >= 4:
                break

    return 0


if __name__ == "__main__":
    raise SystemExit(main())
