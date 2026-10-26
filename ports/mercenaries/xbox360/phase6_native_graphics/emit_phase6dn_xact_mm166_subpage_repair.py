#!/usr/bin/env python3
r"""Phase 6DN: repair canonical sub-page Mm166 allocation after graphics claims.

Hardware 6DK + source audits 6DL/6DM proved:
  * XACT factory sub_0027F3DC allocates/constructs the root successfully.
  * its initializer sub_0027DC5B returns 0x8007000E.
  * the failure path legitimately releases the root through sub_0027F2C2.
  * immediately before that release, ordinal 166 receives:
        size=4, low=0, high=FFFFFFFF, align=0x1000, protect=0x4,
        canonical +24 frame
    and returns base=0.
  * phase4c_page_round(4) is 0x1000. The failure is policy, not arithmetic:
    Phase 6CJ's safe post-graphics tail fallback requires size>=0x1000.

6DN widens only that fallback's requested-size eligibility from >= one page to
nonzero, while retaining:
  * canonical +24 kernel frame;
  * low=0/high=FFFFFFFF;
  * PAGE_READWRITE;
  * alignment >= 0x1000 and power-of-two;
  * page-rounding by phase4c_page_round;
  * exact current free-tail ownership;
  * no live heap crossing;
  * unmanaged-page requirement;
  * reservation-capacity checks.

The previously rejected 96-byte audio request remains ineligible because its
alignment is 4, not >= 0x1000.

No XACT refcount/destructor/free behavior is suppressed or fabricated.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
from pathlib import Path

BASE_TAG = "P6DK-XACT-RELEASE-PRETRACE-20261026-A"
BUILD_TAG = "P6DN-XACT-MM166-SUBPAGE-REPAIR-20261026-A"
COOKIE_OLD = "phase6dk_env_build_cookie"
COOKIE_NEW = "phase6dn_env_build_cookie"
EMITTER_REVISION = "6DN-R1"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DN] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(
            f"[Phase6DN] expected one {label}, found {count}"
        )
    return text.replace(old, new, 1)


def patch_mm166_subpage_gate(text: str) -> str:
    old = (
        "           prot==0x00000004u &&\n"
        "           size>=0x00001000u &&\n"
        "           align>=0x00001000u &&\n"
        "           (align & (align - 1u))==0u)"
    )
    new = (
        "           prot==0x00000004u &&\n"
        "           size!=0u &&\n"
        "           align>=0x00001000u &&\n"
        "           (align & (align - 1u))==0u)"
    )
    text = replace_once(
        text, old, new, "canonical general-tail size gate"
    )

    old_success = r'''            if(va!=0u)
            {
                ++s_phase6cjGeneralTailSuccesses;
                generalTailClaim=1u;
            }
'''
    new_success = r'''            if(va!=0u)
            {
                ++s_phase6cjGeneralTailSuccesses;
                generalTailClaim=1u;
                if(size<0x00001000u)
                {
                    sprintf(
                        line,
                        "PASS: Phase 6DN canonical subpage Mm166 tail claim requested=%u rounded=%u align=%u base=%08X",
                        (unsigned)size,
                        (unsigned)actual,
                        (unsigned)align,
                        (unsigned)va);
                    trace(line);
                }
            }
'''
    return replace_once(
        text, old_success, new_success, "general-tail success block"
    )


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DN] expected one 6DK build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DK", "PHASE 6DN")
        .replace("Phase 6DK", "Phase 6DN")
        .replace('"P6DK ', '"P6DN ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DN] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DK", "PHASE 6DN")
        .replace("Phase 6DK", "Phase 6DN")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dn_base")
    p6bl = load(args.phase6bl_emitter, "phase6dn_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6dk-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DN] missing input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DK" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DN] cached 6DK identity mismatch")

    dk = manifest.get("phase6dk_xact_release_pretrace") or {}
    if (
        dk.get("target") != "0x0027F2C2"
        or dk.get("probe_only") is not True
        or dk.get("dispatch_semantics_changed") is not False
        or dk.get("refcount_changed_by_probe") is not False
        or dk.get("destructor_suppressed") is not False
        or dk.get("free_suppressed") is not False
    ):
        raise SystemExit("[Phase6DN] inherited 6DK policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    required_inherited = (
        BASE_TAG,
        COOKIE_OLD,
        "static uint32_t phase4c_page_round(uint32_t size)",
        "return (size + 0xFFFu) & ~0xFFFu;",
        "static uint32_t phase6at_claim_post_create_tail(",
        "size>=0x00001000u",
        "align>=0x00001000u",
        "(align & (align - 1u))==0u",
        "frameBytes==24u",
        "low==0u",
        "high==0xFFFFFFFFu",
        "prot==0x00000004u",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required_inherited:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DN] inherited marker missing: {marker}")

    main_text = patch_mm166_subpage_gate(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required_output = (
        BUILD_TAG,
        COOKIE_NEW,
        "size!=0u",
        "align>=0x00001000u",
        "(align & (align - 1u))==0u",
        "frameBytes==24u",
        "PASS: Phase 6DN canonical subpage Mm166 tail claim",
        "P6DN XACT RELEASE PRETRACE:",
        "P6DN XACT RELEASE ENTRY:",
        "P6DN XACT GLOBAL WRITE SITE:",
        "#pragma warning(disable:4146)",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
    )
    for marker in required_output:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DN] generated source lost marker: {marker}")

    # The canonical general-tail gate must no longer reject a page-aligned
    # sub-page request merely because requested size is below 0x1000.
    gate_fragment = (
        "frameBytes==24u &&\n"
        "           low==0u &&\n"
        "           high==0xFFFFFFFFu &&\n"
        "           prot==0x00000004u &&\n"
        "           size!=0u &&\n"
        "           align>=0x00001000u &&"
    )
    if gate_fragment not in main_text:
        raise SystemExit("[Phase6DN] canonical subpage eligibility gate missing")

    # Keep the old 96-byte/align4 case fenced by the alignment condition.
    if "align>=0x00001000u" not in main_text:
        raise SystemExit("[Phase6DN] alignment safety gate was weakened")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({"phase": "6DN", "build_tag": BUILD_TAG})
    manifest["phase6dn_xact_mm166_subpage_repair"] = {
        "source_phase": "6DK",
        "hardware_proof": {
            "factory": "0x0027F3DC",
            "initializer": "0x0027DC5B",
            "failure_hresult": "0x8007000E",
            "failed_ordinal": 166,
            "request_size": 4,
            "low": "0x00000000",
            "high": "0xFFFFFFFF",
            "alignment": 4096,
            "protect": "0x00000004",
            "frame_bytes": 24,
            "returned_base": "0x00000000",
            "following_release_target": "0x0027F2C2",
            "released_root": "0x01B5C320",
        },
        "repair": {
            "old_minimum_requested_size": 4096,
            "new_minimum_requested_size": 1,
            "page_rounding_unchanged": True,
            "minimum_alignment": 4096,
            "alignment_power_of_two_required": True,
            "canonical_frame_bytes": 24,
            "low": "0x00000000",
            "high": "0xFFFFFFFF",
            "protect": "0x00000004",
            "tail_safety_checks_unchanged": True,
            "audio_96_align4_still_ineligible": True,
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
    (args.out_dir / "phase6dn-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    print(f"[Phase6DN] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DN] hardware root cause: canonical Mm166 size=4 align=4096 returned NULL")
    print("[Phase6DN] phase4c_page_round(4) remains one page; arithmetic unchanged")
    print("[Phase6DN] repair: canonical tail fallback accepts nonzero requested size")
    print("[Phase6DN] alignment>=4096 + power-of-two safety gates preserved")
    print("[Phase6DN] 96-byte align=4 audio request remains ineligible")
    print("[Phase6DN] XACT refcount/destructor/free semantics unchanged")
    print("[Phase6DN] money line:")
    print("[Phase6DN]   PASS: Phase 6DN canonical subpage Mm166 tail claim requested=4 rounded=4096 align=4096 base=...")
    print("[Phase6DN] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
