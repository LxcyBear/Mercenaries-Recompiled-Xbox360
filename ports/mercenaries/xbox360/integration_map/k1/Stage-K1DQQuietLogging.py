#!/usr/bin/env python3
"""Main-only Phase6DQ xbWatson success-pair coalescer.

The 2026-11-03 hardware log contained 4588 repetitive success/entry lines:
640+640 LowerIRQL; 628+628 RaiseIRQL; 513+513 EnterCS; 513+513 LeaveCS.
Wrap the existing trace output sink, not the guest calls or translated TUs.
Hold each LIVE FRAME until the immediately following matching PASS.  If the
next trace is not the exact expected success or the IRQL result is anomalous,
flush the pending LIVE FRAME and the actual next line unfiltered.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

PARENT = "P6K1NV2A-DAC-PALETTE-20261103"
MARK = "P6K1DQ-QUIET-LOG-20261103"
# Real generated mains can use a different parameter name, place the
# opening brace on the signature line, or use LF/CRLF around arguments.
# Match a DEFINITION (not a prototype), then verify the actual body has all
# three inherited Xbox debug/file sinks before changing anything.
DECL = re.compile(
    r"(?m)^[ \t]*(?:(?:static|inline|__forceinline)\s+)*"
    r"(?:void|VOID)\s+(?:__cdecl\s+)?(?P<name>trace)\b\s*"
    r"\((?P<args>[^(){};]{1,256})\)\s*\{"
)
TRACE_CANDIDATE = re.compile(
    r"(?m)^[ \t]*[^\r\n]{0,160}\btrace\s*\([^\r\n]{0,160}"
)
WRAPPER = r'''
/* K1DQ quiet mode: coalesce only exact, verified successful log pairs.
 * No kernel calls, guest operations, fault paths, or other loggers changed.
 * All other messages (incl. failures, MMIO, XInput, DAC, Present) pass.
 */
static void trace(const char* line)
{
    static const char* k1qFrames[4] = {
        "KfLowerIrql LIVE FRAME:",
        "KfRaiseIrql LIVE FRAME:",
        "RtlEnterCriticalSection LIVE FRAME:",
        "RtlLeaveCriticalSection LIVE FRAME:"
    };
    static const char* k1qSuccesses[4] = {
        "PASS: Phase 6DQ KfLowerIrql",
        "PASS: Phase 6DQ KfRaiseIrql",
        "PASS: ordinal 277 RtlEnterCriticalSection",
        "PASS: ordinal 294 RtlLeaveCriticalSection"
    };
    static const char* k1qNames[4] = {
        "KfLowerIrql", "KfRaiseIrql",
        "RtlEnterCriticalSection", "RtlLeaveCriticalSection"
    };
    static unsigned int k1qSuccessfulPairs[4] = {0u, 0u, 0u, 0u};
    static unsigned int k1qMutedLines[4] = {0u, 0u, 0u, 0u};
    static char k1qPendingLine[1024] = {0};
    static int k1qPendingKind = -1;
    if (k1qPendingKind >= 0)
    {
        const int p = k1qPendingKind;
        const int matched = (strncmp(line, k1qSuccesses[p],
                           strlen(k1qSuccesses[p])) == 0);
        int expected = matched;
        /* Preserve unusual IRQL transition results, even on a PASS log. */
        if (expected && p <= 1)
        {
            const int knownOld = strstr(line, "old=0 ") != NULL ||
                                 strstr(line, "old=2 ") != NULL;
            const int knownNew = (p == 0)
                ? (strstr(line, "new=0 ") != NULL)
                : (strstr(line, "new=2 ") != NULL);
            expected = knownOld && knownNew;
        }
        if (expected)
        {
            if (k1qSuccessfulPairs[p] == 0u)
            {
                k1quiet_emit_unfiltered(k1qPendingLine);
                k1quiet_emit_unfiltered(line);
            }
            else
            {
                k1qMutedLines[p] += 2u;
            }
            ++k1qSuccessfulPairs[p];
            k1qPendingKind = -1;
            /* One compact aggregate every 256 proven repeat successes. */
            if ((k1qSuccessfulPairs[p] & 255u) == 0u)
            {
                char k1qPeriodic[240];
                sprintf(k1qPeriodic,
                    "K1QUIET SUCCESS SUMMARY: op=%s successful_pairs=%u muted_lines=%u",
                    k1qNames[p], k1qSuccessfulPairs[p], k1qMutedLines[p]);
                k1quiet_emit_unfiltered(k1qPeriodic);
            }
            return;
        }
        /* Nonmatching, failed, interleaved or unusual state: preserve
           the complete original FRAME BEFORE the next incoming line. */
        k1quiet_emit_unfiltered(k1qPendingLine);
        k1qPendingKind = -1;
    }
    for (unsigned int k1q = 0u; k1q < 4u; ++k1q)
    {
        if (strncmp(line, k1qFrames[k1q], strlen(k1qFrames[k1q])) == 0)
        {
            /* A very long frame must be logged intact, not truncated. */
            if (strlen(line) >= sizeof(k1qPendingLine))
            {
                k1quiet_emit_unfiltered(line);
                return;
            }
            strncpy(k1qPendingLine, line, sizeof(k1qPendingLine) - 1u);
            k1qPendingLine[sizeof(k1qPendingLine) - 1u] = '\0';
            k1qPendingKind = (int)k1q;
            return;
        }
    }
    /* Keep major milestones, all hard faults, every GPU write and
       guest present event unconditionally. Add a summary before
       selected already-existing milestones; the milestone still logs. */
    if (strstr(line, "P6DQ ROCKET HARD STOP") != NULL ||
        strstr(line, "PHASE 6DQ INTERNAL D3D DEVICE RESULT") != NULL ||
        strstr(line, "PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF END") != NULL)
    {
        char k1qMilestone[300];
        sprintf(k1qMilestone,
            "K1QUIET MILESTONE SUMMARY: lower=%u raise=%u enter=%u leave=%u muted_lines=%u",
            k1qSuccessfulPairs[0], k1qSuccessfulPairs[1],
            k1qSuccessfulPairs[2], k1qSuccessfulPairs[3],
            k1qMutedLines[0] + k1qMutedLines[1] +
            k1qMutedLines[2] + k1qMutedLines[3]);
        k1quiet_emit_unfiltered(k1qMilestone);
    }
    k1quiet_emit_unfiltered(line);
}
'''


def sha(b: bytes) -> str:
    return hashlib.sha256(b).hexdigest()


def trace_end(source: str, start: int) -> int:
    """Close exactly the original C++ trace sink; fail on unmatched braces."""
    depth = 0
    for i in range(start, len(source)):
        if source[i] == "{":
            depth += 1
        elif source[i] == "}":
            depth -= 1
            if depth == 0:
                return i + 1
    raise ValueError("Cannot isolate original trace sink body")


def patch(src: str) -> str:
    if MARK in src or "K1QUIET MILESTONE SUMMARY:" in src:
        raise ValueError("Quiet logging already applied")
    if src.count(PARENT) != 1:
        raise ValueError("Missing exact hardware source-verified DAC parent")
    if "P6K1NV2A-PRMDIO-WRITE8-20261103" not in src:
        raise ValueError("Missing earlier hardware-proven write8 witness")
    if src.count("K1NV2A DAC PALETTE COMMIT:") != 1:
        raise ValueError("Original DAC data logging missing")
    if "P6DQ ROCKET HARD STOP" not in src:
        raise ValueError("Original hard-stop logger absent")
    if "\r" in src.replace("\r\n", ""):
        raise ValueError("Unsupported mixed line endings")
    candidates = list(DECL.finditer(src))
    qualifying = []
    for candidate in candidates:
        args = re.sub(r"\s+", " ", candidate.group("args")).strip()
        is_const_char = ("const char" in args and "*" in args)
        is_pcstr = args.startswith("LPCSTR ")
        # The wrapper uses trace(const char* line); do not silently alter a
        # variadic or multi-argument ABI even if the implementation logs.
        if not (is_const_char or is_pcstr) or "," in args:
            continue
        end = trace_end(src, candidate.end() - 1)
        original = src[candidate.start():end]
        if all(token in original for token in
               ("OutputDebugStringA(", "WriteFile(", "FlushFileBuffers(")):
            qualifying.append((candidate, end))
    if len(qualifying) != 1:
        suspects = [re.sub(r"\s+", " ", x.group(0).strip())
                    for x in TRACE_CANDIDATE.finditer(src)]
        raise ValueError(
            "Expected exactly one central trace DEFINITION with unchanged "
            f"Xbox debug/file output, found {len(qualifying)} "
            f"({len(candidates)} trace definitions); candidates: {suspects[:12]}"
        )
    marker, end = qualifying[0]
    old_function = src[marker.start():end]
    nl = "\r\n" if "\r\n" in src else "\n"
    # Rename only the actual *function name* token. Keeping all original
    # argument names and whitespace avoids another generator-format issue.
    rename_at = marker.start("name") - marker.start()
    raw_function = (old_function[:rename_at] + "k1quiet_emit_unfiltered"
                    + old_function[rename_at + len("trace"):])
    wrapper = WRAPPER.replace("\n", nl)
    new = (src[:marker.start()] + raw_function + "\n".replace("\n", nl) +
           wrapper + src[end:])
    new = new.replace(PARENT, PARENT + " | " + MARK, 1)
    # The only differences from parent are sink renaming, wrapper and boot tag.
    untagged = new.replace(PARENT + " | " + MARK, PARENT, 1)
    restored = untagged.replace(raw_function + "\n".replace("\n", nl) + wrapper,
                                old_function, 1)
    if restored != src:
        raise ValueError("Quiet mode changed code outside central trace sink")
    if new.count("static void trace(const char* line)") != 1:
        raise ValueError("Central trace wrapper missing or duplicated")
    if new.count("K1QUIET MILESTONE SUMMARY:") != 1 or new.count(MARK) != 1:
        raise ValueError("Quiet mode trace marker/summary drift")
    return new


def selftest():
    fixture = """static DWORD s_logFile;
