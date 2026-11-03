#!/usr/bin/env python3
"""Compare actual Xbox Merc360 hardware telemetry with the working PC port.

A one-XEX build can retain guest instrumentation, but this script may only
claim hardware observations AFTER an actual Xbox log is supplied.
PC renderer events are comparison milestones, not transferable Xenos code
and not automatically the same original guest-VA execution sequence.
"""
from __future__ import annotations

import argparse
import json
import re
from collections import Counter
from pathlib import Path

PATTERNS = {
    "pfifo_command_submits": re.compile(r"\[PFIFO\]\s+submit\b", re.I),
    "render_target_creations": re.compile(r"\[PGRAPH-SURFACE\]\s+color create\b", re.I),
    "surface_resolves": re.compile(r"\[PGRAPH-SURFACE\]\s+resolve\b", re.I),
    "pgraph_draw_state_events": re.compile(r"\[PGRAPH-DRAW-STATE\]", re.I),
    "gpu_blits": re.compile(r"\[PGRAPH-IMAGE-BLIT\]", re.I),
    "async_callbacks_queued": re.compile(r"\[GUEST-APC\]\s+queued\b", re.I),
    "async_callbacks_delivered": re.compile(r"\[GUEST-APC\]\s+delivered\b", re.I),
    "nv2a_mmio_events": re.compile(r"(?:\bNV2A\b|FE82[0-9A-F]{4})", re.I),
    "xenos_create_success": re.compile(r"XENOS: PASS Direct3D_CreateDevice", re.I),
    "xenos_reset_success": re.compile(r"(?:XENOS Reset PASS|XENOS RESET.*(?:PASS|HRESULT=00000000))", re.I),
    "guest_present_witness": re.compile(
        r"\b(?:D3DDevice_Swap|PersistDisplay|guest present|guest swap)\b", re.I),
    "xact_audio_activity": re.compile(r"(?:XACTENG|XACT setup|XACT list)", re.I),
    "audio_allocation_warning": re.compile(
        r"(?:audio (?:fallback )?alloc(?:ation)?.{0,100}fail|"
        r"(?:alloc(?:ation)? fail).{0,100}audio)", re.I),
    "direct_frontier": re.compile(r"(?:BOUNDARY:.*kind=DIRECT_FRONTIER|DIRECT_FRONTIER)", re.I),
    "indirect_frontier": re.compile(r"(?:BOUNDARY:.*kind=ICALL_SAFE|BOUNDARY:.*kind=ITAIL)", re.I),
}
MARKERS = {
    "guest_display_calls": re.compile(r"\bdisplay_calls\s*[=:]\s*(\d+)", re.I),
    "guest_framebuffer": re.compile(r"\bframebuffer\s*[=:]\s*([0-9A-F]{8})\b", re.I),
    "hardware_fault": re.compile(r"\bfault\s*[=:]\s*(\d+)", re.I),
    "tick_count": re.compile(r"\bticks\s*[=:]\s*(\d+)", re.I),
    "last_direct_target": re.compile(
        r"\bkind=DIRECT_FRONTIER\b[^\r\n]*?\btarget=([0-9A-Fa-f]{8})", re.I),
    "last_direct_caller": re.compile(
        r"\bkind=DIRECT_FRONTIER\b[^\r\n]*?\bcaller=([0-9A-Fa-f]{8})", re.I),
}
KNOWN_TEST = {
    "previous_r4_boundary_va": "0x002228C0",
    "previous_r4_ticks": 58612771,
    "previous_r4_guest_display_calls": 0,
}


def observe(path: Path, kind: str) -> dict:
    counts = Counter()
    markers: dict[str, str | int] = {}
    first = {}
    lines = 0
    with path.open("r", encoding="utf-8-sig", errors="replace") as inp:
        for line in inp:
            lines += 1
            for key, pattern in PATTERNS.items():
                if pattern.search(line):
                    counts[key] += 1
                    first.setdefault(key, line.strip()[-260:])
            for key, pattern in MARKERS.items():
                m = pattern.search(line)
                if m:
                    value = m.group(1)
                    if key in ("guest_display_calls", "hardware_fault", "tick_count"):
                        value = int(value)
                    elif key.startswith("last_direct_"):
                        value = "0x" + value.upper()
                    else:
                        value = value.upper()
                    markers[key] = value
    return {
        "kind": kind,
        "file_name": path.name,
        "line_count": lines,
        "pattern_event_counts": dict(sorted(counts.items())),
        "last_observed_counters": markers,
        "first_event_examples": first,
        "event_counts_are_log_matches_not_full_runtime_totals": True,
    }


