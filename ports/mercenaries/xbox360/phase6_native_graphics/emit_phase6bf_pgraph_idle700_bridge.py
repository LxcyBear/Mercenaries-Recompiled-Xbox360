#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6BE-PFIFO-IDLE-BRIDGE-20261024-A"
BUILD_TAG = "P6BF-PGRAPH-IDLE700-BRIDGE-20261024-A"
COOKIE_OLD = "phase6be_env_build_cookie"
COOKIE_NEW = "phase6bf_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BF] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BE build tag")
    old_policy = "Policy: Phase 6BE bridge proven PFIFO idle-status reads only; all other NV2A/MMIO/VRAM stays fenced"
    new_policy = "Policy: Phase 6BF add proven PGRAPH 0x700 idle-status read; all other NV2A/MMIO/VRAM stays fenced"
    text = replace_once(text, old_policy, new_policy, "Phase 6BE runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BE", "PHASE 6BF")
    text = text.replace("Phase 6BE", "Phase 6BF")
    text = text.replace('"P6BE ', '"P6BF ')

    state_old = "static DWORD s_phase6bePfifoWrite32Count = 0u;\n"
    state_new = """static DWORD s_phase6bePfifoWrite32Count = 0u;
static DWORD s_phase6bfPgraph700Read32Count = 0u;
"""
    text = replace_once(text, state_old, state_new, "Phase 6BE PFIFO state anchor")

    helper_anchor = "static void phase4c_budget_tick(DWORD va)\n"
    helper = r'''static uint32_t phase6bf_pgraph_idle700_read32(uint32_t address)
{
    char line[192];

    if (s_phase6atPostCreateInitActive && address == 0xFD400700u)
    {
        ++s_phase6bfPgraph700Read32Count;
        if (s_phase6bfPgraph700Read32Count <= 16u)
        {
            sprintf(
                line,
                "P6BF PGRAPH IDLE700 READ32 addr=%08X value=00000000 count=%u",
                (unsigned int)address,
                (unsigned int)s_phase6bfPgraph700Read32Count);
            trace(line);
        }

        /*
         * The maintained src/nv2a backend routes BAR0+0x400000 through
         * pgraph_read(), whose standalone state is zero-initialized.
         * That source also documents register offset 0x700 as the XDK
         * idle-status read.  Return the backend-equivalent idle value only
         * for this exact hardware-proven address.
         */
        return 0u;
    }

    return GUEST_READ32(address);
}

'''
    text = replace_once(text, helper_anchor, helper + helper_anchor, "budget tick helper anchor")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BF] stale Phase 6BE env cookie remains")
    return text

def patch_pgraph_wait_function(text: str, label: str) -> str:
    m = re.search(
        r"((?:static\s+)?void\s+sub_0029528C\s*\(\s*void\s*\)\s*\{.*?\n\})",
        text,
        re.S | re.I,
    )
    if not m:
        raise SystemExit(f"[Phase6BF] sub_0029528C body not found in {label}")

    body = m.group(1)
    pat = re.compile(r"GUEST_READ32\(([^()\n]*0x400700[^()\n]*)\)", re.I)
    hits = list(pat.finditer(body))
    if len(hits) != 2:
        details = " | ".join(m.group(0) for m in hits) if hits else "<none>"
        raise SystemExit(
            f"[Phase6BF] expected exactly two 0x400700 READ32 sites in sub_0029528C "
            f"for {label}, found {len(hits)}: {details}"
        )

    body = pat.sub(r"phase6bf_pgraph_idle700_read32(\1)", body)
    patched = text[:m.start()] + body + text[m.end():]

    if "phase6bf_pgraph_idle700_read32" not in body:
        raise SystemExit(f"[Phase6BF] PGRAPH 0x700 patch marker missing in {label}")
    return patched

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BE", "PHASE 6BF")
    text = text.replace("Phase 6BE", "Phase 6BF")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BF] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BF] stale Phase 6BE cookie remains in env")
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
        args.base_dir / "phase6be-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BF] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6be-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BE" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BF] baseline identity mismatch")

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
    mono = patch_pgraph_wait_function(mono, "main_monolithic.cpp")

    shard_hits = 0
    for shard in sorted(shard_out.glob("*.inl")):
        raw = shard.read_text(encoding="utf-8")
        if "sub_0029528C" not in raw:
            continue
        patched = patch_pgraph_wait_function(raw, shard.name)
        shard.write_text(patched, encoding="utf-8")
        shard_hits += 1
    if shard_hits != 1:
        raise SystemExit(
            f"[Phase6BF] expected exactly one translated shard patch, patched {shard_hits}"
        )

    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6BF"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bf_pgraph_idle700_bridge"] = {
        "source_phase": "6BE",
        "hardware_proof": {
            "pfifo_bridge_completed": True,
            "next_mmio_access": "READ32 0xFD400700",
            "boundary": "GUEST_FAULT",
            "fault": 1,
            "ticks": 670916,
            "final_va": "0x0029528C",
        },
        "backend_semantics": {
            "block": "PGRAPH",
            "offset": "0x00000700",
            "existing_backend": "pgraph_read -> d->pgraph.regs[addr]",
            "standalone_initial_value": "0x00000000",
            "source_note": "XDK idle-status read at 0x700",
        },
        "bridge_value": "0x00000000",
        "scope": "both sub_0029528C +0x400700 READ32 source sites; runtime helper returns zero only for exact 0xFD400700 while post-create init is active",
        "all_other_mmio_fenced": True,
        "mmio_global_fence_changed": False,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6bf-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BF] 6BE hardware: PFIFO idle wait completed")
    print("[Phase6BF] next boundary: READ32 FD400700 at sub_0029528C")
    print("[Phase6BF] patch both sub_0029528C +0x400700 source sites; runtime bridge answers exact FD400700 only")
    print("[Phase6BF] all other NV2A/MMIO/VRAM accesses remain fenced")
    print("[Phase6BF] allocator and 8M budget unchanged")
    print("[Phase6BF] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
