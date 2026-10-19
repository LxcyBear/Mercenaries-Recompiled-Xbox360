#!/usr/bin/env python3
"""Phase 4A: exact Mercenaries kernel/platform surface audit.

Reads the supported retail XBE, enumerates its actual kernel imports, and
cross-checks them against the current kernel ordinal resolver and implementation
sources. This is a planning/proof tool: it does not modify generated code.
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from pathlib import Path

# Make repository packages importable when this file is launched directly.
_REPO_FROM_SCRIPT = Path(__file__).resolve().parents[4]
if str(_REPO_FROM_SCRIPT) not in sys.path:
    sys.path.insert(0, str(_REPO_FROM_SCRIPT))

from tools.xbe_parser.xbe_parser import XBEParser

EXPECTED_XBE_SHA256 = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
EXPECTED_TITLE_ID = 0x4C410015
EXPECTED_IMPORT_COUNT = 111

# These are deliberately evidence labels, not claims about whether an API has
# an Xbox 360 XDK equivalent. Phase 4B will review/replace them deliberately.
HOST_SURFACE_TOKENS = (
    "CreateFileW", "CreateFileA", "ReadFile", "WriteFile", "CloseHandle",
    "CreateThread", "CreateEvent", "CreateSemaphore", "CreateMutex",
    "WaitForSingleObject", "WaitForMultipleObjects", "VirtualAlloc",
    "VirtualFree", "VirtualProtect", "GetFileAttributesW", "SetFilePointer",
    "GetFileInformationByHandle", "GetDiskFreeSpaceEx", "FindFirstFile",
    "FindNextFile", "InitializeCriticalSection", "DeleteCriticalSection",
    "EnterCriticalSection", "LeaveCriticalSection", "QueryPerformanceCounter",
    "QueryPerformanceFrequency", "GetTickCount", "GetTickCount64",
    "Sleep", "WideCharToMultiByte", "MultiByteToWideChar",
)

STUB_HINTS = (
    "stub", "not implemented", "unimplemented", "TODO", "return STATUS_SUCCESS",
    "return XBOX_STATUS_SUCCESS", "return 0;", "(void)",
)


def mask_noncode(text: str) -> str:
    out = list(text)
    i = 0
    n = len(text)
    while i < n:
        if text.startswith("//", i):
            j = text.find("\n", i)
            if j < 0:
                j = n
            for k in range(i, j):
                out[k] = " "
            i = j
            continue
        if text.startswith("/*", i):
            j = text.find("*/", i + 2)
            j = n - 2 if j < 0 else j
            end = min(n, j + 2)
            for k in range(i, end):
                if out[k] != "\n":
                    out[k] = " "
            i = end
            continue
        if text[i] in ('"', "'"):
            quote = text[i]
            j = i + 1
            while j < n:
                if text[j] == "\\":
                    j += 2
                    continue
                if text[j] == quote:
                    j += 1
                    break
                j += 1
            for k in range(i, min(j, n)):
                if out[k] != "\n":
                    out[k] = " "
            i = j
            continue
        i += 1
    return "".join(out)


def extract_braced_body(text: str, brace_pos: int) -> str | None:
    depth = 0
    i = brace_pos
    n = len(text)
    while i < n:
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return text[brace_pos:i + 1]
        i += 1
    return None


def resolver_map(thunks_text: str) -> dict[int, str]:
    masked = mask_noncode(thunks_text)
    start = masked.find("ULONG_PTR xbox_resolve_ordinal")
    if start < 0:
        raise SystemExit("[Phase4A] could not find xbox_resolve_ordinal()")
    brace = masked.find("{", start)
    body = extract_braced_body(masked, brace)
    if body is None:
        raise SystemExit("[Phase4A] could not parse xbox_resolve_ordinal() body")

    mapping: dict[int, str] = {}
    pattern = re.compile(
        r"case\s+(\d+)\s*:\s*return\s*\(ULONG_PTR\)\s*([^;]+);"
    )
    for m in pattern.finditer(body):
        mapping[int(m.group(1))] = m.group(2).strip()
    return mapping


def find_function_body(symbol: str, sources: dict[Path, str]):
    pat = re.compile(
        r"(?m)^[^\n;{}]*\b" + re.escape(symbol) +
        r"\s*\([^;\n]*\)\s*\{"
    )
    for path, text in sources.items():
        masked = mask_noncode(text)
        m = pat.search(masked)
        if not m:
            continue
        brace = masked.find("{", m.start(), m.end())
        body = extract_braced_body(masked, brace)
        if body is not None:
            return path, body
    return None, None


def find_symbol_source(symbol: str, sources: dict[Path, str]):
    token = re.compile(r"\b" + re.escape(symbol) + r"\b")
    for path, text in sources.items():
        if token.search(mask_noncode(text)):
            return path
    return None


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--repo-root", type=Path, required=True)
    ap.add_argument("--xbe", type=Path, required=True)
    ap.add_argument("--json", dest="json_out", type=Path, required=True)
    ap.add_argument("--text", dest="text_out", type=Path, required=True)
    args = ap.parse_args()

    repo = args.repo_root.resolve()
    xbe_path = args.xbe.resolve()
    if not xbe_path.is_file():
        raise SystemExit(f"[Phase4A] retail XBE not found: {xbe_path}")

    actual_sha = hashlib.sha256(xbe_path.read_bytes()).hexdigest().upper()
    if actual_sha != EXPECTED_XBE_SHA256:
        raise SystemExit(
            f"[Phase4A] unsupported default.xbe: expected "
            f"{EXPECTED_XBE_SHA256}, got {actual_sha}"
        )

    xbe = XBEParser(str(xbe_path)).parse()
    if xbe.certificate.title_id != EXPECTED_TITLE_ID:
        raise SystemExit(
            f"[Phase4A] wrong title ID: 0x{xbe.certificate.title_id:08X}"
        )
    if len(xbe.kernel_imports) != EXPECTED_IMPORT_COUNT:
        raise SystemExit(
            f"[Phase4A] expected {EXPECTED_IMPORT_COUNT} Mercenaries kernel "
            f"imports, found {len(xbe.kernel_imports)}"
        )

    thunks_path = repo / "src" / "kernel" / "kernel_thunks.c"
    if not thunks_path.is_file():
        raise SystemExit(f"[Phase4A] missing resolver source: {thunks_path}")
    mapping = resolver_map(thunks_path.read_text(encoding="utf-8-sig"))

    source_paths = sorted((repo / "src" / "kernel").glob("*.c"))
    source_paths += sorted((repo / "src" / "platform").glob("*.c"))
    sources = {
        p: p.read_text(encoding="utf-8-sig", errors="replace")
        for p in source_paths
    }

    rows = []
    counts = {
        "imports": len(xbe.kernel_imports),
        "resolved": 0,
        "unresolved": 0,
        "callable": 0,
        "data": 0,
        "definition_missing": 0,
        "host_surface_flagged": 0,
        "stub_hint_flagged": 0,
    }

    for imp in xbe.kernel_imports:
        expr = mapping.get(imp.ordinal)
        row = {
            "slot": len(rows),
            "ordinal": imp.ordinal,
            "name": imp.name,
            "thunk_addr": f"0x{imp.thunk_addr:08X}",
            "resolver_expression": expr,
            "resolver_symbol": None,
            "kind": "unresolved",
            "source": None,
            "host_surface_tokens": [],
            "stub_hints": [],
        }

        if expr is None:
            counts["unresolved"] += 1
            rows.append(row)
            continue

        counts["resolved"] += 1
        symbol_match = re.search(r"\b(xbox_[A-Za-z0-9_]+)\b", expr)
        if not symbol_match:
            row["kind"] = "resolver-expression"
            counts["definition_missing"] += 1
            rows.append(row)
            continue

        symbol = symbol_match.group(1)
        row["resolver_symbol"] = symbol
        def_path, body = find_function_body(symbol, sources)
        if body is not None:
            row["kind"] = "callable"
            counts["callable"] += 1
            row["source"] = str(def_path.relative_to(repo)).replace("\\", "/")
            host_hits = [tok for tok in HOST_SURFACE_TOKENS if tok in body]
            stub_hits = [tok for tok in STUB_HINTS if tok.lower() in body.lower()]
            row["host_surface_tokens"] = host_hits
            row["stub_hints"] = stub_hits
            if host_hits:
                counts["host_surface_flagged"] += 1
            if stub_hits:
                counts["stub_hint_flagged"] += 1
        else:
            row["kind"] = "data"
            counts["data"] += 1
            src = find_symbol_source(symbol, sources)
            if src is not None:
                row["source"] = str(src.relative_to(repo)).replace("\\", "/")
            else:
                counts["definition_missing"] += 1

        rows.append(row)

    report = {
        "phase": "4A",
        "title": xbe.certificate.title_name,
        "title_id": f"0x{xbe.certificate.title_id:08X}",
        "retail_xbe_sha256": actual_sha,
        "kernel_thunk_addr": f"0x{xbe.header.kernel_thunk_addr:08X}",
        "counts": counts,
        "imports": rows,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.text_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")

    lines = [
        "Merc360 Phase 4A - Mercenaries Kernel Surface Audit",
        "=" * 66,
        f"Title:             {xbe.certificate.title_name}",
        f"Title ID:          0x{xbe.certificate.title_id:08X}",
        f"Retail XBE SHA256: {actual_sha}",
        f"Kernel thunk VA:   0x{xbe.header.kernel_thunk_addr:08X}",
        "",
        f"Imports:              {counts['imports']}",
        f"Resolver mappings:    {counts['resolved']}",
        f"Unresolved ordinals:  {counts['unresolved']}",
        f"Callable targets:     {counts['callable']}",
        f"Data exports:         {counts['data']}",
        f"Definition missing:   {counts['definition_missing']}",
        f"Host-surface flagged: {counts['host_surface_flagged']}",
        f"Stub-hint flagged:    {counts['stub_hint_flagged']}",
        "",
        "slot ord  thunk       kind       import -> resolver [source]",
        "-" * 100,
    ]
    for row in rows:
        target = row["resolver_symbol"] or row["resolver_expression"] or "<UNRESOLVED>"
        src = f" [{row['source']}]" if row["source"] else ""
        flags = []
        if row["host_surface_tokens"]:
            flags.append("HOST=" + ",".join(row["host_surface_tokens"]))
        if row["stub_hints"]:
            flags.append("STUB_HINT")
        suffix = (" {" + "; ".join(flags) + "}") if flags else ""
        lines.append(
            f"{row['slot']:>3} {row['ordinal']:>4} {row['thunk_addr']} "
            f"{row['kind']:<10} {row['name']} -> {target}{src}{suffix}"
        )

    lines += [
        "",
        "[Phase4A] RESULT: " + (
            "PASS" if counts["unresolved"] == 0 and
            counts["definition_missing"] == 0 else "REVIEW REQUIRED"
        ),
        "[Phase4A] Next: review host/stub flags and select the first Xenon-native startup batch.",
    ]
    args.text_out.write_text("\n".join(lines) + "\n", encoding="utf-8")

    print("[Phase4A] MERCENARIES KERNEL SURFACE AUDIT")
    print(f"[Phase4A] Verified retail XBE: {actual_sha}")
    print(f"[Phase4A] Exact kernel imports: {counts['imports']}")
    print(
        f"[Phase4A] resolver={counts['resolved']} "
        f"unresolved={counts['unresolved']} callable={counts['callable']} "
        f"data={counts['data']} def_missing={counts['definition_missing']}"
    )
    print(
        f"[Phase4A] host_surface_flagged={counts['host_surface_flagged']} "
        f"stub_hint_flagged={counts['stub_hint_flagged']}"
    )
    print(f"[Phase4A] Text report: {args.text_out}")
    print(f"[Phase4A] JSON report: {args.json_out}")
    print(
        "[Phase4A] RESULT: " +
        ("PASS" if counts["unresolved"] == 0 and counts["definition_missing"] == 0
         else "REVIEW REQUIRED")
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
