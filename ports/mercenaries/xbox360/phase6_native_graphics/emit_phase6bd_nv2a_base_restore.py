#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6AW-D3D-SPIN-PROBE-20261024-A"
BUILD_TAG = "P6BD-NV2A-BASE-RESTORE-20261024-A"
COOKIE_OLD = "phase6aw_env_build_cookie"
COOKIE_NEW = "phase6bd_env_build_cookie"
CHILD_ADDR = 0x0029AFA8
NV2A_BASE = 0xFD000000

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6BD] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6AW build tag")
    old_policy = "Policy: Phase 6AW keeps 6AV behavior; probe the 8M D3D spin without relaxing any fence"
    new_policy = "Policy: Phase 6BD restore proven D3D child NV2A base only; preserve all MMIO/VRAM fences"
    text = replace_once(text, old_policy, new_policy, "Phase 6AW runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6AW", "PHASE 6BD")
    text = text.replace("Phase 6AW", "Phase 6BD")
    text = text.replace('"P6AW ', '"P6BD ')

    state_old = "static DWORD s_phase6awVaRingCount = 0u;\n"
    state_new = """static DWORD s_phase6awVaRingCount = 0u;
static DWORD s_phase6bdNv2aBaseRestoreCount = 0u;
"""
    text = replace_once(text, state_old, state_new, "Phase 6AW VA-ring state anchor")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BD] stale Phase 6AW env cookie remains")
    return text

def patch_wait_function(text: str, label: str) -> str:
    pattern = re.compile(
        r"(static\s+void\s+sub_00292271\s*\(\s*void\s*\)\s*\{.*?"
        r"edi\s*=\s*ecx\s*;\s*\n"
        r"\s*esi\s*=\s*GUEST_READ32\(edi\)\s*;\s*\n)",
        re.S,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6BD] expected one sub_00292271 prologue anchor in {label}, found {len(matches)}"
        )

    restore = f"""    if (s_phase6atPostCreateInitActive &&
        edi == 0x{CHILD_ADDR:08X}u &&
        esi == 0u &&
        s_phase6bdNv2aBaseRestoreCount == 0u)
    {{
        char p6bd_line[192];

        /*
         * Phase 6BC proved the retail constructor helper sub_00291F31 does:
         *     GUEST_WRITE32(ecx, 0xFD000000)
         * before its first NV2A MMIO access at 0xFD001804.
         *
         * Restore only that proven constructor field. Do not emulate or
         * relax any NV2A/MMIO/VRAM access; the existing hard fence owns the
         * next read from the 0xFDxxxxxx aperture.
         */
        GUEST_WRITE32(edi, 0x{NV2A_BASE:08X}u);
        esi = 0x{NV2A_BASE:08X}u;
        ++s_phase6bdNv2aBaseRestoreCount;

        sprintf(
            p6bd_line,
            "P6BD NV2A BASE RESTORE child=%08X old=00000000 new=%08X count=%u",
            (unsigned int)edi,
            (unsigned int)esi,
            (unsigned int)s_phase6bdNv2aBaseRestoreCount);
        trace(p6bd_line);
    }}

"""
    m = matches[0]
    insert_at = m.end()
    text = text[:insert_at] + restore + text[insert_at:]
    if "P6BD NV2A BASE RESTORE" not in text:
        raise SystemExit(f"[Phase6BD] restore marker did not land in {label}")
    return text

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6AW", "PHASE 6BD")
    text = text.replace("Phase 6AW", "Phase 6BD")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6BD] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6BD] stale Phase 6AW cookie remains in env")
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
        args.base_dir / "phase6aw-manifest.json",
        args.base_dir / "translated_shards",
    )
    for p in required:
        if not p.exists():
            raise SystemExit(f"[Phase6BD] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6aw-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6AW" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BD] baseline identity mismatch")

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
            f"[Phase6BD] expected restore in exactly one translated shard, patched {shard_hits}"
        )

    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6BD"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6bd_nv2a_base_restore"] = {
        "source_phase": "6AW",
        "phase6bc_proof": {
            "constructor": "sub_00292424 -> sub_00291F31",
            "child_address": f"0x{CHILD_ADDR:08X}",
            "first_dword_value": f"0x{NV2A_BASE:08X}",
            "first_retail_mmio_read": "0xFD001804",
        },
        "restore_scope": "sub_00292271 first use while s_phase6atPostCreateInitActive",
        "only_if_zero": True,
        "one_shot": True,
        "execution_budget": 8000000,
        "ready_bit_shims": False,
        "mmio_emulation_added": False,
        "mmio_fence_changed": False,
        "vram_fence_changed": False,
        "allocator_policy_changed": False,
        "translated_membership_changed": False,
    }
    (args.out_dir / "phase6bd-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BD] Phase 6BC proof: sub_00291F31 writes child[0] = 0xFD000000")
    print("[Phase6BD] restoring only child 0x0029AFA8 first DWORD, one shot, if zero")
    print("[Phase6BD] no ready-bit shim")
    print("[Phase6BD] no NV2A/MMIO/VRAM emulation or fence relaxation")
    print("[Phase6BD] allocator and 8M budget unchanged")
    print("[Phase6BD] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
