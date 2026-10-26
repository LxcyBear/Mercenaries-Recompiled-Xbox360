#!/usr/bin/env python3
r"""Phase 6DA: DSOUND bad-object argument lineage.

6CZ + local generated-source audit proved the CCCCCCD0 fault is:
    sub_002A41EE:
        esi = GUEST_READ32(esp + 8)
        eax = GUEST_READ32(esi)
        RECOMP_ICALL_SAFE(GUEST_READ32(eax + 4), ...)
with hardware:
    esi = 0x00041D88
    [esi] = 0xCCCCCCCC
    [eax+4] -> 0xCCCCCCD0

Static source then proved sub_0029F992 allocates the new 0x24-byte DSOUND-side
object and forwards its first incoming argument unchanged through:
    0029F992 -> 0029EBEA -> 0029EA79 -> 002A41EE

6DA records that argument at each function entry and the prior trace VA so the
upstream producer can be identified without fabricating a pointer or weakening
the guest-memory fault.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6CZ-PREFAULT-CCCCCCD0-PROVENANCE-20261026-A"
BUILD_TAG = "P6DA-DSOUND-ARG-LINEAGE-00041D88-20261026-A"
COOKIE_OLD = "phase6cz_env_build_cookie"
COOKIE_NEW = "phase6da_env_build_cookie"
EMITTER_REVISION = "6DA-R3"

TARGETS = (
    ("0029F992", 0x0029F992),
    ("0029EBEA", 0x0029EBEA),
    ("0029EA79", 0x0029EA79),
    ("002A41EE", 0x002A41EE),
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DA] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6czTranslatedPrefaultReports = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DA] expected one 6CZ state anchor, found {text.count(anchor)}"
        )
    state = """static DWORD s_phase6daArgLineageReports = 0u;
static DWORD s_phase6daLastStage = 0u;
static DWORD s_phase6daLastPriorVa = 0u;
static DWORD s_phase6daLastArg1 = 0u;
static DWORD s_phase6daLastEsp = 0u;

