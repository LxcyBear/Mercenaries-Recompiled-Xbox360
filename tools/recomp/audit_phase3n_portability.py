#!/usr/bin/env python3
"""Phase 3N portability audit for the complete patched/lowered generated tree."""

from __future__ import annotations

import argparse
import bisect
from collections import Counter
import json
from pathlib import Path
import re
import sys

from tools.recomp.lower_explicit_guest_memory import _mask_noncode


FATAL_PATTERNS = {
    "legacy_guest_memory": re.compile(
        r"\b(?:MEM8|MEM16|MEM32|MEM64|SMEM8|SMEM16|SMEM32|SMEM64|"
        r"MEMF|MEMD)\s*\("
    ),
    "raw_guest_pointer": re.compile(r"\bXBOX_PTR\s*\("),
    "x86_inline_asm": re.compile(r"\b(?:__asm|_asm)\b"),
    "x86_intrinsic": re.compile(
        r"\b(?:__rdtsc|__cpuid|__cpuidex|__m128|__m64|_mm_[A-Za-z0-9_]+)\b"
    ),
}

# These are intentionally *reported*, not rejected here. They identify the
# platform/service surface Phase 4+ must replace or bind natively.
PLATFORM_PATTERNS = {
    "win32": re.compile(
        r"\b(?:CreateFile[A-Z]?|ReadFile|WriteFile|CloseHandle|"
        r"QueryPerformanceCounter|VirtualAlloc|VirtualFree|Sleep)\s*\("
    ),
    "d3d_dxgi": re.compile(r"\b(?:D3D11|D3D9|Direct3D|DXGI|IDirect3D)\w*"),
    "audio": re.compile(r"\b(?:DirectSound|XAudio|XACT|IXACT|IDirectSound)\w*"),
}

SURFACE_PATTERNS = {
    "direct_call": re.compile(r"\bsub_[0-9A-Fa-f]{8}\s*\("),
    "icall": re.compile(r"\bRECOMP_ICALL(?:_SAFE)?\s*\("),
    "itail": re.compile(r"\bRECOMP_ITAIL(?:_SAFE)?\s*\("),
    "x87_round": re.compile(r"\b(?:X87_FIST16|X87_FIST32|X87_FIST64|x87_round_integral)\s*\("),
    "x87_stack": re.compile(r"\b(?:fp_push|fp_pop|fp_popp|fp_top|fp_st|fp_st1)\s*\("),
    "xmm": re.compile(r"\b(?:recomp_xmm_[A-Za-z0-9_]+|xmm[0-7]v?)\b"),
    "mmx": re.compile(r"\b(?:mm[0-7]|g_mm[0-7])\b"),
    "runtime_copy": re.compile(r"\b(?:XBOX_MEMCPY|XBOX_REP_MOVS)\s*\("),
    "guest_read": re.compile(r"\bGUEST_(?:S?READ|READF)(?:8|16|32|64)?\s*\("),
    "guest_write": re.compile(r"\bGUEST_(?:WRITE|WRITEF)(?:8|16|32|64)?\s*\("),
}


def line_number(text: str, offset: int) -> int:
    return text.count("\n", 0, offset) + 1


UNRESOLVED_STUB_RE = re.compile(
    r"void\s+(sub_[0-9A-Fa-f]{8})\s*\(\s*void\s*\)\s*\{[^\n]*?"
    r"/\*\s*0x([0-9A-Fa-f]{8}):\s*not detected;\s*minimal guest ret\s*\*/"
)


def extract_unresolved_entries(text: str) -> list[dict]:
    entries = []
    for match in UNRESOLVED_STUB_RE.finditer(text):
        entries.append({
            "name": match.group(1),
            "address": int(match.group(2), 16),
            "address_hex": f"0x{int(match.group(2), 16):08X}",
            "line": line_number(text, match.start()),
        })
    return entries


