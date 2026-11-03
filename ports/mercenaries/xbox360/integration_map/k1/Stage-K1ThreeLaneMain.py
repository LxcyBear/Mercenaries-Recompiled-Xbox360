#!/usr/bin/env python3
"""Stage three independent K1 lanes into ONE main-only Xbox build.

A: exact hardware-proven PFIFO DMA_PUT readback + bounded guest-write shadow.
B: wall-clock runtime timing from existing rare P6DQ spin/fault trace events.
C: first dispatch attempts for original Swap/PersistDisplay, not a fake Swap.
Keep 64 TrueTUs untouched. All other MMIO still hard-fenced. Source-only.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PARENT = "P6K1DQ-QUIET-LOG-20261103"
MARK = "P6K1-THREELANE-20261103"
READ32 = re.compile(
    r"(?m)^[ \t]*uint32_t[ \t]+recomp_guest_read32[ \t]*"
    r"\(\s*uint32_t[ \t]+address\s*\)\s*\{"
)
WRITE32 = re.compile(
    r"(?m)^[ \t]*void[ \t]+recomp_guest_write32[ \t]*"
    r"\(\s*uint32_t[ \t]+address\s*,\s*uint32_t[ \t]+value\s*\)\s*\{"
)
FRONTIER = re.compile(
    r"(?m)^[ \t]*static[ \t]+void[ \t]+phase6dq_note_dispatch\s*"
    r"\(\s*uint32_t[ \t]+kind\s*,\s*uint32_t[ \t]+target\s*,"
    r"\s*uint32_t[ \t]+caller\s*,\s*uint32_t[ \t]+espValue\s*\)\s*\{"
)
TRACE_START = re.compile(
    r"(?m)^[ \t]*void[ \t]+trace[ \t]*\("
    r"const[ \t]+char[ \t]*\*[ \t]*line\s*\)\s*\{"
)

PFIFO_STATE = '''
/* K1 PFIFO DMA_PUT: exact NV2A CACHE1 register, PFIFO offset 0x1240.
 * Power-on/reset mirror starts zero (NV2A PFIFO registers reset to zero).
 * Track subsequent valid guest PUT writes, never translate into a push.
 * Read is initially accepted ONLY from XBE instruction 0028ED6B.
 * The write gate accepts the same register ONLY from D3D code.
 */
static uint32_t s_k1PfifoDmaPut = 0u;
static unsigned int s_k1PfifoDmaPutReads = 0u;
static unsigned int s_k1PfifoDmaPutWrites = 0u;
'''

PFIFO_READ = '''
    if (address == 0xFD003240u &&
        (k1c_read_guest_va() == 0x0028ED6Bu ||
         s_k1PfifoDmaPutWrites != 0u))
    {
        ++s_k1PfifoDmaPutReads;
        if (s_k1PfifoDmaPutReads == 1u ||
            (s_k1PfifoDmaPutReads & 255u) == 0u)
        {
            char k1PfifoLine[240];
            sprintf(k1PfifoLine,
                "K1PFIFO DMA_PUT READ32: addr=%08X value=%08X reads=%u writes=%u guest_va=%08X",
                (unsigned int)address, (unsigned int)s_k1PfifoDmaPut,
                s_k1PfifoDmaPutReads, s_k1PfifoDmaPutWrites,
                (unsigned int)k1c_read_guest_va());
            trace(k1PfifoLine);
        }
        return s_k1PfifoDmaPut;
    }
'''

PFIFO_WRITE = '''
    if (address == 0xFD003240u &&
        k1c_read_guest_va() >= 0x00288640u &&
        k1c_read_guest_va() < 0x0029B880u &&
        (value & 0xE0000003u) == 0u)
    {
        /* Low two bits encode dword alignment; 0x1FFFFFFC is PUT offset. */
        s_k1PfifoDmaPut = value;
        ++s_k1PfifoDmaPutWrites;
        if (s_k1PfifoDmaPutWrites == 1u ||
            (s_k1PfifoDmaPutWrites & 255u) == 0u)
        {
            char k1PfifoLine[240];
            sprintf(k1PfifoLine,
                "K1PFIFO DMA_PUT WRITE32: addr=%08X value=%08X writes=%u guest_va=%08X",
                (unsigned int)address, (unsigned int)value,
                s_k1PfifoDmaPutWrites, (unsigned int)k1c_read_guest_va());
            trace(k1PfifoLine);
        }
        return;
    }
'''

PERF = '''
    /* K1 performance lane: native clock only on existing sparse telemetry.
       Never alter PHASE4C_BUDGET_TICK or skip any retail code path. */
    static DWORD k1PerfLastTimeMs = 0u;
    static unsigned int k1PerfLastTick = 0u;
    static unsigned int k1PerfSamples = 0u;
    if (strncmp(line, "P6DQ SPIN SAMPLE tick=", 22u) == 0)
    {
        unsigned int k1CurrentTick = 0u;
        if (sscanf(line, "P6DQ SPIN SAMPLE tick=%u", &k1CurrentTick) == 1)
        {
            const DWORD k1CurrentTimeMs = GetTickCount();
            if (k1PerfSamples != 0u && k1CurrentTick > k1PerfLastTick)
            {
                const DWORD k1ElapsedMs = k1CurrentTimeMs - k1PerfLastTimeMs;
                char k1PerfLine[240];
                sprintf(k1PerfLine,
                    "K1PERF WINDOW: from_tick=%u to_tick=%u elapsed_ms=%u ticks_per_sec=%u",
                    k1PerfLastTick, k1CurrentTick,
                    (unsigned int)k1ElapsedMs,
                    k1ElapsedMs == 0u ? 0u :
                    (unsigned int)(((uint64_t)(k1CurrentTick - k1PerfLastTick)
                                   * 1000u) / k1ElapsedMs));
                k1quiet_emit_unfiltered(k1PerfLine);
            }
            ++k1PerfSamples;
            k1PerfLastTick = k1CurrentTick;
            k1PerfLastTimeMs = k1CurrentTimeMs;
        }
    }
    if (strncmp(line, "P6DQ ROCKET HARD STOP", 21u) == 0 &&
        k1PerfSamples != 0u)
    {
        const char* k1Ticks = strstr(line, "ticks=");
        unsigned int k1FaultTick = 0u;
        if (k1Ticks != NULL && sscanf(k1Ticks, "ticks=%u", &k1FaultTick) == 1 &&
            k1FaultTick >= k1PerfLastTick)
        {
            const DWORD k1ElapsedMs = GetTickCount() - k1PerfLastTimeMs;
            char k1PerfLine[240];
            sprintf(k1PerfLine,
                "K1PERF LAST_TO_FAULT: from_tick=%u to_tick=%u elapsed_ms=%u ticks_per_sec=%u",
                k1PerfLastTick, k1FaultTick, (unsigned int)k1ElapsedMs,
                k1ElapsedMs == 0u ? 0u :
                (unsigned int)(((uint64_t)(k1FaultTick - k1PerfLastTick)
                               * 1000u) / k1ElapsedMs));
            k1quiet_emit_unfiltered(k1PerfLine);
        }
    }
'''

PRESENT_WATCH = '''
    /* K1 presentation lane: records attempts through the existing
       packed frontier only. Direct compiled calls are NOT observed here.
       No fake display_calls, framebuffer, Swap, or Xenos Present. */
    if (target == 0x0028BDB0u || target == 0x0028A530u)
    {
        static unsigned int k1PresentSwapFrontier = 0u;
        static unsigned int k1PresentPersistFrontier = 0u;
        unsigned int* k1PresentCounter = target == 0x0028BDB0u
            ? &k1PresentSwapFrontier : &k1PresentPersistFrontier;
        ++*k1PresentCounter;
        if (*k1PresentCounter <= 4u ||
            (*k1PresentCounter & 255u) == 0u)
        {
            char k1PresentLine[240];
            sprintf(k1PresentLine,
                "K1PRESENT FRONTIER ROUTE: kind=%u target=%08X caller=%08X hits=%u",
                kind, target, caller, *k1PresentCounter);
            trace(k1PresentLine);
        }
    }
'''


def once_insert(src: str, expression: re.Pattern, insertion: str,
                label: str) -> str:
    found = list(expression.finditer(src))
    if len(found) != 1:
        raise ValueError(f"Expected exactly one {label} definition, got {len(found)}")
    at = found[0].end()
    nl = "\r\n" if "\r\n" in src else "\n"
    payload = insertion.replace("\n", nl)
    return src[:at] + payload + src[at:]


def patch(src: str) -> str:
    if src.count(PARENT) != 1 or "K1QUIET MILESTONE SUMMARY:" not in src:
        raise ValueError("Missing unique verified DAC/quiet main parent")
    if MARK in src or "K1PFIFO DMA_PUT READ32:" in src:
        raise ValueError("Three-lane patch already installed")
    # The DAC/PRMDIO parent already calls this guest-VA witness in its
    # hardware-tested logging path. Do not assume whether the generated
    # definition/prototype carries a semicolon, a modifier, or a line break.
    if "P6DQ ROCKET HARD STOP" not in src or "k1c_read_guest_va()" not in src:
        raise ValueError("Missing hardware-tested guest-VA call or original hard stop")
    if "\r" in src.replace("\r\n", ""):
        raise ValueError("Mixed end-of-line source")
    before = src
    # Place source-owned state immediately before the central read handler.
    reader = list(READ32.finditer(src))
    if len(reader) != 1:
        raise ValueError("Expected unique external recomp_guest_read32 definition")
    nl = "\r\n" if "\r\n" in src else "\n"
    src = src[:reader[0].start()] + PFIFO_STATE.replace("\n", nl) + src[reader[0].start():]
    src = once_insert(src, READ32, PFIFO_READ, "read32")
    src = once_insert(src, WRITE32, PFIFO_WRITE, "write32")
    src = once_insert(src, TRACE_START, PERF, "global trace")
    src = once_insert(src, FRONTIER, PRESENT_WATCH, "phase6dq_note_dispatch")
    src = src.replace(PARENT, PARENT + " | " + MARK, 1)
    for marker in ("K1PFIFO DMA_PUT READ32:", "K1PFIFO DMA_PUT WRITE32:",
                   "K1PERF WINDOW:", "K1PERF LAST_TO_FAULT:",
                   "K1PRESENT FRONTIER ROUTE:"):
        if src.count(marker) != 1:
            raise ValueError(f"Instrumentation marker drift {marker}")
    # Reversal by exact text inserts is stronger than comparing line-counts.
    reverted = src.replace(PARENT + " | " + MARK, PARENT, 1)
    for part in (PFIFO_STATE, PFIFO_READ, PFIFO_WRITE, PERF, PRESENT_WATCH):
        needle = part.replace("\n", nl)
        if reverted.count(needle) != 1:
            raise ValueError("Injected source fragment was altered/duplicated")
        reverted = reverted.replace(needle, "", 1)
    if reverted != before:
        raise ValueError("Non-instrumented main source changed")
    if re.search(r"(?m)^\s*static\s+void\s+trace\s*\(", src):
        raise ValueError("Trace external symbol accidentally made static")
    return src


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def selftest() -> None:
    fixture = """static DWORD k1c_read_guest_va(void);
