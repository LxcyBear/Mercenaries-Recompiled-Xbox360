#!/usr/bin/env python3
"""Phase 6AI-D: restore the retail internal D3D device-global side effect.

6AH-D hardware proved:
  * native Xenos CreateDevice handoff still passes;
  * exact D3D roots 0x00290895 and 0x0028E700 execute;
  * the maintained D3D sync checkpoints execute;
  * the next boundary is READ32 0x80000004 (orange).

6AI-C source forensics proved that sub_0028E700 contains no literal [eax+4]
read. Its first device-internal access is GUEST_READ32(esi + 0x1C20).

Upstream Mercenaries host code treats 0x00299378 as the current guest D3D
device pointer, while the successful CreateDevice identity is 0x00299380.
The Phase-6AF handoff published 0x00299380 only through the game-facing output
pointer 0x007AD604. This phase restores the missing internal-XDK side effect:

    *(uint32_t *)0x00299378 = 0x00299380

The native Xenos device remains the physical renderer. No KSEG fence, NV2A
MMIO, VRAM, allocator, or guest-memory policy is relaxed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AH-D3D-SYNC-0028E700-20261023-D"
BUILD_TAG = "P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D"
COOKIE_OLD = "phase6ah_env_build_cookie"
COOKIE_NEW = "phase6ai_env_build_cookie"

INTERNAL_DEVICE_GLOBAL = 0x00299378
GUEST_DEVICE = 0x00299380
ROOT = 0x0028E700
ROOT_FIELD_OFFSET = 0x1C20
EXPECTED_FIELD_ADDRESS = GUEST_DEVICE + ROOT_FIELD_OFFSET
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AI] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AI] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AI] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AI] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + policy + '");' + text[line_end:]


def install_state(main_text: str) -> str:
    marker = "static int s_phase6ahRootEntered;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AI] inherited Phase 6AH root-state marker missing")

    state = r'''static uint32_t s_phase6aiInternalDevicePublishCount;
static uint32_t s_phase6aiInternalDeviceLastValue;
static uint32_t s_phase6aiInternalDeviceReadback;
static uint32_t s_phase6aiRootCheckpointCount;
static uint32_t s_phase6aiRootThis;
static uint32_t s_phase6aiRootInternalGlobal;
static uint32_t s_phase6aiRootFieldAddress;

static void phase6ai_d3d_root_checkpoint(uint32_t thisVa)
{
    char line[224];

    ++s_phase6aiRootCheckpointCount;
    s_phase6aiRootThis = thisVa;
    s_phase6aiRootInternalGlobal = GUEST_READ32(0x00299378u);
    s_phase6aiRootFieldAddress = thisVa + 0x1C20u;

    if (s_accessFault)
        return;

    sprintf(
        line,
        "P6AI D3D ROOT INPUT: calls=%u this=%08X internal=%08X field1C20=%08X",
        (unsigned int)s_phase6aiRootCheckpointCount,
        (unsigned int)s_phase6aiRootThis,
        (unsigned int)s_phase6aiRootInternalGlobal,
        (unsigned int)s_phase6aiRootFieldAddress);
    trace(line);
}

'''
    return main_text.replace(marker, state + marker, 1)


def patch_createdevice_publish(main_text: str) -> str:
    old = r'''    s_phase6afGuestDevice = 0x00299380u;
    GUEST_WRITE32(out, s_phase6afGuestDevice);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, out, c);
        return;
    }

    ++s_phase6afCreateDeviceBridgeCount;
'''

    new = r'''    s_phase6afGuestDevice = 0x00299380u;
    GUEST_WRITE32(out, s_phase6afGuestDevice);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, out, c);
        return;
    }

    /*
     * The retail XDK also maintains its current internal D3D device pointer at
     * 0x00299378. Upstream Mercenaries host services dereference this exact
     * global for device fields. Phase 6AF intentionally modeled only the
     * game-facing CreateDevice output; deeper D3D execution now proves this
     * second side effect is required.
     */
    GUEST_WRITE32(0x00299378u, s_phase6afGuestDevice);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x00299378u, c);
        return;
    }

    s_phase6aiInternalDeviceReadback = GUEST_READ32(0x00299378u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x00299378u, c);
        return;
    }
    if (s_phase6aiInternalDeviceReadback != s_phase6afGuestDevice)
    {
        trace("Phase 6AI internal D3D device global readback mismatch");
        phase4c_escape(PHASE4C_BOUNDARY_RENDERER_FATAL, 0x00299378u, c);
        return;
    }

    ++s_phase6aiInternalDevicePublishCount;
    s_phase6aiInternalDeviceLastValue = s_phase6afGuestDevice;

    ++s_phase6afCreateDeviceBridgeCount;
'''

    return replace_unique(
        main_text,
        old,
        new,
        "CreateDevice guest/internal device publication block",
    )


def instrument_root_input(main_text: str, base) -> str:
    signature = "static void sub_0028E700(void)"
    masked = base.mask_noncode(main_text)
    pos = masked.find(signature)
    if pos < 0:
        raise SystemExit("[Phase6AI] exact sub_0028E700 body missing")
    if masked.find(signature, pos + 1) >= 0:
        raise SystemExit("[Phase6AI] multiple sub_0028E700 definitions found")

    brace = masked.find("{", pos, pos + len(signature) + 8)
    if brace < 0:
        raise SystemExit("[Phase6AI] sub_0028E700 opening brace missing")
    end = base.closing_brace(masked, brace)

    body = main_text[pos:end]
    old = "    esi = ecx;\n    eax = GUEST_READ32(esi + 8);"
    new = (
        "    esi = ecx;\n"
        "    phase6ai_d3d_root_checkpoint(esi);\n"
        "    eax = GUEST_READ32(esi + 8);"
    )
    if body.count(old) != 1:
        raise SystemExit("[Phase6AI] sub_0028E700 root-input shape drift")

    body = body.replace(old, new, 1)
    return main_text[:pos] + body + main_text[end:]


def reset_state(main_text: str) -> str:
    marker = "    s_phase6ahRootEntered = 0;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AI] inherited Phase 6AH reset marker missing")

    extra = (
        "    s_phase6aiInternalDevicePublishCount = 0u;\n"
        "    s_phase6aiInternalDeviceLastValue = 0u;\n"
        "    s_phase6aiInternalDeviceReadback = 0u;\n"
        "    s_phase6aiRootCheckpointCount = 0u;\n"
        "    s_phase6aiRootThis = 0u;\n"
        "    s_phase6aiRootInternalGlobal = 0u;\n"
        "    s_phase6aiRootFieldAddress = 0u;\n"
    )
    return main_text.replace(marker, extra + marker, 1)


def install_result(main_text: str) -> str:
    # Keep the old 6AH result as a historical sub-proof and install a new,
    # independent result for the internal-device publication repair.
    old_result = "PHASE 6AH D3D SATURATION RESULT: %s"
    if old_result not in main_text:
        raise SystemExit("[Phase6AI] inherited 6AH result marker missing")
    main_text = main_text.replace(
        old_result,
        "P6AI PRIOR 6AH D3D SATURATION RESULT: %s",
        1,
    )

    marker = "P6AH D3D SYNC CHECKPOINT: calls=%u last_phase=%u"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AI] inherited D3D sync summary marker missing")

    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 3200:
        raise SystemExit("[Phase6AI] could not locate D3D sync summary statement")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AI INTERNAL D3D DEVICE: publishes=%u value=%08X readback=%08X root_calls=%u this=%08X internal=%08X field1C20=%08X",\n'
        f'{indent}    (unsigned int)s_phase6aiInternalDevicePublishCount,\n'
        f'{indent}    (unsigned int)s_phase6aiInternalDeviceLastValue,\n'
        f'{indent}    (unsigned int)s_phase6aiInternalDeviceReadback,\n'
        f'{indent}    (unsigned int)s_phase6aiRootCheckpointCount,\n'
        f'{indent}    (unsigned int)s_phase6aiRootThis,\n'
        f'{indent}    (unsigned int)s_phase6aiRootInternalGlobal,\n'
        f'{indent}    (unsigned int)s_phase6aiRootFieldAddress);\n'
        f'{indent}trace(line);\n'
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "PHASE 6AI INTERNAL D3D DEVICE RESULT: %s",\n'
        f'{indent}    (s_phase6aiInternalDevicePublishCount != 0u &&\n'
        f'{indent}     s_phase6aiInternalDeviceLastValue == 0x00299380u &&\n'
        f'{indent}     s_phase6aiInternalDeviceReadback == 0x00299380u &&\n'
        f'{indent}     s_phase6aiRootCheckpointCount != 0u &&\n'
        f'{indent}     s_phase6aiRootInternalGlobal == 0x00299380u &&\n'
        f'{indent}     s_phase6ahRootEntered &&\n'
        f'{indent}     s_phase6afCreateDeviceBridgeCount != 0u) ? "PASS" : "FAIL");\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AI] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AI] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AI] translated body contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AI] translated function opening brace missing")
        function_ends.append(base.closing_brace(masked, open_index))

    cuts = []
    chunk_start = 0
    last_end = 0
    for end in function_ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cuts.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cuts or cuts[-1] != last_end:
        cuts.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cuts):
        if end <= start:
            continue
        name = f"phase6ai_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append(
            {
                "name": name,
                "chars": len(payload),
                "lines": payload.count("\n") + 1,
            }
        )
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AI] shard writer did not consume translated body")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n' for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]

    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8") for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AI] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6ai_",
        "shard_count": len(shards),
        "body_chars": len(body),
        "body_lines": body.count("\n") + 1,
        "wrapper_chars": len(wrapper),
        "wrapper_lines": wrapper.count("\n") + 1,
        "shards": shards,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ah-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AI] cached Phase 6AH-D baseline missing: {path}")

    base = load(args.base_emitter, "phase6ai_base")
    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AH" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AI] cached Phase 6AH-D baseline identity mismatch")

    ah = manifest.get("phase6ah_d3d_saturation") or {}
    if (
        ah.get("root") != "0x0028E700"
        or ah.get("native_createdevice_handoff_inherited_unchanged") is not True
        or ah.get("d3d_sync_checkpoint_support", {}).get("required_for_root") is not True
    ):
        raise SystemExit("[Phase6AI] inherited Phase 6AH model drift")

    required_base = (
        BASE_TAG,
        "static void sub_0028CAA0(void)",
        "static void sub_0028E700(void)",
        "s_phase6afGuestDevice = 0x00299380u;",
        "GUEST_WRITE32(out, s_phase6afGuestDevice);",
        "static int s_phase6ahRootEntered;",
        "static uint32_t s_phase6ahD3DSyncCheckpointCalls;",
        "PHASE 6AH D3D SATURATION RESULT: %s",
        COOKIE_OLD,
    )
    for marker in required_base:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AI] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = patch_createdevice_publish(main_text)
    main_text = instrument_root_input(main_text, base)
    main_text = reset_state(main_text)
    main_text = install_result(main_text)

    policy = (
        "Policy: inherit 6AH-D; publish retail internal D3D device global "
        "00299378=00299380 during proven CreateDevice handoff; keep translated "
        "D3D, KSEG fence, NV2A/MMIO/VRAM, ABI and guest-fault fences hard"
    )
    if len(policy) > 240:
        raise SystemExit("[Phase6AI] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    # Advance user-visible phase labels after the independent result is installed.
    main_text = (
        main_text
        .replace("PHASE 6AH", "PHASE 6AI")
        .replace("Phase 6AH", "Phase 6AI")
        .replace('"P6AH ', '"P6AI ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AH", "PHASE 6AI")
        .replace("Phase 6AH", "Phase 6AI")
    )

    required = (
        BUILD_TAG,
        "GUEST_WRITE32(0x00299378u, s_phase6afGuestDevice);",
        "s_phase6aiInternalDeviceReadback = GUEST_READ32(0x00299378u);",
        "phase6ai_d3d_root_checkpoint(esi);",
        "P6AI D3D ROOT INPUT:",
        "P6AI INTERNAL D3D DEVICE:",
        "PHASE 6AI INTERNAL D3D DEVICE RESULT: %s",
        "s_phase6aiRootInternalGlobal == 0x00299380u",
        "P6AI PRIOR 6AH D3D SATURATION RESULT: %s",
        COOKIE_NEW,
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AI] generated source lost marker: {marker}")

    if COOKIE_OLD in main_text or COOKIE_OLD in env_text:
        raise SystemExit("[Phase6AI] stale Phase 6AH cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6AI",
            "build_tag": BUILD_TAG,
        }
    )
    manifest["phase6ai_internal_d3d_device_global"] = {
        "source_phase": "6AH",
        "phase6ah_hardware_pass": True,
        "phase6ah_hardware": {
            "native_createdevice": "PASS",
            "prior_root_0x00290895": "PASS",
            "root_0x0028E700_entries": 2,
            "d3d_sync_checkpoint_calls": 6,
            "d3d_sync_last_phase": 3,
            "authoritative_result": "PASS",
            "next_boundary": {
                "kind": "GUEST_FAULT",
                "access": "READ",
                "width": 4,
                "guest": "0x80000004",
                "caller": "0x0023A3CE",
                "esp": "0x008BF974",
                "saved_esp": "0x008BF974",
            },
        },
        "forensic": {
            "root": "0x0028E700",
            "first_internal_read": "GUEST_READ32(esi + 0x1C20)",
            "internal_device_global": "0x00299378",
            "guest_device_identity": "0x00299380",
            "expected_field_1c20_address": f"0x{EXPECTED_FIELD_ADDRESS:08X}",
            "kseg_first_page_remains_fenced": True,
        },
        "repair": {
            "createdevice_public_output": "0x007AD604",
            "createdevice_internal_global": "0x00299378",
            "published_value": "0x00299380",
            "readback_required": True,
            "fabricate_d3d_object": False,
            "relax_kseg_fence": False,
            "nv2a_mmio_writes": False,
        },
        "authoritative_result": (
            "publish/readback 0x00299378==0x00299380 && root sees same internal "
            "device pointer && inherited CreateDevice/root execution remains live"
        ),
        "source_layout": source_layout,
    }

    (args.out_dir / "phase6ai-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AI] INTERNAL D3D DEVICE GLOBAL REPAIR: READY")
    print("[Phase6AI] Public CreateDevice output : 0x007AD604 -> 0x00299380")
    print("[Phase6AI] Internal D3D device global : 0x00299378 -> 0x00299380")
    print(f"[Phase6AI] Expected root +0x1C20    : 0x{EXPECTED_FIELD_ADDRESS:08X}")
    print("[Phase6AI] KSEG 0x80000000-0x80000FFF fence remains unchanged")
    print("[Phase6AI] Native Xenos remains physical renderer")
    print("[Phase6AI] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
