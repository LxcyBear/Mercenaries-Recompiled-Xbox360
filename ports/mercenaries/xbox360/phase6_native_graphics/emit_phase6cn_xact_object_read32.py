#!/usr/bin/env python3
"""Phase 6CN: trace the new downstream XACT object-pointer corruption.

6CM hardware proved the guarded ESI continuity repair:
  * 002832BB captured ESI=01B5C320 twice.
  * 002832CA saw ESI=0 twice and restored 01B5C320 twice.
  * the old READ32(0)->FFFFFFFF->READ32(FFFFFFFF) fault disappeared.
  * execution advanced into 00282Bxx/002833xx and faulted on
    READ32(782E657F) with EAX=782E6567, i.e. READ32(EAX+0x18).

6CN preserves 6CM semantics and adds a narrow READ32 trace only while the
current translated basic block lies in 0x00282B00..0x00283400 after the
002832CA path has armed the probe. The existing budget tick is used to stamp
the current translated VA, so every read log identifies the exact block that
performed it.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CM-XACT-ESI-CONTINUITY-20261025-A"
BUILD_TAG = "P6CN-XACT-OBJECT-READ32-20261025-A"
COOKIE_OLD = "phase6cm_env_build_cookie"
COOKIE_NEW = "phase6cn_env_build_cookie"

ARM_VA = 0x002832CA
TRACE_START = 0x00282B00
TRACE_END = 0x00283400
EMITTER_REVISION = "6CN-R5"


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6CN] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6CN] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def block_window(text: str, va: int) -> str:
    marker = f"loc_{va:08X}: ;\n"
    start = text.find(marker)
    if start < 0:
        raise SystemExit(f"[Phase6CN] source label missing: {marker.strip()}")
    next_match = re.search(r"\nloc_[0-9A-Fa-f]{8}: ;\n", text[start + len(marker):])
    if next_match:
        end = start + len(marker) + next_match.start() + 1
    else:
        end = min(len(text), start + 9000)
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
    raise SystemExit("[Phase6CN] unterminated recomp_guest_read32 body")


def install_current_va_stamp(text: str) -> str:
    tick_signature = "static void phase4c_budget_tick(DWORD va)"
    tick_start = text.find(tick_signature)
    if tick_start < 0:
        raise SystemExit("[Phase6CN] phase4c_budget_tick definition missing")
    tick_open = text.find("{", tick_start)
    tick_close = matching_brace(text, tick_open)
    tick_body = text[tick_open:tick_close + 1]

    increment = "++s_phase4cBlockTicks;"
    if tick_body.count(increment) != 1:
        raise SystemExit(
            f"[Phase6CN] expected one budget increment in phase4c_budget_tick, "
            f"found {tick_body.count(increment)}"
        )
    stamped = increment + "\n    s_phase6cnCurrentVa = va;"
    tick_body = tick_body.replace(increment, stamped, 1)
    return text[:tick_open] + tick_body + text[tick_close + 1:]

def wrap_read32(text: str) -> str:
    signature = "uint32_t recomp_guest_read32(uint32_t address)"
    definition_re = re.compile(
        r"(?m)^uint32_t\s+recomp_guest_read32\(uint32_t address\)\s*\{"
    )
    matches = list(definition_re.finditer(text))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6CN] expected one recomp_guest_read32 definition, found {len(matches)}"
        )

    start = matches[0].start()
    open_pos = text.find("{", matches[0].start(), matches[0].end() + 1)
    if open_pos < 0:
        raise SystemExit("[Phase6CN] recomp_guest_read32 definition brace missing")
    close_pos = matching_brace(text, open_pos)
    original = text[start:close_pos + 1]

    renamed = original.replace(
        signature,
        "static uint32_t phase6cn_inherited_guest_read32(uint32_t address)",
        1,
    )

    wrapper = r"""
static DWORD s_phase6cnCurrentVa = 0u;
static DWORD s_phase6cnReadTraceActive = 0u;
static DWORD s_phase6cnReadTraceVisits = 0u;
static DWORD s_phase6cnReadTraceSeq = 0u;
static DWORD s_phase6cnReadTraceWindowReads = 0u;
static DWORD s_phase6cnReadTraceLastVa = 0u;
static DWORD s_phase6cnReadTraceLastAddr = 0u;
static DWORD s_phase6cnReadTraceLastValue = 0u;
static DWORD s_phase6cnReadTraceFaultVa = 0u;
static DWORD s_phase6cnReadTraceFaultAddr = 0u;

