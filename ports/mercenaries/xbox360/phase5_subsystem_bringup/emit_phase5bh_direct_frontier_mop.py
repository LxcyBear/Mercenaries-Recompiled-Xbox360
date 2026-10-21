#!/usr/bin/env python3
"""Phase 5BH: mop up accumulated exact translated DIRECT_FRONTIER fences.

5BG hardware proved five automatic packed ICALL_SAFE promotions in one launch,
including 0x002471C0, then stopped fault-free at a direct translated boundary:
0x0023776D -> 0x0023BE3C.

Rather than promote only that one address, 5BH harvests every currently fenced
direct target from the inherited generated main.cpp, keeps 0x0023BE3C
mandatory, adds bounded closures for exact generated fence targets, and packs
the largest support-clean subset within a 256-new-function cap.
"""

from __future__ import annotations

import argparse
import importlib.util
import json
import re
import subprocess
import sys
import tempfile
from pathlib import Path

NEW_ROOT = 0x0023BE3C
ROOT_DIRECT_DEPTH = 6
ROOT_DIRECT_CAP = 256
FENCE_DIRECT_DEPTH = 3
FENCE_DIRECT_CAP = 48
TOTAL_NEW_CAP = 256
BUILD_TAG = "P5BH-DIRECTMOP23BE3C-20261021-A"

DIRECT_FENCE_RE = re.compile(
    r"phase4c_direct_frontier\(\s*0x([0-9A-Fa-f]{8})u\s*\)"
)


def load_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase5BH] could not load module: {path}")
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
                f"[Phase5BH] target 0x{root:08X} is not an exact function start; "
                f"containing function is 0x{int(row['start']):08X}-"
                f"0x{int(row['end']):08X} {row['name']}. "
                "Direct-frontier mop refuses a mid-function target."
            )
        raise SystemExit(
            f"[Phase5BH] target 0x{root:08X} is absent from the function inventory"
        )

    if root not in generated:
        row = by_va[root]
        raise SystemExit(
            f"[Phase5BH] target 0x{root:08X} is an exact function start "
            f"({row['name']}) but has no generated translated body"
        )


def instrument_new_root(rendered: str, name: str) -> str:
    name_pos = rendered.find(name)
    brace_pos = rendered.find("{", name_pos)
    if name_pos < 0 or brace_pos < 0:
        raise SystemExit("[Phase5BH] could not instrument direct-frontier root")
    return (
        rendered[: brace_pos + 1]
        + "\n    s_phase5bhDirectRootEntered = 1;"
        + rendered[brace_pos + 1 :]
    )


def append_members(
    order: list[int],
    members: list[int] | set[int],
    old_members: set[int],
    cap: int,
) -> None:
    for va in members:
        if len(order) >= cap:
            return
        if va in old_members or va in order:
            continue
        order.append(va)


def relabel(main_text: str, env_text: str) -> tuple[str, str]:
    main_text = main_text.replace(
        "P5BG-TEXTTAIL2471C0-20261020-A",
        BUILD_TAG,
    )
    env_text = env_text.replace(
        "P5BG-TEXTTAIL2471C0-20261020-A",
        BUILD_TAG,
    )
    main_text = main_text.replace(
        "phase5bg_env_build_cookie",
        "phase5bh_env_build_cookie",
    )
    env_text = env_text.replace(
        "phase5bg_env_build_cookie",
        "phase5bh_env_build_cookie",
    )
    main_text = main_text.replace("50354247", "50354248")
    env_text = env_text.replace("50354247", "50354248")
    main_text = main_text.replace("PHASE 5BG", "PHASE 5BH")
    env_text = env_text.replace("PHASE 5BG", "PHASE 5BH")
    main_text = main_text.replace("Phase 5BG", "Phase 5BH")
    env_text = env_text.replace("Phase 5BG", "Phase 5BH")

    old_policy = (
        "Policy: retain the proven generic broad-sweep dispatcher, seed "
        "ICALL_SAFE 0022B3F1 -> 002471C0, pre-pack support-clean exact "
        "generated entries across the remaining title .text tail "
        "00246000-0025561F capped at 256 new functions, and continue only "
        "through exact targets already present in the widened pack"
    )
    new_policy = (
        "Policy: retain the proven generic broad-sweep dispatcher, seed "
        "DIRECT 0023776D -> 0023BE3C, harvest exact generated targets from "
        "all inherited direct-frontier fences, add bounded translated closures "
        "within a 256-new-function cap, and keep unsupported branches fenced"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase5BH] inherited 5BG policy marker changed")
    main_text = main_text.replace(old_policy, new_policy, 1)

    return main_text, env_text


