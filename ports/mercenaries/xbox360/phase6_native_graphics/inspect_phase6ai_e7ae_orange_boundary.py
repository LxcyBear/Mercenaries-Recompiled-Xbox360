#!/usr/bin/env python3
"""Phase 6AI forensic preflight for the 6AH-D orange boundary.

6AH-D hardware proved the D3D root 0x0028E700 and the diagnostic-only sync
checkpoint path, then faulted on READ32 0x80000004 with EAX=0x80000000 after
sync phase 3 and before phase 4.

This tool intentionally does NOT change memory semantics. The first KSEG page
is a deliberate null/kernel-alias fence. Instead, inspect the exact translated
sub_0028E700 body already emitted by 6AH-D and capture the loc_0028E7AE block
that leads to the fault. If the local regenerated body differs from the
expected retail shape, stop before any build.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6AH-D3D-SYNC-0028E700-20261023-D"
ROOT_NAME = "sub_0028E700"
LABEL = "loc_0028E7AE:"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AI] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def extract_function(text: str, base) -> tuple[str, int, int]:
    masked = base.mask_noncode(text)
    match = re.search(
        rf"(?m)^(?:static\s+)?void\s+{re.escape(ROOT_NAME)}\s*\(\s*void\s*\)\s*\{{",
        masked,
    )
    if not match:
        raise SystemExit("[Phase6AI] exact translated sub_0028E700 body missing from 6AH-D cache")
    open_brace = masked.find("{", match.start(), match.end())
    close_brace = base.closing_brace(masked, open_brace)
    return text[match.start():close_brace], match.start(), close_brace


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    main_path = args.base_dir / "main_monolithic.cpp"
    manifest_path = args.base_dir / "phase6ah-manifest.json"
    if not main_path.exists() or not manifest_path.exists():
        raise SystemExit("[Phase6AI] cached Phase 6AH-D output is missing")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6AH" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AI] cached Phase 6AH-D baseline identity mismatch")

    ah = manifest.get("phase6ah_d3d_saturation") or {}
    if (
        ah.get("root") != "0x0028E700"
        or ah.get("phase6ag_hardware_pass") is not True
        or ah.get("native_createdevice_handoff_inherited_unchanged") is not True
    ):
        raise SystemExit("[Phase6AI] inherited 6AH model drift")

    text = main_path.read_text(encoding="utf-8")
    base = load(args.base_emitter, "phase6ai_base")
    function, start, end = extract_function(text, base)

    label_pos = function.find(LABEL)
    if label_pos < 0:
        raise SystemExit("[Phase6AI] loc_0028E7AE label missing from translated root")

    all_lines = function.splitlines()
    label_line = next(
        (i for i, line in enumerate(all_lines) if LABEL in line),
        None,
    )
    if label_line is None:
        raise SystemExit("[Phase6AI] could not resolve E7AE source line")

    # 6AI-A proved E7AE itself is only POP/RET. Hardware stopped after sync
    # phase 3 and before phase 4, so inspect the predecessor region feeding
    # E7AE instead of the return block.
    prev_label_line = 0
    prev_label_name = "<function-entry>"
    for index in range(label_line - 1, -1, -1):
        stripped = all_lines[index].strip()
        if re.match(r"^loc_[0-9A-Fa-f]+:\\s*;?$", stripped):
            prev_label_line = index
            prev_label_name = stripped
            break

    block_first = max(prev_label_line, label_line - 80)
    block_last = min(len(all_lines), label_line + 6)
    block_lines = all_lines[block_first:block_last]
    block = "\n".join(
        f"{block_first + i + 1:04d}: {line}"
        for i, line in enumerate(block_lines)
    ) + "\n"

    # Wider context makes register/address provenance visible even if the
    # faulting read is expressed through a register other than EAX.
    wide_first = max(0, label_line - 96)
    wide_last = min(len(all_lines), label_line + 24)
    wide_lines = all_lines[wide_first:wide_last]
    wide = "\n".join(
        f"{wide_first + i + 1:04d}: {line}"
        for i, line in enumerate(wide_lines)
    ) + "\n"

    # Compile the forensic patterns up front. This is intentionally a
    # preflight assertion: malformed regex must fail here before report logic.
    eax_plus4_pattern = re.compile(
        r"(?:GUEST_READ32|MEM32)\s*\(\s*eax\s*\+\s*(?:4|0x4)\s*\)"
    )
    offset4_pattern = re.compile(r"\+\s*(?:4|0x4)\s*\)")

    mem32 = []
    for i, line in enumerate(wide_lines, start=wide_first + 1):
        if "GUEST_READ32" in line or "MEM32" in line:
            mem32.append({"line": i, "source": line.strip()})

    eax_plus4 = [
        row for row in mem32
        if eax_plus4_pattern.search(row["source"])
    ]
    offset4_reads = [
        row for row in mem32
        if offset4_pattern.search(row["source"])
    ]

    if eax_plus4:
        classification = "eax_plus_4_textual_candidate"
    elif offset4_reads:
        classification = "other_plus_4_read_candidate"
    else:
        classification = "no_plus_4_read_in_context"

    args.out_dir.mkdir(parents=True, exist_ok=True)
    report_txt = args.out_dir / "phase6ai-e7ae-context.txt"
    report_json = args.out_dir / "phase6ai-e7ae-context.json"

    report_txt.write_text(
        "PHASE 6AI - 0028E700 / E7AE FORENSIC CONTEXT\n"
        f"baseline={BASE_TAG}\n"
        "hardware_fault=READ32 0x80000004\n"
        "hardware_eax=0x80000000\n"
        "hardware_checkpoint_last_phase=3\n"
        f"classification={classification}\n"
        f"function_chars={len(function)} source_range={start}:{end}\n\n"
        "=== PRE-E7AE WINDOW ===\n"
        + block
        + "\n=== WIDE CONTEXT ===\n"
        + wide
        + "\n=== MEMORY READ EXPRESSIONS ===\n"
        + "\n".join(f"{row['line']:04d}: {row['source']}" for row in mem32)
        + "\n",
        encoding="utf-8",
    )

    report_json.write_text(
        json.dumps(
            {
                "phase": "6AI-C",
                "baseline": BASE_TAG,
                "root": "0x0028E700",
                "label": "0x0028E7AE",
                "hardware": {
                    "boundary": "GUEST_FAULT",
                    "access": "READ",
                    "width": 4,
                    "guest": "0x80000004",
                    "eax": "0x80000000",
                    "last_sync_phase": 3,
                    "sync_calls": 6,
                },
                "classification": classification,
                "predecessor_label": prev_label_name,
                "eax_plus_4_candidates": eax_plus4,
                "offset4_read_candidates": offset4_reads,
                "memory_expressions": mem32,
                "exact_block": block,
                "wide_context": wide,
            },
            indent=2,
        ) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AI] ORANGE BOUNDARY FORENSIC: PASS")
    print(f"[Phase6AI] Root: 0x0028E700 / label 0x0028E7AE")
    print(f"[Phase6AI] Hardware: READ32 80000004 with EAX=80000000 after sync phase 3")
    print(f"[Phase6AI] Classification: {classification}")
    print(f"[Phase6AI] Predecessor label: {prev_label_name}")
    if eax_plus4:
        for row in eax_plus4:
            print(f"[Phase6AI] EAX+4 candidate line {row['line']}: {row['source']}")
    elif offset4_reads:
        for row in offset4_reads:
            print(f"[Phase6AI] +4 read candidate line {row['line']}: {row['source']}")
    print(f"[Phase6AI] REPORT: {report_txt}")
    print("[Phase6AI] NO BUILD BY DESIGN - inspect the exact block before changing KSEG/memory semantics")
    print("[Phase6AI] PRE-E7AE WINDOW BEGIN")
    for line in block.rstrip().splitlines():
        print(f"[Phase6AI] | {line}")
    print("[Phase6AI] PRE-E7AE WINDOW END")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