def load_function_ranges(path: Path) -> list[dict]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    rows = []
    for item in raw:
        try:
            start = int(str(item["start"]), 0)
            end = int(str(item["end"]), 0)
        except (KeyError, TypeError, ValueError):
            continue
        rows.append({
            "start": start,
            "end": end,
            "name": item.get("name", f"sub_{start:08X}"),
        })
    rows.sort(key=lambda row: row["start"])
    return rows


def classify_unresolved(entries: list[dict], functions_path: Path | None) -> dict:
    if not functions_path:
        return {"counts": {}, "entries": entries}
    functions = load_function_ranges(functions_path)
    starts = [row["start"] for row in functions]
    counts = Counter()
    classified = []

    for entry in entries:
        addr = entry["address"]
        row = dict(entry)
        idx = bisect.bisect_right(starts, addr) - 1

        if idx >= 0 and functions[idx]["start"] == addr:
            row["classification"] = "known_function_start"
            row["function"] = functions[idx]["name"]
        elif idx >= 0 and functions[idx]["start"] < addr < functions[idx]["end"]:
            parent = functions[idx]
            row["classification"] = "mid_function"
            row["parent_start"] = f"0x{parent['start']:08X}"
            row["parent_end"] = f"0x{parent['end']:08X}"
            row["parent_name"] = parent["name"]
            row["offset"] = addr - parent["start"]
        elif idx >= 0 and addr == functions[idx]["end"]:
            parent = functions[idx]
            row["classification"] = "boundary_continuation"
            row["parent_start"] = f"0x{parent['start']:08X}"
            row["parent_end"] = f"0x{parent['end']:08X}"
            row["parent_name"] = parent["name"]
            if idx + 1 < len(functions):
                row["next_start"] = f"0x{functions[idx + 1]['start']:08X}"
                row["gap_to_next"] = functions[idx + 1]["start"] - addr
        else:
            next_idx = idx + 1
            row["classification"] = "gap_or_outside"
            if idx >= 0:
                row["previous_end"] = f"0x{functions[idx]['end']:08X}"
                row["previous_name"] = functions[idx]["name"]
            if next_idx < len(functions):
                row["next_start"] = f"0x{functions[next_idx]['start']:08X}"
                row["next_name"] = functions[next_idx]["name"]

        counts[row["classification"]] += 1
        classified.append(row)

    return {"counts": dict(counts), "entries": classified}


def scan_file(path: Path) -> dict:
    text = path.read_text(encoding="utf-8", errors="replace")
    code = _mask_noncode(text)

    fatal = []
    for kind, pattern in FATAL_PATTERNS.items():
        for match in pattern.finditer(code):
            fatal.append({
                "kind": kind,
                "line": line_number(code, match.start()),
                "token": match.group(0),
            })

    platform = Counter()
    for kind, pattern in PLATFORM_PATTERNS.items():
        platform[kind] = len(pattern.findall(code))

    surfaces = Counter()
    for kind, pattern in SURFACE_PATTERNS.items():
        surfaces[kind] = len(pattern.findall(code))

    functions = len(re.findall(
        r"(?m)^\s*void\s+(?:sub_[0-9A-Fa-f]{8}|xbe_entry_point)\s*\(\s*void\s*\)",
        code,
    ))

    failed_stubs = len(re.findall(r"/\*\s*FAILED:", text))
    unresolved_entries = extract_unresolved_entries(text)
    residual_unresolved_stubs = len(unresolved_entries)
    return {
        "path": str(path),
        "bytes": len(text.encode("utf-8")),
        "functions": functions,
        "failed_stubs": failed_stubs,
        "residual_unresolved_stubs": residual_unresolved_stubs,
        "unresolved_entries": unresolved_entries,
        "fatal": fatal,
        "platform": dict(platform),
        "surfaces": dict(surfaces),
    }


def _function_spans(code: str) -> list[tuple[int, int, str]]:
    matches = list(re.finditer(
        r"(?m)^\s*void\s+(sub_[0-9A-Fa-f]{8}|xbe_entry_point)\s*"
        r"\(\s*void\s*\)\s*\{",
        code,
    ))
    spans = []
    for i, match in enumerate(matches):
        end = matches[i + 1].start() if i + 1 < len(matches) else len(code)
        spans.append((match.start(), end, match.group(1)))
    return spans


