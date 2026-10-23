#!/usr/bin/env python3
"""Phase 6AD: cross AvGetSavedDataAddress and perform safe cleanup pass #1.

Phase 6AC hardware proved the generalized sub_0022AEE9 ordinal-166 wrapper:
  * the retail graphics pool still succeeds at 0x02880000 / 0x01680000;
  * the later 96-byte MmAllocateContiguousMemoryEx call is accepted by the
    wrapper-proven +28 ABI and reaches the intended audio-allocation fallback;
  * the next boundary is ICALL_SAFE target 0x80000001 (kernel ordinal 1),
    esp=0x008BF958 saved_esp=0x008BF95C (4-byte frame), fault=0;
  * the run ends PASS/XAPI 0 with direct=1817 and last_direct=0x00290450.

Ordinal 1 is AvGetSavedDataAddress(void). 6AD implements the exact observed
zero-argument frame and returns a maintained saved-display-data guest address,
initially NULL. Its natural partner, ordinal 4 AvSetSavedDataAddress(PVOID), is
pre-armed as a strict one-argument round-trip setter. Hardware-facing AV
ordinals 2/3 remain hard stops.

Safe cleanup pass #1 is intentionally semantics-free:
  * throttle only repetitive maintained CRT _msize PASS traces;
  * retain every call, return value, allocation lookup and counter;
  * emit an aggregate suppression summary;
  * write fresh phase6ad_* translated shard names and verify byte-identical
    reconstruction of the monolithic translated body.

No heap, VM, graphics-pool, Xenos, guest-stack, register or renderer behavior
is changed by the cleanup portion.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6AC-MM166-WRAPPER-REUSE-20261023-A"
BUILD_TAG = "P6AD-AV-SAVED-DATA-CLEANUP-20261023-A"
COOKIE_OLD = "phase6ac_env_build_cookie"
COOKIE_NEW = "phase6ad_env_build_cookie"
COOKIE_NUM_OLD = "50366363"
COOKIE_NUM_NEW = "50366464"
SHARD_TARGET_CHARS = 750000


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6AD] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6AD] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, new_policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6AD] runtime Policy trace is missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6AD] multiple runtime Policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    replacement = indent + 'trace("' + new_policy + '");'
    return text[:line_start] + replacement + text[line_end:]


def install_av_saved_data_support(main_text: str) -> str:
    marker = (
        "static int s_phase6acMm166WrapperActive;\n\n"
        "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)"
    )
    if marker not in main_text:
        raise SystemExit("[Phase6AD] Mm166 handler declaration marker changed")

    support = r'''static uint32_t s_phase6adAvSavedDataAddress;
static uint32_t s_phase6adAvGetCount;
static uint32_t s_phase6adAvSetCount;

static void phase6ad_av_get_saved_data_address(uint32_t savedEsp)
{
    uint32_t c = g_esp;
    uint32_t ret;
    char line[320];

    if (savedEsp != c + 4u)
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000001u,
            savedEsp);

    ret = GUEST_READ32(c + 0u);
    if (s_accessFault)
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000001u,
            savedEsp);

    if (ret != 0u)
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000001u,
            savedEsp);

    ++s_phase6adAvGetCount;
    g_eax = s_phase6adAvSavedDataAddress;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6AD ordinal 1 AvGetSavedDataAddress address=%08X calls=%u new_esp=%08X",
        (unsigned int)g_eax,
        (unsigned int)s_phase6adAvGetCount,
        (unsigned int)g_esp);
    trace(line);
}

static void phase6ad_av_set_saved_data_address(uint32_t savedEsp)
{
    uint32_t c = g_esp;
    uint32_t ret;
    uint32_t address;
    char line[320];

    if (savedEsp != c + 8u)
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000004u,
            savedEsp);

    ret = GUEST_READ32(c + 0u);
    address = GUEST_READ32(c + 4u);
    if (s_accessFault)
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000004u,
            savedEsp);

    if (ret != 0u)
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000004u,
            savedEsp);

    s_phase6adAvSavedDataAddress = address;
    ++s_phase6adAvSetCount;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6AD ordinal 4 AvSetSavedDataAddress address=%08X calls=%u new_esp=%08X",
        (unsigned int)address,
        (unsigned int)s_phase6adAvSetCount,
        (unsigned int)g_esp);
    trace(line);
}

'''
    return main_text.replace(marker, support + marker, 1)


def patch_av_dispatch(main_text: str) -> str:
    marker = (
        "} else if (_phase4c_target == 0x8000002Fu && "
        "s_phase4cCallbackEntered) { \\"
    )
    if marker not in main_text:
        raise SystemExit("[Phase6AD] RECOMP_ICALL_SAFE AV insertion marker changed")

    new = (
        "} else if (_phase4c_target == 0x80000001u) { \\\n"
        "        phase6ad_av_get_saved_data_address((uint32_t)(saved_esp)); \\\n"
        "    } else if (_phase4c_target == 0x80000004u) { \\\n"
        "        phase6ad_av_set_saved_data_address((uint32_t)(saved_esp)); \\\n"
        "    " + marker
    )
    main_text = main_text.replace(marker, new, 1)

    if "else if (_phase4c_target == 0x80000002u)" in main_text:
        raise SystemExit("[Phase6AD] ordinal 2 unexpectedly became an automatic continuation")
    if "else if (_phase4c_target == 0x80000003u)" in main_text:
        raise SystemExit("[Phase6AD] ordinal 3 unexpectedly became an automatic continuation")
    return main_text


def containing_function_span(main_text: str, base, marker: str) -> tuple[int, int]:
    marker_pos = main_text.find(marker)
    if marker_pos < 0:
        raise SystemExit(f"[Phase6AD] cleanup marker missing: {marker}")

    masked = base.mask_noncode(main_text)
    candidates = [
        match for match in base.FUNC_RE.finditer(masked)
        if match.start() < marker_pos
    ]
    for match in reversed(candidates):
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            continue
        end = base.closing_brace(masked, open_index)
        if open_index < marker_pos < end:
            return match.start(), end

    raise SystemExit("[Phase6AD] could not identify _msize helper function span")


def throttle_msize_trace(main_text: str, base) -> str:
    marker = '"PASS: Phase 6AC maintained CRT _msize'
    if main_text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6AD] expected one maintained _msize log format, found "
            f"{main_text.count(marker)}"
        )

    start, end = containing_function_span(main_text, base, marker)
    body = main_text[start:end]
    marker_pos = body.find(marker)
    trace_pos = body.find("trace(line);", marker_pos)
    if trace_pos < 0:
        raise SystemExit("[Phase6AD] maintained _msize trace call not found")

    if body.find("trace(line);", trace_pos + len("trace(line);")) >= 0:
        raise SystemExit(
            "[Phase6AD] maintained _msize helper has multiple later trace(line) calls; "
            "refusing ambiguous cleanup"
        )

    replacement = (
        "++s_phase6adMsizeLogCallCount;\n"
        "    if (s_phase6adMsizeLogCallCount <= 4u ||\n"
        "        (s_phase6adMsizeLogCallCount & "
        "(s_phase6adMsizeLogCallCount - 1u)) == 0u)\n"
        "        trace(line);\n"
        "    else\n"
        "        ++s_phase6adMsizeLogSuppressedCount;"
    )
    body = (
        body[:trace_pos]
        + replacement
        + body[trace_pos + len("trace(line);"):]
    )

    declarations = (
        "static uint32_t s_phase6adMsizeLogCallCount;\n"
        "static uint32_t s_phase6adMsizeLogSuppressedCount;\n"
    )
    return main_text[:start] + declarations + body + main_text[end:]


def reset_new_state(main_text: str) -> str:
    old = "    s_phase6acMm166WrapperActive = 0;\n"
    new = (
        old
        + "    s_phase6adAvSavedDataAddress = 0u;\n"
        + "    s_phase6adAvGetCount = 0u;\n"
        + "    s_phase6adAvSetCount = 0u;\n"
        + "    s_phase6adMsizeLogCallCount = 0u;\n"
        + "    s_phase6adMsizeLogSuppressedCount = 0u;\n"
    )
    return replace_unique(main_text, old, new, "Phase 6AC state reset")


def insert_cleanup_summary(main_text: str) -> str:
    marker = "P6AC MM166WRAP SUMMARY:"
    marker_pos = main_text.find(marker)
    if marker_pos < 0:
        raise SystemExit("[Phase6AD] inherited Phase 6AC summary marker missing")

    statement_pos = main_text.rfind("sprintf(", 0, marker_pos)
    if statement_pos < 0 or marker_pos - statement_pos > 1200:
        raise SystemExit("[Phase6AD] could not locate summary sprintf statement")

    line_start = main_text.rfind("\n", 0, statement_pos) + 1
    indent = main_text[line_start:statement_pos]
    cleanup = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6AD SAFE CLEANUP: av_get=%u av_set=%u saved=%08X '
        f'msize_log_calls=%u msize_suppressed=%u",\n'
        f'{indent}    (unsigned int)s_phase6adAvGetCount,\n'
        f'{indent}    (unsigned int)s_phase6adAvSetCount,\n'
        f'{indent}    (unsigned int)s_phase6adAvSavedDataAddress,\n'
        f'{indent}    (unsigned int)s_phase6adMsizeLogCallCount,\n'
        f'{indent}    (unsigned int)s_phase6adMsizeLogSuppressedCount);\n'
        f'{indent}trace(line);\n'
    )
    return main_text[:line_start] + cleanup + main_text[line_start:]


def write_sharded_main(out_dir: Path, main_text: str, base) -> dict:
    off_marker = '#pragma optimize("", off)\n'
    on_marker = '\n#pragma optimize("", on)'
    off_pos = main_text.find(off_marker)
    if off_pos < 0:
        raise SystemExit("[Phase6AD] translated-body optimize-off marker missing")
    body_start = off_pos + len(off_marker)
    on_pos = main_text.find(on_marker, body_start)
    if on_pos < 0:
        raise SystemExit("[Phase6AD] translated-body optimize-on marker missing")

    body = main_text[body_start:on_pos]
    masked = base.mask_noncode(body)
    matches = list(base.FUNC_RE.finditer(masked))
    if not matches:
        raise SystemExit("[Phase6AD] translated-body block contains no functions")

    function_ends = []
    for match in matches:
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            raise SystemExit("[Phase6AD] translated function opening brace missing")
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
        name = f"phase6ad_{index:03d}.inl"
        payload = body[start:end]
        (shard_dir / name).write_text(payload, encoding="utf-8")
        shards.append({
            "name": name,
            "chars": len(payload),
            "lines": payload.count("\n") + 1,
        })
        start = end

    if start != len(body):
        raise SystemExit("[Phase6AD] shard writer did not consume full body block")

    include_block = "".join(
        f'#include "translated_shards/{row["name"]}"\n'
        for row in shards
    )
    wrapper = main_text[:body_start] + include_block + main_text[on_pos:]
    (out_dir / "main_monolithic.cpp").write_text(main_text, encoding="utf-8")
    (out_dir / "main.cpp").write_text(wrapper, encoding="utf-8")

    reconstructed = "".join(
        (shard_dir / row["name"]).read_text(encoding="utf-8")
        for row in shards
    )
    if reconstructed != body:
        raise SystemExit("[Phase6AD] shard reconstruction identity mismatch")

    return {
        "build_main": "main.cpp",
        "monolithic_cache": "main_monolithic.cpp",
        "shard_directory": "translated_shards",
        "shard_prefix": "phase6ad_",
        "shard_count": len(shards),
        "target_chars": SHARD_TARGET_CHARS,
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

    base = load(args.base_emitter, "phase6ad_base")

    base_main = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6ac-manifest.json"
    for path in (base_main, base_env, base_manifest):
        if not path.exists():
            raise SystemExit(f"[Phase6AD] cached Phase 6AC baseline missing: {path}")

    main_text = base_main.read_text(encoding="utf-8")
    env_text = base_env.read_text(encoding="utf-8")
    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6AC" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6AD] cached Phase 6AC baseline identity mismatch")

    ac = manifest.get("phase6ac_mm166_wrapper_reuse") or {}
    proof = ac.get("generated_wrapper_proof") or {}
    if (
        ac.get("phase6ab_hardware_pass") is not True
        or proof.get("wrapper_frame_bytes") != 28
        or ac.get("graphics_pool_special_case_inherited_unchanged") is not True
        or ac.get("hal_boot_video_mode_data_inherited_unchanged") is not True
    ):
        raise SystemExit("[Phase6AD] inherited Phase 6AC proof/model drift")

    for marker in (
        BASE_TAG,
        "PASS: Phase 6AC Mm166 wrapper provenance",
        "PASS: Phase 6AC retail graphics pool claim",
        "P6AC MM166WRAP SUMMARY:",
        "PHASE 6AC MM166 WRAPPER REUSE RESULT",
        "static int s_phase6acMm166WrapperActive;",
        "phase6ac_env_build_cookie",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6AD] inherited Phase 6AC marker missing: {marker}")

    main_text = install_av_saved_data_support(main_text)
    main_text = patch_av_dispatch(main_text)
    main_text = throttle_msize_trace(main_text, base)
    main_text = reset_new_state(main_text)
    main_text = insert_cleanup_summary(main_text)

    # A 6AD PASS must prove we actually crossed the new ordinal-1 boundary.
    main_text = replace_unique(
        main_text,
        "s_phase6aaRootEntered &&",
        "s_phase6adAvGetCount != 0u &&\n        s_phase6aaRootEntered &&",
        "result gate",
    )

    main_text = replace_unique(
        main_text,
        "P6AC MM166WRAP SUMMARY:",
        "P6AD AV/CLEAN SUMMARY:",
        "Phase 6AC summary token",
    )
    main_text = replace_unique(
        main_text,
        "PHASE 6AC MM166 WRAPPER REUSE RESULT",
        "PHASE 6AD AV SAVED-DATA + CLEANUP RESULT",
        "Phase 6AC result token",
    )

    new_policy = (
        "Policy: inherit hardware-proven Phase-6AC Xenos, retail graphics pool, "
        "HalBootSMCVideoMode DATA relocation and generalized Mm166 wrapper ABI; "
        "cross exact ICALL_SAFE ordinal 1 with strict zero-argument "
        "AvGetSavedDataAddress semantics, pre-arm only paired ordinal 4 "
        "AvSetSavedDataAddress with a strict one-argument frame, keep AV "
        "ordinals 2/3 plus NV2A/platform/ABI/guest-fault boundaries hard, and "
        "perform semantics-free _msize trace/shard cleanup only"
    )
    main_text = replace_policy_line(main_text, new_policy)

    main_text = replace_unique(
        main_text,
        BASE_TAG,
        BUILD_TAG,
        "Phase 6AC build tag",
    )
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = main_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)
    env_text = env_text.replace(COOKIE_NUM_OLD, COOKIE_NUM_NEW)

    main_text = (
        main_text
        .replace("PHASE 6AC", "PHASE 6AD")
        .replace("Phase 6AC", "Phase 6AD")
        .replace('"P6AC ', '"P6AD ')
    )
    env_text = (
        env_text
        .replace("PHASE 6AC", "PHASE 6AD")
        .replace("Phase 6AC", "Phase 6AD")
    )

    required = (
        BUILD_TAG,
        "static void phase6ad_av_get_saved_data_address(uint32_t savedEsp)",
        "static void phase6ad_av_set_saved_data_address(uint32_t savedEsp)",
        "_phase4c_target == 0x80000001u",
        "_phase4c_target == 0x80000004u",
        "PASS: Phase 6AD ordinal 1 AvGetSavedDataAddress",
        "PASS: Phase 6AD ordinal 4 AvSetSavedDataAddress",
        "s_phase6adAvGetCount != 0u &&",
        "s_phase6adMsizeLogCallCount <= 4u",
        "s_phase6adMsizeLogSuppressedCount",
        "P6AD SAFE CLEANUP:",
        "P6AD AV/CLEAN SUMMARY:",
        "PHASE 6AD AV SAVED-DATA + CLEANUP RESULT",
        "PASS: Phase 6AD Mm166 wrapper provenance",
        "PASS: Phase 6AD retail graphics pool claim",
        "phase6ad_env_build_cookie",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6AD] generated main lost marker: {marker}")

    if "else if (_phase4c_target == 0x80000002u)" in main_text:
        raise SystemExit("[Phase6AD] AV ordinal 2 must remain fenced")
    if "else if (_phase4c_target == 0x80000003u)" in main_text:
        raise SystemExit("[Phase6AD] AV ordinal 3 must remain fenced")
    if "phase6ac_env_build_cookie" in main_text or "phase6ac_env_build_cookie" in env_text:
        raise SystemExit("[Phase6AD] stale Phase 6AC env cookie remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    source_layout = write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6AD",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6ad_av_saved_data_cleanup"] = {
        "source_phase": "6AC",
        "phase6ac_hardware_pass": True,
        "phase6ac_hardware": {
            "ordinal_166_graphics_pool": {
                "size": "0x01680000",
                "base": "0x02880000",
                "frame_bytes": 28,
                "wrapper_active": 1,
            },
            "ordinal_166_audio_request": {
                "size": "0x00000060",
                "low": "0x00000000",
                "high": "0xFFFFFFFF",
                "alignment": "0x00001000",
                "protect": "0x00000004",
                "base": "0x00000000",
                "frame_bytes": 28,
                "wrapper_active": 1,
                "fault": 0,
            },
            "next_boundary": {
                "kind": "ICALL_SAFE",
                "caller": "0x0023A3CE",
                "target": "0x80000001",
                "ordinal": 1,
                "name": "AvGetSavedDataAddress",
                "esp": "0x008BF958",
                "saved_esp": "0x008BF95C",
                "frame_bytes": 4,
                "ticks": 670846,
                "trace": 179942,
                "fault": 0,
            },
            "summary": {
                "direct": 1817,
                "last_direct": "0x00290450",
                "icall": 9075,
                "last_icall": "0x00209720",
            },
            "result": "PASS",
            "xapi_return": 0,
        },
        "av_saved_data": {
            "ordinal_1": {
                "name": "AvGetSavedDataAddress",
                "hardware_observed": True,
                "frame_bytes": 4,
                "arguments": 0,
                "initial_return": "0x00000000",
            },
            "ordinal_4": {
                "name": "AvSetSavedDataAddress",
                "hardware_observed": False,
                "prearmed": True,
                "frame_bytes": 8,
                "arguments": 1,
                "semantics": "strict maintained get/set guest-address round trip",
            },
            "ordinals_2_3_remain_hard_stops": True,
        },
        "safe_cleanup_pass_1": {
            "runtime_semantics_changed": False,
            "msize_trace_policy": (
                "emit first 4 calls and power-of-two calls; suppress only "
                "diagnostic trace lines while preserving all helper behavior"
            ),
            "msize_suppression_summary": True,
            "translated_shard_prefix": "phase6ad_",
            "shard_reconstruction_identity_required": True,
        },
        "source_layout": source_layout,
        "runtime_policy": (
            "cross only hardware-observed ordinal 1 plus strict paired ordinal 4; "
            "do not guess hardware-facing AV 2/3; preserve all proven Phase 6AC "
            "graphics/memory semantics; cleanup is diagnostics/source-layout only"
        ),
    }

    (args.out_dir / "phase6ad-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6AD] AV SAVED-DATA + SAFE CLEANUP: READY")
    print("[Phase6AD] Ordinal 1 : strict +4 zero-arg AvGetSavedDataAddress")
    print("[Phase6AD] Ordinal 4 : strict +8 paired AvSetSavedDataAddress pre-armed")
    print("[Phase6AD] Ordinals 2/3: remain hard stops")
    print("[Phase6AD] _msize     : semantics unchanged; trace-only throttling")
    print("[Phase6AD] Shards     : phase6ad_* with byte-identity reconstruction")
    print("[Phase6AD] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
