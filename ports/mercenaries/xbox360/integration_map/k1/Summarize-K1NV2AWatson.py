#!/usr/bin/env python3
"""Read-only xbWatson hardware-run triage for the K1NT207 -> PRMDIO frontier.

No XDK, no game files, no guest mutations. Extracts primary witnesses and
counts repetitive debug messages without treating a colored screen as pixels.
"""
from __future__ import annotations
import argparse
import re
from collections import Counter
from pathlib import Path

CATEGORIES = (
    ("native_directory", "K1NT207 REAL ENUM RESULT"),
    ("controller_getstate", "XPP XINPUT state:"),
    ("controller_setstate", "XPP XINPUT setstate:"),
    ("xenos_device", "PHASE 6DQ XENOS DEVICE RESULT:"),
    ("exact_prmdio_value", "K1NV2A EXACT WRITE8:"),
    ("hard_stop", "P6DQ ROCKET HARD STOP"),
    ("guest_swap_symbol", "D3DDevice_Swap"),
    ("guest_persist_symbol", "D3DDevice_PersistDisplay"),
    ("graphics_boundary", "FAULT ACCESS IMMEDIATE:"),
)
NOISE = (
    "KfLowerIrql LIVE FRAME",
    "KfRaiseIrql LIVE FRAME",
    "RtlEnterCriticalSection LIVE FRAME",
    "RtlLeaveCriticalSection LIVE FRAME",
    "PASS: Phase 6DQ KfLowerIrql",
    "PASS: Phase 6DQ KfRaiseIrql",
    "PASS: ordinal 277 RtlEnterCriticalSection",
    "PASS: ordinal 294 RtlLeaveCriticalSection",
)
COUNTER = re.compile(r"display_calls=(\d+).*?framebuffer=([0-9A-Fa-f]{8})")
FAULT = re.compile(r"FAULT ACCESS IMMEDIATE:\s*(\w+)\s+width=(\d+)\s+guest=([0-9A-Fa-f]{8})")
TICKS = re.compile(r"\bticks=(\d+)")
VALUE = re.compile(r"K1NV2A EXACT WRITE8:.*?\baddr=([0-9A-Fa-f]{8}).*?\bvalue=([0-9A-Fa-f]{1,2}).*?\blast_guest_block_va=([0-9A-Fa-f]{8})")


def summarize(lines: list[str]) -> str:
    counts = Counter()
    noise = Counter()
    last = {}
    last_frame = None
    last_ticks = None
    last_fault = None
    last_value = None
    for raw in lines:
        line = raw.strip()
        for name, needle in CATEGORIES:
            if needle in line:
                counts[name] += 1
                last[name] = line
        for needle in NOISE:
            if needle in line:
                noise[needle] += 1
                break
        if m := COUNTER.search(line):
            last_frame = (int(m.group(1)), m.group(2).upper())
        if m := TICKS.search(line):
            last_ticks = int(m.group(1))
        if m := FAULT.search(line):
            last_fault = (m.group(1), int(m.group(2)), m.group(3).upper())
        if m := VALUE.search(line):
            last_value = (m.group(1).upper(), m.group(2).upper(), m.group(3).upper())
    out = [
        "K1NV2A / MERC360 READ-ONLY XBWATSON RUN SUMMARY",
        f"Captured lines: {len(lines)}",
        f"Last reported translated ticks: {last_ticks if last_ticks is not None else 'NOT REPORTED'}",
        f"Native directory records: {counts['native_directory']}",
        f"Native controller GetState / SetState records: {counts['controller_getstate']} / {counts['controller_setstate']}",
        f"Xenos device result records: {counts['xenos_device']}",
        f"Guest Swap / PersistDisplay text occurrences: {counts['guest_swap_symbol']} / {counts['guest_persist_symbol']}",
    ]
    if last_frame is not None:
        out += [f"Last guest display_calls={last_frame[0]} framebuffer={last_frame[1]}"]
    if last_fault:
        out += [f"Last immediate fault: {last_fault[0]} width={last_fault[1]} guest={last_fault[2]}"]
    if last_value:
        out += [f"Exact write8 witness: address={last_value[0]} byte={last_value[1]} last_guest_block_va={last_value[2]}"]
        out += ["Use this guest BLOCK VA to focus Audit-K1NV2ASource.py; it is NOT an exact x86 instruction."]
    else:
        out += ["Exact PRMDIO write8 value: NOT YET CAPTURED (needs tagged new diagnostic XEX)."]
    out += ["", "REPEATED DEBUG OUTPUT (future quiet-mode candidates; not permission to bypass the underlying operation):"]
    for name, count in sorted(noise.items(), key=lambda pair: -pair[1]):
        out.append(f"  {count:5d}  {name}")
    out += [f"  TOTAL {sum(noise.values())} of {len(lines)} captured lines",
            "", "PROVENANCE: these are text log counts, not CPU profiling or frame evidence."]
    if "exact_prmdio_value" in last:
        out += ["", "ACTUAL VALUE LOG:", last["exact_prmdio_value"]]
    if "hard_stop" in last:
        out += ["", "LAST HARD STOP:", last["hard_stop"]]
    if "native_directory" in last:
        out += ["", "LAST DIRECTORY RESULT:", last["native_directory"]]
    return "\n".join(out) + "\n"


def selftest() -> None:
    fixture = [
        "[Merc360:P5] PHASE 6DQ XENOS DEVICE RESULT: PASS",
        "[Merc360:P5] K1NT207 REAL ENUM RESULT: handle=48000001 status=00000000 rows=1",
        "[Merc360:P5] K1NV2A EXACT WRITE8: addr=FD6813C8 value=01 last_guest_block_va=002A0100 esp=008BF000",
        "[Merc360:P5] FAULT ACCESS IMMEDIATE: WRITE width=1 guest=FD6813C8",
        "[Merc360:P5] P6DQ ROCKET HARD STOP ticks=56902779",
        "[Merc360:P5] P6DQ PIXEL CHASE: display_calls=0 framebuffer=00000000",
        "[Merc360:P5] KfRaiseIrql LIVE FRAME foo",
    ]
    result = summarize(fixture)
    for expected in ("Native directory records: 1", "byte=01",
                     "last_guest_block_va=002A0100",
                     "display_calls=0 framebuffer=00000000",
                     "Last immediate fault: WRITE width=1 guest=FD6813C8",
                     "TOTAL 1 of 7 captured lines"):
        assert expected in result, expected
    missing = summarize(["not an xbox capture"])
    assert "NOT YET CAPTURED" in missing
    print("[K1NV2A-PC] SELFTEST PASS: GPU address/byte/block, guest counters, non-pixel proof, quiet-mode counts")


def main():
    parser = argparse.ArgumentParser()
    parser.add_argument("--log", type=Path)
    parser.add_argument("--out", type=Path)
    parser.add_argument("--self-test", action="store_true")
    opts = parser.parse_args()
    if opts.self_test:
        selftest()
        return
    if opts.log is None:
        parser.error("--log is required")
    lines = opts.log.read_text(encoding="utf-8-sig", errors="replace").splitlines()
    report = summarize(lines)
    print(report)
    if opts.out:
        opts.out.parent.mkdir(parents=True, exist_ok=True)
        opts.out.write_text(report, encoding="utf-8")
        print("[K1NV2A-PC] Report:", opts.out)


if __name__ == "__main__":
    main()
