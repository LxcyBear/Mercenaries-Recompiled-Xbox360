#!/usr/bin/env python3
"""Phase 5BR: fifth-pass low-.text saturation around 0x000F8BB0.

5BQ hardware consumed 0x000F8BB0 through generic packed direct dispatch and
advanced fault-free to:
    DIRECT_FRONTIER caller=0x0023A3CE target=0x000F8BB0
    ticks=67067 trace=6018 icall_dispatches=868 direct_dispatches=646
    msize_calls=309 realloc_calls=4 fault=0

The new root remains in the same low-.text band. 5BR keeps the hardware root
mandatory, prioritizes its bounded depth-6 direct closure, then fills the
remaining 256-new-function budget with nearest still-unpacked support-clean
exact generated entries from 0x000A0000..0x0011FFFF.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import subprocess
import sys
import tempfile
from pathlib import Path

NEW_ROOT = 0x000F8BB0
REGION_START = 0x000A0000
REGION_END = 0x00120000
DIRECT_DEPTH = 6
DIRECT_CAP = 256
TOTAL_NEW_CAP = 256
BUILD_TAG = "P5BR-LOWTEXTF8BB0-20261021-A"


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase5BR] could not load module: {path}")
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
                f"[Phase5BR] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Deep-low sweep refuses a mid-function indirect target."
            )
        raise SystemExit(
            f"[Phase5BR] target 0x{root:08X} is absent from the function inventory"
        )

    if root not in generated:
        row = by_va[root]
        raise SystemExit(
            f"[Phase5BR] target 0x{root:08X} is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )


def instrument_new_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase5BR] could not instrument low-.text root")
    return (
        rendered[: brace_pos + 1]
        + "\n    s_phase5brLowTextRootEntered = 1;"
        + rendered[brace_pos + 1 :]
    )


def relabel(main_text: str, env_text: str) -> tuple[str, str]:
    if BUILD_TAG in main_text:
        raise SystemExit("[Phase5BR] output already carries the 5BR build tag")

    if "P5BQ-LOWTEXT10B2B0-20261021-A" not in main_text:
        raise SystemExit("[Phase5BR] inherited 5BQ main build tag changed")
    if "phase5bq_env_build_cookie" not in main_text:
        raise SystemExit("[Phase5BR] inherited 5BQ main cookie marker changed")
    if "phase5bq_env_build_cookie" not in env_text:
        raise SystemExit("[Phase5BR] inherited 5BQ env cookie marker changed")
    if "50354251" not in env_text:
        raise SystemExit("[Phase5BR] inherited 5BQ env cookie value changed")

    main_text = main_text.replace(
        "P5BQ-LOWTEXT10B2B0-20261021-A",
        BUILD_TAG,
    )
    main_text = main_text.replace(
        "phase5bq_env_build_cookie",
        "phase5br_env_build_cookie",
    )
    env_text = env_text.replace(
        "phase5bq_env_build_cookie",
        "phase5br_env_build_cookie",
    )
    main_text = main_text.replace("50354251", "50354252")
    env_text = env_text.replace("50354251", "50354252")
    main_text = main_text.replace("PHASE 5BQ", "PHASE 5BR")
    env_text = env_text.replace("PHASE 5BQ", "PHASE 5BR")
    main_text = main_text.replace("Phase 5BQ", "Phase 5BR")
    env_text = env_text.replace("Phase 5BQ", "Phase 5BR")

    old_policy = (
        "Policy: retain the proven generic broad-sweep dispatcher and maintained "
        "diagnostic support, seed DIRECT_FRONTIER 0023A3CE -> 0010B2B0, revisit "
        "the remaining support-clean low-.text band 000A0000-0011FFFF under a "
        "256-new-function cap, and continue only through exact packed targets "
        "while preserving all genuine subsystem/ABI/kernel hard stops"
    )
    new_policy = (
        "Policy: retain the proven generic broad-sweep dispatcher and maintained "
        "diagnostic support, seed DIRECT_FRONTIER 0023A3CE -> 000F8BB0, revisit "
        "the remaining support-clean low-.text band 000A0000-0011FFFF under a "
        "256-new-function cap, and continue only through exact packed targets "
        "while preserving all genuine subsystem/ABI/kernel hard stops"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase5BR] inherited 5BQ policy marker changed")
    main_text = main_text.replace(old_policy, new_policy, 1)

    if BUILD_TAG not in main_text:
        raise SystemExit("[Phase5BR] main build-tag relabel failed")
    if "phase5br_env_build_cookie" not in main_text:
        raise SystemExit("[Phase5BR] main cookie relabel failed")
    if "phase5br_env_build_cookie" not in env_text:
        raise SystemExit("[Phase5BR] env cookie relabel failed")
    if "50354252" not in env_text:
        raise SystemExit("[Phase5BR] env cookie value relabel failed")

    return main_text, env_text
def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-phase5bq-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bp-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bo-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bn-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bm-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bl-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bk-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bj-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bi-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bh-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bg-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bf-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5be-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bd-emitter", type=Path, required=True)
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

    base = load_module(args.base_emitter, "phase5br_phase4c_base")
    phase5bb = load_module(args.base_phase5bb_emitter, "phase5br_phase5bb_base")
    phase5bc = load_module(args.base_phase5bc_emitter, "phase5br_phase5bc_base")

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="phase5br-base-",
        dir=str(args.out_dir.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        cmd = [
            sys.executable,
            str(args.base_phase5bq_emitter),
            "--base-phase5bp-emitter",
            str(args.base_phase5bp_emitter),
            "--base-phase5bo-emitter",
            str(args.base_phase5bo_emitter),
            "--base-phase5bn-emitter",
            str(args.base_phase5bn_emitter),
            "--base-phase5bm-emitter",
            str(args.base_phase5bm_emitter),
            "--base-phase5bl-emitter",
            str(args.base_phase5bl_emitter),
            "--base-phase5bk-emitter",
            str(args.base_phase5bk_emitter),
            "--base-phase5bj-emitter",
            str(args.base_phase5bj_emitter),
            "--base-phase5bi-emitter",
            str(args.base_phase5bi_emitter),
            "--base-phase5bh-emitter",
            str(args.base_phase5bh_emitter),
            "--base-phase5bg-emitter",
            str(args.base_phase5bg_emitter),
            "--base-phase5bf-emitter",
            str(args.base_phase5bf_emitter),
            "--base-phase5be-emitter",
            str(args.base_phase5be_emitter),
            "--base-phase5bd-emitter",
            str(args.base_phase5bd_emitter),
            "--base-phase5bc-emitter",
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
        base_manifest_path = temp_dir / "phase5bq-manifest.json"
        for required in (base_main, base_env, base_manifest_path):
            if not required.exists():
                raise SystemExit(
                    f"[Phase5BR] Phase 5BQ base emitter did not produce {required.name}"
                )

        main_text = base_main.read_text(encoding="utf-8")
        env_text = base_env.read_text(encoding="utf-8")
        manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact_generated_target(NEW_ROOT, by_va, generated)

    old_members = {int(item, 0) for item in manifest.get("members", [])}
    if NEW_ROOT in old_members:
        raise SystemExit(
            "[Phase5BR] hardware frontier 0x000F8BB0 is already present in the "
            "inherited pack; 5BQ boundary evidence and manifest disagree"
        )

    direct_members = set(
        phase5bb.bounded_promoted_members(
            base,
            NEW_ROOT,
            generated,
            DIRECT_DEPTH,
            DIRECT_CAP,
        )
    )

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
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break

    for va in regional:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if va not in candidate_order:
            candidate_order.append(va)

    if NEW_ROOT not in candidate_order:
        candidate_order.insert(0, NEW_ROOT)

    if len(candidate_order) > TOTAL_NEW_CAP:
        candidate_order = candidate_order[:TOTAL_NEW_CAP]
        if NEW_ROOT not in candidate_order:
            candidate_order[-1] = NEW_ROOT

    candidate_new_members = sorted(set(candidate_order))
    if NEW_ROOT not in candidate_new_members:
        raise SystemExit("[Phase5BR] low-.text candidate set lost 0x000F8BB0")

    expanded_members = set(old_members) | set(candidate_new_members)
    new_members = list(candidate_new_members)

    declaration_marker = "static int s_phase5bqLowTextRootEntered;"
    if declaration_marker not in main_text:
        raise SystemExit("[Phase5BR] Phase 5BQ state marker changed")
    main_text = main_text.replace(
        declaration_marker,
        declaration_marker + "\nstatic int s_phase5brLowTextRootEntered;",
        1,
    )

    reset_marker = "    s_phase5bqLowTextRootEntered = 0;\n"
    if reset_marker not in main_text:
        raise SystemExit("[Phase5BR] Phase 5BQ root reset marker changed")
    main_text = main_text.replace(
        reset_marker,
        reset_marker + "    s_phase5brLowTextRootEntered = 0;\n",
        1,
    )

    gate_marker = "            s_phase5bqLowTextRootEntered &&\n"
    if gate_marker not in main_text:
        raise SystemExit("[Phase5BR] Phase 5BQ PASS gate marker changed")
    main_text = main_text.replace(
        gate_marker,
        gate_marker + "            s_phase5brLowTextRootEntered &&\n",
        1,
    )

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
            "[Phase5BR] support-clean pruning attempted to remove mandatory "
            "hardware-observed root 0x000F8BB0"
        )

    main_text, env_text = relabel(main_text, env_text)

    required_main_markers = (
        BUILD_TAG,
        "case 0x000F8BB0u: return sub_000F8BB0;",
        "s_phase5brLowTextRootEntered = 1;",
        "s_phase5brLowTextRootEntered &&",
        "static void recomp_xact_setup_checkpoint(",
        "static void recomp_teardown_call_checkpoint(",
        "static void recomp_teardown_item_checkpoint(",
        "static void recomp_collision_agent_recycle_range(",
        "PASS: Phase 5BR maintained CRT _msize",
        "PASS: Phase 5BR broad-sweep ICALL_SAFE",
        "PHASE 5BR BROAD TRANSLATED SWEEP RESULT",
    )
    for marker in required_main_markers:
        if marker not in main_text:
            raise SystemExit(
                f"[Phase5BR] generated main lost required low-.text marker: {marker}"
            )

    if "PHASE 5BR RETAIL ENVIRONMENT PREP START" not in env_text:
        raise SystemExit("[Phase5BR] environment phase label patch failed")
    if "phase5br_env_build_cookie" not in env_text or "50354252" not in env_text:
        raise SystemExit("[Phase5BR] environment cookie patch failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "5BR"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = len(expanded_members)
    manifest["members"] = [f"0x{va:08X}" for va in sorted(expanded_members)]
    manifest["phase5br_low_text_sweep"] = {
        "observed_phase": "5BQ",
        "boundary_kind": "DIRECT_FRONTIER",
        "observed_caller": "0x0023A3CE",
        "root": "0x000F8BB0",
        "observed_fault": 0,
        "observed_esp": "0x008BFF3C",
        "observed_saved_esp": "0x008BFF3C",
        "observed_ticks": 67067,
        "observed_trace_count": 6018,
        "observed_icall_dispatches": 868,
        "observed_direct_dispatches": 646,
        "observed_msize_calls": 309,
        "observed_realloc_calls": 4,
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
            mandatory 5BQ direct-frontier root plus its depth-6 direct closure, "
            "then nearest still-unpacked support-clean exact generated entries "
            "across the still-unpacked low-.text band"
        ),
        "pass_policy": (
            all inherited 5BQ invariants must hold and 0x000F8BB0 must "
            "actually enter through generic packed direct dispatch; "
            "continue through further exact packed targets until a newer real "
            "boundary appears"
        ),
    }
    manifest["phase5br_candidate_new_members"] = [
        f"0x{va:08X}" for va in candidate_new_members
    ]
    manifest["phase5br_new_members"] = [
        f"0x{va:08X}" for va in new_members
    ]
    manifest["phase5br_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned_members.items())
    ]
    manifest["phase5br_new_direct_frontier_targets"] = [
        f"0x{va:08X}" for va in sorted(new_direct_frontiers)
    ]

    (args.out_dir / "phase5br-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_new_source = sum(len(rendered_by_va[va]) for va in new_members)
    print(
        "[Phase5BR] FIFTH-PASS LOW-.TEXT SATURATION PACK: "
        f"base={len(old_members)} direct_candidates={len(direct_members - old_members)} "
        f"regional_candidates={len(regional)} candidate_new={len(candidate_new_members)} "
        f"pruned={len(pruned_members)} packed_new={len(new_members)} "
        f"total={len(expanded_members)} new_source_bytes={total_new_source}"
    )
    print(
        "[Phase5BR] AUTO-DISPATCH: inherited generic exact packed ICALL_SAFE "
        "+ exact packed direct continuation"
    )
    print(
        "[Phase5BR] REGION: 0x000A0000-0x0011FFFF, mandatory root 0x000F8BB0"
    )
    print("[Phase5BR] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
