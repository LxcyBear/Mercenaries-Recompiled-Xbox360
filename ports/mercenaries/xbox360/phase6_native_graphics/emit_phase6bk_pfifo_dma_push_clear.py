#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BASE_TAG = "P6BJ-PFB-ZCOMP-BRIDGE-20261024-A"
BUILD_TAG = "P6BK-PFIFO-DMA-PUSH-CLEAR-20261024-A"
COOKIE_OLD = "phase6bj_env_build_cookie"
COOKIE_NEW = "phase6bk_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BK] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BJ build tag")

    old_policy = (
        "Policy: Phase 6BJ shadow documented PFB ZCOMP tile/tag state and "
        "ZCOMP offset only through sub_00292586 scoped dword accesses while "
        "retaining PFB tile and PGRAPH state; all other NV2A/MMIO/VRAM stays fenced"
    )
    new_policy = (
        "Policy: Phase 6BK reuse proven PFIFO DMA_PUSH zero-clear semantics "
        "for the later sub_00292586 setup write while retaining PFB tile/ZCOMP "
        "and PGRAPH state; all other NV2A/MMIO/VRAM stays fenced"
    )
    text = replace_once(text, old_policy, new_policy, "Phase 6BJ runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BJ", "PHASE 6BK")
    text = text.replace("Phase 6BJ", "Phase 6BK")
    text = text.replace('"P6BJ ', '"P6BK ')

    write_old = """    if (s_phase6atPostCreateInitActive &&
        phase6bj_pfb_zcomp_address(address, NULL, NULL))
    {
        phase6bj_pfb_zcomp_write32(address, value);
        return;
    }

    GUEST_WRITE32(address, value);
}"""
    write_new = """    if (s_phase6atPostCreateInitActive &&
        phase6bj_pfb_zcomp_address(address, NULL, NULL))
    {
        phase6bj_pfb_zcomp_write32(address, value);
        return;
    }

    if (s_phase6atPostCreateInitActive &&
        address == 0xFD003220u &&
        value == 0u)
    {
        phase6be_pfifo_idle_write32(address, value);
        return;
    }

    GUEST_WRITE32(address, value);
}"""
    text = replace_once(
        text,
        write_old,
        write_new,
        "Phase 6BJ scoped-write fallback",
    )

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BK] stale Phase 6BJ env cookie remains")
    return text

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BJ", "PHASE 6BK")
    text = text.replace("Phase 6BJ", "Phase 6BK")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BK] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BK] stale Phase 6BJ cookie remains in env")
    return text

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    required = (
        args.base_dir / "main.cpp",
        args.base_dir / "main_monolithic.cpp",
        args.base_dir / "phase5_env.cpp",
        args.base_dir / "phase6bj-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BK] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6bj-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BK] baseline identity mismatch")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    shard_out = args.out_dir / "translated_shards"
    if shard_out.exists():
        shutil.rmtree(shard_out)
    shutil.copytree(args.base_dir / "translated_shards", shard_out)

    wrapper = patch_common(
        (args.base_dir / "main.cpp").read_text(encoding="utf-8")
    )
    mono = patch_common(
        (args.base_dir / "main_monolithic.cpp").read_text(encoding="utf-8")
    )
    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6BK"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bk_pfifo_dma_push_clear"] = {
        "source_phase": "6BJ",
        "hardware_proof": {
            "zcomp_write": {
                "address": "0xFD100304",
                "value": "0x84000000",
            },
            "zcomp_readback": "0x84000000",
            "pgraph_zcomp_mirror": {
                "address": "0xFD400984",
                "write_value": "0x84000000",
                "readback": "0x84000000",
            },
            "next_mmio_access": "WRITE32 0xFD003220",
            "next_mmio_value": "0x00000000",
            "final_va": "0x00292761",
            "ticks": 671011,
        },
        "register_semantics": {
            "register": "NV_PFIFO_CACHE1_DMA_PUSH",
            "address": "0xFD003220",
            "operation": "zero clear",
            "existing_proof": "Phase 6BE already accepted exact zero WRITE32 to FD003220 in the PFIFO idle/quiescence path",
            "implementation": "reuse phase6be_pfifo_idle_write32",
        },
        "scope": (
            "inside sub_00292586's inherited scoped dword wrapper only; "
            "accept exact address 0xFD003220 only when value is zero and "
            "post-create init is active"
        ),
        "pfb_tile_scope_unchanged": True,
        "pfb_zcomp_scope_unchanged": True,
        "pgraph_scope_unchanged": True,
        "all_other_mmio_fenced": True,
        "other_functions_mmio_fenced": True,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6bk-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BK] 6BJ hardware: ZCOMP tile1 write/readback and PGRAPH mirror crossed")
    print("[Phase6BK] next boundary WRITE32 FD003220 value=00000000 at VA 00292761")
    print("[Phase6BK] reuse Phase 6BE proven PFIFO DMA_PUSH zero-clear semantics")
    print("[Phase6BK] scope: sub_00292586 wrapper, exact FD003220, zero value only")
    print("[Phase6BK] PFB tile/ZCOMP and PGRAPH scopes unchanged")
    print("[Phase6BK] all other NV2A/MMIO/VRAM remains fenced")
    print("[Phase6BK] allocator and 8M budget unchanged")
    print("[Phase6BK] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
