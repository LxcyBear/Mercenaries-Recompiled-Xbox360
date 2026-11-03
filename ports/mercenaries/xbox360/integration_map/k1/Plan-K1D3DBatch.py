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
    (0x002965A8, "first exact original function after ITAIL's 75-byte inventory gap"),
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



def inspect_tail_callers(by_va: dict, generated: dict, base,
                         existing: set[int]) -> list[dict]:
    """Original x86 caller/proximity addresses, with real C tail contexts."""
    # 'caller' in the P6DQ log is a route owner, not proof it contains the
    # exact indirect JMP instruction. Audit both the caller and D3D vicinity.
    addresses = (0x0023A3CE, 0x00296550, 0x0029655D,
                 0x002965F0, 0x00296614, 0x0029663F,
                 0x00296670, 0x002966A0, 0x002966F8,
                 0x0028E1C0)
    result = []
    owners_seen = set()
    for address in addresses:
        c = classify(address, by_va, generated)
        if not c["owner_va"]:
            continue
        owner = int(c["owner_va"], 16)
        if owner in owners_seen:
            continue
        owners_seen.add(owner)
        if owner not in generated:
            continue
        source = generated[owner]["source"]
        lines = source.splitlines()
        sites = []
        for i, line in enumerate(lines):
            if ITAIL_CALL.search(base.mask_noncode(line)):
                sites.append({
                    "line": i + 1,
                    "context": lines[max(0, i-6):min(len(lines), i+7)],
                    "nearest_prior_label": next(
                        (match.group(1)
                         for prev in reversed(lines[:i])
                         if (match := LABEL.match(prev))), None
                    ),
                })
        result.append({
            "owner_va": "0x%08X" % owner,
            "original_file": generated[owner]["file"],
            "compiled_in_main_or_64_tus": owner in existing,
            "original_source_sha256": sha(source.encode("utf-8")),
            "tail_site_count": len(sites),
            "tail_sites": sites[:16],
        })
    return result



def inspect_unmapped_gap(address: int, by_va: dict, generated: dict) -> dict:
    """Expose the exact original source inventory gap; do not guess a jump."""
    previous = sorted((row for row in by_va.values()
                       if row["start"] <= address),
                      key=lambda row: row["start"], reverse=True)[:3]
    following = sorted((row for row in by_va.values()
                        if row["start"] > address),
                       key=lambda row: row["start"])[:3]
    rows = []
    for direction, sample in (("previous", previous), ("following", following)):
        for item in sample:
            va = item["start"]
            source = generated.get(va, {}).get("source")
            lines = source.splitlines() if source else []
            nearby = []
            # Include exact generated-source evidence for this address only.
            for i, line in enumerate(lines):
                if ("%08X" % address).lower() in line.lower():
                    nearby.append({
                        "source_line": i+1,
                        "context": lines[max(0, i-3):min(len(lines), i+4)],
                    })
            rows.append({
                "direction": direction,
                "start": "0x%08X" % va,
                "end_exclusive": "0x%08X" % item["end"],
                "length": item["end"]-va,
                "name": item["name"],
                "inventory_fields": sorted(item.keys()),
                "source_file": generated.get(va, {}).get("file"),
                "original_source_sha256": sha(source.encode("utf-8")) if source else None,
                "entry_first_28_lines": lines[:28],
                "ending_last_36_lines": lines[-36:],
                "literal_target_references": nearby[:6],
            })
    predecessor = previous[0] if previous else None
    successor = following[0] if following else None
    prev_end = predecessor["end"] if predecessor else None
    next_start = successor["start"] if successor else None
    region_kind = (
        "function_inventory_gap"
        if prev_end is not None and next_start is not None
           and prev_end <= address < next_start
        else "overlap_or_unresolved_inventory_region"
    )
    # A 0x9655D pointer is not evidence of an instruction start.
    # The exact boundary and source bytes must be checked first.
    hits = []
    needle = ("%08X" % address).lower()
    for va, entry in generated.items():
        if not is_graphics(va):
            continue
        source = entry["source"]
        if needle in source.lower():
            refs = []
            for i, line in enumerate(source.splitlines()):
                if needle in line.lower():
                    refs.append({"line": i+1, "text": line.strip()})
            hits.append({
                "function_start": "0x%08X" % va,
                "source_file": entry["file"],
                "text_matches": refs[:8],
            })
            if len(hits) >= 32:
                break
    return {
        "target": "0x%08X" % address,
        "inventory_region_kind": region_kind,
        "predecessor_start": ("0x%08X" % predecessor["start"]) if predecessor else None,
        "predecessor_end_exclusive": ("0x%08X" % prev_end) if prev_end is not None else None,
        "target_minus_predecessor_end": address-prev_end if prev_end is not None else None,
        "successor_start": ("0x%08X" % next_start) if next_start is not None else None,
        "successor_start_minus_target": next_start-address if next_start is not None else None,
        "gap_width_bytes": next_start-prev_end if
            prev_end is not None and next_start is not None else None,
        "target_is_predecessor_end_exclusive": address == prev_end,
        "adjacent_original_function_sources": rows,
        "original_d3d_source_text_references": hits,
        "raw_instruction_bytes_required": True,
        "safe_to_dispatch_as_function": False,
    }



