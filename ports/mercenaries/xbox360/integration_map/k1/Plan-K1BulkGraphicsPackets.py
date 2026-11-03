#!/usr/bin/env python3
"""Plan a bounded whole-class graphics/audio packet from the retail coverage map.

Read-only, no XDK, no XEX, no source modifications. All candidates are
verified original Xbox-generated C and missing from the real 64 TrueTUs.
A support-clean packet is NOT automatically hardware-ABI-proven: never
turn this report into an unguarded build. The packer must recheck each
member against the new parent after r5 hardware validation.
"""
from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.util
import json
import re
from collections import Counter, deque
from pathlib import Path

XBE_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
EXPECTED_PC_SHA = "f513ae4e041401b7b032410016940971488d523b"
STATUS = "K1_GLOBAL_MISSING_ORIGINAL_SOURCE_BATCH_PACKETS_NO_XDK"
ROOTS = (
    (0x00290610, "render related original function; unproven hardware reachability"),
    (0x00290670, "render related original function; unproven hardware reachability"),
    (0x00288F80, "vertex shader source; PC-only hook suspected"),
    (0x0028BDB0, "retail D3D swap known, guest execution unproven"),
    (0x0028A530, "retail PersistDisplay known, guest execution unproven"),
    (0x002228C0, "previous hardware DIRECT frontier, r5 patch pending"),
    (0x001F7620, "hardware original text ICALL_SAFE"),
    (0x001787C0, "audio pool allocation hardware warning"),
)
MAX_NEW = 24
MAX_CLOSURE = 32
MAX_DEPTH = 6
ABI_HAZARD = re.compile(
    r"\b(?:RECOMP_ITAIL|RECOMP_ICALL|RECOMP_ICALL_SAFE|RECOMP_JUMP)\s*\("
)