def compare(pc: dict | None, xbox: dict | None) -> dict:
    if xbox is None:
        return {
            "status": "NO_NEW_XBOX_RUN_SUPPLIED",
            "first_real_guest_display_call_verified": False,
            "new_hardware_tick_gain_verified": False,
            "explanation": (
                "PC logging is not Xbox hardware execution. Supply the "
                "actual xbWatson output after running the new XEX to "
                "compare frontiers, fault state and guest display."
            ),
        }
    values = xbox["last_observed_counters"]
    displays = values.get("guest_display_calls")
    frame = values.get("guest_framebuffer")
    new_tick = values.get("tick_count")
    new_target = values.get("last_direct_target")
    if new_tick is not None and new_tick >= KNOWN_TEST["previous_r4_ticks"]:
        progress = new_tick - KNOWN_TEST["previous_r4_ticks"]
    else:
        progress = None
    return {
        "status": "XBOX_LOG_PARSED_HARDWARE_WITNESS",
        "first_real_guest_display_call_verified": displays is not None and displays >= 1,
        "guest_display_calls": displays,
        "last_framebuffer": frame,
        "last_reported_fault": values.get("hardware_fault"),
        "observed_last_direct_frontier": new_target,
        "previous_r4_hardware_frontier": KNOWN_TEST["previous_r4_boundary_va"],
        "new_frontier_differs_from_r4": (
            new_target != KNOWN_TEST["previous_r4_boundary_va"]
            if new_target is not None else None
        ),
        "last_reported_ticks": new_tick,
        "tick_gain_vs_r4_if_same_counter": progress,
        "new_hardware_tick_gain_verified": progress is not None and progress > 0,
        "host_gpu_submits_logged": xbox["pattern_event_counts"].get(
            "pfifo_command_submits", 0),
        "limitations": [
            "Log matches are not proof of total rendered frames or exact CPU call-tree.",
            "An Xbox event absent from logs could be uninstrumented rather than absent.",
            "Native Xenos CreateDevice/Reset success alone is not guest presentation.",
            "PC D3D11 PGRAPH events are a reference, not interchangeable native Xbox graphics API calls.",
            "A displayed diagnostic blue surface is not a genuine guest framebuffer.",
        ],
        "pc_comparison_supplied": pc is not None,
    }


def make_report(pcfile: Path | None, xboxfile: Path | None) -> dict:
    if pcfile is None and xboxfile is None:
        raise ValueError("Need PC reference log and/or actual Xbox xbWatson hardware log")
    for p in (pcfile, xboxfile):
        if p is not None and (not p.is_file() or p.stat().st_size == 0):
            raise ValueError("Missing or empty telemetry input: "+str(p))
    pc = observe(pcfile,"PC_reference_not_Xbox_hardware") if pcfile else None
    xbox = observe(xboxfile,"Xbox_xbWatson_hardware") if xboxfile else None
    return {
        "status": "K1_REAL_PC_VS_XBOX_GRAPHICS_AUDIO_TRACE_EVIDENCE",
        "original_hardware_r4": KNOWN_TEST,
        "pc_reference": pc,
        "xbox_hardware": xbox,
        "comparison": compare(pc,xbox),
        "xdk_invoked": False,
        "game_executed_by_analyzer": False,
        "guest_pixels_synthesized": False,
    }