def main() -> int:
    ap = argparse.ArgumentParser()
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

    base = load_module(args.base_emitter, "phase5bh_phase4c_base")
    phase5bb = load_module(args.base_phase5bb_emitter, "phase5bh_phase5bb_base")
    phase5bc = load_module(args.base_phase5bc_emitter, "phase5bh_phase5bc_base")

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="phase5bh-base-",
        dir=str(args.out_dir.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        cmd = [
            sys.executable,
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
        base_manifest_path = temp_dir / "phase5bg-manifest.json"
        for required in (base_main, base_env, base_manifest_path):
            if not required.exists():
                raise SystemExit(
                    f"[Phase5BH] Phase 5BG base emitter did not produce {required.name}"
                )

        main_text = base_main.read_text(encoding="utf-8")
        env_text = base_env.read_text(encoding="utf-8")
        manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    validate_exact_generated_target(NEW_ROOT, by_va, generated)

    old_members = {int(item, 0) for item in manifest.get("members", [])}

    observed_fences: list[int] = []
    seen_fences: set[int] = set()
    for match in DIRECT_FENCE_RE.finditer(main_text):
        va = int(match.group(1), 16)
        if va in seen_fences:
            continue
        seen_fences.add(va)
        observed_fences.append(va)

    exact_generated_fences = [
        va
        for va in observed_fences
        if va in generated and va not in old_members
    ]
    if NEW_ROOT not in exact_generated_fences:
        # The mandatory runtime target must still be represented even if a
        # prior source-format change prevents the fence regex from seeing it.
        exact_generated_fences.insert(0, NEW_ROOT)

    root_members = list(
        phase5bb.bounded_promoted_members(
            base,
            NEW_ROOT,
            generated,
            ROOT_DIRECT_DEPTH,
            ROOT_DIRECT_CAP,
        )
    )

    candidate_order: list[int] = []
    append_members(
        candidate_order,
        [NEW_ROOT] + sorted(va for va in root_members if va != NEW_ROOT),
        old_members,
        TOTAL_NEW_CAP,
    )

    selected_fence_roots: list[int] = []
    for fence_va in exact_generated_fences:
        if len(candidate_order) >= TOTAL_NEW_CAP:
            break
        if fence_va == NEW_ROOT:
            if fence_va not in selected_fence_roots:
                selected_fence_roots.append(fence_va)
            continue

        selected_fence_roots.append(fence_va)
        closure = list(
            phase5bb.bounded_promoted_members(
                base,
                fence_va,
                generated,
                FENCE_DIRECT_DEPTH,
                FENCE_DIRECT_CAP,
            )
        )
        prioritized = [fence_va] + sorted(va for va in closure if va != fence_va)
        append_members(
            candidate_order,
            prioritized,
            old_members,
            TOTAL_NEW_CAP,
        )

    if NEW_ROOT not in candidate_order:
        raise SystemExit("[Phase5BH] candidate set lost mandatory root 0x0023BE3C")

    candidate_new_members = sorted(set(candidate_order))
    expanded_members = set(old_members) | set(candidate_new_members)
    new_members = list(candidate_new_members)

    declaration_marker = "static int s_phase5bgTailRootEntered;"
    if declaration_marker not in main_text:
        raise SystemExit("[Phase5BH] Phase 5BG sweep state marker changed")
    main_text = main_text.replace(
        declaration_marker,
        declaration_marker + "\nstatic int s_phase5bhDirectRootEntered;",
        1,
    )

    reset_marker = "    s_phase5bgTailRootEntered = 0;\n"
    if reset_marker not in main_text:
        raise SystemExit("[Phase5BH] Phase 5BG root reset marker changed")
    main_text = main_text.replace(
        reset_marker,
        reset_marker + "    s_phase5bhDirectRootEntered = 0;\n",
        1,
    )

    gate_marker = "            s_phase5bgTailRootEntered &&\n"
    if gate_marker not in main_text:
        raise SystemExit("[Phase5BH] Phase 5BG PASS gate marker changed")
    main_text = main_text.replace(
        gate_marker,
        gate_marker + "            s_phase5bhDirectRootEntered &&\n",
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
            "[Phase5BH] support-clean pruning attempted to remove mandatory "
            "hardware-observed root 0x0023BE3C"
        )

    main_text, env_text = relabel(main_text, env_text)

    required_main_markers = (
        BUILD_TAG,
        "case 0x0023BE3Cu: return sub_0023BE3C;",
        "s_phase5bhDirectRootEntered = 1;",
        "s_phase5bhDirectRootEntered &&",
        "PASS: Phase 5BH broad-sweep ICALL_SAFE",
        "PHASE 5BH BROAD TRANSLATED SWEEP RESULT",
    )
    for marker in required_main_markers:
        if marker not in main_text:
            raise SystemExit(
                f"[Phase5BH] generated main lost required direct-mop marker: {marker}"
            )

    if "PHASE 5BH RETAIL ENVIRONMENT PREP START" not in env_text:
        raise SystemExit("[Phase5BH] environment phase label patch failed")
    if "phase5bh_env_build_cookie" not in env_text or "50354248" not in env_text:
        raise SystemExit("[Phase5BH] environment cookie patch failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "5BH"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = len(expanded_members)
    manifest["members"] = [f"0x{va:08X}" for va in sorted(expanded_members)]
    manifest["phase5bh_direct_frontier_mop"] = {
        "observed_phase": "5BG",
        "boundary_kind": "DIRECT_FRONTIER",
        "observed_caller": "0x0023776D",
        "root": "0x0023BE3C",
        "observed_fault": 0,
        "observed_esp": "0x008BFF24",
        "observed_saved_esp": "0x008BFF24",
        "root_direct_closure_depth": ROOT_DIRECT_DEPTH,
        "root_direct_closure_cap": ROOT_DIRECT_CAP,
        "fence_direct_closure_depth": FENCE_DIRECT_DEPTH,
        "fence_direct_closure_cap": FENCE_DIRECT_CAP,
        "total_new_cap": TOTAL_NEW_CAP,
        "base_pack_members": len(old_members),
        "observed_direct_fence_targets": len(observed_fences),
        "exact_generated_unpacked_fences": len(exact_generated_fences),
        "selected_fence_roots": len(selected_fence_roots),
        "candidate_new_members": len(candidate_new_members),
        "new_members": len(new_members),
        "pruned_members": len(pruned_members),
        "expanded_pack_members": len(expanded_members),
        "strategy": (
            "mandatory 5BG direct frontier plus bounded closures rooted at "
            "accumulated exact generated direct-frontier fences; unsupported "
            "branches remain fenced"
        ),
        "pass_policy": (
            "all inherited 5BG invariants must hold and 0x0023BE3C must "
            "actually enter through the generic packed direct dispatcher; "
            "continue until a newer real boundary appears"
        ),
    }
    manifest["phase5bh_observed_direct_fences"] = [
        f"0x{va:08X}" for va in observed_fences
    ]
    manifest["phase5bh_exact_generated_unpacked_fences"] = [
        f"0x{va:08X}" for va in exact_generated_fences
    ]
    manifest["phase5bh_selected_fence_roots"] = [
        f"0x{va:08X}" for va in selected_fence_roots
    ]
    manifest["phase5bh_candidate_new_members"] = [
        f"0x{va:08X}" for va in candidate_new_members
    ]
    manifest["phase5bh_new_members"] = [
        f"0x{va:08X}" for va in new_members
    ]
    manifest["phase5bh_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned_members.items())
    ]
    manifest["phase5bh_new_direct_frontier_targets"] = [
        f"0x{va:08X}" for va in sorted(new_direct_frontiers)
    ]

    (args.out_dir / "phase5bh-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    total_new_source = sum(len(rendered_by_va[va]) for va in new_members)
    print(
        "[Phase5BH] DIRECT FRONTIER MOP PACK: "
        f"base={len(old_members)} observed_fences={len(observed_fences)} "
        f"exact_unpacked={len(exact_generated_fences)} "
        f"selected_roots={len(selected_fence_roots)} "
        f"candidate_new={len(candidate_new_members)} "
        f"pruned={len(pruned_members)} packed_new={len(new_members)} "
        f"total={len(expanded_members)} new_source_bytes={total_new_source}"
    )
    print(
        "[Phase5BH] AUTO-DISPATCH: inherited exact packed ICALL_SAFE + "
        "exact packed direct continuation"
    )
    print(
        "[Phase5BH] MANDATORY ROOT: DIRECT 0x0023776D -> 0x0023BE3C"
    )
    print("[Phase5BH] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
