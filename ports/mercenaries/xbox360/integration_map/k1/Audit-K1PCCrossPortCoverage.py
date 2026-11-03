#!/usr/bin/env python3
"""Offline retail-aware Mercenaries PC -> Xbox360 function/frontier coverage.

Inputs:
* Verified original Xbox retail XBE disassembly 16k+ function inventory.
* Original translated C corpus (source provenance by retail VA, not PC chunk).
* Actual r4 Xbox360 64 compiled TrueTUs + main lookup (not a guessed list).
* Git-pinned publicly released PC recomp source patch inventory and scripts.

Outputs JSON + CSV: exhaustive VAs, compiled/not-compiled, original
source/direct call graph, candidate frontiers, PC-only patch/host-helper
risks and bounded priority clusters for likely GPU/audio/input startup.

IMPORTANT: Static reachability != PC runtime execution. The PC repository
does not commit generated C, and the Windows D3D11/audio backend cannot
be transplanted to Xbox 360 Xenos. No XDK, no Xbox run, no derived mutation.
"""
from __future__ import annotations

import argparse
import bisect
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter, defaultdict, deque
from pathlib import Path

XBE_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PC_COMMIT = "f513ae4e041401b7b032410016940971488d523b"
FRONTIERS = [
    (0x002228C0, "hardware latest DIRECT_FRONTIER", "text"),
    (0x001F7620, "earlier hardware ICALL_SAFE", "text"),
    (0x001F7520, "original direct callee", "text"),
    (0x00296550, "original six-case graphics switch", "d3d"),
    (0x0028BDB0, "retail D3DDevice_Swap (not witnessed called)", "graphics"),
    (0x0028A530, "retail D3DDevice_PersistDisplay (not witnessed called)", "graphics"),
    (0x0028CAA0, "retail Direct3D_CreateDevice (not proof of guest Swap)", "graphics"),
    (0x002D54AC, "earlier XInputGetState source frontier", "input"),
]
REPORT_STATUS = "K1_PC_XBOX360_GLOBAL_ORIGINAL_FUNCTION_AND_PATCH_AUDIT_NO_XDK"
HOST_CALL = re.compile(r"\b(recomp_[A-Za-z][A-Za-z0-9_]*)\s*\(")
DYNAMIC_SIGNALS = {
    "indirect_tail": re.compile(r"\bRECOMP_ITAIL\s*\("),
    "indirect_call": re.compile(r"\bRECOMP_ICALL(?:_SAFE)?\s*\("),
    "direct_frontier": re.compile(r"\b(?:PHASE[0-9A-Z_]*DIRECT_FRONTIER|RECOMP_DIRECT_FRONTIER)\s*\("),
}
MAX_LIST = 120


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def module(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    if not spec or not spec.loader:
        raise ValueError("Required original source module missing: " + str(path))
    result = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(result)
    return result


def section_owner(va: int, start_list: list[int], by_va: dict) -> int | None:
    pos = bisect.bisect_right(start_list, va)-1
    if pos < 0:
        return None
    root = start_list[pos]
    return root if root <= va < by_va[root]["end"] else None


def build_patch_owners(transformations: list, by_va: dict) -> tuple[dict, dict, list]:
    starts = sorted(by_va)
    owners = defaultdict(list)
    all_host_helpers = defaultdict(list)
    unknown = []
    for entry in transformations:
        parsed = []
        for address in entry.get("guest_sites", []):
            if not re.fullmatch(r"[0-9a-fA-F]{8}", str(address)):
                continue
            va = int(address, 16)
            owner = section_owner(va, starts, by_va)
            parsed.append("0x%08X" % va)
            if owner is None:
                unknown.append({
                    "index": entry.get("index"),
                    "name": entry.get("name"),
                    "site": "0x%08X" % va,
                    "status": "not_inside_original_function_inventory",
                })
                continue
            owners[owner].append({
                "patch_index": entry.get("index"),
                "name": entry.get("name"),
                "site": "0x%08X" % va,
                "host_helpers": entry.get("host_helpers", []),
            })
            for helper in entry.get("host_helpers", []):
                all_host_helpers[helper].append({
                    "original_function": "0x%08X" % owner,
                    "source_patch_index": entry.get("index"),
                    "site": "0x%08X" % va,
                })
    return dict(owners), dict(all_host_helpers), unknown


def direct_graph(generated: dict, base, by_va: dict) -> tuple[dict, dict]:
    name_to_va = {v["name"]: k for k, v in generated.items()}
    forward, reverse = {}, defaultdict(set)
    for va, row in generated.items():
        text = base.mask_noncode(row["source"])
        direct = sorted({
            name_to_va[name]
            for name in base.CALL_RE.findall(text)
            if name in name_to_va and name_to_va[name] != va
            and name_to_va[name] in by_va
        })
        forward[va] = direct
        for callee in direct:
            reverse[callee].add(va)
    return forward, {k: sorted(v) for k, v in reverse.items()}


def distances(roots: list[int], graph: dict, allowed: set,
              limit: int = 20000) -> dict[int, tuple[int, int]]:
    visited = {}
    queue = deque((va, 0, va) for va in roots if va in allowed)
    while queue and len(visited) < limit:
        va, depth, seed = queue.popleft()
        if va in visited:
            continue
        visited[va] = (depth, seed)
        if depth < 12:
            for callee in graph.get(va, ()):
                if callee in allowed and callee not in visited:
                    queue.append((callee, depth + 1, seed))
    return visited


def classify_compiled_without_generated_c(
    compiled: dict[int, list[str]],
    generated: dict,
    by_va: dict,
    lookup: set[int],
    prior_planner,
) -> list[dict]:
    """Retain all actual compiled addresses without claiming source parity.

    A compiled function can be a retail exact entry whose generated C is
    missing, or an interior entry that the Xbox TrueTU deliberately stages.
    Neither is a normal original generated-C function. Classification is
    evidence, NOT permission to add them to pack lookups or drop hard fences.
    """
    extras = sorted(set(compiled) - set(generated))
    result = []
    for va in extras:
        detail = prior_planner.classify(va, by_va, generated)
        owner_hex = detail.get("owner")
        owner = int(owner_hex, 16) if owner_hex else None
        result.append({
            "compiled_address": "0x%08X" % va,
            "classification": detail["kind"],
            "compiled_owners": list(compiled[va]),
            "in_main_pack_lookup": va in lookup,
            "retail_inventory_owner": owner_hex,
            "retail_inventory_owner_generated_C": owner in generated if owner is not None else False,
            "original_function_name": detail.get("original_name"),
            "original_generated_C_file": detail.get("source_file"),
            "source_provenance_status": (
                "exact_retail_entry_no_original_generated_C"
                if detail["kind"] == "exact_entry_without_original_generated_c"
                else "interior_entry_not_standalone_function"
                if detail["kind"] in ("interior_label", "interior_missing_label")
                else "outside_or_overlapping_original_inventory"
            ),
            "safe_to_treat_as_normal_original_generated_C": False,
            "safe_to_add_new_dispatch_case": False,
            "required_followup": (
                "Prove original XBE instruction/ABI/translation purpose; "
                "inspect actual compiled owner and dispatch routing. "
                "Do not add a duplicate or make a guessed fallback."
            ),
        })
    return result


def scan_pc_generated(optional_dir: Path | None, compiled: dict, base) -> dict:
    if optional_dir is None or not optional_dir.exists():
        return {
            "available": False,
            "warning": (
                "Public PC repo does not commit recomp/gen generated C. "
                "PC runtime and source patch inventory are references; "
                "generated body parity requires a local PC translated corpus."
            ),
        }
    roots = sorted(optional_dir.rglob("recomp_[0-9][0-9][0-9][0-9].c"))
    if not roots:
        return {
            "available": False,
            "warning": "Optional PC-generated directory has no recomp_XXXX.c files",
        }
    pc_generated = base.load_generated(optional_dir, None)
    # The installed original Xbox C generator expects by_name metadata;
    # use the explicit original inventory in analyze() instead of comparing
    # raw PC chunk numbers or claiming ABI equivalence here.
    return {"available": True, "pc_chunks": len(roots),
            "pc_source_function_count": len(pc_generated),
            "comparison_status": "structural address availability only"}


def analyze(a) -> None:
    pc_helper = module(a.pc_retail_module, "k1_pc_cross_port_ret_helper")
    pc_sha = pc_helper.verify_pc_commit(a.pc_reference)
    before, after, exact_patch = pc_helper.read_templates(a.pc_reference)
    if pc_sha != PC_COMMIT or (exact_patch["name"] != pc_helper.PATCH_NAME or
        before.count("CMP_NE(MEM32(ecx + 0x48), 3)") != 1 or
        after.count(pc_helper.HELPER + "()") != 1):
        raise ValueError("Pinned PC original-retail/developer patch evidence changed")
    pc_inventory = json.loads((a.pc_reference / pc_helper.PC_INVENTORY)
                             .read_text(encoding="utf-8"))
    if pc_inventory.get("retail_xbe_sha256", "").upper() != XBE_SHA:
        raise ValueError("PC patch inventory retail XBE SHA mismatch")

    parent_meta = json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    parent_bytes = a.parent.read_bytes()
    paths = sorted(a.shards.glob("translated_???.cpp"))
    if len(paths) != 64 or not (a.shards/"translated_runtime.h").is_file():
        raise ValueError("Exactly 64 original translated TrueTUs expected")
    hashes = {p.name: sha(p.read_bytes()) for p in paths}
    sources = {p.name: p.read_text(encoding="utf-8", errors="replace")
               for p in paths}
    post = module(a.post_planner, "k1_pc_cross_port_prior_parent")
    parent_proof = post.validate_parent(
        parent_meta, parent_bytes, hashes, sources)
    previous = module(a.previous_planner, "k1_pc_cross_port_inventory")
    compiled, compiled_stats = previous.owner_inventory(
        parent_bytes.decode("utf-8"), a.shards)
    compiled_vas = set(compiled)
    in_lookup = compiled_stats["main_pack_lookup_vas"]
    base = module(a.base_module, "k1_pc_cross_port_xbox_base")
    by_va, by_name = base.load_ranges(a.functions)
    generated = base.load_generated(a.generated, by_name)
    cache_file = a.functions.parent/".disasm_cache.json"
    if not cache_file.is_file() or json.loads(
        cache_file.read_text(encoding="utf-8-sig")
    ).get("xbe_hash", "").upper() != XBE_SHA:
        raise ValueError("Original Xbox retail disassembler SHA mismatch")
    valid_source = set(generated)
    original_inv = set(by_va)
    # The runtime can intentionally compile noncanonical/interior bridge
    # functions. Report those separately instead of aborting the complete
    # coverage census or falsely marking them retail source functions.
    unusual_compiled = classify_compiled_without_generated_c(
        compiled, generated, by_va, in_lookup, previous)
    compiled_original = compiled_vas & valid_source
    patches, host_helper_sites, unowned = build_patch_owners(
        pc_inventory.get("transformations", []), by_va)
    graph, callers = direct_graph(generated, base, by_va)
    walked = distances([va for va, _, _ in FRONTIERS], graph, valid_source)
    known_critical = {va for va, _, _ in FRONTIERS}
    missing_exact_source = valid_source - compiled_vas
    source_missing_from_translator = original_inv - valid_source
    data = []
    risk = []
    all_indirect = Counter()
    pc_only_function_count = 0
    missing_with_pc_patch = 0
    for va in sorted(by_va):
        row = generated.get(va)
        src = row["source"] if row else ""
        src_code = base.mask_noncode(src) if row else ""
        embedded_host = sorted(set(HOST_CALL.findall(src_code)))
        patch_rows = patches.get(va, [])
        expected_from_patch = sorted({h for p in patch_rows
                                      for h in p["host_helpers"]})
        pc_only = sorted(set(embedded_host) & set(host_helper_sites))
        if pc_only:
            pc_only_function_count += 1
        is_source_missing = va in missing_exact_source
        if is_source_missing and patch_rows:
            missing_with_pc_patch += 1
        ind = {name: len(sig.findall(src_code)) for name, sig
               in DYNAMIC_SIGNALS.items()} if row else {}
        all_indirect.update(ind)
        dep_misses = [v for v in graph.get(va, []) if v in missing_exact_source]
        depth, seed = walked.get(va, (None, None))
        risk_weight = (
            10000 if va == 0x002228C0 else
            8000 if va in known_critical else
            max(0, 3000 - depth * 350) if depth is not None else 0
        )
        risk_weight += 100 if pc_only else 0
        risk_weight += 50 if patch_rows else 0
        risk_weight += 25 if sum(ind.values()) else 0
        status = ("no_original_generated_C" if row is None else
                  "compiled" if va in compiled_vas else
                  "missing_original_C_body_from_xbox")
        item = {
            "va": "0x%08X" % va,
            "end_exclusive": "0x%08X" % by_va[va]["end"],
            "source_file": row["file"] if row else "",
            "source_status": status,
            "compiled_owners": "|".join(compiled.get(va, [])),
            "in_main_pack_lookup": int(va in in_lookup),
            "original_direct_callees": len(graph.get(va, [])),
            "original_direct_callers": len(callers.get(va, [])),
            "direct_missing_original_callees": len(dep_misses),
            "original_call_graph_depth_from_seed": depth if depth is not None else "",
            "nearest_seed": "0x%08X" % seed if seed is not None else "",
            "PC_patch_sites_inside_function": len(patch_rows),
            "PC_patch_indexes": "|".join(str(p["patch_index"]) for p in patch_rows),
            "PC_patch_host_helper_mentions": "|".join(expected_from_patch),
            "PC_port_specific_helpers_in_source": "|".join(pc_only),
            "indirect_tail_sites": ind.get("indirect_tail", 0),
            "indirect_call_sites": ind.get("indirect_call", 0),
            "direct_frontier_sites": ind.get("direct_frontier", 0),
            "hardware_observed_seed": int(va in known_critical),
            "static_risk_priority": risk_weight,
        }
        data.append(item)
        if is_source_missing or (pc_only and (va in known_critical or depth is not None)):
            risk.append({
                **item, "original_direct_missing_children":
                    ["0x%08X" % v for v in dep_misses],
                "patch_names": [p["name"] for p in patch_rows],
                "PC_executable_patch_active_in_local_generated_source":
                    bool(pc_only),
                "next_action": (
                    "Original-XBE ABI & PC patch evidence check BEFORE source staging"
                    if pc_only else
                    "Original C support/ABI closure and routing audit"
                ),
            })
    risk.sort(key=lambda x: (
        -x["static_risk_priority"],
        x["source_status"] != "missing_original_C_body_from_xbox",
        x["va"],
    ))
    a.outdir.mkdir(parents=True, exist_ok=True)
    csv_path = a.outdir / "original-retail-va-coverage.csv"
    risks_path = a.outdir / "missing-and-pc-patch-risks.csv"
    outlier_path = a.outdir / "compiled-addresses-without-generated-retail-c.csv"
    with csv_path.open("w", encoding="utf-8", newline="") as file:
        writer = csv.DictWriter(file, fieldnames=list(data[0]))
        writer.writeheader()
        writer.writerows(data)
    with risks_path.open("w", encoding="utf-8", newline="") as file:
        columns = list(risk[0]) if risk else list(data[0])+["next_action"]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        writer.writerows(risk)
    # The seven (or any future) noncanonical compiled owners must never
    # disappear from the audit simply because the PC generated C lacks them.
    with outlier_path.open("w", encoding="utf-8", newline="") as file:
        columns = [
            "compiled_address", "classification", "compiled_owners",
            "in_main_pack_lookup", "retail_inventory_owner",
            "retail_inventory_owner_generated_C", "original_function_name",
            "original_generated_C_file", "source_provenance_status",
            "safe_to_treat_as_normal_original_generated_C",
            "safe_to_add_new_dispatch_case", "required_followup",
        ]
        writer = csv.DictWriter(file, fieldnames=columns)
        writer.writeheader()
        for item in unusual_compiled:
            writer.writerow({**item, "compiled_owners":
                             "|".join(item["compiled_owners"])})
    summary = {
        "status": REPORT_STATUS,
        "provenance": {
            "pc_repo": "https://github.com/KraftMacAndChee/Mercenaries-Recompiled",
            "pc_exact_commit_sha": pc_sha,
            "pc_patch_inventory_sha256": sha(
                (a.pc_reference / pc_helper.PC_INVENTORY).read_bytes()),
            "pc_patch_script_sha256": sha(
                (a.pc_reference / pc_helper.PC_PATCH_SCRIPT).read_bytes()),
            "original_retail_xbe_sha256": XBE_SHA,
            "xb360_parent_r4_main_sha256": sha(parent_bytes),
            "verified_native_six_case_owner": parent_proof["six_case_owner"],
            "verified_native_common_tail_owner": parent_proof["six_case_common_owner"],
            "verified_original_64_true_tu_hashes": hashes,
        },
        "coverage": {
            "retail_original_x86_inventory": len(original_inv),
            "original_generated_C_functions": len(valid_source),
            "compiled_original_functions_in_r4": len(compiled_original),
            "compiled_total_function_addresses_in_r4": len(compiled_vas),
            "compiled_without_original_generated_C_entries": len(unusual_compiled),
            "compiled_without_generated_C_by_classification": dict(
                Counter(item["classification"] for item in unusual_compiled)),
            "compiled_exact_original_entries_in_main_lookup": len(in_lookup),
            "original_generated_C_missing_from_r4_binary": len(missing_exact_source),
            "original_x86_functions_without_translated_C": len(source_missing_from_translator),
            "original_generated_C_compiled_percent": round(
                100 * len(compiled_original) / max(1, len(valid_source)), 2),
            "total_direct_original_C_edges": sum(map(len, graph.values())),
            "original_generated_C_dynamic_site_census": dict(all_indirect),
            "pc_reference_patch_inventory_transformations":
                len(pc_inventory.get("transformations", [])),
            "pc_function_sites_with_patch_inventory_entries": len(patches),
            "patch_inventory_sites_without_original_owner": len(unowned),
            "pc_host_helpers_with_patch_inventory_entries": len(host_helper_sites),
            "functions_in_local_generated_C_using_PC_patch_helpers":
                pc_only_function_count,
            "missing_xbox_original_functions_with_PC_patch_site_mentions":
                missing_with_pc_patch,
            "static_call_graph_reachable_from_known_seeds": len(walked),
            "source_generated_C_without_full_original_inventory": sorted(
                "0x%08X" % x for x in valid_source-original_inv)[:30],
        },
        "hardware_and_structural_priority_seeds": [
            {
                "address": "0x%08X" % va,
                "why": why,
                "classification": kind,
                "exists_in_generated_original_C": va in valid_source,
                "already_compiled": va in compiled_vas,
                "in_pack_lookup": va in in_lookup,
                "retail_owner_function": (
                    "0x%08X" % section_owner(va, sorted(by_va), by_va)
                    if section_owner(va, sorted(by_va), by_va) is not None else None),
            }
            for va, why, kind in FRONTIERS
        ],
        "critical_pc_only_patch_278": {
            "affected_original_va": "0x002228C0",
            "changed_guest_site": "0x002228F0",
            "PC_developer_hook": pc_helper.HELPER,
            "pc_patch_index": exact_patch["index"],
            "pc_original_retail_before_template_sha256": pc_helper.digest(before),
            "pc_modified_after_template_sha256": pc_helper.digest(after),
            "required_correct_action": (
                "Restore original CMP/JNE after validating original retail XBE "
                "bytes; NEVER create a return-false PC helper stub."
            ),
        },
        "compiled_noncanonical_source_entries_require_separate_abi_proof": unusual_compiled,
        "top_missing_and_pc_patch_risks": risk[:MAX_LIST],
        "patch_sites_unowned_sample": unowned[:30],
        "limitations": [
            "PC project does NOT commit generated recomp C: clone alone is not a full live-PC call trace.",
            "Source graph is statically derived direct-call reachability, not hardware execution order.",
            "Original XBE indirect calls/jumps can have dynamic targets absent from the static graph.",
            "PC D3D11 and audio backend cannot be copied directly into native Xbox 360 D3D/XAudio/XDK.",
            "PC patch inventory includes many optional port improvements; a patch site is not proof it executed.",
            "Current PC preview log reports renderer/audio milestones, not function-VAs or guest call ordering.",
            "Compiled body existence alone does not prove direct/indirect guest dispatch ABI correctness.",
            "Compiled addresses without standalone generated retail C are a separate evidence class: neither a real coverage gain nor automatically faulty.",
            "An original entry with no generated C cannot be silently treated as translated retail source.",
        ],
        "safe_to_build_from_report_alone": False,
        "xdk_invoked": False,
        "any_xex_modified": False,
        "coverage_csv": str(csv_path),
        "risks_csv": str(risks_path),
        "noncanonical_compiled_csv": str(outlier_path),
    }
    json_path = a.outdir / "pc-to-xbox360-retail-coverage.json"
    json_path.write_text(json.dumps(summary, indent=2)+"\n", encoding="utf-8")
    c=summary["coverage"]
    print("[K1-PC-AUDIT] PINNED PC SOURCE %s + ORIGINAL RETAIL SHA VERIFIED" % pc_sha[:12])
    print("[K1-PC-AUDIT] Original x86=%s translated source=%s compiled XB360=%s missing=%s (%.2f%% compiled)" %
          (c["retail_original_x86_inventory"],
           c["original_generated_C_functions"],
           c["compiled_original_functions_in_r4"],
           c["original_generated_C_missing_from_r4_binary"],
           c["original_generated_C_compiled_percent"]))
    print("[K1-PC-AUDIT] PC known patch inventory=%s, sites-with-owners=%s, PC helper functions in Xbox source=%s" %
          (c["pc_reference_patch_inventory_transformations"],
           c["pc_function_sites_with_patch_inventory_entries"],
           c["functions_in_local_generated_C_using_PC_patch_helpers"]))
    print("[K1-PC-AUDIT] COMPILED ADDRESS EXCEPTIONS=%d, NOT counted as generated retail C coverage" %
          len(unusual_compiled))
    for item in unusual_compiled:
        print("[K1-PC-AUDIT] NONCANONICAL compiled=%s kind=%s retail_owner=%s true_tu=%s lookup=%s (ABI UNPROVEN)" %
              (item["compiled_address"], item["classification"],
               item["retail_inventory_owner"],
               "|".join(item["compiled_owners"]),
               item["in_main_pack_lookup"]))
    print("[K1-PC-AUDIT] Direct guest-call edges=%s, static seed reachable=%s" %
          (c["total_direct_original_C_edges"],
           c["static_call_graph_reachable_from_known_seeds"]))
    for entry in risk[:20]:
        print("[K1-PC-AUDIT] RISK va=%s %s priority=%d depth=%s pc_helpers=%s missing_callees=%d" %
              (entry["va"], entry["source_status"],
               entry["static_risk_priority"],
               entry["original_call_graph_depth_from_seed"],
               entry["PC_port_specific_helpers_in_source"],
               entry["direct_missing_original_callees"]))
    print("[K1-PC-AUDIT] IMPORTANT: PC preview log is graphics/audio telemetry, NOT guest function trace")
    print("[K1-PC-AUDIT] NO XDK, NO XEX, no speculative imports or dummy pixels")
    print("[K1-PC-AUDIT] Full coverage CSV: "+str(csv_path))
    print("[K1-PC-AUDIT] Risk CSV: "+str(risks_path))
    print("[K1-PC-AUDIT] Noncanonical original source exceptions CSV: "+str(outlier_path))
    print("[K1-PC-AUDIT] JSON: "+str(json_path))


def selftest() -> None:
    inventory = {
        0x1000: {"start": 0x1000, "end": 0x1100},
        0x1200: {"start": 0x1200, "end": 0x1240},
        0x1280: {"start": 0x1280, "end": 0x12C0},
    }
    starts = sorted(inventory)
    assert section_owner(0x1000, starts, inventory) == 0x1000
    assert section_owner(0x10FF, starts, inventory) == 0x1000
    assert section_owner(0x1100, starts, inventory) is None
    assert section_owner(0x1200, starts, inventory) == 0x1200
    assert section_owner(0x1250, starts, inventory) is None
    assert section_owner(0x1280, starts, inventory) == 0x1280
    patches, host, misses = build_patch_owners([
        {"index": 1, "name": "pc feature", "guest_sites": ["00001012", "00001110"],
         "host_helpers": ["recomp_test_developer_only"]},
    ], inventory)
    assert len(patches[0x1000]) == 1 and len(misses) == 1
    assert host["recomp_test_developer_only"][0]["original_function"] == "0x00001000"
    class FixturePlanner:
        @staticmethod
        def classify(va, by_va, generated):
            if va in by_va:
                return {
                    "kind": "exact_entry_without_original_generated_c"
                            if va not in generated else "exact_source_entry",
                    "owner": "0x%08X" % va,
                    "original_name": "sub_%08X" % va,
                    "source_file": generated.get(va, {}).get("file"),
                }
            owner = section_owner(va, sorted(by_va), by_va)
            return {
                "kind": "interior_label" if owner is not None else
                        "absent_from_original_function_inventory",
                "owner": "0x%08X" % owner if owner is not None else None,
                "original_name": ("sub_%08X" % owner if owner is not None else None),
                "source_file": generated.get(owner, {}).get("file"),
            }
    synthetic_owners = {
        0x1000: ["translated_014.cpp"],
        0x1080: ["translated_025.cpp"],
        0x1200: ["translated_005.cpp"],
        0x2000: ["main.cpp"],
    }
    classification = classify_compiled_without_generated_c(
        synthetic_owners, {
            0x1000: {"file": "recomp_0010.c"},
        }, inventory, {0x1000}, FixturePlanner)
    assert len(classification) == 3
    assert {item["classification"] for item in classification} == {
        "interior_label", "exact_entry_without_original_generated_c",
        "absent_from_original_function_inventory"}
    assert all(item["safe_to_add_new_dispatch_case"] is False and
               item["safe_to_treat_as_normal_original_generated_C"] is False
               for item in classification)
    assert {0x1000} == set(synthetic_owners) & {0x1000}
    walk = distances([0x1000], {0x1000: [0x1200],
                                  0x1200: [0x1280],
                                  0x1280: [0x1000]},
                     set(inventory))
    assert walk[0x1280] == (2, 0x1000) and len(walk) == 3
    print("[K1-PC-AUDIT] SELFTEST PASS: exact retail ownership, noncanonical compiled exact/interior/outside classes, separate coverage, patch risk, graph, no XDK")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    for param in ("pc-reference", "pc-retail-module", "base-module", "post-planner",
                  "previous-planner", "functions", "generated", "parent",
                  "parent-manifest", "shards", "outdir"):
        p.add_argument("--"+param, type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    for key in ("pc_reference", "pc_retail_module", "base_module", "post_planner",
                "previous_planner", "functions", "generated", "parent",
                "parent_manifest", "shards", "outdir"):
        if getattr(a, key) is None:
            p.error("Missing --"+key.replace("_", "-"))
    analyze(a)


if __name__ == "__main__":
    main()
