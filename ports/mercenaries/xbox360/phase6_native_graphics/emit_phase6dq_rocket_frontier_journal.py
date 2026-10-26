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
widening ordinary guest-memory fault handling.
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
BUILD_TAG = "P6DQ-R45-AUDIO-PROVENANCE-20261026-A"
COOKIE_OLD = "phase6dp_env_build_cookie"
COOKIE_NEW = "phase6dq_env_build_cookie"
EMITTER_REVISION = "6DQ-R45"

CANDIDATE_CAP = 4096
DSOUND_POISON_SITE = 0x002A41F7
DSOUND_POISON_VALUE = 0xCCCCCCCC
DSOUND_POISON_NOOP_TARGET = 0xF6DCCCD0
DSOUND_START = 0x0029CB80
DSOUND_END = 0x002BB274

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
typedef struct Phase6DQAc97OutputBusMaster
{
    uint32_t bdbar;
    uint8_t civ;
    uint8_t lvi;
    uint16_t sr;
    uint16_t picb;
    uint8_t piv;
    uint8_t cr;
} Phase6DQAc97OutputBusMaster;

static uint32_t s_phase6dqAc97GlobCnt = 0u;
static uint32_t s_phase6dqAc97GlobSta = 0x00000100u;
static uint32_t s_phase6dqAc97ReadCount = 0u;
static uint32_t s_phase6dqAc97WriteCount = 0u;
static Phase6DQAc97OutputBusMaster s_phase6dqAc97PcmOut =
    { 0u, 0u, 0u, 1u, 0u, 0u, 0u };
static Phase6DQAc97OutputBusMaster s_phase6dqAc97SpdifOut =
    { 0u, 0u, 0u, 1u, 0u, 0u, 0u };
