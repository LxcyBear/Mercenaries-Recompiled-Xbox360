#!/usr/bin/env python3
"""Phase 6AE: bridge the compact Xbox AV family and capture display-mode intent.

Phase 6AD hardware proved:
  * ordinal 1 AvGetSavedDataAddress crossed with exact +4 frame;
  * the next boundary is ordinal 2 AvSendTVEncoderOption with
    esp=0x008BF948 saved_esp=0x008BF95C, exactly +20 bytes;
  * _msize trace throttling changed no runtime semantics;
  * run ended PASS / XAPI 0.

6AE handles the complete ordinal 1-4 AV family as one bounded unit:
  1 AvGetSavedDataAddress      (already proven)
  2 AvSendTVEncoderOption@16  (hardware-proven +20 frame)
  3 AvSetDisplayMode@24       (pre-armed strict +28 frame)
  4 AvSetSavedDataAddress@4   (already pre-armed)

Original-Xbox TV encoder / NV2A programming is deliberately NOT performed.
The Xbox 360 Xenos device remains the actual display owner. Encoder write
options are maintained as logical no-ops; bounded query options return stable
port-facing values. AvSetDisplayMode records the title's requested mode,
format, pitch and framebuffer and returns STATUS_SUCCESS without touching
Xbox encoder/NV2A registers.

All inherited heap/VM/storage/Mm166/Xenos/guest-stack behavior stays unchanged.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AD-AV-SAVED-DATA-CLEANUP-20261023-A"
BUILD_TAG = "P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-B"
COOKIE_OLD = "phase6ad_env_build_cookie"
COOKIE_NEW = "phase6ae_env_build_cookie"
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AE] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AE] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AE] runtime Policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AE] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return text[:line_start] + indent + 'trace("' + new_policy + '");' + text[line_end:]


def install_av_family_support(main_text: str) -> str:
    marker = "static uint32_t s_phase6adAvSavedDataAddress;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AE] Phase 6AD AV state marker missing")

    decls = r'''static uint32_t s_phase6aeAvEncoderCount;
static uint32_t s_phase6aeAvEncoderQueryCount;
static uint32_t s_phase6aeAvEncoderWriteCount;
static uint32_t s_phase6aeAvLastRegisterBase;
static uint32_t s_phase6aeAvLastOption;
static uint32_t s_phase6aeAvLastParam;
static uint32_t s_phase6aeAvLastResultPointer;
static uint32_t s_phase6aeAvLastResultValue;

static uint32_t s_phase6aeDisplayModeCount;
static uint32_t s_phase6aeDisplayRegisterBase;
static uint32_t s_phase6aeDisplayStep;
static uint32_t s_phase6aeDisplayMode;
static uint32_t s_phase6aeDisplayFormat;
static uint32_t s_phase6aeDisplayPitch;
static uint32_t s_phase6aeDisplayFrameBuffer;

'''
    main_text = main_text.replace(marker, decls + marker, 1)

    handler_marker = "static void phase6ad_av_get_saved_data_address(uint32_t savedEsp)\n"
    if handler_marker not in main_text:
        raise SystemExit("[Phase6AE] Phase 6AD ordinal-1 handler marker missing")

    handlers = r'''static void phase6ae_av_send_tv_encoder_option(uint32_t savedEsp)
{
    const uint32_t c = g_esp;
    uint32_t ret;
    uint32_t registerBase;
    uint32_t option;
    uint32_t param;
    uint32_t resultVa;
    uint32_t resultValue;
    uint32_t writesResult;
    char line[420];

    if (savedEsp != c + 20u)
    {
        sprintf(
            line,
            "AvSendTVEncoderOption FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=20",
            (unsigned int)c,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - c));
        trace(line);
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000002u, savedEsp);
        return;
    }

    ret = GUEST_READ32(c + 0u);
    registerBase = GUEST_READ32(c + 4u);
    option = GUEST_READ32(c + 8u);
    param = GUEST_READ32(c + 12u);
    resultVa = GUEST_READ32(c + 16u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x80000002u, savedEsp);
        return;
    }

    if (ret != 0u)
    {
        trace("AvSendTVEncoderOption FRAME MISMATCH: nonzero synthetic return slot");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000002u, savedEsp);
        return;
    }

    /*
     * Xbox AV encoder options:
     *   5  AV_QUERY_CC_STATUS
     *   6  AV_QUERY_AV_CAPABILITIES
     *   13 AV_OPTION_QUERY_MODE
     *   16 AV_QUERY_ENCODER_TYPE
     *   17 AV_QUERY_MODE_TABLE_VERSION
     *
     * The native Xbox encoder does not exist on Xbox 360. Query values are
     * therefore stable compatibility values; all other encoder writes are
     * state-only no-ops because Xenos owns the physical display.
     */
    writesResult = 0u;
    resultValue = 0u;
    if (option == 5u)
    {
        writesResult = 1u;
        resultValue = 0u;
    }
    else if (option == 6u)
    {
        /* Standard AV pack | NTSC-M | 60 Hz. Keep the title on 640x480 path. */
        writesResult = 1u;
        resultValue = 0x00400101u;
    }
    else if (option == 13u)
    {
        writesResult = 1u;
        resultValue = s_phase6aeDisplayMode;
    }
    else if (option == 16u)
    {
        writesResult = 1u;
        resultValue = 0u;
    }
    else if (option == 17u)
    {
        writesResult = 1u;
        resultValue = 0u;
    }

    if (writesResult)
    {
        if (resultVa == 0u)
        {
            trace("AvSendTVEncoderOption QUERY MISMATCH: NULL Result for query option");
            phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000002u, savedEsp);
            return;
        }

        GUEST_WRITE32(resultVa, resultValue);
        if (s_accessFault)
        {
            phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x80000002u, savedEsp);
            return;
        }
        ++s_phase6aeAvEncoderQueryCount;
    }
    else
    {
        ++s_phase6aeAvEncoderWriteCount;
    }

    ++s_phase6aeAvEncoderCount;
    s_phase6aeAvLastRegisterBase = registerBase;
    s_phase6aeAvLastOption = option;
    s_phase6aeAvLastParam = param;
    s_phase6aeAvLastResultPointer = resultVa;
    s_phase6aeAvLastResultValue = resultValue;

    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6AE ordinal 2 AvSendTVEncoderOption reg=%08X option=%u param=%08X result_ptr=%08X result=%08X query=%u calls=%u new_esp=%08X",
        (unsigned int)registerBase,
        (unsigned int)option,
        (unsigned int)param,
        (unsigned int)resultVa,
        (unsigned int)resultValue,
        (unsigned int)writesResult,
        (unsigned int)s_phase6aeAvEncoderCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase6ae_av_set_display_mode(uint32_t savedEsp)
{
    const uint32_t c = g_esp;
    uint32_t ret;
    char line[460];

    if (savedEsp != c + 28u)
    {
        sprintf(
            line,
            "AvSetDisplayMode FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=28",
            (unsigned int)c,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - c));
        trace(line);
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000003u, savedEsp);
        return;
    }

    ret = GUEST_READ32(c + 0u);
    s_phase6aeDisplayRegisterBase = GUEST_READ32(c + 4u);
    s_phase6aeDisplayStep = GUEST_READ32(c + 8u);
    s_phase6aeDisplayMode = GUEST_READ32(c + 12u);
    s_phase6aeDisplayFormat = GUEST_READ32(c + 16u);
    s_phase6aeDisplayPitch = GUEST_READ32(c + 20u);
    s_phase6aeDisplayFrameBuffer = GUEST_READ32(c + 24u);
    if (s_accessFault)
    {
        phase4c_escape(PHASE4C_BOUNDARY_GUEST_FAULT, 0x80000003u, savedEsp);
        return;
    }

    if (ret != 0u)
    {
        trace("AvSetDisplayMode FRAME MISMATCH: nonzero synthetic return slot");
        phase4c_escape(PHASE4C_BOUNDARY_KERNEL_FRAME, 0x80000003u, savedEsp);
        return;
    }

    ++s_phase6aeDisplayModeCount;

    /*
     * Do not write NV2A/TV-encoder registers here. The Xbox 360 Xenos device
     * already owns the native surface. Record the retail title's requested
     * display contract and report success so the translated D3D path can
     * continue toward the renderer bridge.
     */
    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6AE ordinal 3 AvSetDisplayMode reg=%08X step=%u mode=%08X format=%08X pitch=%u framebuffer=%08X calls=%u new_esp=%08X",
        (unsigned int)s_phase6aeDisplayRegisterBase,
        (unsigned int)s_phase6aeDisplayStep,
        (unsigned int)s_phase6aeDisplayMode,
        (unsigned int)s_phase6aeDisplayFormat,
        (unsigned int)s_phase6aeDisplayPitch,
        (unsigned int)s_phase6aeDisplayFrameBuffer,
        (unsigned int)s_phase6aeDisplayModeCount,
        (unsigned int)g_esp);
    trace(line);
}

'''
    return main_text.replace(handler_marker, handlers + handler_marker, 1)


def patch_dispatch(main_text: str) -> str:
    marker = (
        "} else if (_phase4c_target == 0x80000004u) { \\\n"
        "        phase6ad_av_set_saved_data_address((uint32_t)(saved_esp)); \\"
    )
    if marker not in main_text:
        raise SystemExit("[Phase6AE] ordinal-4 dispatch marker missing")

    insertion = (
        "} else if (_phase4c_target == 0x80000002u) { \\\n"
        "        phase6ae_av_send_tv_encoder_option((uint32_t)(saved_esp)); \\\n"
        "    } else if (_phase4c_target == 0x80000003u) { \\\n"
        "        phase6ae_av_set_display_mode((uint32_t)(saved_esp)); \\\n"
        "    " + marker
    )
    return main_text.replace(marker, insertion, 1)


def reset_state(main_text: str) -> str:
    marker = "    s_phase6adAvSetCount = 0u;\n"
    if marker not in main_text:
        raise SystemExit("[Phase6AE] Phase 6AD reset marker missing")
    extra = (
        marker
        + "    s_phase6aeAvEncoderCount = 0u;\n"
        + "    s_phase6aeAvEncoderQueryCount = 0u;\n"
        + "    s_phase6aeAvEncoderWriteCount = 0u;\n"
        + "    s_phase6aeAvLastRegisterBase = 0u;\n"
        + "    s_phase6aeAvLastOption = 0u;\n"
        + "    s_phase6aeAvLastParam = 0u;\n"
        + "    s_phase6aeAvLastResultPointer = 0u;\n"
        + "    s_phase6aeAvLastResultValue = 0u;\n"
        + "    s_phase6aeDisplayModeCount = 0u;\n"
        + "    s_phase6aeDisplayRegisterBase = 0u;\n"
        + "    s_phase6aeDisplayStep = 0u;\n"
        + "    s_phase6aeDisplayMode = 0u;\n"
        + "    s_phase6aeDisplayFormat = 0u;\n"
        + "    s_phase6aeDisplayPitch = 0u;\n"
        + "    s_phase6aeDisplayFrameBuffer = 0u;\n"
    )
    return main_text.replace(marker, extra, 1)


def insert_summary(main_text: str) -> str:
    marker = "P6AD SAFE CLEANUP:"
    pos = main_text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6AE] Phase 6AD cleanup summary marker missing")
    stmt = main_text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 1600:
        raise SystemExit("[Phase6AE] could not locate cleanup summary statement")
    line_start = main_text.rfind("\n", 0, stmt) + 1
    indent = main_text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AE AV FAMILY: enc_calls=%u enc_queries=%u enc_writes=%u '
        f'last_option=%u last_param=%08X last_result_ptr=%08X last_result=%08X '
        f'display_calls=%u mode=%08X format=%08X pitch=%u framebuffer=%08X",\n'
        f'{indent}    (unsigned int)s_phase6aeAvEncoderCount,\n'
        f'{indent}    (unsigned int)s_phase6aeAvEncoderQueryCount,\n'
        f'{indent}    (unsigned int)s_phase6aeAvEncoderWriteCount,\n'
        f'{indent}    (unsigned int)s_phase6aeAvLastOption,\n'
        f'{indent}    (unsigned int)s_phase6aeAvLastParam,\n'
        f'{indent}    (unsigned int)s_phase6aeAvLastResultPointer,\n'
        f'{indent}    (unsigned int)s_phase6aeAvLastResultValue,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayModeCount,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayMode,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayFormat,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayPitch,\n'
        f'{indent}    (unsigned int)s_phase6aeDisplayFrameBuffer);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + block + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AE] optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AE] optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AE] translated body contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AE] translated function opening brace missing")
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
        name = f"phase6ae_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({"name": name, "chars": len(payload), "lines": payload.count("\n") + 1})
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AE] shard writer did not consume body")

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
        raise SystemExit("[Phase6AE] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6ae_",
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

    base = load(args.base_emitter, "phase6ae_base")
    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ad-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AE] cached Phase 6AD baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AD" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AE] cached Phase 6AD baseline identity mismatch")

    for marker in (
        BASE_TAG,
        "PASS: Phase 6AD ordinal 1 AvGetSavedDataAddress",
        "_phase4c_target == 0x80000001u",
        "_phase4c_target == 0x80000004u",
        "P6AD SAFE CLEANUP:",
        "PHASE 6AD AV SAVED-DATA + CLEANUP RESULT",
        "phase6ad_env_build_cookie",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AE] inherited marker missing: {marker}")

    if "else if (_phase4c_target == 0x80000002u)" in main_text:
        raise SystemExit("[Phase6AE] baseline unexpectedly already handles ordinal 2")
    if "else if (_phase4c_target == 0x80000003u)" in main_text:
        raise SystemExit("[Phase6AE] baseline unexpectedly already handles ordinal 3")

    main_text = install_av_family_support(main_text)
    main_text = patch_dispatch(main_text)
    main_text = reset_state(main_text)
    main_text = insert_summary(main_text)

    # A 6AE PASS must prove the hardware-observed ordinal-2 frontier crossed.
    main_text = replace_unique(
        main_text,
        "s_phase6adAvGetCount != 0u &&",
        "s_phase6aeAvEncoderCount != 0u &&\n        s_phase6adAvGetCount != 0u &&",
        "result gate",
    )

    main_text = replace_unique(
        main_text,
        "P6AD AV/CLEAN SUMMARY:",
        "P6AE AV/DISPLAY SUMMARY:",
        "summary token",
    )
    main_text = replace_unique(
        main_text,
        "PHASE 6AD AV SAVED-DATA + CLEANUP RESULT",
        "PHASE 6AE AV FAMILY + DISPLAY HANDOFF RESULT",
        "result token",
    )

    new_policy = (
        "Policy: inherit 6AD; bridge AV ordinals 1-4 with strict frames; "
        "record encoder/display intent only; Xenos remains display owner; "
        "keep NV2A/MMIO/VRAM and unrelated fault boundaries hard"
    )
    if len(new_policy) > 240:
        raise SystemExit("[Phase6AE] startup policy trace exceeds safe length")
    main_text = replace_policy_line(main_text, new_policy)

    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AD", "PHASE 6AE")
        .replace("Phase 6AD", "Phase 6AE")
        .replace('"P6AD ', '"P6AE ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AD", "PHASE 6AE")
        .replace("Phase 6AD", "Phase 6AE")
    )

    required = (
        BUILD_TAG,
        "static void phase6ae_av_send_tv_encoder_option(uint32_t savedEsp)",
        "static void phase6ae_av_set_display_mode(uint32_t savedEsp)",
        "_phase4c_target == 0x80000002u",
        "_phase4c_target == 0x80000003u",
        "PASS: Phase 6AE ordinal 2 AvSendTVEncoderOption",
        "PASS: Phase 6AE ordinal 3 AvSetDisplayMode",
        "s_phase6aeAvEncoderCount != 0u &&",
        "P6AE AV FAMILY:",
        "P6AE AV/DISPLAY SUMMARY:",
        "PHASE 6AE AV FAMILY + DISPLAY HANDOFF RESULT",
        "PASS: Phase 6AE Mm166 wrapper provenance",
        "phase6ae_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AE] generated source lost marker: {marker}")

    if COOKIE_OLD in main_text or COOKIE_OLD in env_text:
        raise SystemExit("[Phase6AE] stale Phase 6AD cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6AE", "build_tag": BUILD_TAG})
    manifest["phase6ae_av_family_display_handoff"] = {
        "source_phase": "6AD",
        "phase6ad_hardware_pass": True,
        "phase6ad_hardware": {
            "ordinal_1": {
                "name": "AvGetSavedDataAddress",
                "frame_bytes": 4,
                "address": "0x00000000",
                "calls": 1,
                "result": "PASS",
            },
            "next_boundary": {
                "kind": "ICALL_SAFE",
                "caller": "0x0023A3CE",
                "target": "0x80000002",
                "ordinal": 2,
                "name": "AvSendTVEncoderOption",
                "esp": "0x008BF948",
                "saved_esp": "0x008BF95C",
                "frame_bytes": 20,
                "ticks": 670848,
                "trace": 179942,
                "fault": 0,
            },
            "safe_cleanup": {
                "msize_calls": 601,
                "msize_suppressed_logs": 590,
            },
            "result": "PASS",
            "xapi_return": 0,
        },
        "av_family": {
            "ordinal_1": "inherited maintained AvGetSavedDataAddress",
            "ordinal_2": {
                "name": "AvSendTVEncoderOption",
                "hardware_observed": True,
                "frame_bytes": 20,
                "arguments": 4,
                "query_capabilities": "0x00400101 standard NTSC-M 60Hz",
                "encoder_writes": "logical no-op; Xenos owns physical display",
            },
            "ordinal_3": {
                "name": "AvSetDisplayMode",
                "hardware_observed": False,
                "prearmed": True,
                "frame_bytes": 28,
                "arguments": 6,
                "semantics": "capture mode/format/pitch/framebuffer and return success; no Xbox NV2A writes",
            },
            "ordinal_4": "inherited maintained AvSetSavedDataAddress",
        },
        "source_layout": source_layout,
        "runtime_policy": (
            "one bounded AV-family bridge; no original-Xbox hardware register writes; "
            "native Xenos remains display owner; strict frame/pointer validation retained"
        ),
    }

    (args.out_dir / "phase6ae-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AE] AV FAMILY + DISPLAY HANDOFF: READY")
    print("[Phase6AE] Ordinal 2: strict +20 AvSendTVEncoderOption")
    print("[Phase6AE] Ordinal 3: strict +28 AvSetDisplayMode pre-armed")
    print("[Phase6AE] Xbox encoder/NV2A writes: suppressed; Xenos remains display owner")
    print("[Phase6AE] Existing 6AD _msize cleanup: inherited unchanged")
    print("[Phase6AE] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
