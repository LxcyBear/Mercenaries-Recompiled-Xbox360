#!/usr/bin/env python3
r"""Phase 6DQ ROCKET: broad support-clean pack + bounded runtime frontier journal.

6DP hardware proved the exact VP FREE read and immediately advanced to:
    WRITE32 FE8202A4
at tick 26,712,259. The historical CCCCCCD0/XACT teardown path remained absent,
the XACT root remained published, and native Xenos/D3D remained alive.

6DQ is deliberately optimized for progress per hardware run:
  * pre-pack up to 4096 additional support-clean generated functions across
    D3D, XGRPH, DSOUND and XACTENG (graphics first);
  * route all translated DSOUND guest accesses through the inherited APU
    classifiers so newly packed DSOUND bodies get the same core/DSP/VP routing;
  * permit aligned 32-bit VP command writes as a diagnostic safe-continue path,
    recording every distinct method/address and value while preserving unknown
    VP reads as hard fences;
  * journal packed DIRECT/ICALL dispatch targets and every phase4c hard stop;
  * reduce hot broad-sweep progress printing from every 4096 dispatches to every
    65536 while preserving first-hit and final aggregate visibility.

This phase does NOT claim complete VP/audio semantics. VP write continuation is
explicitly diagnostic so audio initialization cannot force one build per method
while we chase the renderer. Unknown VP reads, meaningful non-VP MMIO, guest faults, ABI boundaries,
missing translated bodies and unresolved support remain hard stops. Hardware-proven
kernel timing ordinal 151 is bridged with maintained busy-wait semantics. R23 also\nbatches the hardware-proven kernel floating-point guard pair 142/139 using opaque\nState-pointer nesting under the serialized runtime. R16's
hardware-proven DSOUND poison-dispatch site 002A41F7 is quarantined without
widening ordinary guest-memory fault handling. R26 adds predictive static
frontier clearing: direct DSOUND producer callsites, literal DSOUND kernel
targets, and real AvSetDisplayMode intent callers are audited before VS builds.
R27 rejects raw constant false positives, backward-slices A41EE arg1 producers,
and adds a bounded runtime callsite ring without suppressing guest faults.
"""

from __future__ import annotations

import argparse
import contextlib
import importlib.util
import io
import json
import re
from pathlib import Path

BASE_TAG = "P6DP-APU-VP-FREE-20261026-A"
BUILD_TAG = "P6DQ-ROCKET-FRONTIER-JOURNAL-20261026-A"
COOKIE_OLD = "phase6dp_env_build_cookie"
COOKIE_NEW = "phase6dq_env_build_cookie"
EMITTER_REVISION = "6DQ-R28"

CANDIDATE_CAP = 4096
DSOUND_POISON_SITE = 0x002A41F7
DSOUND_POISON_VALUE = 0xCCCCCCCC
DSOUND_POISON_NOOP_TARGET = 0xF6DCCCD0
DSOUND_START = 0x0029CB80
DSOUND_END = 0x002BB274
PREDICTIVE_CLOSURE_DEPTH = 12
PREDICTIVE_CLOSURE_CAP_PER_SEED = 768
PREDICTIVE_AUDIO_TARGET = "sub_002A41EE"
PREDICTIVE_DISPLAY_ORDINAL = 0x80000003
MAINTAINED_KERNEL_TARGETS = {
    0x8000008B,  # KeRestoreFloatingPointState
    0x8000008E,  # KeSaveFloatingPointState
    0x80000097,  # KeStallExecutionProcessor
}

GRAPHICS_SURFACE_BASE = 0x024FC000
GRAPHICS_SURFACE_END = 0x02628000
GRAPHICS_DEVICE_BASE = 0x00299380
GRAPHICS_DEVICE_END = 0x0029B000
GRAPHICS_STATIC_ANCHORS = (
    0x00299380,
    0x0029AFA0,
    0x0029AFA8,
    0x024FC000,
    0x024FC003,
    0x02627FFF,
)

SECTIONS = (
    ("D3D", 0x00288640, 0x0029B874, 0x0028E700),
    ("XGRPH", 0x0029B880, 0x0029CB7C, 0x0029C8BE),
    ("DSOUND", 0x0029CB80, 0x002BB274, 0x002A6713),
    ("TEXT_HOT", 0x00011000, 0x0025561C, 0x00209810),
    ("XACTENG", 0x0027D5C0, 0x00288630, 0x0027DB5C),
    ("WMADEC", 0x002BB280, 0x002D4300, 0x002BB280),
    ("XPP", 0x002D4300, 0x002DBCC8, 0x002D4300),
    ("XMV", 0x00255620, 0x0027D5B4, 0x00255620),
)


def load(path: Path, name: str):
    spec = importlib.util.spec_from_file_location(name, path)
    if spec is None or spec.loader is None:
        raise SystemExit(f"[Phase6DQ] could not load helper {path}")
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def replace_once(text: str, old: str, new: str, label: str) -> str:
    count = text.count(old)
    if count != 1:
        raise SystemExit(f"[Phase6DQ] expected one {label}, found {count}")
    return text.replace(old, new, 1)


def function_span(text: str, signature: str) -> tuple[int, int]:
    start = text.find(signature)
    if start < 0:
        raise SystemExit(f"[Phase6DQ] function signature missing: {signature}")
    brace = text.find("{", start)
    if brace < 0:
        raise SystemExit(f"[Phase6DQ] opening brace missing: {signature}")

    depth = 0
    i = brace
    in_string = False
    quote = ""
    escape = False
    line_comment = False
    block_comment = False
    while i < len(text):
        c = text[i]
        n = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if c == "\n":
                line_comment = False
            i += 1
            continue
        if block_comment:
            if c == "*" and n == "/":
                block_comment = False
                i += 2
            else:
                i += 1
            continue
        if in_string:
            if escape:
                escape = False
            elif c == "\\":
                escape = True
            elif c == quote:
                in_string = False
            i += 1
            continue

        if c == "/" and n == "/":
            line_comment = True
            i += 2
            continue
        if c == "/" and n == "*":
            block_comment = True
            i += 2
            continue
        if c in ('"', "'"):
            in_string = True
            quote = c
            i += 1
            continue

        if c == "{":
            depth += 1
        elif c == "}":
            depth -= 1
            if depth == 0:
                return start, i + 1
        i += 1

    raise SystemExit(f"[Phase6DQ] unterminated function: {signature}")


def translated_function_defs(text: str, base) -> list[dict]:
    masked = base.mask_noncode(text)
    rows = []
    for m in base.FUNC_RE.finditer(masked):
        name = m.group(1)
        open_pos = masked.find("{", m.start(), m.end())
        if open_pos < 0:
            continue
        end = base.closing_brace(masked, open_pos)
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        va = int(vm.group(1), 16) if vm else 0
        rows.append({
            "name": name,
            "va": va,
            "start": m.start(),
            "open": open_pos,
            "end": end,
        })
    return rows


def _literal_icall_occurrences(source: str) -> list[dict]:
    """Return only literal 0x800000XX values used inside an ICALL_SAFE statement."""
    rows = []
    for match in re.finditer(r"0x800000([0-9A-Fa-f]{2})u?", source):
        literal_pos = match.start()
        previous_semi = source.rfind(";", 0, literal_pos)
        statement_start = previous_semi + 1
        prefix = source[statement_start:literal_pos]
        if "ICALL_SAFE" not in prefix:
            continue

        statement_end = source.find(";", match.end())
        if statement_end < 0:
            continue
        statement = source[statement_start:statement_end + 1]
        if "ICALL_SAFE" not in statement:
            continue

        target = 0x80000000 | int(match.group(1), 16)
        rows.append({
            "target": target,
            "statement": " ".join(statement.split()),
            "offset": literal_pos,
        })
    return rows


def predictive_seed_vas(generated: dict) -> list[int]:
    """
    Prioritize real call-path owners only.

    Raw occurrences of 0x80000003 are NOT seeds: R26 proved several are plain
    status masks/object fields. Display seeding requires a literal ordinal 3
    inside an ICALL_SAFE statement.
    """
    seeds = []
    for va, row in generated.items():
        source = row["source"]
        source_lower = source.lower()
        if "sub_002A41EE();" in source:
            seeds.append(va)
            continue
        if any(
            call["target"] == PREDICTIVE_DISPLAY_ORDINAL
            for call in _literal_icall_occurrences(source)
        ):
            seeds.append(va)
            continue
        if any(
            (f"0x{anchor:x}" in source_lower) or
            (f"0x{anchor:08x}" in source_lower)
            for anchor in GRAPHICS_STATIC_ANCHORS
        ):
            seeds.append(va)

    seeds.extend((0x002A6713, 0x0029C8BE, 0x0028E700))
    return list(dict.fromkeys(seeds))


def build_predictive_candidates(
    seeds: list[int],
    old: set[int],
    generated: dict,
    base,
    p5bb,
) -> list[int]:
    selected = []

    def add(va: int) -> None:
        if (
            va in generated
            and va not in old
            and va not in selected
            and len(selected) < CANDIDATE_CAP
        ):
            selected.append(va)

    for seed in seeds:
        add(seed)
        if seed not in generated:
            continue
        try:
            closure = p5bb.bounded_promoted_members(
                base,
                seed,
                generated,
                PREDICTIVE_CLOSURE_DEPTH,
                PREDICTIVE_CLOSURE_CAP_PER_SEED,
            )
        except BaseException:
            closure = []
        for va in closure:
            add(va)

    return selected


def _previous_arg1_push(body: str, call_offset: int) -> tuple[str, str]:
    """
    Recover the already-pushed A41EE arg1 expression immediately before the
    synthetic return-slot PUSH32(esp, 0). This is static provenance only.
    """
    prefix = body[:call_offset]
    lines = prefix.splitlines()
    for line in reversed(lines[-32:]):
        stripped = line.strip()
        if not stripped or stripped.startswith("loc_"):
            if stripped.startswith("loc_"):
                break
            continue
        match = re.search(r"PUSH32\(\s*esp\s*,\s*(.+)\s*\)\s*;", stripped)
        if match:
            expr = match.group(1).strip()
            kind = "register_or_expression"
            if "read32(esp" in expr.lower():
                kind = "stack_relative"
            elif "read32(ebp" in expr.lower():
                kind = "frame_relative"
            elif re.fullmatch(r"(?:e?ax|e?bx|e?cx|e?dx|esi|edi|ebp)", expr, re.I):
                kind = "register"
            elif re.search(r"read32\(\s*0x[0-9A-Fa-f]+", expr):
                kind = "global_read"
            elif re.fullmatch(r"0x[0-9A-Fa-f]+|\d+", expr):
                kind = "literal"
            return expr, kind
    return "<not-found>", "unknown"


def _last_register_assignments(body: str, call_offset: int) -> dict:
    lines = body[:call_offset].splitlines()
    result = {}
    for reg in ("eax", "ebx", "ecx", "edx", "esi", "edi"):
        pat = re.compile(rf"^\s*{reg}\s*=\s*(.+);\s*$", re.I)
        for line in reversed(lines[-80:]):
            m = pat.match(line)
            if m:
                result[reg] = m.group(1).strip()
                break
    return result


