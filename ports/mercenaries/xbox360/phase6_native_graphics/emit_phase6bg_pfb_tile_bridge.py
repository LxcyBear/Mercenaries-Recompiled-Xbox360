#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6BF-PGRAPH-IDLE700-BRIDGE-20261024-A"
BUILD_TAG = "P6BG-PFB-TILE-BRIDGE-20261024-A"
COOKIE_OLD = "phase6bf_env_build_cookie"
COOKIE_NEW = "phase6bg_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BG] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BF build tag")
    old_policy = "Policy: Phase 6BF add proven PGRAPH 0x700 idle-status read; all other NV2A/MMIO/VRAM stays fenced"
    new_policy = "Policy: Phase 6BG shadow documented PFB tile base/limit/pitch state in sub_00292586; all other NV2A/MMIO/VRAM stays fenced"
    text = replace_once(text, old_policy, new_policy, "Phase 6BF runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BF", "PHASE 6BG")
    text = text.replace("Phase 6BF", "Phase 6BG")
    text = text.replace('"P6BF ', '"P6BG ')

    state_old = "static DWORD s_phase6bfPgraph700Read32Count = 0u;\n"
    state_new = """static DWORD s_phase6bfPgraph700Read32Count = 0u;
static DWORD s_phase6bgPfbTileWrite32Count = 0u;
static DWORD s_phase6bgPfbTileRead32Count = 0u;
static uint32_t s_phase6bgPfbTileShadow[32] = { 0u };
"""
    text = replace_once(text, state_old, state_new, "Phase 6BF PGRAPH state anchor")

    helper_anchor = "static void phase4c_budget_tick(DWORD va)\n"
    helper = r'''static bool phase6bg_pfb_tile_address(uint32_t address, uint32_t *shadow_index)
{
    uint32_t offset;
    uint32_t field;

    if (address < 0xFD100240u || address >= 0xFD1002C0u)
        return false;

    offset = address - 0xFD100240u;
    if ((offset & 3u) != 0u)
        return false;

    field = offset & 0xFu;
    if (field != 0u && field != 4u && field != 8u)
        return false;

    if (shadow_index)
        *shadow_index = offset >> 2;
    return true;
}

static void phase6bg_pfb_tile_write32(uint32_t address, uint32_t value)
{
    uint32_t shadow_index = 0u;
    char line[224];

    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, &shadow_index))
    {
        uint32_t offset = address - 0xFD100240u;
        uint32_t tile = offset >> 4;
        uint32_t field = offset & 0xFu;

        s_phase6bgPfbTileShadow[shadow_index] = value;
        ++s_phase6bgPfbTileWrite32Count;

        if (s_phase6bgPfbTileWrite32Count <= 32u)
        {
            sprintf(
                line,
                "P6BG PFB TILE WRITE32 addr=%08X tile=%u field=%02X value=%08X count=%u",
                (unsigned int)address,
                (unsigned int)tile,
                (unsigned int)field,
                (unsigned int)value,
                (unsigned int)s_phase6bgPfbTileWrite32Count);
            trace(line);
        }
        return;
    }

    GUEST_WRITE32(address, value);
}

static uint32_t phase6bg_pfb_tile_read32(uint32_t address)
{
    uint32_t shadow_index = 0u;
    char line[224];

    if (s_phase6atPostCreateInitActive &&
        phase6bg_pfb_tile_address(address, &shadow_index))
    {
        uint32_t value = s_phase6bgPfbTileShadow[shadow_index];
        uint32_t offset = address - 0xFD100240u;
        uint32_t tile = offset >> 4;
        uint32_t field = offset & 0xFu;

        ++s_phase6bgPfbTileRead32Count;
        if (s_phase6bgPfbTileRead32Count <= 32u)
        {
            sprintf(
                line,
                "P6BG PFB TILE READ32 addr=%08X tile=%u field=%02X value=%08X count=%u",
                (unsigned int)address,
                (unsigned int)tile,
                (unsigned int)field,
                (unsigned int)value,
                (unsigned int)s_phase6bgPfbTileRead32Count);
            trace(line);
        }
        return value;
    }

    return GUEST_READ32(address);
}

'''
    text = replace_once(text, helper_anchor, helper + helper_anchor, "budget tick helper anchor")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BG] stale Phase 6BF env cookie remains")
    return text

