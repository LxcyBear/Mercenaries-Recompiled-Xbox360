#!/usr/bin/env python3
r"""Phase 6DO: allow safe alignment slack in the post-graphics Mm166 tail claimant.

6DN hardware proved its sub-page repair worked:
  size=4, align=0x1000 -> base=0x024F3000, rounded=0x1000.

The immediately following canonical MmAllocateContiguousMemoryEx request is:
  size=0x8000, low=0, high=0xFFFFFFFF, align=0x8000, protect=0x4,
  old_page_next=0x024F3000.

phase6at_claim_post_create_tail computes:
  base = (oldPageNext - size) & ~(alignment - 1)
       = 0x024E8000
  end  = 0x024F0000
leaving a 0x3000 alignment pad below oldPageNext.

The inherited helper rejects this only because it requires base+size to equal
oldPageNext exactly. All stronger safety checks already reason about the full
consumed tail down to base: no live heap allocation may cross base, the one free
heap tail must end at oldPageNext, the heap tail is trimmed to base, allocation
pages must be unmanaged, and the page frontier moves to base.

6DO therefore permits base+size <= oldPageNext when the slack is strictly less
than the requested power-of-two alignment. The slack is intentionally consumed
as non-addressable alignment padding: it is removed from the heap tail and lies
above the new page frontier, but is not reported as part of the guest allocation.

No XACT refcount/destructor/free, dispatch, guest fault, MMIO, or hard-fence
semantics are changed.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6DN-XACT-MM166-SUBPAGE-REPAIR-20261026-A"
BUILD_TAG = "P6DO-MM166-ALIGNMENT-GAP-REPAIR-20261026-A"
COOKIE_OLD = "phase6dn_env_build_cookie"
COOKIE_NEW = "phase6do_env_build_cookie"
EMITTER_REVISION = "6DO-R4"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DO] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6DO] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def patch_tail_alignment_gap(text: str) -> str:
    # Scope every rewrite to the actual tail-claim helper. Several generic
    # declaration/trace fragments also occur in other allocator helpers.
    helper_start = text.find(
        "static uint32_t phase6at_claim_post_create_tail(\n"
    )
    helper_end_marker = (
        "\nstatic void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)\n"
    )
    if helper_start < 0:
        raise SystemExit("[Phase6DO] tail-claim helper start missing")
    helper_end = text.find(helper_end_marker, helper_start)
    if helper_end < 0:
        raise SystemExit("[Phase6DO] tail-claim helper end missing")

    helper = text[helper_start:helper_end]

    helper = replace_once(
        helper,
        "    uint32_t page;\n"
        "    uint32_t index;\n"
        "    uint32_t heapHigh = PHASE4C_TITLE_HEAP_START;\n",
        "    uint32_t page;\n"
        "    uint32_t index;\n"
        "    uint32_t alignmentPad = 0u;\n"
        "    uint32_t heapHigh = PHASE4C_TITLE_HEAP_START;\n",
        "tail helper alignment-pad declaration",
    )

    old = r'''    base = (oldPageNext - size) & ~(alignment - 1u);
    if (base < PHASE4C_TITLE_HEAP_START ||
        base >= oldPageNext ||
        base + size != oldPageNext ||
        !phase4c_vm_page_range(base, size, &firstPage, &lastPage))
        return 0u;
'''
    new = r'''    base = (oldPageNext - size) & ~(alignment - 1u);
    if (base < PHASE4C_TITLE_HEAP_START ||
        base >= oldPageNext ||
        base + size < base ||
        base + size > oldPageNext ||
        !phase4c_vm_page_range(base, size, &firstPage, &lastPage))
        return 0u;

    alignmentPad = oldPageNext - (base + size);
    if (alignmentPad >= alignment)
        return 0u;
'''
    helper = replace_once(helper, old, new, "exact-end tail gate")

    marker = r'''    if (actualSize)
        *actualSize = size;

    ++s_phase6atTailClaimSuccesses;
'''
    replacement = r'''    if (actualSize)
        *actualSize = size;

    if (alignmentPad != 0u)
    {
        sprintf(
            line,
            "PASS: Phase 6DO aligned tail claim base=%08X requested=%u rounded=%u align=%u alignment_pad=%u old_page_next=%08X",
            (unsigned int)base,
            (unsigned int)requested,
            (unsigned int)size,
            (unsigned int)alignment,
            (unsigned int)alignmentPad,
            (unsigned int)oldPageNext);
        trace(line);
    }

    ++s_phase6atTailClaimSuccesses;
'''
    helper = replace_once(
        helper, marker, replacement, "alignment-gap success trace"
    )

    return text[:helper_start] + helper + text[helper_end:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DO] expected one 6DN build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DN", "PHASE 6DO")
        .replace("Phase 6DN", "Phase 6DO")
        .replace('"P6DN ', '"P6DO ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DO] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DN", "PHASE 6DO")
        .replace("Phase 6DN", "Phase 6DO")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6do_base")
    p6bl = load(args.phase6bl_emitter, "phase6do_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6dn-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DO] missing input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DN" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DO] cached 6DN identity mismatch")

    dn = manifest.get("phase6dn_xact_mm166_subpage_repair") or {}
    if (
        dn.get("repair", {}).get("new_minimum_requested_size") != 1
        or dn.get("repair", {}).get("minimum_alignment") != 4096
        or dn.get("xact_refcount_semantics_changed") is not False
        or dn.get("destructor_suppressed") is not False
        or dn.get("free_suppressed") is not False
    ):
        raise SystemExit("[Phase6DO] inherited 6DN policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    required = (
        BASE_TAG,
        COOKIE_OLD,
        "PASS: Phase 6DN canonical subpage Mm166 tail claim",
        "static uint32_t phase6at_claim_post_create_tail(",
        "base + size != oldPageNext",
        "tail->capacity = base - tail->address;",
        "s_phase4cVmPageNext = base;",
        "size!=0u",
        "align>=0x00001000u",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DO] inherited marker missing: {marker}")

    main_text = patch_tail_alignment_gap(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "uint32_t alignmentPad = 0u;",
        "base + size > oldPageNext",
        "alignmentPad = oldPageNext - (base + size);",
        "if (alignmentPad >= alignment)",
        "PASS: Phase 6DO aligned tail claim",
        "alignment_pad=%u",
        "PASS: Phase 6DO canonical subpage Mm166 tail claim",
        "P6DO XACT RELEASE PRETRACE:",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DO] generated source lost marker: {marker}")

    verify_start = main_text.find(
        "static uint32_t phase6at_claim_post_create_tail(\n"
    )
    verify_end = main_text.find(
        "\nstatic void phase5bb_mm_allocate_contiguous_ex(uint32_t savedEsp)\n",
        verify_start,
    )
    if verify_start < 0 or verify_end < 0:
        raise SystemExit("[Phase6DO] generated tail helper verification bounds missing")
    verify_helper = main_text[verify_start:verify_end]
    if "base + size != oldPageNext" in verify_helper:
        raise SystemExit(
            "[Phase6DO] stale exact-end restriction remains inside tail helper"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6DO", "build_tag": BUILD_TAG})
    manifest["phase6do_mm166_alignment_gap_repair"] = {
        "source_phase": "6DN",
        "hardware_proof": {
            "prior_subpage_request_succeeded": True,
            "prior_request_size": 4,
            "prior_request_alignment": 4096,
            "prior_base": "0x024F3000",
            "next_failed_request_size": 32768,
            "next_failed_alignment": 32768,
            "next_failed_protect": "0x00000004",
            "old_page_next": "0x024F3000",
            "computed_aligned_base": "0x024E8000",
            "computed_allocation_end": "0x024F0000",
            "alignment_padding": 12288,
            "following_hresult": "0x8007000E",
        },
        "repair": {
            "exact_end_requirement_removed": True,
            "allocation_end_must_not_exceed_old_frontier": True,
            "alignment_padding_must_be_less_than_alignment": True,
            "alignment_padding_consumed_from_free_tail": True,
            "alignment_padding_reported_to_guest": False,
            "guest_allocation_size_unchanged": True,
            "tail_heap_overlap_checks_unchanged": True,
            "unmanaged_page_checks_unchanged": True,
            "reservation_capacity_checks_unchanged": True,
            "canonical_mm166_gate_unchanged": True,
            "minimum_alignment_unchanged": 4096,
            "subpage_repair_inherited": True,
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
    (args.out_dir / "phase6do-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6DO] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DO] 6DN subpage repair hardware result: PASS")
    print("[Phase6DO] next blocker: Mm166 size=32768 align=32768 returned NULL")
    print("[Phase6DO] computed aligned base=024E8000 end=024F0000 pad=12288")
    print("[Phase6DO] repair: consume safe alignment pad while preserving guest size")
    print("[Phase6DO] heap overlap/unmanaged-page/reservation fences unchanged")
    print("[Phase6DO] XACT refcount/destructor/free semantics unchanged")
    print("[Phase6DO] money line:")
    print("[Phase6DO]   PASS: Phase 6DO aligned tail claim ... requested=32768 rounded=32768 align=32768 alignment_pad=12288 ...")
    print("[Phase6DO] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
