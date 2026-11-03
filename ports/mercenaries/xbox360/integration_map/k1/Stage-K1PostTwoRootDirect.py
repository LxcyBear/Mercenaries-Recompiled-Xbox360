#!/usr/bin/env python3
"""One build unit: original 002228C0 after hardware r4 DIRECT_FRONTIER.

Only the retail-generated 0x002228C0 .text function from recomp_0011.c
is introduced, using the already hardware-tested original-C packer. Reuse
the unchanged 64 TrueTUs from the exact r4 parent and refuse loss of the
six-case guest D3D bridge, its common tail, or prior two .text functions.
No synthetic source, no fake pixels, no guessed guest ABI, no XDK here.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

TARGET = 0x002228C0
PREV = (0x001F7620, 0x001F7520)
ORIGINAL_FILE = "recomp_0011.c"
RETAIL_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PARENT_MARKER = "K1-TEXT-ICALL-1F7620-1F7520-20261103"
SIX_CASE_MARKER = "K1D3D-296550-SIXCASES-ONEBUILD-20261103"
MARKER = "K1-TEXT-DIRECT-002228C0-20261103"
STATUS = "K1_TEXT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY_NO_XDK"


def digest(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    if not spec or not spec.loader:
        raise ValueError("Required maintained source module is missing: " + str(path))
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def verify_original_graph(post, base, generated, by_va, compiled):
    # Uses EXACT same 4-deep graph/96-member cap as the user's successful
    # source-only hardware audit. This is not a claim of a runtime call tree.
    post.ROOTS = (
        (TARGET, "hardware DIRECT_FRONTIER 0x002228C0"),
        (PREV[0], "preceding original ICALL_SAFE"),
        (PREV[1], "preceding original direct callee"),
    )
    post.MAX_DEPTH = 4
    post.MAX_NEW = 96
    missing, graph = post.walk_missing_graph(
        generated, by_va, base, compiled)
    roots = {int(item["va"], 16) for item in missing}
    if (roots != {TARGET} or graph["graph_truncated"] or
        graph["remaining_queue"] != 0):
        raise ValueError("Hardware direct .text dependency graph changed; "
                         "expected exactly the original 002228C0 missing")
    return missing, graph


def stage(args):
    parent_blob = args.parent.read_bytes()
    meta_blob = args.parent_manifest.read_bytes()
    parent_meta = json.loads(meta_blob.decode("utf-8-sig"))
    shard_files = sorted(args.shards.glob("translated_???.cpp"))
    if (len(shard_files) != 64 or
            not (args.shards / "translated_runtime.h").is_file()):
        raise ValueError("Expected exact original 64 TrueTUs and runtime header")
    shard_blob = {p.name: p.read_bytes() for p in shard_files}
    hashes = {name: digest(blob) for name, blob in shard_blob.items()}
    texts = {name: blob.decode("utf-8", errors="replace")
             for name, blob in shard_blob.items()}

    post = load(args.post_planner, "k1_r5_direct_post_audit")
    parent_proof = post.validate_parent(parent_meta, parent_blob, hashes, texts)
    if (parent_meta.get("xdk_verified") is not False or
            parent_meta.get("hardware_verified") is not False or
            parent_meta.get("original_proven_source_file") != "recomp_0010.c" or
            parent_meta.get("hardware_observed_target") != "0x001F7620"):
        raise ValueError("Unexpected r4 two-body parent manifest")
    if (parent_meta.get("six_case_owner_marker_verified") is not True or
            parent_meta.get("six_case_original_64_true_tu_sha256_verified") is not True):
        raise ValueError("Hardware r4 six-case bridge/64-TU proof missing")
    cached = args.functions.parent / ".disasm_cache.json"
    if (not cached.is_file() or
            json.loads(cached.read_text(encoding="utf-8-sig"))
            .get("xbe_hash", "").upper() != RETAIL_SHA):
        raise ValueError("Original retail XBE SHA-256 corpus mismatch")

    base = load(args.base_module, "k1_r5_direct_base")
    bb = load(args.bb_module, "k1_r5_direct_bb")
    bc = load(args.bc_module, "k1_r5_direct_bc")
    previous = load(args.previous_planner, "k1_r5_direct_inventory")
    old_pack = load(args.previous_stage, "k1_r5_reuse_proven_pack")
    pc_retail = load(args.pc_retail_module, "k1_r5_pc_original_retail_patch")
    pc_commit = pc_retail.verify_pc_commit(args.pc_reference)
    if pc_commit != pc_retail.PC_SHA:
        raise ValueError("Pinned PC commit mismatch")
    retail_proof = pc_retail.verify_original_x86(
        args.retail_xbe, args.retail_auditor
    )
    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated, by_name)

    originals, info = previous.owner_inventory(
        parent_blob.decode("utf-8"), args.shards)
    cls = previous.classify(TARGET, by_va, generated)
    if (cls["kind"] != "exact_source_entry" or
            cls["owner"] != "0x002228C0" or
            cls["source_file"] != ORIGINAL_FILE):
        raise ValueError("Original retail 002228C0 is no longer exact .text entry")
    if (TARGET not in generated or
            generated[TARGET]["file"] != ORIGINAL_FILE or
            not 0x00011000 <= TARGET < by_va[TARGET]["end"] <= 0x00255620):
        raise ValueError("002228C0 original source/section end boundary changed")
    if (TARGET in originals or TARGET in info["main_pack_lookup_vas"] or
            TARGET in info["compiled_in_64_or_main"]):
        raise ValueError("002228C0 is already compiled or in lookup; no duplicate code")
    if not set(PREV).issubset(info["compiled_in_64_or_main"]) or (
            not set(PREV).issubset(info["main_pack_lookup_vas"])):
        raise ValueError("Previous r4 original packed entries no longer in source")
    if parent_proof["previous_original_packed_members"] != [
            "0x001F7620", "0x001F7520"]:
        raise ValueError("Original r4 two-body parent compiler provenance changed")
    missing, graph = verify_original_graph(
        previous, base, generated, by_va, info["compiled_in_64_or_main"])
    # PC port adds optional developer-region completed-read reuse to
    # original retail 002228C0. Restore precisely the original CMP/JNE
    # branch from the pinned PC before-template; the verified retail XBE
    # independently proves its x86 instruction and destination.
    # Do not emit fake recomp_dev_region_import_active() == 0 or
    # pretend the PC developer feature exists on Xbox 360.
    restored_source, pc_patch_proof = pc_retail.restore_exact_pc_patch(
        generated[TARGET]["source"], args.pc_reference,
        attest_x86=retail_proof,
    )
    generated[TARGET] = dict(generated[TARGET])
    generated[TARGET]["source"] = restored_source
    if (pc_retail.HELPER in restored_source or
            not pc_patch_proof["x86_retail_cmp_jne_proof"]["original_002228f0_x86_cmp_jne"]):
        raise ValueError("PC-only developer hook still present after original retail restoration")

    # Reuse audited packer with a different exact original function. The
    # original packer fully localizes C guest registers and rewrites direct
    # calls only when the target is already present; it fences unknowns.
    old_pack.ROOT = TARGET
    old_pack.MEMBERS = (TARGET,)
    old_pack.MARKER = MARKER
    old_pack.OPT_PLACEHOLDER = "/* K1_TEXT_DIRECT_002228C0_OPT_ON_HIDDEN */"
    # Preserve original external definitions without recompiling, plus
    # source-verified maintained helpers (no fabricated guest state).
    original_support = base.support_symbols
    externals = {"sub_%08X" % va for va in info["compiled_in_64_or_main"]}
    externals.update(original_support(
        (args.shards / "translated_runtime.h").read_text(
            encoding="utf-8", errors="replace")))
    base.support_symbols = lambda text: original_support(text) | externals

    output, frontiers, pruned = old_pack.pack(
        parent_blob.decode("utf-8"), generated,
        info["compiled_in_64_or_main"], base, bb, bc)
    old_source = parent_blob.decode("utf-8")
    if (output.count(MARKER) != 1 or
            output.count("/* " + MARKER + " */") != 1 or
            output.count("case 0x002228C0u: return sub_002228C0;") != 1 or
            TARGET in pruned or pruned):
        raise ValueError("002228C0 original C body/lookup was not staged cleanly")
    for expected in (
        PARENT_MARKER,
        "case 0x001F7620u: return sub_001F7620;",
        "case 0x001F7520u: return sub_001F7520;",
        "K1D3D SECOND: native Xenos Reset PASS",
        "P6DQ ROCKET HARD STOP",
        "K1STATE MAIN CHECKPOINT:",
    ):
        if old_source.count(expected) != 1 or output.count(expected) != 1:
            raise ValueError("r4 exact-original source marker/lookup lost: "+expected)
    for va in PREV:
        if old_pack.source_inventory(output).__contains__(va) is False:
            raise ValueError("Original r4 function definition lost: 0x%08X" % va)
    if (parent_proof["six_case_owner"] != "main.cpp" and (
            SIX_CASE_MARKER in output or
            "k1d3d_296550_original_sixcase" in output)):
        raise ValueError("Original six-case code duplicated in new main")
    if parent_proof["six_case_owner"] == "main.cpp" and (
            output.count(SIX_CASE_MARKER) != 1):
        raise ValueError("Main-owned original six-case bridge lost")

    new_blob = output.encode("utf-8")
    new_manifest = {
        "status": STATUS,
        "marker": MARKER,
        "previous_hardware_boundary_kind": "DIRECT_FRONTIER",
        "previous_hardware_boundary_target": "0x002228C0",
        "previous_hardware_boundary_ticks": 58612771,
        "previous_hardware_display_calls": 0,
        "previous_hardware_fault": 0,
        "original_retail_xbe_sha256": RETAIL_SHA,
        "original_generated_c": ORIGINAL_FILE,
        "original_function_address": "0x002228C0",
        "original_function_sha256": digest(
            generated[TARGET]["source"].encode("utf-8")),
        "pc_reference_git_commit": pc_commit,
        "pc_developer_patch_reverted_to_original_retail": pc_patch_proof,
        "original_graph_missing_count": len(missing),
        "original_graph_missing_addresses": [i["va"] for i in missing],
        "original_graph_compiled_traversed": graph["original_compiled_nodes_traversed"],
        "original_graph_truncated": graph["graph_truncated"],
        "source_only_staged_new_functions": 1,
        "original_r4_bodies_preserved": ["0x001F7620", "0x001F7520"],
        "main_pack_lookup_original_root_present": True,
        "parent_r4_manifest_sha256": digest(meta_blob),
        "parent_r4_main_sha256": digest(parent_blob),
        "new_main_sha256": digest(new_blob),
        "true_tu_count": 64,
        "original_true_tu_hashes_sha256": hashes,
        "original_true_tus_unchanged": True,
        "runtime_header_unchanged": True,
        "six_case_verified_owner": parent_proof["six_case_owner"],
        "six_case_verified_common_owner": parent_proof["six_case_common_owner"],
        "native_xenos_reset_source_preserved": True,
        "unknown_direct_and_indirect_hard_fences_preserved": True,
        "dummy_guest_data": False,
        "new_xdk_verified": False,
        "new_hardware_verified": False,
        "new_display_calls": None,
        "remaining_direct_frontiers": ["0x%08X" % va for va in frontiers],
    }
    if (args.output.resolve() == args.parent.resolve() or
            args.output.parent.resolve() == args.parent.parent.resolve()):
        raise ValueError("Cannot overwrite last known good r4 hardware main")
    args.output.parent.mkdir(parents=True, exist_ok=True)
    manifest_bytes = (json.dumps(new_manifest, indent=2) + "\n").encode("utf-8")
    for path, data in ((args.output, new_blob), (args.manifest, manifest_bytes)):
        if path.is_file() and path.read_bytes() != data:
            raise ValueError("Existing derived output changed; refuse overwrite: "+str(path))
        if not path.exists():
            path.write_bytes(data)
    if args.parent.read_bytes() != parent_blob or (
            args.parent_manifest.read_bytes() != meta_blob):
        raise ValueError("Hardware-good r4 parent changed during stage")
    for p in shard_files:
        if p.read_bytes() != shard_blob[p.name]:
            raise ValueError("Original six-case translated TrueTU modified by stage: "+p.name)
    print("[K1-DIRECT-R5] ORIGINAL RETAIL .text EXACT ENTRY 002228C0 from recomp_0011.c PASS")
    print("[K1-DIRECT-R5] SOURCE GRAPH: %d original missing, %d compiled traversed, truncated=%s" %
          (len(missing), graph["original_compiled_nodes_traversed"], graph["graph_truncated"]))
    print("[K1-DIRECT-R5] PINNED PC PATCH 278: 002228F0 original retail CMP/JNE RESTORED with XBE bytes proof")
    print("[K1-DIRECT-R5] NO PC developer-import hook/NO guessed helper or stub")
    print("[K1-DIRECT-R5] PACKED: one retail-restored generated-C body + exact 002228C0 main lookup")
    print("[K1-DIRECT-R5] r4 ORIGINAL 001F7620/001F7520 + six-case owner %s preserved" %
          parent_proof["six_case_owner"])
    print("[K1-DIRECT-R5] ALL 64 TrueTUs unchanged, native Xenos Reset and unknown hard fences kept")
    print("[K1-DIRECT-R5] NO XDK, NO PIXELS CLAIMED")
    print("[K1-DIRECT-R5] Manifest: "+str(args.manifest))


def selftest(args):
    previous = load(args.previous_planner, "k1_r5_fixture_previous_planner")
    if not (hasattr(previous, "walk_missing_graph") and
            hasattr(previous, "owner_inventory") and
            hasattr(previous, "classify")):
        raise AssertionError("R5 original-source graph/inventory module invalid")
    old = load(args.previous_stage, "k1_r5_synthetic_old_packer")
    old.ROOT = TARGET
    old.MEMBERS = (TARGET,)
    old.MARKER = MARKER
    old.OPT_PLACEHOLDER = "/* K1_TEXT_DIRECT_002228C0_OPT_ON_HIDDEN */"
    class FakeBase:
        STANDARD_CALLS = set()
        @staticmethod
        def support_symbols(text):
            return set()
    class FakeBC:
        SWEEP_ROOT = 0
        instrument_root_entry = None
        @staticmethod
        def insert_pack_members(source, base, bb, generated, members, expanded,
                                require_sweep_root=True):
            assert require_sweep_root and FakeBC.SWEEP_ROOT == TARGET
            assert members == [TARGET] and expanded == {TARGET, *PREV}
            assert "P6DQ ROCKET HARD STOP" in source
            source = source.replace(old.CANON, "static void sub_002228C0(void);\n"+old.CANON, 1)
            source = source.replace(
                "    default: return (recomp_func_t)0;",
                "    case 0x002228C0u: return sub_002228C0;\n"
                "    default: return (recomp_func_t)0;", 1)
            source = source.replace('#pragma optimize("", on)',
                "static void sub_002228C0(void) {return;}\n#pragma optimize(\"\", on)", 1)
            return source, {TARGET: "original-generated-fixture"}, set(), {}
    fixture = (
        "/* "+PARENT_MARKER+" */\n"
        "P6DQ ROCKET HARD STOP\n"
        "K1D3D SECOND: native Xenos Reset PASS\n"
        "K1STATE MAIN CHECKPOINT:\n"
        "case 0x00289E20u: return sub_00289E20;\n"
        "case 0x0017A0A0u: return sub_0017A0A0;\n"
        "case 0x001F7620u: return sub_001F7620;\n"
        "case 0x001F7520u: return sub_001F7520;\n"
        "static void sub_001F7620(void) {return;}\n"
        "static void sub_001F7520(void) {return;}\n"
        "recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n"
        "{\n"
        "    default: return (recomp_func_t)0;\n"
        "}\n"
        "#pragma optimize(\"\", on)\n"
    )
    fake_generated = {TARGET: {"name": "sub_002228C0",
                               "source": "void sub_002228C0(void) {return;}",
                               "file": ORIGINAL_FILE}}
    staged, _, pruned = old.pack(
        fixture, fake_generated, set(PREV), FakeBase, None, FakeBC)
    assert not pruned and staged.count("/* "+MARKER+" */") == 1
    assert staged.count("case 0x002228C0u: return sub_002228C0;") == 1
    assert staged.count(PARENT_MARKER) == 1
    assert all(staged.count(
        "case 0x%08Xu: return sub_%08X;" % (va, va)) == 1 for va in PREV)
    for bad in (
        fixture.replace(PARENT_MARKER, "source gone"),
        fixture.replace("P6DQ ROCKET HARD STOP", "fence gone"),
        fixture.replace("K1D3D SECOND: native Xenos Reset PASS", "reset gone"),
        staged,
    ):
        try:
            if PARENT_MARKER not in bad:
                raise ValueError("Missing hardware r4 marker")
            old.pack(bad, fake_generated, set(PREV), FakeBase, None, FakeBC)
        except ValueError:
            pass
        else:
            raise AssertionError("Synthetic parent source gate accepted unsafe fixture")
    print("[K1-DIRECT-R5] SELFTEST PASS: r4 source preserved, exact one original body/lookup, no XDK")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for arg in (
        "base-module", "bb-module", "bc-module", "post-planner",
        "previous-planner", "previous-stage", "pc-retail-module",
        "pc-reference", "retail-xbe", "retail-auditor",
        "functions", "generated",
        "parent", "parent-manifest", "shards", "output", "manifest",
    ):
        p.add_argument("--"+arg, type=Path)
    args = p.parse_args()
    if args.self_test:
        if args.previous_stage is None or args.previous_planner is None:
            p.error("--previous-stage and --previous-planner required for self-test")
        selftest(args)
    else:
        for attr in ("base_module", "bb_module", "bc_module",
                     "post_planner", "previous_planner", "previous_stage",
                     "pc_retail_module", "pc_reference", "retail_xbe", "retail_auditor",
                     "functions", "generated", "parent", "parent_manifest",
                     "shards", "output", "manifest"):
            if getattr(args, attr) is None:
                p.error("Missing --"+attr.replace("_", "-"))
        stage(args)


if __name__ == "__main__":
    main()
