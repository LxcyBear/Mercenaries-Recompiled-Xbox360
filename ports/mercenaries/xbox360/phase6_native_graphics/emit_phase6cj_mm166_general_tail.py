#!/usr/bin/env python3
"""Phase 6CJ: general safe dual-frontier Mm166 tail allocation after 6CI.

6CI hardware proved the GP/EP DSP bootstrap shadows and then reached a new
non-MMIO guest fault. Immediately before that fault, retail DSOUND/XACT made a
canonical ordinal-166 request:
  size=0x2000, low=0, high=0xFFFFFFFF, align=0x1000, protect=0x4,
  frame=24, result=0.

The inherited normal page allocator still rejects allocations once pageNext has
been pulled below the compile-time title-heap end by the graphics reservations.
Phase 6AT already introduced a safety-checked tail claimant, but gated it to the
post-Create D3D initializer and a +28 wrapper frame.

6CJ reuses that exact safety proof for ordinary canonical +24 Mm166 requests,
but only when:
  * normal allocation returned 0;
  * the call is outside the D3D initializer;
  * low=0, high=0xFFFFFFFF;
  * protect=PAGE_READWRITE (0x4);
  * size and alignment are at least one page and alignment is power-of-two.

The claimant still requires the requested region to be exactly the current free
heap tail, above every live heap allocation, and entirely unmanaged in page
state. The 96-byte audio fallback (align=4) is intentionally still rejected.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6CI-APU-GPEP-DSP-20261025-A"
BUILD_TAG = "P6CJ-MM166-GENERAL-TAIL-20261025-A"
COOKIE_OLD = "phase6ci_env_build_cookie"
COOKIE_NEW = "phase6cj_env_build_cookie"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CJ] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CJ] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def replace_policy_line(text: str, policy: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0:
        raise SystemExit("[Phase6CJ] runtime policy trace missing")
    if text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CJ] multiple runtime policy traces found")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    return (
        text[:line_start]
        + indent
        + 'trace("Policy: '
        + policy
        + '");'
        + text[line_end:]
    )


def install_state(text: str) -> str:
    anchor = "static uint32_t s_phase6ciDspLastValue = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6CJ] expected one 6CI state anchor, found {text.count(anchor)}"
        )
    state = """static uint32_t s_phase6cjGeneralTailCalls = 0u;
static uint32_t s_phase6cjGeneralTailSuccesses = 0u;
static uint32_t s_phase6cjGeneralTailLastRequested = 0u;
static uint32_t s_phase6cjGeneralTailLastAlignment = 0u;
static uint32_t s_phase6cjGeneralTailLastBase = 0u;
static uint32_t s_phase6cjGeneralTailLastActual = 0u;