def predictive_static_audit(text: str, base) -> dict:
    """
    R27 static pre-build provenance audit.

    Only syntactic call shapes are labeled calls. Plain constants are retained
    as noise counts and never drive predictive pack priority.
    """
    defs = translated_function_defs(text, base)
    audio_sites = []
    kernel_calls = []
    display_calls = []
    raw_kernel_constants = 0
    raw_display_constants = 0

    direct_re = re.compile(
        r"PUSH32\(\s*esp\s*,\s*0\s*\)\s*;\s*"
        r"sub_002A41EE\(\)\s*;\s*/\*\s*call\s+0x002A41EE\s*\*/"
    )

    site_id = 0
    for row in defs:
        if not row["va"]:
            continue
        body = text[row["open"]:row["end"]]

        raw_kernel_constants += len(
            re.findall(r"0x800000[0-9A-Fa-f]{2}u?", body)
        )
        raw_display_constants += body.count("0x80000003")

        for match in direct_re.finditer(body):
            site_id += 1
            arg1_expr, arg1_kind = _previous_arg1_push(body, match.start())
            rel_line = body[:match.start()].count("\n")
            body_lines = body.splitlines()
            lo = max(0, rel_line - 18)
            hi = min(len(body_lines), rel_line + 7)
            audio_sites.append({
                "site_id": site_id,
                "owner_va": f"0x{row['va']:08X}",
                "owner_name": row["name"],
                "arg1_expression": arg1_expr,
                "arg1_kind": arg1_kind,
                "last_register_assignments": _last_register_assignments(
                    body, match.start()
                ),
                "context": body_lines[lo:hi],
            })

        if DSOUND_START <= row["va"] < DSOUND_END:
            for call in _literal_icall_occurrences(body):
                item = {
                    "owner_va": f"0x{row['va']:08X}",
                    "owner_name": row["name"],
                    "target": f"0x{call['target']:08X}",
                    "ordinal": call["target"] & 0xFFFF,
                    "maintained": call["target"] in MAINTAINED_KERNEL_TARGETS,
                    "statement": call["statement"],
                }
                kernel_calls.append(item)
                if call["target"] == PREDICTIVE_DISPLAY_ORDINAL:
                    display_calls.append(item)

    return {
        "enabled": True,
        "mode": "static_prebuild_predictive_frontier_clearing_r27",
        "r25_hardware_seed": {
            "ticks": 27025727,
            "boundary_kind": "GUEST_FAULT",
            "fault_address": "0xEC83F0E4",
            "dsound_function": "0x002A41EE",
            "entry_arg1": "0xEC83F0E4",
            "hresult_register_ebx": "0x8007000E",
            "fp_save_calls": 1,
            "fp_restore_calls": 1,
            "fp_guard_depth": 0,
            "fp_guard_mismatches": 0,
        },
        "audio_target": "0x002A41EE",
        "audio_direct_call_sites": audio_sites,
        "audio_direct_call_site_count": len(audio_sites),
        "dsound_kernel_calls": kernel_calls,
        "dsound_kernel_call_count": len(kernel_calls),
        "display_ordinal": "0x80000003",
        "display_kernel_call_sites": display_calls,
        "display_kernel_call_site_count": len(display_calls),
        "raw_kernel_constant_occurrences": raw_kernel_constants,
        "raw_display_ordinal_constant_occurrences": raw_display_constants,
        "raw_constants_are_not_calls": True,
        "ordinary_guest_faults_bypassed": False,
        "unknown_kernel_calls_auto_succeeded": False,
        "unknown_mmio_auto_accepted": False,
        "unknown_reads_zero_filled": False,
    }


def print_predictive_audit(audit: dict) -> None:
    print("[Phase6DQ] ============ PREDICTIVE PROVENANCE AUDIT R27 ============")
    seed = audit["r25_hardware_seed"]
    print(
        "[Phase6DQ] R25 seed: ticks={ticks} fault={fault_address} "
        "func={dsound_function} arg1={entry_arg1} ebx={hresult_register_ebx}".format(
            **seed
        )
    )
    print(
        f"[Phase6DQ] AUDIO direct callers of 002A41EE: "
        f"{audit['audio_direct_call_site_count']}"
    )
    for site in audit["audio_direct_call_sites"]:
        print(
            f"[Phase6DQ] AUDIO SITE[{site['site_id']}] "
            f"owner={site['owner_va']} name={site['owner_name']} "
            f"arg1_kind={site['arg1_kind']} arg1_expr={site['arg1_expression']}"
        )
        regs = site["last_register_assignments"]
        if regs:
            print(
                "[Phase6DQ]   LAST-REGS "
                + " ".join(f"{k}={v}" for k, v in regs.items())
            )
        for line in site["context"]:
            print("[Phase6DQ]   " + line)

    print(
        f"[Phase6DQ] DSOUND literal ICALL kernel targets: "
        f"{audit['dsound_kernel_call_count']}"
    )
    for call in audit["dsound_kernel_calls"]:
        print(
            f"[Phase6DQ] KERNEL CALL owner={call['owner_va']} "
            f"target={call['target']} ordinal={call['ordinal']} "
            f"maintained={int(call['maintained'])} stmt={call['statement']}"
        )

    print(
        f"[Phase6DQ] DISPLAY ordinal-3 literal ICALL sites: "
        f"{audit['display_kernel_call_site_count']}"
    )
    print(
        f"[Phase6DQ] RAW CONSTANT NOISE: kernel_like="
        f"{audit['raw_kernel_constant_occurrences']} "
        f"ordinal3={audit['raw_display_ordinal_constant_occurrences']} "
        "(not treated as calls)"
    )
    print("[Phase6DQ] Predictive policy: unknown kernel/MMIO/read semantics remain HARD FENCES")
    print("[Phase6DQ] =========================================================")


def instrument_a41ee_callsites(text: str, base) -> tuple[str, list[dict]]:
    """Tag every direct A41EE caller without changing the callee or fault policy."""
    masked = base.mask_noncode(text)
    direct_re = re.compile(
        r"(?P<indent>[ \t]*)PUSH32\(\s*esp\s*,\s*0\s*\)\s*;\s*"
        r"sub_002A41EE\(\)\s*;\s*/\*\s*call\s+0x002A41EE\s*\*/"
    )
    patches = []
    site_map = []
    site_id = 0

    for match in base.FUNC_RE.finditer(masked):
        name = match.group(1)
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if not vm:
            continue
        owner = int(vm.group(1), 16)
        open_pos = masked.find("{", match.start(), match.end())
        if open_pos < 0:
            continue
        end = base.closing_brace(masked, open_pos)
        body = text[open_pos:end]

        for call in direct_re.finditer(body):
            site_id += 1
            absolute_start = open_pos + call.start()
            absolute_end = open_pos + call.end()
            indent = call.group("indent")
            original = text[absolute_start:absolute_end]
            probe = (
                f"{indent}{{\n"
                f"{indent}    uint32_t phase6dqA41eeArg1 = GUEST_READ32(esp);\n"
                f"{indent}    phase6dq_note_a41ee_callsite("
                f"{site_id}u, 0x{owner:08X}u, phase6dqA41eeArg1);\n"
                f"{indent}}}\n"
                + original
            )
            patches.append((absolute_start, absolute_end, probe))
            site_map.append({
                "site_id": site_id,
                "owner_va": f"0x{owner:08X}",
                "owner_name": name,
            })

    for start, end, replacement in reversed(patches):
        text = text[:start] + replacement + text[end:]

    if not site_map:
        raise SystemExit("[Phase6DQ] predictive A41EE callsite instrumentation found no sites")

    return text, site_map

def select_candidates(
    generated: dict,
    old: set[int],
    existing_defs: set[str],
) -> tuple[list[int], dict[str, int], dict[str, int]]:
    selected: list[int] = []
    available_counts: dict[str, int] = {}
    selected_counts: dict[str, int] = {}

    for section, start, end, seed in SECTIONS:
        choices = [
            va
            for va, row in generated.items()
            if start <= va < end
            and va not in old
            and row["name"] not in existing_defs
        ]
        choices.sort(key=lambda va: (abs(va - seed), va))
        available_counts[section] = len(choices)

        room = CANDIDATE_CAP - len(selected)
        take = choices[: max(0, room)]
        selected.extend(take)
        selected_counts[section] = len(take)

        if len(selected) >= CANDIDATE_CAP:
            break

    for section, _, _, _ in SECTIONS:
        available_counts.setdefault(section, 0)
        selected_counts.setdefault(section, 0)

    return selected, available_counts, selected_counts


