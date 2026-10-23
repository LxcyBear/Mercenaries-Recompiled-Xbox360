#!/usr/bin/env python3
"""Normalize and compare Phase-6 PC/Xbox360 guest-semantic JSONL traces."""
from __future__ import annotations

import argparse
import json
from pathlib import Path

KINDS = {
    "direct", "icall", "kernel", "vm", "heap", "file",
    "mmio-read", "mmio-write", "vram-read", "vram-write",
    "pfifo", "pgraph", "draw", "shader",
}

COMPARE_FIELDS = {
    "direct": ("caller", "target"),
    "icall": ("caller", "target"),
    "kernel": ("ordinal",),
    "vm": ("op", "address", "size"),
    "heap": ("op", "size"),
    "file": ("op", "path"),
    "mmio-read": ("address", "width"),
    "mmio-write": ("address", "width", "value"),
    "vram-read": ("address", "width"),
    "vram-write": ("address", "width", "value"),
    "pfifo": ("put",),
    "pgraph": ("subchannel", "method", "value"),
    "draw": ("hash",),
    "shader": ("shader_kind", "hash"),
}


def load(path: Path) -> list[dict]:
    rows: list[dict] = []
    for lineno, raw in enumerate(path.read_text(encoding="utf-8").splitlines(), 1):
        raw = raw.strip()
        if not raw:
            continue
        try:
            row = json.loads(raw)
        except json.JSONDecodeError as exc:
            raise SystemExit(f"{path}:{lineno}: invalid JSON: {exc}") from exc
        if not isinstance(row, dict):
            raise SystemExit(f"{path}:{lineno}: event must be an object")
        kind = row.get("kind")
        if kind not in KINDS:
            raise SystemExit(f"{path}:{lineno}: unsupported kind {kind!r}")
        rows.append(row)
    return rows


def normalized(row: dict) -> tuple:
    kind = row["kind"]
    fields = COMPARE_FIELDS[kind]
    return (kind,) + tuple(row.get(name) for name in fields)


def command_normalize(args: argparse.Namespace) -> int:
    rows = load(args.input)
    out = args.output.open("w", encoding="utf-8") if args.output else None
    try:
        target = out if out else __import__("sys").stdout
        for seq, row in enumerate(rows, 1):
            value = {"seq": seq, "kind": row["kind"]}
            for name in COMPARE_FIELDS[row["kind"]]:
                if name in row:
                    value[name] = row[name]
            target.write(json.dumps(value, sort_keys=True, separators=(",", ":")) + "\n")
    finally:
        if out:
            out.close()
    return 0


def command_diff(args: argparse.Namespace) -> int:
    oracle = load(args.oracle)
    candidate = load(args.candidate)
    limit = min(len(oracle), len(candidate))
    for index in range(limit):
        a = normalized(oracle[index])
        b = normalized(candidate[index])
        if a != b:
            print(f"DIVERGENCE index={index} seq={index + 1}")
            print("oracle   =", json.dumps(oracle[index], sort_keys=True))
            print("candidate=", json.dumps(candidate[index], sort_keys=True))
            return 1
    if len(oracle) != len(candidate):
        print(
            f"LENGTH DIVERGENCE common={limit} "
            f"oracle={len(oracle)} candidate={len(candidate)}"
        )
        return 1
    print(f"PASS: semantic traces match ({len(oracle)} events)")
    return 0


def main() -> int:
    ap = argparse.ArgumentParser()
    sub = ap.add_subparsers(dest="cmd", required=True)

    n = sub.add_parser("normalize")
    n.add_argument("input", type=Path)
    n.add_argument("-o", "--output", type=Path)
    n.set_defaults(func=command_normalize)

    d = sub.add_parser("diff")
    d.add_argument("oracle", type=Path)
    d.add_argument("candidate", type=Path)
    d.set_defaults(func=command_diff)

    args = ap.parse_args()
    return args.func(args)


if __name__ == "__main__":
    raise SystemExit(main())
