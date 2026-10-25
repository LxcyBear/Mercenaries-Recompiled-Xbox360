#!/usr/bin/env python3
"""Phase 6CG: ordinal-160 KfRaiseIrql guest-only continuation.

6CF hardware proved the executive pool family and advanced to:
  ICALL_SAFE caller=0x0023A3CE target=0x800000A0
  esp=0x008BF86C saved_esp=0x008BF870
  ticks=26,711,301 fault=0
  ECX=0x008BF802 -> CL=2 (DISPATCH_LEVEL)

Ordinal 160 is KfRaiseIrql(KIRQL NewIrql). Match the already-proven guest-only
IRQL model used by ordinal 129/161: consume no stack arguments, take the
byte-sized FASTCALL argument from CL, return the previous guest KIRQL in EAX,
and never alter the real Xenon/XDK processor IRQL.

No translated membership, XACTENG sweep, executive-pool semantics, graphics
policy, allocator geometry, watchdog budget, or hard-fence policy changes.
"""
from __future__ import annotations

import argparse
import json
import shutil
from pathlib import Path

BASE_TAG = "P6CF-EXPOOL-FAMILY-20261025-A"
BUILD_TAG = "P6CG-KFRAISEIRQL160-20261025-A"
COOKIE_OLD = "phase6cf_env_build_cookie"
COOKIE_NEW = "phase6cg_env_build_cookie"


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CG] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6bwGuestIrql = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CG] expected one guest-IRQL state anchor, found {text.count(anchor)}"
        )

    state = """static uint32_t s_phase6cgKfRaiseIrqlCallCount = 0u;
static uint32_t s_phase6cgKfRaiseIrqlSuccessCount = 0u;
static uint32_t s_phase6cgKfRaiseIrqlLastOld = 0u;
static uint32_t s_phase6cgKfRaiseIrqlLastNew = 0u;
static uint32_t s_phase6cgKfRaiseIrqlLastRawEcx = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def install_support(text: str) -> str:
    anchor = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CG] expected one pack lookup anchor, found {text.count(anchor)}"
        )

    support = r'''static void phase6cg_kf_raise_irql(uint32_t savedEsp)
{
    const uint32_t callEsp = g_esp;
    uint32_t returnSlot;
    uint32_t oldIrql;
    uint32_t newIrql;
    uint32_t rawEcx;
    char line[640];

    if (savedEsp != callEsp + 4u)
    {
        sprintf(
            line,
            "KfRaiseIrql FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=4",
            (unsigned int)callEsp,
            (unsigned int)savedEsp,
            (unsigned int)(savedEsp - callEsp));
        trace(line);
        phase4c_escape(
            PHASE4C_BOUNDARY_KERNEL_FRAME,
            0x800000A0u,
            savedEsp);
        return;
    }

    returnSlot = GUEST_READ32(callEsp);
    if (s_accessFault)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_GUEST_FAULT,
            0x800000A0u,
            savedEsp);
        return;
    }

    ++s_phase6cgKfRaiseIrqlCallCount;
    oldIrql = s_phase6bwGuestIrql;
    rawEcx = g_ecx;
    newIrql = rawEcx & 0xFFu;

    sprintf(
        line,
        "KfRaiseIrql LIVE FRAME: ret=%08X raw_ecx=%08X new_guest_irql=%u old_guest_irql=%u esp=%08X saved_esp=%08X",
        (unsigned int)returnSlot,
        (unsigned int)rawEcx,
        (unsigned int)newIrql,
        (unsigned int)oldIrql,
        (unsigned int)callEsp,
        (unsigned int)savedEsp);
    trace(line);

    if (
        returnSlot != 0u ||
        oldIrql > 2u ||
        newIrql > 2u ||
        newIrql < oldIrql)
    {
        trace("KfRaiseIrql REJECTED: invalid guest IRQL raising transition");
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x800000A0u,
            savedEsp);
        return;
    }

    /*
     * FASTCALL KIRQL is byte-sized, so only CL is semantic.
     * Keep this guest-only exactly like the hardware-proven 129/161 model:
     * do not mask real Xenon interrupts across translated title execution.
     */
    s_phase6bwGuestIrql = newIrql;
    ++s_phase6cgKfRaiseIrqlSuccessCount;
    s_phase6cgKfRaiseIrqlLastOld = oldIrql;
    s_phase6cgKfRaiseIrqlLastNew = newIrql;
    s_phase6cgKfRaiseIrqlLastRawEcx = rawEcx;

    g_eax = oldIrql;
    g_esp = savedEsp;

    sprintf(
        line,
        "PASS: Phase 6CG KfRaiseIrql guest continuation old=%u new=%u raw_ecx=%08X calls=%u successes=%u new_esp=%08X",
        (unsigned int)oldIrql,
        (unsigned int)newIrql,
        (unsigned int)rawEcx,
        (unsigned int)s_phase6cgKfRaiseIrqlCallCount,
        (unsigned int)s_phase6cgKfRaiseIrqlSuccessCount,
        (unsigned int)g_esp);
    trace(line);
}

'''
    text = text.replace(anchor, support + anchor, 1)

    state_pos = text.find("static uint32_t s_phase6cgKfRaiseIrqlCallCount = 0u;")
    helper_pos = text.find("static void phase6cg_kf_raise_irql(uint32_t savedEsp)")
    summary_helper_pos = text.find("static void phase6cd_dump_hot_profile(void)")
    lookup_pos = text.find(anchor)
    if min(state_pos, helper_pos, summary_helper_pos, lookup_pos) < 0:
        raise SystemExit("[Phase6CG] compile-order proof marker missing")

    if not (
        state_pos < summary_helper_pos < helper_pos < lookup_pos
        or state_pos < helper_pos < summary_helper_pos < lookup_pos
    ):
        # State must be visible globally before both helper users. The exact
        # relative ordering of the two functions is inherited and irrelevant.
        raise SystemExit("[Phase6CG] compile-order proof failed")

    return text


def patch_icall_dispatch(text: str) -> str:
    macro_start = text.find("#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {")
    if macro_start < 0:
        raise SystemExit("[Phase6CG] RECOMP_ICALL_SAFE macro start missing")
    next_macro = text.find("#define RECOMP_ITAIL", macro_start)
    if next_macro < 0:
        raise SystemExit("[Phase6CG] RECOMP_ITAIL anchor missing")

    macro = text[macro_start:next_macro]
    if "_phase4c_target == 0x800000A0u" in macro:
        raise SystemExit("[Phase6CG] ordinal 160 already dispatched")

    bs = chr(92)
    inherited = "if (_phase4c_target == 0x800000A1u) { " + bs
    pos = macro.find(inherited)
    if pos < 0:
        raise SystemExit("[Phase6CG] inherited ordinal-161 dispatch head missing")

    replacement = (
        "if (_phase4c_target == 0x800000A0u) { " + bs + "\n"
        "        phase6cg_kf_raise_irql((uint32_t)(saved_esp)); " + bs + "\n"
        "    } else if (_phase4c_target == 0x800000A1u) { " + bs
    )
    macro = macro[:pos] + replacement + macro[pos + len(inherited):]

    if macro.count("_phase4c_target == 0x800000A0u") != 1:
        raise SystemExit("[Phase6CG] ordinal-160 dispatch insertion failed")

    return text[:macro_start] + macro + text[next_macro:]


def insert_arm_trace(text: str) -> str:
    marker = (
        '    trace("PASS: Phase 6CF executive pool family armed: '
        'ordinals 14/15/17/23 guest-heap semantics");\n'
    )
    if text.count(marker) != 1:
        raise SystemExit("[Phase6CG] inherited 6CF pool-family arm trace missing")

    return text.replace(
        marker,
        marker
        + '    trace("PASS: Phase 6CG ordinal 160 KfRaiseIrql guest-IRQL continuation armed");\n',
        1,
    )


def insert_summary(text: str) -> str:
    marker = "P6CF KFLOWERIRQL161:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CG] inherited KfLowerIrql summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 5000:
        raise SystemExit("[Phase6CG] could not locate IRQL summary insertion point")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CG KFRAISEIRQL160: calls=%u successes=%u old=%u new=%u raw_ecx=%08X current=%u",\n'
        f'{indent}    (unsigned int)s_phase6cgKfRaiseIrqlCallCount,\n'
        f'{indent}    (unsigned int)s_phase6cgKfRaiseIrqlSuccessCount,\n'
        f'{indent}    (unsigned int)s_phase6cgKfRaiseIrqlLastOld,\n'
        f'{indent}    (unsigned int)s_phase6cgKfRaiseIrqlLastNew,\n'
        f'{indent}    (unsigned int)s_phase6cgKfRaiseIrqlLastRawEcx,\n'
        f'{indent}    (unsigned int)s_phase6bwGuestIrql);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_main(text: str) -> str:
    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "_phase4c_target == 0x800000A1u",
        "static uint32_t s_phase6bwGuestIrql = 0u;",
        "P6CF KFLOWERIRQL161:",
        "P6CF KERAISEIRQL129:",
        "P6CF EXPOOL:",
        "case 0x0027DB5Cu:",
    ):
        if marker not in text:
            raise SystemExit(f"[Phase6CG] inherited 6CF marker missing: {marker}")

    text = install_state(text)
    text = install_support(text)
    text = patch_icall_dispatch(text)
    text = insert_arm_trace(text)
    text = insert_summary(text)

    old_policy = (
        "Policy: Phase 6CF continues the hardware-proven 6CE XACTENG path through "
        "canonical Xbox executive pool ordinals 14/15/17/23 using the maintained "
        "zero-filled 16-byte-aligned guest title heap; preserve XACTENG membership, "
        "32M watchdog, quiet logging, manual PblMath, graphics/file/IDEX/IRQL semantics "
        "and every genuine hard fence"
    )
    new_policy = (
        "Policy: Phase 6CG continues the hardware-proven 6CF audio/XACT path through "
        "ordinal 160 KfRaiseIrql using the maintained guest-only IRQL model; preserve "
        "the executive pool family, XACTENG membership, 32M watchdog, quiet logging, "
        "manual PblMath, graphics/file/IDEX semantics and every genuine hard fence"
    )
    text = replace_once(text, old_policy, new_policy, "runtime policy")
    text = replace_once(text, BASE_TAG, BUILD_TAG, "build tag")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)

    text = (
        text.replace("PHASE 6CF", "PHASE 6CG")
        .replace("Phase 6CF", "Phase 6CG")
        .replace('"P6CF ', '"P6CG ')
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "_phase4c_target == 0x800000A0u",
        "phase6cg_kf_raise_irql",
        "KfRaiseIrql LIVE FRAME:",
        "PASS: Phase 6CG KfRaiseIrql guest continuation",
        "P6CG KFRAISEIRQL160:",
        "P6CG KFLOWERIRQL161:",
        "P6CG EXPOOL:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    )
    for marker in required:
        if marker not in text:
            raise SystemExit(f"[Phase6CG] patched source lost marker: {marker}")

    state_pos = text.find("static uint32_t s_phase6cgKfRaiseIrqlCallCount = 0u;")
    summary_pos = text.find("P6CG KFRAISEIRQL160:")
    if state_pos < 0 or summary_pos < 0 or state_pos > summary_pos:
        raise SystemExit(
            "[Phase6CG] KfRaiseIrql state declarations are not visible before summary"
        )

    if COOKIE_OLD in text:
        raise SystemExit("[Phase6CG] stale 6CF env cookie remains")
    return text


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CF", "PHASE 6CG")
        .replace("Phase 6CF", "Phase 6CG")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CG] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base_main = args.base_dir / "main.cpp"
    base_mono = args.base_dir / "main_monolithic.cpp"
    base_env = args.base_dir / "phase5_env.cpp"
    base_manifest = args.base_dir / "phase6cf-manifest.json"
    base_shards = args.base_dir / "translated_shards"

    for path in (base_main, base_mono, base_env, base_manifest, base_shards):
        if not path.exists():
            raise SystemExit(f"[Phase6CG] missing cached 6CF input: {path}")

    manifest = json.loads(base_manifest.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6CF" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CG] cached Phase 6CF identity mismatch")

    cf = manifest.get("phase6cf_executive_pool_family", {})
    if (
        cf.get("execution_budget_inherited") != 32000000
        or cf.get("translated_membership_changed") is not False
        or cf.get("hard_fences_changed") is not False
    ):
        raise SystemExit("[Phase6CG] inherited 6CF policy mismatch")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    out_shards = args.out_dir / "translated_shards"
    if out_shards.exists():
        shutil.rmtree(out_shards)
    shutil.copytree(base_shards, out_shards)

    main_text = patch_main(base_main.read_text(encoding="utf-8"))
    mono_text = patch_main(base_mono.read_text(encoding="utf-8"))
    env_text = patch_env(base_env.read_text(encoding="utf-8"))

    (args.out_dir / "main.cpp").write_text(main_text, encoding="utf-8")
    (args.out_dir / "main_monolithic.cpp").write_text(mono_text, encoding="utf-8")
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CG"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cg_kf_raise_irql"] = {
        "source_phase": "6CF",
        "phase6cf_hardware": {
            "boundary_kind": "ICALL_SAFE",
            "caller": "0x0023A3CE",
            "target": "0x800000A0",
            "ordinal": 160,
            "name": "KfRaiseIrql",
            "esp": "0x008BF86C",
            "saved_esp": "0x008BF870",
            "frame_delta": 4,
            "ticks": 26711301,
            "trace": 1017529,
            "fault": 0,
            "eax": "0x00000001",
            "ecx": "0x008BF802",
            "new_irql_from_cl": 2,
            "guest_irql_before": 0,
            "xapi_return": 0,
        },
        "semantics": {
            "fastcall_argument": "CL",
            "return_register": "EAX",
            "return_value": "previous guest KIRQL",
            "host_xenon_irql_changed": False,
            "valid_guest_range": "0..2",
        },
        "translated_membership_changed": False,
        "xacteng_membership_changed": False,
        "executive_pool_semantics_changed": False,
        "execution_budget_inherited": 32000000,
        "dispatch_log_stride_inherited": 4096,
        "hard_fences_changed": False,
        "shards_reused_byte_for_byte": True,
        "shard_count": len(list(out_shards.glob("*.inl"))),
    }

    (args.out_dir / "phase6cg-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CG] 6CF hardware: executive pool family PASS")
    print("[Phase6CG] next boundary: ordinal 160 KfRaiseIrql at tick 26,711,301")
    print("[Phase6CG] live FASTCALL: ECX=008BF802 -> CL=2, guest IRQL before=0")
    print("[Phase6CG] semantics: guest-only 0->2, return old IRQL in EAX")
    print("[Phase6CG] real Xenon/XDK processor IRQL remains untouched")
    print("[Phase6CG] translated/XACTENG/pool semantic changes: 0")
    print("[Phase6CG] execution budget: inherited 32,000,000 ticks")
    print("[Phase6CG] hard fences: unchanged")
    print("[Phase6CG] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