def install_journal_support(text: str) -> str:
    caller_sig = "static DWORD phase4c_current_caller(void)"
    start, end = function_span(text, caller_sig)

    state = r'''
#define PHASE6DQ_DISPATCH_JOURNAL_CAP 96u
#define PHASE6DQ_HARDSTOP_JOURNAL_CAP 24u
#define PHASE6DQ_VP_JOURNAL_CAP 64u

typedef struct Phase6DQDispatchJournal
{
    uint32_t kind;
    uint32_t target;
    uint32_t caller;
    uint32_t firstEsp;
    uint32_t lastEsp;
    uint32_t hits;
} Phase6DQDispatchJournal;

typedef struct Phase6DQHardStopJournal
{
    uint32_t kind;
    uint32_t target;
    uint32_t caller;
    uint32_t savedEsp;
    uint32_t eaxValue;
    uint32_t ecxValue;
    uint32_t edxValue;
    uint32_t ebxValue;
    uint32_t esiValue;
    uint32_t ediValue;
    uint32_t ticks;
    uint32_t hits;
} Phase6DQHardStopJournal;

typedef struct Phase6DQVpJournal
{
    uint32_t address;
    uint32_t firstValue;
    uint32_t lastValue;
    uint32_t firstCaller;
    uint32_t lastCaller;
    uint32_t firstEsp;
    uint32_t lastEsp;
    uint32_t hits;
} Phase6DQVpJournal;

static Phase6DQDispatchJournal
    s_phase6dqDispatchJournal[PHASE6DQ_DISPATCH_JOURNAL_CAP];
static Phase6DQHardStopJournal
    s_phase6dqHardStopJournal[PHASE6DQ_HARDSTOP_JOURNAL_CAP];
static Phase6DQVpJournal
    s_phase6dqVpJournal[PHASE6DQ_VP_JOURNAL_CAP];
static uint32_t s_phase6dqDispatchJournalCount = 0u;
static uint32_t s_phase6dqDispatchJournalOverflow = 0u;
static uint32_t s_phase6dqHardStopJournalCount = 0u;
static uint32_t s_phase6dqHardStopJournalOverflow = 0u;
static uint32_t s_phase6dqVpJournalCount = 0u;
static uint32_t s_phase6dqVpJournalOverflow = 0u;
static uint32_t s_phase6dqVpWrite32Count = 0u;
static uint32_t s_phase6dqVpUnknownReadCount = 0u;
static uint32_t s_phase6dqIoapicDefaultReadCount = 0u;
static uint32_t s_phase6dqIoapicDefaultWriteCount = 0u;
static uint32_t s_phase6dqIoapicSpecialFenceCount = 0u;
static uint32_t s_phase6dqKeStall151Count = 0u;
static uint64_t s_phase6dqKeStall151TotalUs = 0ui64;
static uint32_t s_phase6dqKeStall151LastUs = 0u;
static uint32_t s_phase6dqKeStall151MaxUs = 0u;
static uint32_t s_phase6dqDsoundPoisonSiteCount = 0u;
static uint32_t s_phase6dqDsoundPoisonNoopCount = 0u;
static uint32_t s_phase6dqDsoundPoisonLastObject = 0u;
static uint32_t s_phase6dqDsoundPoisonLastArg = 0u;
#define PHASE6DQ_FP_GUARD_DEPTH_CAP 8u
static uint32_t s_phase6dqFpGuardStates[PHASE6DQ_FP_GUARD_DEPTH_CAP];
static uint32_t s_phase6dqFpGuardDepth = 0u;
static uint32_t s_phase6dqFpSave142Count = 0u;
static uint32_t s_phase6dqFpRestore139Count = 0u;
static uint32_t s_phase6dqFpGuardMismatchCount = 0u;
static uint32_t s_phase6dqFpGuardLastState = 0u;
#define PHASE6DQ_A41EE_RING_CAP 16u
typedef struct Phase6DQA41eeCall
{
    uint32_t sequence;
    uint32_t site;
    uint32_t owner;
    uint32_t arg1;
} Phase6DQA41eeCall;
static Phase6DQA41eeCall s_phase6dqA41eeRing[PHASE6DQ_A41EE_RING_CAP];
static uint32_t s_phase6dqA41eeSequence = 0u;
static uint32_t s_phase6dqA41eeRingWrite = 0u;
static uint32_t s_phase6dqA41eeRingCount = 0u;
static uint32_t s_phase6dqA41eeLastSite = 0u;
static uint32_t s_phase6dqA41eeLastOwner = 0u;
static uint32_t s_phase6dqA41eeLastArg1 = 0u;

'''
    text = text[:start] + state + text[start:]
    # Current-caller function shifted by inserted state; find it again.
    _, end = function_span(text, caller_sig)

    support = r'''

static const char* phase6dq_vp_method_name(uint32_t offset)
{
    if (offset == 0x00000010u) return "NV1BA0_PIO_FREE";
    if (offset >= 0x00000200u && offset <= 0x0000027Cu &&
        (offset & 3u) == 0u) return "NV1BA0_PIO_SET_SUBMIX_HEADROOM";
    if (offset == 0x00000280u) return "NV1BA0_PIO_SET_HRTF_HEADROOM";
    if (offset == 0x000002C0u) return "NV1BA0_PIO_SET_HRTF_SUBMIXES";
    if (offset == 0x000002F8u) return "NV1BA0_PIO_SET_CURRENT_VOICE";
    if (offset == 0x000002FCu) return "NV1BA0_PIO_VOICE_LOCK";
    if (offset >= 0x00000300u && offset <= 0x000003DCu &&
        (offset & 3u) == 0u) return "NV1BA0_PIO_VOICE_CONFIG";
    if (offset >= 0x00000400u && offset <= 0x0000043Cu &&
        (offset & 3u) == 0u) return "NV1BA0_PIO_SET_HRIR";
    if (offset >= 0x00000600u && offset <= 0x00000808u &&
        (offset & 3u) == 0u) return "NV1BA0_PIO_BUFFER_OR_SSL";
    return "VP_UNNAMED_OR_UNMODELED";
}

static void phase6dq_note_a41ee_callsite(
    uint32_t site,
    uint32_t owner,
    uint32_t arg1)
{
    Phase6DQA41eeCall* row;
    char line[384];

    ++s_phase6dqA41eeSequence;
    s_phase6dqA41eeLastSite = site;
    s_phase6dqA41eeLastOwner = owner;
    s_phase6dqA41eeLastArg1 = arg1;

    row = &s_phase6dqA41eeRing[s_phase6dqA41eeRingWrite];
    row->sequence = s_phase6dqA41eeSequence;
    row->site = site;
    row->owner = owner;
    row->arg1 = arg1;
    s_phase6dqA41eeRingWrite =
        (s_phase6dqA41eeRingWrite + 1u) % PHASE6DQ_A41EE_RING_CAP;
    if (s_phase6dqA41eeRingCount < PHASE6DQ_A41EE_RING_CAP)
        ++s_phase6dqA41eeRingCount;

    if (s_phase6dqA41eeSequence <= 16u || arg1 == 0xEC83F0E4u)
    {
        sprintf(
            line,
            "P6DQ A41EE CALLSITE: seq=%u site=%u owner=%08X arg1=%08X esp=%08X",
            (unsigned int)s_phase6dqA41eeSequence,
            (unsigned int)site,
            (unsigned int)owner,
            (unsigned int)arg1,
            (unsigned int)g_esp);
        trace(line);
    }
}

static void phase6dq_note_dispatch(
    uint32_t kind,
    uint32_t target,
    uint32_t caller,
    uint32_t espValue)
{
    uint32_t i;
    char line[320];

    for (i = 0u; i < s_phase6dqDispatchJournalCount; ++i)
    {
        Phase6DQDispatchJournal* row = &s_phase6dqDispatchJournal[i];
        if (row->kind == kind && row->target == target &&
            row->caller == caller)
        {
            ++row->hits;
            row->lastEsp = espValue;
            return;
        }
    }

    if (s_phase6dqDispatchJournalCount >= PHASE6DQ_DISPATCH_JOURNAL_CAP)
    {
        ++s_phase6dqDispatchJournalOverflow;
        return;
    }

    {
        Phase6DQDispatchJournal* row =
            &s_phase6dqDispatchJournal[s_phase6dqDispatchJournalCount++];
        row->kind = kind;
        row->target = target;
        row->caller = caller;
        row->firstEsp = espValue;
        row->lastEsp = espValue;
        row->hits = 1u;
    }

    sprintf(
        line,
        "P6DQ ROCKET DISPATCH FIRST kind=%s caller=%08X target=%08X esp=%08X unique=%u",
        kind == 1u ? "ICALL" : "DIRECT",
        (unsigned int)caller,
        (unsigned int)target,
        (unsigned int)espValue,
        (unsigned int)s_phase6dqDispatchJournalCount);
    trace(line);
}

static void phase6dq_note_hard_stop(
    uint32_t kind,
    uint32_t target,
    uint32_t caller,
    uint32_t savedEsp)
{
    uint32_t i;
    char line[448];

    for (i = 0u; i < s_phase6dqHardStopJournalCount; ++i)
    {
        Phase6DQHardStopJournal* row = &s_phase6dqHardStopJournal[i];
        if (row->kind == kind && row->target == target &&
            row->caller == caller)
        {
            ++row->hits;
            return;
        }
    }

    if (s_phase6dqHardStopJournalCount >= PHASE6DQ_HARDSTOP_JOURNAL_CAP)
    {
        ++s_phase6dqHardStopJournalOverflow;
        return;
    }

    {
        Phase6DQHardStopJournal* row =
            &s_phase6dqHardStopJournal[s_phase6dqHardStopJournalCount++];
        row->kind = kind;
        row->target = target;
        row->caller = caller;
        row->savedEsp = savedEsp;
        row->eaxValue = g_eax;
        row->ecxValue = g_ecx;
        row->edxValue = g_edx;
        row->ebxValue = g_ebx;
        row->esiValue = g_esi;
        row->ediValue = g_edi;
        row->ticks = s_phase4cBlockTicks;
        row->hits = 1u;
    }

    sprintf(
        line,
        "P6DQ ROCKET HARD STOP kind=%u caller=%08X target=%08X esp=%08X ticks=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X",
        (unsigned int)kind,
        (unsigned int)caller,
        (unsigned int)target,
        (unsigned int)savedEsp,
        (unsigned int)s_phase4cBlockTicks,
        (unsigned int)g_eax,
        (unsigned int)g_ecx,
        (unsigned int)g_edx,
        (unsigned int)g_ebx,
        (unsigned int)g_esi,
        (unsigned int)g_edi);
    trace(line);
}

static void phase6dq_note_vp_write(
    uint32_t address,
    uint32_t value,
    uint32_t caller,
    uint32_t espValue)
{
    uint32_t i;
    uint32_t offset = address - 0xFE820000u;
    char line[448];

    ++s_phase6dqVpWrite32Count;

    for (i = 0u; i < s_phase6dqVpJournalCount; ++i)
    {
        Phase6DQVpJournal* row = &s_phase6dqVpJournal[i];
        if (row->address == address)
        {
            ++row->hits;
            row->lastValue = value;
            row->lastCaller = caller;
            row->lastEsp = espValue;
            return;
        }
    }

    if (s_phase6dqVpJournalCount >= PHASE6DQ_VP_JOURNAL_CAP)
    {
        ++s_phase6dqVpJournalOverflow;
        return;
    }

    {
        Phase6DQVpJournal* row =
            &s_phase6dqVpJournal[s_phase6dqVpJournalCount++];
        row->address = address;
        row->firstValue = value;
        row->lastValue = value;
        row->firstCaller = caller;
        row->lastCaller = caller;
        row->firstEsp = espValue;
        row->lastEsp = espValue;
        row->hits = 1u;
    }

    sprintf(
        line,
        "P6DQ ROCKET VP WRITE FIRST addr=%08X method=%04X name=%s value=%08X caller=%08X esp=%08X unique=%u",
        (unsigned int)address,
        (unsigned int)offset,
        phase6dq_vp_method_name(offset),
        (unsigned int)value,
        (unsigned int)caller,
        (unsigned int)espValue,
        (unsigned int)s_phase6dqVpJournalCount);
    trace(line);
}

static int phase6dq_ioapic_is_page(uint32_t address)
{
    return address >= 0xFEC00000u && address < 0xFEC01000u;
}

static int phase6dq_ioapic_is_default_offset(uint32_t address)
{
    uint32_t offset = address & 0xFFu;

    /*
     * xemu/QEMU's IOAPIC MMIO handler masks the 4 KiB page address to the
     * low byte. Only 0x00 (IOREGSEL), 0x10 (IOWIN), and 0x40 (EOI write)
     * have device semantics. Every other offset returns zero on read and
     * ignores writes. Keep those three special offsets fenced so this ROCKET
     * bridge cannot accidentally emulate selector/window/EOI behavior.
     */
    return phase6dq_ioapic_is_page(address) &&
        offset != 0x00u &&
        offset != 0x10u &&
        offset != 0x40u;
}

static uint32_t phase6dq_ioapic_default_read(
    uint32_t address,
    uint32_t width)
{
    char line[384];
    uint32_t value = 0u;

    ++s_phase6dqIoapicDefaultReadCount;

    if (s_phase6dqIoapicDefaultReadCount <= 16u ||
        (s_phase6dqIoapicDefaultReadCount & 0xFFu) == 0u)
    {
        sprintf(
            line,
            "P6DQ ROCKET IOAPIC DEFAULT READ width=%u addr=%08X offset=%02X value=%08X caller=%08X esp=%08X count=%u",
            (unsigned int)width,
            (unsigned int)address,
            (unsigned int)(address & 0xFFu),
            (unsigned int)value,
            (unsigned int)phase4c_current_caller(),
            (unsigned int)g_esp,
            (unsigned int)s_phase6dqIoapicDefaultReadCount);
        trace(line);
    }

    return value;
}

static void phase6dq_ioapic_default_write(
    uint32_t address,
    uint32_t width,
    uint32_t value)
{
    char line[384];

    ++s_phase6dqIoapicDefaultWriteCount;

    if (s_phase6dqIoapicDefaultWriteCount <= 16u ||
        (s_phase6dqIoapicDefaultWriteCount & 0xFFu) == 0u)
    {
        sprintf(
            line,
            "P6DQ ROCKET IOAPIC DEFAULT WRITE width=%u addr=%08X offset=%02X value=%08X caller=%08X esp=%08X count=%u no_op=1",
            (unsigned int)width,
            (unsigned int)address,
            (unsigned int)(address & 0xFFu),
            (unsigned int)value,
            (unsigned int)phase4c_current_caller(),
            (unsigned int)g_esp,
            (unsigned int)s_phase6dqIoapicDefaultWriteCount);
        trace(line);
    }
}

static void phase6dq_note_ioapic_special_fence(
    uint32_t address,
    uint32_t width,
    uint32_t isWrite,
    uint32_t value)
{
    char line[384];

    ++s_phase6dqIoapicSpecialFenceCount;
    sprintf(
        line,
        "P6DQ ROCKET IOAPIC SPECIAL HARD %s width=%u addr=%08X offset=%02X value=%08X caller=%08X esp=%08X count=%u",
        isWrite ? "WRITE" : "READ",
        (unsigned int)width,
        (unsigned int)address,
        (unsigned int)(address & 0xFFu),
        (unsigned int)value,
        (unsigned int)phase4c_current_caller(),
        (unsigned int)g_esp,
        (unsigned int)s_phase6dqIoapicSpecialFenceCount);
    trace(line);
}

static uint32_t phase6dq_dsound_poison_dispatch_target(
    uint32_t candidate,
    uint32_t objectValue,
    uint32_t argumentValue)
{
    char line[384];

    if (candidate != 0xCCCCCCCCu)
        return candidate;

    ++s_phase6dqDsoundPoisonSiteCount;
    s_phase6dqDsoundPoisonLastObject = objectValue;
    s_phase6dqDsoundPoisonLastArg = argumentValue;

    sprintf(
        line,
        "P6DQ DSOUND POISON SLOT: site=002A41F7 candidate=%08X object=%08X arg=%08X esp=%08X hits=%u synthetic=%08X",
        (unsigned int)candidate,
        (unsigned int)objectValue,
        (unsigned int)argumentValue,
        (unsigned int)g_esp,
        (unsigned int)s_phase6dqDsoundPoisonSiteCount,
        (unsigned int)0xF6DCCCD0u);
    trace(line);

    return 0xF6DCCCD0u;
}

static void phase6dq_dsound_poison_noop(uint32_t savedEsp)
{
    char line[320];

    ++s_phase6dqDsoundPoisonNoopCount;

    /*
     * R16 hardware proved an unconstructed/poisoned DSOUND dispatch slot at
     * 002A41F7: candidate vtable/dispatch pointer CCCCCCCC followed by slot +4.
     * Treat only this exact translated dispatch site as an absent DSOUND slot.
     * Return DS_OK (0) and restore the already-computed safe post-call ESP.
     * No ordinary guest-memory fault or unrelated CCCCCCCC value is bypassed.
     */
    eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "P6DQ DSOUND POISON NOOP: calls=%u result=%08X new_esp=%08X object=%08X arg=%08X",
        (unsigned int)s_phase6dqDsoundPoisonNoopCount,
        (unsigned int)eax,
        (unsigned int)g_esp,
        (unsigned int)s_phase6dqDsoundPoisonLastObject,
        (unsigned int)s_phase6dqDsoundPoisonLastArg);
    trace(line);
}

static void phase6dq_ke_save_floating_point_state(uint32_t savedEsp)
{
    uint32_t state = GUEST_READ32(g_esp + 4u);
    char line[384];

    ++s_phase6dqFpSave142Count;
    s_phase6dqFpGuardLastState = state;

    if (state == 0u || s_phase6dqFpGuardDepth >= PHASE6DQ_FP_GUARD_DEPTH_CAP)
    {
        ++s_phase6dqFpGuardMismatchCount;
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x8000008Eu,
            savedEsp);
        return;
    }

    s_phase6dqFpGuardStates[s_phase6dqFpGuardDepth++] = state;

    /*
     * Xbox ordinal 142 is NTSTATUS KeSaveFloatingPointState(PVOID State).
     * The translated runtime is serialized and does not context-switch an
     * independent kernel FPU owner beneath guest code, so retain the opaque
     * guest State pointer/nesting contract and return STATUS_SUCCESS without
     * fabricating an unproven KFLOATING_SAVE byte layout.
     */
    eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "P6DQ KESAVEFP142: calls=%u state=%08X depth=%u result=%08X caller=%08X new_esp=%08X",
        (unsigned int)s_phase6dqFpSave142Count,
        (unsigned int)state,
        (unsigned int)s_phase6dqFpGuardDepth,
        (unsigned int)eax,
        (unsigned int)phase4c_current_caller(),
        (unsigned int)g_esp);
    trace(line);
}

static void phase6dq_ke_restore_floating_point_state(uint32_t savedEsp)
{
    uint32_t state = GUEST_READ32(g_esp + 4u);
    char line[384];

    ++s_phase6dqFpRestore139Count;
    s_phase6dqFpGuardLastState = state;

    if (state == 0u ||
        s_phase6dqFpGuardDepth == 0u ||
        s_phase6dqFpGuardStates[s_phase6dqFpGuardDepth - 1u] != state)
    {
        ++s_phase6dqFpGuardMismatchCount;
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x8000008Bu,
            savedEsp);
        return;
    }

    --s_phase6dqFpGuardDepth;
    s_phase6dqFpGuardStates[s_phase6dqFpGuardDepth] = 0u;

    eax = 0u;
    g_esp = savedEsp;

    sprintf(
        line,
        "P6DQ KERESTOREFP139: calls=%u state=%08X depth=%u result=%08X caller=%08X new_esp=%08X",
        (unsigned int)s_phase6dqFpRestore139Count,
        (unsigned int)state,
        (unsigned int)s_phase6dqFpGuardDepth,
        (unsigned int)eax,
        (unsigned int)phase4c_current_caller(),
        (unsigned int)g_esp);
    trace(line);
}

static void phase6dq_ke_stall_execution_processor(uint32_t savedEsp)
{
    uint32_t microSeconds = GUEST_READ32(g_esp + 4u);
    LARGE_INTEGER frequency;
    LARGE_INTEGER start;
    LARGE_INTEGER now;
    uint64_t waitTicks = 0ui64;
    char line[384];

    ++s_phase6dqKeStall151Count;
    s_phase6dqKeStall151LastUs = microSeconds;
    s_phase6dqKeStall151TotalUs += (uint64_t)microSeconds;
    if (microSeconds > s_phase6dqKeStall151MaxUs)
        s_phase6dqKeStall151MaxUs = microSeconds;

    /*
     * A real stall is expected to be short. Refuse a corrupted/unbounded
     * duration rather than pinning the Xenon CPU for an arbitrarily long time.
     * R16 hardware proved 20 us per call, far below this guard.
     */
    if (microSeconds > 1000000u)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x80000097u,
            savedEsp);
        return;
    }

    /*
     * Xbox ordinal 151 is VOID KeStallExecutionProcessor(ULONG MicroSeconds).
     * Preserve its busy-wait contract using the native high-resolution
     * counter. The guest frame is stdcall: return slot + one dword argument.
     */
    if (microSeconds != 0u &&
        QueryPerformanceFrequency(&frequency) &&
        frequency.QuadPart > 0 &&
        QueryPerformanceCounter(&start))
    {
        waitTicks =
            (((uint64_t)frequency.QuadPart * (uint64_t)microSeconds) +
             999999ui64) /
            1000000ui64;

        do
        {
            QueryPerformanceCounter(&now);
        }
        while ((uint64_t)(now.QuadPart - start.QuadPart) < waitTicks);
    }

    g_esp = savedEsp;

    if (s_phase6dqKeStall151Count <= 16u ||
        (s_phase6dqKeStall151Count & 0xFFu) == 0u)
    {
        sprintf(
            line,
            "P6DQ KESTALL151: calls=%u us=%u total_us=%I64u max_us=%u caller=%08X new_esp=%08X",
            (unsigned int)s_phase6dqKeStall151Count,
            (unsigned int)microSeconds,
            (unsigned __int64)s_phase6dqKeStall151TotalUs,
            (unsigned int)s_phase6dqKeStall151MaxUs,
            (unsigned int)phase4c_current_caller(),
            (unsigned int)g_esp);
        trace(line);
    }
}

static void phase6dq_note_vp_unknown_read(
    uint32_t address,
    uint32_t width)
{
    char line[384];
    ++s_phase6dqVpUnknownReadCount;
    sprintf(
        line,
        "P6DQ ROCKET VP READ HARD width=%u addr=%08X method=%04X name=%s caller=%08X esp=%08X count=%u",
        (unsigned int)width,
        (unsigned int)address,
        (unsigned int)(address - 0xFE820000u),
        phase6dq_vp_method_name(address - 0xFE820000u),
        (unsigned int)phase4c_current_caller(),
        (unsigned int)g_esp,
        (unsigned int)s_phase6dqVpUnknownReadCount);
    trace(line);
}

static void phase6dq_dump_journals(void)
{
    uint32_t i;
    char line[1024];

    sprintf(
        line,
        "P6DQ ROCKET JOURNAL SUMMARY dispatch_unique=%u dispatch_overflow=%u hard_unique=%u hard_overflow=%u vp_write32=%u vp_unique=%u vp_overflow=%u vp_unknown_reads=%u ioapic_default_reads=%u ioapic_default_writes=%u ioapic_special_fences=%u kestall151_calls=%u kestall151_last_us=%u kestall151_total_us=%I64u kestall151_max_us=%u fpsave142_calls=%u fprestore139_calls=%u fpguard_depth=%u fpguard_mismatches=%u fpguard_last_state=%08X dsound_poison_sites=%u dsound_poison_noops=%u dsound_poison_object=%08X dsound_poison_arg=%08X a41ee_seq=%u a41ee_last_site=%u a41ee_last_owner=%08X a41ee_last_arg1=%08X",
        (unsigned int)s_phase6dqDispatchJournalCount,
        (unsigned int)s_phase6dqDispatchJournalOverflow,
        (unsigned int)s_phase6dqHardStopJournalCount,
        (unsigned int)s_phase6dqHardStopJournalOverflow,
        (unsigned int)s_phase6dqVpWrite32Count,
        (unsigned int)s_phase6dqVpJournalCount,
        (unsigned int)s_phase6dqVpJournalOverflow,
        (unsigned int)s_phase6dqVpUnknownReadCount,
        (unsigned int)s_phase6dqIoapicDefaultReadCount,
        (unsigned int)s_phase6dqIoapicDefaultWriteCount,
        (unsigned int)s_phase6dqIoapicSpecialFenceCount,
        (unsigned int)s_phase6dqKeStall151Count,
        (unsigned int)s_phase6dqKeStall151LastUs,
        (unsigned __int64)s_phase6dqKeStall151TotalUs,
        (unsigned int)s_phase6dqKeStall151MaxUs,
        (unsigned int)s_phase6dqFpSave142Count,
        (unsigned int)s_phase6dqFpRestore139Count,
        (unsigned int)s_phase6dqFpGuardDepth,
        (unsigned int)s_phase6dqFpGuardMismatchCount,
        (unsigned int)s_phase6dqFpGuardLastState,
        (unsigned int)s_phase6dqDsoundPoisonSiteCount,
        (unsigned int)s_phase6dqDsoundPoisonNoopCount,
        (unsigned int)s_phase6dqDsoundPoisonLastObject,
        (unsigned int)s_phase6dqDsoundPoisonLastArg,
        (unsigned int)s_phase6dqA41eeSequence,
        (unsigned int)s_phase6dqA41eeLastSite,
        (unsigned int)s_phase6dqA41eeLastOwner,
        (unsigned int)s_phase6dqA41eeLastArg1);
    trace(line);

    for (i = 0u; i < s_phase6dqA41eeRingCount; ++i)
    {
        uint32_t index =
            (s_phase6dqA41eeRingWrite + PHASE6DQ_A41EE_RING_CAP -
             s_phase6dqA41eeRingCount + i) % PHASE6DQ_A41EE_RING_CAP;
        Phase6DQA41eeCall* row = &s_phase6dqA41eeRing[index];
        sprintf(
            line,
            "P6DQ A41EE RING[%u] seq=%u site=%u owner=%08X arg1=%08X",
            (unsigned int)i,
            (unsigned int)row->sequence,
            (unsigned int)row->site,
            (unsigned int)row->owner,
            (unsigned int)row->arg1);
        trace(line);
    }

    for (i = 0u; i < s_phase6dqDispatchJournalCount; ++i)
    {
        Phase6DQDispatchJournal* row = &s_phase6dqDispatchJournal[i];
        sprintf(
            line,
            "P6DQ ROCKET JOURNAL DISPATCH[%u] kind=%s caller=%08X target=%08X hits=%u first_esp=%08X last_esp=%08X",
            (unsigned int)i,
            row->kind == 1u ? "ICALL" : "DIRECT",
            (unsigned int)row->caller,
            (unsigned int)row->target,
            (unsigned int)row->hits,
            (unsigned int)row->firstEsp,
            (unsigned int)row->lastEsp);
        trace(line);
    }

    for (i = 0u; i < s_phase6dqVpJournalCount; ++i)
    {
        Phase6DQVpJournal* row = &s_phase6dqVpJournal[i];
        sprintf(
            line,
            "P6DQ ROCKET JOURNAL VP[%u] addr=%08X method=%04X name=%s hits=%u first=%08X last=%08X first_caller=%08X last_caller=%08X first_esp=%08X last_esp=%08X",
            (unsigned int)i,
            (unsigned int)row->address,
            (unsigned int)(row->address - 0xFE820000u),
            phase6dq_vp_method_name(row->address - 0xFE820000u),
            (unsigned int)row->hits,
            (unsigned int)row->firstValue,
            (unsigned int)row->lastValue,
            (unsigned int)row->firstCaller,
            (unsigned int)row->lastCaller,
            (unsigned int)row->firstEsp,
            (unsigned int)row->lastEsp);
        trace(line);
    }

    for (i = 0u; i < s_phase6dqHardStopJournalCount; ++i)
    {
        Phase6DQHardStopJournal* row = &s_phase6dqHardStopJournal[i];
        sprintf(
            line,
            "P6DQ ROCKET JOURNAL HARD[%u] kind=%u caller=%08X target=%08X hits=%u esp=%08X ticks=%u eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X",
            (unsigned int)i,
            (unsigned int)row->kind,
            (unsigned int)row->caller,
            (unsigned int)row->target,
            (unsigned int)row->hits,
            (unsigned int)row->savedEsp,
            (unsigned int)row->ticks,
            (unsigned int)row->eaxValue,
            (unsigned int)row->ecxValue,
            (unsigned int)row->edxValue,
            (unsigned int)row->ebxValue,
            (unsigned int)row->esiValue,
            (unsigned int)row->ediValue);
        trace(line);
    }
}
'''
    return text[:end] + support + text[end:]