def patch_tile_function(text: str, label: str) -> str:
    m = re.search(
        r"((?:static\s+)?void\s+sub_00292586\s*\(\s*void\s*\)\s*\{.*?\n\})",
        text,
        re.S | re.I,
    )
    if not m:
        raise SystemExit(f"[Phase6BG] sub_00292586 body not found in {label}")

    body = m.group(1)
    replacements = (
        (
            "GUEST_WRITE32(eax + 0x100244, edx);",
            "phase6bg_pfb_tile_write32(eax + 0x100244, edx);",
            "tile limit write",
        ),
        (
            "GUEST_WRITE32(eax + 0x100248, ecx);",
            "phase6bg_pfb_tile_write32(eax + 0x100248, ecx);",
            "tile pitch write",
        ),
        (
            "eax = GUEST_READ32(ecx + 0x100248);",
            "eax = phase6bg_pfb_tile_read32(ecx + 0x100248);",
            "tile pitch readback",
        ),
        (
            "ecx = GUEST_READ32(eax + 0x100244);",
            "ecx = phase6bg_pfb_tile_read32(eax + 0x100244);",
            "tile limit readback",
        ),
    )

    for old, new, desc in replacements:
        n = body.count(old)
        if n != 1:
            raise SystemExit(
                f"[Phase6BG] expected one {desc} in sub_00292586 for {label}, found {n}"
            )
        body = body.replace(old, new, 1)

    patched = text[:m.start()] + body + text[m.end():]
    if body.count("phase6bg_pfb_tile_write32") != 2:
        raise SystemExit(f"[Phase6BG] expected two tile write bridge sites in {label}")
    if body.count("phase6bg_pfb_tile_read32") != 2:
        raise SystemExit(f"[Phase6BG] expected two tile read bridge sites in {label}")
    return patched

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BF", "PHASE 6BG")
    text = text.replace("Phase 6BF", "Phase 6BG")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BG] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BG] stale Phase 6BF cookie remains in env")
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
        args.base_dir / "phase6bf-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BG] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6bf-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BF" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BG] baseline identity mismatch")

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
    mono = patch_tile_function(mono, "main_monolithic.cpp")

    shard_hits = 0
    for shard in sorted(shard_out.glob("*.inl")):
        raw = shard.read_text(encoding="utf-8")
        if "sub_00292586" not in raw:
            continue
        patched = patch_tile_function(raw, shard.name)
        shard.write_text(patched, encoding="utf-8")
        shard_hits += 1
    if shard_hits != 1:
        raise SystemExit(
            f"[Phase6BG] expected exactly one translated shard patch, patched {shard_hits}"
        )

    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6BG"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bg_pfb_tile_bridge"] = {
        "source_phase": "6BF",
        "hardware_proof": {
            "pgraph_idle700_bridge_completed": True,
            "pgraph_idle700_reads": 2,
            "second_tail_claim_base": "0x024FC000",
            "second_tail_claim_size": 1228800,
            "second_tail_claim_limit_inclusive": "0x02627FFF",
            "next_mmio_access": "WRITE32 0xFD100254",
            "next_mmio_value": "0x02627FFF",
            "final_va": "0x00292618",
            "ticks": 670997,
        },
        "register_semantics": {
            "block": "PFB",
            "tile_array_base": "0xFD100240",
            "tile_stride": 16,
            "tile_count": 8,
            "fields": {
                "0x0": "BASE_ADDRESS_AND_FLAGS",
                "0x4": "LIMIT",
                "0x8": "PITCH",
            },
            "maintained_backend": "pfb_write stores generic PFB register state; pfb_read returns stored state",
        },
        "current_observation": {
            "tile": 1,
            "limit_address": "0xFD100254",
            "limit_value": "0x02627FFF",
            "pitch_address_expected_next": "0xFD100258",
            "pitch_value_from_fault_register_ecx": "0x00000A00",
        },
        "scope": "four exact tile setup/readback source sites in sub_00292586; runtime helper accepts only documented PFB tile base/limit/pitch dwords while post-create init is active",
        "all_other_mmio_fenced": True,
        "mmio_global_fence_changed": False,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6bg-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BG] 6BF hardware: PGRAPH 0x700 idle read crossed twice")
    print("[Phase6BG] next boundary WRITE32 FD100254 = PFB tile1 LIMIT")
    print("[Phase6BG] observed LIMIT 02627FFF exactly matches 024FC000 + 1228800 - 1")
    print("[Phase6BG] bridge documented PFB tile base/limit/pitch shadow state in sub_00292586")
    print("[Phase6BG] all other NV2A/MMIO/VRAM accesses remain fenced")
    print("[Phase6BG] allocator and 8M budget unchanged")
    print("[Phase6BG] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
