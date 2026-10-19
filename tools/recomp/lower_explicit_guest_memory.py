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
import os
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

RAW_GUEST_MEMSET_RE = re.compile(
    r"^(?P<indent>\s*)memset\(\(void\s*\*\)XBOX_PTR\((?P<addr>[^()]+)\),\s*"
    r"\(uint8_t\)(?P<value>[^,;]+),\s*(?P<count>[^);]+)\);\s*$"
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


def _is_unary_address_of(mask: str, amp_pos: int) -> bool:
    """Distinguish unary address-of from binary/logical AND.

    Examples:
        foo(&MEM32(x))        -> unary address-of
        eax = eax & MEM32(x)  -> binary bitwise AND
        if (eax && MEM8(x))   -> logical AND
    """
    # If this '&' is literally the second character of '&&', it is the
    # logical-AND operator immediately preceding the MEM expression.
    if amp_pos > 0 and mask[amp_pos - 1] == "&":
        return False

    prev = _skip_ws(mask, amp_pos - 1, -1)
    if prev < 0:
        return True

    ch = mask[prev]
    # After an opening delimiter, comma, assignment, or another operator, '&'
    # begins a unary operand. After an identifier/value/closing delimiter it is
    # the binary bitwise-AND operator.
    if ch in "([{,:;=!?+-*/%~^|&<>":
        return True

    # Handle the uncommon but valid 'return &MEM32(...)' shape.
    prefix = mask[:amp_pos].rstrip()
    if prefix.endswith("return"):
        return True

    return False


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
    """Return text between the previous top-level delimiter and this write.

    Semicolons inside a control header such as a for-loop header are not
    statement boundaries.
    """
    i = start - 1
    paren_depth = 0
    bracket_depth = 0
    while i >= 0:
        ch = mask[i]
        if ch == ")":
            paren_depth += 1
        elif ch == "(":
            if paren_depth:
                paren_depth -= 1
        elif ch == "]":
            bracket_depth += 1
        elif ch == "[":
            if bracket_depth:
                bracket_depth -= 1
        elif paren_depth == 0 and bracket_depth == 0 and ch in ";{}":
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
        if (before >= 0 and mask[before] == "&" and
                _is_unary_address_of(mask, before)):
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

        if (before >= 0 and mask[before] == "&" and
                _is_unary_address_of(mask, before)):
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


def _lower_raw_guest_bulk_line(line: str) -> tuple[str, int]:
    """Lower legacy raw-pointer bulk guest writes emitted by the lifter.

    The normal PC path uses host memset for forward REP STOSB. In the explicit
    ABI the destination is a guest address, so preserve x86 semantics with
    checked byte writes instead of exposing XBOX_PTR.
    """
    body = line[:-1] if line.endswith("\n") else line
    newline = "\n" if line.endswith("\n") else ""
    match = RAW_GUEST_MEMSET_RE.match(body)
    if not match:
        return line, 0

    indent = match.group("indent")
    addr = match.group("addr").strip()
    value = match.group("value").strip()
    count = match.group("count").strip()
    lowered = (
        f"{indent}{{ uint32_t _guest_memset_i; "
        f"for (_guest_memset_i = 0; _guest_memset_i < ({count}); "
        f"++_guest_memset_i) "
        f"GUEST_WRITE8(({addr}) + _guest_memset_i, (uint8_t)({value})); }}"
        f"{newline}"
    )
    return lowered, 1


def lower_file_to_temp(path: Path) -> tuple[Path, dict]:
    """Lower one file without mutating the audited source tree yet.

    Generated instructions and Mercenaries patch statements are intentionally
    line-oriented. Lowering each active source line avoids repeatedly rescanning
    an entire ~80k-line chunk for every guest write. A guest-memory expression
    that crosses a physical line is rejected rather than guessed.
    """
    raw = path.read_bytes()
    newline = "\r\n" if b"\r\n" in raw else "\n"
    source = raw.decode("utf-8").replace("\r\n", "\n")
    masked = _mask_noncode(source)

    source_lines = source.splitlines(keepends=True)
    mask_lines = masked.splitlines(keepends=True)
    if len(source_lines) != len(mask_lines):
        raise LoweringError("internal line-map mismatch after comment masking")

    totals = {
        "writes": 0,
        "compound_writes": 0,
        "incdec_writes": 0,
        "reads": 0,
        "bulk_writes": 0,
    }
    output = []
    i = 0
    while i < len(source_lines):
        line_number = i + 1
        line = source_lines[i]
        mask_line = mask_lines[i]

        # Raw-pointer bulk stores are not MEM lvalues, so lower them before the
        # ordinary MEM* fast path.
        lowered_bulk, bulk_count = _lower_raw_guest_bulk_line(line)
        if bulk_count:
            output.append(lowered_bulk)
            totals["bulk_writes"] += bulk_count
            i += 1
            continue

        active = list(MACRO_RE.finditer(mask_line))
        if not active:
            output.append(line)
            i += 1
            continue

        # Fast path: almost every generated instruction is contained on one
        # physical line. If a MEM(...) expression or write statement wraps,
        # grow only this fragment until it is syntactically complete.
        fragment = line
        end = i

        # Refuse a rare cross-line block-comment ambiguity instead of letting
        # a fragment-local masker reinterpret text hidden by the full-file mask.
        local_active = list(MACRO_RE.finditer(_mask_noncode(line)))
        if len(local_active) != len(active):
            raise LoweringError(
                f"line {line_number}: cross-line comment around guest-memory "
                "syntax requires explicit handling")

        while True:
            try:
                lowered_fragment, stats = lower_source(fragment)
                break
            except LoweringError as exc:
                message = str(exc)
                incomplete = (
                    "unmatched '('" in message or
                    "write has no terminating semicolon" in message
                )
                if not incomplete:
                    raise LoweringError(
                        f"line {line_number}: {exc}") from exc
                end += 1
                if end >= len(source_lines):
                    raise LoweringError(
                        f"line {line_number}: incomplete multi-line guest-memory "
                        f"expression at end of file: {exc}") from exc
                if end - i >= 64:
                    raise LoweringError(
                        f"line {line_number}: guest-memory expression spans more "
                        "than 64 physical lines") from exc
                fragment += source_lines[end]

        for key in ("writes", "compound_writes", "incdec_writes", "reads"):
            totals[key] += stats[key]
        output.append(lowered_fragment)
        i = end + 1

    lowered = "".join(output)
    if newline == "\r\n":
        lowered = lowered.replace("\n", "\r\n")

    temp = path.with_name(path.name + ".phase3n.tmp")
    temp.write_bytes(lowered.encode("utf-8"))
    totals["bytes"] = temp.stat().st_size
    return temp, totals


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
        "bulk_writes": 0,
        "source_bytes": 0,
    }
    per_file = []
    staged = []
    try:
        for path in files:
            try:
                temp, stats = lower_file_to_temp(path)
            except LoweringError as exc:
                raise LoweringError(f"{path.name}: {exc}") from exc
            staged.append((path, temp))
            stats["file"] = path.name
            total["source_bytes"] += stats["bytes"]
            for key in ("writes", "compound_writes", "incdec_writes", "reads"):
                total[key] += stats[key]
            total["bulk_writes"] += stats.get("bulk_writes", 0)
            per_file.append(stats)

        # Commit the conversion only after every generated source file proves
        # lowerable. This keeps Stage A restartable after a newly discovered
        # unsupported shape instead of leaving a half-converted tree.
        for path, temp in staged:
            os.replace(str(temp), str(path))
    finally:
        for _, temp in staged:
            try:
                temp.unlink()
            except FileNotFoundError:
                pass

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
        f"{report['incdec_writes']} inc/dec, "
        f"{report.get('bulk_writes', 0)} bulk guest stores)"
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
