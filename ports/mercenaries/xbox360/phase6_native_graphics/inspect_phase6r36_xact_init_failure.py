#!/usr/bin/env python3
r"""Phase 6R36 zero-build audit: isolate the XACT init failure in sub_0027DC5B.

R35/6DM proved sub_0027F3DC only releases the newly-created XACT root after
sub_0027DC5B returns a failing HRESULT.  This audit prints the exact 0027DC5B
body, all callsites, and local post-call status/branch context so the failing
initializer step can be identified without compiling or running hardware.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGET = "sub_0027DC5B"
FUNC_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*void\s*\)\s*\{"
)
TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")
CALL_PATTERNS = (
    re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)\s*;"),
    re.compile(r"phase4c_direct_frontier\s*\(\s*(0x[0-9A-Fa-f]+u?)\s*\)"),
    re.compile(r"PHASE6DJ_ICALL_SAFE\s*\([^,]+,\s*([^,]+),"),
)


def closing_brace(text: str, brace: int) -> int:
    depth = 0
    i = brace
    ins = False
    quote = ""
    esc = False
    linec = False
    blockc = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if linec:
            if c == "\n":
                linec = False
            i += 1
            continue
        if blockc:
            if c == "*" and n == "/":
                blockc = False
                i += 2
            else:
                i += 1
            continue
        if ins:
            if esc:
                esc = False
            elif c == "\\":
                esc = True
            elif c == quote:
                ins = False
            i += 1
            continue
        if c == "/" and n == "/":
            linec = True
            i += 2
            continue
        if c == "/" and n == "*":
            blockc = True
            i += 2
            continue
        if c in ('"', "'"):
            ins = True
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


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"[Phase6R36] source missing: {args.source}")

    text = args.source.read_text(encoding="utf-8", errors="replace")
    funcs = parse_functions(text)
    matches = [f for f in funcs if f["name"] == TARGET]
    if len(matches) != 1:
        raise SystemExit(f"[Phase6R36] expected one {TARGET}, found {len(matches)}")

    f = matches[0]
    lines = f["body"].splitlines()
    va = f["va"]
    print("[Phase6R36] XACT INIT FAILURE ZERO-BUILD AUDIT")
    print(f"[Phase6R36] target={TARGET} va={(va or 0):08X} lines={len(lines)}")
    print("[Phase6R36] BODY BEGIN")
    for i, line in enumerate(lines, 1):
        print(f"{i:04d}: {line}")
    print("[Phase6R36] BODY END")

    call_rows = []
    for i, line in enumerate(lines):
        kind = None
        target = None
        m = CALL_PATTERNS[0].search(line)
        if m:
            kind, target = "DIRECT", m.group(1)
        else:
            m = CALL_PATTERNS[1].search(line)
            if m:
                kind, target = "FRONTIER", m.group(1)
            else:
                m = CALL_PATTERNS[2].search(line)
                if m:
                    kind, target = "ICALL", m.group(1).strip()

        if kind:
            call_rows.append((i, kind, target))

    print(f"[Phase6R36] calls={len(call_rows)}")
    for idx, (line_i, kind, target) in enumerate(call_rows, 1):
        print(f"[Phase6R36] CALL {idx}: kind={kind} target={target} line={line_i+1}")
        lo = max(0, line_i - 8)
        hi = min(len(lines), line_i + 15)
        for j in range(lo, hi):
            mark = ">>" if j == line_i else "  "
            print(f"[Phase6R36] {mark} {j+1:04d}: {lines[j]}")

    # Highlight every status-propagation / failure branch in the initializer.
    status_tokens = (
        "esi = eax",
        "edi = eax",
        "ebx = eax",
        "if (TEST_S(",
        "if (((int32_t)",
        "0x8007000E",
        "SetLastError",
        "MmAllocate",
        "sub_001787C0",
    )
    status_hits = [
        i for i, line in enumerate(lines)
        if any(tok in line for tok in status_tokens)
    ]
    print(f"[Phase6R36] status/failure hits={len(status_hits)}")
    for idx, hit in enumerate(status_hits, 1):
        print(f"[Phase6R36] STATUS {idx}: line={hit+1}")
        lo = max(0, hit - 5)
        hi = min(len(lines), hit + 9)
        for j in range(lo, hi):
            mark = ">>" if j == hit else "  "
            print(f"[Phase6R36] {mark} {j+1:04d}: {lines[j]}")

    # Find direct callers too, useful if 27DC5B itself only forwards a status.
    call_pat = re.compile(r"\bsub_0027DC5B\s*\(\s*\)\s*;")
    callers = []
    for g in funcs:
        if g["name"] == TARGET:
            continue
        glines = g["body"].splitlines()
        ghits = [i for i, line in enumerate(glines) if call_pat.search(line)]
        if ghits:
            callers.append((g, glines, ghits))

    print(f"[Phase6R36] direct callers={len(callers)}")
    for idx, (g, glines, ghits) in enumerate(callers, 1):
        gv = g["va"] or 0
        print(f"[Phase6R36] CALLER {idx}: name={g['name']} va={gv:08X} hits={len(ghits)}")
        for hit in ghits:
            lo = max(0, hit - 10)
            hi = min(len(glines), hit + 14)
            for j in range(lo, hi):
                mark = ">>" if j == hit else "  "
                print(f"[Phase6R36] {mark} {j+1:04d}: {glines[j]}")

    print("[Phase6R36] AUDIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
