#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6BG-PFB-TILE-BRIDGE-20261024-A"
BUILD_TAG = "P6BH-PGRAPH-STATE-BRIDGE-20261024-A"
COOKIE_OLD = "phase6bg_env_build_cookie"
COOKIE_NEW = "phase6bh_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BH] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BG build tag")
    old_policy = "Policy: Phase 6BG shadow documented PFB tile base/limit/pitch state in sub_00292586; all other NV2A/MMIO/VRAM stays fenced"
    new_policy = "Policy: Phase 6BH shadow PGRAPH dword register state only inside sub_00292586; all other NV2A/MMIO/VRAM stays fenced"
    text = replace_once(text, old_policy, new_policy, "Phase 6BG runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BG", "PHASE 6BH")
    text = text.replace("Phase 6BG", "Phase 6BH")
    text = text.replace('"P6BG ', '"P6BH ')

    state_old = "static uint32_t s_phase6bgPfbTileShadow[32] = { 0u };\n"
    state_new = """static uint32_t s_phase6bgPfbTileShadow[32] = { 0u };
static DWORD s_phase6bhPgraphWrite32Count = 0u;
static DWORD s_phase6bhPgraphRead32Count = 0u;
static uint32_t s_phase6bhPgraphShadow[0x2000u / 4u] = { 0u };
"""
    text = replace_once(text, state_old, state_new, "Phase 6BG PFB shadow anchor")

    helper_anchor = "static void phase4c_budget_tick(DWORD va)\n"
    helper = r'''static bool phase6bh_pgraph_dword_address(uint32_t address, uint32_t *shadow_index)
{
    if (address < 0xFD400000u || address >= 0xFD402000u)
        return false;
    if ((address & 3u) != 0u)
        return false;

    if (shadow_index)
        *shadow_index = (address - 0xFD400000u) >> 2;
    return true;
}

static void phase6bh_pgraph_scoped_write32(uint32_t address, uint32_t value)
{
    uint32_t shadow_index = 0u;
    char line[224];

    if (s_phase6atPostCreateInitActive &&
        phase6bh_pgraph_dword_address(address, &shadow_index))
    {
        s_phase6bhPgraphShadow[shadow_index] = value;
        ++s_phase6bhPgraphWrite32Count;

        if (s_phase6bhPgraphWrite32Count <= 64u)
        {
            sprintf(
                line,
                "P6BH PGRAPH WRITE32 addr=%08X offset=%04X value=%08X count=%u",
                (unsigned int)address,
                (unsigned int)(address - 0xFD400000u),
                (unsigned int)value,
                (unsigned int)s_phase6bhPgraphWrite32Count);
            trace(line);
        }
        return;
    }

    GUEST_WRITE32(address, value);
}

static uint32_t phase6bh_pgraph_scoped_read32(uint32_t address)
{
    uint32_t shadow_index = 0u;
    char line[224];

    if (s_phase6atPostCreateInitActive &&
        phase6bh_pgraph_dword_address(address, &shadow_index))
    {
        uint32_t value = s_phase6bhPgraphShadow[shadow_index];
        ++s_phase6bhPgraphRead32Count;

        if (s_phase6bhPgraphRead32Count <= 64u)
        {
            sprintf(
                line,
                "P6BH PGRAPH READ32 addr=%08X offset=%04X value=%08X count=%u",
                (unsigned int)address,
                (unsigned int)(address - 0xFD400000u),
                (unsigned int)value,
                (unsigned int)s_phase6bhPgraphRead32Count);
            trace(line);
        }
        return value;
    }

    return GUEST_READ32(address);
}

'''
    text = replace_once(text, helper_anchor, helper + helper_anchor, "budget tick helper anchor")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BH] stale Phase 6BG env cookie remains")
    return text

