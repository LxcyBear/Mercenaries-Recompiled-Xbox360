#!/usr/bin/env python3
"""
Phase 3I composite translated slice preparation.

Lift a fixed set of already hardware-proven Mercenaries retail functions into
one local XDK fixture:
  0x00050010 -> direct CALL -> 0x0004CFF0
  0x001EF850 -> tail JMP   -> 0x0021AB90
  0x0008DE60 -> RECOMP_ICALL_SAFE through its real guest pointer slot

The generated retail bodies remain under build/ and are never committed.
"""

import argparse
import json
import os
import re
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.recomp import config
from tools.recomp.lifter import configure_guest_memory_abi
from tools.recomp.translator import BatchTranslator


DIRECT_CALLER = 0x00050010
SHARED_TARGET = 0x0004CFF0
TAIL_WRAPPER = 0x001EF850
TAIL_CALLEE = 0x0021AB90
ICALL_CALLER = 0x0008DE60

DIRECT_CALL_RE = re.compile(
    r"PUSH32\(esp,\s*0\);\s*"
    r"(?P<name>sub_(?P<addr>[0-9A-Fa-f]{8}))\(\);\s*"
    r"/\*\s*call 0x(?P=addr)\s*\*/",
    re.IGNORECASE,
)

ICALL_RE = re.compile(
    r"PUSH32\(esp,\s*0\);\s*"
    r"RECOMP_ICALL_SAFE\((?P<expr>.+?),\s*_icall_esp\);\s*"
    r"/\*\s*indirect call\s*\*/"
)

READ32_EXPR_RE = re.compile(
    r"^GUEST_READ32\(\s*(?P<reg>eax|ecx|edx|ebx|esi|edi)"
    r"(?:\s*\+\s*(?P<off>0x[0-9A-Fa-f]+|\d+))?\s*\)$"
)


def rename_function(source, old_name, new_name):
    out, count = re.subn(
        rf"\bvoid\s+{re.escape(old_name)}\s*\(\s*void\s*\)",
        f"static void {new_name}(void)",
        source,
        count=1,
    )
    if count != 1:
        raise RuntimeError(f"could not rename {old_name} -> {new_name}")
    return out


