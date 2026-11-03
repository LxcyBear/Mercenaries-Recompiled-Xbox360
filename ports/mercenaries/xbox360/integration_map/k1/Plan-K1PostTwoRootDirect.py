#!/usr/bin/env python3
"""Classify DIRECT_FRONTIER 0x002228C0 after the K1 two-body Xbox hardware run.

Strictly source-only; preserves graphics and audio work, no build, no
guest ABI guesses, no artificial display, no new XEX.
It reuses the previous audited retail-inventory functions rather than
recoding classification and accidentally treating an interior as an entry.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

TARGET = 0x002228C0
PREV_TARGET = 0x001F7620
PREV_CALLEE = 0x001F7520
PREV_TICKS = 58_612_295
NEW_TICKS = 58_612_771
RETAIL_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PARENT_STATUS = "K1_NEXT_ICALL_TWO_SOURCE_AUTHENTIC_BODIES_NO_XDK"
PARENT_MARKER = "K1-TEXT-ICALL-1F7620-1F7520-20261103"
SIX_CASE_MARKER = "K1D3D-296550-SIXCASES-ONEBUILD-20261103"
MAX_NEW = 96
MAX_DEPTH = 4
OUTPUT_STATUS = "K1_POST_TWO_ROOT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY"


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Source module unavailable: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def validate_parent(
    meta: dict, main: bytes, shard_hashes: dict[str, str],
    shard_sources: dict[str, str],
) -> dict:
    """Prove two-root main and six-case original TrueTU ownership."""
    expected = {
        "status": PARENT_STATUS,
        "marker": PARENT_MARKER,
        "original_retail_xbe_sha256": RETAIL_SHA,
        "new_members_count": 2,
        "original_true_tus": 64,
        "original_true_tus_reused_not_modified": True,
        "original_runtime_header_unchanged": True,
        "lookup_both_exact_original_entries": True,
        "preserves_six_case_graphics_dispatch": True,
        "native_xenos_reset_source_unchanged": True,
        "unknown_indirect_hard_fence_unchanged": True,
        "dummy_guest_data": False,
    }
    bad = {k: {"expected": v, "actual": meta.get(k)}
           for k, v in expected.items() if meta.get(k) != v}
    if bad:
        raise ValueError("Two-root parent source/safety identity mismatch: " + repr(bad))
    if meta.get("new_members") != ["0x001F7620", "0x001F7520"]:
        raise ValueError("Two original .text roots changed")
    if meta.get("new_main_sha256") != digest(main):
        raise ValueError("Parent main hash differs from original two-root manifest")
    if len(shard_hashes) != 64 or (
        meta.get("original_64_true_tu_sha256") != shard_hashes
    ):
        raise ValueError("One or more parent 64 TrueTUs changed")
    source = main.decode("utf-8", errors="replace")
    for evidence in (
        PARENT_MARKER,
        "case 0x001F7620u: return sub_001F7620;",
        "case 0x001F7520u: return sub_001F7520;",
        "K1D3D SECOND: native Xenos Reset PASS",
        "P6DQ ROCKET HARD STOP",
        "K1STATE MAIN CHECKPOINT:",
    ):
        if evidence not in source:
            raise ValueError("Hardware parent main lost source evidence: " + evidence)
    root_owner = meta.get("six_case_verified_owner_file")
    common_owner = meta.get("six_case_verified_common_tail_owner")
    if not root_owner or not common_owner:
        raise ValueError("Missing original six-case owner/common-tail provenance")
    owners = {"main.cpp": source}
    owners.update(shard_sources)
    if root_owner not in owners or common_owner not in owners:
        raise ValueError("Six-case root or common owner source no longer present")
    if owners[root_owner].count(SIX_CASE_MARKER) != 1 or (
        "k1d3d_296550_original_sixcase(eax, k1_original_tail_target)"
        not in owners[root_owner]
    ) or "RECOMP_ITAIL(k1_original_tail_target)" not in owners[root_owner]:
        raise ValueError("Original six-case bridge or unknown ITAIL hard fence lost")
    if "void sub_002965A8(void)" not in owners[common_owner]:
        raise ValueError("Original six-case common tail no longer compiled")
    if sum(text.count(SIX_CASE_MARKER) for text in owners.values()) != 1:
        raise ValueError("Six-case marker was duplicated/moved into other source")
    return {"six_case_owner": root_owner,
            "six_case_common_owner": common_owner,
            "previous_original_packed_members": meta["new_members"]}


def analyze(a):
    parent = a.parent.read_bytes()
    meta = json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    shard_paths = sorted(a.shards.glob("translated_???.cpp"))
    if len(shard_paths) != 64 or not (a.shards / "translated_runtime.h").is_file():
        raise ValueError("64 original TrueTUs + runtime header required")
    shard_sources = {p.name: p.read_text(encoding="utf-8", errors="replace")
                     for p in shard_paths}
    hashes = {p.name: digest(p.read_bytes()) for p in shard_paths}
    verified = validate_parent(meta, parent, hashes, shard_sources)
    base = import_module(a.base_module, "k1_post_two_root_original_base")
    prior = import_module(a.previous_planner, "k1_post_two_root_previous_planner")
    by_va, by_name = base.load_ranges(a.functions)
    generated = base.load_generated(a.generated, by_name)
    original_cache = a.functions.parent / ".disasm_cache.json"
    if not original_cache.is_file() or json.loads(
        original_cache.read_text(encoding="utf-8-sig")
    ).get("xbe_hash", "").upper() != RETAIL_SHA:
        raise ValueError("Original retail XBE disassembler cache hash mismatch")
    compiled_owners, info = prior.owner_inventory(parent.decode("utf-8"), a.shards)
    expected_targets = {PREV_TARGET, PREV_CALLEE}
    if not expected_targets.issubset(info["compiled_in_64_or_main"]) or (
        not expected_targets.issubset(info["main_pack_lookup_vas"])
    ):
        raise ValueError("Previous two original .text functions are not both compiled/routed")

    # The previous planner's established classifier handles exact entry,
    # interior translated label, and absent-in-inventory correctly.
    classification = prior.classify(TARGET, by_va, generated)
    original_owner = (
        int(classification["owner"], 16)
        if classification.get("owner") else None
    )
    origin = generated.get(original_owner, {})
    src = origin.get("source", "")
    compile_owners = compiled_owners.get(original_owner, [])
    in_lookup = TARGET in info["main_pack_lookup_vas"]
    if classification["kind"] == "exact_source_entry":
        if TARGET in info["compiled_in_64_or_main"]:
            gate = (
                "Original 002228C0 body already compiled; check exact DIRECT dispatch "
                "router/lookup/guest frame; do not emit duplicate function body"
                if not in_lookup else
                "Original 002228C0 already compiled AND in main pack lookup; "
                "inspect DIRECT router ABI/callsite rather than inventing another function"
            )
        else:
            gate = (
                "Exact retail original function 002228C0 source exists but is absent "
                "from the derived 64-TU/main binary; batch source-authentic function "
                "and bounded dependency closure only after support/ABI proof"
            )
    elif classification["kind"] == "interior_label":
        gate = (
            "Original target 002228C0 is an interior translated label; "
            "requires original instruction-state/ABI entry proof, NOT direct function insertion"
        )
    elif classification["kind"] == "interior_missing_label":
        gate = (
            "Original target 002228C0 is interior without original generated label; "
            "decode verified original XBE instructions before building"
        )
    else:
        gate = (
            "No proven original function entry at 002228C0; "
            "investigate XBE code/data/disassembler provenance, NO build"
        )

    # Walk bounded original .text source callgraph, including already
    # compiled parents, for a coherent next batch. Never interpret the
    # hardware router caller as proof of an original x86 callsite.
    prior.ROOTS = (
        (TARGET, "hardware DIRECT_FRONTIER 0x002228C0"),
        (PREV_TARGET, "preceding hardware ICALL_SAFE original target"),
        (PREV_CALLEE, "preceding original direct callee"),
    )
    prior.MAX_DEPTH = MAX_DEPTH
    prior.MAX_NEW = MAX_NEW
    missing, graph = prior.walk_missing_graph(
        generated, by_va, base, info["compiled_in_64_or_main"])
    direct_callees = []
    if classification["kind"] == "exact_source_entry":
        names = set(base.CALL_RE.findall(base.mask_noncode(src)))
        for name in sorted(names):
            row = next((g for g in generated.values()
                        if g["name"] == name), None)
            if row is not None:
                va = int(name[4:], 16)
                c = prior.classify(va, by_va, generated)
                c["compiled"] = va in info["compiled_in_64_or_main"]
                c["in_main_pack_lookup"] = va in info["main_pack_lookup_vas"]
                direct_callees.append(c)
    report = {
        "status": OUTPUT_STATUS,
        "hardware": {
            "previous_boundary": {"kind": "ICALL_SAFE", "target": "0x001F7620",
                                  "ticks": PREV_TICKS},
            "new_boundary": {"kind": "DIRECT_FRONTIER", "target": "0x002228C0",
                             "ticks": NEW_TICKS, "fault": 0,
                             "guest_esp": "0x008BF7C0",
                             "guest_eax": "0x00425908",
                             "guest_ecx": "0x004256EC",
                             "guest_edx": "0x00000000",
                             "guest_esi": "0x00417600"},
            "ticks_advanced": NEW_TICKS - PREV_TICKS,
            "native_xenos_reset_pass": True,
            "display_calls": 0,
            "framebuffer": "0x00000000",
            "audio_fallback_allocation_failed": {"bytes": 96,
                                                  "source_reported": True},
            "movie_contract_drift_messages": 9,
            "actual_hard_stop_is_movie": False,
        },
        "prior_stage_sha256": {
            "main": digest(parent),
            "manifest": digest(a.parent_manifest.read_bytes()),
        },
        "verified_compiled_parent": verified,
        "original_retail_disasm_sha256": RETAIL_SHA,
        "original_64_true_tus_verified": True,
        "compiled_original_function_count": info["compiled_functions_count"],
        "target": {
            "original_classification": classification,
            "compiled_owner_files": compile_owners,
            "in_main_pack_lookup": in_lookup,
            "original_generated_c_file": origin.get("file"),
            "original_source_sha256": (
                digest(src.encode("utf-8")) if src else None),
            "original_source_top": src.splitlines()[:48],
            "original_source_bottom": src.splitlines()[-48:],
            "direct_original_source_callees": direct_callees,
        },
        "bounded_text_graph": graph,
        "missing_source_candidates": missing,
        "next_gate": gate,
        "safe_to_build": False,
        "safe_to_insert_function_at_unknown_va": False,
        "xdk_invoked": False,
        "source_only": True,
        "hardware_evidence_limit": (
            "The latest log does not print an explicit 001F7620 function-entry "
            "counter. Boundary movement alone does not prove either new body "
            "executed or that the full renderer is operational."
        ),
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(report, indent=2) + "\n", encoding="utf-8")
    print("[K1-DIRECT-NEXT] RETAIL DISASM SHA + SIX-CASE OWNER + BOTH ORIGINAL TWO-ROOT LOOKUPS PASS")
    print("[K1-DIRECT-NEXT] HARDWARE: old ICALL_SAFE 001F7620 tick=%d -> new DIRECT 002228C0 tick=%d (+%d), fault=0" %
          (PREV_TICKS, NEW_TICKS, NEW_TICKS - PREV_TICKS))
    print("[K1-DIRECT-NEXT] TARGET class=%s owner=%s original_source=%s" %
          (classification["kind"], classification["owner"], origin.get("file")))
    print("[K1-DIRECT-NEXT] compiled_owner_files=%s pack_lookup=%s" %
          (compile_owners, in_lookup))
    print("[K1-DIRECT-NEXT] ORIGINAL GRAPH: visited=%d compiled=%d missing=%d truncated=%s" %
          (graph["original_graph_visited"],
           graph["original_compiled_nodes_traversed"],
           graph["missing_original_functions"],
           graph["graph_truncated"]))
    for item in missing[:50]:
        print("[K1-DIRECT-NEXT] MISSING ORIGINAL C %s depth=%s file=%s from=%s" %
              (item["va"], item["depth"], item["source_file"],
               item["reached_from"]))
    print("[K1-DIRECT-NEXT] GATE: " + gate)
    print("[K1-DIRECT-NEXT] NO XDK. NO XEX CHANGED. NO PIXELS CLAIMED.")
    print("[K1-DIRECT-NEXT] Report: " + str(a.out))


def self_test():
    valid_meta = {
        "status": PARENT_STATUS,
        "marker": PARENT_MARKER,
        "original_retail_xbe_sha256": RETAIL_SHA,
        "new_members_count": 2,
        "original_true_tus": 64,
        "original_true_tus_reused_not_modified": True,
        "original_runtime_header_unchanged": True,
        "lookup_both_exact_original_entries": True,
        "preserves_six_case_graphics_dispatch": True,
        "native_xenos_reset_source_unchanged": True,
        "unknown_indirect_hard_fence_unchanged": True,
        "dummy_guest_data": False,
        "new_members": ["0x001F7620", "0x001F7520"],
        "six_case_verified_owner_file": "translated_017.cpp",
        "six_case_verified_common_tail_owner": "translated_017.cpp",
    }
    source = "\n".join((
        PARENT_MARKER,
        "case 0x001F7620u: return sub_001F7620;",
        "case 0x001F7520u: return sub_001F7520;",
        "K1D3D SECOND: native Xenos Reset PASS",
        "P6DQ ROCKET HARD STOP",
        "K1STATE MAIN CHECKPOINT:",
    )).encode("utf-8")
    shards = {"translated_%03d.cpp" % i: "" for i in range(64)}
    patched = (SIX_CASE_MARKER +
               "k1d3d_296550_original_sixcase(eax, k1_original_tail_target)" +
               "RECOMP_ITAIL(k1_original_tail_target)" +
               "void sub_002965A8(void)")
    shards["translated_017.cpp"] = patched
    sh = {name: digest(body.encode("utf-8")) for name, body in shards.items()}
    valid_meta["new_main_sha256"] = digest(source)
    valid_meta["original_64_true_tu_sha256"] = sh
    good = validate_parent(valid_meta, source, sh, shards)
    assert good["six_case_owner"] == "translated_017.cpp"
    assert good["six_case_common_owner"] == "translated_017.cpp"
    for changed in (
        {**valid_meta, "new_main_sha256": "000"},
        {**valid_meta, "new_members_count": 1},
        {**valid_meta, "six_case_verified_owner_file": "translated_006.cpp"},
        {**valid_meta, "original_true_tus_reused_not_modified": False},
    ):
        try:
            validate_parent(changed, source, sh, shards)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid manifest source proof accepted")
    try:
        validate_parent(valid_meta, source, sh, {**shards, "translated_017.cpp": ""})
    except ValueError:
        pass
    else:
        raise AssertionError("Missing six-case bridge source accepted")
    print("[K1-DIRECT-NEXT] SELFTEST PASS: six-case TrueTU owner, exact 64 hashes, both original bodies, no XDK")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for arg in ("base-module", "previous-planner", "functions", "generated",
                "parent", "parent-manifest", "shards", "out"):
        p.add_argument("--" + arg, type=Path)
    args = p.parse_args()
    if args.self_test:
        self_test()
    else:
        for name in ("base_module", "previous_planner", "functions", "generated",
                     "parent", "parent_manifest", "shards", "out"):
            if getattr(args, name) is None:
                p.error("Missing --" + name.replace("_", "-"))
        analyze(args)


if __name__ == "__main__":
    main()
