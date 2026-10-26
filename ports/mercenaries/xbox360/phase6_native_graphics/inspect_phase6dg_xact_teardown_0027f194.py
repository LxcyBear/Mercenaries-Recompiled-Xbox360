#!/usr/bin/env python3
r"""Phase 6DG zero-build audit for the XACT teardown culprit sub_0027F194.

6DF hardware proved:
  * sub_0027DB5C initializes global 0x0028836C to the live XACT root.
  * sub_0027F194 later writes 0x0028836C = 0.
  * the same live root object is freed immediately afterward.
  * later sub_00280C39 still executes and reads the cleared global.

This script does not modify generated code. It extracts the exact translated
body and all direct translated callers from the cached 6DF monolithic source.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGET_NAME = "sub_0027F194"
TARGET_VA = 0x0027F194
GLOBAL_TEXTS = ("0x0028836C", "0x28836C")
FUNC_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*void\s*\)\s*\{"
)
TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")


def closing_brace(text: str, brace: int) -> int:
    depth = 0
    i = brace
    in_string = False
    quote = ""
    escape = False
    in_line = False
    in_block = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if in_line:
            if c == "\n":
                in_line = False
            i += 1
            continue
        if in_block:
            if c == "*" and n == "/":
                in_block = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                in_string = False
            i += 1
            continue
        if c == "/" and n == "/":
            in_line = True
            i += 2
            continue
        if c == "/" and n == "*":
            in_block = True
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
    raise RuntimeError("unterminated function body")


def functions(text: str):
    out = []
    for m in FUNC_RE.finditer(text):
        brace = text.find("{", m.start(), m.end())
        end = closing_brace(text, brace)
        body = text[m.start():end]
        tm = TRACE_RE.search(body)
        va = int(tm.group(1), 16) if tm else None
        if va is None:
            nm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", m.group(1))
            if nm:
                va = int(nm.group(1), 16)
        out.append((m.group(1), va, m.start(), end, body))
    return out


def print_numbered(label: str, body: str, max_lines: int | None = None):
    lines = body.splitlines()
    print(label)
    lim = len(lines) if max_lines is None else min(len(lines), max_lines)
    for i in range(lim):
        print(f"{i+1:04d}: {lines[i]}")
    if lim < len(lines):
        print(f"... ({len(lines)-lim} more lines omitted)")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"[Phase6DG] source missing: {args.source}")
    text = args.source.read_text(encoding="utf-8", errors="replace")
    fs = functions(text)

    target = [f for f in fs if f[0] == TARGET_NAME or f[1] == TARGET_VA]
    if len(target) != 1:
        raise SystemExit(
            f"[Phase6DG] expected exactly one {TARGET_NAME}, found {len(target)}"
        )
    name, va, start, end, body = target[0]

    print("[Phase6DG] XACT TEARDOWN SOURCE AUDIT")
    print(f"[Phase6DG] target={name} va={va:08X}")
    print(f"[Phase6DG] source_bytes={end-start} body_lines={len(body.splitlines())}")
    print_numbered("[Phase6DG] TARGET BODY BEGIN", body)
    print("[Phase6DG] TARGET BODY END")

    glines = []
    for n, line in enumerate(body.splitlines(), 1):
        if any(g.lower() in line.lower() for g in GLOBAL_TEXTS):
            glines.append((n, line))
    print(f"[Phase6DG] direct literal 0028836C refs in target={len(glines)}")
    for n, line in glines:
        print(f"[Phase6DG] GLOBAL REF line={n}: {line}")

    call_pat = re.compile(r"\bsub_0027F194\s*\(\s*\)\s*;")
    callers = []
    for fname, fva, fstart, fend, fbody in fs:
        if fname == TARGET_NAME:
            continue
        if call_pat.search(fbody):
            callers.append((fname, fva, fbody))

    print(f"[Phase6DG] direct translated callers={len(callers)}")
    for idx, (fname, fva, fbody) in enumerate(callers, 1):
        print(
            f"[Phase6DG] CALLER {idx}: name={fname} "
            f"va={(f'{fva:08X}' if fva is not None else 'UNKNOWN')}"
        )
        lines = fbody.splitlines()
        hit = next(
            (i for i, line in enumerate(lines) if call_pat.search(line)),
            None,
        )
        if hit is None:
            continue
        lo = max(0, hit - 12)
        hi = min(len(lines), hit + 13)
        for i in range(lo, hi):
            mark = ">>" if i == hit else "  "
            print(f"[Phase6DG] {mark} {i+1:04d}: {lines[i]}")

    # Also catch address-based dispatch/call references in generated text.
    address_pat = re.compile(r"(?i)0027F194")
    raw_hits = list(address_pat.finditer(text))
    print(f"[Phase6DG] raw 0027F194 text hits={len(raw_hits)}")
    for idx, m in enumerate(raw_hits[:32], 1):
        line_no = text.count("\n", 0, m.start()) + 1
        line_start = text.rfind("\n", 0, m.start()) + 1
        line_end = text.find("\n", m.start())
        if line_end < 0:
            line_end = len(text)
        line = text[line_start:line_end].strip()
        print(f"[Phase6DG] RAW HIT {idx}: source_line={line_no} text={line}")

    print("[Phase6DG] AUDIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