def _caller_function(spans: list[tuple[int, int, str]], offset: int) -> str | None:
    for start, end, name in spans:
        if start <= offset < end:
            return name
    return None


def scan_tree(root: Path, functions_path: Path | None = None) -> dict:
    files = sorted(root.glob("recomp_*.c"))
    if not files:
        raise FileNotFoundError(f"no recomp_*.c files in {root}")

    rows = [scan_file(path) for path in files]
    fatal = []
    platform = Counter()
    surfaces = Counter()
    for row in rows:
        for hit in row["fatal"]:
            fatal.append({"file": row["path"], **hit})
        platform.update(row["platform"])
        surfaces.update(row["surfaces"])

    unresolved_files = [
        row["path"] for row in rows if "stubs_unresolved" in Path(row["path"]).name
    ]
    unresolved_entries = []
    for row in rows:
        for entry in row["unresolved_entries"]:
            unresolved_entries.append({"file": row["path"], **entry})

    # A post-patch unresolved stub is only a real Gate-3 dependency if some
    # other generated C file still references its symbol. Mercenaries patches
    # repair a number of shared continuations by replacing synthetic sub_XXXX()
    # calls with local gotos, but the original auto-generated stub body remains
    # in recomp_stubs_unresolved.c. Count those dead bodies separately rather
    # than treating them as unresolved execution paths.
    live_entries = []
    dead_entries = []
    source_code = {}
    source_spans = {}
    for path in files:
        if "stubs_unresolved" in path.name:
            continue
        code_text = _mask_noncode(
            path.read_text(encoding="utf-8", errors="replace")
        )
        source_code[path] = code_text
        source_spans[path] = _function_spans(code_text)

    for entry in unresolved_entries:
        symbol = entry["name"]
        pattern = re.compile(r"\b" + re.escape(symbol) + r"\s*\(")
        references = []
        for path, code_text in source_code.items():
            path_refs = []
            for match in pattern.finditer(code_text):
                line_start = code_text.rfind("\n", 0, match.start()) + 1
                line_end = code_text.find("\n", match.end())
                if line_end < 0:
                    line_end = len(code_text)
                line_text = code_text[line_start:line_end].strip()

                # A replacement implementation is a resolution, not a caller.
                if re.match(
                    r"^void\s+" + re.escape(symbol) +
                    r"\s*\(\s*void\s*\)",
                    line_text,
                ):
                    continue

                path_refs.append({
                    "line": line_number(code_text, match.start()),
                    "text": line_text[:240],
                    "caller_function": _caller_function(
                        source_spans[path], match.start()
                    ),
                })
            if path_refs:
                references.append({
                    "file": str(path),
                    "count": len(path_refs),
                    "sites": path_refs,
                })
        row = dict(entry)
        row["references"] = references
        row["reference_count"] = sum(item["count"] for item in references)
        if references:
            live_entries.append(row)
        else:
            dead_entries.append(row)

    unresolved_classification = classify_unresolved(
        live_entries, functions_path
    )
    dead_unresolved_classification = classify_unresolved(
        dead_entries, functions_path
    )
    return {
        "root": str(root),
        "file_count": len(rows),
        "source_bytes": sum(row["bytes"] for row in rows),
        "function_bodies": sum(row["functions"] for row in rows),
        "failed_translation_stubs": sum(row["failed_stubs"] for row in rows),
        "residual_unresolved_stub_bodies": sum(
            row["residual_unresolved_stubs"] for row in rows
        ),
        "residual_unresolved_stubs": len(live_entries),
        "dead_unresolved_stub_bodies": len(dead_entries),
        "unresolved_stub_files": unresolved_files,
        "unresolved_classification": unresolved_classification,
        "dead_unresolved_classification": dead_unresolved_classification,
        "fatal_count": len(fatal),
        "fatal": fatal,
        "platform_surfaces": dict(platform),
        "translated_surfaces": dict(surfaces),
        "files": rows,
    }


