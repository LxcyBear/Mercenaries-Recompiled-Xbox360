#!/usr/bin/env python3
"""Phase 4C-A: analyze the real retail entry-rooted translated startup closure.

This consumes the exact Phase-3N-A audited generated tree. It does not execute
retail code and does not emit copyrighted generated bodies into the repository.
"""

from __future__ import annotations

import argparse
from collections import Counter, deque
import hashlib
import json
from pathlib import Path
import re

ENTRY_VA = 0x0022964A

FUNC_START_RE = re.compile(
    r"(?m)^\s*(?:static\s+)?(?:__forceinline\s+)?"
    r"void\s+(sub_([0-9A-Fa-f]{8}))\s*"
    r"\(\s*void\s*\)\s*\{"
)
SUB_SYMBOL_RE = re.compile(r"\bsub_([0-9A-Fa-f]{8})\b")
CALL_TOKEN_RE = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
DYNAMIC_TOKENS = (
    "RECOMP_ICALL",
    "RECOMP_ICALL_SAFE",
    "RECOMP_ITAIL",
    "RECOMP_ITAIL_SAFE",
    "recomp_lookup",
    "recomp_lookup_manual",
    "recomp_lookup_kernel",
)
COMMON_CALLS = {
    "if", "while", "for", "switch", "sizeof",
    "memcpy", "memmove", "memset", "memcmp",
    "sqrt", "sqrtf", "floor", "ceil", "fabs", "isnan", "ldexp",
}


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


def matching_brace(masked: str, open_index: int) -> int:
    depth = 0
    for index in range(open_index, len(masked)):
        ch = masked[index]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                return index + 1
    raise ValueError(f"unmatched brace at offset {open_index}")


def extract_functions(root: Path) -> dict[int, dict]:
    functions: dict[int, dict] = {}
    for path in sorted(root.glob("recomp_*.c")):
        if path.name in ("recomp_dispatch.c", "recomp_stubs_unresolved.c"):
            continue
        raw = path.read_text(encoding="utf-8", errors="replace")
        masked = mask_noncode(raw)
        for match in FUNC_START_RE.finditer(masked):
            va = int(match.group(2), 16)
            open_index = masked.find("{", match.start(), match.end())
            end = matching_brace(masked, open_index)
            if va in functions:
                raise SystemExit(
                    f"[Phase4C-A] duplicate translated function 0x{va:08X}"
                )
            source = raw[match.start():end]
            masked_source = masked[match.start():end]
            functions[va] = {
                "va": va,
                "name": match.group(1),
                "file": path.name,
                "source": source,
                "masked": masked_source,
            }
    return functions


def load_guest_sizes(path: Path) -> dict[int, int]:
    rows = json.loads(path.read_text(encoding="utf-8-sig"))
    result: dict[int, int] = {}
    for row in rows:
        try:
            start = int(str(row["start"]), 0)
            size = int(str(row.get("size", 0)), 0)
        except (KeyError, TypeError, ValueError):
            continue
        result[start] = size
    return result


def direct_dependencies(row: dict) -> list[int]:
    own = row["name"].lower()
    deps = {
        int(match.group(1), 16)
        for match in SUB_SYMBOL_RE.finditer(row["masked"])
        if f"sub_{match.group(1).lower()}" != own
    }
    return sorted(deps)


def composite_tree_sha(root: Path) -> str:
    lines = []
    for path in sorted(root.glob("recomp_*.c")):
        digest = hashlib.sha256(path.read_bytes()).hexdigest().upper()
        lines.append(f"{path.name}:{path.stat().st_size}:{digest}")
    joined = "\r\n".join(lines).encode("utf-8")
    return hashlib.sha256(joined).hexdigest().upper()


def analyze(functions: dict[int, dict], sizes: dict[int, int]) -> dict:
    if ENTRY_VA not in functions:
        raise SystemExit(
            f"[Phase4C-A] retail entry 0x{ENTRY_VA:08X} is absent from audited tree"
        )

    queue = deque([(ENTRY_VA, 0)])
    seen: set[int] = set()
    depth_by_va: dict[int, int] = {}
    missing: set[int] = set()
    dynamic_rows: list[dict] = []
    helper_counter: Counter[str] = Counter()
    max_depth = 0

    while queue:
        va, depth = queue.popleft()
        if va in seen:
            continue
        seen.add(va)
        depth_by_va[va] = depth
        max_depth = max(max_depth, depth)

        row = functions[va]
        for dep in direct_dependencies(row):
            if dep not in functions:
                missing.add(dep)
            elif dep not in seen:
                queue.append((dep, depth + 1))

        dynamic = [
            token for token in DYNAMIC_TOKENS
            if re.search(r"\b" + re.escape(token) + r"\b", row["masked"])
        ]
        if dynamic:
            dynamic_rows.append({
                "address": f"0x{va:08X}",
                "name": row["name"],
                "tokens": dynamic,
            })

        calls = set(CALL_TOKEN_RE.findall(row["masked"]))
        calls.discard(row["name"])
        calls -= COMMON_CALLS
        calls = {
            call for call in calls
            if not call.startswith("sub_")
            and not call.startswith("MEM")
            and not call.startswith("GUEST_")
            and not call.startswith("XBOX_")
        }
        helper_counter.update(calls)

    members = sorted(seen, key=lambda va: (depth_by_va[va], va))
    guest_bytes = sum(int(sizes.get(va, 0)) for va in members)
    source_bytes = sum(
        len(functions[va]["source"].encode("utf-8")) for va in members
    )

    member_rows = [
        {
            "address": f"0x{va:08X}",
            "name": functions[va]["name"],
            "depth": depth_by_va[va],
            "guest_bytes": int(sizes.get(va, 0)),
            "source_bytes": len(functions[va]["source"].encode("utf-8")),
            "source_file": functions[va]["file"],
            "direct_dependencies": [
                f"0x{dep:08X}" for dep in direct_dependencies(functions[va])
            ],
        }
        for va in members
    ]

    return {
        "entry": f"0x{ENTRY_VA:08X}",
        "member_count": len(members),
        "max_direct_depth": max_depth,
        "guest_bytes": guest_bytes,
        "source_bytes": source_bytes,
        "missing_direct_dependencies": [
            f"0x{va:08X}" for va in sorted(missing)
        ],
        "dynamic_boundary_count": len(dynamic_rows),
        "dynamic_boundaries": dynamic_rows,
        "helper_call_histogram": helper_counter.most_common(),
        "members": member_rows,
    }


