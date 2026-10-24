#!/usr/bin/env python3
from __future__ import annotations

import argparse
import json
import re
import shutil
from pathlib import Path

BASE_TAG = "P6AW-D3D-SPIN-PROBE-20261024-A"
BUILD_TAG = "P6AZ-D3D-READY3214-SHIM-20261024-A"
COOKIE_OLD = "phase6aw_env_build_cookie"
COOKIE_NEW = "phase6az_env_build_cookie"
SPIN_THRESHOLD = 4096

def replace_once(text: str, old: str, new: str, label: str) -> str:
    n = text.count(old)
    if n != 1:
        raise SystemExit(f"[Phase6AZ] expected one {label}, found {n}")
    return text.replace(old, new, 1)

def patch_common(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "Phase 6AW build tag")

    old_policy = "Policy: Phase 6AW keeps 6AV behavior; probe the 8M D3D spin without relaxing any fence"
    new_policy = "Policy: Phase 6AZ one-shot D3D +3214 bit10 completion shim after proven spin; all hard fences preserved"
    text = replace_once(text, old_policy, new_policy, "Phase 6AW runtime policy")

    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6AW", "PHASE 6AZ")
    text = text.replace("Phase 6AW", "Phase 6AZ")
    text = text.replace('"P6AW ', '"P6AZ ')

    state_old = "static DWORD s_phase6awVaRingCount = 0u;\n"
    state_new = """static DWORD s_phase6awVaRingCount = 0u;
static DWORD s_phase6azReady3214Entries = 0u;
static DWORD s_phase6azReady3214Fired = 0u;
"""
    text = replace_once(text, state_old, state_new, "Phase 6AW VA-ring state anchor")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6AZ] stale Phase 6AW env cookie remains")
    return text

def patch_wait_function(text: str, label: str) -> str:
    pattern = re.compile(
        r"(static\s+void\s+sub_00292271\s*\(\s*void\s*\)\s*\{.*?"
        r"loc_00292277\s*:\s*;\s*\n)",
        re.S,
    )
    matches = list(pattern.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6AZ] expected one sub_00292271 wait-loop anchor in {label}, "
            f"found {len(matches)}"
        )

    shim = f"""    if (s_phase6atPostCreateInitActive)
    {{
        ++s_phase6azReady3214Entries;
        if (!s_phase6azReady3214Fired &&
            s_phase6azReady3214Entries >= {SPIN_THRESHOLD}u)
        {{
            uint32_t p6az_3214 = (uint32_t)GUEST_READ8(esi + 0x3214);
            uint32_t p6az_2400 = (uint32_t)GUEST_READ8(esi + 0x2400);
            uint32_t p6az_3220 = GUEST_READ32(esi + 0x3220);
            uint32_t p6az_2100 = GUEST_READ32(esi + 0x2100);
            uint32_t p6az_0100 = GUEST_READ32(esi + 0x100);
            uint32_t p6az_400100 = GUEST_READ32(esi + 0x400100);
            char p6az_line[320];

            GUEST_WRITE8(
                esi + 0x3214,
                (uint8_t)(p6az_3214 | 0x10u));
            s_phase6azReady3214Fired = 1u;

            sprintf(
                p6az_line,
                "P6AZ READY3214 SHIM FIRE entries=%u dev=%08X "
                "3214=%02X->%02X 2400=%02X 3220=%08X "
                "2100=%08X 0100=%08X 400100=%08X",
                (unsigned int)s_phase6azReady3214Entries,
                (unsigned int)esi,
                (unsigned int)(p6az_3214 & 0xFFu),
                (unsigned int)((p6az_3214 | 0x10u) & 0xFFu),
                (unsigned int)(p6az_2400 & 0xFFu),
                (unsigned int)p6az_3220,
                (unsigned int)p6az_2100,
                (unsigned int)p6az_0100,
                (unsigned int)p6az_400100);
            trace(p6az_line);
        }}
    }}

"""

    m = matches[0]
    insert_at = m.end()
    text = text[:insert_at] + shim + text[insert_at:]
    if "P6AZ READY3214 SHIM FIRE" not in text:
        raise SystemExit(f"[Phase6AZ] shim marker did not land in {label}")
    return text

def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = text.replace("PHASE 6AW", "PHASE 6AZ")
    text = text.replace("Phase 6AW", "Phase 6AZ")
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6AZ] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6AZ] stale Phase 6AW cookie remains in env")
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
            raise SystemExit(f"[Phase6AZ] missing baseline input: {p}")

    manifest = json.loads(
        (args.base_dir / "phase6aw-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6AW" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AZ] baseline identity mismatch")

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
            f"[Phase6AZ] expected shim to patch exactly one translated shard, "
            f"patched {shard_hits}"
        )

    env = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest["phase"] = "6AZ"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6az_ready3214_shim"] = {
        "source_phase": "6AW",
        "phase6ay_static_audit_writer_count": 0,
        "proven_wait_function": "sub_00292271",
        "proven_wait_va": "0x00292277",
        "device_state_offset": "0x3214",
        "forced_bit": "0x10",
        "activation_entry_count": SPIN_THRESHOLD,
        "scope": "only while s_phase6atPostCreateInitActive is true",
        "one_shot": True,
        "next_gates_left_unmodified": ["0x2400 bit 0x10", "0x3220 bit 0x10"],
        "execution_budget": 8000000,
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "hard_fences_changed": False,
    }
    (args.out_dir / "phase6az-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AZ] static audit: device+0x3214 writer count = 0")
    print(
        f"[Phase6AZ] one-shot shim: after {SPIN_THRESHOLD} "
        "sub_00292271 entries while post-create init is active"
    )
    print("[Phase6AZ] action: device+0x3214 |= 0x10")
    print("[Phase6AZ] +0x2400 and +0x3220 remain untouched")
    print("[Phase6AZ] allocator/fence/budget policy unchanged")
    print("[Phase6AZ] EMIT RESULT: PASS")
    return 0

if __name__ == "__main__":
    raise SystemExit(main())
