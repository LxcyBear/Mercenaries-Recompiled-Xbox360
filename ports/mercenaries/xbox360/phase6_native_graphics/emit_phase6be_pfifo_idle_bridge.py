#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6BD-NV2A-BASE-RESTORE-20261024-A"
BUILD_TAG = "P6BE-PFIFO-IDLE-BRIDGE-20261024-A"
COOKIE_OLD = "phase6bd_env_build_cookie"
COOKIE_NEW = "phase6be_env_build_cookie"

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BE] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6BD build tag")
    old_policy = "Policy: Phase 6BD restore proven D3D child NV2A base only; preserve all MMIO/VRAM fences"
    new_policy = "Policy: Phase 6BE bridge proven PFIFO idle-status reads only; all other NV2A/MMIO/VRAM stays fenced"
    text = replace_once(text, old_policy, new_policy, "Phase 6BD runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BD", "PHASE 6BE")
    text = text.replace("Phase 6BD", "Phase 6BE")
    text = text.replace('"P6BD ', '"P6BE ')

    state_old = "static DWORD s_phase6bdNv2aBaseRestoreCount = 0u;\n"
    state_new = """static DWORD s_phase6bdNv2aBaseRestoreCount = 0u;
static DWORD s_phase6bePfifoRead8Count = 0u;
static DWORD s_phase6bePfifoRead32Count = 0u;
static DWORD s_phase6bePfifoWrite32Count = 0u;
"""
    text = replace_once(text, state_old, state_new, "Phase 6BD restore state anchor")

    helper_anchor = "static void phase4c_budget_tick(DWORD va)\n"
    helper = r'''static uint8_t phase6be_pfifo_idle_read8(uint32_t address)
{
    uint8_t value;
    char line[192];

    if (s_phase6atPostCreateInitActive)
    {
        if (address == 0xFD003214u)
            value = 0x10u; /* NV_PFIFO_CACHE1_STATUS_LOW_MARK */
        else if (address == 0xFD002400u)
            value = 0x10u; /* NV_PFIFO_RUNOUT_STATUS_LOW_MARK */
        else if (address == 0xFD003220u)
            value = 0x00u; /* NV_PFIFO_CACHE1_DMA_PUSH_STATE clear / idle */
        else
            return GUEST_READ8(address);

        ++s_phase6bePfifoRead8Count;
        if (s_phase6bePfifoRead8Count <= 16u)
        {
            sprintf(
                line,
                "P6BE PFIFO READ8 addr=%08X value=%02X count=%u",
                (unsigned int)address,
                (unsigned int)value,
                (unsigned int)s_phase6bePfifoRead8Count);
            trace(line);
        }
        return value;
    }

    return GUEST_READ8(address);
}

static uint32_t phase6be_pfifo_idle_read32(uint32_t address)
{
    char line[192];

    if (s_phase6atPostCreateInitActive && address == 0xFD003220u)
    {
        ++s_phase6bePfifoRead32Count;
        if (s_phase6bePfifoRead32Count <= 8u)
        {
            sprintf(
                line,
                "P6BE PFIFO READ32 addr=%08X value=00000000 count=%u",
                (unsigned int)address,
                (unsigned int)s_phase6bePfifoRead32Count);
            trace(line);
        }
        return 0u; /* NV_PFIFO_CACHE1_DMA_PUSH idle */
    }

    return GUEST_READ32(address);
}

static void phase6be_pfifo_idle_write32(uint32_t address, uint32_t value)
{
    char line[192];

    if (s_phase6atPostCreateInitActive &&
        address == 0xFD003220u &&
        value == 0u)
    {
        ++s_phase6bePfifoWrite32Count;
        if (s_phase6bePfifoWrite32Count <= 8u)
        {
            sprintf(
                line,
                "P6BE PFIFO WRITE32 addr=%08X value=%08X count=%u",
                (unsigned int)address,
                (unsigned int)value,
                (unsigned int)s_phase6bePfifoWrite32Count);
            trace(line);
        }
        return; /* backend-equivalent zero write; no other MMIO is bridged */
    }

    GUEST_WRITE32(address, value);
}

'''
    text = replace_once(text, helper_anchor, helper + helper_anchor, "budget tick helper anchor")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BE] stale Phase 6BD env cookie remains")
    return text