static void trace(const char* line)
{
    DWORD written = 0;
    OutputDebugStringA(line);
    if (s_logFile) { WriteFile(s_logFile, line, 1, &written, NULL);
                     FlushFileBuffers(s_logFile); }
}
void test() {
  trace("P6K1NV2A-DAC-PALETTE-20261103 | P6K1NV2A-PRMDIO-WRITE8-20261103");
  trace("K1NV2A DAC PALETTE COMMIT:");
  trace("P6DQ ROCKET HARD STOP");
}
"""
    variants = [
        fixture,
        fixture.replace("static void trace(const char* line)\n{",
                        "static void trace(const char* message) {"),
        fixture.replace("static void trace(const char* line)\n{",
                        "void trace(\n const char * msg\n)\n{"),
        fixture.replace("static void trace(const char* line)\n{",
                        "static inline void trace(const char* output)\n{"),
    ]
    for s in variants + [v.replace("\n", "\r\n") for v in variants]:
        out = patch(s)
        assert out.count("static void trace(const char* line)") == 1
        assert out.count("static void k1quiet_emit_unfiltered(const char* line)") == 1
        assert out.count("FlushFileBuffers(s_logFile)") == 1
        assert "k1qMutedLines[p] += 2u" in out
        assert 'strstr(line, "old=2 ") != NULL' in out
        assert "if (strlen(line) >= sizeof(k1qPendingLine))" in out
        assert "k1quiet_emit_unfiltered(k1qPendingLine);" in out
        assert "PHASE 6DQ INTERNAL D3D DEVICE RESULT" in out
        assert "K1NV2A DAC PALETTE COMMIT:" in out
        try:
            patch(out)
        except ValueError:
            pass
        else:
            raise AssertionError("Duplicate logging filter accepted")
        try:
            patch(s.replace("FlushFileBuffers", "FlushFileBuffersBROKEN"))
        except ValueError:
            pass
        else:
            raise AssertionError("Changed logger accepted")
    print("[K1QUIET] SELFTEST PASS: reversible trace sink, failures flushed, first successful pair visible, 256-pair summaries, all faults pass")


def stage(args):
    parent, out = args.parent.resolve(), args.out.resolve()
    if parent == out or parent.parent == out.parent:
        raise ValueError("Refusing in-place original DAC main modification")
    before = parent.read_bytes()
    after = patch(before.decode("utf-8")).encode("utf-8")
    out.parent.mkdir(parents=True, exist_ok=True)
    if out.is_file():
        if out.read_bytes() != after:
            raise ValueError("Existing quiet main source drift")
    else:
        out.write_bytes(after)
    if parent.read_bytes() != before:
        raise ValueError("DAC parent main was altered during quiet staging")
    record = {
        "marker": MARK,
        "status": "QUIET_SOURCE_STAGED_NO_XDK",
        "parent_main_sha256": sha(before),
        "new_main_sha256": sha(after),
        "muted_events": ["KfLowerIrql", "KfRaiseIrql",
                         "RtlEnterCriticalSection", "RtlLeaveCriticalSection"],
        "log_policy": "buffer frame; only coalesce exact expected PASS; unexpected or failures flush",
        "first_success_pair_logged": True,
        "milestone_summary": True,
        "all_other_logs_unchanged": True,
        "guest_execution_changed": False,
        "mmio_fences_changed": False,
        "translated_tus_changed": 0,
        "runtime_headers_changed": 0,
        "hardware_verified": False,
    }
    raw = (json.dumps(record, indent=2) + "\n").encode("utf-8")
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    if args.manifest.is_file():
        if args.manifest.read_bytes() != raw:
            raise ValueError("Existing quiet manifest source drift")
    else:
        args.manifest.write_bytes(raw)
    print("[K1QUIET] STAGE PASS: frame/PASS pairs coalesced only on 4 proven success paths")
    print("[K1QUIET] Unexpected/failure/mismatched trace flushes pending frame; all other messages pass")
    print("[K1QUIET] Periodic summary 256 pairs + D3D/fault/end milestones; 64 TrueTUs untouched")
    print("[K1QUIET] No XDK / no Xbox validation yet")


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
    if not (a.parent and a.out and a.manifest):
        p.error("--parent, --out, --manifest required")
    stage(a)


if __name__ == "__main__":
    main()