uint32_t recomp_guest_read32(uint32_t address)
{
    uint32_t value;
    DWORD seq = 0u;
    DWORD inWindow =
        s_phase6cnReadTraceActive &&
        s_phase6cnCurrentVa >= 0x00282B00u &&
        s_phase6cnCurrentVa < 0x00283400u;

    if (inWindow)
    {
        char line[760];
        seq = ++s_phase6cnReadTraceSeq;
        ++s_phase6cnReadTraceWindowReads;
        s_phase6cnReadTraceLastVa = s_phase6cnCurrentVa;
        s_phase6cnReadTraceLastAddr = address;

        if (seq <= 160u)
        {
            sprintf(
                line,
                "P6CN XACT READ32 PRE visit=%u seq=%u va=%08X addr=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
                (unsigned int)s_phase6cnReadTraceVisits,
                (unsigned int)seq,
                (unsigned int)s_phase6cnCurrentVa,
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

    value = phase6cn_inherited_guest_read32(address);

    if (inWindow)
    {
        char line[760];

        if (s_accessFault)
        {
            s_phase6cnReadTraceFaultVa = s_phase6cnCurrentVa;
            s_phase6cnReadTraceFaultAddr = address;
            sprintf(
                line,
                "P6CN XACT READ32 FAULT visit=%u seq=%u va=%08X addr=%08X returned=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
                (unsigned int)s_phase6cnReadTraceVisits,
                (unsigned int)seq,
                (unsigned int)s_phase6cnCurrentVa,
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
        else
        {
            s_phase6cnReadTraceLastValue = value;
            if (seq <= 160u)
            {
                sprintf(
                    line,
                    "P6CN XACT READ32 POST visit=%u seq=%u va=%08X addr=%08X value=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
                    (unsigned int)s_phase6cnReadTraceVisits,
                    (unsigned int)seq,
                    (unsigned int)s_phase6cnCurrentVa,
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
            f"[Phase6CN] expected one arm label {marker.strip()}, found {text.count(marker)}"
        )

    start = text.find(marker) + len(marker)
    original_tick = "    PHASE4C_BUDGET_TICK(0x002832CAu);\n"
    tick_pos = text.find(original_tick, start)
    if tick_pos < 0 or tick_pos - start > 9000:
        raise SystemExit(
            "[Phase6CN] original 002832CA budget tick not found after inherited 6CM repair"
        )

    inherited_region = text[start:tick_pos]
    if (
        "PASS: Phase 6CM restored XACT ESI at 002832CA" not in inherited_region
        or "P6CM XACT ESI RESTORE SKIP" not in inherited_region
    ):
        raise SystemExit(
            "[Phase6CN] inherited 6CM restore chain missing before 002832CA budget tick"
        )

    code = r'''    s_phase6cnReadTraceActive = 1u;
    ++s_phase6cnReadTraceVisits;
    s_phase6cnReadTraceSeq = 0u;
    {
        char phase6cnArmLine[640];
        sprintf(
            phase6cnArmLine,
            "P6CN XACT READ32 TRACE ARMED visit=%u va=002832CA current_va=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)s_phase6cnReadTraceVisits,
            (unsigned int)s_phase6cnCurrentVa,
            (unsigned int)g_eax,
            (unsigned int)g_ecx,
            (unsigned int)g_edx,
            (unsigned int)g_ebx,
            (unsigned int)g_esi,
            (unsigned int)g_edi,
            (unsigned int)g_esp);
        trace(phase6cnArmLine);
    }
'''
    return text[:tick_pos] + code + text[tick_pos:]

def insert_summary(text: str) -> str:
    marker = "P6CM XACT ESI:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6CN] inherited 6CM XACT summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 7000:
        raise SystemExit("[Phase6CN] summary insertion point not found")
    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6CN XACT READ32: visits=%u seq=%u window_reads=%u last_va=%08X last_addr=%08X last_value=%08X fault_va=%08X fault_addr=%08X",\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceVisits,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceSeq,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceWindowReads,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceLastVa,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceLastAddr,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceLastValue,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceFaultVa,\n'
        f'{indent}    (unsigned int)s_phase6cnReadTraceFaultAddr);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def patch_policy(text: str) -> str:
    marker = 'trace("Policy:'
    start = text.find(marker)
    if start < 0 or text.find(marker, start + 1) >= 0:
        raise SystemExit("[Phase6CN] expected exactly one runtime policy trace")
    line_start = text.rfind("\n", 0, start) + 1
    line_end = text.find("\n", start)
    if line_end < 0:
        line_end = len(text)
    indent = text[line_start:start]
    policy = (
        "Phase 6CN preserves the hardware-proven 6CM XACT ESI continuity repair and "
        "traces guest READ32 operations only while the current translated VA is in "
        "00282B00-002833FF, stamping each read with the exact basic block; preserve "
        "allocator, APU GP/EP, guest IRQL, graphics/file/IDEX, null/SEH semantics, "
        "32M watchdog, translated membership and every hard fence"
    )
    return text[:line_start] + indent + f'trace("Policy: {policy}");' + text[line_end:]


def patch_env(text: str) -> str:
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    text = (
        text.replace("PHASE 6CM", "PHASE 6CN")
        .replace("Phase 6CM", "Phase 6CN")
    )
    if COOKIE_NEW not in text or COOKIE_OLD in text:
        raise SystemExit("[Phase6CN] environment cookie rewrite failed")
    return text


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6cn_base")
    p6bl = load(args.phase6bl_emitter, "phase6cn_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cm-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6CN] missing cached 6CM input: {path}")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if manifest.get("phase") != "6CM" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6CN] cached Phase 6CM identity mismatch")

    cm = manifest.get("phase6cm_xact_esi_continuity", {})
    guard = cm.get("guard", {})
    if (
        cm.get("translated_membership_changed") is not False
        or cm.get("hard_fences_changed") is not False
        or cm.get("execution_budget_inherited") != 32000000
        or guard.get("current_esi_must_be_zero") is not True
        or guard.get("captured_esi_must_equal_live_xact_root") is not True
        or guard.get("null_page_semantics_changed") is not False
        or guard.get("seh_terminator_semantics_changed") is not False
    ):
        raise SystemExit("[Phase6CN] inherited 6CM policy mismatch")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 32000000u",
        "P6CM XACT ESI CAPTURE va=002832BB",
        "PASS: Phase 6CM restored XACT ESI at 002832CA",
        "P6CM XACT ESI:",
        "static DWORD s_phase6awVaRingCount = 0u;",
        f"loc_{ARM_VA:08X}: ;",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CN] inherited marker missing: {marker}")

    ring_vas = [
        0x00282BC2, 0x00282BD7, 0x00282BD9, 0x00282BE2, 0x00282BE6,
        0x00282BE8, 0x00282BEC, 0x00282BF3, 0x00282C6C, 0x002832E7,
        0x002832F2, 0x00283301, 0x00283308, 0x00283317, 0x0028331C,
        0x00283325,
    ]
    source_blocks_found = 0
    for va in ring_vas:
        marker = f"loc_{va:08X}: ;\n"
        if marker not in main_text:
            print(f"[Phase6CN] SOURCE BLOCK {va:08X}: no exact loc label (runtime VA only)")
            continue
        block = block_window(main_text, va)
        source_blocks_found += 1
        print(f"[Phase6CN] SOURCE BLOCK {va:08X} BEGIN")
        for line in block.splitlines():
            print(f"[Phase6CN] | {line}")
        print(f"[Phase6CN] SOURCE BLOCK {va:08X} END")
    print(
        f"[Phase6CN] source diagnostics: {source_blocks_found}/{len(ring_vas)} "
        "runtime-ring VAs had exact loc labels"
    )

    main_text = install_current_va_stamp(main_text)
    main_text = wrap_read32(main_text)
    main_text = arm_probe(main_text)
    main_text = insert_summary(main_text)
    main_text = patch_policy(main_text)

    main_text = replace_once(main_text, BASE_TAG, BUILD_TAG, "build tag")
    main_text = main_text.replace(COOKIE_OLD, COOKIE_NEW)
    main_text = (
        main_text.replace("PHASE 6CM", "PHASE 6CN")
        .replace("Phase 6CM", "Phase 6CN")
        .replace('"P6CM ', '"P6CN ')
    )
    env_text = patch_env(env_text)

    for marker in (
        BUILD_TAG,
        COOKIE_NEW,
        "s_phase6cnCurrentVa = va;",
        "P6CN XACT READ32 TRACE ARMED",
        "P6CN XACT READ32 PRE",
        "P6CN XACT READ32 POST",
        "P6CN XACT READ32 FAULT",
        "P6CN XACT READ32:",
        "PASS: Phase 6CN restored XACT ESI at 002832CA",
        "#define PHASE4C_EXEC_BUDGET 32000000u",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6CN] generated source lost marker: {marker}")

    state_pos = main_text.find("static DWORD s_phase6cnCurrentVa = 0u;")
    tick_pos = main_text.find("static void phase4c_budget_tick(DWORD va)")
    wrapper_pos = main_text.find(
        "uint32_t recomp_guest_read32(uint32_t address)",
        state_pos + 1 if state_pos >= 0 else 0,
    )
    if state_pos < 0 or tick_pos < 0 or wrapper_pos < 0:
        raise SystemExit(
            f"[Phase6CN] compile-order proof marker mismatch "
            f"(state={state_pos} wrapper={wrapper_pos} tick={tick_pos})"
        )
    wrapper_open = main_text.find("{", wrapper_pos)
    wrapper_line_end = main_text.find("\n", wrapper_pos)
    if (
        wrapper_open < 0
        or wrapper_line_end < 0
        or wrapper_open > wrapper_line_end + 2
    ):
        raise SystemExit("[Phase6CN] READ32 definition proof failed")
    if not (state_pos < wrapper_pos and state_pos < tick_pos):
        raise SystemExit(
            "[Phase6CN] trace state must be declared before READ32 wrapper and budget tick"
        )

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest["phase"] = "6CN"
    manifest["build_tag"] = BUILD_TAG
    manifest["phase6cn_xact_object_read32"] = {
        "source_phase": "6CM",
        "phase6cm_hardware": {
            "esi_capture_count": 2,
            "esi_restore_checks": 2,
            "esi_restore_successes": 2,
            "captured_esi": "0x01B5C320",
            "current_before_restore": "0x00000000",
            "xact_root": "0x01B5C320",
            "new_boundary_kind": "GUEST_FAULT",
            "new_fault_address": "0x782E657F",
            "new_fault_eax": "0x782E6567",
            "new_fault_relation": "fault_address = eax + 0x18",
            "ticks": 26711680,
            "trace": 1017599,
        },
        "trace_window_start": f"0x{TRACE_START:08X}",
        "trace_window_end_exclusive": f"0x{TRACE_END:08X}",
        "arm_va": f"0x{ARM_VA:08X}",
        "max_logged_reads_per_visit": 160,
        "current_va_stamped_by_budget_tick": True,
        "xact_esi_repair_preserved": True,
        "translated_membership_changed": False,
        "allocator_policy_changed": False,
        "apu_gp_ep_semantics_changed": False,
        "guest_irql_semantics_changed": False,
        "graphics_semantics_changed": False,
        "null_page_semantics_changed": False,
        "seh_terminator_semantics_changed": False,
        "hard_fences_changed": False,
        "execution_budget_inherited": 32000000,
        "source_layout": layout,
    }

    (args.out_dir / "phase6cn-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6CN] emitter revision: {EMITTER_REVISION}")
    print("[Phase6CN] 6CM ESI continuity repair preserved")
    print("[Phase6CN] current translated VA stamped from phase4c_budget_tick")
    print("[Phase6CN] READ32 trace window: 00282B00-002833FF")
    print("[Phase6CN] target new fault: EAX=782E6567 -> READ32(EAX+18)=782E657F")
    print("[Phase6CN] null/SEH/APU/IRQL/allocator/graphics semantics unchanged")
    print("[Phase6CN] 32M execution budget preserved")
    print("[Phase6CN] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
