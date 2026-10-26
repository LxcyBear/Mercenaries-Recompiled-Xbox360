#!/usr/bin/env python3
r"""Phase 6DC: localize the producer of FBE2 arg1=0x00041D90 inside XACTENG.

6DB hardware proved the single direct caller that supplies the failing FBE2
frame is sub_00280C39:

    caller = 0x00280C39
    FBE2.arg1 = 0x00041D90
    FBE2.arg2 = 0x008BF924
    FBE2.arg3 = 0x01B5DE7C
    FBE2.arg4 = 0

FBE2 then transforms arg1 to 0x00041D88 before the DSOUND chain eventually
dereferences [0x00041D88] == 0xCCCCCCCC and faults on 0xCCCCCCD0.

6DC does not change that behavior. It:
  * prints the exact generated-source window around 00280C39 -> 0029FBE2;
  * logs 00280C39 entry arguments/registers;
  * records a bounded register-history ring at every basic-block label in
    00280C39;
  * immediately before the FBE2 call, logs the live frame and dumps the ring
    only when arg1 == 0x00041D90.

No pointer is substituted, no fault is suppressed, and no address range is
widened.
"""
from __future__ import annotations

import argparse
import importlib.util
import json
import re
from pathlib import Path

BASE_TAG = "P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A"
BUILD_TAG = "P6DC-XACT-280C39-FBE2-ARG1-PRODUCER-20261026-A"
COOKIE_OLD = "phase6db_env_build_cookie"
COOKIE_NEW = "phase6dc_env_build_cookie"
EMITTER_REVISION = "6DC-R1"

CALLER_NAME = "sub_00280C39"
CALLER_VA = 0x00280C39
FBE2_VA = 0x0029FBE2
EXPECTED_ARG1 = 0x00041D90
RING_CAP = 32


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DC] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def find_function(text: str, base, name: str) -> tuple[int, int]:
    masked = base.mask_noncode(text)
    matches = []
    for match in base.FUNC_RE.finditer(masked):
        if match.group(1) != name:
            continue
        open_pos = masked.find("{", match.start(), match.end())
        if open_pos < 0:
            continue
        end = base.closing_brace(masked, open_pos)
        matches.append((match.start(), end))
    if len(matches) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one body for {name}, found {len(matches)}"
        )
    return matches[0]


def install_state(text: str) -> str:
    anchor = "static DWORD s_phase6dbFbe2CallerReports = 0u;\n"
    if text.count(anchor) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one 6DB state anchor, found {text.count(anchor)}"
        )
    state = f"""#define PHASE6DC_RING_CAP {RING_CAP}u
static DWORD s_phase6dcEntryReports = 0u;
static DWORD s_phase6dcCallReports = 0u;
static DWORD s_phase6dcMatchingCalls = 0u;
static DWORD s_phase6dcLastEntryArg1 = 0u;
static DWORD s_phase6dcLastCallArg1 = 0u;
static DWORD s_phase6dcRingWrite = 0u;
static DWORD s_phase6dcRingCount = 0u;
static DWORD s_phase6dcRingVa[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEax[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEcx[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEdx[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEbx[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEsi[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEdi[PHASE6DC_RING_CAP];
static DWORD s_phase6dcRingEsp[PHASE6DC_RING_CAP];

"""
    return text.replace(anchor, state + anchor, 1)