def require(condition, message):
    if not condition:
        raise SystemExit("[Phase3I] " + message)


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

    required_addrs = (
        DIRECT_CALLER,
        SHARED_TARGET,
        TAIL_WRAPPER,
        TAIL_CALLEE,
        ICALL_CALLER,
    )

    sources = {}
    names = {}
    infos = {}

    for addr in required_addrs:
        info = translator.func_db.get(addr)
        require(info is not None, f"required function 0x{addr:08X} missing")
        source = translator.translate_single(addr)
        require(source is not None, f"could not lift function 0x{addr:08X}")
        infos[addr] = info
        names[addr] = info["name"]
        sources[addr] = source

    # Direct CALL family: exact shape proven in 3G.
    direct_source = sources[DIRECT_CALLER]
    direct_target_name = names[SHARED_TARGET]
    direct_pattern = re.compile(
        rf"PUSH32\(esp,\s*0\);\s*{re.escape(direct_target_name)}\(\);\s*"
        rf"/\*\s*call 0x{SHARED_TARGET:08X}\s*\*/",
        re.IGNORECASE,
    )
    require(
        len(direct_pattern.findall(direct_source)) == 1,
        "0x00050010 no longer contains the expected direct CALL to 0x0004CFF0",
    )

    # Tail-call family: exact shapes proven in 3F.
    tail_wrapper_source = sources[TAIL_WRAPPER]
    tail_callee_source = sources[TAIL_CALLEE]
    tail_target_name = names[TAIL_CALLEE]

    require(
        re.search(
            rf"\b{re.escape(tail_target_name)}\(\);\s*return;\s*"
            rf"/\*\s*tail jmp 0x{TAIL_CALLEE:08X}\s*\*/",
            tail_wrapper_source,
            re.IGNORECASE,
        ) is not None,
        "0x001EF850 no longer has the expected tail jump to 0x0021AB90",
    )
    require(
        "recomp_xmm_loadss(xmm0v, esp + 4)" in tail_callee_source,
        "0x0021AB90 MOVSS guest-stack load shape changed",
    )
    require(
        "GUEST_WRITEF32(ecx + 0xDC, xmm0)" in tail_callee_source,
        "0x0021AB90 scalar guest store shape changed",
    )
    require(
        re.search(r"\besp\s*\+=\s*8\s*;\s*return;\s*/\*\s*ret 4\s*\*/",
                  tail_callee_source) is not None,
        "0x0021AB90 ret-4 shape changed",
    )

    # ICALL family: preserve exact 3H-B caller and discover its pointer slot.
    icall_source = sources[ICALL_CALLER]
    require(
        icall_source.count("RECOMP_ICALL_SAFE(") == 1,
        "0x0008DE60 no longer contains exactly one RECOMP_ICALL_SAFE",
    )
    icall_match = ICALL_RE.search(icall_source)
    require(icall_match is not None, "0x0008DE60 ICALL line shape changed")

    expr = icall_match.group("expr").strip()
    expr_match = READ32_EXPR_RE.fullmatch(expr)
    require(
        expr_match is not None,
        "0x0008DE60 no longer uses a simple GUEST_READ32 guest pointer slot",
    )

    slot_reg = expr_match.group("reg")
    slot_off = int(expr_match.group("off"), 0) if expr_match.group("off") else 0
    slot_expr = slot_reg if slot_off == 0 else f"{slot_reg} + 0x{slot_off:X}"

    discovery_source = rename_function(
        icall_source, names[ICALL_CALLER], "phase3i_discovery_caller")
    discovery_source, replaced = ICALL_RE.subn(
        lambda m: (
            f"phase3i_discovery_icall_slot((uint32_t)({slot_expr}), "
            f"_icall_esp); "
            f"/* Phase 3I discover real guest function-pointer slot */"
        ),
        discovery_source,
        count=1,
    )
    require(replaced == 1, "could not construct Phase 3I discovery caller")

    # The 3H caller may carry at most one already-bounded ordinary direct helper.
    direct_calls = list(DIRECT_CALL_RE.finditer(icall_source))
    helper_addr = None
    helper_name = None
    helper_source = None

    if direct_calls:
        require(
            len(direct_calls) == 1,
            "0x0008DE60 now contains more than one ordinary direct helper call",
        )
        helper_addr = int(direct_calls[0].group("addr"), 16)
        helper_name = direct_calls[0].group("name")

        if helper_addr not in required_addrs:
            helper_info = translator.func_db.get(helper_addr)
            require(helper_info is not None, "ICALL direct helper boundary missing")
            helper_source = translator.translate_single(helper_addr)
            require(helper_source is not None, "could not lift ICALL direct helper")
            require(
                "RECOMP_ICALL" not in helper_source and
                "RECOMP_ITAIL" not in helper_source and
                "tail jmp" not in helper_source and
                DIRECT_CALL_RE.search(helper_source) is None,
                "ICALL direct helper acquired another call dependency",
            )
            require(
                re.search(r"\bif\s*\(|\bgoto\s+loc_", helper_source)
                is None,
                "ICALL direct helper acquired branching control flow",
            )

    # Shared target must have one plain return and no additional call closure.
    target_source = sources[SHARED_TARGET]
    require(
        "RECOMP_ICALL" not in target_source and
        "RECOMP_ITAIL" not in target_source and
        "tail jmp" not in target_source,
        "shared target 0x0004CFF0 dependency shape changed",
    )
    require(
        re.search(r"\besp\s*\+=\s*4\s*;\s*return;\s*/\*\s*ret\s*\*/",
                  target_source) is not None,
        "shared target 0x0004CFF0 plain-RET shape changed",
    )

    target_impl = rename_function(
        target_source, names[SHARED_TARGET], "phase3i_shared_target_impl")

    generated = {
        f"{names[DIRECT_CALLER]}.c": direct_source,
        f"{names[SHARED_TARGET]}.c": target_source,
        f"{names[TAIL_WRAPPER]}.c": tail_wrapper_source,
        f"{names[TAIL_CALLEE]}.c": tail_callee_source,
        f"{names[ICALL_CALLER]}.c": icall_source,
        "discovery_caller.c": discovery_source,
        "shared_target_impl.c": target_impl,
    }
    if helper_source is not None:
        generated[f"{helper_name}.c"] = helper_source

    for filename, source in generated.items():
        (out_dir / filename).write_text(source + "\n", encoding="utf-8")

    selection = {
        "direct_caller": f"0x{DIRECT_CALLER:08X}",
        "direct_caller_name": names[DIRECT_CALLER],
        "shared_target": f"0x{SHARED_TARGET:08X}",
        "shared_target_name": names[SHARED_TARGET],
        "tail_wrapper": f"0x{TAIL_WRAPPER:08X}",
        "tail_wrapper_name": names[TAIL_WRAPPER],
        "tail_callee": f"0x{TAIL_CALLEE:08X}",
        "tail_callee_name": names[TAIL_CALLEE],
        "icall_caller": f"0x{ICALL_CALLER:08X}",
        "icall_caller_name": names[ICALL_CALLER],
        "icall_expression": expr,
        "pointer_slot_expression": slot_expr,
        "icall_direct_helper": (
            f"0x{helper_addr:08X}" if helper_addr is not None else None),
        "icall_direct_helper_name": helper_name,
        "function_count": len(required_addrs) + (
            1 if helper_source is not None else 0),
    }
    (out_dir / "selection.json").write_text(
        json.dumps(selection, indent=2) + "\n", encoding="utf-8")

    template = Path(args.template).read_text(encoding="utf-8")
    replacements = {
        "/*__P3I_SHARED_TARGET_IMPL__*/": target_impl,
        "/*__P3I_DIRECT_CALLER__*/": direct_source,
        "/*__P3I_TAIL_CALLEE__*/": tail_callee_source,
        "/*__P3I_TAIL_WRAPPER__*/": tail_wrapper_source,
        "/*__P3I_ICALL_HELPER__*/": (
            helper_source if helper_source is not None
            else "/* no additional ICALL direct helper */"),
        "/*__P3I_DISCOVERY_CALLER__*/": discovery_source,
        "/*__P3I_ICALL_CALLER__*/": icall_source,
        "__P3I_SHARED_TARGET_NAME__": names[SHARED_TARGET],
        "__P3I_DIRECT_CALLER_NAME__": names[DIRECT_CALLER],
        "__P3I_TAIL_WRAPPER_NAME__": names[TAIL_WRAPPER],
        "__P3I_ICALL_CALLER_NAME__": names[ICALL_CALLER],
    }

    for token, value in replacements.items():
        require(token in template, f"template token missing: {token}")
        template = template.replace(token, value)

    Path(args.main_out).write_text(template, encoding="utf-8")

    print("[Phase3I] READY")
    print(
        f"[Phase3I] Direct chain: 0x{DIRECT_CALLER:08X} -> "
        f"0x{SHARED_TARGET:08X}")
    print(
        f"[Phase3I] Tail chain:   0x{TAIL_WRAPPER:08X} -> "
        f"0x{TAIL_CALLEE:08X}")
    print(
        f"[Phase3I] ICALL root:   0x{ICALL_CALLER:08X}, "
        f"operand={expr}")
    print(f"[Phase3I] Pointer slot expression: {slot_expr}")
    if helper_addr is not None:
        print(
            f"[Phase3I] ICALL direct helper: {helper_name} "
            f"@ 0x{helper_addr:08X}")
    else:
        print("[Phase3I] ICALL direct helper: none")
    print(
        f"[Phase3I] Real translated functions in slice: "
        f"{selection['function_count']}")
    print(f"[Phase3I] XDK source: {args.main_out}")


if __name__ == "__main__":
    main()
