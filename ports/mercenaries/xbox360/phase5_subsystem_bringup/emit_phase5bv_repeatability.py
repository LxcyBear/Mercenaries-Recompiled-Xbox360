#!/usr/bin/env python3
"""Phase 5BV: frozen-pack repeatability gate.

5BU hardware consumed 0x001462E0 and then advanced only a collapsed delta
before stopping fault-free at:
    DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30
    esp=0x008BFF3C saved_esp=0x008BFF3C
    ticks=73417 trace=7322
    icall_dispatches=1262 direct_dispatches=1002
    msize_calls=395 realloc_calls=4 fault=0

5BV intentionally adds no translated members. It freezes the exact 5BU pack,
relabels the harness as a repeatability build, and records the expected stable
endpoint so repeated real-hardware boots can prove deterministic runtime,
persistence, heap, ABI, and boundary behavior before the mandatory Phase-5
exit reconnaissance gate.
"""

from __future__ import annotations

import argparse
import json
import subprocess
import sys
import tempfile
from pathlib import Path

BUILD_TAG = "P5BV-REPEATABILITY-20261021-A"
EXPECTED_CALLER = "0x0023A3CE"
EXPECTED_TARGET = "0x0014CD30"
EXPECTED_ESP = "0x008BFF3C"
EXPECTED_TICKS = 73417
EXPECTED_TRACE = 7322
EXPECTED_ICALL = 1262
EXPECTED_DIRECT = 1002
EXPECTED_MSIZE = 395
EXPECTED_REALLOC = 4
REQUIRED_CONSECUTIVE_RUNS = 3