def patch_wait_function(text: str, label: str) -> str:
    replacements = [
        (
            "if (TEST_Z(GUEST_READ8(esi + 0x3214), 0x10)) goto loc_00292292;",
            "if (TEST_Z(phase6be_pfifo_idle_read8(esi + 0x3214), 0x10)) goto loc_00292292;",
            "CACHE1_STATUS read8",
        ),
        (
            "if (TEST_Z(GUEST_READ8(esi + 0x2400), 0x10)) goto loc_00292292;",
            "if (TEST_Z(phase6be_pfifo_idle_read8(esi + 0x2400), 0x10)) goto loc_00292292;",
            "RUNOUT_STATUS read8",
        ),
        (
            "if (TEST_Z(GUEST_READ8(esi + 0x3220), 0x10)) goto loc_002922BE;",
            "if (TEST_Z(phase6be_pfifo_idle_read8(esi + 0x3220), 0x10)) goto loc_002922BE;",
            "DMA_PUSH gate read8",
        ),
        (
            "ecx = GUEST_READ32(eax);",
            "ecx = phase6be_pfifo_idle_read32(eax);",
            "DMA_PUSH read32",
        ),
        (
            "GUEST_WRITE32(eax, 0);",
            "phase6be_pfifo_idle_write32(eax, 0);",
            "DMA_PUSH clear write32",
        ),
        (
            "if (TEST_NZ(GUEST_READ8(eax), 0x10)) goto loc_002922D4;",
            "if (TEST_NZ(phase6be_pfifo_idle_read8(eax), 0x10)) goto loc_002922D4;",
            "DMA_PUSH final read8",
        ),
    ]

    # Restrict edits to the exact translated function body.
    m = re.search(
        r"(static\s+void\s+sub_00292271\s*\(\s*void\s*\)\s*\{.*?\n\})",
        text,
        re.S,
    )
    if not m:
        raise SystemExit(f"[Phase6BE] sub_00292271 body not found in {label}")

    body = m.group(1)
    for old, new, desc in replacements:
        n = body.count(old)
        if n != 1:
            raise SystemExit(
                f"[Phase6BE] expected one {desc} in {label}, found {n}"
            )
        body = body.replace(old, new, 1)

    patched = text[:m.start()] + body + text[m.end():]
    for marker in (
        "phase6be_pfifo_idle_read8(esi + 0x3214)",
        "phase6be_pfifo_idle_read8(esi + 0x2400)",
        "phase6be_pfifo_idle_read8(esi + 0x3220)",
        "phase6be_pfifo_idle_read32(eax)",
        "phase6be_pfifo_idle_write32(eax, 0)",
        "phase6be_pfifo_idle_read8(eax)",
    ):
        if marker not in patched:
            raise SystemExit(f"[Phase6BE] function patch marker missing in {label}: {marker}")
    return patched

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6BD", "PHASE 6BE")
    text = text.replace("Phase 6BD", "Phase 6BE")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BE] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BE] stale Phase 6BD cookie remains in env")
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
        args.base_dir / "phase6bd-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BE] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6bd-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6BD" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BE] baseline identity mismatch")

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
    mono = patch_wait_function(mono, "main_monolithic.cpp")

    shard_hits = 0
    for shard in sorted(shard_out.glob("*.inl")):
        raw = shard.read_text(encoding="utf-8")
        if "sub_00292271" not in raw:
            continue
        patched = patch_wait_function(raw, shard.name)
        shard.write_text(patched, encoding="utf-8")
        shard_hits += 1
    if shard_hits != 1:
        raise SystemExit(
            f"[Phase6BE] expected exactly one translated shard patch, patched {shard_hits}"
        )

    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6BE"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6be_pfifo_idle_bridge"] = {
        "source_phase": "6BD",
        "hardware_proof": {
            "first_mmio_access": "READ8 0xFD003214",
            "boundary": "GUEST_FAULT",
            "fault": 1,
            "final_va": "0x00292277",
        },
        "register_semantics": [
            {
                "address": "0xFD003214",
                "register": "NV_PFIFO_CACHE1_STATUS",
                "read8": "0x10",
                "meaning": "LOW_MARK set; cache1 empty",
            },
            {
                "address": "0xFD002400",
                "register": "NV_PFIFO_RUNOUT_STATUS",
                "read8": "0x10",
                "meaning": "LOW_MARK set; no runout queue modeled",
            },
            {
                "address": "0xFD003220",
                "register": "NV_PFIFO_CACHE1_DMA_PUSH",
                "read8_read32_write32": "0",
                "meaning": "DMA pusher idle; STATE clear",
            },
        ],
        "matches_existing_nv2a_backend": True,
        "scope": "sub_00292271 only while post-create init is active",
        "all_other_mmio_fenced": True,
        "mmio_global_fence_changed": False,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "execution_budget": 8000000,
        "translated_membership_changed": False,
    }

    (args.out_dir / "phase6be-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BE] hardware proof: first graphics touch READ8 FD003214")
    print("[Phase6BE] FD003214 -> PFIFO CACHE1_STATUS LOW_MARK (0x10)")
    print("[Phase6BE] FD002400 -> PFIFO RUNOUT_STATUS LOW_MARK (0x10)")
    print("[Phase6BE] FD003220 -> PFIFO CACHE1_DMA_PUSH idle/state-clear (0x00)")
    print("[Phase6BE] bridge matches existing src/nv2a backend semantics")
    print("[Phase6BE] all other NV2A/MMIO/VRAM accesses remain fenced")
    print("[Phase6BE] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
