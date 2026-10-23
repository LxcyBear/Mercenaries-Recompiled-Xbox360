#!/usr/bin/env python3
"""Phase 6V: deep execution-budget pass over the hardware-proven Phase 6U image.

Phase 6U proved the 32 MiB title-heap expansion on hardware: the previously
fatal 0x012999A0 (~18.6 MiB) RtlAllocateHeap request succeeded at 0x008C2980.
Execution then reached the existing 600,000-tick harness budget with fault=0.

6V changes no translated bodies, no DSOUND packing, no heap geometry, and no
kernel/platform semantics. It reuses the exact Phase-6U source/shards and raises
only PHASE4C_EXEC_BUDGET from 600,000 to 2,000,000 ticks so the long post-
allocation translated initialization can continue to the next real boundary.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BUILD_TAG = "P6V-BUDGET2M-20261023-A"
BASE_TAG = "P6U-TITLE-HEAP32M-20261023-A"
OLD_BUDGET = "#define PHASE4C_EXEC_BUDGET 600000u"
NEW_BUDGET = "#define PHASE4C_EXEC_BUDGET 2000000u"
OLD_BUDGET_TICKS = 600000
NEW_BUDGET_TICKS = 2000000


def replace_exact_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6V] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_main(text: str) -> str:
    text = replace_exact_once(text, OLD_BUDGET, NEW_BUDGET, "execution budget definition")
    text = replace_exact_once(text, BASE_TAG, BUILD_TAG, "Phase 6U build tag")

    text = text.replace("phase6u_env_build_cookie", "phase6v_env_build_cookie")
    text = text.replace("50365555", "50365656")

    # Relabel visible phase text only. Preserve inherited lowercase runtime state
    # symbols from the hardware-proven Phase 6T/6U chain.
    text = (
        text
        .replace("PHASE 6U", "PHASE 6V")
        .replace("Phase 6U", "Phase 6V")
        .replace('"P6U ', '"P6V ')
    )

    text = text.replace(
        "P6V HEAP32M SUMMARY:",
        "P6V BUDGET2M SUMMARY:",
    )
    text = text.replace(
        "PHASE 6V TITLE-HEAP EXPANSION RESULT",
        "PHASE 6V DEEP-BUDGET RESULT",
    )

    old_policy = (
        "Policy: reuse the hardware-proven Phase-6T DSOUND sibling pack unchanged, widen only "
        "the synthetic title heap from 1 MiB to 32 MiB so the observed 0x012999A0 allocation "
        "can fit below the proven 0x03F00000 VM frontier, and retain all existing hard stops"
    )
    new_policy = (
        "Policy: reuse the hardware-proven Phase-6U 32 MiB heap image unchanged, raise only "
        "the translated execution budget from 600000 to 2000000 ticks, and retain every "
        "existing NV2A/platform/ABI/guest-fault/support hard stop"
    )
    text = replace_exact_once(text, old_policy, new_policy, "Phase 6U runtime policy")

    required = (
        BUILD_TAG,
        NEW_BUDGET,
        "phase6v_env_build_cookie",
        "P6V XENOS: PASS Direct3D_CreateDevice",
        "P6V BUDGET2M SUMMARY:",
        "PHASE 6V DEEP-BUDGET RESULT",
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6V] patched main lost marker: {marker}")

    if "phase6u_env_build_cookie" in text:
        raise SystemExit("[Phase6V] stale Phase 6U env cookie remains in main")
    if OLD_BUDGET in text:
        raise SystemExit("[Phase6V] stale 600k execution budget remains in main")

    return text


def patch_env(text: str) -> str:
    text = text.replace("phase6u_env_build_cookie", "phase6v_env_build_cookie")
    text = text.replace("50365555", "50365656")
    text = (
        text
        .replace("PHASE 6U", "PHASE 6V")
        .replace("Phase 6U", "Phase 6V")
    )

    if "phase6v_env_build_cookie" not in text:
        raise SystemExit("[Phase6V] env cookie rewrite did not land")
    if "phase6u_env_build_cookie" in text:
        raise SystemExit("[Phase6V] stale Phase 6U env cookie remains in env")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main.cpp"
    base_monolithic = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6u-manifest.json"
    base_shards = args.base_dir / "translated_shards"

    for path in (base_main, base_monolithic, base_env, base_manifest, base_shards):
        if not path.exists():
            raise SystemExit(f"[Phase6V] cached Phase 6U baseline missing: {path}")

    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6U":
        raise SystemExit("[Phase6V] cached baseline manifest is not Phase 6U")
    if manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6V] cached Phase 6U build tag mismatch")

    heap = manifest.get("phase6u_title_heap_expansion")
    if not isinstance(heap, dict):
        raise SystemExit("[Phase6V] Phase 6U heap-expansion manifest block missing")
    if heap.get("new_heap_end") != "0x028C0000":
        raise SystemExit("[Phase6V] Phase 6U 32 MiB heap identity mismatch")
    if not heap.get("translated_pack_unchanged"):
        raise SystemExit("[Phase6V] Phase 6U translated-pack provenance mismatch")

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

    manifest["phase"] = "6V"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6v_deep_budget"] = {
        "source_phase": "6U",
        "phase6u_hardware_pass": True,
        "phase6u_observed_boundary": {
            "kind": "BUDGET",
            "caller": "0x0023A3CE",
            "target": "0x001F6BF8",
            "fault": 0,
            "ticks": 600001,
            "trace": 165774,
            "direct_dispatches": 1779,
            "last_direct": "0x001F6D80",
            "icall_dispatches": 9073,
            "last_icall": "0x00252E70",
        },
        "phase6u_large_heap_request": {
            "requested_bytes": 19503520,
            "requested_hex": "0x012999A0",
            "result": "0x008C2980",
            "succeeded": True,
        },
        "translated_pack_unchanged": True,
        "heap_geometry_unchanged": True,
        "old_budget_ticks": OLD_BUDGET_TICKS,
        "new_budget_ticks": NEW_BUDGET_TICKS,
        "runtime_policy": (
            "reuse exact Phase-6U source/shards and 32 MiB heap; increase only translated "
            "execution budget; retain all existing hard stops"
        ),
    }

    (args.out_dir / "phase6v-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    shard_count = len(list(out_shards.glob("*.inl")))
    if shard_count < 1:
        raise SystemExit("[Phase6V] translated shard copy is empty")

    print(
        f"[Phase6V] EXECUTION BUDGET: {OLD_BUDGET_TICKS} -> {NEW_BUDGET_TICKS} ticks"
    )
    print("[Phase6V] TITLE HEAP: unchanged 32 MiB window ending at 0x028C0000")
    print(f"[Phase6V] REUSED TRANSLATED SHARDS: {shard_count}")
    print("[Phase6V] TRANSLATED PACK CHANGES: 0")
    print("[Phase6V] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
