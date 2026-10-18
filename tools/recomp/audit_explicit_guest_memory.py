"""Audit generated C for legacy host-lvalue guest-memory accesses.

Use this after all generated-code patch scripts have run for an explicit
Xbox-360-oriented generation. Runtime compatibility headers intentionally
still define legacy MEM macros for the normal PC path; this scanner is for
emitted/generated C, not for recomp_types.h itself.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import re
import sys


LEGACY_ACCESS = re.compile(
    r"\b(?:MEM8|MEM16|MEM32|MEM64|"
    r"SMEM8|SMEM16|SMEM32|SMEM64|MEMF|MEMD|XBOX_PTR)\s*\("
)


def _blank_block_comment(match: re.Match[str]) -> str:
    return "\n" * match.group(0).count("\n")


def strip_c_comments(source: str) -> str:
    """Remove C/C++ comments while preserving source line count."""
    source = re.sub(r"/\*.*?\*/", _blank_block_comment, source, flags=re.S)
    return re.sub(r"//[^\n]*", "", source)


def find_legacy_accesses(source: str):
    """Return line-number/text pairs for executable legacy memory use."""
    audited = strip_c_comments(source)
    hits = []
    for line_number, line_text in enumerate(audited.splitlines(), 1):
        if LEGACY_ACCESS.search(line_text):
            hits.append((line_number, line_text.strip()))
    return hits


def iter_source_files(paths):
    for raw in paths:
        path = Path(raw)
        if path.is_dir():
            for candidate in sorted(path.rglob("*")):
                if candidate.is_file() and candidate.suffix.lower() in {".c", ".cc", ".cpp"}:
                    yield candidate
        elif path.is_file():
            yield path
        else:
            raise FileNotFoundError(path)


def audit_paths(paths):
    findings = []
    for path in iter_source_files(paths):
        source = path.read_text(encoding="utf-8", errors="replace")
        hits = find_legacy_accesses(source)
        if hits:
            findings.append((path, hits))
    return findings


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Reject legacy MEM/XBOX_PTR accesses in explicit generated C")
    parser.add_argument(
        "paths", nargs="+",
        help="Generated C file(s) or directories to audit after patching")
    args = parser.parse_args(argv)

    findings = audit_paths(args.paths)
    if not findings:
        print("PASS: no legacy guest-memory lvalues in generated C")
        return 0

    print("FAIL: legacy guest-memory access remains in explicit generated C",
          file=sys.stderr)
    for path, hits in findings:
        for line_number, line_text in hits[:50]:
            print(f"{path}:{line_number}: {line_text}", file=sys.stderr)
        if len(hits) > 50:
            print(f"{path}: ... {len(hits) - 50} additional hit(s)",
                  file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(main())