void trace(const char* line)
{
    static const char* k1qFrames[4] = {0};
    k1quiet_emit_unfiltered(line);
}
uint32_t recomp_guest_read32(uint32_t address)
{
    return GUEST_READ32(address);
}
void recomp_guest_write32(uint32_t address, uint32_t value)
{
    GUEST_WRITE32(address, value);
}
static void phase6dq_note_dispatch(
    uint32_t kind,
    uint32_t target,
    uint32_t caller,
    uint32_t espValue)
{
    uint32_t i;
    trace("P6DQ ROCKET HARD STOP");
}
void startup()
{
    trace("P6K1DQ-QUIET-LOG-20261103");
    trace("K1QUIET MILESTONE SUMMARY:");
}
"""
    for initial in (fixture, fixture.replace("\n", "\r\n")):
        result = patch(initial)
        assert result.count("K1PRESENT FRONTIER ROUTE:") == 1
        assert result.count("K1PERF WINDOW:") == 1
        assert result.count("K1PFIFO DMA_PUT READ32:") == 1
        assert result.count("K1PFIFO DMA_PUT WRITE32:") == 1
        assert "address == 0xFD003240u" in result
        assert "k1c_read_guest_va() == 0x0028ED6Bu" in result
        assert "GetTickCount()" in result
        assert "GUEST_WRITE32(address, value);" in result
        assert "GUEST_READ32(address);" in result
        try:
            patch(result)
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted duplicate three-lane main")
        try:
            patch(initial.replace("P6DQ ROCKET HARD STOP", "NO HARD STOP"))
        except ValueError:
            pass
        else:
            raise AssertionError("Accepted missing original MMIO hard fence")
    print("[K1-3LANE] SELFTEST PASS: bounded PFIFO DMA_PUT state, rare wallclock probes, specific presentation dispatch witnesses, reversible main-only patch")


def stage(args):
    parent, out, manifest = (args.parent.resolve(), args.out.resolve(),
                             args.manifest.resolve())
    if parent == out or parent.parent == out.parent:
        raise ValueError("Refuse in-place edit of hardware-proven quiet parent")
    before = parent.read_bytes()
    after = patch(before.decode("utf-8")).encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.exists():
        if out.read_bytes() != after:
            raise ValueError("Staged multi-lane main source drift; refuse overwrite")
    else:
        if manifest.exists():
            raise ValueError("Existing multi-lane manifest without source; refuse")
        out.write_bytes(after)
    if parent.read_bytes() != before:
        raise ValueError("Parent source modified during stage")
    record = {
        "marker": MARK,
        "status": "K1_THREE_LANE_SOURCE_STAGED_NO_XDK",
        "parent_main_sha256": sha(before),
        "new_main_sha256": sha(after),
        "pfifo_register": "NV_PFIFO_CACHE1_DMA_PUT",
        "pfifo_address": "0xFD003240",
        "pfifo_initial_read_site": "0x0028ED6B",
        "pfifo_reset_value": 0,
        "unknown_mmio_still_fenced": True,
        "perf_extra_budget_ticks": 0,
        "perf_sampled_from_existing_logs": True,
        "present_attempts_only_no_fake_swap": True,
        "synthetic_pixels": False,
        "translated_tus_changed": 0,
        "runtime_headers_changed": 0,
        "hardware_verified": False,
    }
    raw = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    if manifest.exists():
        if manifest.read_bytes() != raw:
            raise ValueError("Staged multi-lane manifest drift")
    else:
        manifest.write_bytes(raw)
    print("[K1-3LANE] STAGE PASS: exact NV2A PFIFO DMA_PUT, wallclock windows, Swap/Persist frontier probes")
    print("[K1-3LANE] Guest TrueTUs untouched, original faults retained, XDK/hardware still unverified")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("--self-test", action="store_true")
    p.add_argument("--parent", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--manifest", type=Path)
    a = p.parse_args()
    if a.self_test:
        selftest()
        return
    if not a.parent or not a.out or not a.manifest:
        p.error("--parent, --out, --manifest required")
    stage(a)


if __name__ == "__main__":
    main()
