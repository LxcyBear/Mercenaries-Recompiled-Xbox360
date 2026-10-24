#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BASE_TAG = "P6BI-PFB-TILE-BASE-BRIDGE-20261024-A"
BUILD_TAG = "P6BJ-PFB-ZCOMP-BRIDGE-20261024-A"
COOKIE_OLD = "phase6bi_env_build_cookie"
COOKIE_NEW = "phase6bj_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BJ] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BI build tag")

    old_policy = (
        "Policy: Phase 6BI complete documented PFB tile base/limit/pitch "
        "shadowing inside sub_00292586 while retaining scoped PGRAPH state; "
        "all other NV2A/MMIO/VRAM stays fenced"
    )
    new_policy = (
        "Policy: Phase 6BJ shadow documented PFB ZCOMP tile/tag state and "
        "ZCOMP offset only through sub_00292586 scoped dword accesses while "
        "retaining PFB tile and PGRAPH state; all other NV2A/MMIO/VRAM stays fenced"
    )
    text = replace_once(text, old_policy, new_policy, "Phase 6BI runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BI", "PHASE 6BJ")
    text = text.replace("Phase 6BI", "Phase 6BJ")
    text = text.replace('"P6BI ', '"P6BJ ')

    state_old = "static uint32_t s_phase6bhPgraphShadow[0x2000u / 4u] = { 0u };\n"
    state_new = """static uint32_t s_phase6bhPgraphShadow[0x2000u / 4u] = { 0u };
static DWORD s_phase6bjPfbZcompWrite32Count = 0u;
static DWORD s_phase6bjPfbZcompRead32Count = 0u;
static uint32_t s_phase6bjPfbZcompShadow[8] = { 0u };
static uint32_t s_phase6bjPfbZcompOffsetShadow = 0u;
"""
    text = replace_once(text, state_old, state_new, "PGRAPH shadow state anchor")

    proto_anchor = "static void phase6bh_pgraph_scoped_write32(uint32_t address, uint32_t value)\n"
    prototypes = r'''static bool phase6bj_pfb_zcomp_address(
    uint32_t address,
    uint32_t *tile_index,
    bool *is_offset);
static void phase6bj_pfb_zcomp_write32(uint32_t address, uint32_t value);
static uint32_t phase6bj_pfb_zcomp_read32(uint32_t address);

'''
    text = replace_once(
        text,
        proto_anchor,
        prototypes + proto_anchor,
        "Phase 6BH PGRAPH wrapper declaration anchor",
    )

    helper_anchor = "static void phase4c_budget_tick(DWORD va)\n"
    helper = r'''static bool phase6bj_pfb_zcomp_address(
    uint32_t address,
    uint32_t *tile_index,
    bool *is_offset)
{
    if (address >= 0xFD100300u && address < 0xFD100320u &&
        (address & 3u) == 0u)
    {
        if (tile_index)
            *tile_index = (address - 0xFD100300u) >> 2;
        if (is_offset)
            *is_offset = false;
        return true;
    }

    if (address == 0xFD100324u)
    {
        if (tile_index)
            *tile_index = 0u;
        if (is_offset)
            *is_offset = true;
        return true;
    }

    return false;
}

static void phase6bj_pfb_zcomp_write32(uint32_t address, uint32_t value)
{
    uint32_t tile = 0u;
    bool is_offset = false;
    char line[224];

    if (s_phase6atPostCreateInitActive &&
        phase6bj_pfb_zcomp_address(address, &tile, &is_offset))
    {
        if (is_offset)
            s_phase6bjPfbZcompOffsetShadow = value;
        else
            s_phase6bjPfbZcompShadow[tile] = value;

        ++s_phase6bjPfbZcompWrite32Count;
        if (s_phase6bjPfbZcompWrite32Count <= 32u)
        {
            if (is_offset)
            {
                sprintf(
                    line,
                    "P6BJ PFB ZCOMP OFFSET WRITE32 addr=%08X value=%08X count=%u",
                    (unsigned int)address,
                    (unsigned int)value,
                    (unsigned int)s_phase6bjPfbZcompWrite32Count);
            }
            else
            {
                sprintf(
                    line,
                    "P6BJ PFB ZCOMP WRITE32 addr=%08X tile=%u value=%08X count=%u",
                    (unsigned int)address,
                    (unsigned int)tile,
                    (unsigned int)value,
                    (unsigned int)s_phase6bjPfbZcompWrite32Count);
            }
            trace(line);
        }
        return;
    }

    GUEST_WRITE32(address, value);
}

static uint32_t phase6bj_pfb_zcomp_read32(uint32_t address)
{
    uint32_t tile = 0u;
    bool is_offset = false;
    uint32_t value;
    char line[224];

    if (s_phase6atPostCreateInitActive &&
        phase6bj_pfb_zcomp_address(address, &tile, &is_offset))
    {
        value = is_offset
            ? s_phase6bjPfbZcompOffsetShadow
            : s_phase6bjPfbZcompShadow[tile];

        ++s_phase6bjPfbZcompRead32Count;
        if (s_phase6bjPfbZcompRead32Count <= 32u)
        {
            if (is_offset)
            {
                sprintf(
                    line,
                    "P6BJ PFB ZCOMP OFFSET READ32 addr=%08X value=%08X count=%u",
                    (unsigned int)address,
                    (unsigned int)value,
                    (unsigned int)s_phase6bjPfbZcompRead32Count);
            }
            else
            {
                sprintf(
                    line,
                    "P6BJ PFB ZCOMP READ32 addr=%08X tile=%u value=%08X count=%u",
                    (unsigned int)address,
                    (unsigned int)tile,
                    (unsigned int)value,
                    (unsigned int)s_phase6bjPfbZcompRead32Count);
            }
            trace(line);
        }
        return value;
    }

    return GUEST_READ32(address);
}

'''
    text = replace_once(text, helper_anchor, helper + helper_anchor, "budget tick helper anchor")

    write_old = """    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, NULL))
    {
        phase6bg_pfb_tile_write32(address, value);
        return;
    }

    GUEST_WRITE32(address, value);
}"""
    write_new = """    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, NULL))
    {
        phase6bg_pfb_tile_write32(address, value);
        return;
    }

    if (s_phase6atPostCreateInitActive &&
        phase6bj_pfb_zcomp_address(address, NULL, NULL))
    {
        phase6bj_pfb_zcomp_write32(address, value);
        return;
    }

    GUEST_WRITE32(address, value);
}"""
    text = replace_once(text, write_old, write_new, "scoped write fallback")

    read_old = """    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, NULL))
    {
        return phase6bg_pfb_tile_read32(address);
    }

    return GUEST_READ32(address);
}"""
    read_new = """    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, NULL))
    {
        return phase6bg_pfb_tile_read32(address);
    }

    if (s_phase6atPostCreateInitActive &&
        phase6bj_pfb_zcomp_address(address, NULL, NULL))
    {
        return phase6bj_pfb_zcomp_read32(address);
    }

    return GUEST_READ32(address);
}"""
    text = replace_once(text, read_old, read_new, "scoped read fallback")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BJ] stale Phase 6BI env cookie remains")
    return text

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BI", "PHASE 6BJ")
    text = text.replace("Phase 6BI", "Phase 6BJ")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BJ] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BJ] stale Phase 6BI cookie remains in env")
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
        args.base_dir / "phase6bi-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BJ] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6bi-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BI" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BJ] baseline identity mismatch")

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

    manifest["phase"] = "6BJ"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bj_pfb_zcomp_bridge"] = {
        "source_phase": "6BI",
        "hardware_proof": {
            "tile1_base_write": {
                "address": "0xFD100250",
                "value": "0x024FC003",
            },
            "tile1_base_readback": "0x024FC003",
            "pgraph_readbacks": {
                "0xFD400910": "0x024FC003",
                "0xFD400918": "0x00000A00",
                "0xFD400914": "0x02627FFF",
            },
            "next_mmio_access": "WRITE32 0xFD100304",
            "next_mmio_value": "0x84000000",
            "final_va": "0x00292708",
            "ticks": 671009,
        },
        "register_semantics": {
            "pfb_zcomp_base": "0xFD100300",
            "tile_count": 8,
            "tile_stride": 4,
            "observed_tile": 1,
            "observed_tile_address": "0xFD100304",
            "observed_tile_value": "0x84000000",
            "pfb_zcomp_offset": "0xFD100324",
            "source_basis": "XboxDev/nxdk NV_PFB_ZCOMP and NV_PFB_ZCOMP_OFFSET definitions; translated sub_00292586 computes both +0x100300 indexed and +0x100324 accesses",
        },
        "scope": (
            "runtime classifier added only behind sub_00292586's inherited "
            "phase6bh_pgraph_scoped_write32/read32 wrapper; accepts aligned "
            "PFB ZCOMP tile dwords 0xFD100300-0xFD10031C and exact "
            "ZCOMP_OFFSET 0xFD100324 while post-create init is active"
        ),
        "pfb_tile_scope_unchanged": True,
        "pgraph_scope_unchanged": True,
        "all_other_mmio_fenced": True,
        "other_functions_mmio_fenced": True,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6bj-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BJ] 6BI hardware: tile1 BASE write/readback crossed")
    print("[Phase6BJ] 6BI hardware: PGRAPH 0910/0918/0914 readbacks matched shadow state")
    print("[Phase6BJ] next boundary WRITE32 FD100304 value=84000000")
    print("[Phase6BJ] FD100304 = documented PFB ZCOMP tile1 register")
    print("[Phase6BJ] also arm exact documented PFB ZCOMP_OFFSET FD100324")
    print("[Phase6BJ] bridge remains scoped through sub_00292586 dword wrapper only")
    print("[Phase6BJ] all other NV2A/MMIO/VRAM remains fenced")
    print("[Phase6BJ] allocator and 8M budget unchanged")
    print("[Phase6BJ] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
