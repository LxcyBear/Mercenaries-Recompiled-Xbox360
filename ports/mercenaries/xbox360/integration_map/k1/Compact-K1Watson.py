#!/usr/bin/env python3
"""Summarize Merc360 xbWatson logs without removing or modifying the raw log.

This is an OFFLINE view, not a game runtime change. Counts repetitive
Phase6DQ routine PASS and R-series reports, retains exact GPU, performance,
audio errors, fatal boundaries and final graphics telemetry.
"""
from __future__ import annotations
import argparse
import collections
import re
from pathlib import Path

PREFIX = "[Merc360:P5] "
REVISION = re.compile(r"\bP6DQ R(\d+)\s+([^:]+):")
STATUS = re.compile(r"\b(?:status|result|hr)=([0-9A-Fa-f]{8})\b")
PASS = "PASS: Phase 6DQ "
IMPORTANT = (
    "K1PFIFO", "K1NV2A", "K1PERF", "K1PRESENT",
    "K1QUIET", "DIRECT FRONTIER:", "HARD STOP", "HARD REGS",
    "BOUNDARY:", "BOUNDARY REGISTERS", "P6DQ VA[",
    "P6DQ FINAL VA RING", "P6DQ SPIN SAMPLE", "P6DQ HOT PROFILE",
    "P6DQ PIXEL CHASE", "P6DQ PRESENT PROXIMITY",
    "P6DQ AV FAMILY", "P6DQ D3D DEVICE", "P6DQ POST-CREATE D3D INIT",
    "P6DQ INTERNAL D3D DEVICE", "PHASE 6DQ INTERNAL D3D DEVICE RESULT",
    "PHASE 6DQ XENOS DEVICE RESULT", "P6DQ XACT GLOBAL 0028836C",
    "P6DQ XACT FINAL RELEASE", "P6DQ APU VP:", "P6DQ APU CORE:",
    "K1NT207 REAL ENUM SUCCESS", "SOURCE PROMOTION", "BUILD TAG:",
    "ROCKET JOURNAL SUMMARY", "P6DQ R49 ESI REPAIR",
    "P6DQ R51 MM173 FRAME", "P6DQ R45 AUDIO CONTAIN",
)
DANGER = ("FAULT", "EXCEPTION", "HARD FENCE", "UNRESOLVED", "FAILED",
          "WARNING", "ERROR", "ASSERT", "BAD SIGNATURE")


def group_pass(line: str) -> str:
    part = line.split(PASS, 1)[1].strip()
    head = part.split(" ", 2)
    if not head:
        return "other"
    if head[0] in ("ordinal", "caller") and len(head) > 1:
        return " ".join(head[:2])
    if head[0] == "maintained" and len(head) > 1:
        return "maintained " + head[1]
    if head[0] == "entered" and len(head) > 2:
        return "entered " + head[1] + " " + head[2]
    if head[0] == "broad-sweep" and len(head) > 1:
        return "broad-sweep " + head[1]
    if head[0] == "audio" and len(head) > 1:
        return "audio " + head[1]
    return head[0]


def compress(lines: list[str]) -> str:
    total = 0
    passes = collections.Counter()
    revisions = collections.Counter()
    rev_examples: dict[str, list[str]] = {}
    preserved: list[str] = []
    for text in lines:
        total += 1
        clean = text.strip()
        upper = clean.upper()
        body = clean.split(PREFIX, 1)[-1]
        # A caller can report an expected-but-nonzero NTSTATUS with PASS.
        # Never summarize those as equivalent to NTSTATUS_SUCCESS.
        statuses = STATUS.findall(clean)
        unusual_status = any(v.upper() != "00000000" for v in statuses)
        if any(x in upper for x in DANGER) or unusual_status:
            preserved.append(clean)
            continue
        if any(x in clean for x in IMPORTANT):
            preserved.append(clean)
            continue
        if PREFIX in clean and body.startswith(PASS):
            passes[group_pass(body)] += 1
            continue
        m = REVISION.search(clean)
        if m:
            key = "R" + m.group(1) + " " + m.group(2).strip()
            revisions[key] += 1
            examples = rev_examples.setdefault(key, [])
            if len(examples) < 2:
                examples.append(clean)
            continue
        # Retain nonmatching evidence, do not classify it as success.
        preserved.append(clean)

    report = [
        "Mercenaries Xbox 360 — COMPACT xbWatson VIEW (original unchanged)",
        "Raw lines: %d | retained full lines: %d | grouped routine PASS: %d | grouped revision reports: %d"
        % (total, len(preserved), sum(passes.values()), sum(revisions.values())),
        "NOTE: counts are log-message occurrences, NOT proof of extra gameplay, pixels, or successful status.",
        "",
        "=== Routine Phase6DQ PASS summaries ===",
    ]
    report.extend("[SUCCESS] %-42s %d messages" % (name, count)
                  for name, count in passes.most_common())
    report += ["", "=== R-series probe summaries (read full raw log for register details) ==="]
    for key, count in revisions.most_common():
        report.append("[R-PROBE] %-42s %d reports" % (key, count))
        if count <= 2:
            report.extend("  " + x for x in rev_examples[key])
    report += ["", "=== All retained non-routine evidence in chronological order ==="]
    report.extend(preserved)
    report.append("")
    report.append("END OF COMPACT VIEW. Raw xbWatson remains authoritative.")
    return "\n".join(report) + "\n"


def self_test() -> None:
    rows = [
        PREFIX + "PASS: Phase 6DQ maintained RtlAllocateHeap calls=2",
        PREFIX + "PASS: Phase 6DQ NtCreateFile status=C000003A",
        PREFIX + "P6DQ R62 DSOUND ALLOC: n=1 value=00000000",
        PREFIX + "K1NV2A DAC PALETTE COMMIT: entries=256 bytes=768",
        PREFIX + "K1PERF WINDOW: elapsed_ms=1300",
        PREFIX + "P6DQ ROCKET HARD STOP target=0017A0A0",
        PREFIX + "P6DQ AV FAMILY: display_calls=0 framebuffer=00000000",
    ]
    out = compress(rows)
    assert "[SUCCESS] maintained RtlAllocateHeap" in out
    assert "NtCreateFile status=C000003A" in out
    assert "DAC PALETTE COMMIT: entries=256" in out
    assert "K1PERF WINDOW:" in out
    assert "HARD STOP target=0017A0A0" in out
    assert "display_calls=0" in out
    assert "[R-PROBE] R62 DSOUND ALLOC" in out
    print("[K1-LOG] SELFTEST PASS: only routine success condensed; nonzero statuses, faults, GPU/pixels and timing preserved")


def main():
    p = argparse.ArgumentParser()
    p.add_argument("log", nargs="?", type=Path)
    p.add_argument("--out", type=Path)
    p.add_argument("--self-test", action="store_true")
    a = p.parse_args()
    if a.self_test:
        self_test()
        return
    if a.log is None:
        p.error("Raw xbWatson log file required")
    src = a.log.resolve()
    out = a.out.resolve() if a.out else src.with_suffix(".compact.txt")
    if src == out:
        raise ValueError("Never overwrite original hardware log")
    result = compress(src.read_text(encoding="utf-8-sig", errors="replace").splitlines())
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(result, encoding="utf-8")
    print("[K1-LOG] COMPACT REPORT:", out)
    print("[K1-LOG] RAW ORIGINAL PRESERVED:", src)

if __name__ == "__main__":
    main()
