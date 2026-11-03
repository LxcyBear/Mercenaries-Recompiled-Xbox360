#!/usr/bin/env python3
"""K1 after hardware six-case graphics run: source-only ICALL_SAFE batch audit.

Hardware witness: ICALL_SAFE target 001F7620, no guest fault, second
Xenos Reset PASS, guest display_calls=0. All source decisions are made
against the user's SHA-verified original retail disasm/generated corpus.
This NEVER modifies any source, XEX, guest ABI, or Original 64 TrueTUs.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import deque
from pathlib import Path

XBE_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGET = 0x001F7620
LAST_TICKS = 58612295
PREVIOUS_TICKS = 58540888
MARK = "K1D3D-296550-SIXCASES-ONEBUILD-20261103"
PARENT_STATUS = "K1_D3D_SIX_CASES_SOURCE_ONLY_NO_XDK"
MAX_NEW = 64
MAX_DEPTH = 3
MAX_VISITED = 768
TEXT_START, TEXT_END = 0x00011000, 0x00255620
ROOTS = (
    (TARGET, "new hardware ICALL_SAFE boundary"),
    (0x001F6D80, "last visible direct-dispatch context"),
    (0x001FA0B0, "last nearby traced translated function"),
    (0x001FB660, "last repeated traced translated function"),
    (0x0023A3CE, "hardware journal router caller, not proven x86 callsite"),
)
MAIN_DEF = re.compile(
    r'(?m)^\s*(?:static\s+)?void\s+(sub_[0-9A-Fa-f]{8})\s*\(\s*void\s*\)\s*\{'
)
PACK_CASE = re.compile(
    r'\bcase\s+0x([0-9A-Fa-f]{8})u\s*:\s*return\s+(sub_[0-9A-Fa-f]{8})\s*;'
)
LABEL = re.compile(r'(?m)^\s*loc_([0-9A-Fa-f]{8})\s*:\s*;')


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def import_module(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise ValueError("Source tool not found: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify(va: int, by_va: dict, generated: dict) -> dict:
    direct = by_va.get(va)
    if direct is not None:
        return {
            "address": "0x%08X" % va,
            "kind": ("exact_source_entry" if va in generated
                     else "exact_entry_without_original_generated_c"),
            "owner": "0x%08X" % va,
            "end_exclusive": "0x%08X" % direct["end"],
            "original_name": direct["name"],
            "source_file": generated.get(va, {}).get("file"),
            "dispatchable_as_plain_original_function": va in generated,
        }
    parents = [row for row in by_va.values()
               if row["start"] < va < row["end"]]
    if len(parents) == 1:
        row = parents[0]
        owner = row["start"]
        original = generated.get(owner, {}).get("source", "")
        labels = {int(h, 16) for h in LABEL.findall(original)}
        return {
            "address": "0x%08X" % va,
            "kind": "interior_label" if va in labels else "interior_missing_label",
            "owner": "0x%08X" % owner,
            "end_exclusive": "0x%08X" % row["end"],
            "original_name": row["name"],
            "source_file": generated.get(owner, {}).get("file"),
            "dispatchable_as_plain_original_function": False,
        }
    return {
        "address": "0x%08X" % va,
        "kind": "inventory_overlap" if parents else "absent_from_original_function_inventory",
        "owner": None, "end_exclusive": None, "original_name": None,
        "source_file": None, "dispatchable_as_plain_original_function": False,
    }


def owner_inventory(main: str, shard_dir: Path) -> tuple[dict[int, list], dict]:
    paths = sorted(shard_dir.glob("translated_???.cpp"))
    if len(paths) != 64 or not (shard_dir / "translated_runtime.h").is_file():
        raise ValueError("Exactly 64 generated TrueTUs and runtime header required")
    ownership: dict[int, list] = {}
    shard_hashes: dict[str, str] = {}
    sources = [("main.cpp", main)]
    for path in paths:
        blob = path.read_bytes()
        shard_hashes[path.name] = sha(blob)
        sources.append((path.name, blob.decode("utf-8", errors="replace")))
    for name, source in sources:
        for match in MAIN_DEF.finditer(source):
            va = int(match.group(1)[4:], 16)
            ownership.setdefault(va, []).append(name)
    pack_lookup = {}
    for word, func in PACK_CASE.findall(main):
        va = int(word, 16)
        if func.lower() != ("sub_%08X" % va).lower():
            raise ValueError("Main packed dispatch lookup mismatches original body: "+word)
        pack_lookup[va] = func
    duplicated = {va: owners for va, owners in ownership.items()
                  if len(owners) != 1}
    if duplicated:
        sample = list(duplicated.items())[:4]
        raise ValueError("Duplicate original translated definitions: "+str(sample))
    return ownership, {
        "parent_64_true_tu_sha256": shard_hashes,
        "main_pack_lookup_vas": set(pack_lookup),
        "compiled_functions_count": len(ownership),
        "compiled_in_64_or_main": set(ownership),
    }


def walk_missing_graph(generated: dict, by_va: dict, base,
                       compiled: set[int]) -> tuple[list[dict], dict]:
    """Walk *through* compiled nodes; count only original missing C bodies."""
    by_name = {r["name"]: va for va, r in generated.items()}
    q = deque([(va, 0, why) for va, why in ROOTS
               if va in generated and va in by_va
               and TEXT_START <= va < TEXT_END])
    seen: set[int] = set()
    missing = []
    visited_compiled = 0
    while q and len(seen) < MAX_VISITED and len(missing) < MAX_NEW:
        va, depth, why = q.popleft()
        if va in seen:
            continue
        seen.add(va)
        row = generated.get(va)
        if row is None or va not in by_va:
            continue
        calls = set(base.CALL_RE.findall(base.mask_noncode(row["source"])))
        deps = sorted({by_name[name] for name in calls
                       if name in by_name and by_name[name] in by_va
                       and TEXT_START <= by_name[name] < TEXT_END
                       and by_name[name] != va})
        if va in compiled:
            visited_compiled += 1
        else:
            missing.append({
                "va": "0x%08X" % va,
                "source_file": row["file"],
                "original_c_sha256": sha(row["source"].encode("utf-8")),
                "depth": depth, "reached_from": why,
                "direct_dependent_original_text_functions":
                    ["0x%08X" % dep for dep in deps],
            })
        if depth < MAX_DEPTH:
            for dep in deps:
                if dep not in seen:
                    q.append((dep, depth+1,
                              "direct callee of 0x%08X" % va))
    return missing, {
        "original_graph_visited": len(seen),
        "original_compiled_nodes_traversed": visited_compiled,
        "remaining_queue": len(q),
        "graph_truncated": bool(q),
        "candidate_cap": MAX_NEW,
        "depth_cap": MAX_DEPTH,
        "missing_original_functions": len(missing),
    }


def summarize_target(by_va: dict, generated: dict, owners: dict,
                     lookup: set[int]) -> dict:
    classification = classify(TARGET, by_va, generated)
    original_va = (int(classification["owner"], 16)
                   if classification["owner"] else None)
    entry = generated.get(original_va, {})
    src = entry.get("source", "")
    lines = src.splitlines()
    parent = owners.get(original_va, []) if original_va is not None else []
    if classification["kind"] == "exact_source_entry":
        if TARGET in lookup:
            gate = "EXACT ORIGINAL ENTRY ALREADY IN PHASE4C LOOKUP; audit guest ABI/route before compiling"
        elif parent:
            gate = "EXACT ORIGINAL BODY COMPILED BUT NOT IN MAIN LOOKUP; source-authentic lookup/ABI bridge, NOT duplicate source body"
        else:
            gate = "EXACT ORIGINAL BODY MISSING IN COMPILED SET; batch original generated C plus bounded clean dependencies"
    elif classification["kind"] == "interior_label":
        gate = "ORIGINAL INTERIOR LABEL: needs label-specific guest state/ABI bridge; do not package as function start"
    elif classification["kind"] == "interior_missing_label":
        gate = "ORIGINAL INTERIOR VA lacks translated label: original instruction recovery required"
    else:
        gate = "NO SAFE DIRECT FUNCTION ENTRY: recover exact original machine-code provenance"
    return {
        "target_classification": classification,
        "target_original_source_file": entry.get("file"),
        "target_original_source_sha256": sha(src.encode("utf-8")) if src else None,
        "compiled_owner_files": parent,
        "main_dispatch_lookup_entry_present": TARGET in lookup,
        "original_source_first_48_lines": lines[:48],
        "original_source_last_42_lines": lines[-42:],
        "gate": gate,
    }


def plan(a) -> None:
    if not a.parent.is_file() or not a.manifest.is_file():
        raise ValueError("Six-case hardware parent source/manifest missing")
    meta = json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    blob = a.parent.read_bytes()
    if (meta.get("status") != PARENT_STATUS or
        meta.get("original_retail_xbe_sha256") != XBE_SHA or
        meta.get("staged_main_sha256") != sha(blob) or
        meta.get("marker") != MARK or
        meta.get("xenos_reset_source_unchanged") is not True or
        meta.get("preserves_unknown_tail_hard_fence") is not True or
        meta.get("original_true_tus") != 64 or
        meta.get("synthetic_guest_pixels") is not False):
        raise ValueError("Hardware-run six-case parent identity/guest safety proof changed")
    cache = a.functions.parent / ".disasm_cache.json"
    if not cache.is_file() or json.loads(
        cache.read_text(encoding="utf-8-sig")
    ).get("xbe_hash", "").upper() != XBE_SHA:
        raise ValueError("Original retail disassembler/XBE hash identity mismatch")
    base = import_module(a.base_module, "k1_next_icall_base")
    by_va, by_name = base.load_ranges(a.functions)
    generated = base.load_generated(a.generated_root, by_name)
    main = blob.decode("utf-8")
    if ("P6DQ ROCKET HARD STOP" not in main or
        "K1D3D SECOND: native Xenos Reset PASS" not in main or
        "K1STATE MAIN CHECKPOINT:" not in main):
        raise ValueError("Expected main graphics/reset/unknown-call fences lost")
    ownership, counts = owner_inventory(main, a.shards)
    for name, expected in meta.get("derived_64_tu_hashes", {}).items():
        if counts["parent_64_true_tu_sha256"].get(name) != expected:
            raise ValueError("Staged six-case TrueTU differs from original tested manifest: "+name)
    target = summarize_target(
        by_va, generated, ownership, counts["main_pack_lookup_vas"])
    seeds = []
    for va, reason in ROOTS:
        c = classify(va, by_va, generated)
        c["reason"] = reason
        c["compiled_in_main_or_64_tus"] = va in counts["compiled_in_64_or_main"]
        c["present_in_main_pack_lookup"] = va in counts["main_pack_lookup_vas"]
        seeds.append(c)
    missing, graph = walk_missing_graph(
        generated, by_va, base, counts["compiled_in_64_or_main"])
    prev = sorted((v for v in by_va if v <= TARGET), reverse=True)[:3]
    nxt = sorted((v for v in by_va if v > TARGET))[:3]
    around = [{
        "direction": "at_or_before" if v <= TARGET else "after",
        "va": "0x%08X" % v, "end_exclusive": "0x%08X" % by_va[v]["end"],
        "name": by_va[v]["name"],
        "source_file": generated.get(v, {}).get("file"),
    } for v in prev+nxt]
    output = {
        "status": "K1_NEXT_ICALL_1F7620_SOURCE_ONLY_NO_XDK",
        "hardware_witness": {
            "kind": "ICALL_SAFE", "target": "0x001F7620",
            "router_caller_not_verified_original_x86_callsite": "0x0023A3CE",
            "saved_esp": "0x008BF838", "fault": 0,
            "ticks": LAST_TICKS, "old_itail_ticks": PREVIOUS_TICKS,
            "net_more_ticks": LAST_TICKS-PREVIOUS_TICKS,
            "native_xenos_reset_hresult": "0x00000000",
            "display_calls": 0, "guest_framebuffer": "0x00000000",
        },
        "parent_main_sha256": sha(blob),
        "retail_disasm_cache_sha256": XBE_SHA,
        "original_true_tu_count": 64,
        "modified_true_tu_count": meta.get("changed_true_tu_count"),
        "existing_compiled_functions": counts["compiled_functions_count"],
        "target": target,
        "nearby_original_function_inventory": around,
        "seeds": seeds,
        "text_graph": graph,
        "bounded_missing_source_candidates": missing,
        "safe_to_build": False,
        "safe_to_insert_unknown_function": False,
        "next_gate": target["gate"],
        "evidence_limits": [
            "Hardware log does not count six-case bridge executions",
            "Original C direct-call graph is not guaranteed live execution",
            "ICALL_SAFE router caller is not an original x86 callsite proof",
            "No first Swap/guest display/pixels yet",
        ],
    }
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_text(json.dumps(output, indent=2)+"\n", encoding="utf-8")
    print("[K1-NEXT] SIX-CASE HARDWARE PARENT + RETAIL DISASM SHA PASS; original 64 TrueTUs untouched")
    print("[K1-NEXT] PREVIOUS ITAIL=0029655D @58540888; NEW ICALL_SAFE=001F7620 @58612295 (+71407 ticks), fault=0")
    c = target["target_classification"]
    print("[K1-NEXT] TARGET %s class=%s original_owner=%s source=%s" %
          (c["address"], c["kind"], c["owner"], c["source_file"]))
    print("[K1-NEXT] COMPILED OWNERS=%s MAIN LOOKUP=%s" %
          (target["compiled_owner_files"], target["main_dispatch_lookup_entry_present"]))
    print("[K1-NEXT] GRAPH visited=%d through_compiled=%d missing=%d truncated=%s" %
          (graph["original_graph_visited"], graph["original_compiled_nodes_traversed"],
           graph["missing_original_functions"], graph["graph_truncated"]))
    for r in missing[:40]:
        print("[K1-NEXT] ORIGINAL C MISSING %s file=%s depth=%u from=%s" %
              (r["va"], r["source_file"], r["depth"], r["reached_from"]))
    print("[K1-NEXT] GATE: "+target["gate"])
    print("[K1-NEXT] NO XDK BUILD. NO XEX CHANGED. NO PIXELS CLAIMED.")
    print("[K1-NEXT] Report: "+str(a.output))


def self_test() -> None:
    inventory = {
        0x001F7600: {"start": 0x001F7600, "end": 0x001F7610,
                     "name": "sub_001F7600"},
        0x001F7620: {"start": 0x001F7620, "end": 0x001F7630,
                     "name": "sub_001F7620"},
    }
    gen = {
        0x001F7620: {"name": "sub_001F7620",
                     "file": "original.c",
                     "source": "void sub_001F7620(void){sub_001F7610();}"},
        0x001F7610: {"name": "sub_001F7610",
                     "file": "original.c",
                     "source": "void sub_001F7610(void){ }"},
    }
    assert classify(TARGET, inventory, gen)["kind"] == "exact_source_entry"
    summary = summarize_target(inventory, gen, {TARGET:["translated_014.cpp"]}, set())
    assert "COMPILED BUT NOT" in summary["gate"]
    assert not summary["main_dispatch_lookup_entry_present"]
    summary2 = summarize_target(inventory, gen, {}, set())
    assert "MISSING IN COMPILED SET" in summary2["gate"]
    assert "ORIGINAL ENTRY" in summarize_target(
        inventory, gen, {}, {TARGET})["gate"]
    interior = classify(0x001F7622, inventory, gen)
    assert interior["kind"] == "interior_missing_label"
    class Base:
        CALL_RE = re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(")
        @staticmethod
        def mask_noncode(text):
            return text
    inv = {TARGET: inventory[TARGET], 0x001F7610: {
        "start": 0x001F7610, "end": 0x001F7620,
        "name": "sub_001F7610",
    }}
    missing, stats = walk_missing_graph(gen, inv, Base, {TARGET})
    assert any(r["va"] == "0x001F7610" for r in missing)
    assert stats["original_compiled_nodes_traversed"] >= 1
    print("[K1-NEXT] SELFTEST PASS: exact/interior, compiled-vs-lookup, traversal through compiled nodes, no XDK")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for n in ("base-module", "functions", "generated-root", "parent",
              "manifest", "shards", "output"):
        p.add_argument("--"+n, type=Path)
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    for n in ("base_module", "functions", "generated_root", "parent",
              "manifest", "shards", "output"):
        if getattr(a, n) is None:
            p.error("Missing --"+n.replace("_", "-"))
    plan(a)


if __name__ == "__main__":
    main()
