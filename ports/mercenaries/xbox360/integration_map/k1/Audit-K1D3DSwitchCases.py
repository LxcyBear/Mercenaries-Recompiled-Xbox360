#!/usr/bin/env python3
"""Exact-SHA retail XBE: recover six D3D jump-table case code paths.

Source-only. Never copies the XBE, rewrites the guest, edits 64 TrueTUs,
compiles an XEX, or invents an instruction. Uses Capstone x86-32 for
bounded basic-block decoding directly from the user's own retail bytes.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import struct
from collections import deque
from pathlib import Path

XBE_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
SOURCE_ENTRY = 0x00296550
CODE_FIRST = 0x0029655D
CODE_STOP = 0x002965D4  # Data table starts here, not valid sequential code
TABLE = 0x002965D4
CODE_AFTER_TABLE = 0x002965F0
SENTINEL_AT = TABLE + 6*4
# Derived from the local retail XBE hash-verified result.
SIX_SOURCE_DESTINATIONS = (
    0x002965A3, 0x00296599, 0x0029655D,
    0x00296577, 0x0029657E, 0x00296592,
)
PADDING = 0xCCCCCCCC


def hash_bytes(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()


def get_retail_sections(path: Path) -> tuple[bytes, list[tuple[int, int, int, int, int]]]:
    blob = path.read_bytes()
    if hash_bytes(blob).upper() != XBE_SHA:
        raise ValueError("Original retail default.xbe SHA-256 mismatch; refusing decode")
    if len(blob) < 0x124 or blob[:4] != b"XBEH":
        raise ValueError("Not an original XBEH image")
    base = struct.unpack_from("<I", blob, 0x104)[0]
    count = struct.unpack_from("<I", blob, 0x11C)[0]
    table_va = struct.unpack_from("<I", blob, 0x120)[0]
    tab_off = table_va-base
    if not (1 <= count <= 64) or tab_off < 0 or tab_off + 0x38*count > len(blob):
        raise ValueError("Invalid XBE section table")
    result = []
    for i in range(count):
        off = tab_off + i*0x38
        va, virtual_size, raw_offset, raw_size = struct.unpack_from(
            "<IIII", blob, off + 4)
        if (raw_offset < 0 or raw_size < 0 or
                raw_offset+raw_size > len(blob)):
            raise ValueError("Retail section raw bytes out of image bounds")
        result.append((i, va, virtual_size, raw_offset, raw_size))
    return blob, result


def bytes_at(blob: bytes, sections: list[tuple], va: int, size: int) -> bytes:
    if size < 0:
        raise ValueError("Negative read")
    rows = [(idx, start, raw, raw_size)
            for idx, start, virtual_size, raw, raw_size in sections
            if start <= va and va+size <= start+virtual_size
            and va+size <= start+raw_size]
    if len(rows) != 1:
        raise ValueError("Original XBE VA 0x%08X/%d has no unique full raw mapping" %
                         (va, size))
    _, start, raw, _ = rows[0]
    return blob[raw+(va-start):raw+(va-start)+size]


def classify_static_slots(words: tuple[int, ...]) -> dict:
    if len(words) != 7:
        raise ValueError("Expected exactly six original pointer words plus sentinel")
    if tuple(words[:6]) != SIX_SOURCE_DESTINATIONS:
        raise ValueError("Six original x86 jump-table destination words differ from hardware witness")
    if words[6] != PADDING:
        raise ValueError("Original 0xCCCCCCCC padding/sentinel changed")
    if len(set(words[:6])) != 6:
        raise ValueError("Duplicate original case addresses unexpected")
    if any(not (CODE_FIRST <= va < 0x002965A8) for va in words[:6]):
        raise ValueError("Original case destination outside the 75-byte switch code gap")
    return {
        "source_rule": "index = edi & 15; PUSH32(esp,esi); guest READ32(0x002965D4 + index*4) then indirect tail",
        "guest_mathematical_index_range": "0..15",
        "exact_sha_original_pointer_slots": 6,
        "valid_pointer_slot_indices": [0, 1, 2, 3, 4, 5],
        "index_6_padding_sentinel": "0xCCCCCCCC",
        "index_7_plus_overlaps_real_code_at": "0x002965F0",
        "source_proves_bounds_check_for_indices_6_to_15": False,
        "source_proves_valid_case_targets_for_indices_6_to_15": False,
        "hardware_observed_case_index": 2,
        "case_targets": ["0x%08X" % value for value in words[:6]],
    }


def decode_case(cs, cap, blob: bytes, sections: list[tuple], entry: int) -> dict:
    """Bounded reachability: decode one instruction at a time, follow x86
    immediate branches, keep falls-through; never reinterpret the data table.
    """
    work = deque([(entry, "case_entry")])
    seen: set[int] = set()
    ownership: dict[int, int] = {}
    decoded: dict[int, dict] = {}
    edges: list[dict] = []
    hazards: list[str] = []
    budget = 256
    while work and len(decoded) < budget:
        pc, origin = work.popleft()
        if pc in seen:
            continue
        seen.add(pc)
        if pc == CODE_STOP:
            edges.append({"from": origin, "to": "0x%08X" % pc,
                          "kind": "fallthrough_reaches_static_jump_table_data"})
            hazards.append("Execution path reaches data table without terminator")
            continue
        if not (CODE_FIRST <= pc < CODE_STOP):
            edges.append({"from": origin, "to": "0x%08X" % pc,
                          "kind": "leaves_case_decode_window"})
            continue
        n = min(15, CODE_STOP-pc)
        chunk = bytes_at(blob, sections, pc, n)
        instructions = list(cs.disasm(chunk, pc, count=1))
        if not instructions:
            hazards.append("No valid x86 instruction at 0x%08X" % pc)
            continue
        insn = instructions[0]
        if insn.address != pc or insn.size <= 0 or pc+insn.size > CODE_STOP:
            hazards.append("Decode runs into static data at 0x%08X" % pc)
            continue
        for address in range(pc, pc+insn.size):
            prior = ownership.get(address)
            if prior is not None and prior != pc:
                hazards.append("Overlapping instructions at 0x%08X (%08X/%08X)" %
                               (address, prior, pc))
            ownership[address] = pc
        reg = {
            "va": "0x%08X" % pc,
            "size": insn.size,
            "bytes": insn.bytes.hex(" "),
            "mnemonic": insn.mnemonic,
            "operands": insn.op_str,
            "next_sequential_va": "0x%08X" % (pc+insn.size),
        }
        decoded[pc] = reg
        from_id = "0x%08X" % pc
        next_pc = pc+insn.size
        if insn.group(cap.CS_GRP_RET):
            edges.append({"from": from_id, "kind": "return"})
            continue
        if insn.mnemonic in ("int3", "ud2", "hlt"):
            edges.append({"from": from_id, "kind": "trap"})
            continue
        if insn.group(cap.CS_GRP_JUMP):
            target = None
            if insn.operands and insn.operands[0].type == cap.CS_OP_IMM:
                target = insn.operands[0].imm & 0xFFFFFFFF
            conditional = insn.mnemonic not in ("jmp", "ljmp")
            if target is not None:
                edges.append({"from": from_id, "to": "0x%08X" % target,
                              "kind": "conditional_jump" if conditional else "direct_jump"})
                work.append((target, from_id))
            else:
                edges.append({"from": from_id, "kind": "indirect_jump",
                              "operand": insn.op_str})
            if conditional:
                edges.append({"from": from_id, "to": "0x%08X" % next_pc,
                              "kind": "condition_not_taken"})
                work.append((next_pc, from_id))
            continue
        if insn.group(cap.CS_GRP_CALL):
            target = None
            if insn.operands and insn.operands[0].type == cap.CS_OP_IMM:
                target = insn.operands[0].imm & 0xFFFFFFFF
            edges.append({"from": from_id,
                          "to": "0x%08X" % target if target is not None else None,
                          "kind": "direct_call" if target is not None else "indirect_call"})
        work.append((next_pc, from_id))
    if work:
        hazards.append("Case decoder exceeded bounded instruction/branch budget")
    return {
        "case_entry_va": "0x%08X" % entry,
        "insn_count": len(decoded),
        "instructions": [decoded[va] for va in sorted(decoded)],
        "control_flow_edges": edges,
        "hazards": sorted(set(hazards)),
        "decode_complete_within_static_code_window": not hazards and not work,
    }


def analyze(a) -> None:
    try:
        import capstone as cap
    except ImportError as exc:
        raise ValueError(
            "Capstone x86 disassembler is needed. Install into your Python: "
            "python -m pip install capstone"
        ) from exc
    blob, sections = get_retail_sections(a.xbe)
    words = struct.unpack("<7I", bytes_at(blob, sections, TABLE, 28))
    proof = classify_static_slots(words)
    if a.original_generated_c:
        source = a.original_generated_c.read_text(encoding="utf-8", errors="replace")
        for exact in (
            "void sub_00296550(void)",
            "RECOMP_ITAIL(GUEST_READ32(eax * 4 + 0x2965D4))",
            "PUSH32(esp, esi)",
            "eax = eax & 0xF",
        ):
            if exact not in source:
                raise ValueError("Maintained original C corpus no longer proves: "+exact)
    cs = cap.Cs(cap.CS_ARCH_X86, cap.CS_MODE_32)
    cs.detail = True
    cases = [decode_case(cs, cap, blob, sections, va)
             for va in SIX_SOURCE_DESTINATIONS]
    all_instruction_addresses = {
        int(ins["va"], 16)
        for case in cases for ins in case["instructions"]
    }
    every_case_lands_on_instruction_boundary = all(
        va in all_instruction_addresses for va in SIX_SOURCE_DESTINATIONS)
    errors = [h for case in cases for h in case["hazards"]]
    output = {
        "status": "K1_D3D_ORIGINAL_XBE_JUMP_CASES_SOURCE_ONLY",
        "original_retail_xbe_sha256": XBE_SHA,
        "original_source_proof": proof,
        "machine_code_region": {
            "switch_dispatch_function": "0x00296550",
            "case_code_first": "0x%08X" % CODE_FIRST,
            "case_code_stop": "0x%08X" % CODE_STOP,
            "recognized_original_function_start_in_case_region": "0x002965A8",
            "first_later_function": "0x002965F0",
            "original_raw_case_code_sha256": hash_bytes(
                bytes_at(blob, sections, CODE_FIRST, CODE_STOP-CODE_FIRST)),
        },
        "case_paths": cases,
        "six_target_instruction_alignment_proven": every_case_lands_on_instruction_boundary,
        "decode_hazards": sorted(set(errors)),
        "has_hardware_guest_register_snapshots": False,
        "guest_esi_was_pushed_before_itail": True,
        "safe_to_modify_guest_dispatch": False,
        "safe_to_build_new_xex": False,
        "source_only": True,
    }
    a.out.parent.mkdir(parents=True, exist_ok=True)
    a.out.write_text(json.dumps(output, indent=2)+"\n", encoding="utf-8")
    print("[K1D3D-CASES] VERIFIED ORIGINAL RETAIL XBE SHA256 "+XBE_SHA)
    print("[K1D3D-CASES] STATIC CASE POINTERS: 6, indices 0..5; slot 6=CCCCCCCC sentinel")
    print("[K1D3D-CASES] ORIGINAL CODE STARTS 002965F0: do NOT interpret raw bytes as TABLE[07..15]")
    print("[K1D3D-CASES] ORIGINAL CODE CASES: 0029655D..002965D3")
    for slot, case in enumerate(cases):
        print("[K1D3D-CASES] === CASE[%d] target=%s insns=%d hazards=%d ===" %
              (slot, case["case_entry_va"], case["insn_count"], len(case["hazards"])))
        for ins in case["instructions"]:
            print("[K1D3D-CASES] %s  %-22s %-7s %s" %
                  (ins["va"], ins["bytes"], ins["mnemonic"], ins["operands"]))
        for edge in case["control_flow_edges"]:
            if edge["kind"] in (
                "direct_jump", "conditional_jump", "indirect_jump",
                "return", "trap", "leaves_case_decode_window",
                "fallthrough_reaches_static_jump_table_data",
            ):
                print("[K1D3D-CASES] EDGE %s %s -> %s" %
                      (edge["kind"], edge["from"], edge.get("to", edge.get("operand", ""))))
        for warning in case["hazards"]:
            print("[K1D3D-CASES] WARNING "+warning)
    print("[K1D3D-CASES] INSTRUCTION-BOUNDARY CHECK %s; warning_count=%d" %
          ("PASS" if every_case_lands_on_instruction_boundary else "UNPROVEN",
           len(set(errors))))
    print("[K1D3D-CASES] NO XDK BUILD. NO XEX CHANGED. NO 64-TU EDITS.")
    print("[K1D3D-CASES] Report: "+str(a.out))


def selftest() -> None:
    assert classify_static_slots(SIX_SOURCE_DESTINATIONS+(PADDING,))[
        "hardware_observed_case_index"] == 2
    assert classify_static_slots(SIX_SOURCE_DESTINATIONS+(PADDING,))[
        "exact_sha_original_pointer_slots"] == 6
    for bad in (
        SIX_SOURCE_DESTINATIONS,
        SIX_SOURCE_DESTINATIONS+(0x002965F0,),
        (0x002965A3,)*6+(PADDING,),
    ):
        try:
            classify_static_slots(bad)
        except ValueError:
            pass
        else:
            raise AssertionError("Invalid original table accepted")
    # Simulate a single XBE section in memory; prove no reads cross raw bounds.
    raw = bytes(range(128))
    assert bytes_at(raw, [(0, 0x2000, 128, 0, 128)], 0x200A, 3) == bytes((10,11,12))
    for pos, count in ((0x207F, 2), (0x1FFF, 4)):
        try:
            bytes_at(raw, [(0, 0x2000, 128, 0, 128)], pos, count)
        except ValueError:
            pass
        else:
            raise AssertionError("XBE VA read escaped section")
    # Independently test real x86 decode only when capstone is present;
    # full source CI installs Capstone explicitly.
    try:
        import capstone as cap
    except ImportError:
        print("[K1D3D-CASES] SELFTEST static mapping PASS; Capstone runtime test skipped (not installed)")
        return
    code = b"\x74\x01\xc3\xc3"  # jz+1; ret; ret
    fake_cs = cap.Cs(cap.CS_ARCH_X86, cap.CS_MODE_32)
    fake_cs.detail = True
    fake_entry = 0x0029655D
    padded = code + b"\xC3" * (CODE_STOP - CODE_FIRST - len(code))
    synthetic_sections = [(0, CODE_FIRST, len(padded), 0, len(padded))]
    result = decode_case(fake_cs, cap, padded, synthetic_sections, fake_entry)
    assert result["insn_count"] == 3
    assert not result["hazards"]
    assert any(x["kind"] == "conditional_jump" for x in result["control_flow_edges"])
    assert len([x for x in result["control_flow_edges"] if x["kind"] == "return"]) == 2
    print("[K1D3D-CASES] SELFTEST PASS: SHA/section guards, 6 entries + sentinel, real Capstone branch decode, no XDK")


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--xbe", type=Path)
    p.add_argument("--original-generated-c", type=Path)
    p.add_argument("--out", type=Path)
    args = p.parse_args()
    if args.self_test:
        selftest()
    else:
        if args.xbe is None or args.out is None:
            p.error("--xbe and --out required for original case machine-code audit")
        analyze(args)


if __name__ == "__main__":
    main()
