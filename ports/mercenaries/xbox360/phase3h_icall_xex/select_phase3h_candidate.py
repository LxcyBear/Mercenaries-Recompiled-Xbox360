#!/usr/bin/env python3
"""
Phase 3H: select one bounded real Mercenaries RECOMP_ICALL_SAFE site.

The chosen caller remains mechanically translated. The selector only accepts a
linear, stack-simple site whose indirect target expression can be deterministically
seeded to the already hardware-proven translated function 0x0004CFF0.

Generated retail-derived C remains local under build/.
"""

import argparse
import json
import os
import re
import sys
from collections import Counter
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parents[4]
if str(REPO_ROOT) not in sys.path:
    sys.path.insert(0, str(REPO_ROOT))

from tools.recomp import config
from tools.recomp.lifter import configure_guest_memory_abi
from tools.recomp.translator import BatchTranslator


TARGET_VA = 0x0004CFF0
PREFERRED_CALLERS = [0x00034AE0]

ICALL_RE = re.compile(
    r"PUSH32\(esp,\s*0\);\s*"
    r"RECOMP_ICALL_SAFE\((?P<expr>.+?),\s*_icall_esp\);\s*"
    r"/\*\s*indirect call\s*\*/"
)

PLAIN_RET_RE = re.compile(
    r"\besp\s*\+=\s*4\s*;\s*return\s*;\s*/\*\s*ret\s*\*/"
)

FORBIDDEN = re.compile(
    r"\b(?:"
    r"RECOMP_ITAIL|RECOMP_RDTSC|XBOX_MEMCPY|XBOX_REP_MOVS|"
    r"xbox_[A-Za-z0-9_]+|__debugbreak|"
    r"xmm[0-7]|xmm[0-7]v|g_xmm[0-7]|"
    r"mm[0-7]|g_mm[0-7]|"
    r"fp_push|fp_pop|fp_top|fp_st|"
    r"GUEST_READF32|GUEST_READF64|GUEST_WRITEF32|GUEST_WRITEF64|"
    r"recomp_xmm_[A-Za-z0-9_]+|"
    r"cf|zf|sf|of|pf|af|eflags|g_eflags"
    r")\b"
)

CALL_TOKEN = re.compile(r"\b([A-Za-z_][A-Za-z0-9_]*)\s*\(")
TRANSLATED_CALL = re.compile(r"\bsub_[0-9A-Fa-f]{8}\s*\(")

ALLOWED_CALLS = {
    "if", "while", "switch",
    "RECOMP_TRACE_FUNC",
    "RECOMP_ICALL_SAFE",
    "GUEST_READ8", "GUEST_READ16", "GUEST_READ32", "GUEST_READ64",
    "GUEST_SREAD8", "GUEST_SREAD16", "GUEST_SREAD32", "GUEST_SREAD64",
    "GUEST_WRITE8", "GUEST_WRITE16", "GUEST_WRITE32", "GUEST_WRITE64",
    "RECOMP_READ8", "RECOMP_READ16", "RECOMP_READ32", "RECOMP_READ64",
    "RECOMP_WRITE8", "RECOMP_WRITE16", "RECOMP_WRITE32", "RECOMP_WRITE64",
    "PUSH32", "POP32",
    "LO8", "HI8", "LO16", "SET_LO8", "SET_HI8", "SET_LO16",
    "SX8", "SX16", "BSWAP32",
}

REGS = ("eax", "ecx", "edx", "ebx", "esi", "edi")

DIRECT_REG_RE = re.compile(r"^(eax|ecx|edx|ebx|esi|edi)$")
READ32_REG_RE = re.compile(
    r"^GUEST_READ32\(\s*(eax|ecx|edx|ebx|esi|edi)"
    r"(?:\s*\+\s*(0x[0-9A-Fa-f]+|\d+))?\s*\)$"
)


def parse_addr(value):
    if isinstance(value, int):
        return value
    return int(value, 16)


def helper_surface_ok(source, own_name):
    if FORBIDDEN.search(source):
        return False, "forbidden SIMD/flags/runtime dependency"

    unknown = []
    allowed = set(ALLOWED_CALLS)
    allowed.add(own_name)
    for name in CALL_TOKEN.findall(source):
        if name not in allowed:
            unknown.append(name)
    if unknown:
        return False, "unknown helper(s): " + ", ".join(sorted(set(unknown))[:8])
    return True, ""


