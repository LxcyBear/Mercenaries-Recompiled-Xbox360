#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BASE_TAG = "P6BH-PGRAPH-STATE-BRIDGE-20261024-A"
BUILD_TAG = "P6BI-PFB-TILE-BASE-BRIDGE-20261024-A"
COOKIE_OLD = "phase6bh_env_build_cookie"
COOKIE_NEW = "phase6bi_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BI] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BH build tag")

    old_policy = (
        "Policy: Phase 6BH shadow PGRAPH dword register state only inside "
        "sub_00292586; all other NV2A/MMIO/VRAM stays fenced"
    )
    new_policy = (
        "Policy: Phase 6BI complete documented PFB tile base/limit/pitch "
        "shadowing inside sub_00292586 while retaining scoped PGRAPH state; "
        "all other NV2A/MMIO/VRAM stays fenced"
    )
    text = replace_once(text, old_policy, new_policy, "Phase 6BH runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BH", "PHASE 6BI")
    text = text.replace("Phase 6BH", "Phase 6BI")
    text = text.replace('"P6BH ', '"P6BI ')

    write_tail_old = """    GUEST_WRITE32(address, value);
}

static uint32_t phase6bh_pgraph_scoped_read32"""
    write_tail_new = """    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, NULL))
    {
        phase6bg_pfb_tile_write32(address, value);
        return;
    }

    GUEST_WRITE32(address, value);
}

static uint32_t phase6bh_pgraph_scoped_read32"""
    text = replace_once(
        text,
        write_tail_old,
        write_tail_new,
        "Phase 6BH scoped-write fallback",
    )

    read_tail_old = """    return GUEST_READ32(address);
}

static void phase4c_budget_tick"""
    read_tail_new = """    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, NULL))
    {
        return phase6bg_pfb_tile_read32(address);
    }

    return GUEST_READ32(address);
}

static void phase4c_budget_tick"""
    text = replace_once(
        text,
        read_tail_old,
        read_tail_new,
        "Phase 6BH scoped-read fallback",
    )

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BI] stale Phase 6BH env cookie remains")
    return text

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BH", "PHASE 6BI")
    text = text.replace("Phase 6BH", "Phase 6BI")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BI] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BI] stale Phase 6BH cookie remains in env")
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
        args.base_dir / "phase6bh-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BI] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6bh-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BH" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BI] baseline identity mismatch")

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

    manifest["phase"] = "6BI"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bi_pfb_tile_base_bridge"] = {
        "source_phase": "6BH",
        "hardware_proof": {
            "pgraph_writes_crossed": [
                {"address": "0xFD400914", "value": "0x02627FFF"},
                {"address": "0xFD400918", "value": "0x00000A00"},
                {"address": "0xFD400910", "value": "0x024FC003"},
            ],
            "next_mmio_access": "WRITE32 0xFD100250",
            "next_mmio_value": "0x024FC003",
            "final_va_tail": ["0x00292618", "0x00292645", "0x0029264D"],
            "ticks": 670999,
        },
        "register_semantics": {
            "block": "PFB",
            "tile": 1,
            "base_address": "0xFD100250",
            "base_value": "0x024FC003",
            "limit_address": "0xFD100254",
            "limit_value": "0x02627FFF",
            "pitch_address": "0xFD100258",
            "pitch_value": "0x00000A00",
            "note": "existing Phase 6BG helper already models documented PFB tile BASE/LIMIT/PITCH shadow state",
        },
        "scope": (
            "reuse the Phase 6BG PFB tile classifier as the fallback of the "
            "Phase 6BH sub_00292586 dword wrapper, so dynamic tile BASE "
            "write/readback is handled without widening any global MMIO fence"
        ),
        "pgraph_scope_unchanged": True,
        "other_functions_mmio_fenced": True,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6bi-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BI] 6BH hardware: PGRAPH 0914/0918/0910 writes crossed")
    print("[Phase6BI] next boundary WRITE32 FD100250 = PFB tile1 BASE")
    print("[Phase6BI] observed BASE value 024FC003 matches framebuffer allocation base 024FC000 plus tile flags 00000003")
    print("[Phase6BI] reuse documented PFB tile BASE/LIMIT/PITCH shadow helper inside sub_00292586")
    print("[Phase6BI] scoped PGRAPH state bridge remains unchanged")
    print("[Phase6BI] all other functions and unrelated NV2A/MMIO/VRAM remain fenced")
    print("[Phase6BI] allocator and 8M budget unchanged")
    print("[Phase6BI] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
