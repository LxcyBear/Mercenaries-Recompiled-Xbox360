"""Lower patched generated C from legacy MEM lvalues to explicit guest-memory calls.

This pass intentionally runs *after* Mercenaries' Patch-Generated.py. The
retail patcher is a large, mature set of textual patches whose anchors use the
historical MEM8/MEM16/MEM32/MEMF syntax. Rewriting that inventory would make
the known-good PC patch path diverge.

Phase 3N instead lowers the finished patched generated C into the checked
explicit guest-memory ABI used by the Xbox 360 target. The pass is deliberately
conservative: an lvalue shape it cannot prove safe is a hard failure.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys


READ_HELPERS = {
    "MEM8": "GUEST_READ8",
    "MEM16": "GUEST_READ16",
    "MEM32": "GUEST_READ32",
    "MEM64": "GUEST_READ64",
    "SMEM8": "GUEST_SREAD8",
    "SMEM16": "GUEST_SREAD16",
    "SMEM32": "GUEST_SREAD32",
    "SMEM64": "GUEST_SREAD64",
    "MEMF": "GUEST_READF32",
    "MEMD": "GUEST_READF64",
}

WRITE_HELPERS = {
    "MEM8": "GUEST_WRITE8",
    "MEM16": "GUEST_WRITE16",
    "MEM32": "GUEST_WRITE32",
    "MEM64": "GUEST_WRITE64",
    "MEMF": "GUEST_WRITEF32",
    "MEMD": "GUEST_WRITEF64",
}

MACRO_RE = re.compile(
    r"\b(MEM8|MEM16|MEM32|MEM64|SMEM8|SMEM16|SMEM32|SMEM64|MEMF|MEMD)\s*\("
)
ASSIGN_OPS = ("<<=", ">>=", "+=", "-=", "*=", "/=", "%=", "&=", "|=", "^=", "=")
COMPOUND_BINARY = {
    "+=": "+", "-=": "-", "*=": "*", "/=": "/", "%=": "%",
    "&=": "&", "|=": "|", "^=": "^", "<<=": "<<", ">>=": ">>",
}


class LoweringError(RuntimeError):
    pass


def _mask_noncode(source: str) -> str:
    """Blank comments/string/char literals while preserving source offsets."""
    out = list(source)
    i = 0
    n = len(source)
    while i < n:
        ch = source[i]
        if ch == "/" and i + 1 < n and source[i + 1] == "/":
            j = i
            while j < n and source[j] != "\n":
                out[j] = " "
                j += 1
            i = j
            continue
        if ch == "/" and i + 1 < n and source[i + 1] == "*":
            out[i] = out[i + 1] = " "
            i += 2
            while i < n:
                if source[i] == "*" and i + 1 < n and source[i + 1] == "/":
                    out[i] = out[i + 1] = " "
                    i += 2
                    break
                if source[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        if ch in ('"', "'"):
            quote = ch
            out[i] = " "
            i += 1
            while i < n:
                if source[i] == "\\":
                    if source[i] != "\n":
                        out[i] = " "
                    if i + 1 < n:
                        if source[i + 1] != "\n":
                            out[i + 1] = " "
                        i += 2
                    else:
                        i += 1
                    continue
                if source[i] == quote:
                    out[i] = " "
                    i += 1
                    break
                if source[i] != "\n":
                    out[i] = " "
                i += 1
            continue
        i += 1
    return "".join(out)


def _skip_ws(mask: str, pos: int, step: int = 1) -> int:
    while 0 <= pos < len(mask) and mask[pos].isspace():
        pos += step
    return pos


def _matching_paren(mask: str, open_pos: int) -> int:
    if open_pos >= len(mask) or mask[open_pos] != "(":
        raise LoweringError("internal: expected '('")
    depth = 1
    i = open_pos + 1
    while i < len(mask):
        if mask[i] == "(":
            depth += 1
        elif mask[i] == ")":
            depth -= 1
            if depth == 0:
                return i
        i += 1
    raise LoweringError(f"unmatched '(' at source offset {open_pos}")


def _statement_end(mask: str, pos: int) -> int:
    paren = bracket = brace = 0
    i = pos
    while i < len(mask):
        ch = mask[i]
        if ch == "(":
            paren += 1
        elif ch == ")" and paren:
            paren -= 1
        elif ch == "[":
            bracket += 1
        elif ch == "]" and bracket:
            bracket -= 1
        elif ch == "{":
            brace += 1
        elif ch == "}" and brace:
            brace -= 1
        elif ch == ";" and paren == 0 and bracket == 0 and brace == 0:
            return i
        i += 1
    raise LoweringError("write has no terminating semicolon")


def _statement_prefix(mask: str, start: int) -> str:
    """Return text between the previous statement delimiter and this write."""
    i = start - 1
    while i >= 0:
        if mask[i] in ";{}":
            break
        i -= 1
    return mask[i + 1:start]


def _is_complete_control_prefix(prefix: str) -> bool:
    """Accept a write used only as a single control-statement body.

    Examples:
        for (...) MEM32(x) = y;
        if (...) MEM8(x) = y;
        while (...) MEM16(x) = y;

    A write inside the condition/header itself is rejected because the prefix
    does not contain one complete balanced parenthesized control expression.
    """
    text = prefix.strip()
    for keyword in ("for", "if", "while"):
        if not text.startswith(keyword):
            continue
        pos = len(keyword)
        while pos < len(text) and text[pos].isspace():
            pos += 1
        if pos >= len(text) or text[pos] != "(":
            continue
        depth = 0
        close = None
        for index in range(pos, len(text)):
            char = text[index]
            if char == "(":
                depth += 1
            elif char == ")":
                depth -= 1
                if depth == 0:
                    close = index
                    break
            if depth < 0:
                return False
        if close is None:
            return False
        return not text[close + 1:].strip()
    return False


def _write_has_supported_statement_context(mask: str, start: int) -> bool:
    prefix = _statement_prefix(mask, start)
    return not prefix.strip() or _is_complete_control_prefix(prefix)


def _assignment_after(mask: str, close_pos: int):
    pos = _skip_ws(mask, close_pos + 1)
    for op in ASSIGN_OPS:
        if not mask.startswith(op, pos):
            continue
        if op == "=" and pos + 1 < len(mask) and mask[pos + 1] == "=":
            continue
        return pos, op
    return None


def _lower_reads_only(fragment: str) -> tuple[str, int]:
    count = 0
    while True:
        mask = _mask_noncode(fragment)
        matches = list(MACRO_RE.finditer(mask))
        if not matches:
            return fragment, count

        # Rightmost is innermost for nested MEM(MEM(...)) expressions.
        match = matches[-1]
        name = match.group(1)
        open_pos = mask.find("(", match.start(), match.end() + 1)
        close_pos = _matching_paren(mask, open_pos)

        assignment = _assignment_after(mask, close_pos)
        after = _skip_ws(mask, close_pos + 1)
        if assignment or mask.startswith("++", after) or mask.startswith("--", after):
            raise LoweringError(f"write-shaped {name}(...) appeared inside an expression")

        before = _skip_ws(mask, match.start() - 1, -1)
        if before >= 0 and mask[before] == "&":
            raise LoweringError(f"address-of {name}(...) requires a manual guest bridge")
        if before >= 1 and mask[before - 1:before + 1] in ("++", "--"):
            raise LoweringError(f"prefix write-shaped {name}(...) appeared inside an expression")

        address = fragment[open_pos + 1:close_pos]
        replacement = f"{READ_HELPERS[name]}({address})"
        fragment = fragment[:match.start()] + replacement + fragment[close_pos + 1:]
        count += 1


def _find_write(source: str):
    mask = _mask_noncode(source)
    for match in MACRO_RE.finditer(mask):
        name = match.group(1)
        open_pos = mask.find("(", match.start(), match.end() + 1)
        close_pos = _matching_paren(mask, open_pos)

        assignment = _assignment_after(mask, close_pos)
        if assignment:
            if name not in WRITE_HELPERS:
                raise LoweringError(f"signed legacy macro {name} used as an lvalue")
            op_pos, op = assignment
            return ("assign", name, match.start(), open_pos, close_pos, op_pos, op)

        after = _skip_ws(mask, close_pos + 1)
        if mask.startswith("++", after) or mask.startswith("--", after):
            if name not in WRITE_HELPERS:
                raise LoweringError(f"signed legacy macro {name} incremented/decremented")
            return ("postfix", name, match.start(), open_pos, close_pos, after,
                    mask[after:after + 2])

        before = _skip_ws(mask, match.start() - 1, -1)
        if before >= 1 and mask[before - 1:before + 1] in ("++", "--"):
            if name not in WRITE_HELPERS:
                raise LoweringError(f"signed legacy macro {name} incremented/decremented")
            return ("prefix", name, match.start(), open_pos, close_pos, before - 1,
                    mask[before - 1:before + 1])

        if before >= 0 and mask[before] == "&":
            raise LoweringError(
                f"address-of legacy guest lvalue {name}(...) requires a manual bridge")
    return None


def lower_source(source: str) -> tuple[str, dict]:
    stats = {"writes": 0, "compound_writes": 0, "incdec_writes": 0, "reads": 0}

    # Convert writes before reads so an assignable MEM macro cannot accidentally
    # become a read helper on the left side of an assignment.
    while True:
        write = _find_write(source)
        if write is None:
            break

        kind, name, start, open_pos, close_pos, op_pos, op = write
        statement_start = start if kind != "prefix" else op_pos
        if not _write_has_supported_statement_context(
                _mask_noncode(source), statement_start):
            line = source.count("\n", 0, start) + 1
            raise LoweringError(
                f"line {line}: legacy write is embedded in an unsupported expression/control context")

        address = source[open_pos + 1:close_pos]
        address, nested = _lower_reads_only(address)
        stats["reads"] += nested
        read_helper = READ_HELPERS[name]
        write_helper = WRITE_HELPERS[name]

        if kind == "assign":
            rhs_start = op_pos + len(op)
            semi = _statement_end(_mask_noncode(source), rhs_start)
            rhs = source[rhs_start:semi].strip()
            rhs, nested = _lower_reads_only(rhs)
            stats["reads"] += nested
            if op == "=":
                value = rhs
            else:
                value = f"{read_helper}({address}) {COMPOUND_BINARY[op]} ({rhs})"
                stats["compound_writes"] += 1
            replacement = f"{write_helper}({address}, {value})"
            source = source[:start] + replacement + source[semi:]
            stats["writes"] += 1
            continue

        delta = "+" if op == "++" else "-"
        replacement = f"{write_helper}({address}, {read_helper}({address}) {delta} 1)"
        if kind == "postfix":
            source = source[:start] + replacement + source[op_pos + 2:]
        else:
            source = source[:op_pos] + replacement + source[close_pos + 1:]
        stats["writes"] += 1
        stats["incdec_writes"] += 1

    source, reads = _lower_reads_only(source)
    stats["reads"] += reads

    if ("#define RECOMP_GENERATED_CODE" in source and
            "#define RECOMP_EXPLICIT_GUEST_MEMORY_ABI" not in source):
        source = source.replace(
            "#define RECOMP_GENERATED_CODE",
            "#define RECOMP_GENERATED_CODE\n#define RECOMP_EXPLICIT_GUEST_MEMORY_ABI",
            1,
        )

    return source, stats


def lower_file(path: Path) -> dict:
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    source = raw.decode("utf-8").replace("\r\n", "\n")
    lowered, stats = lower_source(source)
    if newline == "\r\n":
        lowered = lowered.replace("\n", "\r\n")
    path.write_bytes(lowered.encode("utf-8"))
    return stats


def lower_tree(root: Path) -> dict:
    files = sorted(root.glob("recomp_*.c"))
    if not files:
        raise LoweringError(f"no generated recomp_*.c files found in {root}")

    total = {
        "files": len(files),
        "writes": 0,
        "compound_writes": 0,
        "incdec_writes": 0,
        "reads": 0,
        "source_bytes": 0,
    }
    per_file = []
    for path in files:
        try:
            stats = lower_file(path)
        except LoweringError as exc:
            raise LoweringError(f"{path.name}: {exc}") from exc
        stats["file"] = path.name
        stats["bytes"] = path.stat().st_size
        total["source_bytes"] += stats["bytes"]
        for key in ("writes", "compound_writes", "incdec_writes", "reads"):
            total[key] += stats[key]
        per_file.append(stats)
    total["per_file"] = per_file
    return total


def main(argv=None):
    parser = argparse.ArgumentParser(
        description="Lower patched generated C to explicit guest-memory calls")
    parser.add_argument("generated_root", type=Path)
    parser.add_argument("--report", type=Path)
    args = parser.parse_args(argv)

    try:
        report = lower_tree(args.generated_root)
    except (OSError, UnicodeError, LoweringError) as exc:
        print(f"FAIL: explicit guest-memory lowering: {exc}", file=sys.stderr)
        return 1

    if args.report:
        args.report.parent.mkdir(parents=True, exist_ok=True)
        args.report.write_text(json.dumps(report, indent=2) + "\n",
                               encoding="utf-8")

    print(
        "PASS: explicit guest-memory lowering: "
        f"{report['files']} files, {report['reads']} reads, "
        f"{report['writes']} writes "
        f"({report['compound_writes']} compound, "
        f"{report['incdec_writes']} inc/dec)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
