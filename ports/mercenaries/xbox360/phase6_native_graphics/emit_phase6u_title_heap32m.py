#!/usr/bin/env python3
"""Phase 6U: widen the synthetic title heap over the hardware-proven Phase 6T pack.

Phase 6T successfully broke out of the 0xB-byte DSOUND sibling crawl and then
stopped at PHASE4C_BOUNDARY_HEAP_EXHAUSTED with target/requested size
0x012999A0 (~18.6 MiB), fault=0.

The inherited Phase-4C title heap is only 1 MiB:
    base  0x008C0000
    start 0x008C1000
    end   base + 0x00100000

Hardware also proved the only VM reservation before this stop is the 1 MiB
top-down reservation at 0x03F00000, so a 32 MiB title-heap window ending at
0x028C0000 remains well below that VM frontier.

6U makes no translated-function or DSOUND packing changes. It copies the exact
Phase-6T source/shards, widens only PHASE4C_TITLE_HEAP_END to base + 32 MiB,
advances the build identity/cookie, and keeps all existing hard-stop behavior.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BUILD_TAG = "P6U-TITLE-HEAP32M-20261023-A"
BASE_TAG = "P6T-DSOUND-SIBLING-SWEEP-002A0164-20261022-A"
OLD_HEAP = "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x00100000u)"
NEW_HEAP = "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)"
HEAP_BASE = 0x008C0000
HEAP_START = 0x008C1000
HEAP_END = 0x028C0000
PROVEN_VM_FRONTIER = 0x03F00000
REQUESTED_AT_6T = 0x012999A0


def replace_exact_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6U] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_main(text: str) -> str:
    text = replace_exact_once(text, OLD_HEAP, NEW_HEAP, "title heap definition")

    text = replace_exact_once(
        text,
        BASE_TAG,
        BUILD_TAG,
        "Phase 6T build tag",
    )

    text = text.replace(
        "phase6t_env_build_cookie",
        "phase6u_env_build_cookie",
    )
    text = text.replace("50365454", "50365555")

    # Visible phase labels only. Do not rename lowercase state symbols such as
    # s_phase6tRootEntered; the exact Phase-6T runtime proof remains inherited.
    text = (
        text
        .replace("PHASE 6T", "PHASE 6U")
        .replace("Phase 6T", "Phase 6U")
        .replace('"P6T ', '"P6U ')
    )

    text = text.replace(
        "P6U DSOUND SIBLING SUMMARY:",
        "P6U HEAP32M SUMMARY:",
    )
    text = text.replace(
        "PHASE 6U DSOUND SIBLING SWEEP RESULT",
        "PHASE 6U TITLE-HEAP EXPANSION RESULT",
    )

    old_policy = (
        "Policy: start from hardware-proven Phase-6S DSOUND frontier pass, sweep exact generated "
        "DSOUND sibling entrypoints from 002A0164 forward with a 1024-member candidate cap, "
        "support-clean prune every unresolved helper, retain proven cos()/sin() CRT support, "
        "and hard-stop on interior-entry, missing-body, NV2A/platform/ABI/guest-fault boundaries"
    )
    new_policy = (
        "Policy: reuse the hardware-proven Phase-6T DSOUND sibling pack unchanged, widen only "
        "the synthetic title heap from 1 MiB to 32 MiB so the observed 0x012999A0 allocation "
        "can fit below the proven 0x03F00000 VM frontier, and retain all existing hard stops"
    )
    if old_policy in text:
        text = text.replace(old_policy, new_policy, 1)

    required = (
        BUILD_TAG,
        NEW_HEAP,
        "phase6u_env_build_cookie",
        "P6U XENOS: PASS Direct3D_CreateDevice",
        "P6U HEAP32M SUMMARY:",
        "PHASE 6U TITLE-HEAP EXPANSION RESULT",
        "s_phase6tRootEntered",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6U] patched main lost marker: {marker}")

    if "phase6t_env_build_cookie" in text:
        raise SystemExit("[Phase6U] stale Phase 6T env cookie remains in main")

    return text


def patch_env(text: str) -> str:
    text = text.replace(
        "phase6t_env_build_cookie",
        "phase6u_env_build_cookie",
    )
    text = text.replace("50365454", "50365555")
    text = (
        text
        .replace("PHASE 6T", "PHASE 6U")
        .replace("Phase 6T", "Phase 6U")
    )

    if "phase6u_env_build_cookie" not in text:
        raise SystemExit("[Phase6U] env cookie rewrite did not land")
    if "phase6t_env_build_cookie" in text:
        raise SystemExit("[Phase6U] stale Phase 6T env cookie remains in env")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main.cpp"
    base_monolithic = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6t-manifest.json"
    base_shards = args.base_dir / "translated_shards"

    for path in (
        base_main,
        base_monolithic,
        base_env,
        base_manifest,
        base_shards,
    ):
        if not path.exists():
            raise SystemExit(f"[Phase6U] cached Phase 6T baseline missing: {path}")

    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6T":
        raise SystemExit("[Phase6U] cached baseline manifest is not Phase 6T")
    if manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6U] cached Phase 6T build tag mismatch")

    if HEAP_END >= PROVEN_VM_FRONTIER:
        raise SystemExit("[Phase6U] configured heap end overlaps proven VM frontier")
    if HEAP_START + REQUESTED_AT_6T > HEAP_END:
        raise SystemExit("[Phase6U] 32 MiB heap still cannot fit observed 6T allocation")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_shards = args.out_dir / "translated_shards"
    if out_shards.exists():
        shutil.rmtree(out_shards)
    shutil.copytree(base_shards, out_shards)

    main_text = patch_main(base_main.read_text(encoding="utf-8"))
    mono_text = patch_main(base_monolithic.read_text(encoding="utf-8"))
    env_text = patch_env(base_env.read_text(encoding="utf-8"))

    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    inherited = manifest.get("phase6t_dsound_sibling_sweep")
    if not isinstance(inherited, dict):
        raise SystemExit("[Phase6U] Phase 6T sibling-sweep manifest block missing")

    manifest["phase"] = "6U"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6u_title_heap_expansion"] = {
        "source_phase": "6T",
        "phase6t_hardware_pass": True,
        "phase6t_observed_boundary": {
            "kind": "HEAP_EXHAUSTED",
            "caller": "0x0023A3CE",
            "requested_bytes": REQUESTED_AT_6T,
            "requested_hex": "0x012999A0",
            "fault": 0,
            "ticks": 431056,
            "trace": 131985,
            "direct_dispatches": 1769,
            "icall_dispatches": 9073,
        },
        "translated_pack_unchanged": True,
        "dsound_sibling_sweep_inherited": True,
        "old_heap_base": "0x008C0000",
        "old_heap_end": "0x009C0000",
        "old_heap_window_bytes": 0x00100000,
        "new_heap_base": f"0x{HEAP_BASE:08X}",
        "new_heap_start": f"0x{HEAP_START:08X}",
        "new_heap_end": f"0x{HEAP_END:08X}",
        "new_heap_window_bytes": 0x02000000,
        "proven_vm_frontier": f"0x{PROVEN_VM_FRONTIER:08X}",
        "vm_gap_bytes": PROVEN_VM_FRONTIER - HEAP_END,
        "observed_request_fits": HEAP_START + REQUESTED_AT_6T <= HEAP_END,
        "runtime_policy": (
            "reuse exact Phase-6T translated/sharded pack; widen only ordinary title heap "
            "window; retain all existing NV2A/platform/ABI/guest-fault/budget/support hard stops"
        ),
    }

    (args.out_dir / "phase6u-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    shard_count = len(list(out_shards.glob("*.inl")))
    if shard_count < 1:
        raise SystemExit("[Phase6U] translated shard copy is empty")

    print(
        "[Phase6U] HEAP WINDOW: "
        f"old=0x009C0000 new=0x{HEAP_END:08X} "
        f"request=0x{REQUESTED_AT_6T:08X} "
        f"vm_frontier=0x{PROVEN_VM_FRONTIER:08X}"
    )
    print(
        f"[Phase6U] REUSED PACK: members={manifest.get('pack_members')} "
        f"shards={shard_count}"
    )
    print("[Phase6U] TRANSLATED PACK CHANGES: 0")
    print("[Phase6U] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