def parse_seed(expr, pre_call_source):
    expr = expr.strip()

    m = DIRECT_REG_RE.fullmatch(expr)
    if m:
        reg = m.group(1)
        seed = f"g_{reg} = s_seedTargetVa;"
    else:
        m = READ32_REG_RE.fullmatch(expr)
        if not m:
            return None, "ICALL target expression is not a simple seedable register/read32"

        reg = m.group(1)
        offset_text = m.group(2)
        offset = int(offset_text, 0) if offset_text else 0
        seed = (
            f"g_{reg} = ICALL_TARGET_SLOT_BASE;\n"
            f"    GUEST_WRITE32(ICALL_TARGET_SLOT_BASE + 0x{offset:X}u, "
            f"DISPATCH_TARGET_VA);"
        )

    # The seeded register must reach the ICALL unchanged. This first 3H proof
    # deliberately avoids symbolic execution of a pointer-building prefix.
    assign_patterns = [
        rf"\b{reg}\s*=",
        rf"\bSET_(?:LO8|HI8|LO16)\s*\(\s*{reg}\b",
        rf"\bPOP32\s*\(\s*esp\s*,\s*{reg}\s*\)",
    ]
    for pat in assign_patterns:
        if re.search(pat, pre_call_source):
            return None, f"ICALL target base register {reg} is modified before call"

    return seed, ""


