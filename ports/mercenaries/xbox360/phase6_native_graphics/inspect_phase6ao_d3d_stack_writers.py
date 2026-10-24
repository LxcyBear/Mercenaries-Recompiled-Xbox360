#!/usr/bin/env python3
"""Phase 6AO-A: PC-only audit of exact Mercenaries D3D +1A10 state-stack writers.

6AN-B hardware proved sub_0028BC60 enters with [device+0x1A10] == 0, then
underflows EDX and walks backward until it finds 0x80000000 at device+0x5C.
Do not guess a synthetic stack depth. This forensic pass identifies:
  * every translated function referencing +1A04..+1A1C;
  * every write to +1A10/+1A14/+1A18/+1A1C or their absolute guest VAs;
  * every direct call to sub_0028BC60;
  * references to the exact guest device/global addresses.

No source is modified and no XEX is built.
"""
from __future__ import annotations

import argparse
import bisect
import importlib.util
import json
import re
from pathlib import Path

PHASE = "6AO-A"
BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
DEVICE = 0x00299380
GLOBAL = 0x00299378
TARGET = "sub_0028BC60"
OFFSETS = [0x1A04, 0x1A08, 0x1A0C, 0x1A10, 0x1A14, 0x1A18, 0x1A1C]
STACK_OFFSETS = [0x1A10, 0x1A14, 0x1A18, 0x1A1C]


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AO] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def function_va(name: str) -> str | None:
    m = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
    return f"0x{m.group(1).upper()}" if m else None