def render_text(report: dict) -> str:
    closure = report["closure"]
    lines = [
        "[Phase4C-A] RETAIL ENTRY-ROOTED STARTUP CLOSURE",
        f"[Phase4C-A] Retail entry: {closure['entry']}",
        f"[Phase4C-A] Reachable direct translated bodies: {closure['member_count']}",
        f"[Phase4C-A] Maximum direct-call depth: {closure['max_direct_depth']}",
        f"[Phase4C-A] Reachable retail guest bytes: {closure['guest_bytes']}",
        f"[Phase4C-A] Reachable generated source bytes: {closure['source_bytes']}",
        f"[Phase4C-A] Missing direct translated dependencies: "
        f"{len(closure['missing_direct_dependencies'])}",
        f"[Phase4C-A] Dynamic/indirect boundary bodies: "
        f"{closure['dynamic_boundary_count']}",
        "",
        "[Phase4C-A] First 64 breadth-first members:",
    ]
    for row in closure["members"][:64]:
        lines.append(
            f"  depth={row['depth']:3d} {row['address']} "
            f"guest={row['guest_bytes']:5d} {row['source_file']}"
        )

    if closure["missing_direct_dependencies"]:
        lines += ["", "[Phase4C-A] Missing direct dependencies:"]
        lines += [
            f"  {value}" for value in closure["missing_direct_dependencies"][:128]
        ]

    if closure["dynamic_boundaries"]:
        lines += ["", "[Phase4C-A] First dynamic/indirect boundaries:"]
        for row in closure["dynamic_boundaries"][:64]:
            lines.append(
                f"  {row['address']} {'/'.join(row['tokens'])}"
            )

    lines += [
        "",
        "[Phase4C-A] STRUCTURAL RESULT: "
        + ("PASS" if report["structural_pass"] else "FAIL"),
    ]
    if report["structural_pass"]:
        lines.append(
            "[Phase4C-A] Entry-rooted direct translated closure is complete "
            "in the locked Phase-3N-A tree."
        )
        lines.append(
            "[Phase4C-A] READY: use this manifest to build the first "
            "startup execution slice."
        )
    return "\n".join(lines) + "\n"


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--gate-report", type=Path, required=True)
    ap.add_argument("--phase4-report", type=Path, required=True)
    ap.add_argument("--json-out", type=Path, required=True)
    ap.add_argument("--text-out", type=Path, required=True)
    args = ap.parse_args()

    gate = json.loads(args.gate_report.read_text(encoding="utf-8-sig"))
    if gate.get("phase") != "3N-A" or gate.get("gate_a_pass") is not True:
        raise SystemExit("[Phase4C-A] Phase 3N-A audit is not a locked PASS")

    p4 = json.loads(args.phase4_report.read_text(encoding="utf-8-sig"))
    counts = p4.get("counts", {})
    required_counts = {
        "imports": 111,
        "host_surface_flagged": 0,
        "platform_surface_bound": 15,
        "guest_native_bound": 2,
        "guest_arg_metadata_missing": 0,
        "guest_arg_metadata_mismatch": 0,
        "fallback_referenced_imports": 0,
        "fallback_static_refs": 0,
    }
    for key, expected in required_counts.items():
        actual = int(counts.get(key, -1))
        if actual != expected:
            raise SystemExit(
                f"[Phase4C-A] Phase 4B final audit mismatch: "
                f"{key} expected {expected}, got {actual}"
            )

    actual_tree = composite_tree_sha(args.generated_root)
    expected_tree = str(gate.get("generated_tree_sha256", "")).upper()
    if actual_tree != expected_tree:
        raise SystemExit(
            "[Phase4C-A] locked Phase-3N-A generated tree changed: "
            f"expected {expected_tree}, got {actual_tree}"
        )

    functions = extract_functions(args.generated_root)
    sizes = load_guest_sizes(args.functions)
    closure = analyze(functions, sizes)

    structural_pass = (
        not closure["missing_direct_dependencies"]
        and closure["member_count"] > 0
    )
    report = {
        "phase": "4C-A",
        "entry": f"0x{ENTRY_VA:08X}",
        "source_phase3n_tree_sha256": actual_tree,
        "phase4_service_split": {
            "host_surface": int(counts["host_surface_flagged"]),
            "platform_bound": int(counts["platform_surface_bound"]),
            "guest_native": int(counts["guest_native_bound"]),
        },
        "closure": closure,
        "structural_pass": structural_pass,
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )
    args.text_out.write_text(render_text(report), encoding="utf-8")

    print(render_text(report), end="")
    print(f"[Phase4C-A] JSON report: {args.json_out}")
    print(f"[Phase4C-A] Text report: {args.text_out}")
    return 0 if structural_pass else 1


if __name__ == "__main__":
    raise SystemExit(main())
