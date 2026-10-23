#!/usr/bin/env python3
"""Validate a local Merc360 GPU replay capture without exposing its contents."""
from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path

VERSION = 1


def sha256(path: Path) -> str:
    h = hashlib.sha256()
    with path.open("rb") as f:
        for block in iter(lambda: f.read(1024 * 1024), b""):
            h.update(block)
    return h.hexdigest()


def safe_file(root: Path, relative: str) -> Path:
    if not isinstance(relative, str) or not relative:
        raise ValueError("capture file path must be a non-empty string")
    p = (root / relative).resolve()
    r = root.resolve()
    try:
        p.relative_to(r)
    except ValueError as exc:
        raise ValueError(f"path escapes capture root: {relative}") from exc
    if not p.is_file():
        raise ValueError(f"missing capture file: {relative}")
    return p


def verify_ref(root: Path, item: dict, label: str) -> None:
    if not isinstance(item, dict):
        raise ValueError(f"{label} must be an object")
    path = safe_file(root, item.get("file", ""))
    expected = str(item.get("sha256", "")).lower()
    if len(expected) != 64 or any(c not in "0123456789abcdef" for c in expected):
        raise ValueError(f"{label}: invalid sha256")
    actual = sha256(path)
    if actual != expected:
        raise ValueError(f"{label}: SHA256 mismatch for {item['file']}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("capture", type=Path)
    args = ap.parse_args()
    root = args.capture.resolve()
    manifest_path = root / "capture.json"
    if not manifest_path.is_file():
        raise SystemExit("capture.json missing")
    data = json.loads(manifest_path.read_text(encoding="utf-8"))
    if data.get("version") != VERSION:
        raise SystemExit(f"unsupported capture version: {data.get('version')!r}")
    retail = data.get("retail_xbe_sha256", "")
    if not isinstance(retail, str) or len(retail) != 64:
        raise SystemExit("retail_xbe_sha256 missing/invalid")
    verify_ref(root, data.get("pushbuffer"), "pushbuffer")
    ranges = data.get("memory_ranges", [])
    if not isinstance(ranges, list):
        raise SystemExit("memory_ranges must be a list")
    for index, item in enumerate(ranges):
        verify_ref(root, item, f"memory_ranges[{index}]")
        for key in ("guest_address", "size"):
            if key not in item:
                raise SystemExit(f"memory_ranges[{index}]: missing {key}")
    print(
        f"PASS: capture v{VERSION}, memory_ranges={len(ranges)}, "
        f"root={root}"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
