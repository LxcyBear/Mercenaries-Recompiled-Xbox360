#!/usr/bin/env python3
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

LOOP_VAS = [
    0x00291BE0,
    0x00291BFF,
    0x00291C10,
    0x00291C60,
    0x00291CCB,
    0x00291D3A,
    0x00291D42,
    0x00291D4E,
    0x00292299,
    0x002922A9,
    0x00292277,
    0x00292292,
]

def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AX] could not load helper: {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def containing_row(rows: list[dict], va: int) -> dict | None:
    hits = []
    for row in rows:
        try:
            start = int(str(row["start"]), 0)
            end = int(str(row["end"]), 0)
        except Exception:
            continue
        if start <= va < end:
            hits.append((start, end, row))
    if not hits:
        return None
    hits.sort(key=lambda x: (x[1] - x[0], x[0]))
    start, end, row = hits[0]
    out = dict(row)
    out["start"] = start
    out["end"] = end
    out["name"] = str(row.get("name", f"sub_{start:08X}"))
    return out

def source_lines_around(source: str, va: int, before: int = 5, after: int = 18) -> list[str]:
    lines = source.splitlines()
    pat = re.compile(rf"^\s*loc_{va:08X}\s*:\s*;\s*$", re.I)
    idx = None
    for i, line in enumerate(lines):
        if pat.match(line):
            idx = i
            break
    if idx is None:
        return []
    lo = max(0, idx - before)
    hi = min(len(lines), idx + after + 1)
    return [f"{i+1:05d}: {lines[i]}" for i in range(lo, hi)]

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--phase4-emitter", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--out", type=Path, required=True)
    args = ap.parse_args()

    for p in (args.phase4_emitter, args.functions, args.generated_root):
        if not p.exists():
            raise SystemExit(f"[Phase6AX] missing input: {p}")

    base = load_module(args.phase4_emitter, "phase6ax_base")
    rows = json.loads(args.functions.read_text(encoding="utf-8-sig"))
    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)

    report: list[str] = []
    report.append("[Phase6AX] D3D SPIN SOURCE CORRELATION")
    report.append("[Phase6AX] Hardware source: P6AW 12-address repeating loop")
    report.append("")

    mappings: list[tuple[int, dict]] = []
    for va in LOOP_VAS:
        row = containing_row(rows, va)
        if row is None:
            report.append(f"[Phase6AX] VA 0x{va:08X}: NO CONTAINING FUNCTION")
            continue
        mappings.append((va, row))
        generated_row = generated.get(int(row["start"]))
        report.append(
            f"[Phase6AX] VA 0x{va:08X} -> "
            f"{row['name']} 0x{int(row['start']):08X}-0x{int(row['end']):08X} "
            f"generated={'yes' if generated_row else 'no'}"
        )

    report.append("")
    unique_starts: list[int] = []
    for _, row in mappings:
        start = int(row["start"])
        if start not in unique_starts:
            unique_starts.append(start)

    report.append(f"[Phase6AX] UNIQUE LOOP FUNCTIONS: {len(unique_starts)}")
    for start in unique_starts:
        row = by_va.get(start)
        gen = generated.get(start)
        if not row:
            continue
        report.append(
            f"[Phase6AX] FUNCTION {row['name']} "
            f"0x{start:08X}-0x{int(row['end']):08X} "
            f"file={gen['file'] if gen else '<missing>'}"
        )
    report.append("")

    for va, row in mappings:
        start = int(row["start"])
        gen = generated.get(start)
        report.append("=" * 88)
        report.append(
            f"[Phase6AX] SOURCE AROUND VA 0x{va:08X} "
            f"in {row['name']} 0x{start:08X}-0x{int(row['end']):08X}"
        )
        if not gen:
            report.append("[Phase6AX] generated body missing")
            continue

        snippet = source_lines_around(gen["source"], va)
        if not snippet:
            if va == start:
                lines = gen["source"].splitlines()
                snippet = [f"{i+1:05d}: {lines[i]}" for i in range(min(24, len(lines)))]
                report.append("[Phase6AX] function-start fallback snippet")
            else:
                report.append("[Phase6AX] loc label not found in generated body")
                continue

        report.extend(snippet)

    report.append("")
    report.append("=" * 88)
    report.append("[Phase6AX] LOOP-FUNCTION MEMORY / CALL / BRANCH SURVEY")
    interesting = re.compile(
        r"(GUEST_(?:READ|WRITE)|RECOMP_(?:ICALL|ITAIL|CALL)|"
        r"if\s*\(|while\s*\(|goto\s+loc_|"
        r"eax\s*=|ebx\s*=|ecx\s*=|edx\s*=|esi\s*=|edi\s*=)",
        re.I,
    )
    for start in unique_starts:
        row = by_va.get(start)
        gen = generated.get(start)
        if not row or not gen:
            continue
        report.append(
            f"[Phase6AX] SURVEY {row['name']} "
            f"0x{start:08X}-0x{int(row['end']):08X}"
        )
        count = 0
        for i, line in enumerate(gen["source"].splitlines(), 1):
            if interesting.search(line):
                report.append(f"{i:05d}: {line}")
                count += 1
                if count >= 160:
                    report.append("[Phase6AX] ...survey truncated at 160 matching lines...")
                    break
        if count == 0:
            report.append("[Phase6AX] no matching memory/call/branch lines")

    args.out.parent.mkdir(parents=True, exist_ok=True)
    payload = "\n".join(report) + "\n"
    args.out.write_text(payload, encoding="utf-8")

    print(payload)
    print(f"[Phase6AX] REPORT: {args.out}")
    print("[Phase6AX] SOURCE CORRELATION RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
