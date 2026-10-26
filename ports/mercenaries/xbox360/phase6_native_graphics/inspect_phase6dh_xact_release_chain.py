#!/usr/bin/env python3
r"""Phase 6DH zero-build audit of the XACT release/destructor chain.

Hardware + 6DG established:
  sub_0027F282 -> sub_0027F194
  sub_0027F194 clears global 0x0028836C
  the XACT root is then freed
  later XACT work still executes.

The immediately preceding translated function is sub_0027F055. 6DH prints
F055, F282, and every direct translated caller to determine whether this is
the Release/refcount -> deleting-destructor path and who invokes it.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGETS = ("sub_0027F055", "sub_0027F282")
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


def print_body(label: str, body: str):
    print(label)
    for i, line in enumerate(body.splitlines(), 1):
        print(f"{i:04d}: {line}")


def callers_of(funcs, target: str):
    pat = re.compile(rf"\b{re.escape(target)}\s*\(\s*\)\s*;")
    rows = []
    for f in funcs:
        if f["name"] == target:
            continue
        lines = f["body"].splitlines()
        hits = [i for i, line in enumerate(lines) if pat.search(line)]
        if hits:
            rows.append((f, hits))
    return rows


def print_callers(funcs, target: str):
    rows = callers_of(funcs, target)
    print(f"[Phase6DH] direct callers of {target}={len(rows)}")
    for idx, (f, hits) in enumerate(rows, 1):
        va = f["va"]
        print(
            f"[Phase6DH] CALLER {idx}: name={f['name']} "
            f"va={(f'{va:08X}' if va is not None else 'UNKNOWN')} hits={len(hits)}"
        )
        lines = f["body"].splitlines()
        for hit in hits:
            lo = max(0, hit - 16)
            hi = min(len(lines), hit + 17)
            for i in range(lo, hi):
                mark = ">>" if i == hit else "  "
                print(f"[Phase6DH] {mark} {i+1:04d}: {lines[i]}")


def raw_hits(text: str, needle: str):
    pat = re.compile(re.escape(needle), re.I)
    hits = list(pat.finditer(text))
    print(f"[Phase6DH] raw hits {needle}={len(hits)}")
    for idx, m in enumerate(hits[:48], 1):
        ln = text.count("\n", 0, m.start()) + 1
        a = text.rfind("\n", 0, m.start()) + 1
        b = text.find("\n", m.start())
        if b < 0:
            b = len(text)
        print(f"[Phase6DH] RAW {idx}: source_line={ln} text={text[a:b].strip()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"[Phase6DH] source missing: {args.source}")

    text = args.source.read_text(encoding="utf-8", errors="replace")
    funcs = parse_functions(text)
    by_name = {f["name"]: f for f in funcs}

    print("[Phase6DH] XACT RELEASE/DESTRUCTOR CHAIN AUDIT")
    for target in TARGETS:
        f = by_name.get(target)
        if f is None:
            raise SystemExit(f"[Phase6DH] target missing: {target}")
        print(
            f"[Phase6DH] target={target} "
            f"va={(f'{f['va']:08X}' if f['va'] is not None else 'UNKNOWN')} "
            f"bytes={f['end']-f['start']} lines={len(f['body'].splitlines())}"
        )
        print_body(f"[Phase6DH] {target} BODY BEGIN", f["body"])
        print(f"[Phase6DH] {target} BODY END")
        print_callers(funcs, target)

    # Recursive caller neighborhood: callers of direct callers, up to two hops.
    seeds = set()
    for target in TARGETS:
        for f, _ in callers_of(funcs, target):
            seeds.add(f["name"])
    for seed in sorted(seeds):
        print_callers(funcs, seed)

    raw_hits(text, "0027F055")
    raw_hits(text, "0027F282")
    raw_hits(text, "0x30266C")
    raw_hits(text, "0x28836C")

    print("[Phase6DH] AUDIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
