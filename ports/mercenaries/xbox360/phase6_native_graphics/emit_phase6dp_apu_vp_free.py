#!/usr/bin/env python3
r"""Phase 6DP: model the first hardware-proven MCPX APU VP register read.

6DO hardware proved the allocator repair stack and eliminated the historical
CCCCCCD0 failure path. XACT remained alive and DSOUND advanced through APU core
initialization until the first access to the intentionally fenced VP window:

    READ32 FE820010

The MCPX APU BAR is based at FE800000. FE820010 therefore maps to VP PIO offset
0x0010, NV1BA0_PIO_FREE. xemu's VP model returns 0x80 for this register and
documents that it does not simulate the queue, so it pretends the queue is
always empty.

6DP models only this exact dword read:
    FE820010 -> 0x00000080

All other FE820000-FE82FFFF VP reads/writes remain fenced and continue through
the checked guest-access path. No VP voice methods, mixer, host audio output,
DSP execution, XACT refcount behavior, or guest-memory fences are widened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6DO-MM166-ALIGNMENT-GAP-REPAIR-20261026-A"
BUILD_TAG = "P6DP-APU-VP-FREE-20261026-A"
COOKIE_OLD = "phase6do_env_build_cookie"
COOKIE_NEW = "phase6dp_env_build_cookie"
EMITTER_REVISION = "6DP-R1"

VP_BASE = 0xFE820000
VP_FREE = 0x00000010
VP_FREE_ADDRESS = VP_BASE + VP_FREE
VP_FREE_VALUE = 0x00000080


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DP] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6DP] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6DP] function signature missing: {signature}")

    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6DP] opening brace missing: {signature}")

    depth = 0
    i = brace
    in_string = False
    quote = ""
    escape = False
    line_comment = False
    block_comment = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                in_string = False
            i += 1
            continue

        if c == "/" and n == "/":
            line_comment = True
            i += 2
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c in ('"', "'"):
            in_string = True
            quote = c
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1

    raise SystemExit(f"[Phase6DP] unterminated function: {signature}")


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6chApuFaultOwnerEntries = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DP] expected one APU state anchor, found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6dpVpFreeReads = 0u;
static uint32_t s_phase6dpVpLastAddress = 0u;
static uint32_t s_phase6dpVpLastValue = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def patch_read32(text: str) -> str:
    sig = "static uint32_t phase6ch_apu_read32(uint32_t address)"
    start, end = function_span(text, sig)
    body = text[start:end]

    old = "    return GUEST_READ32(address);\n"
    if body.count(old) != 1:
        raise SystemExit(
            f"[Phase6DP] expected one read32 fallback in helper, found {body.count(old)}"
        )

    new = """    if (address == 0xFE820010u)
    {
        uint32_t value = 0x00000080u;
        char line[256];
        ++s_phase6dpVpFreeReads;
        s_phase6dpVpLastAddress = address;
        s_phase6dpVpLastValue = value;
        sprintf(
            line,
            "P6DP APU VP READ32 addr=%08X method=NV1BA0_PIO_FREE value=%08X count=%u",
            (unsigned int)address,
            (unsigned int)value,
            (unsigned int)s_phase6dpVpFreeReads);
        trace(line);
        return value;
    }

    return GUEST_READ32(address);
