#!/usr/bin/env python3
"""Phase 6CD: long-run 32M execution window with low-noise hot-region profiling.

6CC crossed the intentional manual PblMath frontier and ran fault-free until
the artificial 8,000,000-tick watchdog. It loaded and processed RadioMsg.ini,
repeated the file/IDEX/IRQL path successfully, executed manual PblMath sin/cos,
and stopped only on PHASE4C_BOUNDARY_BUDGET with fault=0.

6CD changes no translated membership or subsystem semantics. It:
  * raises the execution budget 8M -> 32M;
  * reduces packed broad-sweep progress logging from every 256 dispatches to
    every 4096 (first eight still logged);
  * samples execution at 4M intervals;
  * counts coarse hot regions observed in the 6CC terminal VA ring.

All genuine direct/ICALL/platform/guest-fault fences remain authoritative.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BASE_TAG = "P6CC-DIRECT-FRONTIER-001F9D70-20261024-A"
BUILD_TAG = "P6CD-LONGRUN32M-20261025-A"
COOKIE_OLD = "phase6cc_env_build_cookie"
COOKIE_NEW = "phase6cd_env_build_cookie"
OLD_BUDGET = "#define PHASE4C_EXEC_BUDGET 8000000u"
NEW_BUDGET = "#define PHASE4C_EXEC_BUDGET 32000000u"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CD] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_dispatch_logging(text: str) -> str:
    old_icall = """    if (s_phase5bcPackedIcallDispatchCount <= 8u ||
        (s_phase5bcPackedIcallDispatchCount >= 1268u &&
         s_phase5bcPackedIcallDispatchCount <= 1304u) ||
        (s_phase5bcPackedIcallDispatchCount & 0xFFu) == 0u)
