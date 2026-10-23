#!/usr/bin/env python3
"""Phase 6AB: relocate HalBootSMCVideoMode (kernel DATA export ordinal 356).

Hardware Phase 6AA-B proved:
  * exact translated root sub_0020FAE0 executes on Xbox 360;
  * the 22.5 MiB retail graphics pool remains valid at 0x02880000;
  * execution advances beyond the old 0x0020FAE0 frontier;
  * the next stop is a 32-bit guest read from raw thunk 0x80000164.

0x164 == ordinal 356 == HalBootSMCVideoMode. Upstream classifies ordinal 356
as a DATA export, not a function, at XBOX_KERNEL_DATA_BASE + 0x98, initialized
to zero. Our kernel-data base is the same 0x0087E000, therefore the canonical
guest VA is 0x0087E098.

6AB changes only the startup DATA-thunk relocation and its invariants. The
Phase 6AA renderer closure, recovery helpers, graphics-pool allocator, timing
support and hard-stop policy are inherited unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B"
BUILD_TAG = "P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A"
HAL_BOOT_VIDEO_MODE_VA = 0x0087E098
COOKIE_OLD = "phase6aa_env_build_cookie"
COOKIE_NEW = "phase6ab_env_build_cookie"
COOKIE_NUM_OLD = "50366161"
COOKIE_NUM_NEW = "50366262"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AB] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AB] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--phase6aa-emitter", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    p6aa = load(args.phase6aa_emitter, "phase6ab_p6aa")
    base = load(args.base_emitter, "phase6ab_base")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6aa-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AB] cached Phase 6AA baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AA" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AB] cached Phase 6AA baseline identity mismatch")

    aa = manifest.get("phase6aa_post_graphics_pool_frontier") or {}
    if aa.get("root") != "0x0020FAE0":
        raise SystemExit("[Phase6AB] inherited Phase 6AA root proof drift")
    if aa.get("graphics_pool_model_inherited_unchanged") is not True:
        raise SystemExit("[Phase6AB] inherited graphics-pool proof drift")

    for marker in (
        BASE_TAG,
        "case 0x0020FAE0u:",
        "s_phase6aaRootEntered = 1;",
        "PASS: Phase 6AA retail graphics pool claim",
        "static uint32_t recomp_renderer_test_oom(uint32_t multisample)",
        "static void recomp_renderer_recovery_report(uint32_t result, uint32_t stage)",
        "PHASE4C_BOUNDARY_RENDERER_FATAL = 19",
        "static uint32_t phase4c_startup_data_va_for_ordinal(DWORD ordinal)",
        "case 326u: return 0x0087E040u; /* XeImageFileName ANSI_STRING */",
        "DWORD seen326 = 0u;",
        "if (ordinal == 326u) ++seen326;",
        "seen326 != 1u || relocated != (6u + seen41 + seen42)",
        "GUEST_READ32(0x0087E4A0u) != 3u ||",
        "startup data imports 40/41/42(optional)/156/164/322/324/326 relocated",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AB] inherited source marker changed: {marker}")

    # Upstream canonical layout:
    # XBOX_KERNEL_DATA_BASE 0x0087E000 + KDATA_HAL_BOOT_VIDEO_MODE 0x098.
    main_text = replace_unique(
        main_text,
        "    case 326u: return 0x0087E040u; /* XeImageFileName ANSI_STRING */\n"
        "    default:   return 0u;",
        "    case 326u: return 0x0087E040u; /* XeImageFileName ANSI_STRING */\n"
        "    case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */\n"
        "    default:   return 0u;",
        "startup data ordinal map",
    )

    main_text = replace_unique(
        main_text,
        "    if (!phase5bb_init_xe_image_file_name())\n"
        "        return 0;\n"
        "    DWORD relocated = 0u;",
        "    if (!phase5bb_init_xe_image_file_name())\n"
        "        return 0;\n"
        "\n"
        "    /* Ordinal 356 HalBootSMCVideoMode: canonical retail/default value 0. */\n"
        "    GUEST_WRITE32(0x0087E098u, 0u);\n"
        "    if (s_accessFault || GUEST_READ32(0x0087E098u) != 0u)\n"
        "    {\n"
        "        trace(\"FAIL: Phase 6AB HalBootSMCVideoMode kernel-data initialization invariant\");\n"
        "        return 0;\n"
        "    }\n"
        "    trace(\"PASS: Phase 6AB HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000\");\n"
        "\n"
        "    DWORD relocated = 0u;",
        "HalBootSMCVideoMode initialization",
    )

    main_text = replace_unique(
        main_text,
        "    DWORD seen326 = 0u;\n"
        "    DWORD sentinel;",
        "    DWORD seen326 = 0u;\n"
        "    DWORD seen356 = 0u;\n"
        "    DWORD sentinel;",
        "ordinal 356 count state",
    )

    main_text = replace_unique(
        main_text,
        "        if (ordinal == 326u) ++seen326;\n"
        "        ++relocated;",
        "        if (ordinal == 326u) ++seen326;\n"
        "        if (ordinal == 356u) ++seen356;\n"
        "        ++relocated;",
        "ordinal 356 count increment",
    )

    main_text = replace_unique(
        main_text,
        "        seen326 != 1u || relocated != (6u + seen41 + seen42))",
        "        seen326 != 1u || seen356 != 1u ||\n"
        "        relocated != (7u + seen41 + seen42))",
        "startup data count invariant",
    )

    main_text = replace_unique(
        main_text,
        "FAIL: startup data-thunk counts HalDiskCachePartitionCount=%u HalDiskModelNumber=%u HalDiskSerialNumber=%u KeTickCount=%u LaunchDataPage=%u XboxHardwareInfo=%u XboxKrnlVersion=%u XeImageFileName=%u total=%u",
        "FAIL: startup data-thunk counts HalDiskCachePartitionCount=%u HalDiskModelNumber=%u HalDiskSerialNumber=%u KeTickCount=%u LaunchDataPage=%u XboxHardwareInfo=%u XboxKrnlVersion=%u XeImageFileName=%u HalBootSMCVideoMode=%u total=%u",
        "startup data failure format",
    )

    main_text = replace_unique(
        main_text,
        "            (unsigned int)seen326,\n"
        "            (unsigned int)relocated);",
        "            (unsigned int)seen326,\n"
        "            (unsigned int)seen356,\n"
        "            (unsigned int)relocated);",
        "startup data failure args",
    )

    main_text = replace_unique(
        main_text,
        "        GUEST_READ32(0x0087E4A0u) != 3u ||",
        "        GUEST_READ32(0x0087E4A0u) != 3u ||\n"
        "        GUEST_READ32(0x0087E098u) != 0u ||",
        "HalBootSMCVideoMode readback invariant",
    )

    main_text = replace_unique(
        main_text,
        "PASS: startup data imports 40/41/42(optional)/156/164/322/324/326 relocated; disk_cache_parts=3 seen40=%u seen41=%u seen42=%u seen326=%u LaunchDataPage=NULL XeImageFileName=\\Device\\CdRom0\\default.xbe",
        "PASS: startup data imports 40/41/42(optional)/156/164/322/324/326/356 relocated; disk_cache_parts=3 seen40=%u seen41=%u seen42=%u seen326=%u seen356=%u LaunchDataPage=NULL HalBootSMCVideoMode=0 XeImageFileName=\\Device\\CdRom0\\default.xbe",
        "startup data success format",
    )

    # This argument sequence is unique in the success trace after the failure
    # trace gained its separate seen356 argument above.
    success_old = (
        "        (unsigned int)seen40,\n"
        "        (unsigned int)seen41,\n"
        "        (unsigned int)seen42,\n"
        "        (unsigned int)seen326);\n"
        "    trace(line);\n"
        "    return 1;"
    )
    success_new = (
        "        (unsigned int)seen40,\n"
        "        (unsigned int)seen41,\n"
        "        (unsigned int)seen42,\n"
        "        (unsigned int)seen326,\n"
        "        (unsigned int)seen356);\n"
        "    trace(line);\n"
        "    return 1;"
    )
    main_text = replace_unique(
        main_text, success_old, success_new, "startup data success args"
    )

    main_text = replace_unique(
        main_text,
        BASE_TAG,
        BUILD_TAG,
        "Phase 6AA build tag",
    )
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)
    env_text = env_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)

    main_text = (
        main_text
        .replace("P6AA POST-GFXPOOL SUMMARY:", "P6AB HALDATA SUMMARY:")
        .replace(
            "PHASE 6AA POST-GFXPOOL FRONTIER RESULT",
            "PHASE 6AB HAL BOOT VIDEO MODE RESULT",
        )
        .replace("PHASE 6AA", "PHASE 6AB")
        .replace("Phase 6AA", "Phase 6AB")
        .replace('"P6AA ', '"P6AB ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AA", "PHASE 6AB")
        .replace("Phase 6AA", "Phase 6AB")
    )

    required = (
        BUILD_TAG,
        "case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */",
        "GUEST_WRITE32(0x0087E098u, 0u);",
        "DWORD seen356 = 0u;",
        "if (ordinal == 356u) ++seen356;",
        "seen356 != 1u",
        "relocated != (7u + seen41 + seen42)",
        "GUEST_READ32(0x0087E098u) != 0u",
        "PASS: Phase 6AB HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000",
        "startup data imports 40/41/42(optional)/156/164/322/324/326/356 relocated",
        "case 0x0020FAE0u:",
        "s_phase6aaRootEntered = 1;",
        "PASS: Phase 6AB retail graphics pool claim",
        "static uint32_t recomp_renderer_test_oom(uint32_t multisample)",
        "static void recomp_renderer_recovery_report(uint32_t result, uint32_t stage)",
        "PHASE4C_BOUNDARY_RENDERER_FATAL = 19",
        "P6AB FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
        "P6AB FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
        "P6AB HALDATA SUMMARY:",
        "PHASE 6AB HAL BOOT VIDEO MODE RESULT",
        "phase6ab_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AB] generated main lost marker: {marker}")

    if "phase6aa_env_build_cookie" in main_text or "phase6aa_env_build_cookie" in env_text:
        raise SystemExit("[Phase6AB] stale Phase 6AA env cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = p6aa.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6AB",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6ab_hal_boot_video_mode"] = {
        "source_phase": "6AA",
        "phase6aa_hardware_pass": True,
        "phase6aa_hardware": {
            "graphics_pool_base": "0x02880000",
            "graphics_pool_size": "0x01680000",
            "root_crossed": "0x0020FAE0",
            "next_boundary": {
                "kind": "GUEST_FAULT",
                "caller": "0x0023A3CE",
                "target": "0x80000164",
                "ordinal": 356,
                "width": 4,
                "access": "READ",
                "ticks": 670797,
                "trace": 179929,
                "fault": 1,
            },
        },
        "data_export": {
            "ordinal": 356,
            "name": "HalBootSMCVideoMode",
            "kind": "ULONG data export",
            "kernel_data_base": "0x0087E000",
            "canonical_offset": "0x00000098",
            "guest_va": "0x0087E098",
            "initial_value": "0x00000000",
            "upstream_semantics": (
                "kernel DATA export, not function; canonical bridge initializes "
                "HalBootSMCVideoMode to zero"
            ),
        },
        "expected_retail_import_count": 1,
        "graphics_pool_model_inherited_unchanged": True,
        "phase6aa_renderer_support_inherited_unchanged": True,
        "source_layout": source_layout,
        "runtime_policy": (
            "relocate only hardware-proven ordinal-356 DATA export; preserve "
            "Phase 6AA translated renderer closure, graphics pool, reviewed "
            "recovery support, NV2A/platform/ABI/guest-fault hard stops"
        ),
    }
    (args.out_dir / "phase6ab-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print("[Phase6AB] HAL DATA EXPORT: ordinal 356 HalBootSMCVideoMode")
    print("[Phase6AB] Canonical guest VA : 0x0087E098")
    print("[Phase6AB] Canonical value    : 0x00000000")
    print("[Phase6AB] Retail import count: exactly 1 required at runtime")
    print("[Phase6AB] Phase 6AA renderer closure + graphics pool inherited unchanged")
    print("[Phase6AB] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
