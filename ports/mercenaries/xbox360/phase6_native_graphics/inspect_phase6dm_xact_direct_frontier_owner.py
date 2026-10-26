#!/usr/bin/env python3
r"""Phase 6DM zero-build audit: identify the owner of the rewritten F2C2 direct-frontier call.

6DL proved the generated source still contains:
    phase4c_direct_frontier(0x0027F2C2u);
This call form bypassed the earlier direct-call and ICALL_SAFE attribution probes.
6DM locates the exact translated function containing that call, prints its full
body and local call context, and finds all direct translated callers of that owner.
No generated source is modified.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

NEEDLE = "phase4c_direct_frontier(0x0027F2C2u)"
FUNC_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+([A-Za-z_][A-Za-z0-9_]*)\s*"
    r"\(\s*void\s*\)\s*\{"
)
TRACE_RE = re.compile(r"RECOMP_TRACE_FUNC\s*\(\s*0x([0-9A-Fa-f]{8})u?\s*\)")


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
        out.append({
            "name": m.group(1),
            "va": va,
            "start": m.start(),
            "end": end,
            "body": body,
        })
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"[Phase6DM] source missing: {args.source}")

    text = args.source.read_text(encoding="utf-8", errors="replace")
    funcs = parse_functions(text)

    owners = [f for f in funcs if NEEDLE in f["body"]]
    if len(owners) != 1:
        raise SystemExit(
            f"[Phase6DM] expected exactly one owner of {NEEDLE}, found {len(owners)}"
        )

    owner = owners[0]
    va = owner["va"]
    va_text = f"{va:08X}" if va is not None else "UNKNOWN"
    lines = owner["body"].splitlines()
    hits = [i for i, line in enumerate(lines) if NEEDLE in line]

    print("[Phase6DM] XACT DIRECT-FRONTIER OWNER AUDIT")
    print(f"[Phase6DM] owner={owner['name']} va={va_text} bytes={owner['end']-owner['start']} lines={len(lines)}")
    print(f"[Phase6DM] frontier_hits={len(hits)}")
    print("[Phase6DM] OWNER BODY BEGIN")
    for i, line in enumerate(lines, 1):
        print(f"{i:04d}: {line}")
    print("[Phase6DM] OWNER BODY END")

    for idx, hit in enumerate(hits, 1):
        print(f"[Phase6DM] FRONTIER CONTEXT {idx}")
        lo = max(0, hit - 24)
        hi = min(len(lines), hit + 25)
        for i in range(lo, hi):
            mark = ">>" if i == hit else "  "
            print(f"[Phase6DM] {mark} {i+1:04d}: {lines[i]}")

    if owner["name"].startswith("sub_"):
        call_pat = re.compile(
            rf"\b{re.escape(owner['name'])}\s*\(\s*\)\s*;"
        )
        callers = []
        for f in funcs:
            if f["name"] == owner["name"]:
                continue
            flines = f["body"].splitlines()
            fhits = [i for i, line in enumerate(flines) if call_pat.search(line)]
            if fhits:
                callers.append((f, flines, fhits))

        print(f"[Phase6DM] direct translated callers of owner={len(callers)}")
        for idx, (f, flines, fhits) in enumerate(callers, 1):
            fva = f["va"]
            fvtxt = f"{fva:08X}" if fva is not None else "UNKNOWN"
            print(f"[Phase6DM] CALLER {idx}: name={f['name']} va={fvtxt} hits={len(fhits)}")
            for hit in fhits:
                lo = max(0, hit - 14)
                hi = min(len(flines), hit + 15)
                for i in range(lo, hi):
                    mark = ">>" if i == hit else "  "
                    print(f"[Phase6DM] {mark} {i+1:04d}: {flines[i]}")

    # Show every raw frontier reference to the release target, including comments.
    raw_pat = re.compile(r"(?i)phase4c_direct_frontier\s*\(\s*0x0027F2C2u?\s*\)")
    raw = list(raw_pat.finditer(text))
    print(f"[Phase6DM] raw direct-frontier hits={len(raw)}")
    for idx, m in enumerate(raw, 1):
        ln = text.count("\n", 0, m.start()) + 1
        a = text.rfind("\n", 0, m.start()) + 1
        b = text.find("\n", m.start())
        if b < 0:
            b = len(text)
        print(f"[Phase6DM] RAW {idx}: source_line={ln} text={text[a:b].strip()}")

    print("[Phase6DM] AUDIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