def selftest():
    from tempfile import TemporaryDirectory
    with TemporaryDirectory() as temp:
        root=Path(temp)
        pc=root/"pc.txt"
        xbox=root/"xbox.txt"
        pc.write_text(
            "[PFIFO] submit methods=33\n"
            "[PGRAPH-DRAW-STATE] next=1\n"
            "[PGRAPH-SURFACE] color create off=0123\n"
            "[PGRAPH-SURFACE] resolve 0 -> 1\n"
            "[GUEST-APC] queued routine=FE000098\n"
            "[GUEST-APC] delivered routine=FE000098\n",
            encoding="utf-8")
        xbox.write_text(
            "P6DQ XENOS: PASS Direct3D_CreateDevice\n"
            "BOUNDARY: kind=DIRECT_FRONTIER caller=0023A3CE "
            "target=002228C0 ticks=58612771\n"
            "BOUNDARY REGISTERS: fault=0\n"
            "P6DQ AV FAMILY: display_calls=0 framebuffer=00000000\n",
            encoding="utf-8")
        report=make_report(pc,xbox)
        assert report["pc_reference"]["pattern_event_counts"]["pfifo_command_submits"] == 1
        assert report["comparison"]["new_hardware_tick_gain_verified"] is False
        assert report["comparison"]["first_real_guest_display_call_verified"] is False
        assert report["comparison"]["observed_last_direct_frontier"] == "0x002228C0"
        assert report["comparison"]["last_reported_fault"] == 0
        xbox.write_text(
            xbox.read_text(encoding="utf-8").replace(
                "target=002228C0 ticks=58612771",
                "target=002228D0 ticks=59612771").replace(
                "display_calls=0", "display_calls=1"),
            encoding="utf-8")
        newer=make_report(pc,xbox)
        assert newer["comparison"]["new_hardware_tick_gain_verified"]
        assert newer["comparison"]["first_real_guest_display_call_verified"]
        refonly=make_report(pc,None)
        assert refonly["comparison"]["status"] == "NO_NEW_XBOX_RUN_SUPPLIED"
        assert not refonly["comparison"]["first_real_guest_display_call_verified"]
    print("[K1-TRACE] SELFTEST PASS: PC PGRAPH milestones != Xbox pixels, real direct frontier & tick/display hardware evidence, no XDK")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--pc-log",type=Path)
    p.add_argument("--xbox-log",type=Path)
    p.add_argument("--output",type=Path)
    a=p.parse_args()
    if a.self_test:
        selftest()
        return
    report=make_report(a.pc_log,a.xbox_log)
    if a.output:
        a.output.parent.mkdir(parents=True,exist_ok=True)
        a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    pc=report["pc_reference"]
    hw=report["xbox_hardware"]
    print("[K1-TRACE] PC log=%s Xbox hardware log=%s" %
          (pc["file_name"] if pc else "none",
           hw["file_name"] if hw else "not yet supplied"))
    for label, doc in (("PC",pc),("XBOX",hw)):
        if not doc:
            continue
        print("[K1-TRACE] %s lines=%d submit=%d draw_state=%d resolves=%d APC_queued=%d APC_delivered=%d" %
              (label,doc["line_count"],
               doc["pattern_event_counts"].get("pfifo_command_submits",0),
               doc["pattern_event_counts"].get("pgraph_draw_state_events",0),
               doc["pattern_event_counts"].get("surface_resolves",0),
               doc["pattern_event_counts"].get("async_callbacks_queued",0),
               doc["pattern_event_counts"].get("async_callbacks_delivered",0)))
    comp=report["comparison"]
    print("[K1-TRACE] status=%s display_calls=%s boundary=%s ticks=%s delta_from_r4=%s fault=%s" %
          (comp["status"],comp.get("guest_display_calls","unproven"),
           comp.get("observed_last_direct_frontier","unproven"),
           comp.get("last_reported_ticks","unproven"),
           comp.get("tick_gain_vs_r4_if_same_counter","unproven"),
           comp.get("last_reported_fault","unproven")))
    print("[K1-TRACE] Genuine guest presentation=%s (do NOT equate blue/native clear with pixels)" %
          comp["first_real_guest_display_call_verified"])
    if a.output:
        print("[K1-TRACE] JSON: "+str(a.output))


if __name__=="__main__":
    main()