def relabel(main_text: str, env_text: str) -> tuple[str, str]:
    if BUILD_TAG in main_text:
        raise SystemExit("[Phase5BV] output already carries the 5BV build tag")

    old_tag = "P5BU-MIDTEXT1462E0-20261021-A"
    if old_tag not in main_text:
        raise SystemExit("[Phase5BV] inherited 5BU build tag changed")
    if "phase5bu_env_build_cookie" not in main_text:
        raise SystemExit("[Phase5BV] inherited 5BU main cookie marker changed")
    if "phase5bu_env_build_cookie" not in env_text:
        raise SystemExit("[Phase5BV] inherited 5BU env cookie marker changed")
    if "50354255" not in env_text:
        raise SystemExit("[Phase5BV] inherited 5BU env cookie value changed")

    main_text = main_text.replace(old_tag, BUILD_TAG)
    main_text = main_text.replace(
        "phase5bu_env_build_cookie",
        "phase5bv_env_build_cookie",
    )
    env_text = env_text.replace(
        "phase5bu_env_build_cookie",
        "phase5bv_env_build_cookie",
    )
    main_text = main_text.replace("50354255", "50354256")
    env_text = env_text.replace("50354255", "50354256")

    main_text = main_text.replace("PHASE 5BU", "PHASE 5BV")
    env_text = env_text.replace("PHASE 5BU", "PHASE 5BV")
    main_text = main_text.replace("Phase 5BU", "Phase 5BV")
    env_text = env_text.replace("Phase 5BU", "Phase 5BV")

    old_policy = (
        "Policy: retain the proven generic broad-sweep dispatcher and maintained "
        "diagnostic support, seed DIRECT_FRONTIER 0023A3CE -> 001462E0, revisit "
        "the remaining support-clean mid-.text band 00120000-00235FFF under a "
        "256-new-function cap, and continue only through exact packed targets "
        "while preserving all genuine subsystem/ABI/kernel hard stops"
    )
    new_policy = (
        "Policy: freeze the exact Phase 5BU translated pack with zero new members; "
        "repeat the same retail boot path unchanged and require the fault-free "
        "stable endpoint candidate DIRECT_FRONTIER 0023A3CE -> 0014CD30 with "
        "identical translated dispatch/heap/trace invariants before Phase-5 exit "
        "reconnaissance; preserve all genuine subsystem/ABI/kernel hard stops"
    )
    if old_policy not in main_text:
        raise SystemExit("[Phase5BV] inherited 5BU policy marker changed")
    main_text = main_text.replace(old_policy, new_policy, 1)

    main_text = main_text.replace(
        "PHASE 5BV BROAD TRANSLATED SWEEP RESULT",
        "PHASE 5BV REPEATABILITY RESULT",
    )

    return main_text, env_text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-phase5bu-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bt-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5bs-emitter", type=Path, required=True)
    ap.add_argument("--base-phase5br-emitter", type=Path, required=True)
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

    args.out_dir.parent.mkdir(parents=True, exist_ok=True)

    with tempfile.TemporaryDirectory(
        prefix="phase5bv-base-",
        dir=str(args.out_dir.parent),
    ) as temp_name:
        temp_dir = Path(temp_name)
        cmd = [
            sys.executable,
            str(args.base_phase5bu_emitter),
            "--base-phase5bt-emitter", str(args.base_phase5bt_emitter),
            "--base-phase5bs-emitter", str(args.base_phase5bs_emitter),
            "--base-phase5br-emitter", str(args.base_phase5br_emitter),
            "--base-phase5bq-emitter", str(args.base_phase5bq_emitter),
            "--base-phase5bp-emitter", str(args.base_phase5bp_emitter),
            "--base-phase5bo-emitter", str(args.base_phase5bo_emitter),
            "--base-phase5bn-emitter", str(args.base_phase5bn_emitter),
            "--base-phase5bm-emitter", str(args.base_phase5bm_emitter),
            "--base-phase5bl-emitter", str(args.base_phase5bl_emitter),
            "--base-phase5bk-emitter", str(args.base_phase5bk_emitter),
            "--base-phase5bj-emitter", str(args.base_phase5bj_emitter),
            "--base-phase5bi-emitter", str(args.base_phase5bi_emitter),
            "--base-phase5bh-emitter", str(args.base_phase5bh_emitter),
            "--base-phase5bg-emitter", str(args.base_phase5bg_emitter),
            "--base-phase5bf-emitter", str(args.base_phase5bf_emitter),
            "--base-phase5be-emitter", str(args.base_phase5be_emitter),
            "--base-phase5bd-emitter", str(args.base_phase5bd_emitter),
            "--base-phase5bc-emitter", str(args.base_phase5bc_emitter),
            "--base-phase5bb-emitter", str(args.base_phase5bb_emitter),
            "--base-emitter", str(args.base_emitter),
            "--generated-root", str(args.generated_root),
            "--functions", str(args.functions),
            "--entry-report", str(args.entry_report),
            "--thread-report", str(args.thread_report),
            "--phase3n-template", str(args.phase3n_template),
            "--phase2e-source", str(args.phase2e_source),
            "--out-dir", str(temp_dir),
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
        base_manifest_path = temp_dir / "phase5bu-manifest.json"
        for required in (base_main, base_env, base_manifest_path):
            if not required.exists():
                raise SystemExit(
                    f"[Phase5BV] Phase 5BU base emitter did not produce {required.name}"
                )

        main_text = base_main.read_text(encoding="utf-8")
        env_text = base_env.read_text(encoding="utf-8")
        manifest = json.loads(base_manifest_path.read_text(encoding="utf-8"))

    base_members = list(manifest.get("members", []))
    base_pack_members = int(manifest.get("pack_members", len(base_members)))

    main_text, env_text = relabel(main_text, env_text)

    required_main_markers = (
        BUILD_TAG,
        "case 0x001462E0u: return sub_001462E0;",
        "s_phase5buMidTextRootEntered = 1;",
        "s_phase5buMidTextRootEntered &&",
        "PASS: Phase 5BV maintained CRT _msize",
        "PASS: Phase 5BV broad-sweep ICALL_SAFE",
        "PHASE 5BV REPEATABILITY RESULT",
        "PASS: Phase 5BV maintained RtlAllocateHeap",
        "PASS: Phase 5BV Partition0 backing LOADED",
        "freeze the exact Phase 5BU translated pack with zero new members",
    )
    for marker in required_main_markers:
        if marker not in main_text:
            raise SystemExit(
                f"[Phase5BV] generated main lost required repeatability marker: {marker}"
            )

    required_env_markers = (
        "PHASE 5BV RETAIL ENVIRONMENT PREP START",
        "PHASE 5BV EXACT RETAIL VERIFICATION: PASS",
        "PHASE 5BV EXECUTION ENVIRONMENT RESULT: PASS",
        "phase5bv_env_build_cookie",
        "50354256",
        "PHASE 5BV RETAIL ENVIRONMENT PREP END",
    )
    for marker in required_env_markers:
        if marker not in env_text:
            raise SystemExit(
                f"[Phase5BV] generated environment lost marker: {marker}"
            )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "5BV"
    manifest["build_tag"] = BUILD_TAG
    manifest["pack_members"] = base_pack_members
    manifest["members"] = base_members
    manifest["phase5bv_repeatability_gate"] = {
        "source_phase": "5BU",
        "frozen_pack": True,
        "new_members": 0,
        "required_consecutive_hardware_runs": REQUIRED_CONSECUTIVE_RUNS,
        "expected_boundary_kind": "DIRECT_FRONTIER",
        "expected_caller": EXPECTED_CALLER,
        "expected_target": EXPECTED_TARGET,
        "expected_esp": EXPECTED_ESP,
        "expected_saved_esp": EXPECTED_ESP,
        "expected_fault": 0,
        "expected_ticks": EXPECTED_TICKS,
        "expected_trace_count": EXPECTED_TRACE,
        "expected_icall_dispatches": EXPECTED_ICALL,
        "expected_direct_dispatches": EXPECTED_DIRECT,
        "expected_msize_calls": EXPECTED_MSIZE,
        "expected_realloc_calls": EXPECTED_REALLOC,
        "expected_final_msize": 2048,
        "persistence_policy": (
            "preserve game:\\merc360-partition0\\partition0-config.bin across "
            "all repeatability runs; do not reset backing state between launches"
        ),
        "pass_policy": (
            "three consecutive boots of the same XEX must reproduce the same "
            "fault-free boundary and exact translated dispatch/heap/trace "
            "invariants, each with environment PASS, guest-arena release, "
            "proof-end, and XAPI return 0"
        ),
    }

    (args.out_dir / "phase5bv-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(
        "[Phase5BV] FROZEN REPEATABILITY PACK: "
        f"members={base_pack_members} new_members=0 source_phase=5BU"
    )
    print(
        "[Phase5BV] EXPECTED ENDPOINT: "
        "DIRECT_FRONTIER 0023A3CE -> 0014CD30, fault=0, "
        "ticks=73417 trace=7322 icall=1262 direct=1002 msize=395 realloc=4"
    )
    print(
        "[Phase5BV] HARDWARE GATE: run the exact same XEX three consecutive "
        "times without deleting Partition0 backing; capture the complete xbWatson "
        "log for every run"
    )
    print("[Phase5BV] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
