#!/usr/bin/env python3
"""Phase 6AS-A: inspect the exact contiguous-allocation policy exposed by 6AR.

6AR hardware proved the orange D3D corruption is gone:
  * sub_0028F9E0 runs;
  * device+0x1A10 changes 0 -> 2;
  * the old READ32 0x80000004 disappears.

The new controlled renderer-fatal is E_OUTOFMEMORY (0x8007000E):
  * the retail graphics pool claim reserves 0x1680000 bytes at 0x02880000,
    moving page_next from 0x03F00000 to 0x02880000;
  * a later 0x258000-byte contiguous request from sub_0028F9E0 returns 0,
    even though a large guest gap remains below 0x02880000.

This PC-only audit extracts the exact generated support code around:
  - the Mm166 wrapper provenance logic;
  - the retail graphics-pool claim;
  - the normal MmAllocateContiguousMemoryEx allocator;
  - the BE800000 fallback path currently labelled "audio fallback".

No source is modified and no XEX is built.
"""
from __future__ import annotations

import argparse
import bisect
import json
import re
from pathlib import Path

PHASE = "6AS-A"
BASE_TAG = "P6AR-POST-CREATE-STATE-INIT-20261024-A"

MARKERS = (
    "Mm166 wrapper provenance",
    "retail graphics pool claim",
    "MmAllocateContiguousMemoryEx size=",
    "audio fallback allocation failed",
    "audio alloc failure-test hook",
)

SIGNATURE_RE = re.compile(
    r"(?m)^(?:static\s+)?(?:void|bool|int|uint32_t|uint64_t|DWORD|HRESULT|"
    r"size_t|long|unsigned\s+int)\s+"
    r"([A-Za-z_][A-Za-z0-9_]*)\s*\([^;{}]*\)\s*\{"
)


def nearest_signature(text: str, pos: int) -> str:
    lo = max(0, pos - 50000)
    chunk = text[lo:pos]
    hits = list(SIGNATURE_RE.finditer(chunk))
    if not hits:
        return "<unknown>"
    return hits[-1].group(1)