def patch_escape_journal(text: str) -> str:
    # Do not patch phase4c_escape itself. That function's exact generated shape
    # has evolved across Phase 6 and is intentionally treated as opaque here.
    # Instead, journal at the existing escaped-boundary report, where Phase4C
    # has already published the stable boundary globals and register state.
    marker = (
        '"BOUNDARY: kind=%s caller=%08X target=%08X esp=%08X '
        'saved_esp=%08X ticks=%u trace=%u"'
    )
    if text.count(marker) != 1:
        raise SystemExit(
            f"[Phase6DQ] expected one escaped boundary report, found {text.count(marker)}"
        )

    marker_pos = text.find(marker)
    sprintf_pos = text.rfind("sprintf(", 0, marker_pos)
    if sprintf_pos < 0:
        raise SystemExit("[Phase6DQ] escaped boundary sprintf anchor missing")

    line_start = text.rfind("\n", 0, sprintf_pos) + 1
    indent = text[line_start:sprintf_pos]
    if indent.strip():
        raise SystemExit("[Phase6DQ] escaped boundary sprintf indentation malformed")

    hook = (
        f"{indent}phase6dq_note_hard_stop(\n"
        f"{indent}    s_phase4cBoundaryKind,\n"
        f"{indent}    s_phase4cBoundaryTarget,\n"
        f"{indent}    s_phase4cBoundaryCaller,\n"
        f"{indent}    s_phase4cBoundarySavedEsp);\n\n"
    )
    text = text[:line_start] + hook + text[line_start:]

    if text.count("phase6dq_note_hard_stop(") != 2:
        # One definition + exactly one call site.
        raise SystemExit("[Phase6DQ] hard-stop journal definition/call count mismatch")

    return text

