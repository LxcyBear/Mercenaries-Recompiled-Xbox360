#!/usr/bin/env python3
"""Offline source-authentic K1 D3D predictive batch / ITAIL provenance audit.

NO XDK, no Xbox, no modification of original translated sources. Classify
hardware ITAIL 0x0029655D against the exact retail XBE function inventory
BEFORE attempting to promote a target. Plan one bounded D3D/XGRPH graph
for a later safe, ABI-proven integration/build (not one build per VA).
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
ITAIL = 0x0029655D
# All addresses in these lists are *observations*, not asserted function starts.
# 'VA[]' entries are execution/proximity context and may lie inside functions.
SEEDS = (
    (ITAIL, "hardware ITAIL boundary; mandatory exact control-flow proof"),
    (0x002965F0, "latest AV/display DIRECT context, not necessarily a function start"),
    (0x00296614, "recent D3D VA context"),
    (0x0029663F, "recent D3D VA context"),
    (0x00296670, "recent D3D VA context"),
    (0x002966A0, "recent D3D VA context"),
    (0x002966F8, "recent D3D VA context"),
    (0x00296550, "nearby D3D context; possible interior-owner entry"),
    (0x0028E1C0, "latest AV/display ICALL context"),
    (0x0028BDB0, "original D3DDevice_Swap identified by retail function scan"),
    (0x0028A530, "original D3DDevice_PersistDisplay identified by retail function scan"),
    (0x00294060, "recent D3D VA context"),
    (0x00292AA0, "recent D3D VA context"),
    (0x00290600, "recent D3D VA context"),
)
D3D_START, D3D_END = 0x00288640, 0x0029B874
XGRPH_START, XGRPH_END = 0x0029B880, 0x0029CB7C
MAX_CANDIDATES = 96
MAX_DIRECT_DEPTH = 4
TRUE_TU_DEF = re.compile(
    r'(?m)^\s*(?:static\s+)?void\s+(sub_[0-9A-Fa-f]{8})\s*\(\s*void\s*\)\s*\{'
)
PACK_CASE = re.compile(
    r'\bcase\s+0x([0-9A-Fa-f]{8})u\s*:\s*return\s+(sub_[0-9A-Fa-f]{8})\s*;'
)
LABEL = re.compile(r'(?m)^\s*loc_([0-9A-Fa-f]{8})\s*:\s*;')
ITAIL_CALL = re.compile(r'\bRECOMP_ITAIL\s*\(')


def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def is_graphics(va: int) -> bool:
    return D3D_START <= va < D3D_END or XGRPH_START <= va < XGRPH_END


def load(path: Path, alias: str):
    spec = importlib.util.spec_from_file_location(alias, path)
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load maintained source tools: " + str(path))
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def classify(address: int, by_va: dict, generated: dict) -> dict:
    exact = by_va.get(address)
    if exact is not None:
        return {
            "address": "0x%08X" % address,
            "classification": ("exact_source_entry" if address in generated
                               else "exact_entry_missing_generated_body"),
            "owner_va": "0x%08X" % address,
            "owner_end": "0x%08X" % exact["end"],
            "owner_name": exact["name"],
            "generated_source_file": generated[address]["file"] if address in generated else None,
            "original_label_present": None,
            "can_route_via_plain_function_lookup": address in generated,
        }
    owners = [row for row in by_va.values()
              if row["start"] < address < row["end"]]
    if len(owners) == 1:
        owner = owners[0]
        generated_body = generated.get(owner["start"], {}).get("source", "")
        labels = {int(x, 16) for x in LABEL.findall(generated_body)}
        return {
            "address": "0x%08X" % address,
            "classification": "interior_label" if address in labels else "interior_missing_label",
            "owner_va": "0x%08X" % owner["start"],
            "owner_end": "0x%08X" % owner["end"],
            "owner_name": owner["name"],
            "generated_source_file": generated.get(owner["start"], {}).get("file"),
            "original_label_present": address in labels,
            "can_route_via_plain_function_lookup": False,
        }
    return {
        "address": "0x%08X" % address,
        "classification": "overlapping_ranges" if owners else "not_in_retail_function_inventory",
        "owner_va": None, "owner_end": None, "owner_name": None,
        "generated_source_file": None, "original_label_present": False,
        "can_route_via_plain_function_lookup": False,
    }


def context_of_label(address: int, owner: dict, generated: dict) -> dict:
    if owner.get("owner_va") is None:
        return {"entry_context": [], "target_context": [], "itail_callsites": []}
    va = int(owner["owner_va"], 16)
    if va not in generated:
        return {"entry_context": [], "target_context": [], "itail_callsites": []}
    src = generated[va]["source"]
    lines = src.splitlines()
    entry = lines[:min(42, len(lines))]
    at = [i for i, line in enumerate(lines)
          if re.search(r'^\s*loc_%08X\s*:\s*;' % address, line, re.I)]
    target = lines[max(0, at[0]-12):min(len(lines), at[0]+28)] if len(at) == 1 else []
    itail_calls = []
    for i, line in enumerate(lines):
        if ITAIL_CALL.search(line):
            itail_calls.append({
                "line": i+1,
                "context": lines[max(0, i-3):min(len(lines), i+4)]
            })
    return {
        "original_source_sha256": sha(src.encode("utf-8")),
        "entry_context": entry,
        "target_label_occurrences": len(at),
        "target_context": target,
        "itail_callsites": itail_calls[:12],
        "full_itail_callsite_count": len(itail_calls),
    }


def select_graph(by_va: dict, generated: dict, base, existing: set[int],
                 capacity: int = MAX_CANDIDATES) -> tuple[list[dict], list[dict]]:
    names = {entry["name"]: va for va, entry in generated.items()}
    seed_report: list[dict] = []
    queue: deque[tuple[int, int, str]] = deque()
    for va, reason in SEEDS:
        classified = classify(va, by_va, generated)
        classified["observed_reason"] = reason
        seed_report.append(classified)
        if classified["classification"] == "exact_source_entry" and is_graphics(va):
            queue.append((va, 0, reason))
        # Never silently turn an interior VA into its containing function's
        # entry. That would execute the wrong original retail instructions.
    chosen = []
    seen = set()
    while queue and len(chosen) < capacity:
        va, depth, reason = queue.popleft()
        if va in seen:
            continue
        seen.add(va)
        if va in existing or va not in generated or not is_graphics(va):
            continue
        row = by_va.get(va)
        if row is None or row["start"] != va or row["end"] <= va:
            continue
        source = generated[va]["source"]
        direct_names = set(base.CALL_RE.findall(base.mask_noncode(source)))
        deps = sorted({
            names[name] for name in direct_names
            if name in names and names[name] != va and is_graphics(names[name])
        })
        chosen.append({
            "va": "0x%08X" % va, "name": generated[va]["name"],
            "source_file": generated[va]["file"],
            "source_sha256": sha(source.encode("utf-8")),
            "reason": reason, "depth": depth,
            "generated_direct_graphics_callees": ["0x%08X" % dep for dep in deps],
        })
        if depth < MAX_DIRECT_DEPTH:
            for dep in deps:
                if dep not in seen:
                    queue.append((dep, depth + 1, "direct callee of 0x%08X" % va))
    return seed_report, chosen


def find_existing(main: str, shards: Path) -> tuple[set[int], list[dict]]:
    if not shards.is_dir() or not (shards / "translated_runtime.h").is_file():
        raise ValueError("Original TrueTU directory/header missing")
    files = sorted(shards.glob("translated_???.cpp"))
    if len(files) != 64:
        raise ValueError("Expected exactly 64 TrueTU .cpp files")
    compiled: set[int] = set()
    ownership = []
    for file in files:
        source = file.read_text(encoding="utf-8", errors="replace")
        names = set(TRUE_TU_DEF.findall(source))
        for name in names:
            va = int(name[4:], 16)
            if va in compiled:
                raise ValueError("Duplicate original retail function across TrueTUs: " + name)
            compiled.add(va)
        ownership.append({"file": file.name, "sha256": sha(file.read_bytes())})
    for va_text, name in PACK_CASE.findall(main):
        va = int(va_text, 16)
        if name.upper() != ("sub_%08X" % va).upper():
            raise ValueError("Packed original function lookup mismatch: %s to %s" %
                             (va_text, name))
        compiled.add(va)
    return compiled, ownership


def plan(a) -> None:
    if a.output.resolve() == a.parent.resolve():
        raise ValueError("Do not overwrite original source with audit result")
    cache = a.functions.parent / ".disasm_cache.json"
    if not cache.is_file() or json.loads(
        cache.read_text(encoding="utf-8-sig")
    ).get("xbe_hash", "").upper() != XBE_SHA:
        raise ValueError("Original retail XBE SHA-256 provenance does not match")
    base = load(a.base_module, "k1batch_base")
    by_va, by_name = base.load_ranges(a.functions)
    generated = base.load_generated(a.generated_root, by_name)
    parent_bytes = a.parent.read_bytes()
    main = parent_bytes.decode("utf-8")
    if ("P6K1-D3D-DIRECT-289E20-20261103" not in main
            or "K1D3D SECOND: native Xenos Reset PASS" not in main
            or "P6DQ ROCKET HARD STOP" not in main
            or "K1STATE MAIN CHECKPOINT:" not in main):
        raise ValueError("Missing original successful graphics parent, checkpoint, or hard fence")
    existing, shards = find_existing(main, a.shards)
    target = classify(ITAIL, by_va, generated)
    if not is_graphics(ITAIL):
        raise ValueError("Last observed hardware ITAIL is outside original D3D/XGRPH")
    owner_context = context_of_label(ITAIL, target, generated)
    seeds, selected = select_graph(by_va, generated, base, existing)
    graph_digest = sha(json.dumps(selected, sort_keys=True).encode("utf-8"))
    if target["classification"] == "exact_source_entry":
        next_gate = ("SOURCE ENTRY KNOWN; ITAIL tail-call ABI dispatch still "
                     "requires exact owner/router implementation before XDK")
    elif target["classification"] == "interior_label":
        next_gate = ("INTERIOR LABEL: source-authentic entry-label control flow "
                     "and caller stack/register ABI required BEFORE XDK")
    else:
        next_gate = "NO SAFE ENTRY: resolve original XBE provenance/source before XDK"
    report = {
        "status": "K1_D3D_BATCH_AUDIT_ONLY_NEVER_XDK",
        "retail_xbe_sha256": XBE_SHA,
        "hardware_witness": {
            "target": "0x0029655D", "kind": "ITAIL", "caller": "0x0023A3CE",
            "saved_esp": "0x008BF544", "ticks": 58540888,
            "xenos_native_reset_pass": True,
            "guest_display_calls": 0,
        },
        "parent_main_sha256": sha(parent_bytes),
        "original_true_tus": 64, "modified_true_tus": 0,
        "translated_shard_hashes": shards,
        "function_inventory_count": len(by_va),
        "generated_original_c_functions": len(generated),
        "existing_packed_or_true_tu_count": len(existing),
        "itail_analysis": target,
        "itail_owner_original_source": owner_context,
        "seed_classification": seeds,
        "batch_candidate_count": len(selected),
        "source_authentic_candidates": selected,
        "batch_candidate_manifest_sha256": graph_digest,
        "candidate_cap": MAX_CANDIDATES,
        "direct_graph_depth_cap": MAX_DIRECT_DEPTH,
        "safe_to_build": False,
        "next_gate": next_gate,
        "false_claims_forbidden": [
            "every observed VA is a function entry",
            "compiled original body automatically handles an interior ITAIL",
            "entry or ABI proof follows from the successful native Reset",
            "guest pixels are being presented",
        ],
    }
    data = (json.dumps(report, indent=2) + "\n").encode("utf-8")
    a.output.parent.mkdir(parents=True, exist_ok=True)
    a.output.write_bytes(data)
    print("[K1D3D-BATCH] ORIGINAL retail XBE/hash PASS; original 64 TrueTUs untouched")
    print("[K1D3D-BATCH] ITAIL=%s classification=%s owner=%s .. %s label=%s" %
          (target["address"], target["classification"],
           target["owner_va"], target["owner_end"], target["original_label_present"]))
    print("[K1D3D-BATCH] Original owner source=%s labels=%s itail_callsites=%s" %
          (target["generated_source_file"],
           owner_context.get("target_label_occurrences", 0),
           owner_context.get("full_itail_callsite_count", 0)))
    print("[K1D3D-BATCH] GRAPH: seeds=%d source-authentic candidate=%d max=%d depth=%d digest=%s" %
          (len(seeds), len(selected), MAX_CANDIDATES, MAX_DIRECT_DEPTH, graph_digest[:16]))
    for row in seeds:
        print("[K1D3D-BATCH] SEED %s class=%s owner=%s source=%s" %
              (row["address"], row["classification"],
               row["owner_va"], row["generated_source_file"]))
    print("[K1D3D-BATCH] GATE: " + next_gate)
    print("[K1D3D-BATCH] NO XDK BUILD. NO XEX CHANGED. Report: " + str(a.output))


def selftest() -> None:
    class Base:
        CALL_RE = re.compile(r'\b(sub_[0-9A-Fa-f]{8})\s*\(')
        mask_noncode = staticmethod(lambda value: value)
    body = ("void sub_00296550(void)\n{\n"
            "    uint32_t ecx;\nloc_00296550: ;\nloc_0029655D: ;\n"
            "    sub_00296670();\n}\n")
    by_va = {
        0x00296550: {"start": 0x00296550, "end": 0x002965F0, "name": "sub_00296550"},
        0x002965F0: {"start": 0x002965F0, "end": 0x00296614, "name": "sub_002965F0"},
        0x00296670: {"start": 0x00296670, "end": 0x002966A0, "name": "sub_00296670"},
    }
    generated = {
        0x00296550: {"name": "sub_00296550", "source": body, "file": "original.c"},
        0x002965F0: {"name": "sub_002965F0", "source": "void sub_002965F0(void) { }", "file": "original.c"},
        0x00296670: {"name": "sub_00296670", "source": "void sub_00296670(void) { }", "file": "original.c"},
    }
    cls = classify(ITAIL, by_va, generated)
    assert cls["classification"] == "interior_label"
    assert cls["owner_va"] == "0x00296550"
    assert not cls["can_route_via_plain_function_lookup"]
    assert context_of_label(ITAIL, cls, generated)["target_label_occurrences"] == 1
    seeds, selected = select_graph(by_va, generated, Base(), set())
    assert any(x["va"] == "0x002965F0" for x in selected)
    assert all(x["va"] != "0x0029655D" for x in selected)
    cls2 = classify(0x002965F0, by_va, generated)
    assert cls2["classification"] == "exact_source_entry"
    assert cls2["can_route_via_plain_function_lookup"]
    absent = classify(0x0029655E, by_va, generated)
    assert absent["classification"] == "interior_missing_label"
    chosen_after_compiled = select_graph(by_va, generated, Base(), {0x002965F0})[1]
    assert not any(x["va"] == "0x002965F0" for x in chosen_after_compiled)
    print("[K1D3D-BATCH] SELFTEST PASS: interior ITAIL fenced, exact roots only, deduplicated bounded graphics graph, no XDK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    for arg in ("base-module", "functions", "generated-root", "parent",
                "shards", "output"):
        ap.add_argument("--" + arg, type=Path)
    a = ap.parse_args()
    if a.self_test:
        selftest()
        return
    for name in ("base_module", "functions", "generated_root",
                 "parent", "shards", "output"):
        if getattr(a, name) is None:
            ap.error("Missing --" + name.replace("_", "-"))
    plan(a)


if __name__ == "__main__":
    main()
