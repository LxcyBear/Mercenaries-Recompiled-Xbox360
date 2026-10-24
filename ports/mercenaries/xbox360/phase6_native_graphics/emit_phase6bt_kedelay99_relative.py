#!/usr/bin/env python3
"""Phase 6BT: native ordinal-99 KeDelayExecutionThread relative-delay continuation.

6BS hardware proved ordinal 226 NtSetInformationFile class-14 continuation,
then consumed game:\\xesrb.tga completely: 786432 bytes followed by the final
44 bytes, exactly matching the reported 786476-byte EOF. Execution re-entered
XGRPH and then stopped at a fault-free ICALL_SAFE to 0x80000063.

Ordinal 99 is KeDelayExecutionThread. The observed frame is canonical:
savedEsp-callEsp == 16 bytes, matching return slot + WaitMode + Alertable +
Interval*. This stage supports only well-formed non-alertable/alertable scalar
mode values and non-positive (relative/zero) delays. Positive absolute delays,
very long delays, malformed frames and bad guest pointers remain fenced.

The delay conversion is the same hardware-proven Phase-4B rule: negative
100ns units are rounded up to milliseconds and executed with Sleep(); a zero
delay yields with SwitchToThread().
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6BS-NTSETINFO226-POSITION-20261024-A"
BUILD_TAG = "P6BT-KEDELAY99-RELATIVE-20261024-A"
COOKIE_OLD = "phase6bs_env_build_cookie"
COOKIE_NEW = "phase6bt_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6BT] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6BT] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6BT] RECOMP_ICALL_SAFE macro start missing")

    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6BT] RECOMP_ITAIL anchor missing after RECOMP_ICALL_SAFE")

    macro = text[macro_start:next_macro]
    if "_phase4c_target == 0x80000063u" in macro:
        raise SystemExit("[Phase6BT] ordinal 99 is already dispatched by RECOMP_ICALL_SAFE")

    bs = chr(92)
    inherited = "if (_phase4c_target == 0x800000E2u) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6BT] inherited 6BS ordinal-226 dispatch head missing")

    replacement = (
        "if (_phase4c_target == 0x80000063u) { " + bs + "\n"
        "        phase6bt_ke_delay_execution_thread((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x800000E2u) { " + bs
    )
    patched = macro[:pos] + replacement + macro[pos + len(inherited):]
    if patched.count("_phase4c_target == 0x80000063u") != 1:
        raise SystemExit("[Phase6BT] ordinal-99 dispatch insertion did not produce exactly one branch")

    return text[:macro_start] + patched + text[next_macro:]


def install_delay_support(text: str) -> str:
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6BT] expected one translated-pack lookup definition anchor, found {text.count(anchor)}"
        )

    support = r'''static uint32_t s_phase6btKeDelayCallCount = 0u;
static uint32_t s_phase6btKeDelaySuccessCount = 0u;
static uint32_t s_phase6btKeDelayLastWaitMode = 0u;
static uint32_t s_phase6btKeDelayLastAlertable = 0u;
static uint32_t s_phase6btKeDelayLastIntervalLow = 0u;
static uint32_t s_phase6btKeDelayLastIntervalHigh = 0u;
static uint32_t s_phase6btKeDelayLastMilliseconds = 0u;

static void phase6bt_ke_delay_execution_thread(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t waitMode;
    uint32_t alertable;
    uint32_t intervalVa;
    uint32_t intervalLow;
    uint32_t intervalHigh;
    unsigned __int64 intervalRaw;
    __int64 interval;
    unsigned __int64 ticks100ns;
    unsigned __int64 milliseconds64;
    DWORD milliseconds = 0u;
    BYTE* intervalPtr;
    char line[768];

    if (savedEsp != callEsp + 16u)
    {
        sprintf(
            line,
            "KeDelayExecutionThread FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=16",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000063u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp + 0u);
    waitMode = GUEST_READ32(callEsp + 4u);
    alertable = GUEST_READ32(callEsp + 8u);
    intervalVa = GUEST_READ32(callEsp + 12u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000063u,
            savedEsp);
        return;
    }

    intervalPtr = intervalVa ? guest_ptr((DWORD)intervalVa, 8u) : NULL;
    if (intervalPtr == NULL)
    {
        trace("KeDelayExecutionThread REJECTED: interval pointer is null/invalid");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000063u,
            savedEsp);
        return;
    }

    intervalLow = GUEST_READ32(intervalVa + 0u);
    intervalHigh = GUEST_READ32(intervalVa + 4u);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x80000063u,
            savedEsp);
        return;
    }

    intervalRaw =
        ((unsigned __int64)intervalHigh << 32) |
        (unsigned __int64)intervalLow;
    interval = (__int64)intervalRaw;

    sprintf(
        line,
        "KeDelayExecutionThread LIVE FRAME: ret=%08X wait_mode=%u alertable=%u interval_ptr=%08X interval=%08X%08X esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)waitMode,
        (unsigned int)alertable,
        (unsigned int)intervalVa,
        (unsigned int)intervalHigh,
        (unsigned int)intervalLow,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (returnSlot != 0u || waitMode > 1u || alertable > 1u)
    {
        trace("KeDelayExecutionThread REJECTED: noncanonical return/mode/alertable values");
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x80000063u,
            savedEsp);
        return;
    }

    if (interval > 0)
    {
        trace("KeDelayExecutionThread UNSUPPORTED: positive absolute interval remains fenced in Phase 6BT");
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x80000063u,
            savedEsp);
        return;
    }

    if (interval < 0)
    {
        /* Safe absolute magnitude without overflowing INT64_MIN. */
        ticks100ns =
            (unsigned __int64)(-(interval + 1i64)) + 1ui64;
        milliseconds64 = (ticks100ns + 9999ui64) / 10000ui64;

        /*
         * Hardware-bring-up fence: do not let an unexpected retail wait stall
         * the console for an unbounded period. This is not a semantic clamp;
         * longer waits remain unsupported and escape visibly.
         */
        if (milliseconds64 > 10000ui64)
        {
            sprintf(
                line,
                "KeDelayExecutionThread UNSUPPORTED: relative delay %I64u ms exceeds Phase 6BT 10s hardware bound",
                milliseconds64);
            trace(line);
            phase4c_escape(
                PHASE4C_BOUNDARY_ICALL_SAFE,
                0x80000063u,
                savedEsp);
            return;
        }

        milliseconds = (DWORD)milliseconds64;
        if (milliseconds != 0u)
            Sleep(milliseconds);
        else
            SwitchToThread();
    }
    else
    {
        SwitchToThread();
    }

    ++s_phase6btKeDelayCallCount;
    ++s_phase6btKeDelaySuccessCount;
    s_phase6btKeDelayLastWaitMode = waitMode;
    s_phase6btKeDelayLastAlertable = alertable;
    s_phase6btKeDelayLastIntervalLow = intervalLow;
    s_phase6btKeDelayLastIntervalHigh = intervalHigh;
    s_phase6btKeDelayLastMilliseconds = milliseconds;

    g_eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6BT KeDelayExecutionThread relative continuation interval=%08X%08X ms=%u wait_mode=%u alertable=%u calls=%u new_esp=%08X",
        (unsigned int)intervalHigh,
        (unsigned int)intervalLow,
        (unsigned int)milliseconds,
        (unsigned int)waitMode,
        (unsigned int)alertable,
        (unsigned int)s_phase6btKeDelayCallCount,
        (unsigned int)g_esp);
    trace(line);
}

'''
    return text.replace(anchor, support + anchor, 1)


def insert_arm_trace(text: str) -> str:
    marker = '    trace("PASS: Phase 6BS ordinal 226 NtSetInformationFile class-14 position continuation armed");\n'
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6BT] expected one inherited ordinal-226 arm trace, found {text.count(marker)}"
        )
    addition = (
        marker
        + '    trace("PASS: Phase 6BS ordinal 99 KeDelayExecutionThread relative-delay continuation armed");\n'
    )
    return text.replace(marker, addition, 1)


def insert_summary(text: str) -> str:
    marker = "P6BS NTSETINFO226:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6BT] inherited 6BS NtSetInformationFile summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6BT] could not locate inherited 6BS summary block")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6BS KEDELAY99: calls=%u successes=%u wait_mode=%u alertable=%u interval=%08X%08X ms=%u",\n'
        f'{indent}    (unsigned int)s_phase6btKeDelayCallCount,\n'
        f'{indent}    (unsigned int)s_phase6btKeDelaySuccessCount,\n'
        f'{indent}    (unsigned int)s_phase6btKeDelayLastWaitMode,\n'
        f'{indent}    (unsigned int)s_phase6btKeDelayLastAlertable,\n'
        f'{indent}    (unsigned int)s_phase6btKeDelayLastIntervalHigh,\n'
        f'{indent}    (unsigned int)s_phase6btKeDelayLastIntervalLow,\n'
        f'{indent}    (unsigned int)s_phase6btKeDelayLastMilliseconds);\n'
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

    base = load(args.base_emitter, "phase6bt_base")
    p6bl = load(args.phase6bl_emitter, "phase6bt_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6bs-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6BT] cached Phase 6BS input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6BS" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6BT] cached Phase 6BS identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6BT] inherited membership accounting mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x800000E2u",
        "phase6bs_nt_set_information_file((uint32_t)(saved_esp))",
        "PASS: Phase 6BS NtSetInformationFile position continuation",
        "P6BS NTSETINFO226:",
        "P6BS POST-PBL FRONTIER 00209A70:",
        "P6BS PBL CHECKPOINT:",
        "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BT] inherited 6BS marker missing: {marker}")

    if "_phase4c_target == 0x80000063u" in main_text or "phase6bt_ke_delay_execution_thread" in main_text:
        raise SystemExit(
            "[Phase6BT] ordinal 99 dispatch/support already appears in inherited source"
        )

    main_text = install_delay_support(main_text)
    main_text = patch_icall_dispatch(main_text)
    main_text = insert_arm_trace(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6BT ordinal-99 KeDelayExecutionThread canonical 16-byte frame; relative/zero delay only with 10s hardware bound; preserve 6BS file-position continuation, both ABI repairs and all GPU semantics/hard fences",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6BS", "PHASE 6BT")
        .replace("Phase 6BS", "Phase 6BT")
        .replace('"P6BS ', '"P6BT ')
    )
    env_text = (
        env_text.replace("PHASE 6BS", "PHASE 6BT")
        .replace("Phase 6BS", "Phase 6BT")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x80000063u",
        "phase6bt_ke_delay_execution_thread((uint32_t)(saved_esp))",
        "KeDelayExecutionThread LIVE FRAME:",
        "interval > 0",
        "milliseconds64 > 10000ui64",
        "PASS: Phase 6BT KeDelayExecutionThread relative continuation",
        "P6BT KEDELAY99:",
        "PASS: Phase 6BT ordinal 99 KeDelayExecutionThread relative-delay continuation armed",
        "P6BT NTSETINFO226:",
        "P6BT POST-PBL FRONTIER 00209A70:",
        "P6BT PBL CHECKPOINT:",
        "NtSetInformationFile LIVE FRAME:",
        "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
        "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
        "phase6be_pfifo_idle_write32(address, value)",
        "phase6bj_pfb_zcomp_write32",
        "phase6bg_pfb_tile_write32",
        "phase6bh_pgraph_scoped_write32",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6BT] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6BT",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6bt_kedelay99_relative"] = {
        "source_phase": "6BS",
        "phase6bs_hardware": {
            "ntsetinfo226_calls": 3,
            "ntsetinfo226_successes": 3,
            "ntsetinfo226_last_class": 14,
            "ntsetinfo226_last_position": "0x00000000000C0000",
            "xesrb_eof_bytes": 786476,
            "xesrb_bulk_read_bytes": 786432,
            "xesrb_tail_read_bytes": 44,
            "xesrb_complete_file_consumed": True,
            "pbl_checkpoint_calls": 4,
            "post_pbl_root_00209a70_entries": 2,
            "xgrph_frontier_entries": 7,
            "boundary_kind": "ICALL_SAFE",
            "kernel_target": "0x80000063",
            "kernel_ordinal": 99,
            "kernel_name": "KeDelayExecutionThread",
            "caller": "0x0023A3CE",
            "call_esp": "0x008BF8FC",
            "saved_esp": "0x008BF90C",
            "observed_frame_bytes": 16,
            "canonical_frame_bytes": 16,
            "fault": 0,
            "ticks": 954210,
        },
        "continuation": {
            "relative_negative_delays_supported": True,
            "zero_delay_yields": True,
            "positive_absolute_delays_fenced": True,
            "max_relative_delay_ms": 10000,
            "wait_mode_range": [0, 1],
            "alertable_range": [0, 1],
            "uses_phase4b_proven_sleep_conversion": True,
        },
        "translated_membership_changed": False,
        "all_phase6bs_file_and_abi_repairs_inherited": True,
        "all_phase6bs_gpu_bridges_inherited": True,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6bt-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6BT] 6BS hardware: NtSetInformationFile class-14 continuation PASS x3")
    print("[Phase6BT] 6BS hardware: xesrb.tga fully consumed 786432 + 44 = 786476 bytes")
    print("[Phase6BT] next boundary: ICALL_SAFE 80000063 ordinal 99 KeDelayExecutionThread fault=0")
    print("[Phase6BT] observed frame: 16 bytes, exactly canonical return + three arguments")
    print("[Phase6BT] continuation: negative relative/zero delay only; positive absolute and >10s remain fenced")
    print("[Phase6BT] translated membership unchanged")
    print("[Phase6BT] all 6BS file/GPU/allocator/8M-budget invariants inherited unchanged")
    print("[Phase6BT] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