def numbered(lines: list[str], start: int, end: int) -> list[str]:
    start = max(1, start)
    end = min(len(lines), end)
    return [f"{i:07d}: {lines[i-1]}" for i in range(start, end + 1)]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    main_path = args.base_dir / "main_monolithic.cpp"
    manifest_path = args.base_dir / "phase6ar-manifest.json"
    if not main_path.exists() or not manifest_path.exists():
        raise SystemExit("[Phase6AS] cached Phase 6AR-A output missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AR" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AS] cached Phase 6AR-A identity mismatch")

    text = main_path.read_text(encoding="utf-8", errors="replace")
    lines = text.splitlines()
    newline_offsets = [i for i, ch in enumerate(text) if ch == "\n"]

    hits = []
    for marker in MARKERS:
        start = 0
        while True:
            pos = text.find(marker, start)
            if pos < 0:
                break
            line = bisect.bisect_right(newline_offsets, pos) + 1
            hits.append({
                "marker": marker,
                "line": line,
                "function": nearest_signature(text, pos),
                "window_start": max(1, line - 120),
                "window_end": min(len(lines), line + 180),
            })
            start = pos + len(marker)

    if not hits:
        raise SystemExit("[Phase6AS] allocator trace markers not found")

    # Deduplicate heavily-overlapping windows while preserving every marker.
    groups = []
    for hit in sorted(hits, key=lambda h: h["line"]):
        if groups and hit["window_start"] <= groups[-1]["end"] + 40:
            groups[-1]["end"] = max(groups[-1]["end"], hit["window_end"])
            groups[-1]["hits"].append(hit)
        else:
            groups.append({
                "start": hit["window_start"],
                "end": hit["window_end"],
                "hits": [hit],
            })

    # Collect likely allocator state symbols from extracted windows.
    symbol_re = re.compile(r"\b(?:s_phase[0-9A-Za-z_]+|g_[A-Za-z0-9_]*(?:page|heap|alloc|reserve)[A-Za-z0-9_]*)\b", re.I)
    symbols = []
    for group in groups:
        blob = "\n".join(lines[group["start"]-1:group["end"]])
        for sym in symbol_re.findall(blob):
            if sym not in symbols:
                symbols.append(sym)

    # Global occurrence index for discovered allocator-state symbols.
    symbol_occurrences = {}
    for sym in symbols[:80]:
        rows = []
        for i, line in enumerate(lines, start=1):
            if sym in line:
                rows.append({"line": i, "source": line.strip()})
                if len(rows) >= 40:
                    break
        symbol_occurrences[sym] = rows

    report = {
        "phase": PHASE,
        "baseline": BASE_TAG,
        "hardware": {
            "graphics_claim_base": "0x02880000",
            "graphics_claim_size": "0x01680000",
            "old_page_next": "0x03F00000",
            "new_page_next": "0x02880000",
            "followup_request_size": "0x00258000",
            "followup_result": "0x00000000",
            "initializer_hresult": "0x8007000E",
            "count_before": 0,
            "count_after": 2,
        },
        "marker_hits": hits,
        "window_groups": groups,
        "allocator_symbols": symbols,
        "symbol_occurrences": symbol_occurrences,
    }

    args.out_dir.mkdir(parents=True, exist_ok=True)
    json_path = args.out_dir / "phase6as-contiguous-allocator-audit.json"
    txt_path = args.out_dir / "phase6as-contiguous-allocator-audit.txt"
    json_path.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    out = []
    out.append("Phase 6AS-A contiguous allocator audit")
    out.append(f"baseline={BASE_TAG}")
    out.append("hardware=graphics_claim 02880000+01680000 -> 03F00000")
    out.append("hardware=followup size=00258000 result=0 hr=8007000E count 0->2")
    out.append(f"marker_hits={len(hits)} windows={len(groups)} symbols={len(symbols)}")
    out.append("")
    out.append("MARKERS")
    for h in hits:
        out.append(
            f"L{h['line']} function={h['function']} marker={h['marker']}"
        )
    out.append("")
    out.append("ALLOCATOR WINDOWS")
    for n, group in enumerate(groups, start=1):
        out.append(
            f"===== WINDOW {n} lines={group['start']}..{group['end']} "
            f"markers={','.join(h['marker'] for h in group['hits'])} ====="
        )
        out.extend(numbered(lines, group["start"], group["end"]))
        out.append("===== END WINDOW =====")
        out.append("")
    out.append("ALLOCATOR STATE SYMBOL OCCURRENCES")
    for sym, rows in symbol_occurrences.items():
        out.append(f"===== SYMBOL {sym} =====")
        for row in rows:
            out.append(f"{row['line']:07d}: {row['source']}")
        out.append("")
    txt_path.write_text("\n".join(out) + "\n", encoding="utf-8")

    print("[Phase6AS] CONTIGUOUS ALLOCATOR AUDIT: PASS")
    print(f"[Phase6AS] marker hits          : {len(hits)}")
    print(f"[Phase6AS] merged windows      : {len(groups)}")
    print(f"[Phase6AS] allocator symbols   : {len(symbols)}")
    print(f"[Phase6AS] report              : {txt_path}")
    print("[Phase6AS] NO BUILD BY DESIGN")
    print("[Phase6AS] MARKER SUMMARY BEGIN")
    for h in hits:
        print(
            f"[Phase6AS] | L{h['line']} function={h['function']} "
            f"marker={h['marker']}"
        )
    print("[Phase6AS] MARKER SUMMARY END")
    print("[Phase6AS] ALLOCATOR WINDOWS BEGIN")
    for n, group in enumerate(groups, start=1):
        print(
            f"[Phase6AS] WINDOW {n} BEGIN "
            f"lines={group['start']}..{group['end']}"
        )
        for row in numbered(lines, group["start"], group["end"]):
            print(f"[Phase6AS] | {row}")
        print(f"[Phase6AS] WINDOW {n} END")
    print("[Phase6AS] ALLOCATOR WINDOWS END")
    print("[Phase6AS] STATE SYMBOLS BEGIN")
    for sym, rows in symbol_occurrences.items():
        print(f"[Phase6AS] SYMBOL {sym} BEGIN")
        for row in rows:
            print(f"[Phase6AS] | {row['line']:07d}: {row['source']}")
        print(f"[Phase6AS] SYMBOL {sym} END")
    print("[Phase6AS] STATE SYMBOLS END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