def patch_dispatch_journal(text: str) -> str:
    # Hook the actual packed call in each dispatcher. Do not depend on the
    # surrounding Phase-5/Phase-6 bookkeeping layout, which has evolved.
    sig = "static void phase5bc_dispatch_packed_icall("
    start, end = function_span(text, sig)
    body = text[start:end]

    # R15 hardware crossed the IOAPIC default-offset batch and immediately
    # reached Xbox kernel ordinal 151 (0x80000097), KeStallExecutionProcessor.
    # Handle this maintained one-argument stdcall before pack lookup so the
    # kernel thunk does not become a translated-function frontier.
    lookup_anchor = "    recomp_func_t fn = phase4c_lookup_pack_func(target);\n"
    stall_hook = r'''    if (target == 0xF6DCCCD0u)
    {
        phase6dq_dsound_poison_noop(savedEsp);
        return;
    }

    if (target == 0x8000008Eu)
    {
        phase6dq_ke_save_floating_point_state(savedEsp);
        return;
    }

    if (target == 0x8000008Bu)
    {
        phase6dq_ke_restore_floating_point_state(savedEsp);
        return;
    }

    if (target == 0x80000097u)
    {
        phase6dq_ke_stall_execution_processor(savedEsp);
        return;
    }

'''
    body = replace_once(
        body,
        lookup_anchor,
        stall_hook + lookup_anchor,
        "KeStallExecutionProcessor ordinal-151 ICALL bridge",
    )
    text = text[:start] + body + text[end:]

    start, end = function_span(text, sig)
    body = text[start:end]
    call_pattern = re.compile(r"(?m)^(?P<indent>[ \t]*)fn\s*\(\s*\)\s*;")
    calls = list(call_pattern.finditer(body))
    if len(calls) != 1:
        raise SystemExit(
            f"[Phase6DQ] expected one packed ICALL fn() call, found {len(calls)}"
        )
    m = calls[0]
    indent = m.group("indent")
    hook = (
        f"{indent}phase6dq_note_dispatch(\n"
        f"{indent}    1u,\n"
        f"{indent}    target,\n"
        f"{indent}    phase4c_current_caller(),\n"
        f"{indent}    savedEsp);\n"
    )
    body = body[:m.start()] + hook + body[m.start():]
    text = text[:start] + body + text[end:]

    sig = "static void phase4c_direct_frontier(uint32_t target)"
    start, end = function_span(text, sig)
    body = text[start:end]
    calls = list(call_pattern.finditer(body))
    if len(calls) != 1:
        raise SystemExit(
            f"[Phase6DQ] expected one packed DIRECT fn() call, found {len(calls)}"
        )
    m = calls[0]
    indent = m.group("indent")
    hook = (
        f"{indent}phase6dq_note_dispatch(\n"
        f"{indent}    2u,\n"
        f"{indent}    target,\n"
        f"{indent}    phase4c_current_caller(),\n"
        f"{indent}    g_esp);\n"
    )
    body = body[:m.start()] + hook + body[m.start():]
    text = text[:start] + body + text[end:]
    return text


def patch_quiet_logging(text: str) -> str:
    text = replace_once(
        text,
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFFu) == 0u",
        "ICALL 65536-stride logging",
    )
    text = replace_once(
        text,
        "(s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u",
        "(s_phase5bcPackedDirectDispatchCount & 0xFFFFu) == 0u",
        "DIRECT 65536-stride logging",
    )
    return text


