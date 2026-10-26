#!/usr/bin/env python3
r"""Phase 6DL zero-build audit for the hardware-proven XACT final-release origin.

6DK hardware proved the dynamic packed lookup:
  caller=0x0023A3CE
  target=0x0027F2C2
  global root=0x01B5C320 ref=1

The pretrace also showed ecx=0x008C1104 on entry to sub_0027F2C2, while the
actual refcount decrement inside that function applies to 0x01B5C320.

This audit prints:
  * full translated body of sub_0023A3CE
  * full translated body of sub_0027F2C2
  * direct callers of both
  * all lines in 0023A3CE containing indirect/tail/direct dispatch constructs
  * all reads/writes of 0x0028836C and +8-style refcount accesses in F2C2

It does not modify generated code.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path

TARGETS = ("sub_0023A3CE", "sub_0027F2C2")
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
    print(label.replace("BEGIN", "END"))


def print_matches(label: str, body: str, patterns):
    lines = body.splitlines()
    hits = []
    for i, line in enumerate(lines, 1):
        if any(p.search(line) for p in patterns):
            hits.append((i, line))
    print(f"[Phase6DL] {label} hits={len(hits)}")
    for i, line in hits:
        print(f"[Phase6DL] {label} line={i:04d}: {line}")


def direct_callers(funcs, target: str):
    pat = re.compile(rf"\b{re.escape(target)}\s*\(\s*\)\s*;")
    rows = []
    for f in funcs:
        if f["name"] == target:
            continue
        lines = f["body"].splitlines()
        for hit, line in enumerate(lines):
            if pat.search(line):
                rows.append((f, hit, lines))
    return rows


def print_callers(funcs, target: str):
    rows = direct_callers(funcs, target)
    print(f"[Phase6DL] direct translated callers of {target}={len(rows)}")
    for idx, (f, hit, lines) in enumerate(rows, 1):
        va = f["va"]
        vtxt = f"{va:08X}" if va is not None else "UNKNOWN"
        print(f"[Phase6DL] CALLER {idx}: name={f['name']} va={vtxt}")
        lo = max(0, hit - 18)
        hi = min(len(lines), hit + 19)
        for i in range(lo, hi):
            mark = ">>" if i == hit else "  "
            print(f"[Phase6DL] {mark} {i+1:04d}: {lines[i]}")


def raw_hits(text: str, needle: str):
    pat = re.compile(re.escape(needle), re.I)
    hits = list(pat.finditer(text))
    print(f"[Phase6DL] raw hits {needle}={len(hits)}")
    for idx, m in enumerate(hits[:64], 1):
        ln = text.count("\n", 0, m.start()) + 1
        a = text.rfind("\n", 0, m.start()) + 1
        b = text.find("\n", m.start())
        if b < 0:
            b = len(text)
        print(f"[Phase6DL] RAW {idx}: source_line={ln} text={text[a:b].strip()}")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()

    if not args.source.exists():
        raise SystemExit(f"[Phase6DL] source missing: {args.source}")

    text = args.source.read_text(encoding="utf-8", errors="replace")
    funcs = parse_functions(text)
    by_name = {f["name"]: f for f in funcs}

    print("[Phase6DL] XACT FINAL-RELEASE ORIGIN SOURCE AUDIT")
    print("[Phase6DL] Hardware proof: packed lookup caller=0023A3CE target=0027F2C2 root=01B5C320 ref=1")

    for name in TARGETS:
        f = by_name.get(name)
        if f is None:
            raise SystemExit(f"[Phase6DL] target missing: {name}")
        va = f["va"]
        vtxt = f"{va:08X}" if va is not None else "UNKNOWN"
        print(
            f"[Phase6DL] target={name} va={vtxt} "
            f"bytes={f['end']-f['start']} lines={len(f['body'].splitlines())}"
        )
        print_body(f"[Phase6DL] {name} BODY BEGIN", f["body"])
        print_callers(funcs, name)

    dispatch_patterns = (
        re.compile(r"RECOMP_(?:ICALL|ITAIL|DIRECT)"),
        re.compile(r"phase4c_lookup_pack_func"),
        re.compile(r"recomp_lookup"),
        re.compile(r"_icall_esp"),
        re.compile(r"0027F2C2", re.I),
        re.compile(r"28836C", re.I),
    )
    f_a3ce = by_name["sub_0023A3CE"]
    print_matches("A3CE DISPATCH/ROOT", f_a3ce["body"], dispatch_patterns)

    release_patterns = (
        re.compile(r"28836C", re.I),
        re.compile(r"GUEST_READ32\([^\n]*\+\s*8"),
        re.compile(r"GUEST_WRITE32\([^\n]*\+\s*8"),
        re.compile(r"sub_0027F282"),
        re.compile(r"RtlEnterCriticalSection|RtlLeaveCriticalSection"),
        re.compile(r"RECOMP_"),
    )
    f_f2c2 = by_name["sub_0027F2C2"]
    print_matches("F2C2 ROOT/REFCOUNT", f_f2c2["body"], release_patterns)

    raw_hits(text, "0023A3CE")
    raw_hits(text, "0027F2C2")
    raw_hits(text, "0x28836C")

    print("[Phase6DL] AUDIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