"""
    return text.replace(anchor, anchor + state, 1)


def patch_tail_claim_gate(text: str) -> str:
    old = r'''    if (!s_phase6atPostCreateInitActive ||
        size == 0u ||
        s_phase4cVmReservationCount >= PHASE4C_VM_RESERVATION_CAP)
        return 0u;
'''
    new = r'''    /*
     * Phase 6CJ: callers now provide the provenance gate. The safety checks in
     * this helper remain authoritative: exact current tail, no live heap block
     * crossing the claim, reservation capacity available, and every page still
     * unmanaged. This permits canonical post-graphics physical allocations
     * without making the title heap and page frontier overlap.
     */
    if (size == 0u ||
        s_phase4cVmReservationCount >= PHASE4C_VM_RESERVATION_CAP)
        return 0u;
'''
    return replace_once(text, old, new, "tail-claim active gate")


def patch_mm166(text: str) -> str:
    text = replace_once(
        text,
        "    uint32_t postCreateTailClaim=0u;\n",
        "    uint32_t postCreateTailClaim=0u;\n"
        "    uint32_t generalTailClaim=0u;\n",
        "Mm166 claim declaration",
    )

    anchor = r'''        if(va==0u &&
           s_phase6atPostCreateInitActive &&
           frameBytes==28u &&
           low==0u &&
           high==0xFFFFFFFFu &&
           prot==0x00000404u)
        {
            va=phase6at_claim_post_create_tail(
                size,
                align,
                prot,
                &actual);
            if(va!=0u)
                postCreateTailClaim=1u;
        }
    }

    if(va)
'''
    replacement = r'''        if(va==0u &&
           s_phase6atPostCreateInitActive &&
           frameBytes==28u &&
           low==0u &&
           high==0xFFFFFFFFu &&
           prot==0x00000404u)
        {
            va=phase6at_claim_post_create_tail(
                size,
                align,
                prot,
                &actual);
            if(va!=0u)
                postCreateTailClaim=1u;
        }

        /*
         * Hardware 6CI: DSOUND/XACT requests 0x2000 bytes with canonical +24
         * ABI, low=0, high=FFFFFFFF, align=0x1000, protect=0x4 after the D3D
         * reservations have moved pageNext below PHASE4C_TITLE_HEAP_END.
         *
         * Keep sub-page fallback behavior unchanged. Generalize only the
         * safety-checked physical-page tail path.
         */
        if(va==0u &&
           !s_phase6atPostCreateInitActive &&
           frameBytes==24u &&
           low==0u &&
           high==0xFFFFFFFFu &&
           prot==0x00000004u &&
           size>=0x00001000u &&
           align>=0x00001000u &&
           (align & (align - 1u))==0u)
        {
            ++s_phase6cjGeneralTailCalls;
            s_phase6cjGeneralTailLastRequested=size;
            s_phase6cjGeneralTailLastAlignment=align;
            s_phase6cjGeneralTailLastBase=0u;
            s_phase6cjGeneralTailLastActual=0u;

            va=phase6at_claim_post_create_tail(
                size,
                align,
                prot,
                &actual);

            s_phase6cjGeneralTailLastBase=va;
            s_phase6cjGeneralTailLastActual=actual;
            if(va!=0u)
            {
                ++s_phase6cjGeneralTailSuccesses;
                generalTailClaim=1u;
            }
        }
    }

    if(va)
'''
    text = replace_once(text, anchor, replacement, "Mm166 D3D tail block")

    old_fmt = (
        '"PASS: Phase 6CI ordinal 166 MmAllocateContiguousMemoryEx '
        'size=%u low=%08X high=%08X align=%u protect=%08X base=%08X '
        'rounded=%u frame=%u spill=%08X repair=%u graphics_claim=%u '
        'post_init_tail_claim=%u resume_esp=%08X saved_esp=%08X",'
    )
    new_fmt = (
        '"PASS: Phase 6CI ordinal 166 MmAllocateContiguousMemoryEx '
        'size=%u low=%08X high=%08X align=%u protect=%08X base=%08X '
        'rounded=%u frame=%u spill=%08X repair=%u graphics_claim=%u '
        'post_init_tail_claim=%u general_tail_claim=%u resume_esp=%08X saved_esp=%08X",'
    )
    text = replace_once(text, old_fmt, new_fmt, "Mm166 trace format")

    old_args = (
        "        (unsigned)extra,(unsigned)repaired,(unsigned)retailGraphicsClaim,\n"
        "        (unsigned)postCreateTailClaim,(unsigned)g_esp,(unsigned)savedEsp);"
    )
    new_args = (
        "        (unsigned)extra,(unsigned)repaired,(unsigned)retailGraphicsClaim,\n"
        "        (unsigned)postCreateTailClaim,(unsigned)generalTailClaim,\n"
        "        (unsigned)g_esp,(unsigned)savedEsp);"
    )
    return replace_once(text, old_args, new_args, "Mm166 trace arguments")


def insert_summary(text: str) -> str:
    marker = "P6CI APU DSP:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CJ] inherited 6CI APU DSP summary missing")

    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6CJ] could not locate summary insertion point")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CJ MM166 GENERAL TAIL: calls=%u successes=%u requested=%u align=%u base=%08X actual=%u page_next=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cjGeneralTailCalls,\n'
        f'{indent}    (unsigned int)s_phase6cjGeneralTailSuccesses,\n'
        f'{indent}    (unsigned int)s_phase6cjGeneralTailLastRequested,\n'
        f'{indent}    (unsigned int)s_phase6cjGeneralTailLastAlignment,\n'
        f'{indent}    (unsigned int)s_phase6cjGeneralTailLastBase,\n'
        f'{indent}    (unsigned int)s_phase6cjGeneralTailLastActual,\n'
        f'{indent}    (unsigned int)s_phase4cVmPageNext);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CI", "PHASE 6CJ")
        .replace("Phase 6CI", "Phase 6CJ")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CJ] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cj_base")
    p6bl = load(args.phase6bl_emitter, "phase6cj_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6ci-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CJ] missing cached 6CI input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CI" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CJ] cached Phase 6CI identity mismatch")

    ci = manifest.get("phase6ci_apu_gp_ep_dsp", {})
    if (
        ci.get("execution_budget_inherited") != 32000000
        or ci.get("translated_membership_changed") is not False
        or ci.get("apu_core_semantics_changed") is not False
        or ci.get("guest_irql_semantics_changed") is not False
    ):
        raise SystemExit("[Phase6CJ] inherited 6CI policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "static uint32_t phase6at_claim_post_create_tail(",
        "static void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)",
        "post_init_tail_claim=%u",
        "P6CI APU DSP:",
        "P6CI APU CORE:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CJ] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = patch_tail_claim_gate(main_text)
    main_text = patch_mm166(main_text)
    main_text = insert_summary(main_text)

    main_text = replace_policy_line(
        main_text,
        "Phase 6CJ preserves the 6CI APU GP/EP bootstrap and extends the "
        "safety-checked dual-frontier allocator to canonical page-sized/page-aligned "
        "full-range MmAllocateContiguousMemoryEx requests after graphics setup; "
        "sub-page fallback, graphics special claims, 32M watchdog, XACTENG membership, "
        "guest-only IRQL, NV2A and all hard MMIO/guest-memory fences remain unchanged"
    )

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CI", "PHASE 6CJ")
        .replace("Phase 6CI", "Phase 6CJ")
        .replace('"P6CI ', '"P6CJ ')
    )
    env_text = patch_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "s_phase6cjGeneralTailCalls",
        "size>=0x00001000u",
        "align>=0x00001000u",
        "frameBytes==24u",
        "prot==0x00000004u",
        "general_tail_claim=%u",
        "P6CJ MM166 GENERAL TAIL:",
        "P6CJ APU DSP:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6CJ] generated source lost marker: {marker}")

    if "!s_phase6atPostCreateInitActive ||\n        size == 0u" in main_text:
        raise SystemExit("[Phase6CJ] stale D3D-only helper gate remains")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CJ"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cj_mm166_general_tail"] = {
        "source_phase": "6CI",
        "phase6ci_hardware": {
            "apu_gp_write": {
                "address": "0xFE83FFFC",
                "value": "0x00000000",
                "count": 1,
            },
            "apu_ep_write": {
                "address": "0xFE85FFFC",
                "value": "0x00000001",
                "count": 1,
            },
            "failed_mm166": {
                "size": "0x00002000",
                "low": "0x00000000",
                "high": "0xFFFFFFFF",
                "alignment": "0x00001000",
                "protect": "0x00000004",
                "frame_bytes": 24,
                "base": "0x00000000",
                "rounded": 0,
            },
            "following_boundary": {
                "kind": "GUEST_FAULT",
                "access": "READ32",
                "target": "0xFFFFFFFF",
                "ticks": 26711516,
                "trace": 1017570,
                "fault": 1,
                "eax": "0x00041D70",
                "ecx": "0xFFFFFFFF",
                "edx": "0x008C1134",
                "ebx": "0x00000001",
                "esi": "0x00000000",
                "edi": "0x01B5C3F8",
            },
        },
        "repair": {
            "normal_allocator_first": True,
            "fallback_helper": "phase6at_claim_post_create_tail",
            "helper_safety_checks_preserved": True,
            "canonical_frame_bytes": 24,
            "minimum_size": "0x00001000",
            "minimum_alignment": "0x00001000",
            "alignment_power_of_two_required": True,
            "low": "0x00000000",
            "high": "0xFFFFFFFF",
            "protect": "0x00000004",
            "outside_d3d_initializer_only": True,
            "subpage_fallback_unchanged": True,
            "observed_0x60_align4_request_still_ineligible": True,
        },
        "translated_membership_changed": False,
        "apu_gp_ep_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "xacteng_membership_changed": False,
        "execution_budget_inherited": 32000000,
        "dispatch_log_stride_inherited": 4096,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cj-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CJ] 6CI GP/EP DSP reset writes: PASS")
    print("[Phase6CJ] 6CI next evidence: canonical Mm166 0x2000/align0x1000 returned NULL")
    print("[Phase6CJ] following boundary: READ32 FFFFFFFF at tick 26,711,516")
    print("[Phase6CJ] GENERAL TAIL: canonical +24, low=0, high=FFFFFFFF, protect=4")
    print("[Phase6CJ] GENERAL TAIL: size>=0x1000, align>=0x1000 power-of-two")
    print("[Phase6CJ] 0x60/align4 fallback remains intentionally ineligible")
    print("[Phase6CJ] inherited tail safety checks remain authoritative")
    print("[Phase6CJ] 32M execution budget preserved")
    print("[Phase6CJ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