def patch_vp_accesses(text: str) -> str:
    # Unknown VP reads remain authoritative hard fences, but identify them
    # before they enter the checked guest-access router.
    for sig, width, fallback in (
        (
            "static uint8_t phase6ch_apu_read8(uint32_t address)",
            1,
            "    return GUEST_READ8(address);\n",
        ),
        (
            "static uint16_t phase6ch_apu_read16(uint32_t address)",
            2,
            "    return GUEST_READ16(address);\n",
        ),
        (
            "static uint32_t phase6ch_apu_read32(uint32_t address)",
            4,
            "    return GUEST_READ32(address);\n",
        ),
    ):
        start, end = function_span(text, sig)
        body = text[start:end]
        probe = f"""    if (address >= 0xFE820000u &&
        address < 0xFE830000u)
        phase6dq_note_vp_unknown_read(address, {width}u);

"""
        if fallback not in body:
            raise SystemExit(
                f"[Phase6DQ] checked fallback missing in {sig}"
            )
        body = body.replace(fallback, probe + fallback, 1)
        text = text[:start] + body + text[end:]

    # Hardware R12/R13 proved a contiguous IOAPIC access sequence at
    # FEC0012C -> FEC00130. xemu/QEMU masks the 4 KiB IOAPIC page address to
    # the low byte; only 0x00 (IOREGSEL), 0x10 (IOWIN), and 0x40 (EOI write)
    # carry device semantics. Batch-consume every other offset using the exact
    # default behavior (read zero / write no-op) and keep those special
    # register offsets hard-fenced.
    for sig, width, fallback in (
        (
            "static uint8_t phase6ch_apu_read8(uint32_t address)",
            1,
            "    return GUEST_READ8(address);\n",
        ),
        (
            "static uint16_t phase6ch_apu_read16(uint32_t address)",
            2,
            "    return GUEST_READ16(address);\n",
        ),
        (
            "static uint32_t phase6ch_apu_read32(uint32_t address)",
            4,
            "    return GUEST_READ32(address);\n",
        ),
    ):
        start, end = function_span(text, sig)
        body = text[start:end]
        ioapic_patch = f"""    if (phase6dq_ioapic_is_default_offset(address))
        return ({'uint8_t' if width == 1 else 'uint16_t' if width == 2 else 'uint32_t'})phase6dq_ioapic_default_read(address, {width}u);

    if (phase6dq_ioapic_is_page(address))
        phase6dq_note_ioapic_special_fence(address, {width}u, 0u, 0u);

"""
        body = replace_once(
            body,
            fallback,
            ioapic_patch + fallback,
            f"IOAPIC default READ{width * 8} batch bridge",
        )
        text = text[:start] + body + text[end:]

    # VP writes are command-style. For the rocket diagnostic run, consume
    # aligned dword writes after journaling rather than faulting one method per
    # hardware build. Preserve one proven scalar side effect from xemu:
    # SET_CURRENT_VOICE updates the APU FECV core register.
    sig = "static void phase6ch_apu_write32(uint32_t address, uint32_t value)"
    start, end = function_span(text, sig)
    body = text[start:end]
    fallback = "    GUEST_WRITE32(address, value);\n"
    patch = r'''    if (address >= 0xFE820000u &&
        address < 0xFE830000u &&
        (address & 3u) == 0u)
    {
        uint32_t offset = address - 0xFE820000u;

        if (offset == 0x000002F8u)
            s_phase6chApuRegs[0x00001110u >> 2] = value;

        phase6dq_note_vp_write(
            address,
            value,
            phase4c_current_caller(),
            g_esp);
        return;
    }

'''
    body = replace_once(
        body, fallback, patch + fallback, "VP WRITE32 safe-continue"
    )

    # Batch the xemu/QEMU default IOAPIC write class. Special offsets remain
    # hard-fenced and are journaled before the checked router reports them.
    ioapic_write_patch = r'''    if (phase6dq_ioapic_is_default_offset(address))
    {
        phase6dq_ioapic_default_write(address, 4u, value);
        return;
    }

    if (phase6dq_ioapic_is_page(address))
        phase6dq_note_ioapic_special_fence(address, 4u, 1u, value);

'''
    body = replace_once(
        body,
        fallback,
        ioapic_write_patch + fallback,
        "IOAPIC default WRITE32 batch bridge",
    )
    text = text[:start] + body + text[end:]

    # 8/16-bit VP writes remain hard fenced; add identification only.
    for sig, width, fallback in (
        (
            "static void phase6ch_apu_write8(uint32_t address, uint8_t value)",
            1,
            "    GUEST_WRITE8(address, value);\n",
        ),
        (
            "static void phase6ch_apu_write16(uint32_t address, uint16_t value)",
            2,
            "    GUEST_WRITE16(address, value);\n",
        ),
    ):
        start, end = function_span(text, sig)
        body = text[start:end]
        probe = f"""    if (phase6dq_ioapic_is_default_offset(address))
    {{
        phase6dq_ioapic_default_write(address, {width}u, (uint32_t)value);
        return;
    }}

    if (phase6dq_ioapic_is_page(address))
        phase6dq_note_ioapic_special_fence(address, {width}u, 1u, (uint32_t)value);

    if (address >= 0xFE820000u &&
        address < 0xFE830000u)
        phase6dq_note_vp_unknown_read(address, {width}u);

"""
        body = replace_once(
            body, fallback, probe + fallback, f"VP/IOAPIC WRITE{width * 8} hard fence"
        )
        text = text[:start] + body + text[end:]

    return text



def patch_dsound_poison_slot_dispatch(text: str, base) -> str:
    """Quarantine only the hardware-proven poisoned DSOUND virtual-dispatch site."""
    sig = "static void sub_002A41EE(void)"

    # main_monolithic.cpp contains a forward declaration before the real body.
    # Locate the exact definition by requiring the next non-whitespace token
    # after the signature to be '{', not ';'.
    start = -1
    search_pos = 0
    definition_count = 0
    while True:
        pos = text.find(sig, search_pos)
        if pos < 0:
            break
        cursor = pos + len(sig)
        while cursor < len(text) and text[cursor].isspace():
            cursor += 1
        if cursor < len(text) and text[cursor] == "{":
            start = pos
            definition_count += 1
        search_pos = pos + len(sig)

    if definition_count != 1 or start < 0:
        raise SystemExit(
            f"[Phase6DQ] expected exactly one sub_002A41EE definition, found {definition_count}"
        )

    masked = base.mask_noncode(text)
    brace = masked.find("{", start)
    if brace < 0:
        raise SystemExit("[Phase6DQ] sub_002A41EE definition opening brace missing")
    end = base.closing_brace(masked, brace)
    body = text[start:end]

    # R22 preflight exposed the exact generated source for the R16 hardware
    # fault. At loc_002A41F7 the object dispatch pointer is loaded into eax:
    #
    #   eax = phase6ch_apu_read32(esi);
    #   ...
    #   PUSH32(esp, 0);
    #   PHASE6DJ_ICALL_SAFE(
    #       phase6df_function_va,
    #       phase6ch_apu_read32(eax + 4),
    #       _icall_esp);
    #
    # The CCCCCCD0 fault comes from evaluating that inline target expression
    # with eax == CCCCCCCC. Guard only this exact label/callsite so the poison
    # path never evaluates eax+4. Normal objects keep the original slot read.
    label = "loc_002A41F7: ;"
    label_pos = body.find(label)
    if label_pos < 0:
        raise SystemExit("[Phase6DQ] DSOUND poison label loc_002A41F7 missing")

    next_label = body.find("loc_002A41FD: ;", label_pos)
    if next_label < 0:
        raise SystemExit("[Phase6DQ] DSOUND poison successor label loc_002A41FD missing")

    window = body[label_pos:next_label]

    if window.count("eax = phase6ch_apu_read32(esi);") != 1:
        print("[Phase6DQ] 002A41F7 source window:")
        for line in window.splitlines():
            print("[Phase6DQ]   " + line)
        raise SystemExit(
            "[Phase6DQ] expected exact DSOUND dispatch-base load at 002A41F7"
        )

    call_re = re.compile(
        r"(?P<indent>[ \t]*)PUSH32\(\s*esp\s*,\s*0\s*\)\s*;\s*"
        r"PHASE6DJ_ICALL_SAFE\(\s*phase6df_function_va\s*,\s*"
        r"phase6ch_apu_read32\(\s*eax\s*\+\s*(?:4|4u|0x4|0x04)\s*\)\s*,\s*"
        r"_icall_esp\s*\)\s*;"
    )
    calls = list(call_re.finditer(window))
    if len(calls) != 1:
        print(
            f"[Phase6DQ] 002A41F7 inline poison ICALL candidate count={len(calls)}"
        )
        print("[Phase6DQ] 002A41F7 source window:")
        for line in window.splitlines():
            print("[Phase6DQ]   " + line)
        raise SystemExit(
            "[Phase6DQ] expected exactly one inline DSOUND eax+4 ICALL at 002A41F7"
        )

    m = calls[0]
    indent = m.group("indent")
    replacement = (
        f"{indent}PUSH32(esp, 0);\n"
        f"{indent}{{\n"
        f"{indent}    uint32_t phase6dqDsoundBase =\n"
        f"{indent}        phase6dq_dsound_poison_dispatch_target(eax, esi, ecx);\n"
        f"{indent}    if (phase6dqDsoundBase == 0xF6DCCCD0u)\n"
        f"{indent}    {{\n"
        f"{indent}        phase6dq_dsound_poison_noop(_icall_esp);\n"
        f"{indent}    }}\n"
        f"{indent}    else\n"
        f"{indent}    {{\n"
        f"{indent}        PHASE6DJ_ICALL_SAFE(\n"
        f"{indent}            phase6df_function_va,\n"
        f"{indent}            phase6ch_apu_read32(phase6dqDsoundBase + 4u),\n"
        f"{indent}            _icall_esp);\n"
        f"{indent}    }}\n"
        f"{indent}}}"
    )

    local_start = label_pos + m.start()
    local_end = label_pos + m.end()
    body = body[:local_start] + replacement + body[local_end:]

    if body.count("phase6dq_dsound_poison_dispatch_target(eax, esi, ecx)") != 1:
        raise SystemExit("[Phase6DQ] DSOUND poison callsite guard count mismatch")
    if body.count("phase6dq_dsound_poison_noop(_icall_esp);") != 1:
        raise SystemExit("[Phase6DQ] DSOUND poison local no-op count mismatch")
    if "phase6ch_apu_read32(eax + 4)" in body[label_pos:next_label + 900]:
        raise SystemExit("[Phase6DQ] stale unguarded eax+4 DSOUND target remains")

    return text[:start] + body + text[end:]


def route_all_dsound_accesses(text: str, base) -> tuple[str, dict[str, int]]:
    """Route raw guest accesses in every translated DSOUND sub_* through APU wrappers."""
    masked = base.mask_noncode(text)
    replacements: list[tuple[int, int, str]] = []
    counts = {
        "read8": 0,
        "read16": 0,
        "read32": 0,
        "write8": 0,
        "write16": 0,
        "write32": 0,
        "functions": 0,
    }

    macros = (
        ("GUEST_READ8(", "phase6ch_apu_read8(", "read8"),
        ("GUEST_READ16(", "phase6ch_apu_read16(", "read16"),
        ("GUEST_READ32(", "phase6ch_apu_read32(", "read32"),
        ("GUEST_WRITE8(", "phase6ch_apu_write8(", "write8"),
        ("GUEST_WRITE16(", "phase6ch_apu_write16(", "write16"),
        ("GUEST_WRITE32(", "phase6ch_apu_write32(", "write32"),
    )

    for match in base.FUNC_RE.finditer(masked):
        name = match.group(1)
        m = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if not m:
            continue
        va = int(m.group(1), 16)
        if not (DSOUND_START <= va < DSOUND_END):
            continue

        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            continue
        end = base.closing_brace(masked, open_index)
        source = text[match.start():end]
        changed = source
        local = 0
        for old, new, key in macros:
            n = changed.count(old)
            if n:
                changed = changed.replace(old, new)
                counts[key] += n
                local += n
        if local:
            counts["functions"] += 1
            replacements.append((match.start(), end, changed))

    for start, end, changed in reversed(replacements):
        text = text[:start] + changed + text[end:]

    return text, counts


