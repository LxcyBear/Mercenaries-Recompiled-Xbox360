#!/usr/bin/env python3
"""K1 post-sixcase Xbox360 source-authentic 001F7620+001F7520 batch.

Source-only by default. Promote two exact, missing retail x86 -> C source
functions into the *derived* graphics main, preserving original 64 TrueTUs,
six-case guest ESI/RET bridge and native Xenos Reset. No fake pixels or
speculative ABI bridge.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

ROOT = 0x001F7620
CALLEE = 0x001F7520
MEMBERS = (ROOT, CALLEE)
MARKER = "K1-TEXT-ICALL-1F7620-1F7520-20261103"
RETAIL_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PARENT_STATUS = "K1_D3D_SIX_CASES_SOURCE_ONLY_NO_XDK"
PARENT_MARK = "K1D3D-296550-SIXCASES-ONEBUILD-20261103"
STATUS = "K1_NEXT_ICALL_TWO_SOURCE_AUTHENTIC_BODIES_NO_XDK"
LOOKUP = re.compile(
    r'(?m)^(?:static[ \t]+)?recomp_func_t '
    r'phase4c_lookup_pack_func\(uint32_t xbox_va\)\n\{'
)
CANON = "static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
OPT_ON = '#pragma optimize("", on)'
OPT_PLACEHOLDER = '/* K1_NEXT_ICALL_1F7620_OPT_ON_HIDDEN */'
DEF = re.compile(
    r'(?m)^\s*(?:static\s+)?void\s+(sub_[0-9A-Fa-f]{8})'
    r'\s*\(\s*void\s*\)\s*\{'
)
PACK_CASE = re.compile(
    r'\bcase\s+0x([0-9A-Fa-f]{8})u\s*:\s*return\s+(sub_[0-9A-Fa-f]{8})\s*;'
)
REQUIRED = (
    "K1D3D SECOND: native Xenos Reset PASS",
    "P6DQ ROCKET HARD STOP",
    "K1STATE MAIN CHECKPOINT:",
    "case 0x00289E20u: return sub_00289E20;",
    "case 0x0017A0A0u: return sub_0017A0A0;",
    "phase4c_lookup_pack_func",
)


def digest(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ValueError("Required maintained original source module missing: "+str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def source_inventory(text: str) -> set[int]:
    return {int(m.group(1)[4:], 16) for m in DEF.finditer(text)}


def prepare(parent: str) -> tuple[str, str, str]:
    if '\r' in parent.replace('\r\n', ''):
        raise ValueError("Mixed/invalid parent source line endings")
    newline = '\r\n' if '\r\n' in parent else '\n'
    normalized = parent.replace('\r\n', '\n')
    for required in REQUIRED:
        if required not in normalized:
            raise ValueError("Hardware-proven graphics fence/source lost: "+required)
    if PARENT_MARK not in normalized:
        raise ValueError("Hardware six-case original source missing")
    if MARKER in normalized or OPT_PLACEHOLDER in normalized:
        raise ValueError("Already staged or dirty output")
    for va in MEMBERS:
        name = "sub_%08X" % va
        if va in source_inventory(normalized) or re.search(
                r'\bcase\s+0x%08Xu\s*:' % va, normalized):
            raise ValueError("Original body or lookup already present: "+name)
    definitions = list(LOOKUP.finditer(normalized))
    if len(definitions) != 1:
        raise ValueError("Canonical real XDK pack-lookup definition absent/duplicated")
    original = definitions[0].group()
    normalized = (normalized[:definitions[0].start()] +
                  CANON + normalized[definitions[0].end():])
    if normalized.count(CANON) != 1:
        raise ValueError("Temporary pack lookup declaration not unique")
    normalized = normalized.replace(OPT_ON, OPT_PLACEHOLDER)
    normalized += '\n#pragma optimize("", off)\n#pragma optimize("", on)\n'
    return normalized, original, newline


def restore(packed: str, original_lookup: str, newline: str) -> str:
    if packed.count(CANON) != 1:
        raise ValueError("Real pack lookup changed by emitter")
    packed = packed.replace(CANON, original_lookup, 1)
    packed = packed.replace(OPT_PLACEHOLDER, OPT_ON)
    if MARKER in packed or PARENT_MARK not in packed:
        raise ValueError("Parent stage already contains next pack marker")
    packed = packed.replace(PARENT_MARK, PARENT_MARK + " | " + MARKER, 1)
    if newline == '\r\n':
        packed = packed.replace('\n', '\r\n')
    for required in REQUIRED:
        if required not in packed:
            raise ValueError("Original hardware source/fence lost in result: "+required)
    return packed


def pack(parent: str, generated: dict, compiled: set[int], base, bb, bc):
    prepared, original_lookup, newline = prepare(parent)
    for va in MEMBERS:
        if va not in generated:
            raise ValueError("No original generated C body for retail %08X" % va)
        if va in compiled:
            raise ValueError("Original %08X already compiled, refuse duplicate body" % va)
    original_support = base.STANDARD_CALLS.copy()
    old_root = bc.SWEEP_ROOT
    old_entry = bc.instrument_root_entry
    # No dummy whitelist: these are existing original maths runtime helpers.
    base.STANDARD_CALLS.update(("sin", "cos"))
    try:
        bc.SWEEP_ROOT = ROOT
        bc.instrument_root_entry = lambda rendered, name: rendered
        chosen = list(MEMBERS)
        staged, rendered, frontiers, pruned = bc.insert_pack_members(
            prepared, base, bb, generated, chosen,
            compiled | set(MEMBERS), require_sweep_root=True,
        )
    finally:
        bc.SWEEP_ROOT = old_root
        bc.instrument_root_entry = old_entry
        base.STANDARD_CALLS.clear()
        base.STANDARD_CALLS.update(original_support)
    lost = [va for va in MEMBERS if va not in rendered or va in pruned]
    if lost or len(chosen) != len(MEMBERS):
        raise ValueError(
            "Source dependencies unresolved, cannot package both exact "
            "original text bodies in one build: "+
            repr({"lost": lost, "pruned": pruned, "kept": chosen}))
    for va in MEMBERS:
        entry = "case 0x%08Xu: return sub_%08X;" % (va, va)
        if staged.count(entry) != 1:
            raise ValueError("Exact root and callee must be in main lookup: "+entry)
        if len(re.findall(r'\bstatic\s+void\s+sub_%08X\s*\(' % va,
                          staged)) < 1:
            raise ValueError("Real source declaration/definition absent: %08X" % va)
    restored = restore(staged, original_lookup, newline)
    return restored, sorted(frontiers), pruned


def stage(a) -> None:
    parent_manifest = json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    parent_bytes = a.parent.read_bytes()
    if (parent_manifest.get("status") != PARENT_STATUS or
        parent_manifest.get("marker") != PARENT_MARK or
        parent_manifest.get("original_retail_xbe_sha256") != RETAIL_SHA or
        parent_manifest.get("staged_main_sha256") != digest(parent_bytes) or
        parent_manifest.get("original_true_tus") != 64 or
        parent_manifest.get("xenos_reset_source_unchanged") is not True or
        parent_manifest.get("preserves_unknown_tail_hard_fence") is not True or
        parent_manifest.get("synthetic_guest_pixels") is not False or
        parent_manifest.get("modified_runtime_header") is not False):
        raise ValueError("Hardware six-case parent SHA/retail provenance changed")

    shards = sorted(a.shards.glob("translated_???.cpp"))
    if len(shards) != 64 or not (a.shards / "translated_runtime.h").is_file():
        raise ValueError("Missing parent 64 TrueTU + original runtime header")
    existing = source_inventory(parent_bytes.decode("utf-8", errors="replace"))
    hashes = {}
    for file in shards:
        contents = file.read_bytes()
        hashes[file.name] = digest(contents)
        if hashes[file.name] != parent_manifest.get("derived_64_tu_hashes", {}).get(file.name):
            raise ValueError("Hardware parent TrueTU changed: "+file.name)
        for va in source_inventory(contents.decode("utf-8", errors="replace")):
            if va in existing:
                raise ValueError("Original function duplicated in main/TrueTUs: %08X" % va)
            existing.add(va)
    cache = a.functions.parent / ".disasm_cache.json"
    if (not cache.is_file() or json.loads(cache.read_text(encoding="utf-8-sig"))
            .get("xbe_hash", "").upper() != RETAIL_SHA):
        raise ValueError("Retail XBE provenance changed")
    base = load(a.base_module, "k1_next_batch_base")
    bb = load(a.bb_module, "k1_next_batch_bb")
    bc = load(a.bc_module, "k1_next_batch_bc")
    by_va, by_name = base.load_ranges(a.functions)
    generated = base.load_generated(a.generated, by_name)
    if (any(va not in by_va or va not in generated for va in MEMBERS) or
        generated[ROOT]["file"] != "recomp_0010.c" or
        generated[CALLEE]["file"] != "recomp_0010.c"):
        raise ValueError("Exact original .text entry/callee provenance mismatch")
    if not (0x00011000 <= ROOT < by_va[ROOT]["end"] <= 0x00255620 and
            0x00011000 <= CALLEE < by_va[CALLEE]["end"] <= 0x00255620):
        raise ValueError("Original retail target/callee .text section bounds invalid")
    source_calls = set(base.CALL_RE.findall(
        base.mask_noncode(generated[ROOT]["source"])
    ))
    if ("sub_%08X" % CALLEE) not in source_calls:
        raise ValueError("Target does not call real original 001F7520 helper")
    # Source graph proof from last offline hardware witness.
    next_planner = load(a.planner, "k1_next_batch_source_planner")
    original_ownership, count_data = next_planner.owner_inventory(
        parent_bytes.decode("utf-8"), a.shards)
    if set(original_ownership) != existing:
        raise ValueError("Compiled source ownership inconsistent with six-case planner")
    root_status = next_planner.summarize_target(
        by_va, generated, original_ownership,
        count_data["main_pack_lookup_vas"]
    )
    if (root_status["target_classification"]["kind"] != "exact_source_entry" or
        root_status["compiled_owner_files"] or
        root_status["main_dispatch_lookup_entry_present"]):
        raise ValueError("Hardware ICALL 001F7620 already compiled or no longer exact entry")
    # Existing 64 TrueTUs export original functions. Support finder must
    # account for those external linkable functions, not retranslate them.
    original_support = base.support_symbols
    external = {"sub_%08X" % va for va in existing}
    external.update(original_support(
        (a.shards / "translated_runtime.h").read_text(encoding="utf-8", errors="replace")
    ))
    base.support_symbols = lambda text: original_support(text) | external
    main_before = parent_bytes.decode("utf-8")
    output, frontiers, pruned = pack(main_before, generated, existing, base, bb, bc)
    if (output.count(MARKER) != 1 or
        'case 0x001F7620u: return sub_001F7620;' not in output or
        'case 0x001F7520u: return sub_001F7520;' not in output):
        raise ValueError("Both original missing root/helper and marker not linked")
    if ('K1D3D-296550-SIXCASES-ONEBUILD-20261103' not in output or
        output.count("K1STATE MAIN CHECKPOINT:") != 1):
        raise ValueError("Six-way graphics dispatch or state checkpoint lost")
    changed = output.encode("utf-8")
    metadata = {
        "status": STATUS,
        "marker": MARKER,
        "hardware_observed_target": "0x001F7620",
        "original_retail_xbe_sha256": RETAIL_SHA,
        "original_proven_source_file": "recomp_0010.c",
        "root_original_source_sha256": digest(
            generated[ROOT]["source"].encode("utf-8")),
        "callee_original_source_sha256": digest(
            generated[CALLEE]["source"].encode("utf-8")),
        "parent_manifest_sha256": digest(a.parent_manifest.read_bytes()),
        "parent_main_sha256": digest(parent_bytes),
        "new_main_sha256": digest(changed),
        "original_true_tus": 64,
        "original_true_tus_reused_not_modified": True,
        "original_runtime_header_unchanged": True,
        "original_64_true_tu_sha256": hashes,
        "new_members": ["0x001F7620", "0x001F7520"],
        "new_members_count": 2,
        "remaining_direct_frontiers": ["0x%08X" % x for x in frontiers],
        "pruned_original_functions": {
            "0x%08X" % k: v for k, v in pruned.items()},
        "lookup_both_exact_original_entries": True,
        "preserves_six_case_graphics_dispatch": True,
        "native_xenos_reset_source_unchanged": True,
        "unknown_indirect_hard_fence_unchanged": True,
        "dummy_guest_data": False,
        "xdk_verified": False,
        "hardware_verified": False,
        "display_calls_observed_new_run": None,
    }
    if a.output.resolve() == a.parent.resolve() or (
        a.output.parent.resolve() == a.parent.parent.resolve()):
        raise ValueError("Refuse overwrite of known hardware-good parent main")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    data = (json.dumps(metadata, indent=2)+"\n").encode("utf-8")
    for path, payload in ((a.output, changed), (a.manifest, data)):
        if path.is_file():
            if path.read_bytes() != payload:
                raise ValueError("Output already exists with different contents: "+str(path))
        elif path.exists():
            raise ValueError("Non-file output path: "+str(path))
        else:
            path.write_bytes(payload)
    if a.parent.read_bytes() != parent_bytes:
        raise ValueError("Original six-case parent mutated by stage")
    for path in shards:
        if digest(path.read_bytes()) != hashes[path.name]:
            raise ValueError("Original six-case TrueTU mutated: "+path.name)
    print("[K1-NEXT-PACK] ORIGINAL .text 001F7620 + direct CALLEE 001F7520 PASS")
    print("[K1-NEXT-PACK] Exact original generated C from recomp_0010.c, no synthetic bodies")
    print("[K1-NEXT-PACK] INCREMENTAL BATCH: 2 exact new functions, both in pack lookup")
    print("[K1-NEXT-PACK] Six real D3D switch cases, native Xenos Reset and hard fences preserved")
    print("[K1-NEXT-PACK] Parent 64 TrueTUs unchanged, reused with original runtime header")
    print("[K1-NEXT-PACK] NO XDK, NO XEX, NO NEW PIXELS CLAIMED")
    print("[K1-NEXT-PACK] Source-only manifest: "+str(a.manifest))


def selftest() -> None:
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
            assert require_sweep_root and FakeBC.SWEEP_ROOT == ROOT
            assert members == list(MEMBERS)
            assert expanded == set(MEMBERS)
            assert "P6DQ ROCKET HARD STOP" in source
            definition = CANON
            source = source.replace(definition,
                "static void sub_001F7620(void);\n"
                "static void sub_001F7520(void);\n\n"+definition,1)
            source = source.replace("    default: return (recomp_func_t)0;",
                "    case 0x001F7620u: return sub_001F7620;\n"
                "    case 0x001F7520u: return sub_001F7520;\n"
                "    default: return (recomp_func_t)0;",1)
            anchor = '#pragma optimize("", on)'
            source = source.replace(anchor,
                "static void sub_001F7620(void) {sub_001F7520();}\n"
                "static void sub_001F7520(void) {return;}\n"+anchor,1)
            return source, {ROOT: "one", CALLEE: "two"}, [], {}
    fixture = (
        'P6DQ ROCKET HARD STOP\n'
        'K1D3D SECOND: native Xenos Reset PASS\n'
        'K1STATE MAIN CHECKPOINT:\n'
        'K1D3D-296550-SIXCASES-ONEBUILD-20261103\n'
        'case 0x00289E20u: return sub_00289E20;\n'
        'case 0x0017A0A0u: return sub_0017A0A0;\n'
        'recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n'
        '{\n'
        '    default: return (recomp_func_t)0;\n'
        '}\n'
        '#pragma optimize("", on)\n'
    )
    gen = {va: {"name": "sub_%08X" % va, "source": "void",
                "file": "original.c"} for va in MEMBERS}
    value, frontier, pruned = pack(fixture, gen, set(), FakeBase, None, FakeBC)
    assert not frontier and not pruned
    assert value.count(MARKER) == 1
    assert value.count("case 0x001F7620u: return sub_001F7620;") == 1
    assert value.count("case 0x001F7520u: return sub_001F7520;") == 1
    assert "K1D3D SECOND: native Xenos Reset PASS" in value
    for invalid in (
        fixture.replace("P6DQ ROCKET HARD STOP", "no hard fence"),
        fixture.replace("K1D3D SECOND: native Xenos Reset PASS", "no reset"),
        fixture.replace("recomp_func_t phase4c_lookup_pack_func", "void old_lookup"),
        fixture.replace("K1D3D-296550-SIXCASES-ONEBUILD-20261103", "no D3D"),
        value,
    ):
        try:
            pack(invalid, gen, set(), FakeBase, None, FakeBC)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe previous frame accepted")
    print("[K1-NEXT-PACK] SELFTEST PASS: two real .text entries, six-case/Reset/hard fence, lookup exact; no XDK")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for key in ("base-module", "bb-module", "bc-module", "planner", "functions",
                "generated", "parent", "parent-manifest", "shards",
                "output", "manifest"):
        p.add_argument("--"+key, type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    for key in ("base_module", "bb_module", "bc_module", "planner", "functions",
                "generated", "parent", "parent_manifest", "shards",
                "output", "manifest"):
        if getattr(a, key) is None:
            p.error("Missing --"+key.replace("_", "-"))
    stage(a)


if __name__ == "__main__":
    main()