def install_helpers(text: str) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DC] translated optimize-off marker missing")

    helper = r'''
static void phase6dc_reset_ring(void)
{
    s_phase6dcRingWrite = 0u;
    s_phase6dcRingCount = 0u;
}

static void phase6dc_note_280c39(DWORD va)
{
    DWORD index = s_phase6dcRingWrite;

    s_phase6dcRingVa[index] = va;
    s_phase6dcRingEax[index] = eax;
    s_phase6dcRingEcx[index] = ecx;
    s_phase6dcRingEdx[index] = edx;
    s_phase6dcRingEbx[index] = ebx;
    s_phase6dcRingEsi[index] = esi;
    s_phase6dcRingEdi[index] = edi;
    s_phase6dcRingEsp[index] = esp;

    ++index;
    if (index >= PHASE6DC_RING_CAP)
        index = 0u;
    s_phase6dcRingWrite = index;

    if (s_phase6dcRingCount < PHASE6DC_RING_CAP)
        ++s_phase6dcRingCount;
}

static void phase6dc_dump_280c39_ring(void)
{
    DWORD i;
    DWORD start = 0u;
    char line[512];

    if (s_phase6dcRingCount == PHASE6DC_RING_CAP)
        start = s_phase6dcRingWrite;

    for (i = 0u; i < s_phase6dcRingCount; ++i)
    {
        DWORD index = start + i;
        if (index >= PHASE6DC_RING_CAP)
            index -= PHASE6DC_RING_CAP;

        sprintf(
            line,
            "P6DC 280C39 RING[%02u]: va=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)i,
            (unsigned int)s_phase6dcRingVa[index],
            (unsigned int)s_phase6dcRingEax[index],
            (unsigned int)s_phase6dcRingEcx[index],
            (unsigned int)s_phase6dcRingEdx[index],
            (unsigned int)s_phase6dcRingEbx[index],
            (unsigned int)s_phase6dcRingEsi[index],
            (unsigned int)s_phase6dcRingEdi[index],
            (unsigned int)s_phase6dcRingEsp[index]);
        trace(line);
    }
}

'''
    return text[:pos] + helper + text[pos:]


def source_audit(text: str, base) -> dict:
    start, end = find_function(text, base, CALLER_NAME)
    body = text[start:end]
    needle = "PUSH32(esp, 0); sub_0029FBE2(); /* call 0x0029FBE2 */"
    hits = [m.start() for m in re.finditer(re.escape(needle), body)]
    if len(hits) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one 280C39->FBE2 call, found {len(hits)}"
        )

    lines = body.splitlines()
    running = 0
    hit_line = -1
    for index, line in enumerate(lines):
        line_len = len(line) + 1
        if running <= hits[0] < running + line_len:
            hit_line = index
            break
        running += line_len
    if hit_line < 0:
        raise SystemExit("[Phase6DC] could not map FBE2 call to source line")

    lo = max(0, hit_line - 28)
    hi = min(len(lines), hit_line + 14)
    context = [
        {"line": i + 1, "text": lines[i]}
        for i in range(lo, hi)
    ]
    return {
        "caller": f"0x{CALLER_VA:08X}",
        "callee": f"0x{FBE2_VA:08X}",
        "body_lines": len(lines),
        "call_line": hit_line + 1,
        "context": context,
    }


