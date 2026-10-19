#!/usr/bin/env python3
"""Regression: guest-kernel stdcall cleanup must match canonical prototypes."""

from __future__ import annotations

import re
from pathlib import Path

ROOT = Path(__file__).resolve().parents[2]
KERNEL_H = ROOT / "src" / "kernel" / "kernel.h"
THUNKS_C = ROOT / "src" / "kernel" / "kernel_thunks.c"
BRIDGE_C = ROOT / "src" / "kernel" / "kernel_bridge.c"


def split_params(signature: str) -> list[str]:
    left = signature.find("(")
    right = signature.rfind(")")
    if left < 0 or right < left:
        raise AssertionError(f"bad signature: {signature}")
    text = signature[left + 1:right].strip()
    if not text or text == "void":
        return []
    result: list[str] = []
    current: list[str] = []
    depth = 0
    for ch in text:
        if ch == "(":
            depth += 1
        elif ch == ")":
            depth -= 1
        if ch == "," and depth == 0:
            result.append("".join(current).strip())
            current = []
        else:
            current.append(ch)
    if current:
        result.append("".join(current).strip())
    return result


def expected_cleanup(signature: str) -> int:
    if "__cdecl" in signature:
        return 0
    sizes = []
    for param in split_params(signature):
        by_value_64 = (
            re.search(r"\b(?:LARGE_INTEGER|LONGLONG|ULONGLONG|double|uint64_t|__int64)\b", param)
            and "*" not in param
            and not re.search(r"\bP(?:LARGE_INTEGER|LONGLONG|ULONGLONG)\b", param)
        )
        sizes.append(8 if by_value_64 else 4)
    if "__fastcall" in signature:
        sizes = sizes[2:]
    return sum(sizes)


def prototype_for(header: str, symbol: str) -> str | None:
    pos = header.find(symbol)
    if pos < 0:
        return None
    end = header.find(";", pos)
    if end < 0:
        return None
    start = max(header.rfind(";", 0, pos), header.rfind("\n\n", 0, pos))
    return re.sub(r"\s+", " ", header[start + 1:end + 1]).strip()


def function_body(text: str, name: str) -> str:
    start = text.find(name)
    assert start >= 0, f"missing function {name}"
    brace = text.find("{", start)
    assert brace >= 0
    depth = 0
    for pos in range(brace, len(text)):
        if text[pos] == "{":
            depth += 1
        elif text[pos] == "}":
            depth -= 1
            if depth == 0:
                return text[brace:pos + 1]
    raise AssertionError(f"unclosed function {name}")


def main() -> None:
    header = KERNEL_H.read_text(encoding="utf-8-sig")
    thunks = THUNKS_C.read_text(encoding="utf-8-sig")
    bridge = BRIDGE_C.read_text(encoding="utf-8-sig")

    cleanup_body = function_body(bridge, "static int stdcall_args_for_ordinal")
    actual = {
        int(m.group(1)): int(m.group(2))
        for m in re.finditer(r"case\s+(\d+)\s*:\s*return\s+(\d+)\s*;", cleanup_body)
    }

    failures: list[str] = []
    resolved = 0
    pattern = re.compile(
        r"case\s+(\d+)\s*:\s*return\s*\(ULONG_PTR\)\s*([^;]+);"
    )
    for match in pattern.finditer(thunks):
        ordinal = int(match.group(1))
        expr = match.group(2)
        symbol_match = re.search(r"\b(xbox_[A-Za-z0-9_]+)\b", expr)
        if not symbol_match:
            continue
        symbol = symbol_match.group(1)
        signature = prototype_for(header, symbol)
        if signature is None:
            # Data exports and arrays intentionally have no callable prototype.
            continue
        resolved += 1
        expected = expected_cleanup(signature)
        got = actual.get(ordinal, 0)
        if got != expected:
            failures.append(
                f"ordinal {ordinal} {symbol}: cleanup={got}, expected={expected}; {signature}"
            )

    # Guest-bridge-only helpers are not represented in xbox_resolve_ordinal().
    bridge_only = {188: 12, 232: 12}
    for ordinal, expected in bridge_only.items():
        got = actual.get(ordinal, 0)
        if got != expected:
            failures.append(
                f"bridge-only ordinal {ordinal}: cleanup={got}, expected={expected}"
            )

    # Phase-4A sentinels: these were stale in the pre-Phase-4 table and can
    # corrupt ESP if a fallback import is ever reached.
    sentinels = {
        65: 24, 74: 8, 81: 8, 83: 16, 87: 0, 95: 4,
        232: 12, 327: 4, 328: 4, 335: 4, 336: 12,
        337: 8, 340: 28, 360: 0,
    }
    for ordinal, expected in sentinels.items():
        got = actual.get(ordinal, 0)
        if got != expected:
            failures.append(
                f"Phase-4 sentinel ordinal {ordinal}: cleanup={got}, expected={expected}"
            )

    if failures:
        raise SystemExit("\n".join(["FAIL: guest kernel ABI cleanup mismatch", *failures]))

    print(
        f"PASS: guest kernel stack cleanup matches {resolved} canonical callable "
        f"exports + {len(bridge_only)} bridge-only entries"
    )


if __name__ == "__main__":
    main()
