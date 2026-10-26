#!/usr/bin/env python3
r"""Phase 6R37 zero-build audit for DirectSound DSERR_NODRIVER origin.

R36 hardware proved sub_0027DC5B fails immediately because sub_0029FDF0 returns
0x88780078 (DSERR_NODRIVER).  This tool inspects the current generated
main_monolithic.cpp and prints sub_0029FDF0 plus local failure/status context and
direct callee bodies.  It performs no generated-source mutation and no build.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGET = "sub_0029FDF0"
ERROR_HEX = ("88780078", "0x88780078")
FUNC_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*void\s*\)\s*\{"
)
TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
DIRECT_CALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)\s*;")
FRONTIER_RE = re.compile(r"phase4c_direct_frontier\s*\(\s*(0x[0-9A-Fa-f]+u?)\s*\)")


def closing_brace(text: str, brace: int) -> int:
    depth = 0
    i = brace
    in_string = False
    quote = ""
    escaped = False
    line_comment = False
    block_comment = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if line_comment:
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escaped:
                escaped = False
            elif c == "\\":
                escaped = True
            elif c == quote:
                in_string = False
            i += 1
            continue
        if c == "/" and n == "/":
            line_comment = True
            i += 2
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c in ('"', "'"):
            in_string = True
            quote = c
            i += 1
            continue
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
        i += 1
    raise RuntimeError("unterminated function")


def parse_functions(text: str):
    out = []
    for m in FUNC_RE.finditer(text):
        brace = text.find("{", m.start(), m.end())
        end = closing_brace(text, brace)
        body = text[m.start():end]
        tm = TRACE_RE.search(body)
        va = int(tm.group(1), 16) if tm else None
        if va is None:
            mm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", m.group(1))
            if mm:
                va = int(mm.group(1), 16)
        out.append({"name": m.group(1), "va": va, "body": body})
    return out


def emit_context(prefix: str, lines: list[str], hit: int, before: int = 8, after: int = 12):
    lo = max(0, hit - before)
    hi = min(len(lines), hit + after + 1)
    for j in range(lo, hi):
        mark = ">>" if j == hit else "  "
        print(f"{prefix} {mark} {j+1:04d}: {lines[j]}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()
    if not args.source.exists():
        raise SystemExit(f"[Phase6R37] source missing: {args.source}")

    text = args.source.read_text(encoding="utf-8", errors="replace")
    funcs = parse_functions(text)
    by_name = {f["name"]: f for f in funcs}

    f = by_name.get(TARGET)
    if not f:
        raise SystemExit(f"[Phase6R37] target missing: {TARGET}")

    lines = f["body"].splitlines()
    print("[Phase6R37] DSOUND NODRIVER ZERO-BUILD AUDIT")
    print(f"[Phase6R37] target={TARGET} va={(f['va'] or 0):08X} lines={len(lines)}")
    print("[Phase6R37] BODY BEGIN")
    for i, line in enumerate(lines, 1):
        print(f"{i:04d}: {line}")
    print("[Phase6R37] BODY END")

    # Direct call inventory and local context.
    calls: list[tuple[int, str]] = []
    for i, line in enumerate(lines):
        for m in DIRECT_CALL_RE.finditer(line):
            calls.append((i, m.group(1)))
        for m in FRONTIER_RE.finditer(line):
            calls.append((i, m.group(1)))

    print(f"[Phase6R37] calls={len(calls)}")
    seen_callees = []
    for idx, (hit, target) in enumerate(calls, 1):
        print(f"[Phase6R37] CALL {idx}: line={hit+1} target={target}")
        emit_context("[Phase6R37]", lines, hit, 6, 12)
        if target.startswith("sub_") and target not in seen_callees:
            seen_callees.append(target)

    # Every suspicious status/failure site in the target.
    tokens = (
        "88780078",
        "TEST_S(",
        "CMP_",
        "eax = ",
        "esi = eax",
        "edi = eax",
        "ebx = eax",
        "goto loc_",
        "GUEST_READ32(",
        "GUEST_WRITE32(",
    )
    hits = [i for i, line in enumerate(lines) if any(t in line for t in tokens)]
    print(f"[Phase6R37] status/failure candidates={len(hits)}")
    for idx, hit in enumerate(hits, 1):
        print(f"[Phase6R37] STATUS {idx}: line={hit+1}")
        emit_context("[Phase6R37]", lines, hit, 4, 7)

    # Search the whole monolithic source for exact DSERR_NODRIVER construction.
    whole_lines = text.splitlines()
    error_hits = [
        i for i, line in enumerate(whole_lines)
        if any(tok.lower() in line.lower() for tok in ERROR_HEX)
    ]
    print(f"[Phase6R37] whole-source DSERR_NODRIVER literal hits={len(error_hits)}")
    for idx, hit in enumerate(error_hits, 1):
        print(f"[Phase6R37] NODRIVER LITERAL {idx}: source_line={hit+1}")
        emit_context("[Phase6R37]", whole_lines, hit, 5, 8)

    # Dump immediate direct callee bodies so a wrapper-returning-NODRIVER path
    # can often be resolved from one audit.
    for target in seen_callees:
        g = by_name.get(target)
        if not g:
            print(f"[Phase6R37] CALLEE {target}: body unavailable")
            continue
        glines = g["body"].splitlines()
        print("=" * 96)
        print(f"[Phase6R37] CALLEE BODY name={target} va={(g['va'] or 0):08X} lines={len(glines)}")
        for i, line in enumerate(glines, 1):
            print(f"[Phase6R37] {i:04d}: {line}")

    print("[Phase6R37] AUDIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
