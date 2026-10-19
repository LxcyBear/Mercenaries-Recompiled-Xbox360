#!/usr/bin/env python3
"""Phase 3N-B: build a large XDK scale pack from the exact audited 3N-A tree."""

from __future__ import annotations

import argparse
from collections import Counter
import json
from pathlib import Path
import re
import sys

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.recomp.lower_explicit_guest_memory import _mask_noncode

# Runtime execution is intentionally the Phase 3E hardware-proven accessor.
# Stage B is a compiler/linker scale gate; arbitrary scale-only retail bodies
# must not be executed without valid game state.
EXEC_ROOT = 0x00208F30
EXEC_MEMBERS = (EXEC_ROOT,)
EXEC_DEPTH = 0

TARGET_SCALE_FUNCTIONS = 128
MIN_SCALE_FUNCTIONS = 64
MIN_SCALE_GUEST_BYTES = 0x4000

FUNC_START_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+(sub_([0-9A-Fa-f]{8}))\s*"
    r"\(\s*void\s*\)\s*\{"
)
SUB_SYMBOL_RE = re.compile(r"\bsub_[0-9A-Fa-f]{8}\b")
CALL_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
GLOBAL_TOKEN_RE = re.compile(r"\bg_[A-Za-z_][A-Za-z0-9_]*\b")
LOC_RE = re.compile(r"^(\s*)loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$")
GOTO_RE = re.compile(r"goto\s+loc_([0-9A-Fa-f]{8})\s*;")

FORBIDDEN_RE = re.compile(
    r"\b(?:RECOMP_ICALL(?:_SAFE)?|RECOMP_ITAIL(?:_SAFE)?|"
    r"XBOX_MEMCPY|XBOX_REP_MOVS|RECOMP_RDTSC|__debugbreak|"
    r"g_mm[0-7]|mm[0-7]|g_recomp_[A-Za-z0-9_]+|"
    r"recomp_native_[A-Za-z0-9_]+|recomp_lua_host_[A-Za-z0-9_]+|"
    r"recomp_ps2_[A-Za-z0-9_]+)\b"
)

C_CALLS = {
    "if", "while", "for", "switch", "sizeof",
    "memcpy", "memset", "memcmp",
    "sqrt", "sqrtf", "floor", "ceil", "fabs", "isnan", "ldexp",
}


def find_matching_brace(masked: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(masked)):
        ch = masked[index]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError(f"unmatched function brace at offset {open_index}")


def extract_functions(root: Path) -> dict[int, dict]:
    result = {}
    for path in sorted(root.glob("recomp_*.c")):
        if path.name in ("recomp_stubs_unresolved.c", "recomp_dispatch.c"):
            continue
        text = path.read_text(encoding="utf-8", errors="replace")
        masked = _mask_noncode(text)
        for match in FUNC_START_RE.finditer(masked):
            name = match.group(1)
            address = int(match.group(2), 16)
            open_index = masked.find("{", match.start(), match.end())
            end = find_matching_brace(masked, open_index)
            if address in result:
                raise SystemExit(
                    f"[Phase3N-B] duplicate generated definition {name}"
                )
            result[address] = {
                "address": address,
                "name": name,
                "source": text[match.start():end],
                "file": path.name,
            }
    return result


def load_guest_sizes(path: Path) -> dict[int, int]:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    sizes = {}
    for row in rows:
        try:
            start = int(str(row["start"]), 0)
            size = int(str(row.get("size", 0)), 0)
        except (KeyError, TypeError, ValueError):
            continue
        sizes[start] = size
    return sizes


def template_symbols(text: str) -> set[str]:
    symbols = set(C_CALLS)
    symbols.update(re.findall(
        r"(?m)^\s*#\s*define\s+([A-Za-z_][A-Za-z0-9_]*)\b", text
    ))
    # The Phase 3M-derived harness is self-contained. Any call token already
    # present in it therefore names either a local helper or a C/XDK facility
    # that the known hardware project already links.
    symbols.update(CALL_TOKEN_RE.findall(_mask_noncode(text)))
    symbols.update({
        "recomp_x87_load_f80",
        "x87_set_compare_status",
    })
    return symbols


def direct_sub_symbols(source: str, own_name: str) -> set[str]:
    masked = _mask_noncode(source)
    symbols = set(SUB_SYMBOL_RE.findall(masked))
    symbols.discard(own_name)
    return symbols


def unknown_calls(source: str, own_name: str, supported: set[str]) -> list[str]:
    masked = _mask_noncode(source)
    calls = set(CALL_TOKEN_RE.findall(masked))
    calls.discard(own_name)
    return sorted(token for token in calls if token not in supported)