static uint32_t s_phase6dqAc97OutputReadCount = 0u;
static uint32_t s_phase6dqAc97OutputWriteCount = 0u;
static uint32_t s_phase6dqAc97DescriptorLatchCount = 0u;
static uint32_t s_phase6dqAc97LastDescriptorAddress = 0u;
static uint32_t s_phase6dqAc97LastDescriptorControl = 0u;
static uint32_t s_phase6dqAc97TableWriteWatchCount = 0u;
static uint32_t s_phase6dqAc97TableWriteLastAddress = 0u;
static uint32_t s_phase6dqAc97TableWriteLastWidth = 0u;
static uint32_t s_phase6dqAc97TableWriteLastValue = 0u;
static uint32_t s_phase6dqAc97TableWriteLastOld0 = 0u;
static uint32_t s_phase6dqAc97TableWriteLastOld1 = 0u;
static uint32_t s_phase6dqAc97ChannelWriteNoteCount = 0u;
static uint32_t s_phase6dqAc97ChannelWriteLastSite = 0u;
static uint32_t s_phase6dqAc97ChannelWriteLastObject = 0u;
static uint32_t s_phase6dqAc97ChannelWriteLastIndex = 0u;
static uint32_t s_phase6dqAc97ChannelWriteLastTableValue = 0u;
static uint32_t s_phase6dqAc97ChannelWriteLastDestination = 0u;
static uint32_t s_phase6dqAc97ChannelWriteLastValue = 0u;
#define PHASE6DQ_R45_AUDIO_LOG_CAP 32u
#define PHASE6DQ_R45_BAD_LOG_CAP 16u
static uint32_t s_phase6dqR45AudioObjectCallCount = 0u;
static uint32_t s_phase6dqR45AudioBadSignatureCount = 0u;
static uint32_t s_phase6dqR45AudioContainmentCount = 0u;
static uint32_t s_phase6dqR45AudioLastSite = 0u;
static uint32_t s_phase6dqR45AudioLastObject = 0u;
static uint32_t s_phase6dqR45AudioLastIndex = 0u;
static uint32_t s_phase6dqHalGetVector44Count = 0u;
static uint32_t s_phase6dqHalGetVector44LastBus = 0u;
static uint32_t s_phase6dqHalGetVector44LastVector = 0u;
static uint32_t s_phase6dqHalGetVector44LastIrql = 0u;
static uint32_t s_phase6dqKeInitInterrupt109Count = 0u;
static uint32_t s_phase6dqKeInitInterrupt109LastObject = 0u;
static uint32_t s_phase6dqKeInitInterrupt109LastRoutine = 0u;
static uint32_t s_phase6dqKeInitInterrupt109LastContext = 0u;
static uint32_t s_phase6dqKeInitInterrupt109LastVector = 0u;
static uint32_t s_phase6dqKeInitInterrupt109LastIrql = 0u;
static uint32_t s_phase6dqKeConnectInterrupt98Count = 0u;
static uint32_t s_phase6dqKeConnectInterrupt98Successes = 0u;
static uint32_t s_phase6dqKeConnectInterrupt98LastObject = 0u;
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
static uint32_t s_phase6dqA41eeLastSite = 0u;
static uint32_t s_phase6dqA41eeLastOwner = 0u;
static uint32_t s_phase6dqA41eeSiteWrites = 0u;
static uint32_t s_phase6dqA4622LastSite = 0u;
static uint32_t s_phase6dqA4622LastOwner = 0u;
static uint32_t s_phase6dqA4622SiteWrites = 0u;
static uint32_t s_phase6dqA52adLastSite = 0u;
static uint32_t s_phase6dqA52adLastOwner = 0u;
static uint32_t s_phase6dqA52adSiteWrites = 0u;
#define PHASE6DQ_F78F_READ_CAP 24u
typedef struct Phase6DQF78fRead
{
    uint32_t seq;
    uint32_t site;
    uint32_t address;
    uint32_t value;
} Phase6DQF78fRead;
static Phase6DQF78fRead s_phase6dqF78fReads[PHASE6DQ_F78F_READ_CAP];
static uint32_t s_phase6dqF78fReadCount = 0u;
static uint32_t s_phase6dqF78fPoisonHits = 0u;
static uint32_t s_phase6dqF78fPoisonSite = 0u;
static uint32_t s_phase6dqF78fPoisonAddress = 0u;
static uint32_t s_phase6dqF78fPoisonValue = 0u;
static uint32_t s_phase6dqF78fPoisonEax = 0u;
static uint32_t s_phase6dqF78fPoisonEcx = 0u;
static uint32_t s_phase6dqF78fPoisonEdx = 0u;
static uint32_t s_phase6dqF78fPoisonEbx = 0u;
static uint32_t s_phase6dqF78fPoisonEsi = 0u;
static uint32_t s_phase6dqF78fPoisonEdi = 0u;
static uint32_t s_phase6dqF78fPoisonEsp = 0u;
static uint32_t s_phase6dqF78fA52adCalls = 0u;
static uint32_t s_phase6dqF78fA52adArg1 = 0u;
static uint32_t s_phase6dqF78fA52adEsp = 0u;
static uint32_t s_phase6dqF78fCallEax = 0u;
static uint32_t s_phase6dqF78fCallEcx = 0u;
static uint32_t s_phase6dqF78fCallEdx = 0u;
static uint32_t s_phase6dqF78fCallEbx = 0u;
static uint32_t s_phase6dqF78fCallEsi = 0u;
static uint32_t s_phase6dqF78fCallEdi = 0u;
static uint32_t s_phase6dqXactInitEntries = 0u;
static uint32_t s_phase6dqXactInitStage1Result = 0u;
static uint32_t s_phase6dqXactInitStage2Result = 0u;
static uint32_t s_phase6dqXactInitEventCount = 0u;
static uint32_t s_phase6dqXactInitEventBytes = 0u;
static uint32_t s_phase6dqXactInitAllocResult = 0u;
static uint32_t s_phase6dqXactInitFinalResult = 0u;
static const char* phase6dq_f78f_site_expr(uint32_t site);

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
        "P6DQ ROCKET HARD STOP kind=%u caller=%08X target=%08X esp=%08X ticks=%u a41ee_site=%u a41ee_owner=%08X a41ee_writes=%u a4622_site=%u a4622_owner=%08X a4622_writes=%u a52ad_site=%u a52ad_owner=%08X a52ad_writes=%u",
        (unsigned int)kind,
        (unsigned int)caller,
        (unsigned int)target,
        (unsigned int)savedEsp,
        (unsigned int)s_phase4cBlockTicks,
        (unsigned int)s_phase6dqA41eeLastSite,
        (unsigned int)s_phase6dqA41eeLastOwner,
        (unsigned int)s_phase6dqA41eeSiteWrites,
        (unsigned int)s_phase6dqA4622LastSite,
        (unsigned int)s_phase6dqA4622LastOwner,
        (unsigned int)s_phase6dqA4622SiteWrites,
        (unsigned int)s_phase6dqA52adLastSite,
        (unsigned int)s_phase6dqA52adLastOwner,
        (unsigned int)s_phase6dqA52adSiteWrites);
    trace(line);

    sprintf(
        line,
        "P6DQ ROCKET HARD REGS eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X",
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

static int phase6dq_ac97_offset_table_overlap(
    uint32_t address,
    uint32_t width)
{
    uint32_t end = address + width;
    return address < 0x002BA9C8u && end > 0x002BA9C0u;
}

static void phase6dq_note_ac97_offset_table_write(
    uint32_t address,
    uint32_t width,
    uint32_t value)
{
    char line[512];

    ++s_phase6dqAc97TableWriteWatchCount;
    s_phase6dqAc97TableWriteLastAddress = address;
    s_phase6dqAc97TableWriteLastWidth = width;
    s_phase6dqAc97TableWriteLastValue = value;
    s_phase6dqAc97TableWriteLastOld0 = GUEST_READ32(0x002BA9C0u);
    s_phase6dqAc97TableWriteLastOld1 = GUEST_READ32(0x002BA9C4u);

    sprintf(
        line,
        "P6DQ AC97 TABLE WRITE WATCH: count=%u addr=%08X width=%u value=%08X old0=%08X old1=%08X caller=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
        (unsigned int)s_phase6dqAc97TableWriteWatchCount,
        (unsigned int)address,
        (unsigned int)width,
        (unsigned int)value,
        (unsigned int)s_phase6dqAc97TableWriteLastOld0,
        (unsigned int)s_phase6dqAc97TableWriteLastOld1,
        (unsigned int)phase4c_current_caller(),
        (unsigned int)eax,
        (unsigned int)ecx,
        (unsigned int)edx,
        (unsigned int)ebx,
        (unsigned int)esi,
        (unsigned int)edi,
        (unsigned int)g_esp);
    trace(line);
}

static void phase6dq_note_ac97_channel_write(
    uint32_t site,
    uint32_t object,
    uint32_t index,
    uint32_t tableValue,
    uint32_t writeValue)
{
    uint32_t tableAddress = 0x002BA9C0u + (index * 4u);
    uint32_t destination = tableValue + 0xFEC0010Bu;
    uint32_t table0 = GUEST_READ32(0x002BA9C0u);
    uint32_t table1 = GUEST_READ32(0x002BA9C4u);
    char line[640];

    ++s_phase6dqAc97ChannelWriteNoteCount;
    s_phase6dqAc97ChannelWriteLastSite = site;
    s_phase6dqAc97ChannelWriteLastObject = object;
    s_phase6dqAc97ChannelWriteLastIndex = index;
    s_phase6dqAc97ChannelWriteLastTableValue = tableValue;
    s_phase6dqAc97ChannelWriteLastDestination = destination;
    s_phase6dqAc97ChannelWriteLastValue = writeValue;

    sprintf(
        line,
        "P6DQ AC97 CHANNEL WRITE: count=%u site=%08X object=%08X index=%08X table_addr=%08X table_value=%08X table0=%08X table1=%08X dest=%08X value=%02X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
        (unsigned int)s_phase6dqAc97ChannelWriteNoteCount,
        (unsigned int)site,
        (unsigned int)object,
        (unsigned int)index,
        (unsigned int)tableAddress,
        (unsigned int)tableValue,
        (unsigned int)table0,
        (unsigned int)table1,
        (unsigned int)destination,
        (unsigned int)(writeValue & 0xFFu),
        (unsigned int)eax,
        (unsigned int)ecx,
        (unsigned int)edx,
        (unsigned int)ebx,
        (unsigned int)esi,
        (unsigned int)edi,
        (unsigned int)g_esp);
    trace(line);
}

static uint32_t phase6dq_r45_audio_index(
    uint32_t object,
    uint32_t* readable)
{
    if (readable != 0)
        *readable = 0u;

    /*
     * Phase 2 established a 64 MiB guest arena.  Do not turn provenance
     * logging into a new fault source: only inspect an aligned object whose
     * first dword is inside that arena.
     */
    if ((object & 3u) != 0u || object > 0x03FFFFFCu)
        return 0xFFFFFFFFu;

    if (readable != 0)
        *readable = 1u;
    return GUEST_READ32(object);
}

static void phase6dq_r45_note_audio_object_call(
    uint32_t site,
    uint32_t object)
{
    uint32_t readable = 0u;
    uint32_t index = phase6dq_r45_audio_index(object, &readable);
    uint32_t bad = object == 0x00040000u && readable != 0u &&
                   index == 0x00000400u;
    char line[512];

    ++s_phase6dqR45AudioObjectCallCount;
    if (bad)
        ++s_phase6dqR45AudioBadSignatureCount;

    s_phase6dqR45AudioLastSite = site;
    s_phase6dqR45AudioLastObject = object;
    s_phase6dqR45AudioLastIndex = index;

    if (s_phase6dqR45AudioObjectCallCount <= PHASE6DQ_R45_AUDIO_LOG_CAP ||
        (bad && s_phase6dqR45AudioBadSignatureCount <= PHASE6DQ_R45_BAD_LOG_CAP))
    {
        sprintf(
            line,
            "P6DQ R45 AUDIO OBJECT: call=%u bad=%u bad_count=%u site=%08X object=%08X readable=%u index=%08X caller=%08X eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X esp=%08X",
            (unsigned int)s_phase6dqR45AudioObjectCallCount,
            (unsigned int)bad,
            (unsigned int)s_phase6dqR45AudioBadSignatureCount,
            (unsigned int)site,
            (unsigned int)object,
            (unsigned int)readable,
            (unsigned int)index,
            (unsigned int)phase4c_current_caller(),
            (unsigned int)eax,
            (unsigned int)ecx,
            (unsigned int)edx,
            (unsigned int)ebx,
            (unsigned int)esi,
            (unsigned int)edi,
            (unsigned int)g_esp);
        trace(line);
    }
}

static int phase6dq_r45_bad_audio_object(
    uint32_t site,
    uint32_t object,
    uint32_t index)
{
    char line[448];

    if (object != 0x00040000u || index != 0x00000400u)
        return 0;

    ++s_phase6dqR45AudioContainmentCount;
    if (s_phase6dqR45AudioContainmentCount <= PHASE6DQ_R45_BAD_LOG_CAP)
    {
        sprintf(
            line,
            "P6DQ R45 AUDIO CONTAIN: count=%u site=%08X object=%08X index=%08X table0=%08X table1=%08X caller=%08X esp=%08X",
            (unsigned int)s_phase6dqR45AudioContainmentCount,
            (unsigned int)site,
            (unsigned int)object,
            (unsigned int)index,
            (unsigned int)GUEST_READ32(0x002BA9C0u),
            (unsigned int)GUEST_READ32(0x002BA9C4u),
            (unsigned int)phase4c_current_caller(),
            (unsigned int)g_esp);
        trace(line);
    }

    return 1;
}

static int phase6dq_ac97_is_output_busmaster(uint32_t address)
{
    return
        (address >= 0xFEC00110u && address <= 0xFEC0011Bu) ||
        (address >= 0xFEC00170u && address <= 0xFEC0017Bu);
}

static Phase6DQAc97OutputBusMaster* phase6dq_ac97_output_busmaster(
    uint32_t address,
    uint32_t* streamBase,
    const char** streamName)
{
    if (address >= 0xFEC00170u && address <= 0xFEC0017Bu)
    {
        if (streamBase != 0) *streamBase = 0xFEC00170u;
        if (streamName != 0) *streamName = "SPDIF";
        return &s_phase6dqAc97SpdifOut;
    }

    if (streamBase != 0) *streamBase = 0xFEC00110u;
    if (streamName != 0) *streamName = "PCM";
    return &s_phase6dqAc97PcmOut;
}

static void phase6dq_ac97_latch_descriptor(
    Phase6DQAc97OutputBusMaster* bm)
{
    uint32_t descriptorVa;

    if (bm == 0 || bm->bdbar == 0u)
        return;

    descriptorVa = bm->bdbar + ((uint32_t)bm->civ * 8u);
    s_phase6dqAc97LastDescriptorAddress = GUEST_READ32(descriptorVa) & ~3u;
    s_phase6dqAc97LastDescriptorControl = GUEST_READ32(descriptorVa + 4u);
    bm->picb = (uint16_t)(s_phase6dqAc97LastDescriptorControl & 0xFFFFu);
    ++s_phase6dqAc97DescriptorLatchCount;
}

static uint32_t phase6dq_ac97_output_read(
    uint32_t address,
    uint32_t width)
{
    uint32_t base = 0u;
    uint32_t offset;
    uint32_t value = 0u;
    const char* name = "PCM";
    Phase6DQAc97OutputBusMaster* bm =
        phase6dq_ac97_output_busmaster(address, &base, &name);
    char line[448];

    offset = address - base;
    ++s_phase6dqAc97OutputReadCount;

    if (width == 1u)
    {
        switch (offset)
        {
        case 4u: value = (uint32_t)bm->civ; break;
        case 5u: value = (uint32_t)bm->lvi; break;
        case 6u: value = (uint32_t)(bm->sr & 0xFFu); break;
        case 7u: value = (uint32_t)((bm->sr >> 8) & 0xFFu); break;
        case 8u: value = (uint32_t)(bm->picb & 0xFFu); break;
        case 9u: value = (uint32_t)((bm->picb >> 8) & 0xFFu); break;
        case 10u: value = (uint32_t)bm->piv; break;
        case 11u: value = (uint32_t)bm->cr; break;
        default: value = 0u; break;
        }
    }
    else if (width == 2u)
    {
        if (offset == 6u)
            value = (uint32_t)bm->sr;
        else if (offset == 8u)
            value = (uint32_t)bm->picb;
    }
    else if (width == 4u)
    {
        if (offset == 0u)
            value = bm->bdbar;
        else if (offset == 4u)
            value =
                (uint32_t)bm->civ |
                ((uint32_t)bm->lvi << 8) |
                ((uint32_t)bm->sr << 16);
        else if (offset == 8u)
            value =
                (uint32_t)bm->picb |
                ((uint32_t)bm->piv << 16) |
                ((uint32_t)bm->cr << 24);
    }

    if (s_phase6dqAc97OutputReadCount <= 32u)
    {
        sprintf(
            line,
            "P6DQ AC97 OUT READ stream=%s width=%u addr=%08X off=%02X value=%08X bdbar=%08X civ=%u lvi=%u sr=%04X picb=%u piv=%u cr=%02X caller=%08X reads=%u",
            name,
            (unsigned int)width,
            (unsigned int)address,
            (unsigned int)offset,
            (unsigned int)value,
            (unsigned int)bm->bdbar,
            (unsigned int)bm->civ,
            (unsigned int)bm->lvi,
            (unsigned int)bm->sr,
            (unsigned int)bm->picb,
            (unsigned int)bm->piv,
            (unsigned int)bm->cr,
            (unsigned int)phase4c_current_caller(),
            (unsigned int)s_phase6dqAc97OutputReadCount);
        trace(line);
    }

    return value;
}

static void phase6dq_ac97_output_write(
    uint32_t address,
    uint32_t width,
    uint32_t value)
{
    uint32_t base = 0u;
    uint32_t offset;
    const char* name = "PCM";
    Phase6DQAc97OutputBusMaster* bm =
        phase6dq_ac97_output_busmaster(address, &base, &name);
    char line[512];

    offset = address - base;
    ++s_phase6dqAc97OutputWriteCount;

    if (width == 4u && offset == 0u)
    {
        /* AC'97 BDBAR is dword aligned. */
        bm->bdbar = value & ~3u;
    }
    else if (width == 1u && offset == 5u)
    {
        bm->lvi = (uint8_t)(value & 31u);

        /*
         * Match AC'97 restart semantics closely enough for initialization:
         * if RUN was already requested while halted, publishing a new LVI
         * restarts descriptor consumption at PIV.
         */
        if ((bm->cr & 1u) != 0u && (bm->sr & 1u) != 0u)
        {
            bm->sr = (uint16_t)(bm->sr & ~3u);
            bm->civ = bm->piv;
            bm->piv = (uint8_t)((bm->piv + 1u) & 31u);
            phase6dq_ac97_latch_descriptor(bm);
        }
    }
    else if ((width == 1u || width == 2u) && offset == 6u)
    {
        /*
         * SR bits 2/3/4 are write-one-to-clear. DCH/CELV (bits 0/1)
         * are read-only state.
         */
        bm->sr = (uint16_t)(bm->sr & ~(value & 0x1Cu));
    }
    else if (width == 1u && offset == 11u)
    {
        if ((value & 2u) != 0u)
        {
            /* Reset bus-master engine; preserve interrupt-enable class. */
            bm->bdbar = 0u;
            bm->civ = 0u;
            bm->lvi = 0u;
            bm->sr = 1u;
            bm->picb = 0u;
            bm->piv = 0u;
            bm->cr = (uint8_t)(bm->cr & 0x1Cu);
        }
        else
        {
            bm->cr = (uint8_t)(value & 0x1Fu);

            if ((bm->cr & 1u) == 0u)
            {
                bm->sr = (uint16_t)(bm->sr | 1u);
            }
            else
            {
                bm->civ = bm->piv;
                bm->piv = (uint8_t)((bm->piv + 1u) & 31u);
                phase6dq_ac97_latch_descriptor(bm);
                bm->sr = (uint16_t)(bm->sr & ~1u);
            }
        }
    }

    if (s_phase6dqAc97OutputWriteCount <= 32u)
    {
        sprintf(
            line,
            "P6DQ AC97 OUT WRITE stream=%s width=%u addr=%08X off=%02X value=%08X bdbar=%08X civ=%u lvi=%u sr=%04X picb=%u piv=%u cr=%02X desc_addr=%08X desc_ctl=%08X caller=%08X writes=%u",
            name,
            (unsigned int)width,
            (unsigned int)address,
            (unsigned int)offset,
            (unsigned int)value,
            (unsigned int)bm->bdbar,
            (unsigned int)bm->civ,
            (unsigned int)bm->lvi,
            (unsigned int)bm->sr,
            (unsigned int)bm->picb,
            (unsigned int)bm->piv,
            (unsigned int)bm->cr,
            (unsigned int)s_phase6dqAc97LastDescriptorAddress,
            (unsigned int)s_phase6dqAc97LastDescriptorControl,
            (unsigned int)phase4c_current_caller(),
            (unsigned int)s_phase6dqAc97OutputWriteCount);
        trace(line);
    }
}

static int phase6dq_ac97_is_global32(uint32_t address)
{
    return address == 0xFEC0012Cu || address == 0xFEC00130u;
}

static uint32_t phase6dq_ac97_global_read32(uint32_t address)
{
    uint32_t value = 0u;
    char line[384];

    ++s_phase6dqAc97ReadCount;

    if (address == 0xFEC0012Cu)
    {
        value = s_phase6dqAc97GlobCnt;
    }
    else if (address == 0xFEC00130u)
    {
        /*
         * AC'97 native-audio bus-master GLOB_STA. Bit 8 is the read-only
         * primary-codec-ready bit (GS_S0CR). QEMU's AC97 model exposes that
         * bit on every GLOB_STA read; retail DirectSound polls it in
         * CAc97Device::CodecReady before deciding that an audio driver exists.
         */
        value = s_phase6dqAc97GlobSta | 0x00000100u;
    }

    if (s_phase6dqAc97ReadCount <= 16u)
    {
        sprintf(
            line,
            "P6DQ AC97 GLOBAL READ addr=%08X value=%08X cnt=%08X sta=%08X caller=%08X reads=%u",
            (unsigned int)address,
            (unsigned int)value,
            (unsigned int)s_phase6dqAc97GlobCnt,
            (unsigned int)(s_phase6dqAc97GlobSta | 0x00000100u),
            (unsigned int)phase4c_current_caller(),
            (unsigned int)s_phase6dqAc97ReadCount);
        trace(line);
    }

    return value;
}

static void phase6dq_ac97_global_write32(uint32_t address, uint32_t value)
{
    char line[384];

    ++s_phase6dqAc97WriteCount;

    if (address == 0xFEC0012Cu)
    {
        /*
         * AC'97 GLOB_CNT: bits 1/2 are cold/warm reset requests. Match the
         * conservative QEMU behavior: reset-request writes are commands and
         * do not become persistent control state; ordinary writable bits are
         * retained within the six-bit valid mask.
         */
        if ((value & 0x00000006u) == 0u)
            s_phase6dqAc97GlobCnt = value & 0x0000003Fu;

        /* The native codec is modeled present/ready after reset sequencing. */
        s_phase6dqAc97GlobSta |= 0x00000100u;
    }
    else if (address == 0xFEC00130u)
    {
        /*
         * Preserve the read-only primary-codec-ready bit. Mirror the AC'97
         * W1C status class used by QEMU for RCS/S1R1/S0R1/GSCI, and retain
         * only the two writable modem-status bits.
         */
        s_phase6dqAc97GlobSta &= ~(value & 0x00008C01u);
        s_phase6dqAc97GlobSta &= ~0x00030000u;
        s_phase6dqAc97GlobSta |= value & 0x00030000u;
        s_phase6dqAc97GlobSta |= 0x00000100u;
    }

    if (s_phase6dqAc97WriteCount <= 16u)
    {
        sprintf(
            line,
            "P6DQ AC97 GLOBAL WRITE addr=%08X value=%08X cnt=%08X sta=%08X caller=%08X writes=%u",
            (unsigned int)address,
            (unsigned int)value,
            (unsigned int)s_phase6dqAc97GlobCnt,
            (unsigned int)(s_phase6dqAc97GlobSta | 0x00000100u),
            (unsigned int)phase4c_current_caller(),
            (unsigned int)s_phase6dqAc97WriteCount);
        trace(line);
    }
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


static void phase6dq_hal_get_interrupt_vector(uint32_t savedEsp)
{
    uint32_t busInterruptLevel = GUEST_READ32(g_esp + 4u);
    uint32_t irqlPtr = GUEST_READ32(g_esp + 8u);
    uint32_t vector = 0u;
    uint32_t irql = 0u;
    char line[384];

    ++s_phase6dqHalGetVector44Count;
    s_phase6dqHalGetVector44LastBus = busInterruptLevel;

    /*
     * Xbox IRQ mapping used by retail/nxdk/Cxbx:
     *   vector = IRQ_BASE(0x30) + bus IRQ
     *   IRQL   = MAX_BUS_INTERRUPT_LEVEL(27) - bus IRQ
     *
     * R39 hardware proves retail DSOUND requests bus IRQ 6 (ACI/AC97).
     */
    if (busInterruptLevel <= 27u)
    {
        vector = 0x30u + busInterruptLevel;
        irql = 27u - busInterruptLevel;

        if (irqlPtr != 0u)
            GUEST_WRITE8(irqlPtr, (uint8_t)irql);
    }

    s_phase6dqHalGetVector44LastVector = vector;
    s_phase6dqHalGetVector44LastIrql = irql;
    eax = vector;
    g_esp = savedEsp;

    sprintf(
        line,
        "P6DQ HALGETVECTOR44: calls=%u bus=%u irql_ptr=%08X vector=%08X irql=%u caller=%08X new_esp=%08X",
        (unsigned int)s_phase6dqHalGetVector44Count,
        (unsigned int)busInterruptLevel,
        (unsigned int)irqlPtr,
        (unsigned int)vector,
        (unsigned int)irql,
        (unsigned int)phase4c_current_caller(),
        (unsigned int)g_esp);
    trace(line);
}

static void phase6dq_ke_initialize_interrupt(uint32_t savedEsp)
{
    uint32_t interruptObject = GUEST_READ32(g_esp + 4u);
    uint32_t serviceRoutine = GUEST_READ32(g_esp + 8u);
    uint32_t serviceContext = GUEST_READ32(g_esp + 12u);
    uint32_t vector = GUEST_READ32(g_esp + 16u);
    uint32_t irql = GUEST_READ32(g_esp + 20u);
    uint32_t interruptMode = GUEST_READ32(g_esp + 24u);
    uint32_t shareVector = GUEST_READ32(g_esp + 28u);
    uint32_t busInterruptLevel =
        (vector >= 0x30u && vector <= 0x4Bu) ? (vector - 0x30u) : 0u;
    char line[512];

    ++s_phase6dqKeInitInterrupt109Count;
    s_phase6dqKeInitInterrupt109LastObject = interruptObject;
    s_phase6dqKeInitInterrupt109LastRoutine = serviceRoutine;
    s_phase6dqKeInitInterrupt109LastContext = serviceContext;
    s_phase6dqKeInitInterrupt109LastVector = vector;
    s_phase6dqKeInitInterrupt109LastIrql = irql;

    if (interruptObject == 0u || vector < 0x30u || vector > 0x4Bu)
    {
        phase4c_escape(
            PHASE4C_BOUNDARY_ICALL_SAFE,
            0x8000006Du,
            savedEsp);
        return;
    }

    /*
     * Original Xbox KINTERRUPT layout:
     *   +00 ServiceRoutine
     *   +04 ServiceContext
     *   +08 BusInterruptLevel
     *   +0C Irql (ULONG in Xbox layout)
     *   +10 Connected
     *   +11 ShareVector
     *   +12 Mode
     *   +14 ServiceCount
     * DispatchCode begins at +18 and is not needed by this serialized native
     * runtime because interrupt dispatch is not executed from guest thunk code.
     */
    GUEST_WRITE32(interruptObject + 0x00u, serviceRoutine);
    GUEST_WRITE32(interruptObject + 0x04u, serviceContext);
    GUEST_WRITE32(interruptObject + 0x08u, busInterruptLevel);
    GUEST_WRITE32(interruptObject + 0x0Cu, irql);
    GUEST_WRITE8(interruptObject + 0x10u, 0u);
    GUEST_WRITE8(interruptObject + 0x11u, (uint8_t)(shareVector != 0u));
    GUEST_WRITE8(interruptObject + 0x12u, (uint8_t)interruptMode);
    GUEST_WRITE8(interruptObject + 0x13u, 0u);
    GUEST_WRITE32(interruptObject + 0x14u, 0u);

    g_esp = savedEsp;

    sprintf(
        line,
        "P6DQ KEINITINT109: calls=%u object=%08X routine=%08X context=%08X vector=%08X bus=%u irql=%u mode=%u share=%u caller=%08X new_esp=%08X",
        (unsigned int)s_phase6dqKeInitInterrupt109Count,
        (unsigned int)interruptObject,
        (unsigned int)serviceRoutine,
        (unsigned int)serviceContext,
        (unsigned int)vector,
        (unsigned int)busInterruptLevel,
        (unsigned int)irql,
        (unsigned int)interruptMode,
        (unsigned int)(shareVector != 0u),
        (unsigned int)phase4c_current_caller(),
        (unsigned int)g_esp);
    trace(line);
}

static void phase6dq_ke_connect_interrupt(uint32_t savedEsp)
{
    uint32_t interruptObject = GUEST_READ32(g_esp + 4u);
    uint32_t connected = 0u;
    uint32_t busInterruptLevel = 0u;
    uint32_t irql = 0u;
    uint32_t mode = 0u;
    char line[448];

    ++s_phase6dqKeConnectInterrupt98Count;
    s_phase6dqKeConnectInterrupt98LastObject = interruptObject;

    if (interruptObject != 0u)
    {
        busInterruptLevel = GUEST_READ32(interruptObject + 0x08u);
        irql = GUEST_READ32(interruptObject + 0x0Cu);
        mode = (uint32_t)GUEST_READ8(interruptObject + 0x12u);

        if (busInterruptLevel <= 27u &&
            GUEST_READ8(interruptObject + 0x10u) == 0u)
        {
            /*
             * Serialized runtime: record the connection contract and allow
             * retail initialization to proceed. No host ISR is fabricated;
             * actual APU/AC97 interrupt delivery remains a separately modeled
             * hardware concern.
             */
            GUEST_WRITE8(interruptObject + 0x10u, 1u);
            connected = 1u;
            ++s_phase6dqKeConnectInterrupt98Successes;
        }
    }

    eax = connected;
    g_esp = savedEsp;

    sprintf(
        line,
        "P6DQ KECONNECT98: calls=%u successes=%u object=%08X bus=%u irql=%u mode=%u result=%u caller=%08X new_esp=%08X",
        (unsigned int)s_phase6dqKeConnectInterrupt98Count,
        (unsigned int)s_phase6dqKeConnectInterrupt98Successes,
        (unsigned int)interruptObject,
        (unsigned int)busInterruptLevel,
        (unsigned int)irql,
        (unsigned int)mode,
        (unsigned int)connected,
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
        "P6DQ ROCKET JOURNAL SUMMARY A dispatch_unique=%u dispatch_overflow=%u hard_unique=%u hard_overflow=%u",
        (unsigned int)s_phase6dqDispatchJournalCount,
        (unsigned int)s_phase6dqDispatchJournalOverflow,
        (unsigned int)s_phase6dqHardStopJournalCount,
        (unsigned int)s_phase6dqHardStopJournalOverflow);
    trace(line);

    sprintf(
        line,
        "P6DQ ROCKET JOURNAL SUMMARY B vp_write32=%u vp_unique=%u vp_overflow=%u vp_unknown_reads=%u ioapic_reads=%u ioapic_writes=%u ioapic_fences=%u",
        (unsigned int)s_phase6dqVpWrite32Count,
        (unsigned int)s_phase6dqVpJournalCount,
        (unsigned int)s_phase6dqVpJournalOverflow,
        (unsigned int)s_phase6dqVpUnknownReadCount,
        (unsigned int)s_phase6dqIoapicDefaultReadCount,
        (unsigned int)s_phase6dqIoapicDefaultWriteCount,
        (unsigned int)s_phase6dqIoapicSpecialFenceCount);
    trace(line);

    sprintf(
        line,
        "P6DQ AC97 GLOBAL: reads=%u writes=%u glob_cnt=%08X glob_sta=%08X codec_ready=%u",
        (unsigned int)s_phase6dqAc97ReadCount,
        (unsigned int)s_phase6dqAc97WriteCount,
        (unsigned int)s_phase6dqAc97GlobCnt,
        (unsigned int)(s_phase6dqAc97GlobSta | 0x00000100u),
        (unsigned int)(((s_phase6dqAc97GlobSta | 0x00000100u) & 0x00000100u) != 0u));
    trace(line);

    sprintf(
        line,
        "P6DQ AC97 TABLE PROVENANCE: table0=%08X table1=%08X write_watch=%u last_write_addr=%08X last_write_width=%u last_write_value=%08X last_old0=%08X last_old1=%08X channel_notes=%u last_site=%08X last_object=%08X last_index=%08X last_table_value=%08X last_dest=%08X last_value=%02X",
        (unsigned int)GUEST_READ32(0x002BA9C0u),
        (unsigned int)GUEST_READ32(0x002BA9C4u),
        (unsigned int)s_phase6dqAc97TableWriteWatchCount,
        (unsigned int)s_phase6dqAc97TableWriteLastAddress,
        (unsigned int)s_phase6dqAc97TableWriteLastWidth,
        (unsigned int)s_phase6dqAc97TableWriteLastValue,
        (unsigned int)s_phase6dqAc97TableWriteLastOld0,
        (unsigned int)s_phase6dqAc97TableWriteLastOld1,
        (unsigned int)s_phase6dqAc97ChannelWriteNoteCount,
        (unsigned int)s_phase6dqAc97ChannelWriteLastSite,
        (unsigned int)s_phase6dqAc97ChannelWriteLastObject,
        (unsigned int)s_phase6dqAc97ChannelWriteLastIndex,
        (unsigned int)s_phase6dqAc97ChannelWriteLastTableValue,
        (unsigned int)s_phase6dqAc97ChannelWriteLastDestination,
        (unsigned int)(s_phase6dqAc97ChannelWriteLastValue & 0xFFu));
    trace(line);

    sprintf(
        line,
        "P6DQ AC97 OUTPUT: reads=%u writes=%u pcm_bdbar=%08X pcm_civ=%u pcm_lvi=%u pcm_sr=%04X pcm_picb=%u pcm_piv=%u pcm_cr=%02X spdif_bdbar=%08X spdif_civ=%u spdif_lvi=%u spdif_sr=%04X spdif_picb=%u spdif_piv=%u spdif_cr=%02X desc_latches=%u last_desc_addr=%08X last_desc_ctl=%08X",
        (unsigned int)s_phase6dqAc97OutputReadCount,
        (unsigned int)s_phase6dqAc97OutputWriteCount,
        (unsigned int)s_phase6dqAc97PcmOut.bdbar,
        (unsigned int)s_phase6dqAc97PcmOut.civ,
        (unsigned int)s_phase6dqAc97PcmOut.lvi,
        (unsigned int)s_phase6dqAc97PcmOut.sr,
        (unsigned int)s_phase6dqAc97PcmOut.picb,
        (unsigned int)s_phase6dqAc97PcmOut.piv,
        (unsigned int)s_phase6dqAc97PcmOut.cr,
        (unsigned int)s_phase6dqAc97SpdifOut.bdbar,
        (unsigned int)s_phase6dqAc97SpdifOut.civ,
        (unsigned int)s_phase6dqAc97SpdifOut.lvi,
        (unsigned int)s_phase6dqAc97SpdifOut.sr,
        (unsigned int)s_phase6dqAc97SpdifOut.picb,
        (unsigned int)s_phase6dqAc97SpdifOut.piv,
        (unsigned int)s_phase6dqAc97SpdifOut.cr,
        (unsigned int)s_phase6dqAc97DescriptorLatchCount,
        (unsigned int)s_phase6dqAc97LastDescriptorAddress,
        (unsigned int)s_phase6dqAc97LastDescriptorControl);
    trace(line);

    sprintf(
        line,
        "P6DQ IRQ SETUP: hal44=%u bus=%u vector=%08X irql=%u init109=%u object=%08X routine=%08X context=%08X connect98=%u successes=%u",
        (unsigned int)s_phase6dqHalGetVector44Count,
        (unsigned int)s_phase6dqHalGetVector44LastBus,
        (unsigned int)s_phase6dqHalGetVector44LastVector,
        (unsigned int)s_phase6dqHalGetVector44LastIrql,
        (unsigned int)s_phase6dqKeInitInterrupt109Count,
        (unsigned int)s_phase6dqKeInitInterrupt109LastObject,
        (unsigned int)s_phase6dqKeInitInterrupt109LastRoutine,
        (unsigned int)s_phase6dqKeInitInterrupt109LastContext,
        (unsigned int)s_phase6dqKeConnectInterrupt98Count,
        (unsigned int)s_phase6dqKeConnectInterrupt98Successes);
    trace(line);

    sprintf(
        line,
        "P6DQ ROCKET JOURNAL SUMMARY C kestall_calls=%u last_us=%u total_us=%I64u max_us=%u fpsave=%u fprestore=%u fpdepth=%u fpmismatch=%u fpstate=%08X",
        (unsigned int)s_phase6dqKeStall151Count,
        (unsigned int)s_phase6dqKeStall151LastUs,
        (unsigned __int64)s_phase6dqKeStall151TotalUs,
        (unsigned int)s_phase6dqKeStall151MaxUs,
        (unsigned int)s_phase6dqFpSave142Count,
        (unsigned int)s_phase6dqFpRestore139Count,
        (unsigned int)s_phase6dqFpGuardDepth,
        (unsigned int)s_phase6dqFpGuardMismatchCount,
        (unsigned int)s_phase6dqFpGuardLastState);
    trace(line);

    sprintf(
        line,
        "P6DQ ROCKET JOURNAL SUMMARY D poison_sites=%u noops=%u object=%08X arg=%08X a41ee=%u/%08X/%u a4622=%u/%08X/%u a52ad=%u/%08X/%u",
        (unsigned int)s_phase6dqDsoundPoisonSiteCount,
        (unsigned int)s_phase6dqDsoundPoisonNoopCount,
        (unsigned int)s_phase6dqDsoundPoisonLastObject,
        (unsigned int)s_phase6dqDsoundPoisonLastArg,
        (unsigned int)s_phase6dqA41eeLastSite,
        (unsigned int)s_phase6dqA41eeLastOwner,
        (unsigned int)s_phase6dqA41eeSiteWrites,
        (unsigned int)s_phase6dqA4622LastSite,
        (unsigned int)s_phase6dqA4622LastOwner,
        (unsigned int)s_phase6dqA4622SiteWrites,
        (unsigned int)s_phase6dqA52adLastSite,
        (unsigned int)s_phase6dqA52adLastOwner,
        (unsigned int)s_phase6dqA52adSiteWrites);
    trace(line);

    sprintf(
        line,
        "P6DQ F78F ORIGIN: reads=%u poison_hits=%u poison_site=%u poison_addr=%08X poison_value=%08X a52ad_calls=%u a52ad_arg1=%08X a52ad_esp=%08X",
        (unsigned int)s_phase6dqF78fReadCount,
        (unsigned int)s_phase6dqF78fPoisonHits,
        (unsigned int)s_phase6dqF78fPoisonSite,
        (unsigned int)s_phase6dqF78fPoisonAddress,
        (unsigned int)s_phase6dqF78fPoisonValue,
        (unsigned int)s_phase6dqF78fA52adCalls,
        (unsigned int)s_phase6dqF78fA52adArg1,
        (unsigned int)s_phase6dqF78fA52adEsp);
    trace(line);

    sprintf(
        line,
        "P6DQ F78F CALL REGS eax=%08X ecx=%08X edx=%08X ebx=%08X esi=%08X edi=%08X poison_regs=%08X/%08X/%08X/%08X/%08X/%08X esp=%08X",
        (unsigned int)s_phase6dqF78fCallEax,
        (unsigned int)s_phase6dqF78fCallEcx,
        (unsigned int)s_phase6dqF78fCallEdx,
        (unsigned int)s_phase6dqF78fCallEbx,
        (unsigned int)s_phase6dqF78fCallEsi,
        (unsigned int)s_phase6dqF78fCallEdi,
        (unsigned int)s_phase6dqF78fPoisonEax,
        (unsigned int)s_phase6dqF78fPoisonEcx,
        (unsigned int)s_phase6dqF78fPoisonEdx,
        (unsigned int)s_phase6dqF78fPoisonEbx,
        (unsigned int)s_phase6dqF78fPoisonEsi,
        (unsigned int)s_phase6dqF78fPoisonEdi,
        (unsigned int)s_phase6dqF78fPoisonEsp);
    trace(line);

    sprintf(
        line,
        "P6DQ XACT INIT: entries=%u stage1_29FDF0=%08X stage2_28345A=%08X event_count=%u event_bytes=%u alloc=%08X final=%08X",
        (unsigned int)s_phase6dqXactInitEntries,
        (unsigned int)s_phase6dqXactInitStage1Result,
        (unsigned int)s_phase6dqXactInitStage2Result,
        (unsigned int)s_phase6dqXactInitEventCount,
        (unsigned int)s_phase6dqXactInitEventBytes,
        (unsigned int)s_phase6dqXactInitAllocResult,
        (unsigned int)s_phase6dqXactInitFinalResult);
    trace(line);

    {
        uint32_t phase6dqF78fCount =
            s_phase6dqF78fReadCount < PHASE6DQ_F78F_READ_CAP
                ? s_phase6dqF78fReadCount
                : PHASE6DQ_F78F_READ_CAP;
        uint32_t phase6dqF78fStart =
            s_phase6dqF78fReadCount > PHASE6DQ_F78F_READ_CAP
                ? (s_phase6dqF78fReadCount % PHASE6DQ_F78F_READ_CAP)
                : 0u;
        for (i = 0u; i < phase6dqF78fCount; ++i)
        {
            uint32_t phase6dqF78fIndex =
                (phase6dqF78fStart + i) % PHASE6DQ_F78F_READ_CAP;
            Phase6DQF78fRead* row = &s_phase6dqF78fReads[phase6dqF78fIndex];
            sprintf(
                line,
                "P6DQ F78F READ seq=%u site=%u addr=%08X value=%08X expr=%s",
                (unsigned int)row->seq,
                (unsigned int)row->site,
                (unsigned int)row->address,
                (unsigned int)row->value,
                phase6dq_f78f_site_expr(row->site));
            trace(line);
        }
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

    if (target == 0x8000002Cu)
    {
        phase6dq_hal_get_interrupt_vector(savedEsp);
        return;
    }

    if (target == 0x8000006Du)
    {
        phase6dq_ke_initialize_interrupt(savedEsp);
        return;
    }

    if (target == 0x80000062u)
    {
        phase6dq_ke_connect_interrupt(savedEsp);
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

    # R38 proved FEC0012C/FEC00130 are the AC'97 native-audio bus-master
    # GLOB_CNT/GLOB_STA pair used by retail DirectSound's codec-ready probe.
    # Route those exact dword registers first. Preserve the inherited broad
    # FEC-page default/fence policy everywhere else until additional retail
    # accesses are hardware-proven.
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
        ac97_patch = f"""    if (phase6dq_ac97_is_output_busmaster(address))
        return ({'uint8_t' if width == 1 else 'uint16_t' if width == 2 else 'uint32_t'})phase6dq_ac97_output_read(address, {width}u);

"""
        if width == 4:
            ac97_patch += """    if (phase6dq_ac97_is_global32(address))
        return phase6dq_ac97_global_read32(address);

"""
        ioapic_patch = ac97_patch + f"""    if (phase6dq_ioapic_is_default_offset(address))
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
    ioapic_write_patch = r'''    if (phase6dq_ac97_offset_table_overlap(address, 4u))
        phase6dq_note_ac97_offset_table_write(address, 4u, value);

    if (phase6dq_ac97_is_output_busmaster(address))
    {
        phase6dq_ac97_output_write(address, 4u, value);
        return;
    }

    if (phase6dq_ac97_is_global32(address))
    {
        phase6dq_ac97_global_write32(address, value);
        return;
    }

    if (phase6dq_ioapic_is_default_offset(address))
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
        probe = f"""    if (phase6dq_ac97_offset_table_overlap(address, {width}u))
        phase6dq_note_ac97_offset_table_write(address, {width}u, (uint32_t)value);

    if (phase6dq_ac97_is_output_busmaster(address))
    {{
        phase6dq_ac97_output_write(address, {width}u, (uint32_t)value);
        return;
    }}

    if (phase6dq_ioapic_is_default_offset(address))
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


def _phase6dq_c_escape(text: str) -> str:
    return text.replace("\\", "\\\\").replace('"', '\\"').replace("\r", " ").replace("\n", " ")


def instrument_f78f_origin_probe(text: str, base) -> tuple[str, list[dict]]:
    """
    R35: instrument only sub_0029F78F's routed READ32 calls.
    No read result is changed. The helper records a 24-entry ring and the first/
    latest EC83F0E4-producing read, if one exists.
    """
    signature_re = re.compile(r"(?m)^\s*(?:static\s+)?void\s+sub_0029F78F\(void\)\s*\{")
    matches = list(signature_re.finditer(text))
    if len(matches) != 1:
        raise SystemExit(f"[Phase6DQ] R35 expected one sub_0029F78F body, found {len(matches)}")

    masked = base.mask_noncode(text)
    start = matches[0].start()
    brace = masked.find("{", matches[0].start(), matches[0].end() + 1)
    if brace < 0:
        raise SystemExit("[Phase6DQ] R43 F78F body brace missing")
    end = base.closing_brace(masked, brace)
    body = text[start:end]
    body_masked = base.mask_noncode(body)

    needle = "phase6ch_apu_read32("
    sites = []
    spans = []
    pos = 0
    site_id = 0
    while True:
        call = body_masked.find(needle, pos)
        if call < 0:
            break
        open_paren = call + len(needle) - 1
        depth = 0
        cursor = open_paren
        close_paren = -1
        while cursor < len(body_masked):
            ch = body_masked[cursor]
            if ch == "(":
                depth += 1
            elif ch == ")":
                depth -= 1
                if depth == 0:
                    close_paren = cursor
                    break
            cursor += 1
        if close_paren < 0:
            raise SystemExit("[Phase6DQ] R35 unterminated F78F READ32 call")

        site_id += 1
        expr = body[open_paren + 1:close_paren].strip()
        expr_short = " ".join(expr.split())
        if len(expr_short) > 96:
            expr_short = expr_short[:93] + "..."
        replacement = f"phase6dq_f78f_read32({site_id}u, {expr})"
        spans.append((call, close_paren + 1, replacement))
        sites.append({
            "site_id": site_id,
            "address_expr": expr_short,
        })
        pos = close_paren + 1

    if not sites:
        raise SystemExit("[Phase6DQ] R35 found no routed READ32 calls in sub_0029F78F")

    for a, b, repl in reversed(spans):
        body = body[:a] + repl + body[b:]

    text = text[:start] + body + text[end:]
    return text, sites


def install_f78f_origin_support(text: str, sites: list[dict]) -> str:
    marker = '#pragma optimize("", off)\n'
    pos = text.find(marker)
    if pos < 0:
        raise SystemExit("[Phase6DQ] R35 optimize-off insertion marker missing")

    cases = []
    for row in sites:
        expr = _phase6dq_c_escape(row["address_expr"])
        cases.append(
            f'    case {row["site_id"]}u: return "{expr}";'
        )
    case_text = "\n".join(cases)

    block = f"""
static const char* phase6dq_f78f_site_expr(uint32_t site)
{{
    switch (site)
    {{
{case_text}
    default: return "<unknown>";
    }}
}}

static uint32_t phase6dq_f78f_read32(uint32_t site, uint32_t address)
{{
    uint32_t value = phase6ch_apu_read32(address);
    uint32_t index = s_phase6dqF78fReadCount % PHASE6DQ_F78F_READ_CAP;
    Phase6DQF78fRead* row = &s_phase6dqF78fReads[index];

    row->seq = s_phase6dqF78fReadCount + 1u;
    row->site = site;
    row->address = address;
    row->value = value;
    ++s_phase6dqF78fReadCount;

    if (value == 0xEC83F0E4u)
    {{
        ++s_phase6dqF78fPoisonHits;
        s_phase6dqF78fPoisonSite = site;
        s_phase6dqF78fPoisonAddress = address;
        s_phase6dqF78fPoisonValue = value;
        s_phase6dqF78fPoisonEax = eax;
        s_phase6dqF78fPoisonEcx = ecx;
        s_phase6dqF78fPoisonEdx = edx;
        s_phase6dqF78fPoisonEbx = ebx;
        s_phase6dqF78fPoisonEsi = esi;
        s_phase6dqF78fPoisonEdi = edi;
        s_phase6dqF78fPoisonEsp = esp;
    }}

    return value;
}}

"""
    return text[:pos] + block + text[pos:]


def instrument_xact_init_probe(text: str, base) -> str:
    """
    R36 targeted provenance for sub_0027DC5B. Capture only return values and
    computed event-array count/size. No control-flow or allocator semantics change.
    """
    masked = base.mask_noncode(text)
    m = re.search(r"(?m)^\s*(?:static\s+)?void\s+sub_0027DC5B\(void\)\s*\{", masked)
    if m is None:
        raise SystemExit("[Phase6DQ] R36 sub_0027DC5B body missing")
    brace = masked.find("{", m.start(), m.end())
    end = base.closing_brace(masked, brace)
    body = text[m.start():end]

    replacements = [
        (
            "    PUSH32(esp, 0); sub_0027D5C0(); /* call 0x0027D5C0 */",
            "    ++s_phase6dqXactInitEntries;\n"
            "    PUSH32(esp, 0); sub_0027D5C0(); /* call 0x0027D5C0 */",
        ),
        (
            "    esi = eax;\n    if (TEST_S(esi, esi)) goto loc_0027DD2C; /* jl: less (signed <) */",
            "    esi = eax;\n"
            "    s_phase6dqXactInitStage1Result = esi;\n"
            "    if (TEST_S(esi, esi)) goto loc_0027DD2C; /* jl: less (signed <) */",
        ),
        (
            "    esi = eax;\n    if (TEST_S(esi, esi)) goto loc_0027DD2C; /* jl: less (signed <) */",
            "    esi = eax;\n"
            "    s_phase6dqXactInitStage2Result = esi;\n"
            "    if (TEST_S(esi, esi)) goto loc_0027DD2C; /* jl: less (signed <) */",
        ),
    ]

    # First two identical post-call shapes must be replaced in order, once each.
    old = replacements[0][0]
    if body.count(old) != 1:
        raise SystemExit(f"[Phase6DQ] R36 expected one XACT entry call, found {body.count(old)}")
    body = body.replace(old, replacements[0][1], 1)

    post = replacements[1][0]
    if body.count(post) != 2:
        raise SystemExit(f"[Phase6DQ] R36 expected two XACT status gates, found {body.count(post)}")
    body = body.replace(post, replacements[1][1], 1)
    body = body.replace(post, replacements[2][1], 1)

    count_anchor = "    GUEST_WRITE32(ebx + 0x8C, eax);\n    eax = eax + eax * 2;"
    if body.count(count_anchor) != 1:
        raise SystemExit("[Phase6DQ] R36 event-count anchor drift")
    body = body.replace(
        count_anchor,
        "    GUEST_WRITE32(ebx + 0x8C, eax);\n"
        "    s_phase6dqXactInitEventCount = eax;\n"
        "    eax = eax + eax * 2;",
        1,
    )

    alloc_anchor = "    PUSH32(esp, eax);\n    PUSH32(esp, 0); sub_001787C0(); /* call 0x001787C0 */"
    if body.count(alloc_anchor) != 1:
        raise SystemExit("[Phase6DQ] R36 allocation-call anchor drift")
    body = body.replace(
        alloc_anchor,
        "    s_phase6dqXactInitEventBytes = eax;\n"
        "    PUSH32(esp, eax);\n"
        "    PUSH32(esp, 0); sub_001787C0(); /* call 0x001787C0 */",
        1,
    )

    alloc_result_anchor = "    esi = eax;\n    { uint32_t _neg_value = (uint32_t)(esi);"
    if body.count(alloc_result_anchor) != 1:
        raise SystemExit("[Phase6DQ] R36 allocation-result anchor drift")
    body = body.replace(
        alloc_result_anchor,
        "    esi = eax;\n"
        "    s_phase6dqXactInitAllocResult = esi;\n"
        "    { uint32_t _neg_value = (uint32_t)(esi);",
        1,
    )

    final_anchor = "    eax = esi;\n    POP32(esp, esi);"
    if body.count(final_anchor) != 1:
        raise SystemExit("[Phase6DQ] R36 final-result anchor drift")
    body = body.replace(
        final_anchor,
        "    eax = esi;\n"
        "    s_phase6dqXactInitFinalResult = eax;\n"
        "    POP32(esp, esi);",
        1,
    )

    return text[:m.start()] + body + text[end:]


def instrument_a41ee_site_tags(text: str, base) -> tuple[str, list[dict]]:
    """
    Minimal R31 provenance: before each direct sub_002A41EE call, write only
    a site ID and owner VA to globals. No stack read, no trace, no ring, no
    dispatch/pack reordering, and no change to fault semantics.
    """
    masked = base.mask_noncode(text)
    direct_re = re.compile(
        r"(?P<indent>[ \t]*)PUSH32\(\s*esp\s*,\s*0\s*\)\s*;\s*"
        r"sub_002A41EE\(\)\s*;\s*/\*\s*call\s+0x002A41EE\s*\*/"
    )
    patches = []
    sites = []
    site_id = 0

    for match in base.FUNC_RE.finditer(masked):
        name = match.group(1)
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if not vm:
            continue
        owner = int(vm.group(1), 16)
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            continue
        end = base.closing_brace(masked, open_index)
        body = text[open_index:end]

        for call in direct_re.finditer(body):
            site_id += 1
            absolute = open_index + call.start()
            indent = call.group("indent")
            tag = (
                f"{indent}s_phase6dqA41eeLastSite = {site_id}u;\n"
                f"{indent}s_phase6dqA41eeLastOwner = 0x{owner:08X}u;\n"
                f"{indent}++s_phase6dqA41eeSiteWrites;\n"
            )
            patches.append((absolute, tag))
            sites.append({
                "site_id": site_id,
                "owner_va": f"0x{owner:08X}",
                "owner_name": name,
            })

    for position, tag in reversed(patches):
        text = text[:position] + tag + text[position:]

    if not sites:
        raise SystemExit("[Phase6DQ] R31 found no packed direct A41EE callsites")

    return text, sites


def instrument_a4622_site_tags(text: str, base) -> tuple[str, list[dict]]:
    """
    Minimal R33 upstream provenance: before each direct sub_002A4622 call,
    write only a site ID and owner VA to globals. No stack reads, no trace,
    no ring, no pack reordering, no guest fault-policy changes.
    """
    masked = base.mask_noncode(text)
    call_re = re.compile(
        r"(?P<indent>[ \t]*)PUSH32\(\s*esp\s*,\s*0\s*\)\s*;\s*"
        r"sub_002A4622\(\)\s*;\s*/\*\s*call\s+0x002A4622\s*\*/"
    )
    patches = []
    sites = []
    site_id = 0

    for match in base.FUNC_RE.finditer(masked):
        name = match.group(1)
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if not vm:
            continue
        owner = int(vm.group(1), 16)
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            continue
        end = base.closing_brace(masked, open_index)
        body = text[open_index:end]

        for call in call_re.finditer(body):
            site_id += 1
            absolute = open_index + call.start()
            indent = call.group("indent")
            tag = (
                f"{indent}s_phase6dqA4622LastSite = {site_id}u;\n"
                f"{indent}s_phase6dqA4622LastOwner = 0x{owner:08X}u;\n"
                f"{indent}++s_phase6dqA4622SiteWrites;\n"
            )
            patches.append((absolute, tag))
            sites.append({
                "site_id": site_id,
                "owner_va": f"0x{owner:08X}",
                "owner_name": name,
            })

    for position, tag in reversed(patches):
        text = text[:position] + tag + text[position:]

    if not sites:
        raise SystemExit("[Phase6DQ] R33 found no packed direct A4622 callsites")

    return text, sites


def instrument_a52ad_site_tags(text: str, base) -> tuple[str, list[dict]]:
    """
    Minimal R34 upstream provenance: before each direct sub_002A52AD call,
    write only a site ID and owner VA to globals. No stack reads, traces,
    rings, pack reordering, or fault-policy changes.
    """
    masked = base.mask_noncode(text)
    call_re = re.compile(
        r"(?P<indent>[ \t]*)PUSH32\(\s*esp\s*,\s*0\s*\)\s*;\s*"
        r"sub_002A52AD\(\)\s*;\s*/\*\s*call\s+0x002A52AD\s*\*/"
    )
    patches = []
    sites = []
    site_id = 0

    for match in base.FUNC_RE.finditer(masked):
        name = match.group(1)
        vm = re.fullmatch(r"sub_([0-9A-Fa-f]{8})", name)
        if not vm:
            continue
        owner = int(vm.group(1), 16)
        open_index = masked.find("{", match.start(), match.end())
        if open_index < 0:
            continue
        end = base.closing_brace(masked, open_index)
        body = text[open_index:end]

        for call in call_re.finditer(body):
            site_id += 1
            absolute = open_index + call.start()
            indent = call.group("indent")
            tag = (
                f"{indent}s_phase6dqA52adLastSite = {site_id}u;\n"
                f"{indent}s_phase6dqA52adLastOwner = 0x{owner:08X}u;\n"
                f"{indent}++s_phase6dqA52adSiteWrites;\n"
            )
            if owner == 0x0029F78F:
                tag += (
                    f"{indent}++s_phase6dqF78fA52adCalls;\n"
                    f"{indent}s_phase6dqF78fA52adArg1 = recomp_guest_read32(esp);\n"
                    f"{indent}s_phase6dqF78fA52adEsp = esp;\n"
                    f"{indent}s_phase6dqF78fCallEax = eax;\n"
                    f"{indent}s_phase6dqF78fCallEcx = ecx;\n"
                    f"{indent}s_phase6dqF78fCallEdx = edx;\n"
                    f"{indent}s_phase6dqF78fCallEbx = ebx;\n"
                    f"{indent}s_phase6dqF78fCallEsi = esi;\n"
                    f"{indent}s_phase6dqF78fCallEdi = edi;\n"
                )
            patches.append((absolute, tag))

            # Static-only context: keep the nearest preceding PUSH32 expression
            # so the build log/manifest can identify the producer shape without
            # adding any runtime guest-memory reads.
            prefix = body[max(0, call.start() - 700):call.start()]
            pushes = list(re.finditer(r"PUSH32\(\s*esp\s*,\s*(.*?)\s*\)\s*;", prefix, re.DOTALL))
            arg_expr = pushes[-1].group(1).strip() if pushes else "<unresolved>"
            sites.append({
                "site_id": site_id,
                "owner_va": f"0x{owner:08X}",
                "owner_name": name,
                "nearest_pushed_arg_expr": arg_expr,
            })

    for position, tag in reversed(patches):
        text = text[:position] + tag + text[position:]

    if not sites:
        raise SystemExit("[Phase6DQ] R34 found no packed direct A52AD callsites")

    return text, sites


def instrument_r43_ac97_channel_writes(text: str) -> str:
    """Tag the exact AC97 channel-table consumers implicated by R41/R42.

    Anchor on translated VA labels rather than generated function wrapper
    names. The support-clean pack can change wrapper boundaries while the
    retail instruction labels themselves remain authoritative.
    """
    specs = (
        (
            "loc_002A74ED: ;",
            "loc_002A7505: ;",
            "phase6ch_apu_write8(eax + -20971253, 0);",
            "phase6dq_note_ac97_channel_write(0x002A74EDu, esi, phase6ch_apu_read32(esi), eax, 0u);\n    phase6ch_apu_write8(eax + -20971253, 0);",
            "002A74ED channel write",
        ),
        (
            "loc_002A7712: ;",
            "loc_002A7734: ;",
            "phase6ch_apu_write8(eax + -20971253, 2);",
            "phase6dq_note_ac97_channel_write(0x002A7712u, esi, phase6ch_apu_read32(esi), eax, 2u);\n    phase6ch_apu_write8(eax + -20971253, 2);",
            "002A7712 channel write",
        ),
        (
            "loc_002A77FB: ;",
            "loc_002A7813: ;",
            "phase6ch_apu_write8(eax + -20971253, 0x1D);",
            "phase6dq_note_ac97_channel_write(0x002A77FBu, esi, phase6ch_apu_read32(esi), eax, 0x1Du);\n    phase6ch_apu_write8(eax + -20971253, 0x1D);",
            "002A77FB channel write",
        ),
        (
            "loc_002A7BA6: ;",
            "loc_002A7BBB: ;",
            "phase6ch_apu_write8(ecx + -20971253, 2);",
            "phase6dq_note_ac97_channel_write(0x002A7BA6u, 0u, (eax - 4u) >> 2, ecx, 2u);\n    phase6ch_apu_write8(ecx + -20971253, 2);",
            "002A7BA6 startup channel reset",
        ),
    )

    for begin_label, end_label, old, new, label in specs:
        begin = text.find(begin_label)
        if begin < 0:
            raise SystemExit(f"[Phase6DQ] R43 missing translated label {begin_label}")

        finish = text.find(end_label, begin + len(begin_label))
        if finish < 0:
            raise SystemExit(
                f"[Phase6DQ] R43 missing successor {end_label} after {begin_label}"
            )

        window = text[begin:finish]
        count = window.count(old)
        if count != 1:
            print(f"[Phase6DQ] R43 source window for {label}:")
            for source_line in window.splitlines():
                print("[Phase6DQ]   " + source_line)
            raise SystemExit(
                f"[Phase6DQ] R43 expected one {label} in exact label window, found {count}"
            )

        window = window.replace(old, new, 1)
        text = text[:begin] + window + text[finish:]

    return text



def instrument_r45_audio_object_provenance(text: str) -> str:
    """Trace the five proven callers of 002A76FE and contain only R43\'s exact poison."""

    callsites = (
        ("loc_002A11BB: ;", "loc_002A11C0: ;", 0x002A11BB),
        ("loc_002A11C7: ;", "loc_002A11CC: ;", 0x002A11C7),
        ("loc_002A778D: ;", "loc_002A7794: ;", 0x002A778D),
        ("loc_002A77E4: ;", "loc_002A77EB: ;", 0x002A77E4),
        ("loc_002A78A2: ;", "loc_002A78A9: ;", 0x002A78A2),
    )
    direct = "PUSH32(esp, 0); sub_002A76FE(); /* call 0x002A76FE */"

    for begin_label, end_label, site in callsites:
        begin = text.find(begin_label)
        if begin < 0:
            raise SystemExit(f"[Phase6DQ] R45 missing callsite label {begin_label}")
        finish = text.find(end_label, begin + len(begin_label))
        if finish < 0:
            raise SystemExit(
                f"[Phase6DQ] R45 missing successor {end_label} after {begin_label}"
            )
        window = text[begin:finish]
        if window.count(direct) != 1:
            raise SystemExit(
                f"[Phase6DQ] R45 expected one 002A76FE call at 0x{site:08X}, "
                f"found {window.count(direct)}"
            )
        tagged = (
            f"phase6dq_r45_note_audio_object_call(0x{site:08X}u, ecx);\n    "
            + direct
        )
        window = window.replace(direct, tagged, 1)
        text = text[:begin] + window + text[finish:]

    entry_begin = text.find("loc_002A76FE: ;")
    entry_end = text.find("loc_002A7712: ;", entry_begin)
    if entry_begin < 0 or entry_end < 0:
        raise SystemExit("[Phase6DQ] R45 002A76FE entry window missing")
    entry_window = text[entry_begin:entry_end]
    entry_tick = "PHASE4C_BUDGET_TICK(0x002A76FEu);"
    if entry_window.count(entry_tick) != 1:
        raise SystemExit("[Phase6DQ] R45 002A76FE entry tick shape changed")
    entry_window = entry_window.replace(
        entry_tick,
        entry_tick
        + "\n    phase6dq_r45_note_audio_object_call(0x002A76FEu, ecx);",
        1,
    )
    text = text[:entry_begin] + entry_window + text[entry_end:]

    lookup_begin = text.find("loc_002A7712: ;")
    lookup_end = text.find("loc_002A7734: ;", lookup_begin)
    if lookup_begin < 0 or lookup_end < 0:
        raise SystemExit("[Phase6DQ] R45 002A7712 lookup window missing")
    lookup_window = text[lookup_begin:lookup_end]

    object_read = "eax = phase6ch_apu_read32(esi);"
    object_read_count = lookup_window.count(object_read)
    table_read_matches = list(
        re.finditer(
            r"eax\s*=\s*phase6ch_apu_read32\(\s*eax\s*\*\s*4\s*\+\s*0x2BA9C0\s*\)\s*;",
            lookup_window,
        )
    )
    if object_read_count != 1 or len(table_read_matches) != 1:
        print("[Phase6DQ] R45 002A7712 lookup window:")
        for source_line in lookup_window.splitlines():
            print("[Phase6DQ]   " + source_line)
        raise SystemExit(
            "[Phase6DQ] R45 expected one object-index read and one 002BA9C0 "
            f"table read; found object={object_read_count} table={len(table_read_matches)}"
        )

    replacement = (
        object_read
        + "\n    phase6dq_r45_note_audio_object_call(0x002A7712u, esi);"
        + "\n    if (phase6dq_r45_bad_audio_object(0x002A7712u, esi, eax)) "
        + "goto loc_002A776D;"
    )
    lookup_window = lookup_window.replace(object_read, replacement, 1)
    text = text[:lookup_begin] + lookup_window + text[lookup_end:]

    return text

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

    candidates, available_counts, selected_counts = select_candidates(
        generated, old, existing_defs
    )
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
    main_text = instrument_r43_ac97_channel_writes(main_text)
    main_text = instrument_r45_audio_object_provenance(main_text)
    main_text = instrument_xact_init_probe(main_text, base)
    main_text, f78f_read_sites = instrument_f78f_origin_probe(main_text, base)
    main_text = install_f78f_origin_support(main_text, f78f_read_sites)
    main_text, a41ee_site_tags = instrument_a41ee_site_tags(main_text, base)
    main_text, a4622_site_tags = instrument_a4622_site_tags(main_text, base)
    main_text, a52ad_site_tags = instrument_a52ad_site_tags(main_text, base)
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
        "maximum trustworthy progress toward guest presentation per hardware run"
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
        "P6DQ ROCKET HARD REGS",
        "P6DQ ROCKET VP WRITE FIRST",
        "P6DQ ROCKET VP READ HARD",
        "P6DQ ROCKET JOURNAL SUMMARY A",
        "P6DQ ROCKET JOURNAL SUMMARY D",
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
        "P6DQ AC97 TABLE WRITE WATCH: count=%u addr=%08X width=%u value=%08X",
        "P6DQ AC97 CHANNEL WRITE: count=%u site=%08X object=%08X index=%08X",
        "P6DQ AC97 TABLE PROVENANCE: table0=%08X table1=%08X write_watch=%u",
        "P6DQ R45 AUDIO OBJECT: call=%u bad=%u bad_count=%u site=%08X object=%08X",
        "P6DQ R45 AUDIO CONTAIN: count=%u site=%08X object=%08X index=%08X",
        "phase6dq_r45_note_audio_object_call(0x002A11BBu, ecx);",
        "phase6dq_r45_note_audio_object_call(0x002A11C7u, ecx);",
        "phase6dq_r45_note_audio_object_call(0x002A778Du, ecx);",
        "phase6dq_r45_note_audio_object_call(0x002A77E4u, ecx);",
        "phase6dq_r45_note_audio_object_call(0x002A78A2u, ecx);",
        "phase6dq_r45_note_audio_object_call(0x002A76FEu, ecx);",
        "phase6dq_r45_note_audio_object_call(0x002A7712u, esi);",
        "goto loc_002A776D;",
        "loc_002A74ED: ;",
        "loc_002A7712: ;",
        "loc_002A77FB: ;",
        "loc_002A7BA6: ;",
        "phase6dq_note_ac97_channel_write(0x002A74EDu",
        "phase6dq_note_ac97_channel_write(0x002A7712u",
        "phase6dq_note_ac97_channel_write(0x002A77FBu",
        "phase6dq_note_ac97_channel_write(0x002A7BA6u",
        "P6DQ AC97 OUT READ stream=%s width=%u addr=%08X",
        "P6DQ AC97 OUT WRITE stream=%s width=%u addr=%08X",
        "P6DQ AC97 OUTPUT: reads=%u writes=%u pcm_bdbar=%08X",
        "address >= 0xFEC00110u && address <= 0xFEC0011Bu",
        "address >= 0xFEC00170u && address <= 0xFEC0017Bu",
        "bm->bdbar = value & ~3u;",
        "P6DQ AC97 GLOBAL READ addr=%08X value=%08X",
        "P6DQ AC97 GLOBAL WRITE addr=%08X value=%08X",
        "P6DQ AC97 GLOBAL: reads=%u writes=%u glob_cnt=%08X glob_sta=%08X codec_ready=%u",
        "address == 0xFEC0012Cu || address == 0xFEC00130u",
        "value = s_phase6dqAc97GlobSta | 0x00000100u",
        "target == 0x8000002Cu",
        "target == 0x8000006Du",
        "target == 0x80000062u",
        "P6DQ HALGETVECTOR44: calls=%u bus=%u irql_ptr=%08X vector=%08X irql=%u",
        "P6DQ KEINITINT109: calls=%u object=%08X routine=%08X context=%08X vector=%08X",
        "P6DQ KECONNECT98: calls=%u successes=%u object=%08X bus=%u irql=%u mode=%u result=%u",
        "P6DQ IRQ SETUP: hal44=%u bus=%u vector=%08X irql=%u init109=%u object=%08X routine=%08X context=%08X connect98=%u successes=%u",
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
        "a41ee_site=%u a41ee_owner=%08X a41ee_writes=%u",
        "s_phase6dqA41eeLastSite = ",
        "s_phase6dqA4622LastSite = ",
        "s_phase6dqA52adLastSite = ",
        "a4622_site=%u a4622_owner=%08X a4622_writes=%u",
        "a52ad_site=%u a52ad_owner=%08X a52ad_writes=%u",
        "P6DQ F78F ORIGIN:",
        "P6DQ XACT INIT: entries=%u stage1_29FDF0=%08X stage2_28345A=%08X event_count=%u event_bytes=%u alloc=%08X final=%08X",
        "s_phase6dqXactInitStage1Result = esi;",
        "s_phase6dqXactInitStage2Result = esi;",
        "s_phase6dqXactInitAllocResult = esi;",
        "P6DQ F78F READ seq=%u site=%u addr=%08X value=%08X expr=%s",
        "phase6dq_f78f_read32(",
        "s_phase6dqF78fA52adArg1 = recomp_guest_read32(esp);",
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
        "audio_interrupt_registration_bridge": {
            "hardware_proof": "R39",
            "hal_get_interrupt_vector": {
                "ordinal": 44,
                "target": "0x8000002C",
                "observed_bus_irq": 6,
                "irq_base": "0x30",
                "expected_vector": "0x36",
                "expected_irql": 21,
            },
            "ke_initialize_interrupt": {
                "ordinal": 109,
                "target": "0x8000006D",
                "guest_kinterrupt_layout_written": True,
                "dispatch_code_fabricated": False,
            },
            "ke_connect_interrupt": {
                "ordinal": 98,
                "target": "0x80000062",
                "serialized_connection_state": True,
                "host_isr_fabricated": False,
            },
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
        "r43_ac97_channel_table_provenance": {
            "r41_fault": "WRITE8 0xDEA85111",
            "r42_table_base": "0x002BA9C0",
            "r42_expected_entry_shape": ["0x00000010", "0x00000070"],
            "candidate_sites": [
                "0x002A74ED",
                "0x002A7712",
                "0x002A77FB",
                "0x002A7BA6",
            ],
            "table_write_watch": True,
            "channel_index_and_table_value_capture": True,
            "invalid_write_bypassed": False,
            "guest_memory_semantics_changed": False,
        },
        "r45_bad_audio_object_provenance": {
            "r43_proof_site": "0x002A7712",
            "r43_proof_object": "0x00040000",
            "r43_proof_index": "0x00000400",
            "r43_proof_table0": "0x00000010",
            "r43_proof_table1": "0x00000070",
            "direct_call_sites": [
                "0x002A11BB",
                "0x002A11C7",
                "0x002A778D",
                "0x002A77E4",
                "0x002A78A2",
            ],
            "target_entry": "0x002A76FE",
            "lookup_site": "0x002A7712",
            "exact_bad_signature_contained": True,
            "containment_epilogue": "0x002A776D",
            "table_index_clamped": False,
            "table_rewritten": False,
            "ordinary_audio_objects_bypassed": False,
            "diagnostic_only": True,
        },
        "ac97_output_busmaster_bridge": {
            "hardware_proof": "R40",
            "pcm_out_base": "0xFEC00110",
            "spdif_out_base": "0xFEC00170",
            "register_layout": [
                "BDBAR+0 dword",
                "CIV+4 byte",
                "LVI+5 byte",
                "SR+6 word",
                "PICB+8 word",
                "PIV+10 byte",
                "CR+11 byte",
            ],
            "pcm_descriptor_base_hardware_value": "0x0248F000",
            "reference_models": [
                "QEMU AC97 native-audio bus-master",
                "XboxDev nxdk lib/hal/audio.c",
            ],
            "bdbars_are_dword_aligned": True,
            "status_w1c_semantics": True,
            "control_reset_semantics": True,
            "descriptor_header_latched_on_run": True,
            "native_audio_samples_emitted": False,
            "host_isr_fabricated": False,
            "scope": "PCM-out + Xbox SPDIF output bus-master register state only",
        },
        "ac97_codec_ready_bridge": {
            "hardware_proof": "R36/R38",
            "glob_cnt_address": "0xFEC0012C",
            "glob_sta_address": "0xFEC00130",
            "primary_codec_ready_mask": "0x00000100",
            "reference_model": "QEMU AC97 GLOB_CNT/GLOB_STA",
            "scope": "exact global-control/status dword pair only",
            "other_fec_page_semantics_expanded": False,
            "dsound_nodriver_bypass_faked": False,
            "retail_poll_semantics_preserved": True,
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
        "r33_minimal_provenance": {
            "stable_pack_order": "exact_R25",
            "a41ee_site_count": len(a41ee_site_tags),
            "a41ee_sites": a41ee_site_tags,
            "a4622_site_count": len(a4622_site_tags),
            "a4622_sites": a4622_site_tags,
            "a52ad_site_count": len(a52ad_site_tags),
            "a52ad_sites": a52ad_site_tags,
            "f78f_origin_probe": {
                "target": "0x0029F78F",
                "read_site_count": len(f78f_read_sites),
                "read_sites": f78f_read_sites,
                "ring_capacity": 24,
                "poison_value": "0xEC83F0E4",
                "per_read_logging": False,
                "read_values_changed": False,
                "a52ad_arg1_capture": True,
            },
            "callsite_stack_reads": True,
            "callsite_traces": False,
            "ring_buffer": False,
            "fault_semantics_changed": False,
            "trace_records_bounded": True,
            "startup_policy_restored_to_r25_length": True,
        },
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

    (args.out_dir / "phase6dq-manifest.json").write_text(
        json.dumps(manifest, indent=2) + "\n", encoding="utf-8"
    )

    total_source = sum(len(rendered.get(va, "")) for va in new_members)
    print(f"[Phase6DQ] emitter revision: {EMITTER_REVISION}")
    print("[Phase6DQ] ROCKET PHASE: ENABLED")
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
    print(f"[Phase6DQ] R43 A41EE site tags: {len(a41ee_site_tags)}")
    print(f"[Phase6DQ] R43 A4622 upstream site tags: {len(a4622_site_tags)}")
    print(f"[Phase6DQ] R43 A52AD upstream site tags: {len(a52ad_site_tags)}")
    print(f"[Phase6DQ] R43 F78F targeted READ32 sites: {len(f78f_read_sites)}")
    for site in f78f_read_sites:
        print(f"[Phase6DQ] R43 F78F READ[{site['site_id']}] expr={site['address_expr']}")
    print("[Phase6DQ] R43 AC97 CODEC READY: R39 hardware-proven semantics retained")
    print("[Phase6DQ] R43 AUDIO IRQ SETUP: R40 hardware-proven ordinals 44/109/98 retained")
    print("[Phase6DQ] R43 AC97 OUTPUT BUSMASTER: R41 hardware-proven PCM BDBAR state retained")
    print("[Phase6DQ] R43 TABLE PROVENANCE: watch 002BA9C0/4 mutations + exact channel-index consumers")
    print("[Phase6DQ] R43 CANDIDATES: 002A74ED / 002A7712 / 002A77FB / startup 002A7BA6")
    print("[Phase6DQ] R43 SAFETY: no invalid-write bypass; ordinary guest fault policy unchanged")
    print("[Phase6DQ] R43 debugger safety: bounded runtime DebugStrings retained")
    print("[Phase6DQ] Pixel chase/present proximity instrumentation: INHERITED")
    print("[Phase6DQ] EMIT RESULT: PASS")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
