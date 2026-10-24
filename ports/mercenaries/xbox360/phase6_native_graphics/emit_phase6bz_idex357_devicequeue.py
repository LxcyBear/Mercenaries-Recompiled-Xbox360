#!/usr/bin/env python3
"""Phase 6BZ: model ordinal-357 IdexChannelObject as a real empty IDE device queue.

6BY hardware proved the ordinal-357 relocation itself:
  thunk 0x002DBDBC -> 0x0087E0A0
and retail advanced beyond the old 0x8000018D low-KSEG fault.

The next live access showed the important semantic detail:
  0x0087E0A0 + 0x28 = 0x0087E0C8
  retail read DeviceQueue.DeviceListHead.Flink there and received zero.

Xbox IDE_CHANNEL_OBJECT embeds CurrentIrp at +0x20 and KDEVICE_QUEUE at +0x24;
KDEVICE_QUEUE.DeviceListHead is therefore +0x28. For host-backed synchronous
I/O there are no queued guest IRPs, so the truthful queue state is an empty
circular list:
  Type = DeviceQueueObject (0x14)
  Size = sizeof(KDEVICE_QUEUE) (0x0C)
  Busy = 0
  Flink = Blink = &DeviceListHead

This stage changes no KSEG mapping and no graphics/file/timing semantics.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BY-IDEX357-DATA-20261024-A"
BUILD_TAG = "P6BZ-IDEX357-DEVICEQUEUE-20261024-A"
COOKIE_OLD = "phase6by_env_build_cookie"
COOKIE_NEW = "phase6bz_env_build_cookie"

IDEX_BASE = 0x0087E0A0
IDEX_CURRENT_IRP = 0x0087E0C0
IDEX_QUEUE_HEADER = 0x0087E0C4
IDEX_LIST_HEAD = 0x0087E0C8
IDEX_LIST_BLINK = 0x0087E0CC
IDEX_QUEUE_HEADER_VALUE = 0x000C0014


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BZ] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BZ] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_idex_object(text: str) -> str:
    text = replace_unique(
        text,
        "    case 357u: return 0x0087E0A0u; /* IdexChannelObject PVOID export slot */",
        "    case 357u: return 0x0087E0A0u; /* IdexChannelObject IDE_CHANNEL_OBJECT */",
        "ordinal-357 startup DATA comment",
    )

    old_init = r'''    /* Ordinal 357 IdexChannelObject is a pointer-valued DATA export. */
    GUEST_WRITE32(0x0087E0A0u, 0x0087E0A4u);
    GUEST_WRITE32(0x0087E0A4u, 0x49444558u); /* 'IDEX' */
    if (s_accessFault ||
        GUEST_READ32(0x0087E0A0u) != 0x0087E0A4u ||
        GUEST_READ32(0x0087E0A4u) != 0x49444558u ||
        s_accessFault)
    {
        trace("FAIL: Phase 6BY IdexChannelObject guest-data initialization invariant");
        return 0;
    }
    trace("PASS: Phase 6BY IdexChannelObject initialized ordinal=357 pointer_slot=0087E0A0 object=0087E0A4 marker=49444558");
'''
    new_init = r'''    /*
     * Ordinal 357 exports IDE_CHANNEL_OBJECT directly. The title's live
     * file-close path walks DeviceQueue.DeviceListHead at object+0x28.
     * Host-backed synchronous I/O has no guest IRPs queued, so initialize an
     * honest empty KDEVICE_QUEUE circular list.
     */
    GUEST_WRITE32(0x0087E0A0u, 0u);
    GUEST_WRITE32(0x0087E0A4u, 0u);
    GUEST_WRITE32(0x0087E0A8u, 0u);
    GUEST_WRITE32(0x0087E0ACu, 0u);
    GUEST_WRITE32(0x0087E0B0u, 0u);
    GUEST_WRITE32(0x0087E0B4u, 0u);
    GUEST_WRITE32(0x0087E0B8u, 0u);
    GUEST_WRITE32(0x0087E0BCu, 0u);
    GUEST_WRITE32(0x0087E0C0u, 0u);          /* CurrentIrp */
    GUEST_WRITE32(0x0087E0C4u, 0x000C0014u); /* Type=0x14 Size=0x0C Busy=0 */
    GUEST_WRITE32(0x0087E0C8u, 0x0087E0C8u); /* DeviceListHead.Flink */
    GUEST_WRITE32(0x0087E0CCu, 0x0087E0C8u); /* DeviceListHead.Blink */
    if (s_accessFault ||
        GUEST_READ32(0x0087E0C0u) != 0u ||
        GUEST_READ32(0x0087E0C4u) != 0x000C0014u ||
        GUEST_READ32(0x0087E0C8u) != 0x0087E0C8u ||
        GUEST_READ32(0x0087E0CCu) != 0x0087E0C8u ||
        s_accessFault)
    {
        trace("FAIL: Phase 6BZ IdexChannelObject DeviceQueue initialization invariant");
        return 0;
    }
    trace("PASS: Phase 6BZ IdexChannelObject initialized ordinal=357 base=0087E0A0 queue=0087E0C4 list=0087E0C8 flink=0087E0C8 blink=0087E0C8");
'''
    text = replace_unique(text, old_init, new_init, "IdexChannelObject initialization block")

    old_readback = r'''    if (GUEST_READ32(0x002DBDBCu) != 0x0087E0A0u ||
        GUEST_READ32(0x0087E0A0u) != 0x0087E0A4u ||
        GUEST_READ32(0x0087E0A4u) != 0x49444558u ||
        s_accessFault)
    {
        trace("FAIL: Phase 6BY IdexChannelObject thunk/pointer/object readback invariant");
        return 0;
    }
    trace("PASS: Phase 6BY IdexChannelObject thunk slot 002DBDBC -> 0087E0A0 -> 0087E0A4");
'''
    new_readback = r'''    if (GUEST_READ32(0x002DBDBCu) != 0x0087E0A0u ||
        GUEST_READ32(0x0087E0C4u) != 0x000C0014u ||
        GUEST_READ32(0x0087E0C8u) != 0x0087E0C8u ||
        GUEST_READ32(0x0087E0CCu) != 0x0087E0C8u ||
        s_accessFault)
    {
        trace("FAIL: Phase 6BZ IdexChannelObject thunk/DeviceQueue readback invariant");
        return 0;
    }
    trace("PASS: Phase 6BZ IdexChannelObject thunk slot 002DBDBC -> object 0087E0A0 empty DeviceListHead=0087E0C8");
'''
    text = replace_unique(text, old_readback, new_readback, "Idex readback block")

    old_invariant = (
        "        GUEST_READ32(0x0087E0A0u) != 0x0087E0A4u ||\n"
        "        GUEST_READ32(0x0087E0A4u) != 0x49444558u ||"
    )
    new_invariant = (
        "        GUEST_READ32(0x0087E0C4u) != 0x000C0014u ||\n"
        "        GUEST_READ32(0x0087E0C8u) != 0x0087E0C8u ||\n"
        "        GUEST_READ32(0x0087E0CCu) != 0x0087E0C8u ||"
    )
    text = replace_unique(text, old_invariant, new_invariant, "kernel-data Idex invariant")

    text = replace_unique(
        text,
        "IdexChannelObject=0087E0A4",
        "IdexChannelObject=0087E0A0 queue_head=0087E0C8",
        "startup success Idex text",
    )

    # The 6BY trace landed on exactly the field retail wants: object+0x28.
    text = replace_unique(
        text,
        "P6BY IDEX LIVE THUNK: slot=002DBDBC value=%08X expected_slot=0087E0A0",
        "P6BZ IDEX LIVE BASE: slot=002DBDBC object_base=%08X expected_base=0087E0A0",
        "live Idex base trace",
    )
    text = replace_unique(
        text,
        "P6BY IDEX LIVE OBJECT: pointer_slot=%08X object=%08X expected_object=0087E0A4",
        "P6BZ IDEX QUEUE HEAD: list_head=%08X flink=%08X expected_self=0087E0C8",
        "live DeviceListHead trace",
    )

    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6bz_base")
    p6bl = load(args.phase6bl_emitter, "phase6bz_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6by-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BZ] cached Phase 6BY input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BY" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BZ] cached Phase 6BY identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BZ] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "case 357u: return 0x0087E0A0u; /* IdexChannelObject PVOID export slot */",
        "GUEST_WRITE32(0x0087E0A0u, 0x0087E0A4u);",
        "GUEST_WRITE32(0x0087E0A4u, 0x49444558u);",
        "P6BY IDEX LIVE THUNK:",
        "P6BY IDEX LIVE OBJECT:",
        "idexThunkBefore != 0x80000165u",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BZ] inherited 6BY marker missing: {marker}")

    main_text = patch_idex_object(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BZ model ordinal-357 IdexChannelObject as direct IDE_CHANNEL_OBJECT with empty KDEVICE_QUEUE circular DeviceListHead at +0x28; preserve low-KSEG fence, guest IRQL, FILE_OBJECT sentinel, file/delay/GPU semantics, allocator geometry and 8M budget",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BY", "PHASE 6BZ")
        .replace("Phase 6BY", "Phase 6BZ")
        .replace('"P6BY ', '"P6BZ ')
    )
    env_text = (
        env_text.replace("PHASE 6BY", "PHASE 6BZ")
        .replace("Phase 6BY", "Phase 6BZ")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 357u: return 0x0087E0A0u; /* IdexChannelObject IDE_CHANNEL_OBJECT */",
        "GUEST_WRITE32(0x0087E0C4u, 0x000C0014u)",
        "GUEST_WRITE32(0x0087E0C8u, 0x0087E0C8u)",
        "GUEST_WRITE32(0x0087E0CCu, 0x0087E0C8u)",
        "PASS: Phase 6BZ IdexChannelObject initialized ordinal=357 base=0087E0A0",
        "P6BZ IDEX LIVE BASE:",
        "P6BZ IDEX QUEUE HEAD:",
        "expected_self=0087E0C8",
        "idexThunkBefore != 0x80000165u",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6BZ] generated source lost marker: {marker}")

    expected_env = (
        env_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6BY", "PHASE 6BZ")
        .replace("Phase 6BY", "Phase 6BZ")
    )
    if env_text != expected_env:
        raise SystemExit(
            "[Phase6BZ] phase5_env.cpp changed beyond expected tag/cookie renames"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BZ",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bz_idex357_devicequeue"] = {
        "source_phase": "6BY",
        "phase6by_hardware": {
            "data_thunk_fixup_old": "0x80000165",
            "data_thunk_fixup_new": "0x0087E0A0",
            "live_thunk_value": "0x0087E0A0",
            "device_list_head_access": "0x0087E0C8",
            "device_list_head_offset": "0x28",
            "observed_flink_before_fix": "0x00000000",
            "old_low_kseg_fault_cleared": True,
            "new_fault_address": "0xFFFFFFFF",
            "advanced_vas": [
                "0x0022AC9E",
                "0x0022ACA1",
                "0x0022ACD1",
            ],
            "xapi_return": 0,
        },
        "device_queue_model": {
            "object_base": "0x0087E0A0",
            "current_irp_va": "0x0087E0C0",
            "queue_header_va": "0x0087E0C4",
            "queue_header_value": "0x000C0014",
            "device_list_head_va": "0x0087E0C8",
            "flink": "0x0087E0C8",
            "blink": "0x0087E0C8",
            "empty_circular_list": True,
            "host_backed_sync_io_has_no_guest_irps": True,
        },
        "translated_membership_changed": False,
        "low_kseg_fence_changed": False,
        "phase5_env_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bz-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BZ] 6BY hardware: ordinal-357 relocation PASS; old 8000018D fault cleared")
    print("[Phase6BZ] hardware field: IdexChannelObject+0x28 = DeviceQueue.DeviceListHead")
    print("[Phase6BZ] Xbox queue model: Type=14 Size=0C Busy=0")
    print("[Phase6BZ] empty circular list: Flink=Blink=0087E0C8")
    print("[Phase6BZ] low-KSEG ambiguity fence unchanged")
    print("[Phase6BZ] translated membership unchanged")
    print("[Phase6BZ] all 6BY file/sentinel/IRQL/delay/GPU/allocator/8M-budget invariants inherited")
    print("[Phase6BZ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