def main(argv=None) -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("generated_root", type=Path)
    parser.add_argument("--output", type=Path)
    parser.add_argument("--functions", type=Path,
                        help="functions.json used to classify unresolved targets")
    args = parser.parse_args(argv)

    try:
        report = scan_tree(args.generated_root, args.functions)
    except (OSError, UnicodeError) as exc:
        print(f"FAIL: Phase 3N portability audit: {exc}", file=sys.stderr)
        return 1

    rendered = json.dumps(report, indent=2) + "\n"
    if args.output:
        args.output.parent.mkdir(parents=True, exist_ok=True)
        args.output.write_text(rendered, encoding="utf-8")

    print(
        "Phase 3N portability audit: "
        f"files={report['file_count']} functions={report['function_bodies']} "
        f"bytes={report['source_bytes']} fatal={report['fatal_count']} "
        f"failed_stubs={report['failed_translation_stubs']} "
        f"residual_unresolved={report['residual_unresolved_stubs']} "
        f"dead_stub_bodies={report['dead_unresolved_stub_bodies']}"
    )
    if report["platform_surfaces"]:
        print("Phase 4+ platform surfaces: " + ", ".join(
            f"{key}={value}" for key, value in sorted(
                report["platform_surfaces"].items()) if value
        ) or "none")

    unresolved_info = report.get("unresolved_classification", {})
    unresolved_counts = unresolved_info.get("counts", {})
    if unresolved_counts:
        print("LIVE residual unresolved classification: " + ", ".join(
            f"{key}={value}" for key, value in sorted(unresolved_counts.items())
        ))
        for entry in unresolved_info.get("entries", []):
            details = ""
            if entry.get("classification") == "mid_function":
                details = (
                    f" parent={entry.get('parent_name')}+0x{entry.get('offset', 0):X}"
                )
            elif entry.get("classification") == "boundary_continuation":
                details = f" parent={entry.get('parent_name')}"
            elif entry.get("classification") == "gap_or_outside":
                details = (
                    f" prev={entry.get('previous_name', '-')}"
                    f" next={entry.get('next_name', '-')}"
                )
            print(
                "  unresolved "
                f"{entry['address_hex']} {entry['name']}: "
                f"{entry.get('classification', 'unclassified')}{details} "
                f"refs={entry.get('reference_count', 0)}"
            )
            for ref in entry.get("references", []):
                for site in ref.get("sites", []):
                    caller_name = site.get("caller_function") or "-"
                    relation = ""
                    parent_name = entry.get("parent_name")
                    if parent_name:
                        relation = (
                            " same-parent" if caller_name == parent_name
                            else f" cross-parent->{parent_name}"
                        )
                    print(
                        f"    caller {caller_name} "
                        f"{Path(ref['file']).name}:{site['line']}:{relation} "
                        f"{site['text']}"
                    )

    dead_info = report.get("dead_unresolved_classification", {})
    dead_counts = dead_info.get("counts", {})
    if report.get("dead_unresolved_stub_bodies", 0):
        print(
            "Dead repaired unresolved stub bodies: "
            f"{report['dead_unresolved_stub_bodies']}"
            + (
                " (" + ", ".join(
                    f"{key}={value}" for key, value in sorted(dead_counts.items())
                ) + ")"
                if dead_counts else ""
            )
        )

    if report["fatal"]:
        print("FAIL: Gate-3-fatal generated portability leaks remain",
              file=sys.stderr)
        for hit in report["fatal"][:100]:
            print(
                f"{hit['file']}:{hit['line']}: "
                f"{hit['kind']}: {hit['token']}",
                file=sys.stderr,
            )
        if len(report["fatal"]) > 100:
            print(
                f"... {len(report['fatal']) - 100} additional fatal hit(s)",
                file=sys.stderr,
            )
        return 1

    print("PASS: no Gate-3-fatal host/x86/native-pointer surfaces in generated C")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