def insert_final_dump(text: str) -> str:
    anchor = "    phase6aw_dump_va_ring();\n"
    return replace_once(
        text,
        anchor,
        "    phase6dq_dump_journals();\n" + anchor,
        "rocket final journal dump",
    )


def update_vp_summary(text: str) -> str:
    old = (
        "P6DP APU VP: free_reads=%u last_addr=%08X last_value=%08X "
        "other_vp_accesses_fenced=1"
    )
    new = (
        "P6DQ APU VP: free_reads=%u last_addr=%08X last_value=%08X "
        "vp_write32_diagnostic_continue=1 unknown_vp_reads_fenced=1"
    )
    return replace_once(text, old, new, "VP summary policy")


def relabel(text: str) -> str:
    text = replace_once(text, BASE_TAG, BUILD_TAG, "6DP build tag")
    text = text.replace(COOKIE_OLD, COOKIE_NEW)
    return (
        text.replace("PHASE 6DP", "PHASE 6DQ")
        .replace("Phase 6DP", "Phase 6DQ")
        .replace('"P6DP ', '"P6DQ ')
    )


def assert_no_newline_in_c_string(text: str) -> None:
    """Reject accidental physical newlines inside ordinary C/C++ string literals."""
    i = 0
    line = 1
    in_string = False
    in_char = False
    line_comment = False
    block_comment = False
    escaped = False
    string_line = 0

    while i < len(text):
        ch = text[i]
        nxt = text[i + 1] if i + 1 < len(text) else ""

        if line_comment:
            if ch == "\n":
                line_comment = False
                line += 1
            i += 1
            continue

        if block_comment:
            if ch == "*" and nxt == "/":
                block_comment = False
                i += 2
                continue
            if ch == "\n":
                line += 1
            i += 1
            continue

        if in_string:
            if ch == "\n":
                if not escaped:
                    raise SystemExit(
                        f"[Phase6DQ] generated C string literal crosses physical newline "
                        f"(opened line {string_line}, reached line {line})"
                    )
                escaped = False
                line += 1
                i += 1
                continue
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == '"':
                in_string = False
            i += 1
            continue

        if in_char:
            if ch == "\n":
                raise SystemExit(
                    f"[Phase6DQ] generated C character literal crosses physical newline "
                    f"at line {line}"
                )
            if escaped:
                escaped = False
            elif ch == "\\":
                escaped = True
            elif ch == "'":
                in_char = False
            i += 1
            continue

        if ch == "/" and nxt == "/":
            line_comment = True
            i += 2
            continue
        if ch == "/" and nxt == "*":
            block_comment = True
            i += 2
            continue
        if ch == '"':
            in_string = True
            string_line = line
            escaped = False
            i += 1
            continue
        if ch == "'":
            in_char = True
            escaped = False
            i += 1
            continue
        if ch == "\n":
            line += 1
        i += 1

    if in_string:
        raise SystemExit(
            f"[Phase6DQ] generated C string literal is unterminated "
            f"(opened line {string_line})"
        )
    if in_char:
        raise SystemExit("[Phase6DQ] generated C character literal is unterminated")
    if block_comment:
        raise SystemExit("[Phase6DQ] generated C block comment is unterminated")