def patch_caller(text: str, base) -> tuple[str, int]:
    start, end = find_function(text, base, CALLER_NAME)
    body = text[start:end]

    trace_marker = f"    RECOMP_TRACE_FUNC(0x{CALLER_VA:08X}u);\n"
    trace_pos = body.find(trace_marker)
    if trace_pos < 0:
        raise SystemExit("[Phase6DC] 280C39 entry trace marker missing")

    entry = r'''    {
        DWORD phase6dcArg1;
        DWORD phase6dcArg2;
        DWORD phase6dcArg3;
        DWORD phase6dcArg4;
        DWORD phase6dcArg5;
        DWORD phase6dcArg6;
        char phase6dcLine[640];

        phase6dc_reset_ring();
        phase6dcArg1 = GUEST_READ32(esp + 4u);
        phase6dcArg2 = GUEST_READ32(esp + 8u);
        phase6dcArg3 = GUEST_READ32(esp + 12u);
        phase6dcArg4 = GUEST_READ32(esp + 16u);
        phase6dcArg5 = GUEST_READ32(esp + 20u);
        phase6dcArg6 = GUEST_READ32(esp + 24u);
        ++s_phase6dcEntryReports;
        s_phase6dcLastEntryArg1 = phase6dcArg1;

        sprintf(
            phase6dcLine,
            "P6DC 280C39 ENTRY: esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X arg5=%08X arg6=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X reports=%u",
            (unsigned int)esp,
            (unsigned int)phase6dcArg1,
            (unsigned int)phase6dcArg2,
            (unsigned int)phase6dcArg3,
            (unsigned int)phase6dcArg4,
            (unsigned int)phase6dcArg5,
            (unsigned int)phase6dcArg6,
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)s_phase6dcEntryReports);
        trace(phase6dcLine);
    }
'''
    body = body[:trace_pos] + entry + body[trace_pos:]

    needle = "PUSH32(esp, 0); sub_0029FBE2(); /* call 0x0029FBE2 */"
    call_pos = body.find(needle)
    if call_pos < 0:
        raise SystemExit("[Phase6DC] 280C39->FBE2 call disappeared")

    line_start = body.rfind("\n", 0, call_pos) + 1
    indent = body[line_start:call_pos]
    indent = indent[:len(indent) - len(indent.lstrip())]

    call_probe = f'''{indent}{{
{indent}    DWORD phase6dcArg1 = GUEST_READ32(esp);
{indent}    DWORD phase6dcArg2 = GUEST_READ32(esp + 4u);
{indent}    DWORD phase6dcArg3 = GUEST_READ32(esp + 8u);
{indent}    DWORD phase6dcArg4 = GUEST_READ32(esp + 12u);
{indent}    char phase6dcLine[640];
{indent}
{indent}    ++s_phase6dcCallReports;
{indent}    s_phase6dcLastCallArg1 = phase6dcArg1;
{indent}    if (phase6dcArg1 == 0x{EXPECTED_ARG1:08X}u)
{indent}        ++s_phase6dcMatchingCalls;
{indent}
{indent}    sprintf(
{indent}        phase6dcLine,
{indent}        "P6DC 280C39->FBE2: esp=%08X arg1=%08X arg2=%08X arg3=%08X arg4=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X calls=%u matches=%u",
{indent}        (unsigned int)esp,
{indent}        (unsigned int)phase6dcArg1,
{indent}        (unsigned int)phase6dcArg2,
{indent}        (unsigned int)phase6dcArg3,
{indent}        (unsigned int)phase6dcArg4,
{indent}        (unsigned int)eax,
{indent}        (unsigned int)ecx,
{indent}        (unsigned int)edx,
{indent}        (unsigned int)ebx,
{indent}        (unsigned int)esi,
{indent}        (unsigned int)edi,
{indent}        (unsigned int)s_phase6dcCallReports,
{indent}        (unsigned int)s_phase6dcMatchingCalls);
{indent}    trace(phase6dcLine);
{indent}
{indent}    if (phase6dcArg1 == 0x{EXPECTED_ARG1:08X}u)
{indent}        phase6dc_dump_280c39_ring();
{indent}}}
'''
    body = body[:line_start] + call_probe + body[line_start:]

    label_re = re.compile(r"(?m)^(\s*)loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$")
    labels = list(label_re.finditer(body))
    if not labels:
        raise SystemExit("[Phase6DC] 280C39 contains no basic-block labels")

    pieces = []
    cursor = 0
    for match in labels:
        pieces.append(body[cursor:match.end()])
        va = int(match.group(2), 16)
        pieces.append(
            f"\n{match.group(1)}    phase6dc_note_280c39(0x{va:08X}u);"
        )
        cursor = match.end()
    pieces.append(body[cursor:])
    body = "".join(pieces)

    return text[:start] + body + text[end:], len(labels)


def insert_summary(text: str) -> str:
    marker = "P6DB FBE2 PROVENANCE:"
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DC] inherited 6DB summary missing")
    stmt = text.rfind("sprintf(", 0, pos)
    if stmt < 0 or pos - stmt > 12000:
        raise SystemExit("[Phase6DC] summary insertion point changed")

    line_start = text.rfind("\n", 0, stmt) + 1
    indent = text[line_start:stmt]
    block = (
        f'{indent}sprintf(\n'
        f'{indent}    line,\n'
        f'{indent}    "P6DC 280C39 PRODUCER: entries=%u calls=%u matches=%u entry_arg1=%08X call_arg1=%08X ring_count=%u",\n'
        f'{indent}    (unsigned int)s_phase6dcEntryReports,\n'
        f'{indent}    (unsigned int)s_phase6dcCallReports,\n'
        f'{indent}    (unsigned int)s_phase6dcMatchingCalls,\n'
        f'{indent}    (unsigned int)s_phase6dcLastEntryArg1,\n'
        f'{indent}    (unsigned int)s_phase6dcLastCallArg1,\n'
        f'{indent}    (unsigned int)s_phase6dcRingCount);\n'
        f'{indent}trace(line);\n'
    )
    return text[:line_start] + block + text[line_start:]


def relabel_main(text: str) -> str:
    if text.count(BASE_TAG) != 1:
        raise SystemExit(
            f"[Phase6DC] expected one 6DB build tag, found {text.count(BASE_TAG)}"
        )
    text = text.replace(BASE_TAG, BUILD_TAG, 1)
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DB", "PHASE 6DC")
        .replace("Phase 6DB", "Phase 6DC")
        .replace('"P6DB ', '"P6DC ')
    )