"""
    new_icall = """    if (s_phase5bcPackedIcallDispatchCount <= 8u ||
        (s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u)
"""
    text = replace_once(
        text, old_icall, new_icall, "quiet ICALL dispatch condition"
    )

    old_direct = """        if (s_phase5bcPackedDirectDispatchCount <= 8u ||
            (s_phase5bcPackedDirectDispatchCount >= 1008u &&
             s_phase5bcPackedDirectDispatchCount <= 1056u) ||
            (s_phase5bcPackedDirectDispatchCount & 0xFFu) == 0u)
"""
    new_direct = """        if (s_phase5bcPackedDirectDispatchCount <= 8u ||
            (s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u)
"""
    text = replace_once(
        text, old_direct, new_direct, "quiet DIRECT dispatch condition"
    )
    return text


def patch_budget_profile(text: str) -> str:
    state_anchor = """static DWORD s_phase6awVaRing[32];
static DWORD s_phase6awVaRingPos = 0u;
static DWORD s_phase6awVaRingCount = 0u;
"""
    state_new = state_anchor + """static DWORD s_phase6cdHot1EFCount = 0u;
static DWORD s_phase6cdHot1F29Count = 0u;
static DWORD s_phase6cdHot208F40Count = 0u;
static DWORD s_phase6cdHot194150Count = 0u;
static DWORD s_phase6cdHot23A3CECount = 0u;
static DWORD s_phase6cdOtherTickCount = 0u;
"""
    text = replace_once(text, state_anchor, state_new, "VA ring state")

    ring_tick = """    s_phase6awVaRing[s_phase6awVaRingPos] = va;
    s_phase6awVaRingPos = (s_phase6awVaRingPos + 1u) & 31u;
    if (s_phase6awVaRingCount < 32u)
        ++s_phase6awVaRingCount;
"""
    ring_tick_new = ring_tick + """
    if ((va & 0xFFFF0000u) == 0x001E0000u)
        ++s_phase6cdHot1EFCount;
    else if (va >= 0x001F2900u && va < 0x001F2B00u)
        ++s_phase6cdHot1F29Count;
    else if (va == 0x00208F40u)
        ++s_phase6cdHot208F40Count;
    else if (va == 0x00194150u)
        ++s_phase6cdHot194150Count;
    else if (va == 0x0023A3CEu)
        ++s_phase6cdHot23A3CECount;
    else
        ++s_phase6cdOtherTickCount;
"""
    text = replace_once(text, ring_tick, ring_tick_new, "budget hot-profile hook")

    old_samples = """    if (s_phase4cBlockTicks == 2000000u ||
        s_phase4cBlockTicks == 4000000u ||
        s_phase4cBlockTicks == 6000000u ||
        s_phase4cBlockTicks == 8000000u)
"""
    new_samples = """    if (s_phase4cBlockTicks == 4000000u ||
        s_phase4cBlockTicks == 8000000u ||
        s_phase4cBlockTicks == 12000000u ||
        s_phase4cBlockTicks == 16000000u ||
        s_phase4cBlockTicks == 20000000u ||
        s_phase4cBlockTicks == 24000000u ||
        s_phase4cBlockTicks == 28000000u ||
        s_phase4cBlockTicks == 32000000u)
"""
    text = replace_once(text, old_samples, new_samples, "spin sample schedule")

    dump_anchor = """static void phase6aw_dump_va_ring(void)
"""
    dump_pos = text.find(dump_anchor)
    if dump_pos < 0:
        raise SystemExit("[Phase6CD] inherited VA-ring dump helper missing")

    macro_anchor = (
        "#define PHASE4C_BUDGET_TICK(va) \\\n"
        "    do { phase4c_budget_tick((DWORD)(va)); } while (0)\n"
    )
    macro_pos = text.find(macro_anchor, dump_pos)
    if macro_pos < 0:
        raise SystemExit("[Phase6CD] budget macro anchor missing")

    profile_helper = r'''static void phase6cd_dump_hot_profile(void)
{
    char line[448];
    sprintf(
        line,
        "P6CD HOT PROFILE: total=%u hot_001E=%u hot_001F29=%u exact_00208F40=%u exact_00194150=%u exact_0023A3CE=%u other=%u",
        (unsigned int)s_phase4cBlockTicks,
        (unsigned int)s_phase6cdHot1EFCount,
        (unsigned int)s_phase6cdHot1F29Count,
        (unsigned int)s_phase6cdHot208F40Count,
        (unsigned int)s_phase6cdHot194150Count,
        (unsigned int)s_phase6cdHot23A3CECount,
        (unsigned int)s_phase6cdOtherTickCount);
    trace(line);
}

'''
    text = text[:macro_pos] + profile_helper + text[macro_pos:]

    call_anchor = "    phase6aw_dump_va_ring();\n"
    text = replace_once(
        text,
        call_anchor,
        call_anchor + "    phase6cd_dump_hot_profile();\n",
        "final VA-ring dump call",
    )
    return text


def patch_main(text: str) -> str:
    text = replace_once(text, OLD_BUDGET, NEW_BUDGET, "execution budget")
    text = patch_dispatch_logging(text)
    text = patch_budget_profile(text)

    text = replace_once(text, BASE_TAG, BUILD_TAG, "build tag")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)

    old_policy = (
        "Policy: Phase 6CC route hardware-proven DIRECT_FRONTIER 0023A3CE -> "
        "001F9D70 through the maintained source-matched manual PblMath 8192-entry "
        "trig family (001F9D70/001F9DA0/001F9DE0); preserve 6CB balanced FILE_OBJECT "
        "release, all graphics/file/fence/allocator semantics and 8M budget"
    )
    new_policy = (
        "Policy: Phase 6CD long-run continuation after fault-free 6CC budget stop; "
        "preserve translated membership/manual PblMath/graphics/file/IDEX/IRQL/allocator "
        "semantics, raise watchdog 8M->32M, reduce broad-sweep log cadence to 4096, "
        "and profile recurring runtime regions while all genuine hard fences remain armed"
    )
    text = replace_once(text, old_policy, new_policy, "runtime policy")

    text = (
        text.replace("PHASE 6CC", "PHASE 6CD")
        .replace("Phase 6CC", "Phase 6CD")
        .replace('"P6CC ', '"P6CD ')
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        NEW_BUDGET,
        "P6CD HOT PROFILE:",
        "s_phase4cBlockTicks == 32000000u",
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
        "(s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u",
        "phase6cd_dump_hot_profile();",
        "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CD] patched source lost marker: {marker}")

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6CD] stale 6CC env cookie remains")
    return text


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CC", "PHASE 6CD")
        .replace("Phase 6CC", "Phase 6CD")
    )
    if COOKIE_NEW not in text:
        raise SystemExit("[Phase6CD] env cookie rewrite did not land")
    if COOKIE_OLD in text:
        raise SystemExit("[Phase6CD] stale 6CC env cookie remains in env")
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
        args.base_dir / "phase6cc-manifest.json",
        args.base_dir / "translated_shards",
    )
    for path in required:
        if not path.exists():
            raise SystemExit(f"[Phase6CD] missing cached 6CC input: {path}")

    manifest = json.loads(
        (args.base_dir / "phase6cc-manifest.json").read_text(encoding="utf-8")
    )
    if manifest.get("phase") != "6CC" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CD] cached Phase 6CC identity mismatch")

    p6cc = manifest.get("phase6cc_direct_frontier", {})
    if (
        p6cc.get("root") != "0x001F9D70"
        or p6cc.get("root_is_declared_manual_function") is not True
        or p6cc.get("translated_membership_changed") is not False
        or p6cc.get("execution_budget") != 8000000
    ):
        raise SystemExit("[Phase6CD] 6CC manual-root inheritance gate failed")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    shard_dir = args.out_dir / "translated_shards"
    if shard_dir.exists():
        shutil.rmtree(shard_dir)
    shutil.copytree(args.base_dir / "translated_shards", shard_dir)

    # 6CD changes harness/support code only. The translated body shards are
    # therefore inherited byte-for-byte from 6CC; patch both the build-facing
    # wrapper and monolithic cache so the next phase sees the same semantics.
    wrapper_text = patch_main(
        (args.base_dir / "main.cpp").read_text(encoding="utf-8")
    )
    mono_text = patch_main(
        (args.base_dir / "main_monolithic.cpp").read_text(encoding="utf-8")
    )
    env_text = patch_env(
        (args.base_dir / "phase5_env.cpp").read_text(encoding="utf-8")
    )

    (args.out_dir / "main.cpp").write_text(wrapper_text, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    inherited_layout = manifest.get("phase6cc_direct_frontier", {}).get(
        "source_layout", {}
    )
    layout = dict(inherited_layout) if isinstance(inherited_layout, dict) else {}
    layout["translated_shards_reused_byte_for_byte"] = True
    layout["shard_count"] = len(list(shard_dir.glob("*.inl")))

    manifest.update(
        {
            "phase": "6CD",
            "build_tag": BUILD_TAG,
        }
    )
    manifest["phase6cd_longrun32m"] = {
        "source_phase": "6CC",
        "phase6cc_hardware": {
            "boundary_kind": "BUDGET",
            "boundary_target": "0x001EF672",
            "ticks": 8000001,
            "trace": 763936,
            "fault": 0,
            "manual_pbl_sin_calls": 24,
            "manual_pbl_cos_calls": 24,
            "obref_calls": 2,
            "obfderef_successes": 2,
            "synthetic_outstanding": 0,
            "guest_irql_current": 0,
            "direct_dispatches": 2160,
            "icall_dispatches": 552111,
            "xapi_return": 0,
        },
        "old_budget_ticks": 8000000,
        "new_budget_ticks": 32000000,
        "sample_ticks": [
            4000000,
            8000000,
            12000000,
            16000000,
            20000000,
            24000000,
            28000000,
            32000000,
        ],
        "dispatch_log_stride_old": 256,
        "dispatch_log_stride_new": 4096,
        "hot_profile": {
            "range_001e": "0x001E0000-0x001EFFFF",
            "range_001f29": "0x001F2900-0x001F2AFF",
            "exact_targets": [
                "0x00208F40",
                "0x00194150",
                "0x0023A3CE",
            ],
        },
        "translated_membership_changed": False,
        "manual_pbl_semantics_changed": False,
        "phase5_env_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "hard_fences_changed": False,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cd-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CD] 6CC hardware: fault-free artificial BUDGET stop at 8,000,001")
    print("[Phase6CD] execution budget: 8,000,000 -> 32,000,000")
    print("[Phase6CD] broad-sweep logging: every 256 -> every 4096 dispatches")
    print("[Phase6CD] samples: 4M/8M/12M/16M/20M/24M/28M/32M")
    print("[Phase6CD] coarse hot-region profiler armed")
    print("[Phase6CD] translated membership changes: 0")
    print("[Phase6CD] subsystem/allocator/fence semantic changes: 0")
    print("[Phase6CD] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