def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--base-dir", type=Path, required=True)
    ap.add_argument("--base-emitter", type=Path, required=True)
    ap.add_argument("--phase5bb-emitter", type=Path, required=True)
    ap.add_argument("--phase5bc-emitter", type=Path, required=True)
    ap.add_argument("--phase6bl-emitter", type=Path, required=True)
    ap.add_argument("--generated-root", type=Path, required=True)
    ap.add_argument("--functions", type=Path, required=True)
    ap.add_argument("--out-dir", type=Path, required=True)
    args = ap.parse_args()

    base = load(args.base_emitter, "phase6dq_base")
    p5bb = load(args.phase5bb_emitter, "phase6dq_p5bb")
    p5bc = load(args.phase5bc_emitter, "phase6dq_p5bc")
    p6bl = load(args.phase6bl_emitter, "phase6dq_p6bl")

    main_path = args.base_dir / "main_monolithic.cpp"
    env_path = args.base_dir / "phase5_env.cpp"
    manifest_path = args.base_dir / "phase6dp-manifest.json"
    for p in (main_path, env_path, manifest_path):
        if not p.exists():
            raise SystemExit(f"[Phase6DQ] missing 6DP input: {p}")

    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    if manifest.get("phase") != "6DP" or manifest.get("build_tag") != BASE_TAG:
        raise SystemExit("[Phase6DQ] cached 6DP identity mismatch")

    dp = manifest.get("phase6dp_apu_vp_free") or {}
    if (
        dp.get("hardware_proof", {}).get("old_failure_eliminated")
        != "0xCCCCCCD0"
        or dp.get("register_identity", {}).get("address") != "0xFE820010"
        or dp.get("register_identity", {}).get("read_value") != "0x00000080"
        or dp.get("xact_refcount_semantics_changed") is not False
        or dp.get("guest_memory_fences_changed") is not False
        or dp.get("execution_budget_inherited") != 64000000
    ):
        raise SystemExit("[Phase6DQ] inherited 6DP policy mismatch")

    main_text = main_path.read_text(encoding="utf-8")
    env_text = env_path.read_text(encoding="utf-8")

    for marker in (
        BASE_TAG,
        COOKIE_OLD,
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "#pragma warning(disable:4146)",
        "P6DP APU VP READ32",
        "other_vp_accesses_fenced=1",
        "static void phase5bc_dispatch_packed_icall(",
        "static void phase4c_direct_frontier(uint32_t target)",
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
        "(s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u",
        "P6DP PIXEL CHASE:",
        "P6DP PRESENT PROXIMITY:",
    ):
        if marker not in main_text:
            raise SystemExit(f"[Phase6DQ] inherited marker missing: {marker}")

    by_va, by_name = base.load_ranges(args.functions)
    generated = base.load_generated(args.generated_root, by_name)
    old = {int(x, 0) for x in manifest.get("members", [])}
    existing_defs = set(base.support_symbols(main_text))

    predictive_seeds = predictive_seed_vas(generated)
    predictive_candidates = build_predictive_candidates(
        predictive_seeds, old, generated, base, p5bb
    )

    broad_candidates, available_counts, selected_counts = select_candidates(
        generated,
        old | set(predictive_candidates),
        existing_defs,
    )
    candidates = list(predictive_candidates)
    for va in broad_candidates:
        if va not in candidates and len(candidates) < CANDIDATE_CAP:
            candidates.append(va)

    expanded = old | set(candidates)
    new_members = list(candidates)

    if candidates:
        base.STANDARD_CALLS.add("sin")
        base.STANDARD_CALLS.add("cos")
        p5bc.SWEEP_ROOT = 0xFFFFFFFF
        p5bc.instrument_root_entry = lambda rendered, name: rendered

        # Phase5BC normally prints every pruned function. ROCKET preserves the
        # complete prune inventory in phase6dq-manifest.json but keeps prep
        # output compact so useful failures are not buried under hundreds of
        # expected support-clean fence lines.
        sweep_output = io.StringIO()
        try:
            with contextlib.redirect_stdout(sweep_output), contextlib.redirect_stderr(
                sweep_output
            ):
                main_text, rendered, frontiers, pruned = p5bc.insert_pack_members(
                    main_text,
                    base,
                    p5bb,
                    generated,
                    new_members,
                    expanded,
                    require_sweep_root=False,
                )
        except BaseException:
            buffered = sweep_output.getvalue().splitlines()
            if buffered:
                print("[Phase6DQ] Phase5BC buffered failure tail:")
                for line in buffered[-40:]:
                    print(line)
            raise
    else:
        rendered = {}
        frontiers = set()
        pruned = {}

    # Runtime rocket layer.
    main_text = install_journal_support(main_text)
    main_text = patch_dsound_poison_slot_dispatch(main_text, base)
    main_text = patch_escape_journal(main_text)
    main_text = patch_dispatch_journal(main_text)
    main_text = patch_quiet_logging(main_text)
    main_text = patch_vp_accesses(main_text)
    main_text, dsound_route_counts = route_all_dsound_accesses(main_text, base)
    predictive_audit = predictive_static_audit(main_text, base)
    main_text, a41ee_site_map = instrument_a41ee_callsites(main_text, base)
    by_site_id = {
        int(row["site_id"]): row
        for row in predictive_audit["audio_direct_call_sites"]
    }
    for row in a41ee_site_map:
        detail = by_site_id.get(int(row["site_id"]))
        if detail:
            row["arg1_expression"] = detail["arg1_expression"]
            row["arg1_kind"] = detail["arg1_kind"]
    main_text = insert_final_dump(main_text)
    main_text = update_vp_summary(main_text)

    old_policy_prefix = "Policy: Phase 6DP "
    policy_pos = main_text.find(old_policy_prefix)
    if policy_pos < 0:
        raise SystemExit("[Phase6DQ] inherited runtime policy line missing")
    policy_line_end = main_text.find("\n", policy_pos)
    if policy_line_end < 0:
        policy_line_end = len(main_text)
    policy_quote_end = main_text.find('"', policy_pos)
    if policy_quote_end < 0 or policy_quote_end > policy_line_end:
        raise SystemExit("[Phase6DQ] inherited runtime policy closing quote missing")
    new_policy_payload = (
        "Policy: Phase 6DQ ROCKET carries the hardware-proven 6DP VP FREE success, "
        "batch-packs up to 4096 additional support-clean D3D/XGRPH/DSOUND/XACTENG "
        "functions, journals unique packed dispatches and hard stops, diagnostic-"
        "continues aligned VP WRITE32 commands while unknown VP reads remain hard "
        "fences, preserves 64M/C4146/allocator/XACT/NV2A semantics, and prioritizes "
        "maximum trustworthy progress toward guest presentation per hardware run; "
        "R27 adds call-shape-filtered predictive provenance audits while unknown "
        "kernel calls, MMIO and reads remain hard fences"
    )
    # Replace only the payload inside the existing C string literal. Preserve
    # the closing quote, parenthesis and semicolon from the inherited trace().
    main_text = (
        main_text[:policy_pos]
        + new_policy_payload
        + main_text[policy_quote_end:]
    )

    main_text = relabel(main_text)
    env_text = (
        env_text.replace(COOKIE_OLD, COOKIE_NEW)
        .replace("PHASE 6DP", "PHASE 6DQ")
        .replace("Phase 6DP", "Phase 6DQ")
    )

    required = (
        BUILD_TAG,
        COOKIE_NEW,
        "PHASE6DQ_DISPATCH_JOURNAL_CAP 96u",
        "P6DQ ROCKET DISPATCH FIRST",
        "P6DQ ROCKET HARD STOP",
        "P6DQ ROCKET VP WRITE FIRST",
        "P6DQ ROCKET VP READ HARD",
        "P6DQ ROCKET JOURNAL SUMMARY",
        "phase6dq_dump_journals();",
        "address >= 0xFE820000u",
        "address < 0xFE830000u",
        "s_phase6chApuRegs[0x00001110u >> 2] = value;",
        "(s_phase5bcPackedIcallDispatchCount & 0xFFFFu) == 0u",
        "(s_phase5bcPackedDirectDispatchCount & 0xFFFFu) == 0u",
        "vp_write32_diagnostic_continue=1 unknown_vp_reads_fenced=1",
        "P6DQ PIXEL CHASE:",
        "P6DQ PRESENT PROXIMITY:",
        "P6DQ ROCKET IOAPIC DEFAULT READ width=%u addr=%08X",
        "P6DQ ROCKET IOAPIC DEFAULT WRITE width=%u addr=%08X",
        "P6DQ ROCKET IOAPIC SPECIAL HARD %s width=%u addr=%08X",
        "target == 0x80000097u",
        "target == 0x8000008Eu",
        "target == 0x8000008Bu",
        "P6DQ KESAVEFP142: calls=%u state=%08X",
        "P6DQ KERESTOREFP139: calls=%u state=%08X",
        "P6DQ KESTALL151: calls=%u us=%u",
        "microSeconds > 1000000u",
        "static void sub_002A41EE(void)",
        "loc_002A41F7: ;",
        "phase6dq_dsound_poison_dispatch_target(eax, esi, ecx)",
        "phase6dq_dsound_poison_noop(_icall_esp);",
        "phase6ch_apu_read32(phase6dqDsoundBase + 4u)",
        "target == 0xF6DCCCD0u",
        "P6DQ DSOUND POISON SLOT:",
        "P6DQ DSOUND POISON NOOP:",
        "P6DQ A41EE CALLSITE:",
        "P6DQ A41EE RING[%u]",
        "R27 adds call-shape-filtered predictive provenance audits",
        "#define PHASE4C_EXEC_BUDGET 64000000u",
        "#pragma warning(disable:4146)",
    )
    for marker in required:
        if marker not in main_text:
            raise SystemExit(f"[Phase6DQ] generated source lost marker: {marker}")

    if "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u" in main_text:
        raise SystemExit("[Phase6DQ] stale 4096 ICALL logging cadence remains")
    if "(s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u" in main_text:
        raise SystemExit("[Phase6DQ] stale 4096 DIRECT logging cadence remains")

    assert_no_newline_in_c_string(main_text)

    args.out_dir.mkdir(parents=True, exist_ok=True)
    layout = p6bl.write_sharded_main(args.out_dir, main_text, base)
    (args.out_dir / "phase5_env.cpp").write_text(env_text, encoding="utf-8")

    final_members = old | set(new_members)
    manifest.update(
        {
            "phase": "6DQ",
            "build_tag": BUILD_TAG,
            "pack_members": len(final_members),
            "members": [f"0x{x:08X}" for x in sorted(final_members)],
        }
    )
    manifest["phase6dq_rocket_frontier_journal"] = {
        "source_phase": "6DP",
        "emitter_revision": EMITTER_REVISION,
        "phase6dp_hardware": {
            "vp_free_read_passed": True,
            "vp_free_address": "0xFE820010",
            "vp_free_value": "0x00000080",
            "new_boundary_kind": "GUEST_FAULT",
            "new_boundary_access": "WRITE32",
            "new_boundary_target": "0xFE8202A4",
            "new_boundary_ticks": 26712259,
            "historical_ccccccd0_observed": False,
            "xact_final_release_entries": 0,
            "xact_global_zero_writes": 0,
            "xenos_ready": True,
            "display_calls": 0,
            "framebuffer": "0x00000000",
        },
        "static_pack": {
            "candidate_cap": CANDIDATE_CAP,
            "base_pack_members": len(old),
            "candidate_members": len(candidates),
            "packed_new_members": len(new_members),
            "pruned_members": len(pruned),
            "expanded_pack_members": len(final_members),
            "available_by_section": available_counts,
            "selected_by_section_before_prune": selected_counts,
            "new_direct_frontier_targets": [
                f"0x{x:08X}" for x in sorted(frontiers)
            ],
            "priority": [
                "D3D", "XGRPH", "DSOUND", "TEXT_HOT",
                "XACTENG", "WMADEC", "XPP", "XMV"
            ],
        },
        "runtime_journal": {
            "dispatch_unique_capacity": 96,
            "hard_stop_unique_capacity": 24,
            "vp_write_unique_capacity": 64,
            "first_unique_logged_immediately": True,
            "final_aggregate_dump": True,
            "register_context_on_hard_stop": True,
            "dispatch_log_stride": 65536,
        },
        "kernel_timing_bridge": {
            "target": "0x80000097",
            "ordinal": 151,
            "name": "KeStallExecutionProcessor",
            "argument": "ULONG MicroSeconds",
            "calling_convention": "stdcall",
            "implementation": "QPC-backed busy-wait",
            "hardware_seed_ticks": 26712270,
            "hardware_seed_microseconds": 20,
            "hardware_seed_calls": 1000,
            "hardware_seed_total_microseconds": 20000,
            "max_safe_microseconds": 1000000,
            "unreasonable_duration_fenced": True,
        },
        "kernel_fp_guard_bridge": {
            "save_target": "0x8000008E",
            "save_ordinal": 142,
            "save_name": "KeSaveFloatingPointState",
            "restore_target": "0x8000008B",
            "restore_ordinal": 139,
            "restore_name": "KeRestoreFloatingPointState",
            "argument": "PVOID State",
            "calling_convention": "stdcall",
            "hardware_seed_ticks": 27025618,
            "serialized_runtime_no_kernel_fp_context_switch": True,
            "opaque_guest_state_layout_fabricated": False,
            "pointer_nesting_guard": True,
            "max_nesting": 8,
            "mismatch_hard_fenced": True,
            "journal_summary_buffer_bytes": 1024,
            "result": "STATUS_SUCCESS",
        },
        "dsound_poison_slot_bridge": {
            "hardware_seed_ticks": 27025451,
            "translated_function": "0x002A41EE",
            "fault_site": "0x002A41F7",
            "poison_value": "0xCCCCCCCC",
            "historical_fault_address": "0xCCCCCCD0",
            "synthetic_noop_target": "0xF6DCCCD0",
            "scope": "exact hardware-proven DSOUND dispatch site only",
            "emitter_source_shape_guard": True,
            "definition_not_forward_declaration_guard": True,
            "exact_label_guard": "0x002A41F7",
            "inline_icall_target_shape_proven": True,
            "local_short_circuit_before_slot_read": True,
            "guarded_dereference_postcheck": True,
            "whitespace_tolerant_icall_guard": True,
            "result": "DS_OK",
            "saved_esp_restored": True,
            "ordinary_guest_faults_bypassed": False,
            "unrelated_poison_values_bypassed": False,
        },
        "predictive_frontier_clearing": {
            **predictive_audit,
            "seed_count": len(predictive_seeds),
            "predictive_candidate_count": len(predictive_candidates),
            "closure_depth": PREDICTIVE_CLOSURE_DEPTH,
            "closure_cap_per_seed": PREDICTIVE_CLOSURE_CAP_PER_SEED,
            "broad_sweep_runs_after_predictive_priority": True,
            "runtime_a41ee_callsite_probe": True,
            "runtime_a41ee_site_map": a41ee_site_map,
            "runtime_fault_policy_changed": False,
        },
        "vp_diagnostic_continue": {
            "aligned_write32_continue": True,
            "write32_semantics_complete": False,
            "current_voice_scalar_side_effect": True,
            "unknown_read8_fenced": True,
            "unknown_read16_fenced": True,
            "unknown_read32_fenced": True,
            "write8_fenced": True,
            "write16_fenced": True,
            "reference_model_note": (
                "xemu VP write default ignores unrecognized methods; 6DQ uses "
                "write-only diagnostic continuation to avoid one-build-per-command"
            ),
            "audio_fidelity_claimed": False,
        },
        "dsound_apu_routing": dsound_route_counts,
        "execution_budget": 64000000,
        "generated_c4146_scope_inherited": True,
        "allocator_repairs_inherited": True,
        "xact_refcount_semantics_changed": False,
        "destructor_suppressed": False,
        "free_suppressed": False,
        "ordinary_guest_memory_fences_changed": False,
        "vp_write32_fence_changed_for_diagnostics": True,
        "unknown_vp_read_fences_changed": False,
        "non_vp_mmio_fences_changed": False,
        "nv2a_mmio_policy_changed": False,
        "source_layout": layout,
    }
    manifest["phase6dq_candidate_new_members"] = [
        f"0x{x:08X}" for x in candidates
    ]
    manifest["phase6dq_new_members"] = [
        f"0x{x:08X}" for x in sorted(new_members)
    ]
    manifest["phase6dq_pruned_members"] = [
        {
            "address": f"0x{va:08X}",
            "name": generated[va]["name"],
            "unresolved_support": names,
        }
        for va, names in sorted(pruned.items())
    ]

    (args.out_dir / "phase6dq-predictive-audit.json").write_text(
        json.dumps(predictive_audit, indent=2) + "\n",
        encoding="utf-8",
    )
    (args.out_dir / "phase6dq-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_source = sum(len(rendered.get(va, "")) for va in new_members)
    print(f"[Phase6DQ] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DQ] ROCKET PHASE: ENABLED")
    print_predictive_audit(predictive_audit)
    print(
        f"[Phase6DQ] STATIC PACK: base={len(old)} candidate={len(candidates)} "
        f"pruned={len(pruned)} packed_new={len(new_members)} "
        f"total={len(final_members)} new_source_bytes={total_source}"
    )
    print(
        "[Phase6DQ] SECTION SELECTION: "
        + " ".join(
            f"{name}={selected_counts[name]}/{available_counts[name]}"
            for name, _, _, _ in SECTIONS
        )
    )
    print(
        "[Phase6DQ] DSOUND APU ROUTING: "
        + " ".join(f"{k}={v}" for k, v in dsound_route_counts.items())
    )
    print("[Phase6DQ] VP WRITE32 diagnostic continuation: ARMED")
    print("[Phase6DQ] Unknown VP reads + non-VP MMIO: HARD FENCED")
    print("[Phase6DQ] Dispatch progress logging: first 8 + every 65536")
    print("[Phase6DQ] Runtime unique frontier/hard-stop/VP journals: ARMED")
    print("[Phase6DQ] 64M execution budget + C4146 scope: INHERITED")
    print("[Phase6DQ] A41EE runtime provenance ring: ARMED (fault semantics unchanged)")
    print("[Phase6DQ] Pixel chase/present proximity instrumentation: INHERITED")
    print("[Phase6DQ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