def patch_pgraph_function(text: str, label: str) -> tuple[str, int, int]:
    m = re.search(
        r"((?:static\s+)?void\s+sub_00292586\s*\(\s*void\s*\)\s*\{.*?\n\})",
        text,
        re.S | re.I,
    )
    if not m:
        raise SystemExit(f"[Phase6BH] sub_00292586 body not found in {label}")

    body = m.group(1)

    # 6BG already owns the proven PFB tile accesses.  Route the remaining raw
    # dword guest accesses through a runtime classifier.  Normal guest RAM
    # falls straight through unchanged; only FD400000-FD401FFF is shadowed.
    write_count = body.count("GUEST_WRITE32(")
    read_count = body.count("GUEST_READ32(")
    if write_count < 1:
        raise SystemExit(f"[Phase6BH] no raw GUEST_WRITE32 sites found in sub_00292586 for {label}")
    if read_count < 1:
        raise SystemExit(f"[Phase6BH] no raw GUEST_READ32 sites found in sub_00292586 for {label}")

    body = body.replace("GUEST_WRITE32(", "phase6bh_pgraph_scoped_write32(")
    body = body.replace("GUEST_READ32(", "phase6bh_pgraph_scoped_read32(")

    if "phase6bg_pfb_tile_write32(eax + 0x100244, edx)" not in body:
        raise SystemExit(f"[Phase6BH] inherited 6BG tile LIMIT bridge missing in {label}")
    if "phase6bg_pfb_tile_write32(eax + 0x100248, ecx)" not in body:
        raise SystemExit(f"[Phase6BH] inherited 6BG tile PITCH bridge missing in {label}")

    patched = text[:m.start()] + body + text[m.end():]
    return patched, write_count, read_count

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BG", "PHASE 6BH")
    text = text.replace("Phase 6BG", "Phase 6BH")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BH] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BH] stale Phase 6BG cookie remains in env")
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
        args.base_dir / "phase6bg-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BH] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6bg-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BG" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BH] baseline identity mismatch")

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
    mono, mono_writes, mono_reads = patch_pgraph_function(
        mono, "main_monolithic.cpp"
    )

    shard_hits = 0
    shard_writes = 0
    shard_reads = 0
    for shard in sorted(shard_out.glob("*.inl")):
        raw = shard.read_text(encoding="utf-8")
        if "sub_00292586" not in raw:
            continue
        patched, wc, rc = patch_pgraph_function(raw, shard.name)
        shard.write_text(patched, encoding="utf-8")
        shard_hits += 1
        shard_writes += wc
        shard_reads += rc

    if shard_hits != 1:
        raise SystemExit(
            f"[Phase6BH] expected exactly one translated shard patch, patched {shard_hits}"
        )
    if shard_writes != mono_writes or shard_reads != mono_reads:
        raise SystemExit(
            "[Phase6BH] monolithic/shard raw dword access counts disagree: "
            f"mono writes={mono_writes} reads={mono_reads}, "
            f"shard writes={shard_writes} reads={shard_reads}"
        )

    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6BH"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bh_pgraph_state_bridge"] = {
        "source_phase": "6BG",
        "hardware_proof": {
            "pfb_tile_limit_write": {
                "address": "0xFD100254",
                "value": "0x02627FFF",
            },
            "pfb_tile_pitch_write": {
                "address": "0xFD100258",
                "value": "0x00000A00",
            },
            "next_mmio_access": "WRITE32 0xFD400914",
            "final_va": "0x00292618",
            "ticks": 670997,
        },
        "backend_semantics": {
            "block": "PGRAPH",
            "range": "0xFD400000-0xFD401FFF",
            "maintained_backend": "pgraph_write stores regs[addr]=value; pgraph_read returns regs[addr]",
        },
        "scope": {
            "function": "sub_00292586",
            "access_width": 4,
            "runtime_range": "0xFD400000-0xFD401FFF",
            "raw_write_sites_wrapped": mono_writes,
            "raw_read_sites_wrapped": mono_reads,
            "normal_guest_addresses_fall_through": True,
        },
        "all_other_mmio_fenced": True,
        "other_functions_pgraph_fenced": True,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6bh-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BH] 6BG hardware: tile1 LIMIT/PITCH writes crossed")
    print("[Phase6BH] next boundary: WRITE32 FD400914 in sub_00292586")
    print("[Phase6BH] maintained backend semantics: generic PGRAPH write=store, read=readback")
    print(
        f"[Phase6BH] wrapped sub_00292586 raw dword sites: "
        f"writes={mono_writes} reads={mono_reads}"
    )
    print("[Phase6BH] runtime bridge accepts only aligned FD400000-FD401FFF dwords")
    print("[Phase6BH] other functions and all other MMIO/VRAM remain fenced")
    print("[Phase6BH] allocator and 8M budget unchanged")
    print("[Phase6BH] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
