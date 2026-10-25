#!/usr/bin/env python3
"""Phase 6CL: trace every guest READ32 after XACT block 0x002832CA begins.

6CK hardware proved:
  * all six probe blocks are hit exactly once;
  * ECX is still 0 at loc_002832CA;
  * the next boundary is READ32 FFFFFFFF with ECX=FFFFFFFF.

Therefore the invalid value is produced inside/after the 002832CA block, not
carried into it. 6CL keeps 6CJ semantics and instruments the central
recomp_guest_read32 helper, gated off until loc_002832CA. This captures the
address/value chain of every 32-bit guest read leading directly to the fault.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CJ-MM166-GENERAL-TAIL-20261025-A"
BUILD_TAG = "P6CL-XACT-READ32-CHAIN-20261025-A"
COOKIE_OLD = "phase6cj_env_build_cookie"
COOKIE_NEW = "phase6cl_env_build_cookie"
ARM_VA = 0x002832CA


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CL] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CL] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def block_window(text: str, va: int) -> str:
    marker = f"loc_{va:08X}: ;\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"[Phase6CL] source label missing: {marker.strip()}")
    next_match = re.search(r"\nloc_[0-9A-Fa-f]{8}: ;\n", text[start + len(marker):])
    if next_match:
        end = start + len(marker) + next_match.start() + 1
    else:
        end = min(len(text), start + 7000)
    return text[start:end]


def matching_brace(text: str, open_pos: int) -> int:
    depth = 0
    in_string = False
    quote = ""
    escape = False
    i = open_pos
    while i < len(text):
        ch = text[i]
        if in_string:
            if escape:
                escape = False
            elif ch == "\\":
                escape = True
            elif ch == quote:
                in_string = False
        else:
            if ch in ('"', "'"):
                in_string = True
                quote = ch
            elif ch == "{":
                depth += 1
            elif ch == "}":
                depth -= 1
                if depth == 0:
                    return i
        i += 1
    raise SystemExit("[Phase6CL] unterminated recomp_guest_read32 body")


def wrap_read32(text: str) -> str:
    signature = "uint32_t recomp_guest_read32(uint32_t address)"
    definition_re = re.compile(
        r"(?m)^uint32_t\\s+recomp_guest_read32\\(uint32_t address\\)\\s*\\{"
    )
    matches = list(definition_re.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6CL] expected one recomp_guest_read32 definition, "
            f"found {len(matches)}"
        )

    start = matches[0].start()
    open_pos = text.find("{", matches[0].start(), matches[0].end() + 1)
    if open_pos < 0:
        raise SystemExit("[Phase6CL] recomp_guest_read32 definition brace missing")
    close_pos = matching_brace(text, open_pos)
    original = text[start:close_pos + 1]

    renamed = original.replace(
        signature,
        "static uint32_t phase6cl_inherited_guest_read32(uint32_t address)",
        1,
    )

    wrapper = r"""
static DWORD s_phase6clReadTraceActive = 0u;
static DWORD s_phase6clReadTraceSeq = 0u;
static DWORD s_phase6clReadTraceLastAddr = 0u;
static DWORD s_phase6clReadTraceLastValue = 0u;
static DWORD s_phase6clReadTraceFaultAddr = 0u;
static void trace(const char* line);

