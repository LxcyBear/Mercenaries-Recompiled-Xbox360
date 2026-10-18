#!/usr/bin/env python3
"""
Select and prepare the first bounded real translated Mercenaries direct-CALL
chain for Xbox 360 Phase 3G.

The selector consumes the already-reviewed disassembler functions.json, chooses
one tiny caller -> callee pair connected by an actual x86 CALL, lifts both with
the explicit guest-memory ABI, applies strict isolation guards, and emits:
  - the unmodified translated caller
  - a renamed translated callee implementation
  - a reference caller whose generated PUSH32 call is replaced by an
    independent explicit guest return-slot write
  - a combined XDK main.cpp from the committed template

No retail-derived generated C is committed to the repository.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

from tools.recomp import config
from tools.recomp.lifter import configure_guest_memory_abi
from tools.recomp.translator import BatchTranslator


FORBIDDEN = re.compile(
    r"\b(?:"
    r"RECOMP_ICALL(?:_SAFE)?|RECOMP_ITAIL|RECOMP_RDTSC|"
    r"XBOX_MEMCPY|XBOX_REP_MOVS|xbox_[A-Za-z0-9_]+|__debugbreak|"
    r"g_seh_ebp|"
    r"xmm[0-7]|xmm[0-7]v|g_xmm[0-7]|"
    r"mm[0-7]|g_mm[0-7]|"
    r"fp_push|fp_pop|fp_top|fp_st|"
    r"GUEST_READF32|GUEST_READF64|GUEST_WRITEF32|GUEST_WRITEF64|"
    r"recomp_xmm_[A-Za-z0-9_]+"
    r")\b"
)

ALLOWED_CALLS = {
    "if", "while", "switch",
    "RECOMP_TRACE_FUNC",
    "GUEST_READ8", "GUEST_READ16", "GUEST_READ32", "GUEST_READ64",
    "GUEST_SREAD8", "GUEST_SREAD16", "GUEST_SREAD32", "GUEST_SREAD64",
    "GUEST_WRITE8", "GUEST_WRITE16", "GUEST_WRITE32", "GUEST_WRITE64",
    "RECOMP_READ8", "RECOMP_READ16", "RECOMP_READ32", "RECOMP_READ64",
    "RECOMP_WRITE8", "RECOMP_WRITE16", "RECOMP_WRITE32", "RECOMP_WRITE64",
    "PUSH32", "POP32",
    "LO8", "HI8", "LO16", "SET_LO8", "SET_HI8", "SET_LO16",
    "SX8", "SX16", "BSWAP32",
}

CALL_TOKEN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
PLAIN_RET = re.compile(r"\besp\s*\+=\s*4\s*;\s*return\s*;\s*/\*\s*ret\s*\*/")
ESP_WRITE = re.compile(r"\besp\s*(?:=|\+=|-=)")
TRANSLATED_CALL = re.compile(r"\bsub_[0-9A-Fa-f]{8}\s*\(")


def parse_addr(value):
    if isinstance(value, int):
        return value
    return int(value, 16)


def clean_name(info, addr):
    expected = f"sub_{addr:08X}"
    return info.get("name", "") == expected


def helper_surface_ok(source, own_name, callee_name=None):
    if FORBIDDEN.search(source):
        return False, "forbidden runtime/SIMD/SEH dependency"

    allowed = set(ALLOWED_CALLS)
    allowed.add(own_name)
    if callee_name:
        allowed.add(callee_name)

    unknown = []
    for name in CALL_TOKEN.findall(source):
        if name not in allowed:
            unknown.append(name)
    if unknown:
        return False, "unknown helper(s): " + ", ".join(sorted(set(unknown))[:8])
    return True, ""


def stack_shape_ok(source, direct_call_line=None, is_caller=False):
    lines = source.splitlines()

    if "POP32(" in source:
        return False, "POP32 present"

    if is_caller:
        if source.count("PUSH32(") != 1:
            return False, f"caller PUSH32 count is {source.count('PUSH32(')}, expected 1"
    elif "PUSH32(" in source:
        return False, "callee PUSH32 present"

    plain_ret_count = len(PLAIN_RET.findall(source))
    if plain_ret_count == 0:
        return False, "no plain RET translation"

    # Every translated RET in this first CALL-chain fixture must be plain RET,
    # not RET N. This keeps expected final ESP exact and independent.
    ret_comments = re.findall(r"/\*\s*ret(?:\s+\d+)?\s*\*/", source)
    if len(ret_comments) != plain_ret_count:
        return False, "RET N or unsupported RET shape present"

    if is_caller and direct_call_line is not None:
        try:
            call_idx = next(i for i, line in enumerate(lines)
                            if direct_call_line.search(line))
        except StopIteration:
            return False, "direct call line missing"

        # The actual x86 CALL must be unconditionally reached from function
        # entry in this first bounded fixture.
        pre = "\n".join(lines[:call_idx])
        if re.search(r"\bif\s*\(|\bgoto\s+loc_|\breturn\s*;", pre):
            return False, "branch/return before direct CALL"

        # No translated caller stack mutation before the CALL. The one guest
        # stack change under test is precisely the generated synthetic push.
        for line in lines[:call_idx]:
            if ESP_WRITE.search(line):
                return False, "caller modifies ESP before direct CALL"

    # Outside the direct call PUSH itself, only plain RET's esp += 4 is allowed.
    for line in lines:
        stripped = line.strip()
        if direct_call_line is not None and direct_call_line.search(line):
            continue
        if PLAIN_RET.search(line):
            continue
        if ESP_WRITE.search(line):
            return False, "unexpected ESP mutation: " + stripped

    return True, ""


def candidate_sources(translator, caller_addr, callee_addr):
    caller = translator.translate_single(caller_addr)
    callee = translator.translate_single(callee_addr)
    if not caller or not callee:
        return None, None
    return caller, callee


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--xbe", required=True)
    ap.add_argument("--disasm-dir", required=True)
    ap.add_argument("--out-dir", required=True)
    ap.add_argument("--template", required=True)
    ap.add_argument("--main-out", required=True)
    args = ap.parse_args()

    xbe = os.path.abspath(args.xbe)
    disasm_dir = os.path.abspath(args.disasm_dir)
    out_dir = Path(args.out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    functions_path = os.path.join(disasm_dir, "functions.json")
    labels_path = os.path.join(disasm_dir, "labels.json")
    if not os.path.isfile(functions_path):
        raise SystemExit(f"functions.json not found: {functions_path}")

    configure_guest_memory_abi(True)
    config.configure_from_xbe(xbe)

    translator = BatchTranslator(
        xbe_path=xbe,
        func_json_path=functions_path,
        labels_json_path=labels_path if os.path.isfile(labels_path) else None,
        identified_json_path=None,
        abi_json_path=None,
        output_dir=str(out_dir),
        discover_entry_splits=False,
    )

    funcs = translator.func_db
    rejected = Counter()
    candidates = []

    for caller_addr, caller_info in funcs.items():
        if not clean_name(caller_info, caller_addr):
            continue

        caller_size = int(caller_info.get("size", 0))
        caller_insns = int(caller_info.get("num_instructions", 999999) or 999999)
        if not (5 <= caller_size <= 96 and caller_insns <= 28):
            continue

        calls_to = sorted(set(parse_addr(x) for x in caller_info.get("calls_to", [])))
        if len(calls_to) != 1:
            continue

        callee_addr = calls_to[0]
        callee_info = funcs.get(callee_addr)
        if not callee_info or not clean_name(callee_info, callee_addr):
            continue

        callee_size = int(callee_info.get("size", 0))
        callee_insns = int(callee_info.get("num_instructions", 999999) or 999999)
        if not (1 <= callee_size <= 96 and callee_insns <= 28):
            continue

        if callee_info.get("calls_to"):
            continue

        candidates.append((
            caller_size + callee_size,
            caller_insns + callee_insns,
            caller_addr,
            callee_addr,
        ))

    candidates.sort()

    selected = None
    for _, _, caller_addr, callee_addr in candidates[:400]:
        caller_info = funcs[caller_addr]
        callee_info = funcs[callee_addr]
        caller_name = caller_info["name"]
        callee_name = callee_info["name"]

        try:
            caller_src, callee_src = candidate_sources(
                translator, caller_addr, callee_addr)
        except Exception as exc:
            rejected["lift exception"] += 1
            continue

        if not caller_src or not callee_src:
            rejected["lift failed"] += 1
            continue

        call_line = re.compile(
            rf"PUSH32\(esp,\s*0\);\s*{re.escape(callee_name)}\(\);\s*"
            rf"/\*\s*call 0x{callee_addr:08X}\s*\*/",
            re.IGNORECASE,
        )
        if len(call_line.findall(caller_src)) != 1:
            rejected["not exactly one generated normal CALL"] += 1
            continue

        if "tail jmp" in caller_src or "tail jmp" in callee_src:
            rejected["tail jump present"] += 1
            continue

        ok, why = helper_surface_ok(caller_src, caller_name, callee_name)
        if not ok:
            rejected["caller " + why] += 1
            continue

        ok, why = helper_surface_ok(callee_src, callee_name)
        if not ok:
            rejected["callee " + why] += 1
            continue

        ok, why = stack_shape_ok(
            caller_src, direct_call_line=call_line, is_caller=True)
        if not ok:
            rejected["caller stack: " + why] += 1
            continue

        ok, why = stack_shape_ok(callee_src, is_caller=False)
        if not ok:
            rejected["callee stack: " + why] += 1
            continue

        # No third translated calls may survive either generated body.
        caller_subs = set(
            m.group(0).split("(")[0].strip()
            for m in TRANSLATED_CALL.finditer(caller_src)
        )
        caller_subs.discard(caller_name)
        caller_subs.discard(callee_name)
        if caller_subs:
            rejected["third translated caller dependency"] += 1
            continue

        callee_subs = set(
            m.group(0).split("(")[0].strip()
            for m in TRANSLATED_CALL.finditer(callee_src)
        )
        callee_subs.discard(callee_name)
        if callee_subs:
            rejected["translated callee dependency"] += 1
            continue

        # Keep this first normal-CALL fixture compact.
        if len(caller_src.splitlines()) > 180 or len(callee_src.splitlines()) > 160:
            rejected["generated body too large"] += 1
            continue

        selected = (
            caller_addr, callee_addr, caller_info, callee_info,
            caller_src, callee_src, call_line,
        )
        break

    if selected is None:
        print("[Phase3G] NO SAFE DIRECT-CALL CANDIDATE FOUND")
        print(f"[Phase3G] Metadata candidates considered: {len(candidates)}")
        for reason, count in rejected.most_common(12):
            print(f"[Phase3G] reject {count:3d}: {reason}")
        raise SystemExit(2)

    (caller_addr, callee_addr, caller_info, callee_info,
     caller_src, callee_src, call_line) = selected

    caller_name = caller_info["name"]
    callee_name = callee_info["name"]

    callee_impl_src = re.sub(
        rf"\bvoid\s+{re.escape(callee_name)}\s*\(\s*void\s*\)",
        "static void phase3g_callee_impl(void)",
        callee_src,
        count=1,
    )

    reference_src = re.sub(
        rf"\bvoid\s+{re.escape(caller_name)}\s*\(\s*void\s*\)",
        "static void phase3g_reference_caller(void)",
        caller_src,
        count=1,
    )
    reference_src, replaced = call_line.subn(
        "phase3g_reference_call(); "
        "/* Phase 3G independent explicit guest return-slot reference */",
        reference_src,
        count=1,
    )
    if replaced != 1:
        raise SystemExit("failed to build Phase 3G reference caller")

    caller_path = out_dir / f"{caller_name}.c"
    callee_path = out_dir / f"{callee_name}.c"
    callee_impl_path = out_dir / "callee_impl.c"
    reference_path = out_dir / "reference_caller.c"
    selection_path = out_dir / "selection.json"

    caller_path.write_text(caller_src + "\n", encoding="utf-8")
    callee_path.write_text(callee_src + "\n", encoding="utf-8")
    callee_impl_path.write_text(callee_impl_src + "\n", encoding="utf-8")
    reference_path.write_text(reference_src + "\n", encoding="utf-8")

    selection = {
        "caller": f"0x{caller_addr:08X}",
        "callee": f"0x{callee_addr:08X}",
        "caller_name": caller_name,
        "callee_name": callee_name,
        "caller_size": int(caller_info.get("size", 0)),
        "callee_size": int(callee_info.get("size", 0)),
        "caller_instructions": int(caller_info.get("num_instructions", 0) or 0),
        "callee_instructions": int(callee_info.get("num_instructions", 0) or 0),
        "reference_model": "manual GUEST_WRITE32(ESP-4, 0), set ESP, invoke translated callee",
    }
    selection_path.write_text(json.dumps(selection, indent=2) + "\n", encoding="utf-8")

    template = Path(args.template).read_text(encoding="utf-8")
    replacements = {
        "/*__PHASE3G_CALLEE_IMPL__*/": callee_impl_src,
        "/*__PHASE3G_REFERENCE_CALLER__*/": reference_src,
        "/*__PHASE3G_REAL_CALLER__*/": caller_src,
        "__PHASE3G_CALLER_NAME__": caller_name,
        "__PHASE3G_CALLEE_NAME__": callee_name,
        "__PHASE3G_CALLER_VA__": f"0x{caller_addr:08X}u",
        "__PHASE3G_CALLEE_VA__": f"0x{callee_addr:08X}u",
        "__PHASE3G_CALLER_VA_TEXT__": f"0x{caller_addr:08X}",
        "__PHASE3G_CALLEE_VA_TEXT__": f"0x{callee_addr:08X}",
    }
    for key, value in replacements.items():
        if key not in template:
            raise SystemExit(f"template token missing: {key}")
        template = template.replace(key, value)

    Path(args.main_out).write_text(template, encoding="utf-8")

    print("[Phase3G] SELECTED")
    print(
        f"[Phase3G] Caller: {caller_name} @ 0x{caller_addr:08X} "
        f"({caller_info.get('size')} bytes / "
        f"{caller_info.get('num_instructions')} insns)"
    )
    print(
        f"[Phase3G] Callee: {callee_name} @ 0x{callee_addr:08X} "
        f"({callee_info.get('size')} bytes / "
        f"{callee_info.get('num_instructions')} insns)"
    )
    print("[Phase3G] Generated normal CALL shape verified: PUSH32(esp, 0); callee();")
    print("[Phase3G] Caller/callee plain-RET stack shape verified")
    print("[Phase3G] No indirect/tail/kernel/SIMD/x87 dependency survived")
    print(f"[Phase3G] Selection JSON: {selection_path}")
    print(f"[Phase3G] XDK source:     {args.main_out}")


if __name__ == "__main__":
    main()
