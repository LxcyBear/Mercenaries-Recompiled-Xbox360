#!/usr/bin/env python3
"""Emit real C++ translation units from the Phase 6 monolithic generated source.

The older "translated_shards/*.inl" layout only made the generated source easier
to manage: every shard was still #included by main.cpp, so cl.exe saw one giant
translation unit.  This emitter keeps runtime/support code in main.cpp and emits
64 independently compiled translated_###.cpp files.

Design goals:
  * deterministic VA-based shard ownership (adding one function does not reshuffle
    unrelated functions);
  * content-stable writes (unchanged files keep their mtimes);
  * translated functions and shared runtime helpers/state use external linkage;
  * each shard declares only the translated callees it actually references;
  * fail closed when a runtime global needed by translated code cannot be
    declarationized safely.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

SHARD_COUNT = 64
TRUE_TU_EMITTER_REVISION = "6TU-R7-SHARED-PROTOTYPE-LINKAGE-20261027"
OFF_MARKER = '#pragma optimize("", off)\n'
ON_MARKER = '\n#pragma optimize("", on)'

FUNC_RE = re.compile(
    r"(?m)^(?P<indent>\s*)(?P<static>static\s+)?"
    r"(?P<ret>(?:__forceinline\s+)?(?:[A-Za-z_]\w*(?:::\w+)?(?:\s*[*&])?"
    r"(?:\s+const)?|const\s+[A-Za-z_]\w*(?:\s*[*&])?))\s+"
    r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*\{"
)
SUB_DEF_RE = re.compile(r"(?m)^\s*static\s+void\s+(sub_([0-9A-Fa-f]{8}))\(void\)\s*\{")
SUB_DECL_RE = re.compile(r"(?m)^(\s*)static\s+void\s+(sub_[0-9A-Fa-f]{8})\(void\)\s*;")
SUB_CALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(")
ID_RE = re.compile(r"\b[A-Za-z_]\w*\b")

# EBP is intentionally a per-translated-function local frame register.  It is
# seeded from shared g_seh_ebp at function entry and must never be externalized.
LOCAL_TRANSLATED_ARCH_REGS = {"ebp"}


def mask_noncode(text: str) -> str:
    out = list(text)
    i = 0
    state = "code"
    quote = ""
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""
        if state == "line":
            if c == "\n":
                state = "code"
            else:
                out[i] = " "
            i += 1
            continue
        if state == "block":
            out[i] = " "
            if c == "*" and n == "/":
                out[i + 1] = " "
                i += 2
                state = "code"
            else:
                i += 1
            continue
        if state == "string":
            out[i] = " "
            if c == "\\":
                if i + 1 < len(text):
                    out[i + 1] = " "
                    i += 2
                    continue
            if c == quote:
                state = "code"
            i += 1
            continue
        if c == "/" and n == "/":
            out[i] = out[i + 1] = " "
            i += 2
            state = "line"
            continue
        if c == "/" and n == "*":
            out[i] = out[i + 1] = " "
            i += 2
            state = "block"
            continue
        if c in ("'", '"'):
            out[i] = " "
            quote = c
            state = "string"
            i += 1
            continue
        i += 1
    return "".join(out)


def closing_brace(masked: str, brace: int) -> int:
    depth = 0
    for i in range(brace, len(masked)):
        c = masked[i]
        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise RuntimeError("unterminated brace block")


def function_spans(text: str) -> list[dict]:
    masked = mask_noncode(text)
    rows = []
    for m in FUNC_RE.finditer(masked):
        brace = masked.find("{", m.start(), m.end())
        if brace < 0:
            continue
        end = closing_brace(masked, brace)
        rows.append(
            {
                "start": m.start(),
                "brace": brace,
                "end": end,
                "name": m.group("name"),
                "source": text[m.start():end],
                "signature": text[m.start():brace].rstrip(),
                "static": bool(m.group("static")),
            }
        )
    # Reject nested false positives by retaining only non-overlapping top-level defs.
    out = []
    last_end = -1
    for row in rows:
        if row["start"] >= last_end:
            out.append(row)
            last_end = row["end"]
    return out


def write_if_changed(path: Path, data: str) -> bool:
    encoded = data.encode("utf-8")
    if path.exists() and path.read_bytes() == encoded:
        return False
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_bytes(encoded)
    return True


def extract_preprocessor(prefix: str) -> str:
    lines = prefix.splitlines(True)
    out: list[str] = []
    i = 0
    keep_heads = ("#include", "#define", "#pragma", "#if", "#ifdef", "#ifndef",
                  "#elif", "#else", "#endif", "#undef")
    while i < len(lines):
        stripped = lines[i].lstrip()
        if stripped.startswith(keep_heads):
            block = [lines[i]]
            while block[-1].rstrip("\r\n").endswith("\\") and i + 1 < len(lines):
                i += 1
                block.append(lines[i])
            out.extend(block)
        i += 1
    return "".join(out)


def extract_type_blocks(prefix_without_functions: str) -> list[str]:
    """Extract top-level typedef/struct/enum/union declarations conservatively."""
    masked = mask_noncode(prefix_without_functions)
    starts = list(re.finditer(r"(?m)^\s*(?:typedef\s+|struct\s+[A-Za-z_]\w*\s*\{|enum\s+[A-Za-z_]\w*\s*\{|union\s+[A-Za-z_]\w*\s*\{)", masked))
    blocks: list[str] = []
    consumed_until = -1
    for m in starts:
        if m.start() < consumed_until:
            continue
        # Walk to a semicolon at brace/paren/bracket depth zero.
        depth_b = depth_p = depth_s = 0
        i = m.start()
        while i < len(masked):
            c = masked[i]
            if c == "{":
                depth_b += 1
            elif c == "}":
                depth_b -= 1
            elif c == "(":
                depth_p += 1
            elif c == ")":
                depth_p -= 1
            elif c == "[":
                depth_s += 1
            elif c == "]":
                depth_s -= 1
            elif c == ";" and depth_b == depth_p == depth_s == 0:
                end = i + 1
                block = prefix_without_functions[m.start():end].strip()
                if block and block not in blocks:
                    blocks.append(block)
                consumed_until = end
                break
            i += 1
    return blocks


def remove_spans(text: str, spans: list[dict]) -> str:
    pieces = []
    pos = 0
    for row in spans:
        pieces.append(text[pos:row["start"]])
        pieces.append("\n")
        pos = row["end"]
    pieces.append(text[pos:])
    return "".join(pieces)


def prototype_from_signature(signature: str) -> str:
    sig = re.sub(r"^\s*static\s+", "", signature, count=1)
    return sig.strip() + ";"


def externalize_prefix_functions(
    prefix: str,
) -> tuple[str, list[str], list[str], list[str]]:
    """Externalize ordinary support functions and share inline/template bodies.

    Ordinary support functions live once in runtime main and receive prototypes
    in the shard header. __forceinline/template helpers need their full
    definitions visible in every shard TU.
    """
    spans = function_spans(prefix)
    prototypes: list[str] = []
    template_definitions: list[str] = []
    inline_definitions: list[str] = []
    pieces = []
    pos = 0

    for row in spans:
        pieces.append(prefix[pos:row["start"]])

        before = prefix[:row["start"]]
        template_match = re.search(
            r"(?s)([ \t]*template\s*<[^;{}]+>\s*)\Z",
            before,
        )
        is_template = template_match is not None
        is_forceinline = "__forceinline" in row["signature"]

        src = row["source"]
        if is_template:
            template_definitions.append(template_match.group(1) + src)
            # Keep the original runtime copy unchanged.
        elif is_forceinline:
            # Keep the original runtime copy and put the full body in the shard
            # header. A prototype alone is insufficient for force-inline helpers
            # such as XBOX_REP_MOVS under the VS2017 Xbox 360 compiler.
            inline_definitions.append(src)
        else:
            if row["static"]:
                src = re.sub(r"^(\s*)static\s+", r"\1", src, count=1)
            prototypes.append(prototype_from_signature(row["signature"]))

        pieces.append(src)
        pos = row["end"]

    pieces.append(prefix[pos:])
    runtime = "".join(pieces)
    runtime = SUB_DECL_RE.sub(
        lambda m: f"{m.group(1)}void {m.group(2)}(void);",
        runtime,
    )
    return runtime, prototypes, template_definitions, inline_definitions



def looks_like_variable_declaration(stmt: str, name: str) -> bool:
    """Reject assignments/statements that merely mention a runtime symbol."""
    match = re.search(rf"\b{re.escape(name)}\b", stmt)
    if match is None:
        return False

    before = stmt[:match.start()].strip()
    if not before:
        return False
    if any(ch in before for ch in "=(){};"):
        return False

    head_tokens = re.findall(r"\b[A-Za-z_]\w*\b", before)
    if not head_tokens:
        return False
    if head_tokens[0] in {
        "return", "if", "while", "for", "switch", "case", "goto",
    }:
        return False
    return True


def declaration_statement_names(stmt: str) -> set[str]:
    """Return g_*/s_* identifiers declared by a simple variable statement.

    This intentionally supports comma declarations such as:
        uint64_t g_mm0 = 0, g_mm1 = 0, g_mm2 = 0, g_mm3 = 0;
    where only the first declarator is preceded by the type.
    """
    masked = mask_noncode(stmt)
    head = masked.strip()
    if not head.endswith(";"):
        return set()
    if head.startswith(("#", "typedef", "return", "if", "while", "for", "switch")):
        return set()

    # Function prototypes/calls are not storage declarations.
    before_equals = head.split("=", 1)[0]
    if "(" in before_equals or ")" in before_equals:
        return set()

    # A declaration must start with at least one plausible type/qualifier token
    # before the first g_*/s_* declarator.
    first = re.search(r"\b[gs]_[A-Za-z_]\w*\b", head)
    if first is None:
        return set()
    prefix = head[:first.start()]
    if "=" in prefix or ";" in prefix or "{" in prefix or "}" in prefix:
        return set()
    type_tokens = re.findall(r"\b[A-Za-z_]\w*\b", prefix)
    if not type_tokens:
        return set()

    return set(re.findall(r"\b[gs]_[A-Za-z_]\w*\b", head))


def line_statement_for_name(
    prefix_no_funcs: str,
    name: str,
) -> tuple[int, int, str] | None:
    """Find a top-level variable declaration containing name.

    Handles both ordinary one-variable declarations and grouped comma
    declarations where only the first variable is adjacent to the type.
    """
    candidates: list[tuple[int, int, str]] = []

    # Generated runtime globals are overwhelmingly one-line declarations.
    for m in re.finditer(r"(?m)^[ \t]*[^\n;]+;[ \t]*$", prefix_no_funcs):
        stmt = m.group(0)
        if name in declaration_statement_names(stmt):
            candidates.append((m.start(), m.end(), stmt))

    if len(candidates) == 1:
        return candidates[0]
    if len(candidates) > 1:
        return None

    # Multiline array/object declaration fallback, bounded to 4 KiB.
    idx = 0
    hits = []
    while True:
        idx = prefix_no_funcs.find(name, idx)
        if idx < 0:
            break
        if idx > 0 and (
            prefix_no_funcs[idx - 1].isalnum()
            or prefix_no_funcs[idx - 1] == "_"
        ):
            idx += len(name)
            continue
        after = idx + len(name)
        if after < len(prefix_no_funcs) and (
            prefix_no_funcs[after].isalnum()
            or prefix_no_funcs[after] == "_"
        ):
            idx = after
            continue

        # Walk backward to the previous statement boundary/newline and forward
        # to a bounded semicolon; then validate as a declaration as a whole.
        prev_semicolon = prefix_no_funcs.rfind(";", 0, idx)
        prev_newline = prefix_no_funcs.rfind("\n", 0, idx)
        start = max(prev_semicolon + 1, prev_newline + 1)
        end = prefix_no_funcs.find(
            ";",
            idx,
            min(len(prefix_no_funcs), idx + 4096),
        )
        if end >= 0:
            stmt = prefix_no_funcs[start:end + 1]
            if name in declaration_statement_names(stmt):
                hits.append((start, end + 1, stmt))
        idx = after

    uniq = {(x, y): (x, y, z) for x, y, z in hits}
    if len(uniq) == 1:
        return next(iter(uniq.values()))
    return None



def strip_initializer(stmt: str) -> str:
    """Remove every top-level declarator initializer, preserving comma lists."""
    out: list[str] = []
    i = 0
    depth_p = depth_b = depth_s = 0

    while i < len(stmt):
        c = stmt[i]
        if c == "(":
            depth_p += 1
            out.append(c)
            i += 1
            continue
        if c == ")":
            depth_p -= 1
            out.append(c)
            i += 1
            continue
        if c == "{":
            depth_b += 1
            out.append(c)
            i += 1
            continue
        if c == "}":
            depth_b -= 1
            out.append(c)
            i += 1
            continue
        if c == "[":
            depth_s += 1
            out.append(c)
            i += 1
            continue
        if c == "]":
            depth_s -= 1
            out.append(c)
            i += 1
            continue

        if c == "=" and depth_p == depth_b == depth_s == 0:
            # Skip this initializer until the next top-level comma/semicolon.
            i += 1
            init_p = init_b = init_s = 0
            in_string = False
            quote = ""
            escape = False
            while i < len(stmt):
                d = stmt[i]
                if in_string:
                    if escape:
                        escape = False
                    elif d == "\\":
                        escape = True
                    elif d == quote:
                        in_string = False
                    i += 1
                    continue
                if d in ("'", '"'):
                    in_string = True
                    quote = d
                    i += 1
                    continue
                if d == "(":
                    init_p += 1
                elif d == ")":
                    init_p -= 1
                elif d == "{":
                    init_b += 1
                elif d == "}":
                    init_b -= 1
                elif d == "[":
                    init_s += 1
                elif d == "]":
                    init_s -= 1
                elif d in ",;" and init_p == init_b == init_s == 0:
                    out.append(d)
                    i += 1
                    break
                i += 1
            continue

        out.append(c)
        i += 1

    return "".join(out)



def externize_statement(stmt: str) -> str:
    x = stmt.strip()
    x = re.sub(r"^static\s+", "", x, count=1)
    x = re.sub(r"^extern\s+", "", x, count=1)
    x = strip_initializer(x)
    return "extern " + x


def grouped_architecture_declaration_fallback(
    prefix_no_funcs: str,
    name: str,
) -> tuple[int, int, str] | None:
    """Resolve known architecture register groups stored in one declaration."""
    mmx_groups = {
        "g_mm0": "g_mm0", "g_mm1": "g_mm0", "g_mm2": "g_mm0", "g_mm3": "g_mm0",
        "g_mm4": "g_mm4", "g_mm5": "g_mm4", "g_mm6": "g_mm4", "g_mm7": "g_mm4",
    }
    anchor_name = mmx_groups.get(name)
    if anchor_name is None or anchor_name == name:
        return None

    row = line_statement_for_name(prefix_no_funcs, anchor_name)
    if row is None:
        return None

    # The source statement must actually mention the requested sibling.
    if re.search(rf"\b{re.escape(name)}\b", row[2]) is None:
        return None
    return row


def collect_runtime_globals(
    prefix: str,
    body: str,
    preprocessor: str,
) -> tuple[list[tuple[int, int, str, str]], list[str], list[str]]:
    """Find shared state referenced directly or through generated macros.

    True-TU splits expose all state that used to be visible simply because every
    translated function lived in one giant C++ file.  Collect every g_*/s_*
    top-level variable that translated code or copied macro bodies reference.
    Any unresolved g_*/s_* token that is not syntactically used as a function
    call is treated as required shared state and fails emission before VS can
    multiply one missing declaration across all 64 shards.
    """
    spans = function_spans(prefix)
    no_funcs = remove_spans(prefix, spans)
    tokens = set(ID_RE.findall(mask_noncode(body + "\n" + preprocessor)))

    required_arch = {
        "eax", "ecx", "edx", "ebx", "esi", "edi", "esp",
        "g_eax", "g_ecx", "g_edx", "g_ebx", "g_esi", "g_edi",
        "g_ebp", "g_esp", "g_eflags", "g_seh_ebp", "g_ram",
    }
    names = sorted(
        n
        for n in tokens
        if n not in LOCAL_TRANSLATED_ARCH_REGS
        and (
            n in required_arch
            or n.startswith("g_")
            or n.startswith("s_")
        )
    )

    found = []
    required_missing = []
    optional_unresolved = []
    seen_spans = set()
    satisfied_names: set[str] = set()

    for name in names:
        if name in satisfied_names:
            continue

        row = line_statement_for_name(no_funcs, name)
        if row is None:
            row = grouped_architecture_declaration_fallback(no_funcs, name)

        if row is None:
            macro_pat = re.compile(
                rf"(?m)^\s*#define\s+{re.escape(name)}\b"
            )
            if macro_pat.search(preprocessor):
                continue
            used_as_call = re.search(
                rf"\b{re.escape(name)}\s*\(",
                mask_noncode(body + "\n" + preprocessor),
            ) is not None
            if name in required_arch or not used_as_call:
                required_missing.append(name)
            else:
                optional_unresolved.append(name)
            continue

        a, b, stmt = row
        key = (a, b)
        declared_here = declaration_statement_names(stmt)
        satisfied_names.update(declared_here)

        if key in seen_spans:
            continue
        seen_spans.add(key)

        decl = externize_statement(stmt)
        if re.match(r"^extern\s+[gs]_[A-Za-z_]\w*\s*;$", decl.strip()):
            raise SystemExit(
                "[Phase6TU] refused malformed type-less extern generated from "
                f"{name}: {decl!r}"
            )
        found.append((a, b, stmt, decl))

    if required_missing:
        print("[Phase6TU] REQUIRED GLOBAL DIAGNOSTICS:")
        for missing_name in required_missing:
            print(f"[Phase6TU]   missing={missing_name}")
            # Print nearby source statements from the function-free prefix so
            # declaration-shape mismatches can be fixed from one run.
            hit_positions = [
                m.start()
                for m in re.finditer(
                    rf"\b{re.escape(missing_name)}\b",
                    no_funcs,
                )
            ][:6]
            if not hit_positions:
                print("[Phase6TU]     source_hits=0")
                continue
            for pos in hit_positions:
                line_start = no_funcs.rfind("\n", 0, pos) + 1
                line_end = no_funcs.find("\n", pos)
                if line_end < 0:
                    line_end = len(no_funcs)
                line = no_funcs[line_start:line_end].strip()
                print(f"[Phase6TU]     source={line[:300]}")

    return found, required_missing, optional_unresolved



def externalize_remaining_sub_symbols(text: str) -> tuple[str, int]:
    """Remove internal linkage from real sub_XXXXXXXX declarations/definitions.

    Search a comment/string-masked copy so text inside diagnostics, comments, or
    raw documentation cannot trigger a mutation. mask_noncode() preserves byte
    positions, so replacements can be applied safely to the original source.
    """
    masked = mask_noncode(text)
    pattern = re.compile(
        r"(?m)^(?P<indent>[ \t]*)static\s+void\s+"
        r"(?P<name>sub_[0-9A-Fa-f]{8})\s*"
        r"(?P<args>\([^;{}]*\))\s*(?P<tail>[;{])"
    )
    matches = list(pattern.finditer(masked))
    if not matches:
        return text, 0

    out = text
    for match in reversed(matches):
        line_start = match.start()
        static_start = line_start + len(match.group("indent"))
        static_end = static_start + len("static ")
        if out[static_start:static_end] != "static ":
            raise SystemExit(
                "[Phase6TU] internal-linkage sub symbol mask/source position mismatch"
            )
        out = out[:static_start] + out[static_end:]

    return out, len(matches)


def assert_no_internal_sub_linkage(text: str, label: str) -> None:
    masked = mask_noncode(text)
    match = re.search(
        r"(?m)^[ \t]*static\s+void\s+sub_[0-9A-Fa-f]{8}\s*\(",
        masked,
    )
    if match:
        line = masked.count("\n", 0, match.start()) + 1
        snippet = text[match.start(): text.find("\n", match.start()) if "\n" in text[match.start():] else len(text)]
        raise SystemExit(
            f"[Phase6TU] internal-linkage sub symbol remains in {label} "
            f"at line {line}: {snippet.strip()}"
        )



def externalize_runtime_globals(runtime_prefix: str, declarations: list[tuple[int,int,str,str]]) -> str:
    # Match exact original statements in the runtime prefix.  They survived
    # function externalization byte-for-byte.
    out = runtime_prefix
    for _, _, stmt, _ in declarations:
        replacement = re.sub(r"^(\s*)static\s+", r"\1", stmt, count=1)
        if out.count(stmt) != 1:
            raise SystemExit(f"[Phase6TU] runtime global declaration shape changed: {stmt[:120]!r}")
        out = out.replace(stmt, replacement, 1)
    return out


def shard_index_for_va(va: int) -> int:
    # Multiplicative hash of the guest VA. Stable: adding/removing a function
    # never changes ownership of existing functions.
    return ((va * 2654435761) & 0xFFFFFFFF) >> 26


def extract_body_support_functions(
    body: str,
) -> tuple[list[dict], str]:
    """Preserve non-translated support functions inside the optimize-off region.

    The monolithic layout can contain helper/root functions next to translated
    sub_XXXXXXXX bodies. Dropping the entire region after extracting only
    translated bodies strands declarations such as xbe_entry_point.
    """
    rows = [
        row
        for row in function_spans(body)
        if re.fullmatch(r"sub_[0-9A-Fa-f]{8}", row["name"]) is None
    ]
    pieces: list[str] = []
    prototypes: list[str] = []
    for row in rows:
        src = row["source"]
        if row["static"]:
            src = re.sub(r"^(\s*)static\s+", r"\1", src, count=1)
        pieces.append(src)
        pieces.append("\n\n")
        prototypes.append(prototype_from_signature(row["signature"]))

    return rows, "".join(pieces)


def externalize_named_forward_declarations(
    text: str,
    names: set[str],
) -> str:
    """Remove static from forward declarations for preserved body support."""
    out = text
    for name in sorted(names):
        pat = re.compile(
            rf"(?m)^(?P<indent>[ \t]*)static\s+"
            rf"(?P<decl>[^;\n{{}}]*\b{re.escape(name)}\s*"
            rf"\([^;{{}}]*\)\s*;)"
        )
        out = pat.sub(
            lambda m: f"{m.group('indent')}{m.group('decl')}",
            out,
        )
    return out



def parse_translated_functions(body: str) -> list[dict]:
    masked = mask_noncode(body)
    rows = []
    for m in SUB_DEF_RE.finditer(masked):
        brace = masked.find("{", m.start(), m.end())
        if brace < 0:
            raise SystemExit("[Phase6TU] translated function opening brace missing")
        end = closing_brace(masked, brace)
        name = m.group(1)
        va = int(m.group(2), 16)
        src = body[m.start():end]
        src = re.sub(r"^(\s*)static\s+void\s+", r"\1void ", src, count=1)
        rows.append({"name": name, "va": va, "source": src})
    if not rows:
        raise SystemExit("[Phase6TU] no translated functions found")
    return rows


def validate_local_architecture_registers(funcs: list[dict]) -> dict[str, int]:
    """Prove EBP remains per-function storage after the TU split.

    The generated corpus has used more than one harmless spelling over time
    (separate declaration/assignment versus declaration with initializer).
    TU correctness only requires that a function which operationally uses EBP
    owns local storage for it; the monolithic source already defines the value
    semantics.  Keep the standard g_seh_ebp seed as an audited statistic rather
    than rejecting alternate-but-local source shapes.
    """
    ebp_decl = re.compile(
        r"(?m)^\s*(?:uint32_t|DWORD)\s+ebp\s*(?:=\s*[^;]+)?;\s*$"
    )
    ebp_token = re.compile(r"\bebp\b")
    users = 0
    seeded_from_seh = 0

    for row in funcs:
        src = row["source"]
        masked = mask_noncode(src)
        if not ebp_token.search(masked):
            continue

        users += 1
        decls = ebp_decl.findall(masked)
        if len(decls) != 1:
            raise SystemExit(
                f"[Phase6TU] {row['name']} uses ebp but does not own exactly one "
                f"local EBP declaration (found {len(decls)})"
            )

        if re.search(
            r"\bebp\s*=\s*g_seh_ebp\s*;",
            masked,
        ) or re.search(
            r"\b(?:uint32_t|DWORD)\s+ebp\s*=\s*g_seh_ebp\s*;",
            masked,
        ):
            seeded_from_seh += 1

    if users == 0:
        raise SystemExit("[Phase6TU] expected translated local-ebp users, found none")

    return {
        "ebp_users": users,
        "ebp_seeded_from_g_seh_ebp": seeded_from_seh,
    }


def externalize_called_suffix_support(
    suffix: str,
    body: str,
) -> tuple[str, list[str], list[str]]:
    """Expose suffix-defined helpers that translated shards call directly.

    The monolithic file may define late support functions after the translated
    pragma region. They were naturally visible in the old one-TU layout only
    when declared earlier. For true TUs, add prototypes and external linkage
    only for suffix functions actually referenced by translated code.
    """
    called_names = set(
        re.findall(
            r"\b([A-Za-z_]\w*)\s*\(",
            mask_noncode(body),
        )
    )
    rows = function_spans(suffix)
    prototypes: list[str] = []
    externalized_names: list[str] = []
    pieces: list[str] = []
    pos = 0

    for row in rows:
        pieces.append(suffix[pos:row["start"]])
        src = row["source"]
        if row["name"] in called_names:
            if row["static"]:
                src = re.sub(r"^(\s*)static\s+", r"\1", src, count=1)
            prototypes.append(prototype_from_signature(row["signature"]))
            externalized_names.append(row["name"])
        pieces.append(src)
        pos = row["end"]

    pieces.append(suffix[pos:])
    return "".join(pieces), prototypes, externalized_names



def externalize_header_static_function_prototypes(
    header: str,
) -> tuple[str, list[str]]:
    """Remove internal linkage from declaration-only functions in the shared header.

    A static function prototype in translated_runtime.h gives every shard its own
    private function contract and triggers C2129 because the body lives in runtime
    main. Full static inline/template definitions are intentionally untouched.
    """
    masked = mask_noncode(header)
    pattern = re.compile(
        r"(?ms)^(?P<indent>[ \t]*)static\s+"
        r"(?P<decl>[^;{}\n][^;{}]*?\b"
        r"(?P<name>[A-Za-z_]\w*)\s*\([^;{}]*\)\s*;)"
    )
    matches = list(pattern.finditer(masked))
    if not matches:
        return header, []

    out = header
    names: list[str] = []
    for match in reversed(matches):
        static_start = match.start() + len(match.group("indent"))
        static_end = static_start + len("static ")
        if out[static_start:static_end] != "static ":
            raise SystemExit(
                "[Phase6TU] shared static prototype mask/source mismatch"
            )
        out = out[:static_start] + out[static_end:]
        names.append(match.group("name"))

    names.reverse()
    return out, names


def externalize_named_runtime_definitions(
    text: str,
    names: set[str],
) -> tuple[str, list[str]]:
    """Ensure shared-header prototype names have one external runtime body."""
    if not names:
        return text, []

    masked = mask_noncode(text)
    edits: list[tuple[int, int, str]] = []
    confirmed: list[str] = []

    for name in sorted(names):
        any_pattern = re.compile(
            rf"(?ms)^(?P<indent>[ \t]*)(?P<static>static\s+)?"
            rf"(?P<sig>[^;{{}}\n][^;{{}}]*?\b{re.escape(name)}\s*"
            rf"\([^;{{}}]*\)\s*)\{{"
        )
        found = list(any_pattern.finditer(masked))
        if len(found) != 1:
            raise SystemExit(
                f"[Phase6TU] shared prototype {name} expected exactly one "
                f"runtime definition, found {len(found)}"
            )

        m = found[0]
        if m.group("static"):
            static_start = m.start() + len(m.group("indent"))
            static_end = static_start + len("static ")
            edits.append((static_start, static_end, name))
        confirmed.append(name)

    out = text
    for start_pos, end_pos, name in sorted(edits, reverse=True):
        if out[start_pos:end_pos] != "static ":
            raise SystemExit(
                f"[Phase6TU] runtime definition linkage position mismatch: {name}"
            )
        out = out[:start_pos] + out[end_pos:]

    return out, confirmed



def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--shards", type=int, default=SHARD_COUNT)
    args = ap.parse_args()

    if args.shards != 64:
        raise SystemExit("[Phase6TU] Phase 6 currently requires exactly 64 shards")

    text = args.source.read_text(encoding="utf-8", errors="strict")
    off = text.find(OFF_MARKER)
    if off < 0:
        raise SystemExit("[Phase6TU] optimize-off marker missing")
    body_start = off + len(OFF_MARKER)
    on = text.find(ON_MARKER, body_start)
    if on < 0:
        raise SystemExit("[Phase6TU] optimize-on marker missing")

    prefix = text[:body_start]
    body = text[body_start:on]
    suffix = text[on:]
    funcs = parse_translated_functions(body)
    local_arch_stats = validate_local_architecture_registers(funcs)

    (
        runtime_prefix,
        helper_prototypes,
        template_definitions,
        inline_definitions,
    ) = externalize_prefix_functions(prefix)

    body_support_rows, body_support_source = extract_body_support_functions(body)
    body_support_names = {row["name"] for row in body_support_rows}
    runtime_prefix = externalize_named_forward_declarations(
        runtime_prefix,
        body_support_names,
    )
    for row in body_support_rows:
        helper_prototypes.append(prototype_from_signature(row["signature"]))

    suffix, suffix_support_prototypes, suffix_support_names = (
        externalize_called_suffix_support(suffix, body)
    )
    runtime_prefix = externalize_named_forward_declarations(
        runtime_prefix,
        set(suffix_support_names),
    )
    helper_prototypes.extend(suffix_support_prototypes)
    preprocessor = extract_preprocessor(prefix)
    prefix_no_funcs = remove_spans(prefix, function_spans(prefix))
    type_blocks = extract_type_blocks(prefix_no_funcs)
    globals_found, globals_missing, globals_optional_unresolved = (
        collect_runtime_globals(prefix, body, preprocessor)
    )
    if globals_missing:
        raise SystemExit(
            "[Phase6TU] could not safely declarationize required runtime globals: "
            + ", ".join(globals_missing)
        )
    runtime_prefix = externalize_runtime_globals(runtime_prefix, globals_found)

    # main.cpp keeps exactly one definition of runtime/support state. No translated
    # bodies remain here; linker resolves them from translated_###.cpp.
    runtime_main = runtime_prefix + body_support_source + suffix
    runtime_main, remaining_subs_externalized = externalize_remaining_sub_symbols(
        runtime_main
    )
    assert_no_internal_sub_linkage(runtime_main, "runtime main")

    runtime_masked = mask_noncode(runtime_main)
    for support_name in sorted(
        body_support_names | set(suffix_support_names)
    ):
        stale_static_decl = re.search(
            rf"(?m)^[ \t]*static\s+[^;\n{{}}]*\b"
            rf"{re.escape(support_name)}\s*\([^;{{}}]*\)\s*;",
            runtime_masked,
        )
        if stale_static_decl:
            raise SystemExit(
                "[Phase6TU] externally visible support still has static "
                f"forward declaration: {support_name}"
            )

    header_parts = [
        "#pragma once\n",
        "/* AUTO-GENERATED Phase6 true-TU runtime declarations. */\n",
        preprocessor,
        "\n/* shared generated types */\n",
    ]
    for block in type_blocks:
        header_parts.append(block + "\n")
    header_parts.append("\n/* shared runtime storage */\n")
    for _, _, _, decl in globals_found:
        header_parts.append(decl + "\n")
    header_parts.append("\n/* runtime/support entry points */\n")
    seen_proto = set()
    for proto in helper_prototypes:
        if re.search(r"\bT\b", proto):
            raise SystemExit(
                "[Phase6TU] template parameter leaked into ordinary helper prototype: "
                + proto
            )
        # Translated sub_* declarations are emitted per shard instead.
        if re.search(r"\bsub_[0-9A-Fa-f]{8}\s*\(", proto):
            continue
        normalized = " ".join(proto.split())
        if normalized in seen_proto:
            continue
        seen_proto.add(normalized)
        header_parts.append(proto + "\n")

    # Inline/template definitions come last because they may reference shared
    # globals and ordinary runtime helpers declared above.
    if template_definitions or inline_definitions:
        header_parts.append("\n/* shared template/inline support */\n")
        for template_definition in template_definitions:
            header_parts.append(template_definition + "\n")
        for inline_definition in inline_definitions:
            header_parts.append(inline_definition + "\n")

    header = "".join(header_parts)

    header, shared_static_prototype_names = (
        externalize_header_static_function_prototypes(header)
    )
    runtime_main, shared_runtime_definitions_externalized = (
        externalize_named_runtime_definitions(
            runtime_main,
            set(shared_static_prototype_names),
        )
    )

    header_masked = mask_noncode(header)
    stale_static_prototype = re.search(
        r"(?ms)^[ \t]*static\s+[^;{}\n][^;{}]*?"
        r"\b[A-Za-z_]\w*\s*\([^;{}]*\)\s*;",
        header_masked,
    )
    if stale_static_prototype:
        line = header_masked.count("\n", 0, stale_static_prototype.start()) + 1
        raise SystemExit(
            "[Phase6TU] shared header retains a static function prototype "
            f"at line {line}"
        )

    # Any inline body dependency must be declared before the inline section.
    inline_marker = header.find("/* shared template/inline support */")
    if inline_marker >= 0:
        before_inline = mask_noncode(header[:inline_marker])
        for dependency in (
            "recomp_guest_read64",
            "recomp_guest_read32",
            "recomp_guest_read16",
            "recomp_guest_read8",
            "recomp_guest_write32",
            "recomp_guest_write16",
            "recomp_guest_write8",
            "g_x87_status_word",
        ):
            if dependency in mask_noncode("".join(inline_definitions)):
                if re.search(rf"\b{re.escape(dependency)}\b", before_inline) is None:
                    raise SystemExit(
                        "[Phase6TU] inline dependency not declared before shared "
                        f"inline bodies: {dependency}"
                    )

    if "XBOX_REP_MOVS(" in mask_noncode(body):
        if not re.search(
            r"(?m)^\s*static\s+__forceinline\s+void\s+"
            r"XBOX_REP_MOVS\s*\(",
            mask_noncode(header),
        ):
            raise SystemExit(
                "[Phase6TU] XBOX_REP_MOVS is used by translated code but its "
                "inline definition is missing from translated_runtime.h"
            )

    malformed_externs = re.findall(
        r"(?m)^\s*extern\s+[gs]_[A-Za-z_]\w*\s*;\s*$",
        mask_noncode(header),
    )
    if malformed_externs:
        raise SystemExit(
            "[Phase6TU] generated runtime header contains type-less externs: "
            + ", ".join(x.strip() for x in malformed_externs[:8])
        )

    buckets: list[list[dict]] = [[] for _ in range(args.shards)]
    for row in funcs:
        buckets[shard_index_for_va(row["va"])].append(row)
    for bucket in buckets:
        bucket.sort(key=lambda r: r["va"])

    out_dir = args.out_dir
    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)

    changed = []
    unchanged = []
    main_path = out_dir / "main.cpp"
    mono_path = out_dir / "main_monolithic.cpp"
    header_path = shard_dir / "translated_runtime.h"
    for path, payload in (
        (main_path, runtime_main),
        (mono_path, text),
        (header_path, header),
    ):
        (changed if write_if_changed(path, payload) else unchanged).append(path.name)

    shard_rows = []
    expected_names = {"translated_runtime.h"}
    for index, bucket in enumerate(buckets):
        name = f"translated_{index:03d}.cpp"
        expected_names.add(name)
        callees = sorted(
            {
                callee
                for row in bucket
                for callee in SUB_CALL_RE.findall(mask_noncode(row["source"]))
            }
        )
        payload = [
            '#include "translated_runtime.h"\n',
            '#pragma optimize("", off)\n',
        ]
        if callees:
            payload.append("\n/* translated callees used by this shard */\n")
            payload.extend(f"void {name_}(void);\n" for name_ in callees)
        payload.append("\n")

        declared_callees = set(callees)
        used_callees = {
            callee
            for row in bucket
            for callee in SUB_CALL_RE.findall(mask_noncode(row["source"]))
        }
        missing_callee_decls = sorted(used_callees - declared_callees)
        if missing_callee_decls:
            raise SystemExit(
                f"[Phase6TU] {name} missing translated callee declarations: "
                + ", ".join(missing_callee_decls[:16])
            )

        for row in bucket:
            payload.append(row["source"])
            payload.append("\n\n")
        payload.append('#pragma optimize("", on)\n')
        shard_text = "".join(payload)
        shard_text, shard_subs_externalized = externalize_remaining_sub_symbols(
            shard_text
        )
        assert_no_internal_sub_linkage(shard_text, name)

        shard_path = shard_dir / name
        (changed if write_if_changed(shard_path, shard_text) else unchanged).append(name)
        shard_rows.append(
            {
                "name": name,
                "functions": len(bucket),
                "sub_symbols_externalized": shard_subs_externalized,
                "chars": len(shard_text),
                "min_va": f"0x{bucket[0]['va']:08X}" if bucket else None,
                "max_va": f"0x{bucket[-1]['va']:08X}" if bucket else None,
                "sha256": hashlib.sha256(shard_text.encode("utf-8")).hexdigest(),
            }
        )

    stale_removed = []
    for p in shard_dir.iterdir():
        if p.is_file() and p.name not in expected_names:
            p.unlink()
            stale_removed.append(p.name)

    manifest = {
        "phase": "6TU",
        "source": str(args.source),
        "shard_count": args.shards,
        "translated_functions": len(funcs),
        "runtime_helpers_externalized": len(helper_prototypes),
        "runtime_template_definitions_shared": len(template_definitions),
        "runtime_inline_definitions_shared": len(inline_definitions),
        "body_support_functions_preserved": [row["name"] for row in body_support_rows],
        "suffix_support_functions_externalized": suffix_support_names,
        "shared_static_prototypes_externalized": shared_static_prototype_names,
        "shared_runtime_definitions_externalized": shared_runtime_definitions_externalized,
        "runtime_globals_externalized": len(globals_found),
        "runtime_global_names_externalized": sum(
            len(declaration_statement_names(stmt))
            for _, _, stmt, _ in globals_found
        ),
        "runtime_globals_optional_unresolved": globals_optional_unresolved,
        "remaining_runtime_sub_symbols_externalized": remaining_subs_externalized,
        "shard_sub_symbols_externalized": sum(
            row["sub_symbols_externalized"] for row in shard_rows
        ),
        "local_architecture_registers": sorted(LOCAL_TRANSLATED_ARCH_REGS),
        "local_architecture_stats": local_arch_stats,
        "stable_assignment": "multiplicative guest-VA hash",
        "content_stable_writes": True,
        "changed_files": sorted(changed),
        "unchanged_files": sorted(unchanged),
        "stale_removed": sorted(stale_removed),
        "shards": shard_rows,
    }
    manifest_path = out_dir / "phase6tu-manifest.json"
    write_if_changed(manifest_path, json.dumps(manifest, indent=2) + "\n")

    counts = [len(x) for x in buckets]
    print("[Phase6TU] TRUE TRANSLATION-UNIT EMISSION: PASS")
    print(f"[Phase6TU] emitter_revision={TRUE_TU_EMITTER_REVISION}")
    print(f"[Phase6TU] translated_functions={len(funcs)} shards={args.shards}")
    print(f"[Phase6TU] shard_functions_min={min(counts)} max={max(counts)}")
    print(f"[Phase6TU] runtime_helpers_externalized={len(helper_prototypes)}")
    print(f"[Phase6TU] runtime_template_definitions_shared={len(template_definitions)}")
    print(f"[Phase6TU] runtime_inline_definitions_shared={len(inline_definitions)}")
    print(
        "[Phase6TU] body_support_functions_preserved="
        f"{len(body_support_rows)}"
    )
    if body_support_rows:
        print(
            "[Phase6TU] body_support_names="
            + ",".join(row["name"] for row in body_support_rows)
        )
    print(
        "[Phase6TU] suffix_support_functions_externalized="
        f"{len(suffix_support_names)}"
    )
    if suffix_support_names:
        print(
            "[Phase6TU] suffix_support_names="
            + ",".join(suffix_support_names)
        )
    print(
        "[Phase6TU] shared_static_prototypes_externalized="
        f"{len(shared_static_prototype_names)}"
    )
    if shared_static_prototype_names:
        print(
            "[Phase6TU] shared_static_prototype_names="
            + ",".join(shared_static_prototype_names)
        )
    print(f"[Phase6TU] runtime_globals_externalized={len(globals_found)}")
    print(
        "[Phase6TU] runtime_global_names_externalized="
        f"{sum(len(declaration_statement_names(stmt)) for _, _, stmt, _ in globals_found)}"
    )
    print(
        "[Phase6TU] runtime_globals_optional_unresolved="
        f"{len(globals_optional_unresolved)}"
    )
    print(f"[Phase6TU] remaining_runtime_sub_symbols_externalized={remaining_subs_externalized}")
    print(
        "[Phase6TU] shard_sub_symbols_externalized="
        f"{sum(row['sub_symbols_externalized'] for row in shard_rows)}"
    )
    print("[Phase6TU] local_architecture_registers=" + ",".join(sorted(LOCAL_TRANSLATED_ARCH_REGS)))
    print(
        "[Phase6TU] local_ebp_users="
        f"{local_arch_stats['ebp_users']} seeded_from_g_seh_ebp="
        f"{local_arch_stats['ebp_seeded_from_g_seh_ebp']}"
    )
    print(f"[Phase6TU] changed_files={len(changed)} unchanged_files={len(unchanged)} stale_removed={len(stale_removed)}")
    print(f"[Phase6TU] out={out_dir}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