JUMP_TABLE_SOURCE = 0x00296550
JUMP_TABLE_START = 0x002965D4
JUMP_TABLE_COUNT = 16
JUMP_TABLE_END = JUMP_TABLE_START + 4 * JUMP_TABLE_COUNT
JUMP_TABLE_CODE = re.compile(
    r'\bRECOMP_ITAIL\s*\(\s*GUEST_READ32\s*\(\s*eax\s*\*\s*4\s*\+\s*'
    r'0x2965D4\s*\)\s*\)\s*;'
)


def prove_d3d_jump_table(by_va: dict, generated: dict) -> dict:
    """Source-proven indexed indirect branch and inventory/code overlap.

    This does NOT assert the table bytes are static pointers, because the
    original D3D segment can be writable at runtime.
    """
    row = generated.get(JUMP_TABLE_SOURCE)
    if not row:
        raise ValueError("Retail 00296550 original translated source absent")
    masked = row["source"]
    if len(JUMP_TABLE_CODE.findall(masked)) != 1 or not re.search(
        r'\beax\s*=\s*eax\s*&\s*0xF\s*;', masked
    ) or not re.search(r'\bPUSH32\s*\(\s*esp\s*,\s*esi\s*\)', masked):
        raise ValueError(
            "Retail D3D 00296550 indexed-ITAIL/guest-stack contract changed"
        )
    overlaps = []
    for row in by_va.values():
        start, end = row["start"], row["end"]
        if start < JUMP_TABLE_END and end > JUMP_TABLE_START:
            overlaps.append({
                "source_start": "0x%08X" % start,
                "source_end_exclusive": "0x%08X" % end,
                "source_name": row["name"],
                "starts_inside_jump_table": JUMP_TABLE_START <= start < JUMP_TABLE_END,
                "start_table_slot_index": ((start - JUMP_TABLE_START) // 4)
                if (JUMP_TABLE_START <= start < JUMP_TABLE_END
                    and (start - JUMP_TABLE_START) % 4 == 0) else None,
                "generated_body_present": start in generated,
                "overlap_start": "0x%08X" % max(start, JUMP_TABLE_START),
                "overlap_end_exclusive": "0x%08X" % min(end, JUMP_TABLE_END),
            })
    return {
        "verified_original_source_function": "0x%08X" % JUMP_TABLE_SOURCE,
        "verified_original_source_file": generated[JUMP_TABLE_SOURCE]["file"],
        "source_sha256": sha(generated[JUMP_TABLE_SOURCE]["source"].encode("utf-8")),
        "indexed_dispatch_rule": "eax=(edi & 15); PUSH32(esp,esi); ITAIL=GUEST_READ32(0x002965D4+eax*4)",
        "table_start": "0x%08X" % JUMP_TABLE_START,
        "table_end_exclusive": "0x%08X" % JUMP_TABLE_END,
        "entries": JUMP_TABLE_COUNT,
        "bytes": JUMP_TABLE_COUNT * 4,
        "observed_hardware_target": "0x%08X" % ITAIL,
        "original_function_inventory_overlaps": overlaps,
        "ambiguous_code_data_region": bool(overlaps),
        "retail_source_proves_actual_table_values": False,
        "guest_memory_table_could_be_modified_at_runtime": True,
        "safe_to_reclassify_compiled_function_as_data": False,
        "safe_to_emulate_tail_target": False,
    }


def read_verified_jump_table(blob: bytes, section_rows: list[tuple],
                             by_va: dict, generated: dict) -> dict:
    """Extract 16 original Xbox little-endian DWORDs with section bounds."""
    import struct
    sections = [r for r in section_rows if
                r[1] <= JUMP_TABLE_START and
                JUMP_TABLE_END <= r[1]+r[2] and
                JUMP_TABLE_END <= r[1]+r[4]]
    if len(sections) != 1:
        raise ValueError("Jump-table 64 bytes do not fit unique original raw section")
    _, va, _, raw, _ = sections[0]
    off = raw + JUMP_TABLE_START - va
    if off < 0 or off + JUMP_TABLE_COUNT*4 > len(blob):
        raise ValueError("Retail XBE jump-table raw bytes out of bounds")
    values = struct.unpack_from("<16I", blob, off)
    rows = []
    for idx, value in enumerate(values):
        classified = classify(value, by_va, generated)
        rows.append({
            "index": idx,
            "table_word_va": "0x%08X" % (JUMP_TABLE_START + 4*idx),
            "raw_word_hex_little_endian": blob[off+4*idx:off+4*idx+4].hex(" "),
            "value": "0x%08X" % value,
            "destination_classification": classified["classification"],
            "destination_inventory_owner": classified["owner_va"],
            "destination_in_d3d_section": D3D_START <= value < D3D_END,
            "destination_in_75_byte_gap": ITAIL <= value < 0x002965A8,
            "matches_hardware_itail": value == ITAIL,
        })
    return {
        "table_va": "0x%08X" % JUMP_TABLE_START,
        "table_file_offset": "0x%08X" % off,
        "entries": rows,
        "hardware_target_match_indices": [
            row["index"] for row in rows if row["matches_hardware_itail"]],
        "matching_hardware_target_present_in_original_raw_bytes": ITAIL in values,
        "table_entry_values_sha256": sha(blob[off:off+64]),
        "static_file_table_is_not_a_runtime_memory_proof": True,
    }


def inspect_verified_xbe_bytes(path: Path, target: int,
                               by_va: dict | None = None,
                               generated: dict | None = None) -> dict:
    """Read a *user-local* exact-SHA original XBE, never copy it into repo."""
    import struct
    blob = path.read_bytes()
    digest = sha(blob).upper()
    if digest != XBE_SHA:
        raise ValueError("Local XBE SHA-256 does not match supported retail build: "
                         + digest)
    if len(blob) < 0x124 or blob[:4] != b"XBEH":
        raise ValueError("Retail XBE has no valid XBEH header")
    base = struct.unpack_from("<I", blob, 0x104)[0]
    count = struct.unpack_from("<I", blob, 0x11C)[0]
    table_va = struct.unpack_from("<I", blob, 0x120)[0]
    table_off = table_va-base
    if count == 0 or count > 64 or table_off < 0 or \
       table_off+count*0x38 > len(blob):
        raise ValueError("Retail XBE section table missing/out of bounds")
    section_rows = []
    sections = []
    for i in range(count):
        off = table_off+i*0x38
        va, virtual_size, raw, raw_size = struct.unpack_from("<IIII", blob, off+4)
        section_rows.append((i, va, virtual_size, raw, raw_size))
        if va <= target < va+virtual_size:
            sections.append((i, va, virtual_size, raw, raw_size))
    if len(sections) != 1:
        raise ValueError("Target lacks unique retail-XBE section byte provenance")
    number, va, virtual_size, raw, raw_size = sections[0]
    start = max(va, target-32)
    end = min(va+virtual_size, va+raw_size, target+96)
    start_file = raw+(start-va)
    end_file = raw+(end-va)
    if end <= start or start_file < 0 or end_file > len(blob):
        raise ValueError("Requested XBE window outside real raw section bytes")
    return {
        "exact_retail_xbe_sha256": digest,
        "original_xbe_path_local_only": str(path),
        "section_index": number,
        "section_va": "0x%08X" % va,
        "section_virtual_size": virtual_size,
        "section_raw_offset": "0x%08X" % raw,
        "section_raw_size": raw_size,
        "target_raw_file_offset": "0x%08X" % (raw+target-va),
        "window_start_va": "0x%08X" % start,
        "window_end_va_exclusive": "0x%08X" % end,
        "original_128_byte_window_hex": blob[start_file:end_file].hex(" "),
        "disassembly_status": "raw exact bytes only; x86 instruction boundary not assumed",
        "source_verified_jump_table": (
            read_verified_jump_table(blob, section_rows, by_va, generated)
            if by_va is not None and generated is not None else None
        ),
    }


def select_graph(by_va: dict, generated: dict, base, existing: set[int],
                 capacity: int = MAX_CANDIDATES) -> tuple[list[dict], list[dict], dict]:
    """Traverse existing compiled functions to discover missing graph leaves.

    Existing compiled seeds aren't candidates, but their *original* direct
    calls may lead to novel, genuine D3D/XGRPH functions. Never stop the BFS
    just because a seed is already in the parent lookup or original TrueTUs.
    """
    names = {entry["name"]: va for va, entry in generated.items()}
    seed_report: list[dict] = []
    queue: deque[tuple[int, int, str]] = deque()
    for va, reason in SEEDS:
        classified = classify(va, by_va, generated)
        classified["observed_reason"] = reason
        classified["compiled_in_parent_or_true_tu"] = va in existing
        seed_report.append(classified)
        if classified["classification"] == "exact_source_entry" and is_graphics(va):
            queue.append((va, 0, reason))
        # Never silently turn a mid-function VA into the owner's entry.
    chosen: list[dict] = []
    seen: set[int] = set()
    traversed_existing = 0
    traversed_original = 0
    beyond_graphics = 0
    skipped_missing_body = 0
    truncated = False
    # Bounded search, independent of count of *new* candidates.
    while queue:
        if len(chosen) >= capacity or len(seen) >= 1024:
            truncated = True
            break
        va, depth, reason = queue.popleft()
        if va in seen:
            continue
        seen.add(va)
        if not is_graphics(va):
            beyond_graphics += 1
            continue
        if va not in generated:
            skipped_missing_body += 1
            continue
        row = by_va.get(va)
        if row is None or row["start"] != va or row["end"] <= va:
            skipped_missing_body += 1
            continue
        source = generated[va]["source"]
        direct_names = set(base.CALL_RE.findall(base.mask_noncode(source)))
        deps = sorted({
            names[name] for name in direct_names
            if name in names and names[name] != va and is_graphics(names[name])
        })
        traversed_original += 1
        if va in existing:
            traversed_existing += 1
        else:
            chosen.append({
                "va": "0x%08X" % va, "name": generated[va]["name"],
                "source_file": generated[va]["file"],
                "source_sha256": sha(source.encode("utf-8")),
                "reason": reason, "depth": depth,
                "generated_direct_graphics_callees": [
                    "0x%08X" % dep for dep in deps],
            })
        if depth < MAX_DIRECT_DEPTH:
            for dep in deps:
                if dep not in seen:
                    queue.append((dep, depth+1,
                                  "direct callee of 0x%08X" % va))
    metrics = {
        "observed_seed_count": len(SEEDS),
        "observed_exact_source_seed_count": sum(
            int(row["classification"] == "exact_source_entry")
            for row in seed_report),
        "already_compiled_exact_seed_count": sum(
            int(row["classification"] == "exact_source_entry" and
                row["compiled_in_parent_or_true_tu"])
            for row in seed_report),
        "existing_original_functions_traversed": traversed_existing,
        "total_original_functions_traversed": traversed_original,
        "source_missing_bodies_or_malformed_ranges": skipped_missing_body,
        "outside_graphics_graph_count": beyond_graphics,
        "visited_distinct_vas": len(seen),
        "graph_truncated": truncated,
        "candidate_count": len(chosen),
    }
    return seed_report, chosen, metrics

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
    gap = inspect_unmapped_gap(ITAIL, by_va, generated)
    jump_table = prove_d3d_jump_table(by_va, generated)
    local_xbe = inspect_verified_xbe_bytes(a.xbe, ITAIL, by_va, generated) if a.xbe else None
    seeds, selected, graph_metrics = select_graph(by_va, generated, base, existing)
    control_flow_contexts = inspect_tail_callers(by_va, generated, base, existing)
    graph_digest = sha(json.dumps(selected, sort_keys=True).encode("utf-8"))
    if target["classification"] == "exact_source_entry":
        next_gate = ("SOURCE ENTRY KNOWN; ITAIL tail-call ABI dispatch still "
                     "requires exact owner/router implementation before XDK")
    elif target["classification"] == "interior_label":
        next_gate = ("INTERIOR LABEL: source-authentic entry-label control flow "
                     "and caller stack/register ABI required BEFORE XDK")
    elif target["classification"] == "not_in_retail_function_inventory" and \
         gap["target_is_predecessor_end_exclusive"]:
        next_gate = (
            "16-WAY ITAIL from original 00296550: verify raw jump-table slots "
            "002965D4..00296613, code/data overlap at 002965F0 and guest "
            "stack/target ABI. Do not build an invented function."
        )
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
        "itail_gap_provenance": gap,
        "source_proven_16_entry_indirect_jump_table": jump_table,
        "verified_local_original_xbe_target_bytes": local_xbe,
        "itail_owner_original_source": owner_context,
        "related_original_c_control_flow": control_flow_contexts,
        "seed_classification": seeds,
        "graph_metrics": graph_metrics,
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
    print("[K1D3D-BATCH] RETAIL DISASM CACHE/hash PASS; original 64 TrueTUs untouched")
    if local_xbe is None:
        print("[K1D3D-BATCH] RAW XBE NOT CHECKED: cannot prove jump-table DWORD values from cache alone")
    print("[K1D3D-BATCH] ITAIL=%s classification=%s owner=%s .. %s label=%s" %
          (target["address"], target["classification"],
           target["owner_va"], target["owner_end"], target["original_label_present"]))
    print("[K1D3D-BATCH] GAP PROVENANCE: type=%s prev=%s end=%s delta=%s next=%s distance=%s width=%s" %
          (gap["inventory_region_kind"], gap["predecessor_start"],
           gap["predecessor_end_exclusive"],
           gap["target_minus_predecessor_end"],
           gap["successor_start"], gap["successor_start_minus_target"],
           gap["gap_width_bytes"]))
    for item in gap["original_d3d_source_text_references"]:
        for site in item["text_matches"][:8]:
            print("[K1D3D-BATCH] EXACT TARGET C REFERENCE: function=%s file=%s line=%u text=%s" %
                  (item["function_start"], item["source_file"],
                   site["line"], site["text"][:240]))
    if gap["target_is_predecessor_end_exclusive"]:
        print("[K1D3D-BATCH] CRITICAL: hardware ITAIL equals exclusive END of %s, NOT valid function start" %
              gap["predecessor_start"])
    for item in gap["adjacent_original_function_sources"]:
        if item["direction"] == "previous" and item["start"] == gap["predecessor_start"]:
            print("[K1D3D-BATCH] PREVIOUS ORIGINAL SOURCE TAIL %s file=%s:" %
                  (item["start"], item["source_file"]))
            for line in item["ending_last_36_lines"][-24:]:
                print("[K1D3D-BATCH]   " + line[:240])
        if item["direction"] == "following" and item["start"] == gap["successor_start"]:
            print("[K1D3D-BATCH] NEXT ORIGINAL SOURCE HEAD %s file=%s:" %
                  (item["start"], item["source_file"]))
            for line in item["entry_first_28_lines"][:18]:
                print("[K1D3D-BATCH]   " + line[:240])
    for item in selected:
        print("[K1D3D-BATCH] MISSING SOURCE CANDIDATE %s file=%s depth=%d from=%s" %
              (item["va"], item["source_file"], item["depth"], item["reason"]))
    print("[K1D3D-BATCH] JUMPTABLE PROVEN: 00296550 -> GUEST_READ32(002965D4 + 4*(edi&15)); 16 entries; table end=%s" %
          jump_table["table_end_exclusive"])
    for overlap in jump_table["original_function_inventory_overlaps"]:
        print("[K1D3D-BATCH] CODE/DATA CONFLICT: %s..%s overlaps table slot=%s source=%s" %
              (overlap["source_start"], overlap["source_end_exclusive"],
               overlap["start_table_slot_index"], overlap["source_name"]))
    if local_xbe is not None:
        proof = local_xbe["source_verified_jump_table"]
        for slot in proof["entries"]:
            print("[K1D3D-BATCH] TABLE[%02u] @%s -> %s (%s)%s" %
                  (slot["index"], slot["table_word_va"], slot["value"],
                   slot["destination_classification"],
                   " [HARDWARE TARGET]" if slot["matches_hardware_itail"] else ""))
        print("[K1D3D-BATCH] STATIC TABLE VS HARDWARE: matched_indices=%s; runtime data could differ" %
              proof["hardware_target_match_indices"])
    print("[K1D3D-BATCH] Target literal in other original D3D source bodies: %u; exact local-XBE bytes: %s" %
          (len(gap["original_d3d_source_text_references"]), "YES" if local_xbe else "NOT SUPPLIED"))
    print("[K1D3D-BATCH] Original owner source=%s labels=%s itail_callsites=%s" %
          (target["generated_source_file"],
           owner_context.get("target_label_occurrences", 0),
           owner_context.get("full_itail_callsite_count", 0)))
    print("[K1D3D-BATCH] RELATED ORIGINAL CALLSITES: owners=%u itail_macro_sites=%u" %
          (len(control_flow_contexts),
           sum(item["tail_site_count"] for item in control_flow_contexts)))
    print("[K1D3D-BATCH] GRAPH WALK: compiled_seeds=%d traversed_original=%d traversed_compiled=%d truncated=%s" %
          (graph_metrics["already_compiled_exact_seed_count"],
           graph_metrics["total_original_functions_traversed"],
           graph_metrics["existing_original_functions_traversed"],
           graph_metrics["graph_truncated"]))
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
    proof_generated = dict(generated)
    proof_generated[JUMP_TABLE_SOURCE] = {
        "name": "sub_00296550",
        "source": "void sub_00296550(void){ eax=edi; "
                  "PUSH32(esp, esi); eax = eax & 0xF; "
                  "RECOMP_ITAIL(GUEST_READ32(eax * 4 + 0x2965D4));}",
        "file": "original.c",
    }
    jt = prove_d3d_jump_table(by_va, proof_generated)
    assert jt["entries"] == 16
    assert jt["table_end_exclusive"] == "0x00296614"
    assert jt["ambiguous_code_data_region"] and not jt["safe_to_emulate_tail_target"]
    assert any(r["source_start"] == "0x002965F0" and
               r["start_table_slot_index"] == 7
               for r in jt["original_function_inventory_overlaps"])
    import struct
    sample_blob = bytearray(128)
    values = [0x0029655D]+[0x002965A8]*15
    struct.pack_into("<16I", sample_blob, 0, *values)
    sample_table = read_verified_jump_table(
        bytes(sample_blob), [(3, JUMP_TABLE_START, 128, 0, 128)],
        by_va, generated)
    assert sample_table["hardware_target_match_indices"] == [0]
    assert sample_table["entries"][0]["destination_in_75_byte_gap"]
    assert sample_table["entries"][0]["destination_in_d3d_section"]
    try:
        prove_d3d_jump_table(by_va, {
            **generated, JUMP_TABLE_SOURCE: {
                "source": "void sub_00296550(void){RECOMP_ITAIL(0x2965D4);}",
                "file": "changed.c"}})
    except ValueError:
        pass
    else:
        raise AssertionError("Changed original jumptable code accepted")

    assert cls["owner_va"] == "0x00296550"
    assert not cls["can_route_via_plain_function_lookup"]
    assert context_of_label(ITAIL, cls, generated)["target_label_occurrences"] == 1
    seeds, selected, stats = select_graph(by_va, generated, Base(), set())
    assert stats["total_original_functions_traversed"] >= 2
    assert any(x["va"] == "0x002965F0" for x in selected)
    assert all(x["va"] != "0x0029655D" for x in selected)
    cls2 = classify(0x002965F0, by_va, generated)
    assert cls2["classification"] == "exact_source_entry"
    # Exercise inventory-gap interpretation without inventing a function
    # or claiming an instruction boundary.
    with_gap = {
        0x00296550: {"start": 0x00296550, "end": 0x0029655C,
                     "name": "sub_00296550"},
        0x002965F0: {"start": 0x002965F0, "end": 0x00296614,
                     "name": "sub_002965F0"},
    }
    gap = inspect_unmapped_gap(ITAIL, with_gap, generated)
    assert gap["inventory_region_kind"] == "function_inventory_gap"
    assert gap["predecessor_end_exclusive"] == "0x0029655C"
    assert gap["target_minus_predecessor_end"] == 1
    assert gap["successor_start_minus_target"] == 0x93
    assert gap["gap_width_bytes"] == 0x94
    assert gap["target_is_predecessor_end_exclusive"] is False
    edge_gap = {
        0x00296550: {"start": 0x00296550, "end": 0x0029655D, "name": "sub_00296550"},
        0x002965A8: {"start": 0x002965A8, "end": 0x002965F0, "name": "sub_002965A8"},
    }
    edge = inspect_unmapped_gap(ITAIL, edge_gap, generated)
    assert edge["target_is_predecessor_end_exclusive"]
    assert edge["successor_start_minus_target"] == 75
    assert edge["gap_width_bytes"] == 75

    assert not gap["safe_to_dispatch_as_function"]
    with_bad_xbe = Path(__file__).resolve()
    try:
        inspect_verified_xbe_bytes(with_bad_xbe, ITAIL)
    except ValueError:
        pass
    else:
        raise AssertionError("Unverified source file accepted as retail XBE")
    assert cls2["can_route_via_plain_function_lookup"]
    absent = classify(0x0029655E, by_va, generated)
    assert absent["classification"] == "interior_missing_label"
    sites = inspect_tail_callers(by_va, generated, Base(), set())
    assert any(row["owner_va"] == "0x00296550" for row in sites)
    chosen_after_compiled = select_graph(by_va, generated, Base(), {0x002965F0})[1]
    assert not any(x["va"] == "0x002965F0" for x in chosen_after_compiled)
    # Regression: previously compiled start must be traversed, so its real
    # uncompiled sub_00296670 callee remains discoverable.
    compiled_graph = select_graph(
        by_va, generated, Base(), {0x00296550, 0x002965F0})[1]
    assert any(x["va"] == "0x00296670" for x in compiled_graph)
    assert not any(x["va"] in ("0x00296550", "0x002965F0")
                   for x in compiled_graph)
    print("[K1D3D-BATCH] SELFTEST PASS: interior ITAIL fenced, exact roots only, deduplicated bounded graphics graph, no XDK")


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--self-test", action="store_true")
    for arg in ("base-module", "functions", "generated-root", "parent",
                "shards", "output"):
        ap.add_argument("--" + arg, type=Path)
    ap.add_argument("--xbe", type=Path,
                    help="Optional exact local retail default.xbe for raw instruction-window provenance")
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
