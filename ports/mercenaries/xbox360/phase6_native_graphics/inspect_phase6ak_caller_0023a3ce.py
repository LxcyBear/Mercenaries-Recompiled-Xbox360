#!/usr/bin/env python3
"""Phase 6AK-A: inspect the caller after the 6AJ orange-boundary proof.

6AJ hardware proved sub_0028E700 reaches its return path (probe step 10),
while the eventual guest fault is still READ32 0x80000004 and the boundary
caller is 0x0023A3CE. This forensic pass inspects the exact cached translated
caller source and prints the neighborhood around calls/returns involving
sub_0028E700. It does not change guest semantics and does not build an XEX.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
CALLER_VA = 0x0023A3CE
ROOT_VA = 0x0028E700
CALLER_NAME = "sub_0023A3CE"
ROOT_NAME = "sub_0028E700"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AK] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_function(text: str, base, name: str) -> tuple[str, int, int]:
    masked = base.mask_noncode(text)
    signature = f"static void {name}(void)"
    defs: list[tuple[int, int]] = []
    cursor = 0
    while True:
        pos = masked.find(signature, cursor)
        if pos < 0:
            break
        after = pos + len(signature)
        probe = after
        while probe < len(masked) and masked[probe].isspace():
            probe += 1
        if probe < len(masked) and masked[probe] == "{":
            defs.append((pos, probe))
        cursor = after
    if not defs:
        raise SystemExit(f"[Phase6AK] exact translated {name} definition missing")
    if len(defs) != 1:
        raise SystemExit(
            f"[Phase6AK] expected one translated {name} definition, found {len(defs)}"
        )
    start, brace = defs[0]
    end = base.closing_brace(masked, brace)
    return text[start:end], start, end


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    main_path = args.base_dir / "main_monolithic.cpp"
    manifest_path = args.base_dir / "phase6aj-manifest.json"
    if not main_path.exists() or not manifest_path.exists():
        raise SystemExit("[Phase6AK] cached Phase 6AJ-A output is missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AK] cached Phase 6AJ-A baseline identity mismatch")

    aj = manifest.get("phase6aj_d3d_orange_source_probe") or {}
    if (
        aj.get("probe_only") is not True
        or aj.get("guest_semantics_changed") is not False
        or aj.get("phase6ai_hardware", {}).get("next_boundary", {}).get("guest")
           != "0x80000004"
    ):
        raise SystemExit("[Phase6AK] inherited 6AJ probe model drift")

    base = load(args.base_emitter, "phase6ak_base")
    text = main_path.read_text(encoding="utf-8")
    caller, start, end = find_function(text, base, CALLER_NAME)
    lines = caller.splitlines()

    call_hits: list[int] = []
    root_mentions: list[int] = []
    for i, line in enumerate(lines):
        if ROOT_NAME in line:
            root_mentions.append(i)
            if re.search(rf"\b{ROOT_NAME}\s*\(\s*\)\s*;", line):
                call_hits.append(i)

    # If a direct call was transformed into a dispatch form, retain every
    # textual root mention instead of falsely reporting no evidence.
    anchors = call_hits or root_mentions

    interesting: list[dict] = []
    for i, line in enumerate(lines):
        stripped = line.strip()
        if (
            "GUEST_READ" in stripped
            or "GUEST_WRITE" in stripped
            or "RECOMP_" in stripped
            or "0x80000000" in stripped
            or "80000000" in stripped
            or re.search(r"\beax\s*\+\s*(?:4|0x4)\b", stripped)
            or re.search(r"\b(?:eax|ecx|edx|esi|edi|ebx)\s*=\s*0x80000000", stripped)
        ):
            interesting.append({"line": i + 1, "source": stripped})

    windows: list[dict] = []
    if anchors:
        for anchor in anchors:
            first = max(0, anchor - 28)
            last = min(len(lines), anchor + 90)
            payload = "\n".join(
                f"{i+1:04d}: {lines[i]}" for i in range(first, last)
            )
            windows.append(
                {
                    "anchor_line": anchor + 1,
                    "first_line": first + 1,
                    "last_line": last,
                    "source": payload + "\n",
                }
            )
    else:
        # Still emit the whole beginning/end diagnostic if no explicit root
        # call survived textual lowering.
        first = 0
        last = min(len(lines), 180)
        windows.append(
            {
                "anchor_line": None,
                "first_line": 1,
                "last_line": last,
                "source": "\n".join(
                    f"{i+1:04d}: {lines[i]}" for i in range(first, last)
                ) + "\n",
            }
        )

    eax_plus4 = [
        row for row in interesting
        if re.search(r"GUEST_READ(?:8|16|32|64|F32|F64)\s*\(\s*eax\s*\+\s*(?:4|0x4)\s*\)",
                     row["source"], re.IGNORECASE)
    ]
    eax_8000 = [
        row for row in interesting
        if re.search(r"\beax\s*=\s*0x80000000u?\b", row["source"], re.IGNORECASE)
    ]

    args.out_dir.mkdir(parents=True, exist_ok=True)
    txt = args.out_dir / "phase6ak-caller-0023a3ce.txt"
    js = args.out_dir / "phase6ak-caller-0023a3ce.json"

    text_report = [
        "PHASE 6AK-A CALLER FORENSIC",
        f"baseline={BASE_TAG}",
        f"caller=0x{CALLER_VA:08X}",
        f"root=0x{ROOT_VA:08X}",
        "hardware_fault=READ32 0x80000004",
        "hardware_probe_step=10 (root return path reached)",
        f"caller_source_range={start}:{end}",
        f"caller_lines={len(lines)}",
        f"root_mentions={len(root_mentions)} direct_call_hits={len(call_hits)}",
        f"eax_plus4_reads={len(eax_plus4)} eax_80000000_assignments={len(eax_8000)}",
        "",
    ]

    for idx, window in enumerate(windows):
        text_report.append(
            f"=== CALLER WINDOW {idx+1} anchor={window['anchor_line']} "
            f"lines={window['first_line']}-{window['last_line']} ==="
        )
        text_report.append(window["source"])

    text_report.append("=== INTERESTING MEMORY/REGISTER LINES ===")
    for row in interesting:
        text_report.append(f"{row['line']:04d}: {row['source']}")

    txt.write_text("\n".join(text_report) + "\n", encoding="utf-8")
    js.write_text(
        json.dumps(
            {
                "phase": "6AK-A",
                "baseline": BASE_TAG,
                "caller": f"0x{CALLER_VA:08X}",
                "root": f"0x{ROOT_VA:08X}",
                "hardware": {
                    "fault": "READ32 0x80000004",
                    "probe_step": 10,
                    "interpretation": "sub_0028E700 reached return path before boundary",
                },
                "root_mentions": [i + 1 for i in root_mentions],
                "direct_call_hits": [i + 1 for i in call_hits],
                "eax_plus4_reads": eax_plus4,
                "eax_80000000_assignments": eax_8000,
                "interesting_lines": interesting,
                "windows": windows,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AK] CALLER FORENSIC: PASS")
    print(f"[Phase6AK] Caller: 0x{CALLER_VA:08X} ({CALLER_NAME})")
    print(f"[Phase6AK] Root mentions: {len(root_mentions)} direct calls: {len(call_hits)}")
    print(f"[Phase6AK] EAX+4 reads: {len(eax_plus4)}")
    print(f"[Phase6AK] EAX=80000000 assignments: {len(eax_8000)}")
    print(f"[Phase6AK] REPORT: {txt}")
    print("[Phase6AK] NO BUILD BY DESIGN")
    for idx, window in enumerate(windows):
        print(f"[Phase6AK] CALLER WINDOW {idx+1} BEGIN")
        for line in window["source"].rstrip().splitlines():
            print(f"[Phase6AK] | {line}")
        print(f"[Phase6AK] CALLER WINDOW {idx+1} END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