def localize(source: str, name: str) -> str:
    localized, count = re.subn(
        rf"\bvoid\s+{re.escape(name)}\s*\(\s*void\s*\)",
        f"static void {name}(void)",
        source,
        count=1,
    )
    if count != 1:
        raise SystemExit(
            f"[Phase3N-B] could not localize generated definition {name}"
        )
    return localized


def instrument_exec(source: str) -> str:
    out = []
    current_va = None
    for line in source.splitlines():
        match = LOC_RE.match(line)
        if match:
            current_va = int(match.group(2), 16)
            out.append(line)
            out.append(
                f"{match.group(1)}    RECOMP_BUDGET_TICK(0x{current_va:08X}u);"
            )
            continue
        if current_va is not None and "goto loc_" in line:
            def replace_goto(goto_match):
                target = int(goto_match.group(1), 16)
                original = goto_match.group(0)
                if target <= current_va:
                    return (
                        "{ RECOMP_TRACE_BACKEDGE("
                        f"0x{current_va:08X}u, 0x{target:08X}u); "
                        + original + " }"
                    )
                return original
            line = GOTO_RE.sub(replace_goto, line)
        out.append(line)
    return "\n".join(out) + ("\n" if source.endswith("\n") else "")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--gate-report", type=Path, required=True)
    ap.add_argument("--template", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    ap.add_argument("--main-out", type=Path, required=True)
    args = ap.parse_args()

    gate = json.loads(args.gate_report.read_text(encoding="utf-8-sig"))
    if gate.get("phase") != "3N-A" or gate.get("gate_a_pass") is not True:
        raise SystemExit("[Phase3N-B] 3N-A gate report is not a PASS")
    if int(gate["recompiler"]["failed"]) != 0:
        raise SystemExit("[Phase3N-B] 3N-A report contains failed translations")
    if int(gate["portability"]["fatal_count"]) != 0:
        raise SystemExit("[Phase3N-B] 3N-A report contains fatal portability hits")
    if int(gate["portability"]["residual_unresolved_stubs"]) != 0:
        raise SystemExit("[Phase3N-B] 3N-A report contains live unresolved stubs")

    functions = extract_functions(args.generated_root)
    sizes = load_guest_sizes(args.functions)
    template = args.template.read_text(encoding="utf-8")
    supported = template_symbols(template)
    supported_globals = set(GLOBAL_TOKEN_RE.findall(_mask_noncode(template)))

    missing_exec = [va for va in EXEC_MEMBERS if va not in functions]
    if missing_exec:
        raise SystemExit(
            "[Phase3N-B] audited tree is missing Phase 3E execution proof "
            "member(s): " + ", ".join(f"0x{va:08X}" for va in missing_exec)
        )

    exec_names = {f"sub_{va:08X}" for va in EXEC_MEMBERS}
    for va in EXEC_MEMBERS:
        row = functions[va]
        outside = direct_sub_symbols(row["source"], row["name"]) - exec_names
        if outside:
            raise SystemExit(
                f"[Phase3N-B] execution member {row['name']} gained outside "
                "dependency: " + ", ".join(sorted(outside))
            )
        unknown = unknown_calls(row["source"], row["name"], supported | exec_names)
        if unknown:
            raise SystemExit(
                f"[Phase3N-B] execution member {row['name']} uses unsupported "
                "helper(s): " + ", ".join(unknown[:12])
            )
        unknown_globals = sorted(
            set(GLOBAL_TOKEN_RE.findall(_mask_noncode(row["source"]))) -
            supported_globals
        )
        if unknown_globals:
            raise SystemExit(
                f"[Phase3N-B] execution member {row['name']} uses unsupported "
                "global(s): " + ", ".join(unknown_globals[:12])
            )

    rejects = Counter()
    candidates = []
    exec_set = set(EXEC_MEMBERS)
    for va, row in functions.items():
        if va in exec_set:
            continue
        source = row["source"]
        masked = _mask_noncode(source)

        if direct_sub_symbols(source, row["name"]):
            rejects["not a leaf translated body"] += 1
            continue
        forbidden = FORBIDDEN_RE.search(masked)
        if forbidden:
            rejects["unsupported runtime/dynamic surface"] += 1
            continue
        unknown = unknown_calls(source, row["name"], supported)
        if unknown:
            rejects["helper not provided by XDK harness"] += 1
            continue
        unknown_globals = (
            set(GLOBAL_TOKEN_RE.findall(masked)) - supported_globals
        )
        if unknown_globals:
            rejects["global not provided by XDK harness"] += 1
            continue

        guest_bytes = int(sizes.get(va, 0))
        if guest_bytes <= 0:
            rejects["missing guest-size metadata"] += 1
            continue

        candidates.append({
            **row,
            "guest_bytes": guest_bytes,
            "source_bytes": len(source.encode("utf-8")),
        })

    # Maximize real translated-code pressure while keeping the source count
    # deterministic across repeated preparation runs.
    candidates.sort(key=lambda row: (
        -row["guest_bytes"],
        -row["source_bytes"],
        row["address"],
    ))
    selected = candidates[:TARGET_SCALE_FUNCTIONS]

    total_guest = sum(row["guest_bytes"] for row in selected)
    total_source = sum(row["source_bytes"] for row in selected)
    if len(selected) < MIN_SCALE_FUNCTIONS:
        print("[Phase3N-B] rejection histogram:")
        for reason, count in rejects.most_common():
            print(f"[Phase3N-B]   {count:5d} {reason}")
        raise SystemExit(
            f"[Phase3N-B] only {len(selected)} safe audited leaf bodies; "
            f"need at least {MIN_SCALE_FUNCTIONS}"
        )
    if total_guest < MIN_SCALE_GUEST_BYTES:
        raise SystemExit(
            f"[Phase3N-B] selected guest code is only {total_guest} bytes; "
            f"need at least {MIN_SCALE_GUEST_BYTES}"
        )

    exec_bodies = []
    for va in EXEC_MEMBERS:
        row = functions[va]
        exec_bodies.append(localize(instrument_exec(row["source"]), row["name"]))

    scale_bodies = [
        localize(row["source"], row["name"]) for row in selected
    ]
    all_rows = [functions[va] for va in EXEC_MEMBERS] + selected
    forward_decls = "\n".join(
        f"static void {row['name']}(void);" for row in all_rows
    )
    anchor_rows = ",\n".join(
        f"    {row['name']}" for row in selected
    )

    replacements = {
        "/*__P3NB_FORWARD_DECLS__*/": forward_decls,
        "/*__P3NB_EXEC_BODIES__*/": "\n\n".join(exec_bodies),
        "/*__P3NB_SCALE_BODIES__*/": "\n\n".join(scale_bodies),
        "/*__P3NB_SCALE_ANCHORS__*/": anchor_rows,
        "__P3NB_ROOT_NAME__": f"sub_{EXEC_ROOT:08X}",
        "__P3NB_ROOT_VA__": f"0x{EXEC_ROOT:08X}u",
        "__P3NB_MEMBER_COUNT__": str(len(EXEC_MEMBERS)),
        "__P3NB_DEPTH__": str(EXEC_DEPTH),
        "__P3NB_MEMBER_VAS__": ", ".join(
            f"0x{va:08X}u" for va in EXEC_MEMBERS
        ),
        "__P3NB_SCALE_COUNT__": str(len(selected)),
        "__P3NB_SCALE_GUEST_BYTES__": str(total_guest),
        "__P3NB_SCALE_SOURCE_BYTES__": str(total_source),
    }
    for token, value in replacements.items():
        if token not in template:
            raise SystemExit(f"[Phase3N-B] template token missing: {token}")
        template = template.replace(token, value)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    args.main_out.write_text(template, encoding="utf-8")

    selection = {
        "phase": "3N-B",
        "source_gate_tree_sha256": gate["generated_tree_sha256"],
        "execution_root": f"0x{EXEC_ROOT:08X}",
        "execution_members": [f"0x{va:08X}" for va in EXEC_MEMBERS],
        "execution_member_count": len(EXEC_MEMBERS),
        "execution_depth": EXEC_DEPTH,
        "scale_function_count": len(selected),
        "scale_guest_bytes": total_guest,
        "scale_source_bytes": total_source,
        "scale_members": [
            {
                "address": f"0x{row['address']:08X}",
                "name": row["name"],
                "guest_bytes": row["guest_bytes"],
                "source_bytes": row["source_bytes"],
                "source_file": row["file"],
            }
            for row in selected
        ],
        "candidate_count": len(candidates),
        "rejections": dict(rejects),
    }
    (args.out_dir / "selection.json").write_text(
        json.dumps(selection, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase3N-B] XDK SCALE PACK READY")
    print(
        f"[Phase3N-B] Execution proof: Phase 3E reference accessor "
        f"0x{EXEC_ROOT:08X} ({len(EXEC_MEMBERS)} audited body)"
    )
    print(
        f"[Phase3N-B] Scale pack: {len(selected)} audited leaf bodies, "
        f"guest_bytes={total_guest}, source_bytes={total_source}"
    )
    print(
        f"[Phase3N-B] Source Gate-A tree: {gate['generated_tree_sha256']}"
    )
    print(f"[Phase3N-B] XDK main.cpp: {args.main_out}")
    print("[Phase3N-B] Rejection histogram:")
    for reason, count in rejects.most_common():
        print(f"[Phase3N-B]   {count:5d} {reason}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