def linear_icall_candidate(source, own_name):
    if source.count("RECOMP_ICALL_SAFE(") != 1:
        return None, "not exactly one RECOMP_ICALL_SAFE"

    if "RECOMP_ICALL(" in source.replace("RECOMP_ICALL_SAFE", ""):
        return None, "additional non-safe ICALL present"

    if "tail jmp" in source:
        return None, "tail jump present"

    if re.search(r"\bif\s*\(|\bgoto\s+loc_", source):
        return None, "branching control flow present"

    if TRANSLATED_CALL.search(source):
        return None, "direct translated call present"

    ok, why = helper_surface_ok(source, own_name)
    if not ok:
        return None, why

    match = ICALL_RE.search(source)
    if not match:
        return None, "generated ICALL line shape not recognized"

    call_start = match.start()
    pre = source[:call_start]

    # Require the translator's stack-safe save block and no guest argument
    # pushes before the dummy return slot. That lets the known plain-RET target
    # return exactly to saved_esp.
    saves = list(re.finditer(
        r"\{\s*uint32_t\s+_icall_esp\s*=\s*g_esp\s*;", source))
    if len(saves) != 1 or saves[0].start() > call_start:
        return None, "missing unique pre-call _icall_esp save"

    block_pre = source[saves[0].end():call_start]
    if "PUSH32(" in block_pre:
        return None, "ICALL pushes guest arguments before dummy return slot"

    # Keep all other stack behavior out of this first ICALL fixture.
    without_icall = source[:match.start()] + source[match.end():]
    if "PUSH32(" in without_icall or "POP32(" in without_icall:
        return None, "other PUSH32/POP32 stack traffic present"

    ret_comments = re.findall(r"/\*\s*ret(?:\s+\d+)?\s*\*/", source)
    plain_rets = PLAIN_RET_RE.findall(source)
    if len(ret_comments) != 1 or len(plain_rets) != 1:
        return None, "caller does not have exactly one plain RET"

    # No ESP mutation besides the generated call push (inside matched text)
    # and the final plain RET.
    scrubbed = source[:match.start()] + source[match.end():]
    scrubbed = PLAIN_RET_RE.sub("", scrubbed)
    if re.search(r"\besp\s*(?:=|\+=|-=)", scrubbed):
        return None, "unexpected caller ESP mutation"

    if "g_seh_ebp" in source:
        return None, "SEH/EBP bridge dependency present"

    seed, why = parse_seed(match.group("expr"), pre)
    if not seed:
        return None, why

    return {
        "expr": match.group("expr").strip(),
        "seed_code": seed,
        "match": match,
    }, ""


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

    funcs = translator.func_db
    target_info = funcs.get(TARGET_VA)
    if not target_info:
        raise SystemExit(f"known Phase 3G target 0x{TARGET_VA:08X} is missing")

    target_name = target_info["name"]
    target_src = translator.translate_single(TARGET_VA)
    if not target_src:
        raise SystemExit("could not lift Phase 3G translated target")

    # Preserve the already-proven target constraints.
    if (target_src.count("PUSH32(") or target_src.count("POP32(") or
            "RECOMP_ICALL" in target_src or "tail jmp" in target_src or
            len(PLAIN_RET_RE.findall(target_src)) != 1):
        raise SystemExit("Phase 3G target no longer has the expected plain-RET shape")

    target_ok, target_why = helper_surface_ok(target_src, target_name)
    if not target_ok:
        raise SystemExit("Phase 3G target dependency changed: " + target_why)

    ordered = []
    seen = set()

    for addr in PREFERRED_CALLERS:
        if addr in funcs:
            ordered.append(addr)
            seen.add(addr)

    for addr, info in sorted(
        funcs.items(),
        key=lambda item: (
            int(item[1].get("size", 1 << 30)),
            int(item[1].get("num_instructions", 1 << 30) or (1 << 30)),
            item[0],
        ),
    ):
        if addr in seen:
            continue
        size = int(info.get("size", 0))
        insns = int(info.get("num_instructions", 999999) or 999999)
        if 5 <= size <= 160 and insns <= 48:
            ordered.append(addr)

    rejected = Counter()
    selected = None
    scanned = 0

    for caller_addr in ordered[:1600]:
        info = funcs[caller_addr]
        name = info["name"]
        if name != f"sub_{caller_addr:08X}":
            continue

        try:
            src = translator.translate_single(caller_addr)
        except Exception:
            rejected["lift exception"] += 1
            continue

        scanned += 1
        if not src or "RECOMP_ICALL_SAFE(" not in src:
            continue

        details, why = linear_icall_candidate(src, name)
        if not details:
            rejected[why] += 1
            continue

        selected = (caller_addr, info, src, details)
        break

    if selected is None:
        print("[Phase3H] NO SAFE ICALL CANDIDATE FOUND")
        print(f"[Phase3H] Lifted/scanned functions: {scanned}")
        for reason, count in rejected.most_common(14):
            print(f"[Phase3H] reject {count:3d}: {reason}")
        raise SystemExit(2)

    caller_addr, caller_info, caller_src, details = selected
    caller_name = caller_info["name"]

    # Build the reference caller from the exact translated caller, replacing
    # only the generated PUSH32+RECOMP_ICALL_SAFE operation.
    reference_src = rename_function(
        caller_src, caller_name, "phase3h_reference_caller")

    reference_re = ICALL_RE
    reference_src, replaced = reference_re.subn(
        lambda m: (
            f"phase3h_reference_icall((uint32_t)({m.group('expr')}), "
            f"_icall_esp); "
            f"/* Phase 3H independent indirect-call reference */"
        ),
        reference_src,
        count=1,
    )
    if replaced != 1:
        raise SystemExit("failed to construct Phase 3H reference caller")

    target_impl_src = rename_function(
        target_src, target_name, "phase3h_target_impl")

    paths = {
        "caller": out_dir / f"{caller_name}.c",
        "reference": out_dir / "reference_caller.c",
        "target": out_dir / f"{target_name}.c",
        "target_impl": out_dir / "target_impl.c",
    }
    paths["caller"].write_text(caller_src + "\n", encoding="utf-8")
    paths["reference"].write_text(reference_src + "\n", encoding="utf-8")
    paths["target"].write_text(target_src + "\n", encoding="utf-8")
    paths["target_impl"].write_text(target_impl_src + "\n", encoding="utf-8")

    selection = {
        "caller": f"0x{caller_addr:08X}",
        "caller_name": caller_name,
        "caller_size": int(caller_info.get("size", 0)),
        "caller_instructions": int(caller_info.get("num_instructions", 0) or 0),
        "icall_expression": details["expr"],
        "dispatch_target": f"0x{TARGET_VA:08X}",
        "dispatch_target_name": target_name,
        "dispatch_target_size": int(target_info.get("size", 0)),
        "dispatch_target_instructions": int(
            target_info.get("num_instructions", 0) or 0),
    }
    (out_dir / "selection.json").write_text(
        json.dumps(selection, indent=2) + "\n", encoding="utf-8")

    template = Path(args.template).read_text(encoding="utf-8")
    replacements = {
        "/*__PHASE3H_TARGET_IMPL__*/": target_impl_src,
        "/*__PHASE3H_REFERENCE_CALLER__*/": reference_src,
        "/*__PHASE3H_REAL_CALLER__*/": caller_src,
        "__PHASE3H_CALLER_NAME__": caller_name,
        "__PHASE3H_TARGET_NAME__": target_name,
        "__PHASE3H_CALLER_VA__": f"0x{caller_addr:08X}u",
        "__PHASE3H_TARGET_VA__": f"0x{TARGET_VA:08X}u",
        "__PHASE3H_CALLER_VA_TEXT__": f"0x{caller_addr:08X}",
        "__PHASE3H_TARGET_VA_TEXT__": f"0x{TARGET_VA:08X}",
        "/*__PHASE3H_TARGET_SEED__*/": details["seed_code"],
    }
    for key, value in replacements.items():
        if key not in template:
            raise SystemExit(f"template token missing: {key}")
        template = template.replace(key, value)

    Path(args.main_out).write_text(template, encoding="utf-8")

    print("[Phase3H] SELECTED")
    print(
        f"[Phase3H] Caller: {caller_name} @ 0x{caller_addr:08X} "
        f"({caller_info.get('size')} bytes / "
        f"{caller_info.get('num_instructions')} insns)")
    print(f"[Phase3H] ICALL expression: {details['expr']}")
    print(
        f"[Phase3H] Dispatch target: {target_name} @ 0x{TARGET_VA:08X} "
        f"({target_info.get('size')} bytes / "
        f"{target_info.get('num_instructions')} insns)")
    print("[Phase3H] Generated RECOMP_ICALL_SAFE shape verified")
    print("[Phase3H] No guest arguments are pushed before the dummy return slot")
    print("[Phase3H] Caller is linear, flag-free, plain-RET and stack-simple")
    print("[Phase3H] XDK source: " + args.main_out)


if __name__ == "__main__":
    main()