def relabel_env(text: str) -> str:
    if COOKIE_OLD not in text:
        raise SystemExit("[Phase6DC] inherited env cookie missing")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DB", "PHASE 6DC")
        .replace("Phase 6DB", "Phase 6DC")
    )


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dc_base")
    p6bl = load(args.phase6bl_emitter, "phase6dc_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6db-manifest.json"
    for path in (main_path, env_path, manifest_path):
        if not path.exists():
            raise SystemExit(f"[Phase6DC] missing input: {path}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DB" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DC] cached 6DB identity mismatch")

    db = manifest.get("phase6db_dsound_fbe2_caller", {})
    if (
        db.get("probe_only") is not True
        or db.get("guest_memory_semantics_changed") is not False
        or db.get("value_fabrication") is not False
        or db.get("fault_suppression") is not False
        or db.get("address_range_widened") is not False
        or db.get("execution_budget_inherited") != 64000000
        or db.get("hard_fences_weakened") is not False
    ):
        raise SystemExit("[Phase6DC] inherited 6DB policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "P6DB FBE2 CALLER:",
        "P6DB FBE2 ENTRY:",
        "P6DB FBE2 PROVENANCE:",
        "P6DB PREFAULT ROUTER READ32:",
        "PASS: Phase 6DB ExFreePool ITAIL",
        "PASS: Phase 6DB manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DB APU CORE:",
        "P6DB AV/DISPLAY SUMMARY:",
        CALLER_NAME,
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DC] inherited marker missing: {marker}")

    audit = source_audit(main_text, base)
    main_text = install_state(main_text)
    main_text = install_helpers(main_text)
    main_text, label_count = patch_caller(main_text, base)
    main_text = insert_summary(main_text)
    main_text = relabel_main(main_text)
    env_text = relabel_env(env_text)

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "P6DC 280C39 ENTRY:",
        "P6DC 280C39->FBE2:",
        "P6DC 280C39 RING[",
        "P6DC 280C39 PRODUCER:",
        "P6DC FBE2 CALLER:",
        "P6DC FBE2 ENTRY:",
        "P6DC PREFAULT ROUTER READ32:",
        "PASS: Phase 6DC ExFreePool ITAIL",
        "PASS: Phase 6DC manual DSOUND decrypt",
        "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "P6DC APU CORE:",
        "P6DC AV/DISPLAY SUMMARY:",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DC] generated source lost marker: {marker}")

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    manifest.update({
        "phase": "6DC",
        "build_tag": BUILD_TAG,
    })
    manifest["phase6dc_xact_280c39_arg1_producer"] = {
        "source_phase": "6DB",
        "hardware_proof": {
            "caller": "0x00280C39",
            "fbe2_arg1": "0x00041D90",
            "fbe2_arg2": "0x008BF924",
            "fbe2_arg3": "0x01B5DE7C",
            "fbe2_arg4": "0x00000000",
            "downstream_bad_object": "0x00041D88",
            "fault_address": "0xCCCCCCD0",
            "ticks": 27021609,
        },
        "source_audit": audit,
        "instrumented_basic_blocks": label_count,
        "ring_capacity": RING_CAP,
        "probe_only": True,
        "guest_memory_semantics_changed": False,
        "value_fabrication": False,
        "fault_suppression": False,
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

    (args.out_dir / "phase6dc-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n",
        encoding="utf-8",
    )

    print(f"[Phase6DC] emitter revision: {EMITTER_REVISION}")
    print(
        f"[Phase6DC] instrumented 00280C39 basic blocks: {label_count}; "
        f"ring capacity={RING_CAP}"
    )
    print("[Phase6DC] 00280C39 -> FBE2 generated-source window:")
    for row in audit["context"]:
        mark = ">>" if row["line"] == audit["call_line"] else "  "
        print(f"[Phase6DC] {mark} {row['line']:04d}: {row['text']}")
    print("[Phase6DC] no pointer substitution; no fault suppression")
    print("[Phase6DC] money lines:")
    print("[Phase6DC]   P6DC 280C39 ENTRY: ...")
    print("[Phase6DC]   P6DC 280C39->FBE2: ... arg1=00041D90 ...")
    print("[Phase6DC]   P6DC 280C39 RING[..]: va=... registers...")
    print("[Phase6DC] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
