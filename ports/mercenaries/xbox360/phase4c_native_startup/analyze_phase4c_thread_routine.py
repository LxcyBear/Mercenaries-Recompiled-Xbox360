#!/usr/bin/env python3
"""Phase 4C-D: analyze the hardware-observed first title-thread routine."""

from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

THREAD_START = 0x0022B43F
THREAD_CTX1 = 0x002295D6
THREAD_CTX2 = 0x00000000


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase4C-D] could not load helper module {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--closure-analyzer", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--gate-report", type=Path, required=True)
    ap.add_argument("--phase4-report", type=Path, required=True)
    ap.add_argument("--json-out", type=Path, required=True)
    ap.add_argument("--text-out", type=Path, required=True)
    args = ap.parse_args()

    closure_mod = load_module(args.closure_analyzer, "phase4c_closure")
    emitter_mod = load_module(args.base_emitter, "phase4c_emitter")

    gate = json.loads(args.gate_report.read_text(encoding="utf-8-sig"))
    if gate.get("phase") != "3N-A" or gate.get("gate_a_pass") is not True:
        raise SystemExit("[Phase4C-D] Phase 3N-A audit is not a locked PASS")

    phase4 = json.loads(args.phase4_report.read_text(encoding="utf-8-sig"))
    counts = phase4.get("counts", {})
    expected = {
        "imports": 111,
        "host_surface_flagged": 0,
        "platform_surface_bound": 15,
        "guest_native_bound": 2,
        "guest_arg_metadata_missing": 0,
        "guest_arg_metadata_mismatch": 0,
        "fallback_referenced_imports": 0,
        "fallback_static_refs": 0,
    }
    for key, value in expected.items():
        actual = int(counts.get(key, -1))
        if actual != value:
            raise SystemExit(
                f"[Phase4C-D] Phase 4B baseline mismatch: "
                f"{key} expected {value}, got {actual}"
            )

    actual_tree = closure_mod.composite_tree_sha(args.generated_root)
    expected_tree = str(gate.get("generated_tree_sha256", "")).upper()
    if actual_tree != expected_tree:
        raise SystemExit(
            "[Phase4C-D] locked Phase-3N-A generated tree changed: "
            f"expected {expected_tree}, got {actual_tree}"
        )

    ranges = closure_mod.load_function_ranges(args.functions)
    functions = closure_mod.extract_functions(args.generated_root, ranges)
    sizes = closure_mod.load_guest_sizes(args.functions)

    closure_mod.ENTRY_VA = THREAD_START
    closure = closure_mod.analyze(functions, sizes, ranges)

    if closure["entry_resolution"]["kind"] != "exact_function":
        raise SystemExit(
            "[Phase4C-D] hardware-observed StartRoutine is not an exact "
            "translated function start"
        )

    member_vas = [
        int(str(row["address"]), 0)
        for row in closure["members"]
    ]

    support_template = args.base_emitter
    # Classify helper calls using the same support vocabulary as the 4C-B emitter.
    # We do not emit an XEX here; this is only a readiness report.
    translated_names = {
        functions[va]["name"]
        for va in member_vas
        if va in functions
    }

    helper_hits = {}
    for va in member_vas:
        row = functions[va]
        calls = set(
            emitter_mod.CALL_RE.findall(
                emitter_mod.mask_noncode(row["source"])
            )
        )
        calls.discard(row["name"])
        calls -= translated_names
        calls -= emitter_mod.STANDARD_CALLS
        calls -= set(emitter_mod.DEFINE_RE.findall(row["source"]))
        if calls:
            helper_hits[f"0x{va:08X} {row['name']}"] = sorted(calls)

    report = {
        "phase": "4C-D",
        "hardware_observed": {
            "start_routine": f"0x{THREAD_START:08X}",
            "context1": f"0x{THREAD_CTX1:08X}",
            "context2": f"0x{THREAD_CTX2:08X}",
            "ps_create_system_thread_ex_target": "0x800000FF",
            "frame_bytes": 44,
        },
        "source_phase3n_tree_sha256": actual_tree,
        "phase4_service_split": {
            "host_surface": int(counts["host_surface_flagged"]),
            "platform_bound": int(counts["platform_surface_bound"]),
            "guest_native": int(counts["guest_native_bound"]),
        },
        "closure": closure,
        "direct_helper_surface": helper_hits,
        "structural_pass": (
            len(closure["missing_direct_dependencies"]) == 0
            and closure["entry_resolution"]["kind"] == "exact_function"
        ),
    }

    args.json_out.parent.mkdir(parents=True, exist_ok=True)
    args.json_out.write_text(
        json.dumps(report, indent=2) + "\n",
        encoding="utf-8",
    )

    lines = [
        "[Phase4C-D] HARDWARE-OBSERVED STARTUP THREAD PREFLIGHT",
        f"[Phase4C-D] StartRoutine: 0x{THREAD_START:08X}",
        f"[Phase4C-D] Context1:     0x{THREAD_CTX1:08X}",
        f"[Phase4C-D] Context2:     0x{THREAD_CTX2:08X}",
        f"[Phase4C-D] Entry resolution: "
        f"{closure['entry_resolution']['kind']}",
        f"[Phase4C-D] Entry owner: "
        f"{closure['entry_resolution']['owner_start']}:"
        f"{closure['entry_resolution']['owner_end']} "
        f"{closure['entry_resolution']['owner_name']}",
        f"[Phase4C-D] Reachable direct translated bodies: "
        f"{closure['member_count']}",
        f"[Phase4C-D] Maximum direct-call depth: "
        f"{closure['max_direct_depth']}",
        f"[Phase4C-D] Reachable retail guest bytes: "
        f"{closure['guest_bytes']}",
        f"[Phase4C-D] Reachable generated source bytes: "
        f"{closure['source_bytes']}",
        f"[Phase4C-D] Missing direct translated dependencies: "
        f"{len(closure['missing_direct_dependencies'])}",
        f"[Phase4C-D] Dynamic/indirect boundary bodies: "
        f"{closure['dynamic_boundary_count']}",
        f"[Phase4C-D] Bodies with non-translated helper calls: "
        f"{len(helper_hits)}",
        "",
        "[Phase4C-D] First 48 breadth-first members:",
    ]

    for row in closure["members"][:48]:
        lines.append(
            f"  depth={row['depth']:3d} {row['address']} "
            f"guest={row['guest_bytes']:5d} {row['source_file']}"
        )

    if closure["dynamic_boundaries"]:
        lines += ["", "[Phase4C-D] First dynamic/indirect boundaries:"]
        for row in closure["dynamic_boundaries"][:48]:
            lines.append(
                f"  {row['address']} {'/'.join(row['tokens'])}"
            )

    if helper_hits:
        lines += ["", "[Phase4C-D] Direct helper surface:"]
        for owner, calls in sorted(helper_hits.items()):
            lines.append(f"  {owner}: {', '.join(calls)}")

    lines += [
        "",
        "[Phase4C-D] STRUCTURAL RESULT: "
        + ("PASS" if report["structural_pass"] else "FAIL"),
    ]

    text = "\n".join(lines) + "\n"
    args.text_out.write_text(text, encoding="utf-8")
    print(text, end="")
    print(f"[Phase4C-D] JSON report: {args.json_out}")
    print(f"[Phase4C-D] Text report: {args.text_out}")
    return 0 if report["structural_pass"] else 1


if __name__ == "__main__":
    raise SystemExit(main())