uint32_t recomp_guest_read32(uint32_t address)
{
    uint32_t value;
    DWORD seq = 0u;

    if (s_phase6clReadTraceActive)
    {
        char line[640];
        seq = ++s_phase6clReadTraceSeq;
        s_phase6clReadTraceLastAddr = address;

        if (seq <= 32u)
        {
            sprintf(
                line,
                "P6CL READ32 PRE seq=%u addr=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
                (unsigned int)seq,
                (unsigned int)address,
                (unsigned int)g_eax,
                (unsigned int)g_ecx,
                (unsigned int)g_edx,
                (unsigned int)g_ebx,
                (unsigned int)g_esi,
                (unsigned int)g_edi,
                (unsigned int)g_esp);
            trace(line);
        }
    }

    value = phase6cl_inherited_guest_read32(address);

    if (s_phase6clReadTraceActive)
    {
        char line[640];

        if (s_accessFault)
        {
            s_phase6clReadTraceFaultAddr = address;
            sprintf(
                line,
                "P6CL READ32 INVALID seq=%u addr=%08X returned=%08X eax=%08X ecx=%08X edx=%08X esi=%08X edi=%08X",
                (unsigned int)seq,
                (unsigned int)address,
                (unsigned int)value,
                (unsigned int)g_eax,
                (unsigned int)g_ecx,
                (unsigned int)g_edx,
                (unsigned int)g_esi,
                (unsigned int)g_edi);
            trace(line);
        }
        else
        {
            s_phase6clReadTraceLastValue = value;
            if (seq <= 32u)
            {
                sprintf(
                    line,
                    "P6CL READ32 POST seq=%u addr=%08X value=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
                    (unsigned int)seq,
                    (unsigned int)address,
                    (unsigned int)value,
                    (unsigned int)g_eax,
                    (unsigned int)g_ecx,
                    (unsigned int)g_edx,
                    (unsigned int)g_ebx,
                    (unsigned int)g_esi,
                    (unsigned int)g_edi,
                    (unsigned int)g_esp);
                trace(line);
            }
        }
    }

    return value;
}
"""

    return text[:start] + renamed + "\n\n" + wrapper + text[close_pos + 1:]

def arm_probe(text: str) -> str:
    marker = f"loc_{ARM_VA:08X}: ;\n"
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6CL] expected one arm label {marker.strip()}, "
            f"found {text.count(marker)}"
        )
    code = r'''    s_phase6clReadTraceActive = 1u;
    s_phase6clReadTraceSeq = 0u;
    s_phase6clReadTraceLastAddr = 0u;
    s_phase6clReadTraceLastValue = 0u;
    s_phase6clReadTraceFaultAddr = 0u;
    {
        char phase6clArmLine[512];
        sprintf(
            phase6clArmLine,
            "P6CL READ32 TRACE ARMED va=002832CA eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_ebx,
            (unsigned int)g_esi,
            (unsigned int)g_edi,
            (unsigned int)g_esp);
        trace(phase6clArmLine);
    }
'''
    return text.replace(marker, marker + code, 1)


def insert_summary(text: str) -> str:
    marker = "P6CJ MM166 GENERAL TAIL:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CL] inherited summary marker missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6CL] summary insertion point not found")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CL READ32 CHAIN: active=%u seq=%u last_addr=%08X last_value=%08X fault_addr=%08X",\n'
        f'{indent}    (unsigned int)s_phase6clReadTraceActive,\n'
        f'{indent}    (unsigned int)s_phase6clReadTraceSeq,\n'
        f'{indent}    (unsigned int)s_phase6clReadTraceLastAddr,\n'
        f'{indent}    (unsigned int)s_phase6clReadTraceLastValue,\n'
        f'{indent}    (unsigned int)s_phase6clReadTraceFaultAddr);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CJ", "PHASE 6CL")
        .replace("Phase 6CJ", "Phase 6CL")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CL] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cl_base")
    p6bl = load(args.phase6bl_emitter, "phase6cl_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cj-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CL] missing cached 6CJ input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CJ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CL] cached Phase 6CJ identity mismatch")

    cj = manifest.get("phase6cj_mm166_general_tail", {})
    if (
        cj.get("translated_membership_changed") is not False
        or cj.get("apu_gp_ep_semantics_changed") is not False
        or cj.get("guest_irql_semantics_changed") is not False
        or cj.get("xacteng_membership_changed") is not False
        or cj.get("execution_budget_inherited") != 32000000
    ):
        raise SystemExit("[Phase6CL] inherited 6CJ policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CJ MM166 GENERAL TAIL:",
        "P6CJ APU DSP:",
        f"loc_{ARM_VA:08X}: ;",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CL] inherited marker missing: {marker}")

    prior_block = block_window(main_text, 0x002832BB)
    block = block_window(main_text, ARM_VA)
    if len(prior_block) < 20 or len(block) < 20:
        raise SystemExit("[Phase6CL] XACT block extraction is unexpectedly short")

    print("[Phase6CL] 002832BB SOURCE BLOCK BEGIN")
    for line in prior_block.splitlines():
        print(f"[Phase6CL] | {line}")
    print("[Phase6CL] 002832BB SOURCE BLOCK END")
    print("[Phase6CL] 002832CA SOURCE BLOCK BEGIN")
    for line in block.splitlines():
        print(f"[Phase6CL] | {line}")
    print("[Phase6CL] 002832CA SOURCE BLOCK END")

    main_text = wrap_read32(main_text)
    main_text = arm_probe(main_text)
    main_text = insert_summary(main_text)

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CJ", "PHASE 6CL")
        .replace("Phase 6CJ", "Phase 6CL")
        .replace('"P6CJ ', '"P6CL ')
    )
    env_text = patch_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "P6CL READ32 TRACE ARMED va=002832CA",
        "P6CL READ32 PRE",
        "P6CL READ32 POST",
        "P6CL READ32 INVALID",
        "P6CL READ32 CHAIN:",
        "P6CL MM166 GENERAL TAIL:",
        "P6CL APU DSP:",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CL] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")
    source_report = args.out_dir / "phase6cl-002832ca-source.txt"
    source_report.write_text(
        "===== loc_002832BB =====\n" + prior_block +
        "\n===== loc_002832CA =====\n" + block + "\n",
        encoding="utf-8",
    )

    manifest["phase"] = "6CL"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cl_xact_read32_chain"] = {
        "source_phase": "6CJ",
        "phase6ck_hardware_provenance": {
            "all_six_path_probes_hit_once": True,
            "arm_entry": "0x002832CA",
            "entry_eax": "0x00041D70",
            "entry_ecx": "0x00000000",
            "entry_edx": "0x00000000",
            "entry_esi": "0x00000000",
            "entry_edi": "0x01B5C3F8",
            "following_fault_target": "0xFFFFFFFF",
            "following_fault_ecx": "0xFFFFFFFF",
            "ticks": 26711574,
        },
        "read32_trace_arm_va": "0x002832CA",
        "read32_trace_cap": 32,
        "semantic_repair": False,
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "apu_gp_ep_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "xacteng_membership_changed": False,
        "execution_budget_inherited": 32000000,
        "source_report": source_report.name,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cl-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print("[Phase6CL] 6CK proof: ECX enters 002832CA as 00000000")
    print("[Phase6CL] gated central READ32 chain probe armed at 002832CA")
    print("[Phase6CL] first 32 reads after arm will report PRE/POST; invalid read reports INVALID")
    print(f"[Phase6CL] source report: {source_report}")
    print("[Phase6CL] no allocator/XACT/APU/IRQL semantics changed")
    print("[Phase6CL] 32M execution budget preserved")
    print("[Phase6CL] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