def load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    if not spec or not spec.loader:
        raise ValueError("Original maintained source module unavailable "+str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def sha(blob: bytes) -> str:
    return hashlib.sha256(blob).hexdigest()


def closure(
    root: int,
    edges: dict[int, list[int]],
    missing: set[int],
    cap: int = MAX_CLOSURE,
) -> tuple[list[int], str]:
    if root not in missing:
        return [], "already_compiled_or_not_original_generated_C"
    seen = set()
    queue = deque([(root, 0)])
    while queue:
        va, depth = queue.popleft()
        if va in seen:
            continue
        if va not in missing:
            continue
        seen.add(va)
        if len(seen) > cap:
            return sorted(seen), "original_direct_dependency_closure_exceeds_%d" % cap
        for dep in edges.get(va, []):
            if dep in missing:
                if depth >= MAX_DEPTH:
                    return sorted(seen), "missing_original_callee_beyond_depth_%d" % MAX_DEPTH
                queue.append((dep, depth + 1))
    return sorted(seen), "closed"


def classify_packet(
    packet: list[int],
    generated: dict,
    compiled: set[int],
    base,
    bb,
    support: set[str],
) -> tuple[bool, dict]:
    allowed = compiled | set(packet)
    names = {generated[va]["name"] for va in packet}
    unsupported = {}
    risks = {}
    frontier = set()
    for va in packet:
        row = generated[va]
        src = row["source"]
        if ABI_HAZARD.search(base.mask_noncode(src)):
            risks["0x%08X" % va] = (
                "original_indirect_call_or_tail_unverified; requires ABI/target proof")
        rendered = base.localize_and_instrument(src, row["name"])
        rendered, exits = bb.rewrite_direct_frontier(
            base, rendered, generated, allowed)
        frontier.update(exits)
        local = support | names | set(base.DEFINE_RE.findall(rendered))
        calls = set(base.CALL_RE.findall(base.mask_noncode(rendered)))
        unknown = sorted(call for call in calls
                         if call not in local and call not in base.STANDARD_CALLS)
        if unknown:
            unsupported["0x%08X" % va] = unknown
    leftover = sorted(frontier & (set(generated)-allowed))
    if leftover:
        risks["missing_original_callees_fenced_outside_packet"] = [
            "0x%08X" % va for va in leftover]
    detail = {
        "members": ["0x%08X" % va for va in packet],
        "member_count": len(packet),
        "original_generated_c_sha256": {
            "0x%08X" % va: sha(generated[va]["source"].encode("utf-8"))
            for va in packet
        },
        "unresolved_support_symbols": unsupported,
        "direct_original_frontiers": [
            "0x%08X" % va for va in sorted(frontier)],
        "unproven_indirect_abi_or_missing_dependency": risks,
        "source_clean_eligible": not unsupported and not risks,
        "compile_and_hardware_verified": False,
    }
    return detail["source_clean_eligible"], detail


def plan(args):
    pc = load(args.pc_retail_module, "k1_bulk_original_pc")
    if pc.verify_pc_commit(args.pc_reference) != EXPECTED_PC_SHA:
        raise ValueError("PC source SHA pinned reference changed")
    audit = json.loads(args.coverage.read_text(encoding="utf-8-sig"))
    if (audit.get("status") !=
        "K1_PC_XBOX360_GLOBAL_ORIGINAL_FUNCTION_AND_PATCH_AUDIT_NO_XDK" or
        audit.get("safe_to_build_from_report_alone") is not False or
        audit.get("provenance",{}).get("pc_exact_commit_sha") != EXPECTED_PC_SHA):
        raise ValueError("Global original source map lacks required provenance")
    manifest = json.loads(args.manifest.read_text(encoding="utf-8-sig"))
    if (manifest.get("original_retail_xbe_sha256") != XBE_SHA or
        manifest.get("new_main_sha256") != sha(args.main.read_bytes()) or
        manifest.get("original_true_tus") != 64 or
        manifest.get("original_true_tus_reused_not_modified") is not True):
        raise ValueError("64 TrueTU original source hardware parent changed")
    paths = sorted(args.shards.glob("translated_???.cpp"))
    if len(paths) != 64:
        raise ValueError("Missing original TrueTU set")
    for shard in paths:
        if (sha(shard.read_bytes()) !=
                manifest.get("original_64_true_tu_sha256", {}).get(shard.name)):
            raise ValueError("Original compiled TrueTU changed: "+shard.name)
    previous = load(args.previous, "k1_bulk_original_owners")
    base = load(args.base, "k1_bulk_original_base")
    bb = load(args.bb, "k1_bulk_original_bb")
    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated, by_name)
    owners, info = previous.owner_inventory(
        args.main.read_text(encoding="utf-8",errors="replace"), args.shards)
    compiled = info["compiled_in_64_or_main"]
    missing = set(generated)-compiled
    if len(missing) != audit["coverage"]["original_generated_C_missing_from_r4_binary"]:
        raise ValueError("404-count snapshot does not match original source parent inventory")
    if not missing or 0x002228C0 not in missing:
        raise ValueError("Expected known original hardware r4 missing root absent")
    supports = set(base.support_symbols(
        args.main.read_text(encoding="utf-8",errors="replace")))
    supports.update(base.support_symbols(
        (args.shards/"translated_runtime.h").read_text(
            encoding="utf-8", errors="replace")))
    supports.update("sub_%08X" % va for va in compiled)
    graph = {}
    name_to_va = {row["name"]: va for va,row in generated.items()}
    for va,row in generated.items():
        calls = base.CALL_RE.findall(base.mask_noncode(row["source"]))
        graph[va] = sorted({name_to_va[name] for name in calls
                            if name in name_to_va and name_to_va[name] != va})
    # Use map's whole original function risk census, but NEVER conflate
    # PC patch mentions with proof that a guest instruction was executed.
    priorities = {}
    evidence_reachable = set()
    for_row_critical = {va for va,_ in ROOTS}
    with args.map_csv.open("r", encoding="utf-8-sig", newline="") as f:
        for row in csv.DictReader(f):
            va=int(row["va"],16)
            priorities[va] = int(row.get("static_risk_priority") or 0)
            # Only stage source actually linked to a known graphics/audio/
            # hardware frontier. Cold missing game logic is NOT evidence
            # that it should be inserted just to inflate tick counts.
            depth=row.get("original_call_graph_depth_from_seed", "").strip()
            if (depth or va in for_row_critical):
                evidence_reachable.add(va)
    for va,_ in ROOTS:
        priorities[va] = max(priorities.get(va,0), 10000 if va==0x002228C0 else 8000)
    candidate_roots = sorted(missing & evidence_reachable,
                             key=lambda va:(-priorities.get(va,0),va))
    selected = []
    reservations = set()
    blocked=[]
    shortlisted=[]
    for root in candidate_roots:
        packet, why=closure(root,graph,missing)
        if why!="closed":
            blocked.append({"seed":"0x%08X"%root,"status":why,
                            "candidate_count":len(packet)})
            continue
        if not packet or set(packet)&reservations:
            continue
        eligible,detail=classify_packet(
            packet, generated, compiled, base, bb, supports)
        detail["seed"] = "0x%08X" % root
        detail["source_graph_depth_cap"] = MAX_DEPTH
        detail["static_priority_score"] = priorities.get(root,0)
        if not eligible:
            blocked.append({
                "seed": detail["seed"],
                "status":"requires_real_source_support_or_indirect_ABI_proof",
                "unresolved_support_symbols":detail["unresolved_support_symbols"],
                "risks":detail["unproven_indirect_abi_or_missing_dependency"],
            })
            continue
        shortlisted.append(detail)
        if len(selected)+len(packet) <= MAX_NEW:
            for va in packet:
                if va not in reservations:
                    selected.append(va)
            reservations.update(packet)
    selected.sort()
    total = len(missing)
    result = {
        "status": STATUS,
        "original_retail_xbe_sha256": XBE_SHA,
        "pinned_pc_commit": EXPECTED_PC_SHA,
        "original_r4_parent_main_sha256": sha(args.main.read_bytes()),
        "compiled_64_true_tus_reused": 64,
        "missing_original_functions": total,
        "graph_seed_reachable_missing_candidates": len(missing & evidence_reachable),
        "cold_original_missing_excluded_from_batch": len(missing - evidence_reachable),
        "bounded_source_clean_packet_candidates": shortlisted[:128],
        "source_clean_eligible_members_selected": [
            "0x%08X" % va for va in selected],
        "source_clean_eligible_count": len(selected),
        "source_only_max_new": MAX_NEW,
        "blocked_seeds": blocked[:180],
        "blocked_total": len(blocked),
        "still_missing_after_selected_if_built": total-len(selected),
        "safe_to_build_without_xdk_compiler_and_original_xbe_abi_checks": False,
        "safe_to_deploy_unverified_xex": False,
        "xdk_invoked": False,
        "original_64_true_tus_modified": False,
        "source_only": True,
        "note": (
            "This only tests bounded original direct-call source closure and "
            "known symbols in the r4 source snapshot. The r5 actual build "
            "and Xbox hardware result must be validated before a new r6 "
            "source stage. No tick gains or pixels claimed."
        ),
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("[K1-BULK] RETAIL ORIGINAL/PC SOURCE SHA PASS; source-only")
    print("[K1-BULK] original missing=%d, seed-reachable candidates=%d, cold omitted=%d, source-clean selected=%d, blocked=%d" %
          (total,len(missing & evidence_reachable),
           len(missing - evidence_reachable),len(selected),len(blocked)))
    for item in shortlisted[:15]:
        print("[K1-BULK] ELIGIBLE seed=%s count=%d direct_frontiers=%s" %
              (item["seed"],item["member_count"],len(item["direct_original_frontiers"])))
    for item in blocked[:18]:
        print("[K1-BULK] BLOCKED seed=%s reason=%s" %
              (item["seed"],item["status"]))
        for k,v in list(item.get("unresolved_support_symbols",{}).items())[:4]:
            print("[K1-BULK]   %s unknown_symbols=%s" % (k,",".join(v)))
    print("[K1-BULK] NO XDK, NO XEX, NO GUEST PIXELS CLAIMED.")
    print("[K1-BULK] Plan: "+str(args.output))


def self_test():
    edges={0x1000:[0x1020],0x1020:[0x1030],0x1030:[0x2000]}
    missing={0x1000,0x1020,0x1030}
    items,why=closure(0x1000,edges,missing)
    assert why=="closed" and items==[0x1000,0x1020,0x1030]
    many,why=closure(0x1000,edges,missing,cap=2)
    assert "exceeds" in why and len(many)==3
    no,why=closure(0x2000,edges,missing)
    assert no==[] and why=="already_compiled_or_not_original_generated_C"
    print("[K1-BULK] SELFTEST PASS: bounded closed original C dependency packet, cap and guard; no XDK")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for k in ("pc-retail-module","pc-reference","coverage","main","manifest",
              "shards","previous","base","bb","functions","generated",
              "map-csv","output"):
        p.add_argument("--"+k,type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test()
        return
    for attr in ("pc_retail_module","pc_reference","coverage","main",
                 "manifest","shards","previous","base","bb","functions",
                 "generated","map_csv","output"):
        if getattr(a,attr) is None:
            p.error("Missing --"+attr.replace("_","-"))
    plan(a)


if __name__=="__main__":
    main()