"""
    return text.replace(anchor, state + anchor, 1)


def entry_probe(stage: int, va: int) -> str:
    # Probe is inserted immediately before RECOMP_TRACE_FUNC at function entry,
    # so g_esp still has the original translated call frame:
    # [esp+0]=dummy return, [esp+4]=arg1, etc.
    return f'''    {{
        DWORD phase6daPriorVa = 0u;
        DWORD phase6daArg1 = GUEST_READ32(esp + 4u);
        DWORD phase6daArg2 = GUEST_READ32(esp + 8u);
        DWORD phase6daArg3 = GUEST_READ32(esp + 12u);
        DWORD phase6daArg4 = GUEST_READ32(esp + 16u);
        char phase6daLine[512];

        if (s_traceCount != 0u)
        {{
            DWORD phase6daIndex = s_traceCount - 1u;
            if (phase6daIndex >= TRACE_CAPACITY)
                phase6daIndex = TRACE_CAPACITY - 1u;
            phase6daPriorVa = s_trace[phase6daIndex];
        }}

        ++s_phase6daArgLineageReports;
        s_phase6daLastStage = {stage}u;
        s_phase6daLastPriorVa = phase6daPriorVa;
        s_phase6daLastArg1 = phase6daArg1;
        s_phase6daLastEsp = esp;

        sprintf(
            phase6daLine,
            "P6DA DSOUND ARG: stage={stage} func={va:08X} prior_va=%08X esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X eax=%08X ecx=%08X edx=%08X esi=%08X reports=%u",
            (unsigned int)phase6daPriorVa,
            (unsigned int)esp,
            (unsigned int)phase6daArg1,
            (unsigned int)phase6daArg2,
            (unsigned int)phase6daArg3,
            (unsigned int)phase6daArg4,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)esi,
            (unsigned int)s_phase6daArgLineageReports);
        trace(phase6daLine);
    }}
'''


def patch_entries(text: str) -> str:
    for stage, (name, va) in enumerate(TARGETS, 1):
        signature = f"void sub_{name}(void)"

        # main_monolithic.cpp contains forward declarations before translated
        # bodies.  Anchor on the actual function definition, not the prototype.
        definition_re = re.compile(
            rf"(?m)^void\s+sub_{name}\(void\)\s*\{{"
        )
        matches = list(definition_re.finditer(text))
        if len(matches) != 1:
            raise SystemExit(
                f"[Phase6DA] expected one body for {signature}, found {len(matches)}"
            )

        sig = matches[0].start()
        body_open = text.find("{", matches[0].start(), matches[0].end() + 1)
        if body_open < 0:
            raise SystemExit(f"[Phase6DA] body brace missing for {signature}")

        trace_marker = f"    RECOMP_TRACE_FUNC(0x{va:08X}u);\n"
        pos = text.find(trace_marker, body_open)
        if pos < 0 or pos - body_open > 4096:
            raise SystemExit(
                f"[Phase6DA] entry trace marker missing/too far for {signature}"
            )

        text = text[:pos] + entry_probe(stage, va) + text[pos:]

    return text


def insert_summary(text: str) -> str:
    marker = "P6CZ PREFAULT PROVENANCE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DA] inherited 6CZ provenance summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DA] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DA DSOUND ARG LINEAGE: reports=%u last_stage=%u prior_va=%08X arg1=%08X esp=%08X",\n'
        f'{indent}    (unsigned int)s_phase6daArgLineageReports,\n'
        f'{indent}    (unsigned int)s_phase6daLastStage,\n'
        f'{indent}    (unsigned int)s_phase6daLastPriorVa,\n'
        f'{indent}    (unsigned int)s_phase6daLastArg1,\n'
        f'{indent}    (unsigned int)s_phase6daLastEsp);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DA] expected one 6CZ build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6CZ", "PHASE 6DA")
        .replace("Phase 6CZ", "Phase 6DA")
        .replace('"P6CZ ', '"P6DA ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DA] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6CZ", "PHASE 6DA")
        .replace("Phase 6CZ", "Phase 6DA")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6da_base")
    p6bl = load(args.phase6bl_emitter, "phase6da_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6cz-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6DA] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6CZ" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DA] cached 6CZ identity mismatch")

    cz = manifest.get("phase6cz_prefault_ccccccd0_provenance", {})
    if (
        cz.get("guest_memory_semantics_changed") is not False
        or cz.get("value_fabrication") is not False
        or cz.get("address_range_widened") is not False
        or cz.get("execution_budget_inherited") != 64000000
        or cz.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DA] inherited 6CZ policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6CZ PREFAULT ROUTER READ32:",
        "PASS: Phase 6CZ ExFreePool ITAIL",
        "PASS: Phase 6CZ manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6CZ APU CORE:",
        "P6CZ AV/DISPLAY SUMMARY:",
        "void sub_0029F992(void)",
        "void sub_0029EBEA(void)",
        "void sub_0029EA79(void)",
        "void sub_002A41EE(void)",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DA] inherited marker missing: {marker}")

    main_text = install_state(main_text)
    main_text = patch_entries(main_text)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DA DSOUND ARG: stage=1 func=0029F992",
        "P6DA DSOUND ARG: stage=2 func=0029EBEA",
        "P6DA DSOUND ARG: stage=3 func=0029EA79",
        "P6DA DSOUND ARG: stage=4 func=002A41EE",
        "P6DA DSOUND ARG LINEAGE:",
        "P6DA PREFAULT ROUTER READ32:",
        "PASS: Phase 6DA ExFreePool ITAIL",
        "PASS: Phase 6DA manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DA APU CORE:",
        "P6DA AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DA] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DA",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6da_dsound_argument_lineage"] = {
        "source_phase": "6CZ",
        "phase6cz_hardware": {
            "fault_address": "0xCCCCCCD0",
            "fault_object_argument": "0x00041D88",
            "fault_vtable_value": "0xCCCCCCCC",
            "ticks": 27021609,
            "trace": 1071691,
            "final_va_ring_tail": [
                "0x0029F9C3",
                "0x0029F9C8",
                "0x0029EBEA",
                "0x0029EA79",
                "0x002A41EE",
                "0x002A41F7",
            ],
        },
        "static_source_proof": {
            "sub_0029F992_forwards_arg1": True,
            "chain": [
                "0x0029F992",
                "0x0029EBEA",
                "0x0029EA79",
                "0x002A41EE",
            ],
            "push32_evaluates_operand_before_esp_decrement": True,
        },
        "probe_only": True,
        "target_entry_count": 4,
        "guest_memory_semantics_changed": False,
        "value_fabrication": False,
        "address_range_widened": False,
        "execution_budget_inherited": 64000000,
        "exfreepool_itail_preserved": True,
        "manual_dsound_decrypt_preserved": True,
        "shadow_ram_alias_preserved": True,
        "graphics_semantics_changed": False,
        "apu_semantics_changed": False,
        "hard_fences_weakened": False,
        "source_layout": layout,
    }
    (args.out_dir / "phase6da-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DA] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DA] targeted chain: 0029F992 -> 0029EBEA -> 0029EA79 -> 002A41EE")
    print("[Phase6DA] hardware bad object argument: 00041D88")
    print("[Phase6DA] entry probes preserve call frames and log prior VA + args 1..4")
    print("[Phase6DA] no pointer substitution; CCCCCCD0 remains a hard fault")
    print("[Phase6DA] money line: P6DA DSOUND ARG: stage=1 func=0029F992 prior_va=... arg1=00041D88 ...")
    print("[Phase6DA] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
