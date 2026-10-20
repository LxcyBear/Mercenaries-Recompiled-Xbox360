#!/usr/bin/env python3
"""Phase 5BD: regional translated sweep after the 5BC ICALL frontier.

Inherits the hardware-proven Phase 5BC package, requires the new runtime target
0x00237801, and pre-packs a support-clean neighborhood around the 0x00237xxx /
0x00238xxx startup subsystem so multiple subsequent exact indirect targets can
be consumed by the already-proven generic packed dispatcher.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

NEW_ROOT = 0x00237801
REGION_START = 0x00236000
REGION_END = 0x00239000
DIRECT_DEPTH = 6
DIRECT_CAP = 256
TOTAL_NEW_CAP = 256
BUILD_TAG = "P5BD-REGIONALSWEEP237801-20261020-A"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase5BD] could not load module: {path}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_exact_generated_target(root: int, by_va: dict, generated: dict) -> None:
    if root not in by_va:
        containing = [
            row
            for row in by_va.values()
            if int(row["start"]) < root < int(row["end"])
        ]
        if containing:
            row = sorted(containing, key=lambda item: int(item["start"]))[-1]
            raise SystemExit(
                f"[Phase5BD] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Regional sweep refuses a mid-function indirect target."
            )
        raise SystemExit(
            f"[Phase5BD] target 0x{root:08X} is absent from the function inventory"
        )

    if root not in generated:
        row = by_va[root]
        raise SystemExit(
            f"[Phase5BD] target 0x{root:08X} is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )


def instrument_new_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase5BD] could not instrument regional-sweep root")
    return (
        rendered[: brace_pos + 1]
        + "\n    s_phase5bdRegionalRootEntered = 1;"
        + rendered[brace_pos + 1 :]
    )


def relabel(main_text: str, env_text: str) -> tuple[str, str]:
    main_text = main_text.replace(
        "P5BC-BROADSWEEP237052-20261020-C",
        BUILD_TAG,
    )
    env_text = env_text.replace(
        "P5BC-BROADSWEEP237052-20261020-C",
        BUILD_TAG,
    )
    main_text = main_text.replace(
        "phase5bc_env_build_cookie",
        "phase5bd_env_build_cookie",
    )
    env_text = env_text.replace(
        "phase5bc_env_build_cookie",
        "phase5bd_env_build_cookie",
    )
    main_text = main_text.replace("50354243", "50354244")
    env_text = env_text.replace("50354243", "50354244")
    main_text = main_text.replace("PHASE 5BC", "PHASE 5BD")
    env_text = env_text.replace("PHASE 5BC", "PHASE 5BD")
    main_text = main_text.replace("Phase 5BC", "Phase 5BD")
    env_text = env_text.replace("Phase 5BC", "Phase 5BD")
    return main_text, env_text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--entry-report", type=Path, required=True)
    ap.add_argument("--thread-report", type=Path, required=True)
    ap.add_argument("--phase3n-template", type=Path, required=True)
    ap.add_argument("--phase2e-source", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load_module(args.base_emitter, "phase5bd_phase4c_base")
    phase5bb = load_module(args.base_phase5bb_emitter, "phase5bd_phase5bb_base")
    phase5bc = load_module(args.base_phase5bc_emitter, "phase5bd_phase5bc_base")

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="phase5bd-base-",
        dir=str(args.out_dir.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        cmd = [
            sys.executable,
            str(args.base_phase5bc_emitter),
            "--base-phase5bb-emitter",
            str(args.base_phase5bb_emitter),
            "--base-emitter",
            str(args.base_emitter),
            "--generated-root",
            str(args.generated_root),
            "--functions",
            str(args.functions),
            "--entry-report",
            str(args.entry_report),
            "--thread-report",
            str(args.thread_report),
            "--phase3n-template",
            str(args.phase3n_template),
            "--phase2e-source",
            str(args.phase2e_source),
            "--out-dir",
            str(temp_dir),
        ]
        completed = subprocess.run(
            cmd,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            text=True,
        )
        if completed.stdout:
            print(completed.stdout, end="")
        if completed.returncode != 0:
            return completed.returncode

        base_main = temp_dir / "main.cpp"
        base_env = temp_dir / "phase5_env.cpp"
        base_manifest_path = temp_dir / "phase5bc-manifest.json"
        for required in (base_main, base_env, base_manifest_path):
            if not required.exists():
                raise SystemExit(
                    f"[Phase5BD] Phase 5BC base emitter did not produce {required.name}"
                )

        main_text = base_main.read_text(encoding="utf-8")
        env_text = base_env.read_text(encoding="utf-8")
        manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact_generated_target(NEW_ROOT, by_va, generated)

    old_members = {int(item, 0) for item in manifest.get("members", [])}

    direct_members = set(
        phase5bb.bounded_promoted_members(
            base,
            NEW_ROOT,
            generated,
            DIRECT_DEPTH,
            DIRECT_CAP,
        )
    )

    # Add nearby exact generated functions so follow-on function-pointer calls
    # in this startup subsystem have a strong chance of already resolving.
    regional = [
        va
        for va in generated
        if REGION_START <= va < REGION_END and va not in old_members
    ]
    regional.sort(key=lambda va: (abs(va - NEW_ROOT), va))

    candidate_order: list[int] = []
    for va in sorted(direct_members, key=lambda value: (value != NEW_ROOT, value)):
        if va not in old_members and va not in candidate_order:
            candidate_order.append(va)

    for va in regional:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    if NEW_ROOT not in candidate_order and NEW_ROOT not in old_members:
        candidate_order.insert(0, NEW_ROOT)

    if len(candidate_order) > TOTAL_NEW_CAP:
        # NEW_ROOT and direct closure have priority over neighborhood extras.
        candidate_order = candidate_order[:TOTAL_NEW_CAP]
        if NEW_ROOT not in candidate_order:
            candidate_order[-1] = NEW_ROOT

    candidate_new_members = sorted(set(candidate_order))
    if NEW_ROOT not in candidate_new_members:
        raise SystemExit("[Phase5BD] regional candidate set lost 0x00237801")

    expanded_members = set(old_members) | set(candidate_new_members)
    new_members = list(candidate_new_members)

    declaration_marker = "static int s_phase5bcSweepRootEntered;"
    if declaration_marker not in main_text:
        raise SystemExit("[Phase5BD] Phase 5BC sweep state marker changed")
    main_text = main_text.replace(
        declaration_marker,
        declaration_marker + "\nstatic int s_phase5bdRegionalRootEntered;",
        1,
    )

    reset_marker = "    s_phase5bcSweepRootEntered = 0;\n"
    if reset_marker not in main_text:
        raise SystemExit("[Phase5BD] Phase 5BC root reset marker changed")
    main_text = main_text.replace(
        reset_marker,
        reset_marker + "    s_phase5bdRegionalRootEntered = 0;\n",
        1,
    )

    gate_marker = "            s_phase5bcSweepRootEntered &&\n"
    if gate_marker not in main_text:
        raise SystemExit("[Phase5BD] Phase 5BC PASS gate marker changed")
    main_text = main_text.replace(
        gate_marker,
        gate_marker + "            s_phase5bdRegionalRootEntered &&\n",
        1,
    )

    # Reuse the 5BC support-clean packer but point its mandatory-root
    # instrumentation at the new runtime-proven ICALL target.
    phase5bc.SWEEP_ROOT = NEW_ROOT
    phase5bc.instrument_root_entry = instrument_new_root

    (
        main_text,
        rendered_by_va,
        new_direct_frontiers,
        pruned_members,
    ) = phase5bc.insert_pack_members(
        main_text,
        base,
        phase5bb,
        generated,
        new_members,
        expanded_members,
    )

    if NEW_ROOT not in new_members:
        raise SystemExit(
            "[Phase5BD] support-clean pruning attempted to remove mandatory "
            "hardware-observed root 0x00237801"
        )

    main_text, env_text = relabel(main_text, env_text)

    policy_old = (
        "Policy: retain prior Phase-5 proofs, seed ICALL_SAFE 0022C3FA -> "
        "00237052, sweep a depth-6/cap-256 exact generated closure, and "
        "auto-dispatch only exact targets already present in the widened pack"
    )
    policy_new = (
        "Policy: retain the proven 5BC generic dispatcher, seed ICALL_SAFE "
        "0023701A -> 00237801, pre-pack a support-clean 00236000-00239000 "
        "regional neighborhood capped at 256 new functions, and continue "
        "only through exact targets already present in the widened pack"
    )
    if policy_old in main_text:
        main_text = main_text.replace(policy_old, policy_new, 1)

    required_main_markers = (
        BUILD_TAG,
        "case 0x00237801u: return sub_00237801;",
        "s_phase5bdRegionalRootEntered = 1;",
        "s_phase5bdRegionalRootEntered &&",
        "PASS: Phase 5BD broad-sweep ICALL_SAFE",
        "PHASE 5BD BROAD TRANSLATED SWEEP RESULT",
    )
    for marker in required_main_markers:
        if marker not in main_text:
            raise SystemExit(
                f"[Phase5BD] generated main lost required regional-sweep marker: {marker}"
            )

    if "PHASE 5BD RETAIL ENVIRONMENT PREP START" not in env_text:
        raise SystemExit("[Phase5BD] environment phase label patch failed")
    if "phase5bd_env_build_cookie" not in env_text or "50354244" not in env_text:
        raise SystemExit("[Phase5BD] environment cookie patch failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "5BD"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = len(expanded_members)
    manifest["members"] = [f"0x{va:08X}" for va in sorted(expanded_members)]
    manifest["phase5bd_regional_sweep"] = {
        "observed_phase": "5BC",
        "boundary_kind": "ICALL_SAFE",
        "observed_caller": "0x0023701A",
        "root": "0x00237801",
        "observed_fault": 0,
        "observed_esp": "0x008BFF40",
        "observed_saved_esp": "0x008BFF44",
        "region_start": f"0x{REGION_START:08X}",
        "region_end_exclusive": f"0x{REGION_END:08X}",
        "direct_closure_depth": DIRECT_DEPTH,
        "direct_closure_cap": DIRECT_CAP,
        "total_new_cap": TOTAL_NEW_CAP,
        "base_pack_members": len(old_members),
        "direct_candidate_members": len(direct_members - old_members),
        "regional_generated_candidates": len(regional),
        "candidate_new_members": len(candidate_new_members),
        "new_members": len(new_members),
        "pruned_members": len(pruned_members),
        "expanded_pack_members": len(expanded_members),
        "strategy": (
            "mandatory runtime-proven root plus nearest exact generated regional "
            "entries; unresolved side branches are pruned/fenced, never guessed"
        ),
        "pass_policy": (
            "all inherited 5BC invariants must hold and 0x00237801 must actually "
            "enter; generic packed dispatch may consume further exact regional "
            "targets before stopping at a genuinely unsupported boundary"
        ),
    }
    manifest["phase5bd_candidate_new_members"] = [
        f"0x{va:08X}" for va in candidate_new_members
    ]
    manifest["phase5bd_new_members"] = [
        f"0x{va:08X}" for va in new_members
    ]
    manifest["phase5bd_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned_members.items())
    ]
    manifest["phase5bd_new_direct_frontier_targets"] = [
        f"0x{va:08X}" for va in sorted(new_direct_frontiers)
    ]

    (args.out_dir / "phase5bd-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_new_source = sum(len(rendered_by_va[va]) for va in new_members)
    print(
        "[Phase5BD] REGIONAL SWEEP PACK: "
        f"base={len(old_members)} direct_candidates={len(direct_members - old_members)} "
        f"regional_candidates={len(regional)} candidate_new={len(candidate_new_members)} "
        f"pruned={len(pruned_members)} packed_new={len(new_members)} "
        f"total={len(expanded_members)} new_source_bytes={total_new_source}"
    )
    print(
        "[Phase5BD] AUTO-DISPATCH: inherited generic exact packed ICALL_SAFE "
        "+ exact packed direct continuation"
    )
    print(
        "[Phase5BD] REGION: 0x00236000-0x00238FFF, mandatory root 0x00237801"
    )
    print("[Phase5BD] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