def classify_line(line: str) -> str:
    if "GUEST_WRITE" in line:
        return "WRITE"
    if "GUEST_READ" in line:
        return "READ"
    return "REF"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    main_path = args.base_dir / "main_monolithic.cpp"
    manifest_path = args.base_dir / "phase6aj-manifest.json"
    if not main_path.exists() or not manifest_path.exists():
        raise SystemExit("[Phase6AO] cached 6AJ baseline missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AO] cached 6AJ baseline identity mismatch")

    base = load(args.base_emitter, "phase6ao_base")
    text = main_path.read_text(encoding="utf-8", errors="replace")
    masked = base.mask_noncode(text)
    lines = text.splitlines()

    # Precompute newline offsets once. Repeated text.count(..., 0, pos) calls
    # over this multi-megabyte translation unit turn a simple function scan into
    # quadratic work.
    newline_offsets = [i for i, ch in enumerate(text) if ch == "\n"]

    funcs = []
    matches = list(base.FUNC_RE.finditer(masked))
    total_matches = len(matches)
    print(f"[Phase6AO] Function index      : {total_matches} translated definitions", flush=True)
    for idx, m in enumerate(matches, start=1):
        brace = masked.find("{", m.start(), m.end())
        if brace < 0:
            continue
        end = base.closing_brace(masked, brace)
        name = m.group(1)
        start_line = bisect.bisect_right(newline_offsets, m.start()) + 1
        end_line = bisect.bisect_right(newline_offsets, end) + 1
        funcs.append((m.start(), end, name, start_line, end_line))
        if idx % 5000 == 0 or idx == total_matches:
            print(
                f"[Phase6AO] Index progress      : {idx}/{total_matches}",
                flush=True,
            )

    refs = []
    writes = []
    callers = []
    device_refs = []

    offset_tokens = {}
    for off in OFFSETS:
        offset_tokens[off] = [
            f"0x{off:X}", f"0x{off:x}",
            f"0x{DEVICE + off:08X}", f"0x{DEVICE + off:08x}",
        ]

    total_funcs = len(funcs)
    for func_idx, (start, end, name, start_line, end_line) in enumerate(funcs, start=1):
        body = text[start:end]
        body_lines = body.splitlines()
        body_abs_start = start_line

        if f"{TARGET}();" in body:
            hit_lines = []
            for i, line in enumerate(body_lines, start=body_abs_start):
                if f"{TARGET}();" in line:
                    hit_lines.append({"line": i, "source": line.strip()})
            callers.append({
                "function": name,
                "va": function_va(name),
                "range": [start_line, end_line],
                "hits": hit_lines,
            })

        for i, line in enumerate(body_lines, start=body_abs_start):
            for off, tokens in offset_tokens.items():
                if any(tok.lower() in line.lower() for tok in tokens):
                    row = {
                        "function": name,
                        "va": function_va(name),
                        "line": i,
                        "offset": f"0x{off:X}",
                        "absolute": f"0x{DEVICE + off:08X}",
                        "kind": classify_line(line),
                        "source": line.strip(),
                    }
                    refs.append(row)
                    if off in STACK_OFFSETS and row["kind"] == "WRITE":
                        writes.append(row)

            if any(tok.lower() in line.lower() for tok in (
                "0x00299380", "0x299380", "0x00299378", "0x299378"
            )):
                device_refs.append({
                    "function": name,
                    "va": function_va(name),
                    "line": i,
                    "kind": classify_line(line),
                    "source": line.strip(),
                })

        if func_idx % 5000 == 0 or func_idx == total_funcs:
            print(
                f"[Phase6AO] Audit progress      : {func_idx}/{total_funcs}",
                flush=True,
            )

    # Also capture non-function/global occurrences for exact absolute addresses.
    global_hits = []
    for i, line in enumerate(lines, start=1):
        low = line.lower()
        if any(f"0x{DEVICE + off:08x}" in low for off in OFFSETS):
            global_hits.append({"line": i, "source": line.strip()})

    # Produce contextual windows for the most actionable functions: writers and callers.
    interesting_names = []
    for row in writes:
        if row["function"] not in interesting_names:
            interesting_names.append(row["function"])
    for row in callers:
        if row["function"] not in interesting_names:
            interesting_names.append(row["function"])

    windows = []
    for name in interesting_names:
        entry = next((f for f in funcs if f[2] == name), None)
        if entry is None:
            continue
        _, _, _, sl, el = entry
        hit_lines = sorted({
            r["line"] for r in refs if r["function"] == name
        } | {
            h["line"] for c in callers if c["function"] == name for h in c["hits"]
        })
        if not hit_lines:
            continue
        lo = max(sl, min(hit_lines) - 24)
        hi = min(el, max(hit_lines) + 36)
        windows.append({
            "function": name,
            "va": function_va(name),
            "range": [sl, el],
            "window": [
                f"{n:07d}: {lines[n-1]}" for n in range(lo, hi + 1)
            ],
        })

    report = {
        "phase": PHASE,
        "baseline": BASE_TAG,
        "hardware": {
            "device": "0x00299380",
            "fault": "READ32 0x80000004",
            "target": "0x0028BC60",
            "count": 0,
            "sentinel_edx": "0xFFFFF993",
            "sentinel_hits": 1,
        },
        "offsets": [f"0x{x:X}" for x in OFFSETS],
        "references": refs,
        "stack_writes": writes,
        "direct_callers": callers,
        "device_global_refs": device_refs,
        "global_absolute_hits": global_hits,
        "windows": windows,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    txt_path = args.out_dir / "phase6ao-d3d-stack-writer-audit.txt"
    json_path = args.out_dir / "phase6ao-d3d-stack-writer-audit.json"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    out = []
    out.append("Phase 6AO-A exact D3D stack writer audit")
    out.append(f"baseline={BASE_TAG}")
    out.append("hardware=count=0 target=0x0028BC60 fault=READ32 0x80000004")
    out.append(f"references={len(refs)} stack_writes={len(writes)} direct_callers={len(callers)}")
    out.append("")
    out.append("STACK WRITES")
    if writes:
        for r in writes:
            out.append(
                f"{r['function']} {r['va'] or '-'} L{r['line']} "
                f"{r['offset']} {r['source']}"
            )
    else:
        out.append("<none>")
    out.append("")
    out.append("DIRECT CALLERS OF sub_0028BC60")
    if callers:
        for c in callers:
            out.append(
                f"{c['function']} {c['va'] or '-'} range={c['range'][0]}..{c['range'][1]}"
            )
            for h in c["hits"]:
                out.append(f"  L{h['line']}: {h['source']}")
    else:
        out.append("<none>")
    out.append("")
    out.append("ALL +1Axx REFERENCES")
    for r in refs:
        out.append(
            f"{r['function']} {r['va'] or '-'} L{r['line']} "
            f"{r['kind']} {r['offset']} {r['source']}"
        )
    out.append("")
    out.append("ACTIONABLE WINDOWS")
    for w in windows:
        out.append(
            f"===== {w['function']} {w['va'] or '-'} "
            f"{w['range'][0]}..{w['range'][1]} ====="
        )
        out.extend(w["window"])
        out.append("===== END =====")
        out.append("")

    txt_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    print("[Phase6AO] D3D STACK WRITER AUDIT: PASS")
    print(f"[Phase6AO] +1Axx references : {len(refs)}")
    print(f"[Phase6AO] stack writes      : {len(writes)}")
    print(f"[Phase6AO] direct callers    : {len(callers)}")
    print(f"[Phase6AO] report            : {txt_path}")
    print("[Phase6AO] NO BUILD BY DESIGN")
    print("[Phase6AO] STACK WRITES BEGIN")
    if writes:
        for r in writes:
            print(
                f"[Phase6AO] | {r['function']} {r['va'] or '-'} "
                f"L{r['line']} {r['offset']} {r['source']}"
            )
    else:
        print("[Phase6AO] | <none>")
    print("[Phase6AO] STACK WRITES END")
    print("[Phase6AO] DIRECT CALLERS BEGIN")
    if callers:
        for c in callers:
            print(f"[Phase6AO] | {c['function']} {c['va'] or '-'}")
            for h in c["hits"]:
                print(f"[Phase6AO] |   L{h['line']}: {h['source']}")
    else:
        print("[Phase6AO] | <none>")
    print("[Phase6AO] DIRECT CALLERS END")
    for w in windows:
        print(f"[Phase6AO] WINDOW {w['function']} BEGIN")
        for row in w["window"]:
            print(f"[Phase6AO] | {row}")
        print(f"[Phase6AO] WINDOW {w['function']} END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