"""
    body = body.replace(old, new, 1)
    return text[:start] + body + text[end:]


def insert_summary(text: str) -> str:
    marker = "P6DO APU DSP:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DP] inherited APU DSP summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6DP] summary insertion point missing")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]

    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DP APU VP: free_reads=%u last_addr=%08X last_value=%08X other_vp_accesses_fenced=1",\n'
        f'{indent}    (unsigned int)s_phase6dpVpFreeReads,\n'
        f'{indent}    (unsigned int)s_phase6dpVpLastAddress,\n'
        f'{indent}    (unsigned int)s_phase6dpVpLastValue);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DP] expected one 6DO build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DO", "PHASE 6DP")
        .replace("Phase 6DO", "Phase 6DP")
        .replace('"P6DO ', '"P6DP ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DP] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DO", "PHASE 6DP")
        .replace("Phase 6DO", "Phase 6DP")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dp_base")
    p6bl = load(args.phase6bl_emitter, "phase6dp_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6do-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DP] missing input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DO" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DP] cached 6DO identity mismatch")

    do = manifest.get("phase6do_mm166_alignment_gap_repair") or {}
    if (
        do.get("repair", {}).get("exact_end_requirement_removed") is not True
        or do.get("xact_refcount_semantics_changed") is not False
        or do.get("destructor_suppressed") is not False
        or do.get("free_suppressed") is not False
        or do.get("guest_memory_fences_changed") is not False
    ):
        raise SystemExit("[Phase6DP] inherited 6DO policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "static uint32_t phase6ch_apu_read32(uint32_t address)",
        "phase6ci_dsp_range(address, 4u",
        "return GUEST_READ32(address);",
        "P6DO APU CORE:",
        "P6DO APU DSP:",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DP] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = patch_read32(main_text)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "static uint32_t s_phase6dpVpFreeReads = 0u;",
        "address == 0xFE820010u",
        "0x00000080u",
        "NV1BA0_PIO_FREE",
        "P6DP APU VP READ32",
        "P6DP APU VP:",
        "other_vp_accesses_fenced=1",
        "P6DP APU CORE:",
        "P6DP APU DSP:",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DP] generated source lost marker: {marker}")

    # Prove only the exact VP FREE read was opened. The helper must retain its
    # checked fallback for every other FE82 access.
    start, end = function_span(
        main_text, "static uint32_t phase6ch_apu_read32(uint32_t address)"
    )
    helper = main_text[start:end]
    if helper.count("address == 0xFE820010u") != 1:
        raise SystemExit("[Phase6DP] exact VP FREE gate count mismatch")
    if helper.count("return GUEST_READ32(address);") != 1:
        raise SystemExit("[Phase6DP] checked read32 fallback was not preserved")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6DP", "build_tag": BUILD_TAG})
    manifest["phase6dp_apu_vp_free"] = {
        "source_phase": "6DO",
        "hardware_proof": {
            "old_failure_eliminated": "0xCCCCCCD0",
            "xact_final_release_observed": False,
            "xact_global_zero_write_observed": False,
            "new_boundary": "0xFE820010",
            "access": "READ32",
            "ticks": 26712001,
            "translated_caller": "0x0023A3CE",
            "apu_core_reads_before_boundary": 9,
            "apu_core_writes_before_boundary": 47,
        },
        "register_identity": {
            "apu_base": "0xFE800000",
            "vp_base": "0xFE820000",
            "address": "0xFE820010",
            "vp_offset": "0x00000010",
            "name": "NV1BA0_PIO_FREE",
            "read_value": "0x00000080",
            "reference_model": "xemu MCPX APU VP",
            "reference_semantics": "queue not simulated; report always empty",
        },
        "scope": {
            "exact_read32_only": True,
            "other_vp_reads_fenced": True,
            "all_vp_writes_fenced": True,
            "voice_methods_modeled": False,
            "actual_audio_processing": False,
            "actual_host_audio_output": False,
            "dsp_execution_changed": False,
        },
        "xact_refcount_semantics_changed": False,
        "destructor_suppressed": False,
        "free_suppressed": False,
        "dispatch_semantics_changed": False,
        "guest_memory_fences_changed": False,
        "generated_c4146_scope_inherited": True,
        "execution_budget_inherited": 64000000,
        "source_layout": layout,
    }
    (args.out_dir / "phase6dp-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6DP] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DP] 6DO hardware: historical CCCCCCD0 boundary eliminated")
    print("[Phase6DP] 6DO hardware: no XACT final Release and no global zero write")
    print("[Phase6DP] new boundary: READ32 FE820010 after APU core initialization")
    print("[Phase6DP] FE820010 = VP NV1BA0_PIO_FREE")
    print("[Phase6DP] modeled value: 00000080 (queue reported empty)")
    print("[Phase6DP] all other VP accesses remain fenced")
    print("[Phase6DP] money line:")
    print("[Phase6DP]   P6DP APU VP READ32 addr=FE820010 method=NV1BA0_PIO_FREE value=00000080 count=1")
    print("[Phase6DP] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
