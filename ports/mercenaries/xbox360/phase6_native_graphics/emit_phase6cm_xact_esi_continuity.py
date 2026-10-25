#!/usr/bin/env python3
"""Phase 6CM: guarded XACT ESI continuity experiment.

6CL hardware proved the exact failing chain at loc_002832CA:
  ESI=0
  READ32(00000000) -> FFFFFFFF (synthetic TIB/SEH terminator)
  READ32(FFFFFFFF) -> GUEST_FAULT

6CK also proved that ESI was the live XACT root (01B5C320) at loc_002832BB,
immediately before the failing block. 6CM therefore tests one narrow
hypothesis: the translated 002832BB path is incorrectly losing the XACT engine
pointer before 002832CA.

This phase starts from clean 6CJ semantics (no 6CK/6CL probes) and:
  * captures ESI at loc_002832BB;
  * at loc_002832CA, restores it only if current ESI == 0, the captured pointer
    is a bounded/aligned guest address, and it exactly matches the live XACTENG
    root pointer recorded by the inherited 6CE root probe.

No null-page behavior, SEH sentinel behavior, allocator semantics, APU model,
IRQL model, translated membership, or other hard fence is changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CJ-MM166-GENERAL-TAIL-20261025-A"
BUILD_TAG = "P6CM-XACT-ESI-CONTINUITY-20261025-A"
COOKIE_OLD = "phase6cj_env_build_cookie"
COOKIE_NEW = "phase6cm_env_build_cookie"

CAPTURE_VA = 0x002832BB
RESTORE_VA = 0x002832CA


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CM] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CM] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6cjGeneralTailLastActual = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CM] expected one 6CJ state anchor, found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6cmCaptureCount = 0u;
static uint32_t s_phase6cmRestoreChecks = 0u;
static uint32_t s_phase6cmRestoreSuccesses = 0u;
static uint32_t s_phase6cmCapturedEsi = 0u;
static uint32_t s_phase6cmLastCurrentEsi = 0u;
static uint32_t s_phase6cmLastRoot = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def instrument_capture(text: str) -> str:
    marker = f"loc_{CAPTURE_VA:08X}: ;\n"
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6CM] expected one capture label {marker.strip()}, "
            f"found {text.count(marker)}"
        )
    code = r'''    ++s_phase6cmCaptureCount;
    s_phase6cmCapturedEsi = esi;
    if (s_phase6cmCaptureCount <= 4u)
    {
        char phase6cmLine[480];
        sprintf(
            phase6cmLine,
            "P6CM XACT ESI CAPTURE va=002832BB count=%u esi=%08X root=%08X eax=%08X ecx=%08X edx=%08X edi=%08X esp=%08X",
            (unsigned int)s_phase6cmCaptureCount,
            (unsigned int)esi,
            (unsigned int)s_phase6ceXactLastEax,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)edi,
            (unsigned int)esp);
        trace(phase6cmLine);
    }
'''
    return text.replace(marker, marker + code, 1)


def instrument_restore(text: str) -> str:
    marker = f"loc_{RESTORE_VA:08X}: ;\n"
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6CM] expected one restore label {marker.strip()}, "
            f"found {text.count(marker)}"
        )
    code = r'''    ++s_phase6cmRestoreChecks;
    s_phase6cmLastCurrentEsi = esi;
    s_phase6cmLastRoot = s_phase6ceXactLastEax;

    if (esi == 0u &&
        s_phase6cmCapturedEsi != 0u &&
        (s_phase6cmCapturedEsi & 3u) == 0u &&
        s_phase6cmCapturedEsi <= 0x03FFFFFCu &&
        s_phase6cmCapturedEsi == s_phase6ceXactLastEax)
    {
        char phase6cmLine[560];
        uint32_t oldEsi = esi;
        esi = s_phase6cmCapturedEsi;
        ++s_phase6cmRestoreSuccesses;
        sprintf(
            phase6cmLine,
            "PASS: Phase 6CM restored XACT ESI at 002832CA old=%08X restored=%08X root=%08X captures=%u checks=%u successes=%u",
            (unsigned int)oldEsi,
            (unsigned int)esi,
            (unsigned int)s_phase6ceXactLastEax,
            (unsigned int)s_phase6cmCaptureCount,
            (unsigned int)s_phase6cmRestoreChecks,
            (unsigned int)s_phase6cmRestoreSuccesses);
        trace(phase6cmLine);
    }
    else if (s_phase6cmRestoreChecks <= 4u)
    {
        char phase6cmLine[560];
        sprintf(
            phase6cmLine,
            "P6CM XACT ESI RESTORE SKIP current=%08X captured=%08X root=%08X captures=%u checks=%u",
            (unsigned int)esi,
            (unsigned int)s_phase6cmCapturedEsi,
            (unsigned int)s_phase6ceXactLastEax,
            (unsigned int)s_phase6cmCaptureCount,
            (unsigned int)s_phase6cmRestoreChecks);
        trace(phase6cmLine);
    }
'''
    return text.replace(marker, marker + code, 1)


def insert_summary(text: str) -> str:
    marker = "P6CJ MM166 GENERAL TAIL:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CM] inherited 6CJ summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6CM] summary insertion point not found")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CM XACT ESI: captures=%u checks=%u successes=%u captured=%08X current_before=%08X root=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cmCaptureCount,\n'
        f'{indent}    (unsigned int)s_phase6cmRestoreChecks,\n'
        f'{indent}    (unsigned int)s_phase6cmRestoreSuccesses,\n'
        f'{indent}    (unsigned int)s_phase6cmCapturedEsi,\n'
        f'{indent}    (unsigned int)s_phase6cmLastCurrentEsi,\n'
        f'{indent}    (unsigned int)s_phase6cmLastRoot);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_policy(text: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0 or text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CM] expected exactly one runtime policy trace")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    policy = (
        "Phase 6CM tests hardware-proven XACT ESI continuity only: capture the live "
        "XACT root at 002832BB and restore it at 002832CA solely when ESI became zero "
        "and the captured pointer exactly matches the inherited XACTENG root; preserve "
        "6CJ allocator, APU GP/EP, guest IRQL, graphics/file/IDEX semantics, 32M "
        "watchdog, translated membership and every null/MMIO/guest-memory hard fence"
    )
    return text[:line_start] + indent + f'trace("Policy: {policy}");' + text[line_end:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CJ", "PHASE 6CM")
        .replace("Phase 6CJ", "Phase 6CM")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CM] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cm_base")
    p6bl = load(args.phase6bl_emitter, "phase6cm_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cj-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CM] missing cached 6CJ input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CM] cached Phase 6CJ identity mismatch")

    cj = manifest.get("phase6cj_mm166_general_tail", {})
    if (
        cj.get("translated_membership_changed") is not False
        or cj.get("apu_gp_ep_semantics_changed") is not False
        or cj.get("guest_irql_semantics_changed") is not False
        or cj.get("xacteng_membership_changed") is not False
        or cj.get("execution_budget_inherited") != 32000000
    ):
        raise SystemExit("[Phase6CM] inherited 6CJ policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "static uint32_t s_phase6ceXactLastEax = 0u;",
        "P6CJ XACTENG ROOT:",
        f"loc_{CAPTURE_VA:08X}: ;",
        f"loc_{RESTORE_VA:08X}: ;",
        "P6CJ MM166 GENERAL TAIL:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CM] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = instrument_capture(main_text)
    main_text = instrument_restore(main_text)
    main_text = insert_summary(main_text)
    main_text = patch_policy(main_text)

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CJ", "PHASE 6CM")
        .replace("Phase 6CJ", "Phase 6CM")
        .replace('"P6CJ ', '"P6CM ')
    )
    env_text = patch_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CM XACT ESI CAPTURE va=002832BB",
        "PASS: Phase 6CM restored XACT ESI at 002832CA",
        "P6CM XACT ESI RESTORE SKIP",
        "P6CM XACT ESI:",
        "P6CM MM166 GENERAL TAIL:",
        "P6CM APU DSP:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CM] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CM"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cm_xact_esi_continuity"] = {
        "source_phase": "6CJ",
        "phase6cl_hardware": {
            "build_tag": "P6CL-XACT-READ32-CHAIN-20261025-A",
            "entry_block": "0x002832CA",
            "entry_esi": "0x00000000",
            "read_chain": [
                {
                    "sequence": 1,
                    "address": "0x00000000",
                    "value": "0xFFFFFFFF",
                },
                {
                    "sequence": 2,
                    "address": "0xFFFFFFFF",
                    "result": "GUEST_FAULT",
                },
            ],
            "ticks": 26711574,
            "fault": 1,
        },
        "phase6ck_hardware": {
            "capture_block": "0x002832BB",
            "capture_esi": "0x01B5C320",
            "restore_block": "0x002832CA",
            "restore_entry_esi": "0x00000000",
        },
        "guard": {
            "capture_va": f"0x{CAPTURE_VA:08X}",
            "restore_va": f"0x{RESTORE_VA:08X}",
            "current_esi_must_be_zero": True,
            "captured_esi_must_be_nonzero": True,
            "captured_esi_must_be_dword_aligned": True,
            "captured_esi_must_be_inside_guest_ram": True,
            "captured_esi_must_equal_live_xact_root": True,
            "null_page_semantics_changed": False,
            "seh_terminator_semantics_changed": False,
        },
        "semantic_change": "single guarded ESI restore on one XACT basic-block edge",
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "apu_gp_ep_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "graphics_semantics_changed": False,
        "hard_fences_changed": False,
        "execution_budget_inherited": 32000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cm-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CM] 6CL proof: READ32(0)=FFFFFFFF then READ32(FFFFFFFF) faults")
    print("[Phase6CM] 6CK proof: ESI 01B5C320 at 002832BB -> ESI 0 at 002832CA")
    print("[Phase6CM] guarded restore armed only when captured ESI == inherited live XACT root")
    print("[Phase6CM] null-page / SEH terminator behavior remains unchanged")
    print("[Phase6CM] allocator/APU/IRQL/graphics semantics unchanged from 6CJ")
    print("[Phase6CM] 32M execution budget preserved")
    print("[Phase6CM] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
