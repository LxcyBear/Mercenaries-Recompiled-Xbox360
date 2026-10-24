#!/usr/bin/env python3
"""Phase 6AF: native-Xenos handoff for the retail D3D CreateDevice boundary.

Phase 6AE-B hardware proved:
  * native Xenos CreateDevice remains alive and healthy;
  * ordinal 2 AvSendTVEncoderOption@16 crosses cleanly;
  * observed ordinal-2 call: reg=0, option=9, param=1, Result=NULL;
  * the next clean frontier is renderer recovery stage 3 with
    HRESULT 0x8007000E (E_OUTOFMEMORY), fault=0;
  * the harness ends PASS / XAPI 0.

Upstream Mercenaries-Recompiled's own renderer-recovery regression test
identifies the retail CreateDevice routine as sub_0028CAA0 and validates its
six-argument + return-slot frame:
  adapter=0, deviceType=1, focusWindow=0, behavior=0x40,
  presentationParameters*, deviceOut*.
The same test's success fixture publishes guest device pointer 0x00299380.

6AF replaces only that original-Xbox device-creation routine with a bounded
compatibility handoff to the already-created native Xbox 360 Xenos device.
It validates the exact retail 640x480 presentation contract, records all
relevant parameters, writes the guest-visible device pointer, returns S_OK,
and then lets the existing translated D3D pack continue naturally.

No original-Xbox NV2A register writes are fabricated here. Existing MMIO/VRAM,
platform, ABI and guest-fault fences remain authoritative.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-B"
BUILD_TAG = "P6AF-NATIVE-D3D-CREATEDEVICE-HANDOFF-20261023-A"
COOKIE_OLD = "phase6ae_env_build_cookie"
COOKIE_NEW = "phase6af_env_build_cookie"
SHARD_TARGET_CHARS = 750000

RETAIL_CREATE_DEVICE = "sub_0028CAA0"
RETAIL_GUEST_DEVICE = 0x00299380
RETAIL_DEVICE_GLOBAL = 0x007AD604


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AF] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AF] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AF] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AF] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + new_policy + '");' + text[line_end:]


def install_state(main_text: str) -> str:
    marker = "static uint32_t s_phase6aeAvEncoderCount;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AF] Phase 6AE state marker missing")

    state = r'''static uint32_t s_phase6afCreateDeviceBridgeCount;
static uint32_t s_phase6afCreateDeviceAdapter;
static uint32_t s_phase6afCreateDeviceType;
static uint32_t s_phase6afCreateDeviceFocus;
static uint32_t s_phase6afCreateDeviceBehavior;
static uint32_t s_phase6afCreateDevicePp;
static uint32_t s_phase6afCreateDeviceOut;
static uint32_t s_phase6afCreateDeviceWidth;
static uint32_t s_phase6afCreateDeviceHeight;
static uint32_t s_phase6afCreateDeviceFormat;
static uint32_t s_phase6afCreateDeviceBackBuffers;
static uint32_t s_phase6afCreateDeviceMultisample;
static uint32_t s_phase6afCreateDeviceSwap;
static uint32_t s_phase6afCreateDeviceAutoDepth;
static uint32_t s_phase6afCreateDeviceDepthFormat;
static uint32_t s_phase6afGuestDevice;

'''
    return main_text.replace(marker, state + marker, 1)


def replace_create_device(main_text: str, base) -> str:
    signature = f"static void {RETAIL_CREATE_DEVICE}(void)"
    masked = base.mask_noncode(main_text)

    definitions = []
    cursor = 0
    while True:
        pos = masked.find(signature, cursor)
        if pos < 0:
            break
        after = pos + len(signature)
        probe = after
        while probe < len(masked) and masked[probe].isspace():
            probe += 1
        if probe < len(masked) and masked[probe] == "{":
            definitions.append((pos, probe))
        cursor = after

    if len(definitions) != 1:
        raise SystemExit(
            f"[Phase6AF] expected one {RETAIL_CREATE_DEVICE} definition, found {len(definitions)}"
        )

    start, brace = definitions[0]
    end = base.closing_brace(masked, brace)

    replacement = r'''static void sub_0028CAA0(void)
{
    const uint32_t c = g_esp;
    uint32_t ret;
    uint32_t adapter;
    uint32_t deviceType;
    uint32_t focusWindow;
    uint32_t behavior;
    uint32_t pp;
    uint32_t out;
    uint32_t width;
    uint32_t height;
    uint32_t format;
    uint32_t backBuffers;
    uint32_t multisample;
    uint32_t swap;
    uint32_t autoDepth;
    uint32_t depthFormat;
    char line[448];

    ret = GUEST_READ32(c + 0u);
    adapter = GUEST_READ32(c + 4u);
    deviceType = GUEST_READ32(c + 8u);
    focusWindow = GUEST_READ32(c + 12u);
    behavior = GUEST_READ32(c + 16u);
    pp = GUEST_READ32(c + 20u);
    out = GUEST_READ32(c + 24u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x0028CAA0u, c);
        return;
    }

    if (pp == 0u || out == 0u)
    {
        trace("Phase 6AF CreateDevice contract mismatch: NULL pp/out");
        phase4c_escape(PHASE4C_BOUNDARY_RENDERER_FATAL, 0x80070057u, c);
        return;
    }

    width = GUEST_READ32(pp + 0u);
    height = GUEST_READ32(pp + 4u);
    format = GUEST_READ32(pp + 8u);
    backBuffers = GUEST_READ32(pp + 12u);
    multisample = GUEST_READ32(pp + 16u);
    swap = GUEST_READ32(pp + 20u);
    autoDepth = GUEST_READ32(pp + 32u);
    depthFormat = GUEST_READ32(pp + 36u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x0028CAA0u, c);
        return;
    }

    sprintf(
        line,
        "Phase 6AF CreateDevice LIVE frame ret=%08X adapter=%u type=%u focus=%08X behavior=%08X pp=%08X out=%08X",
        (unsigned int)ret,
        (unsigned int)adapter,
        (unsigned int)deviceType,
        (unsigned int)focusWindow,
        (unsigned int)behavior,
        (unsigned int)pp,
        (unsigned int)out);
    trace(line);

    sprintf(
        line,
        "Phase 6AF CreateDevice PP width=%u height=%u format=%08X buffers=%u ms=%08X swap=%u auto_depth=%u depth_format=%08X",
        (unsigned int)width,
        (unsigned int)height,
        (unsigned int)format,
        (unsigned int)backBuffers,
        (unsigned int)multisample,
        (unsigned int)swap,
        (unsigned int)autoDepth,
        (unsigned int)depthFormat);
    trace(line);

    /*
     * This bridge is deliberately narrow. These fields are the exact retail
     * contract validated by Mercenaries-Recompiled's renderer-recovery test.
     * Multisample is not fixed because the retail fallback explicitly changes
     * it to the non-AA mode before retrying CreateDevice.
     */
    if (ret != 0u ||
        adapter != 0u ||
        deviceType != 1u ||
        focusWindow != 0u ||
        behavior != 0x40u ||
        width != 640u ||
        height != 480u ||
        format != 6u ||
        backBuffers != 1u ||
        swap != 1u ||
        autoDepth != 1u ||
        depthFormat != 0x2Au)
    {
        trace("Phase 6AF CreateDevice contract mismatch: refusing generalized device fabrication");
        phase4c_escape(PHASE4C_BOUNDARY_RENDERER_FATAL, 0x80070057u, c);
        return;
    }

    if (!s_phase6bXenosReady || s_phase6bXenosDevice == NULL)
    {
        trace("Phase 6AF CreateDevice handoff rejected: native Xenos device is not alive");
        phase4c_escape(PHASE4C_BOUNDARY_RENDERER_FATAL, 0x80004005u, c);
        return;
    }

    /*
     * The real physical device is s_phase6bXenosDevice. The translated Xbox
     * D3D code still expects its retail guest-visible device identity. Upstream
     * renderer recovery fixtures use 0x00299380 for that successful identity.
     */
    s_phase6afGuestDevice = 0x00299380u;
    GUEST_WRITE32(out, s_phase6afGuestDevice);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, out, c);
        return;
    }

    ++s_phase6afCreateDeviceBridgeCount;
    s_phase6afCreateDeviceAdapter = adapter;
    s_phase6afCreateDeviceType = deviceType;
    s_phase6afCreateDeviceFocus = focusWindow;
    s_phase6afCreateDeviceBehavior = behavior;
    s_phase6afCreateDevicePp = pp;
    s_phase6afCreateDeviceOut = out;
    s_phase6afCreateDeviceWidth = width;
    s_phase6afCreateDeviceHeight = height;
    s_phase6afCreateDeviceFormat = format;
    s_phase6afCreateDeviceBackBuffers = backBuffers;
    s_phase6afCreateDeviceMultisample = multisample;
    s_phase6afCreateDeviceSwap = swap;
    s_phase6afCreateDeviceAutoDepth = autoDepth;
    s_phase6afCreateDeviceDepthFormat = depthFormat;

    g_eax = 0u;
    g_esp = c + 28u;

    sprintf(
        line,
        "PASS: Phase 6AF native D3D CreateDevice handoff guest_device=%08X out=%08X global=%08X calls=%u new_esp=%08X",
        (unsigned int)s_phase6afGuestDevice,
        (unsigned int)out,
        (unsigned int)0x007AD604u,
        (unsigned int)s_phase6afCreateDeviceBridgeCount,
        (unsigned int)g_esp);
    trace(line);
}
'''
    return main_text[:start] + replacement + main_text[end:]


def reset_state(main_text: str) -> str:
    marker = "    s_phase6aeDisplayFrameBuffer = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AF] Phase 6AE reset marker missing")
    extra = marker + (
        "    s_phase6afCreateDeviceBridgeCount = 0u;\n"
        "    s_phase6afCreateDeviceAdapter = 0u;\n"
        "    s_phase6afCreateDeviceType = 0u;\n"
        "    s_phase6afCreateDeviceFocus = 0u;\n"
        "    s_phase6afCreateDeviceBehavior = 0u;\n"
        "    s_phase6afCreateDevicePp = 0u;\n"
        "    s_phase6afCreateDeviceOut = 0u;\n"
        "    s_phase6afCreateDeviceWidth = 0u;\n"
        "    s_phase6afCreateDeviceHeight = 0u;\n"
        "    s_phase6afCreateDeviceFormat = 0u;\n"
        "    s_phase6afCreateDeviceBackBuffers = 0u;\n"
        "    s_phase6afCreateDeviceMultisample = 0u;\n"
        "    s_phase6afCreateDeviceSwap = 0u;\n"
        "    s_phase6afCreateDeviceAutoDepth = 0u;\n"
        "    s_phase6afCreateDeviceDepthFormat = 0u;\n"
        "    s_phase6afGuestDevice = 0u;\n"
    )
    return main_text.replace(marker, extra, 1)


def insert_summary(main_text: str) -> str:
    marker = "P6AE AV FAMILY:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AF] inherited AV summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 2200:
        raise SystemExit("[Phase6AF] could not locate AV summary statement")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AF D3D DEVICE: calls=%u guest=%08X pp=%08X out=%08X '
        f'%ux%u fmt=%08X buffers=%u ms=%08X swap=%u depth=%u depth_fmt=%08X",\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceBridgeCount,\n'
        f'{indent}    (unsigned int)s_phase6afGuestDevice,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDevicePp,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceOut,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceWidth,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceHeight,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceFormat,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceBackBuffers,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceMultisample,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceSwap,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceAutoDepth,\n'
        f'{indent}    (unsigned int)s_phase6afCreateDeviceDepthFormat);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AF] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AF] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AF] translated body contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AF] translated function opening brace missing")
        function_ends.append(base.closing_brace(masked, open_index))

    cut_points = []
    chunk_start = 0
    last_end = 0
    for end in function_ends:
        last_end = end
        if end - chunk_start >= SHARD_TARGET_CHARS:
            cut_points.append(end)
            chunk_start = end
    if last_end < len(body):
        last_end = len(body)
    if not cut_points or cut_points[-1] != last_end:
        cut_points.append(last_end)

    shard_dir = out_dir / "translated_shards"
    shard_dir.mkdir(parents=True, exist_ok=True)
    for stale in shard_dir.glob("*.inl"):
        stale.unlink()

    shards = []
    start = 0
    for index, end in enumerate(cut_points):
        if end <= start:
            continue
        name = f"phase6af_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({"name": name, "chars": len(payload), "lines": payload.count("\n") + 1})
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AF] shard writer did not consume body")

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
        raise SystemExit("[Phase6AF] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6af_",
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

    base = load(args.base_emitter, "phase6af_base")
    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ae-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AF] cached Phase 6AE baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AE" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AF] cached Phase 6AE baseline identity mismatch")

    for marker in (
        BASE_TAG,
        "P6AE XENOS: PASS Direct3D_CreateDevice",
        "static D3DDevice* s_phase6bXenosDevice = NULL;",
        "static int s_phase6bXenosReady = 0;",
        "PASS: Phase 6AE ordinal 2 AvSendTVEncoderOption",
        "static void sub_0028CAA0(void)",
        "static void recomp_renderer_recovery_report(uint32_t result, uint32_t stage)",
        "PHASE 6AE AV FAMILY + DISPLAY HANDOFF RESULT",
        "phase6ae_env_build_cookie",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AF] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = replace_create_device(main_text, base)
    main_text = reset_state(main_text)
    main_text = insert_summary(main_text)

    main_text = replace_unique(
        main_text,
        "s_phase6aeAvEncoderCount != 0u &&",
        "s_phase6afCreateDeviceBridgeCount != 0u &&\n        s_phase6aeAvEncoderCount != 0u &&",
        "result gate",
    )
    main_text = replace_unique(
        main_text,
        "PHASE 6AE AV FAMILY + DISPLAY HANDOFF RESULT",
        "PHASE 6AF NATIVE D3D DEVICE HANDOFF RESULT",
        "result token",
    )

    new_policy = (
        "Policy: inherit 6AE-B; hand off exact retail D3D CreateDevice to the "
        "already-live native Xenos device; publish guest device 00299380; "
        "continue translated D3D; keep NV2A/MMIO/VRAM and fault fences hard"
    )
    if len(new_policy) > 240:
        raise SystemExit("[Phase6AF] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, new_policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AE", "PHASE 6AF")
        .replace("Phase 6AE", "Phase 6AF")
        .replace('"P6AE ', '"P6AF ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AE", "PHASE 6AF")
        .replace("Phase 6AE", "Phase 6AF")
    )

    required = (
        BUILD_TAG,
        "static void sub_0028CAA0(void)",
        "PASS: Phase 6AF native D3D CreateDevice handoff",
        "s_phase6afCreateDeviceBridgeCount != 0u &&",
        "P6AF D3D DEVICE:",
        "P6AF AV FAMILY:",
        "PHASE 6AF NATIVE D3D DEVICE HANDOFF RESULT",
        "P6AF XENOS: PASS Direct3D_CreateDevice",
        "PASS: Phase 6AF ordinal 2 AvSendTVEncoderOption",
        "phase6af_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AF] generated source lost marker: {marker}")

    if COOKIE_OLD in main_text or COOKIE_OLD in env_text:
        raise SystemExit("[Phase6AF] stale Phase 6AE cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6AF", "build_tag": BUILD_TAG})
    manifest["phase6af_native_d3d_createdevice_handoff"] = {
        "source_phase": "6AE",
        "phase6ae_hardware_pass": True,
        "phase6ae_hardware": {
            "xenos_device_result": "PASS",
            "ordinal_2": {
                "name": "AvSendTVEncoderOption",
                "register_base": "0x00000000",
                "option": 9,
                "param": "0x00000001",
                "result_pointer": "0x00000000",
                "query": False,
                "result": "PASS",
            },
            "renderer_boundary": {
                "kind": "RENDERER_FATAL",
                "stage": 3,
                "hresult": "0x8007000E",
                "esp": "0x008BF99C",
                "saved_esp": "0x008BF99C",
                "ticks": 671044,
                "trace": 179943,
                "fault": 0,
            },
            "result": "PASS",
            "xapi_return": 0,
        },
        "upstream_recovery_contract": {
            "source_test": "tools/recomp/test_renderer_creation_recovery_native.py",
            "retail_create_device": "sub_0028CAA0",
            "frame_bytes": 28,
            "arguments": 6,
            "success_guest_device": "0x00299380",
            "device_global": "0x007AD604",
            "validated_presentation": {
                "width": 640,
                "height": 480,
                "format": 6,
                "back_buffers": 1,
                "swap": 1,
                "auto_depth": 1,
                "depth_format": "0x2A",
                "multisample": "variable by retail AA/non-AA recovery",
            },
        },
        "native_handoff": {
            "physical_device": "existing Phase-6 native Xenos D3DDevice",
            "guest_device_identity": "0x00299380",
            "return": "S_OK",
            "stack_advance": 28,
            "original_xbox_nv2a_register_writes": False,
            "strict_contract_validation": True,
        },
        "source_layout": source_layout,
        "runtime_policy": (
            "replace only retail sub_0028CAA0 with exact-contract native-Xenos "
            "handoff; preserve translated D3D continuation and hard-stop genuine "
            "NV2A/MMIO/VRAM, platform, ABI and guest faults"
        ),
    }

    (args.out_dir / "phase6af-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AF] NATIVE D3D CREATEDEVICE HANDOFF: READY")
    print("[Phase6AF] Retail routine: sub_0028CAA0")
    print("[Phase6AF] Physical owner: existing native Xenos device")
    print("[Phase6AF] Guest-visible device identity: 0x00299380")
    print("[Phase6AF] Exact 640x480 retail presentation contract enforced")
    print("[Phase6AF] NV2A/MMIO/VRAM remains a hard stop")
    print("[Phase6AF] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
