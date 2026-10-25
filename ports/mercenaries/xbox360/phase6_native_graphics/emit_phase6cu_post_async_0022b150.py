#!/usr/bin/env python3
r"""Phase 6CU: continue the post-XACT async path through maintained GetLastError.

6CT-R5 hardware proved:
  * XACT stream root 0x0027E780 entered;
  * shl_streams.xwb opened on async handle options=0x48;
  * the 2048-byte NtReadFile completed successfully;
  * final IOSB status=STATUS_SUCCESS and guest return=STATUS_PENDING;
  * RtlNtStatusToDosError mapped STATUS_PENDING to ERROR_IO_PENDING (997);
  * SetLastError stored 997;
  * execution then stopped cleanly at DIRECT_FRONTIER
        caller=0x0023A3CE -> target=0x0022B150
    at ticks=27,019,869 trace=1,071,512 fault=0.

0x0022B150 is not an unknown translated body. It is the maintained
support-owned GetLastError helper paired with the already-maintained
SetLastError at 0x0022B178. 6CU therefore exposes that canonical helper through
phase4c_lookup_pack_func instead of emitting a duplicate translated body.

All 6CT async-read, Partition0, XACT, D3D/XGRPH, watchdog, and hard-fence
semantics are preserved.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CT-XACT-ASYNC-READ-20261025-A"
BUILD_TAG = "P6CU-POST-ASYNC-GETLASTERROR-0022B150-20261025-A"
COOKIE_OLD = "phase6ct_env_build_cookie"
COOKIE_NEW = "phase6cu_env_build_cookie"
EMITTER_REVISION = "6CU-R3"

TARGET = 0x0022B150
CALLER = 0x0023A3CE


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CU] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6CU] function missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6CU] function brace missing: {signature}")

    depth = 0
    for i in range(brace, len(text)):
        ch = text[i]
        if ch == "{":
            depth += 1
        elif ch == "}":
            depth -= 1
            if depth == 0:
                end = i + 1
                if end < len(text) and text[end] == "\n":
                    end += 1
                return start, end
    raise SystemExit(f"[Phase6CU] function unterminated: {signature}")


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6ctAsyncReadCalls;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CU] expected one 6CT async-state anchor, "
            f"found {text.count(anchor)}"
        )
    state = (
        anchor
        + "static uint32_t s_phase6cuGetLastErrorCalls;\n"
        + "static uint32_t s_phase6cuGetLastErrorLastValue;\n"
    )
    return text.replace(anchor, state, 1)


def instrument_get_last_error(text: str) -> str:
    signature = "static void sub_0022B150(void)"
    start, end = function_span(text, signature)
    body = text[start:end]

    for marker in (
        "g_eax = s_phase4cLastError;",
        "g_esp += 4u;",
    ):
        if marker not in body:
            raise SystemExit(
                f"[Phase6CU] maintained GetLastError body lost marker: {marker}"
            )

    brace = body.find("{")
    if brace < 0:
        raise SystemExit("[Phase6CU] GetLastError body brace missing")

    probe = r'''
    char phase6cuLine[320];

    RECOMP_TRACE_FUNC(0x0022B150u);
    ++s_phase6cuGetLastErrorCalls;
    s_phase6cuGetLastErrorLastValue = s_phase4cLastError;

    sprintf(
        phase6cuLine,
        "PASS: Phase 6CU maintained GetLastError value=%08X calls=%u new_esp=%08X",
        (unsigned int)s_phase4cLastError,
        (unsigned int)s_phase6cuGetLastErrorCalls,
        (unsigned int)(g_esp + 4u));
    trace(phase6cuLine);
'''
    body = body[:brace + 1] + probe + body[brace + 1:]
    return text[:start] + body + text[end:]


def expose_support_target(text: str) -> str:
    signature = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\\n{"
    start, end = function_span(text, signature)
    body = text[start:end]

    case = "    case 0x0022B150u: return sub_0022B150;\n"
    if case in body:
        raise SystemExit(
            "[Phase6CU] GetLastError target already exists in pack lookup; "
            "hardware frontier requires dispatch bookkeeping diagnosis instead"
        )

    default = "    default: return (recomp_func_t)0;"
    if body.count(default) != 1:
        raise SystemExit(
            f"[Phase6CU] expected one pack-lookup default, found {body.count(default)}"
        )

    body = body.replace(default, case + default, 1)
    return text[:start] + body + text[end:]


def insert_summary(text: str) -> str:
    marker = "P6CT ASYNC STREAM READ:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CU] inherited 6CT async summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6CU] final summary insertion point missing")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CU GETLASTERROR: calls=%u last_value=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cuGetLastErrorCalls,\n'
        f'{indent}    (unsigned int)s_phase6cuGetLastErrorLastValue);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cu_base")
    p6bl = load(args.phase6bl_emitter, "phase6cu_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6ct-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CU] missing cached 6CT input: {path}")

    text = main_path.read_text(encoding="utf-8")
    env = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CT" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CU] cached 6CT identity mismatch")

    inherited = manifest.get("phase6ct_xact_async_read", {})
    policy = inherited.get("policy", {})
    if (
        inherited.get("execution_budget_inherited") != 64000000
        or inherited.get("translated_pack_changed") is not False
        or inherited.get("graphics_bridge_semantics_changed") is not False
        or inherited.get("hard_fences_weakened") is not False
        or policy.get("immediate_host_completion") is not True
        or policy.get("async_guest_return") != "STATUS_PENDING"
        or policy.get("apc_context_without_callback_allowed") is not True
    ):
        raise SystemExit("[Phase6CU] inherited 6CT policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "static void sub_0022B150(void)",
        "g_eax = s_phase4cLastError;",
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)",
        "P6CT ASYNC STREAM READ:",
        "PASS: Phase 6CT XACT async NtReadFile immediate completion",
        "partition0Config",
        "P6CT PIXEL CHASE:",
        "P6CT PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CU] inherited marker missing: {marker}")

    text = install_state(text)
    text = instrument_get_last_error(text)
    text = expose_support_target(text)
    text = insert_summary(text)

    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6CU] expected one inherited build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    env = env.replace(COOKIE_OLD, COOKIE_NEW)

    text = (
        text.replace("PHASE 6CT", "PHASE 6CU")
        .replace("Phase 6CT", "Phase 6CU")
        .replace('"P6CT ', '"P6CU ')
    )
    env = (
        env.replace("PHASE 6CT", "PHASE 6CU")
        .replace("Phase 6CT", "Phase 6CU")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "case 0x0022B150u: return sub_0022B150;",
        "PASS: Phase 6CU maintained GetLastError",
        "P6CU GETLASTERROR:",
        "P6CU ASYNC STREAM READ:",
        "PASS: Phase 6CU XACT async NtReadFile immediate completion",
        "partition0Config",
        "P6CU PIXEL CHASE:",
        "P6CU PRESENT PROXIMITY:",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CU] generated source lost marker: {marker}")

    if text.count("case 0x0022B150u: return sub_0022B150;") != 1:
        raise SystemExit("[Phase6CU] GetLastError lookup dispatch count mismatch")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env, encoding="utf-8")

    manifest.update({
        "phase": "6CU",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6cu_post_async_get_last_error"] = {
        "source_phase": "6CT",
        "phase6ct_hardware": {
            "boundary_kind": "DIRECT_FRONTIER",
            "caller": "0x0023A3CE",
            "target": "0x0022B150",
            "ticks": 27019869,
            "trace": 1071512,
            "fault": 0,
            "async_read_calls": 1,
            "async_read_successes": 1,
            "async_pending_returns": 1,
            "async_completion_status": "0x00000000",
            "async_bytes": 2048,
            "async_guest_return": "0x00000103",
            "xact_root_entries": 1,
            "d3d_device_calls": 1,
            "guest_device": "0x00299380",
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "target": f"0x{TARGET:08X}",
        "target_role": "maintained support-owned GetLastError",
        "frontier_caller": f"0x{CALLER:08X}",
        "dispatch_policy": {
            "duplicate_translated_body_emitted": False,
            "canonical_support_helper_reused": True,
            "phase4c_lookup_pack_func_extended": True,
            "paired_set_last_error": "0x0022B178",
            "shared_state": "s_phase4cLastError",
        },
        "execution_budget_inherited": 64000000,
        "translated_pack_changed": False,
        "async_read_semantics_changed": False,
        "partition0_semantics_changed": False,
        "xact_semantics_changed": False,
        "graphics_bridge_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cu-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CU] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CU] TARGET 0022B150: canonical GetLastError support dispatch armed")
    print("[Phase6CU] paired SetLastError 0022B178 shared state preserved")
    print("[Phase6CU] 6CT async XACT stream-read semantics preserved")
    print("[Phase6CU] Partition0 + XACT + D3D/XGRPH semantics preserved")
    print("[Phase6CU] display/pixel telemetry preserved")
    print("[Phase6CU] 64M watchdog preserved")
    print("[Phase6CU] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
