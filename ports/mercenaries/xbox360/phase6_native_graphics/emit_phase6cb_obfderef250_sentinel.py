#!/usr/bin/env python3
"""Phase 6CB: ordinal-250 ObfDereferenceObject sentinel-release continuation.

6CA hardware proved the complete guest-IRQL path:
  KeRaiseIrqlToDpcLevel: 0 -> 2
  IdexChannelObject empty KDEVICE_QUEUE traversal
  KfLowerIrql: 2 -> 0
and immediately reached 0x800000FA, Xbox ordinal 250
ObfDereferenceObject, with a canonical 4-byte FASTCALL frame.

The live ECX value is 0x04000000, exactly the diagnostic FILE_OBJECT sentinel
returned by the Phase-6BV ObReferenceObjectByHandle continuation. Retail did
not dereference FILE_OBJECT fields; it only releases the synthetic reference.

Model that exact proven class as a guest-only no-op release. Never touch host
object refcounts and never dereference the unmapped sentinel.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CA-KFLOWERIRQL161-20261024-A"
BUILD_TAG = "P6CB-OBFDEREF250-SENTINEL-20261024-A"
COOKIE_OLD = "phase6ca_env_build_cookie"
COOKIE_NEW = "phase6cb_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CB] could not load {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_unique(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CB] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6CB] RECOMP_ICALL_SAFE macro start missing")
    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6CB] RECOMP_ITAIL anchor missing")

    macro = text[macro_start:next_macro]
    if "_phase4c_target == 0x800000FAu" in macro:
        raise SystemExit("[Phase6CB] ordinal 250 already dispatched")

    bs = chr(92)
    inherited = "if (_phase4c_target == 0x800000A1u) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6CB] inherited ordinal-161 dispatch head missing")

    replacement = (
        "if (_phase4c_target == 0x800000FAu) { " + bs + "\n"
        "        phase6cb_obf_dereference_object((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x800000A1u) { " + bs
    )
    macro = macro[:pos] + replacement + macro[pos + len(inherited):]

    if macro.count("_phase4c_target == 0x800000FAu") != 1:
        raise SystemExit("[Phase6CB] ordinal-250 dispatch insertion failed")

    return text[:macro_start] + macro + text[next_macro:]


def install_support(text: str) -> str:
    # Insert after the complete inherited 6BV/6CA support block. 6CB reads
    # s_phase6bvObRefContinuationCount and PHASE6BV_FILE_OBJECT_SENTINEL, so
    # placing this helper before those declarations breaks VS2017 C++ name
    # lookup even though emission-time marker checks still pass.
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CB] expected one post-ObRef support anchor, found {text.count(anchor)}"
        )

    support = r'''static uint32_t s_phase6cbObfDereferenceCallCount = 0u;
static uint32_t s_phase6cbObfDereferenceSuccessCount = 0u;
static uint32_t s_phase6cbObfDereferenceLastObject = 0u;

static void phase6cb_obf_dereference_object(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t object;
    char line[512];

    if (savedEsp != callEsp + 4u)
    {
        sprintf(
            line,
            "ObfDereferenceObject FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=4",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000FAu,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000FAu,
            savedEsp);
        return;
    }

    ++s_phase6cbObfDereferenceCallCount;
    object = g_ecx;

    sprintf(
        line,
        "ObfDereferenceObject LIVE FRAME: ret=%08X object=%08X obref_calls=%u releases=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)object,
        (unsigned int)s_phase6bvObRefContinuationCount,
        (unsigned int)s_phase6cbObfDereferenceSuccessCount,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    /*
     * This continuation is intentionally restricted to the exact synthetic
     * FILE_OBJECT sentinel created by the proven ordinal-246 continuation.
     * The sentinel is unmapped by design, so never read/write through it.
     */
    if (returnSlot != 0u ||
        object != PHASE6BV_FILE_OBJECT_SENTINEL ||
        s_phase6bvObRefContinuationCount == 0u ||
        s_phase6cbObfDereferenceSuccessCount >= s_phase6bvObRefContinuationCount)
    {
        trace("ObfDereferenceObject REJECTED: outside proven synthetic FILE_OBJECT sentinel reference class");
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x800000FAu,
            savedEsp);
        return;
    }

    ++s_phase6cbObfDereferenceSuccessCount;
    s_phase6cbObfDereferenceLastObject = object;

    /* VOID FASTCALL: preserve EAX; one return slot and no stack arguments. */
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6CB ObfDereferenceObject sentinel release object=%08X calls=%u successes=%u outstanding=%u new_esp=%08X",
        (unsigned int)object,
        (unsigned int)s_phase6cbObfDereferenceCallCount,
        (unsigned int)s_phase6cbObfDereferenceSuccessCount,
        (unsigned int)(s_phase6bvObRefContinuationCount - s_phase6cbObfDereferenceSuccessCount),
        (unsigned int)g_esp);
    trace(line);
}

'''
    text = text.replace(anchor, support + anchor, 1)

    # Compile-order proof: every inherited symbol referenced by the new helper
    # must be declared before the helper definition in the emitted C++.
    helper_pos = text.find("static void phase6cb_obf_dereference_object")
    obref_pos = text.find("static uint32_t s_phase6bvObRefContinuationCount")
    sentinel_pos = text.find("#define PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u")
    lookup_pos = text.find(anchor)
    if min(helper_pos, obref_pos, sentinel_pos, lookup_pos) < 0:
        raise SystemExit("[Phase6CB] compile-order proof marker missing")
    if not (obref_pos < helper_pos and sentinel_pos < helper_pos < lookup_pos):
        raise SystemExit(
            "[Phase6CB] compile-order proof failed: 6BV sentinel state must precede 6CB helper"
        )

    return text


def insert_arm_trace(text: str) -> str:
    marker = '    trace("PASS: Phase 6CA ordinal 161 KfLowerIrql guest-IRQL continuation armed");\n'
    if text.count(marker) != 1:
        raise SystemExit("[Phase6CB] inherited ordinal-161 arm trace missing")

    return text.replace(
        marker,
        marker
        + '    trace("PASS: Phase 6CB ordinal 250 ObfDereferenceObject synthetic FILE_OBJECT release armed");\n',
        1,
    )


def insert_summary(text: str) -> str:
    marker = "P6CA KFLOWERIRQL161:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CB] inherited KfLowerIrql summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CB] could not locate inherited IRQL summary block")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CB OBFDEREF250: calls=%u successes=%u object=%08X obref_calls=%u outstanding=%u",\n'
        f'{indent}    (unsigned int)s_phase6cbObfDereferenceCallCount,\n'
        f'{indent}    (unsigned int)s_phase6cbObfDereferenceSuccessCount,\n'
        f'{indent}    (unsigned int)s_phase6cbObfDereferenceLastObject,\n'
        f'{indent}    (unsigned int)s_phase6bvObRefContinuationCount,\n'
        f'{indent}    (unsigned int)(s_phase6bvObRefContinuationCount - s_phase6cbObfDereferenceSuccessCount));\n'
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

    base = load(args.base_emitter, "phase6cb_base")
    p6bl = load(args.phase6bl_emitter, "phase6cb_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6ca-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CB] cached Phase 6CA input missing: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    env_before = env_text
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CA" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CB] cached Phase 6CA identity mismatch")

    members = list(manifest.get("members", []))
    pack_count = int(manifest.get("pack_members", 0))
    if not members or pack_count != len(members):
        raise SystemExit("[Phase6CB] inherited membership accounting mismatch")

    lower = manifest.get("phase6ca_kf_lower_irql", {})
    if (
        lower.get("phase6bz_hardware", {}).get("next_boundary_target") != "0x800000A1"
        or lower.get("continuation", {}).get("expected_first_new_irql") != 0
    ):
        raise SystemExit("[Phase6CB] inherited 6CA KfLowerIrql identity mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "_phase4c_target == 0x800000A1u",
        "PHASE6BV_FILE_OBJECT_SENTINEL 0x04000000u",
        "s_phase6bvObRefContinuationCount",
        "PASS: Phase 6CA KfLowerIrql guest continuation",
        "P6CA KFLOWERIRQL161:",
        "P6CA IDEX QUEUE HEAD:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CB] inherited 6CA marker missing: {marker}")

    main_text = install_support(main_text)
    main_text = patch_icall_dispatch(main_text)
    main_text = insert_arm_trace(main_text)
    main_text = insert_summary(main_text)

    main_text = p6bl.replace_policy_line(
        main_text,
        "Policy: Phase 6CB ordinal-250 ObfDereferenceObject FASTCALL exact synthetic FILE_OBJECT sentinel release; 6CA proved guest IRQL 2->0 and next target 800000FA with ECX=04000000; never dereference sentinel or touch host object refs; preserve all graphics/file/fence/allocator/8M semantics",
    )
    main_text = replace_unique(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    env_text = env_text.replace(COOKIE_OLD, COOKIE_NEW)

    main_text = (
        main_text.replace("PHASE 6CA", "PHASE 6CB")
        .replace("Phase 6CA", "Phase 6CB")
        .replace('"P6CA ', '"P6CB ')
    )
    env_text = (
        env_text.replace("PHASE 6CA", "PHASE 6CB")
        .replace("Phase 6CA", "Phase 6CB")
    )

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x800000FAu",
        "phase6cb_obf_dereference_object",
        "ObfDereferenceObject LIVE FRAME:",
        "PASS: Phase 6CB ObfDereferenceObject sentinel release",
        "P6CB OBFDEREF250:",
        "P6CB KFLOWERIRQL161:",
        "P6CB IDEX QUEUE HEAD:",
        "#define PHASE4C_EXEC_BUDGET 8000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CB] generated source lost marker: {marker}")

    expected_env = (
        env_before.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6CA", "PHASE 6CB")
        .replace("Phase 6CA", "Phase 6CB")
    )
    if env_text != expected_env:
        raise SystemExit(
            "[Phase6CB] phase5_env.cpp changed beyond expected tag/cookie renames"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update(
        {
            "phase": "6CB",
            "build_tag": BUILD_TAG,
            "pack_members": pack_count,
            "members": members,
        }
    )
    manifest["phase6cb_obf_dereference_object"] = {
        "source_phase": "6CA",
        "phase6ca_hardware": {
            "kf_lower_irql_calls": 1,
            "kf_lower_irql_successes": 1,
            "guest_irql_old": 2,
            "guest_irql_new": 0,
            "next_boundary_target": "0x800000FA",
            "next_boundary_ordinal": 250,
            "next_boundary_name": "ObfDereferenceObject",
            "boundary_esp": "0x008BF8F8",
            "boundary_saved_esp": "0x008BF8FC",
            "frame_bytes": 4,
            "boundary_ecx": "0x04000000",
            "fault": 0,
            "last_vas": ["0x0022ACE1", "0x0022ACE9", "0x0022AD0F"],
            "xapi_return": 0,
        },
        "continuation": {
            "calling_convention": "FASTCALL",
            "argument_source": "ECX",
            "expected_object": "0x04000000",
            "expected_object_is_phase6bv_sentinel": True,
            "dereferences_guest_object_memory": False,
            "changes_host_object_refcount": False,
            "void_return_preserves_guest_eax": True,
            "requires_prior_synthetic_obref": True,
            "tracks_balanced_synthetic_release": True,
        },
        "translated_membership_changed": False,
        "low_kseg_fence_changed": False,
        "file_object_sentinel_preserved": True,
        "phase5_env_semantics_changed": False,
        "nv2a_mmio_vram_policy_changed": False,
        "allocator_changed": False,
        "execution_budget": 8000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cb-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CB] 6CA hardware: KfLowerIrql PASS guest IRQL 2 -> 0")
    print("[Phase6CB] next boundary: 800000FA = ordinal 250 ObfDereferenceObject FASTCALL")
    print("[Phase6CB] ECX=04000000 exactly matches Phase-6BV FILE_OBJECT sentinel")
    print("[Phase6CB] retail performed no FILE_OBJECT field dereference before release")
    print("[Phase6CB] continuation: balanced synthetic sentinel release only")
    print("[Phase6CB] host object refcounts and sentinel memory remain untouched")
    print("[Phase6CB] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
