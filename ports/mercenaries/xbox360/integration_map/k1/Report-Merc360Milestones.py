#!/usr/bin/env python3
"""Summarize a completed Merc360 xbWatson log with HONEST, conspicuous milestones.

Does not need the XDK, generated guest C, Xbox connection or any new XEX.
Run *after* xbWatson finishes writing the log (not while it is still recording).
It appends a clearly identified HOST ANALYSIS to the end of the existing log,
writes an adjacent verdict.txt and verdict.json, and never claims source
coverage alone proves hardware execution.
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path

BEGIN = "========== MERC360 POST-RUN VERDICT START =========="
END = "========== MERC360 POST-RUN VERDICT END =========="
BAR = "=" * 72
START = re.compile(r"\[Merc360:P5\] PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START")
STOP = re.compile(
    r"P6DQ ROCKET HARD STOP kind=(\d+) caller=([0-9A-Fa-f]{8}) "
    r"target=([0-9A-Fa-f]{8}) esp=([0-9A-Fa-f]{8}) ticks=(\d+)")
BOUNDARY = re.compile(
    r"BOUNDARY: kind=([A-Z_]+) caller=([0-9A-Fa-f]{8}) "
    r"target=([0-9A-Fa-f]{8}) .*?ticks=(\d+)")
FAULT = re.compile(r"BOUNDARY REGISTERS:.*?\bfault=(\d+)")
DISPLAY = re.compile(r"\bdisplay_calls=(\d+)")
FB = re.compile(r"\bframebuffer=([0-9A-Fa-f]{8})")
GSTATE = re.compile(r"XPP XINPUT state:.*?\bstatus=([0-9A-Fa-f]{8})")
SSTATE = re.compile(r"XPP XINPUT setstate:.*?\bstatus=([0-9A-Fa-f]{8})")
FRAME = re.compile(r"\b(?:native_present_calls|xenos_present_calls)=(\d+)")
# Runtime-specific evidence only. A static xref/compiled symbol is NOT an entry.
SWAP_ENTRY = re.compile(
    r"(?:\bD3DDevice_Swap\s+(?:ENTRY|ENTERED|LIVE)\b|"
    r"\b(?:GUEST\s+)?SWAP\s+(?:ENTRY|EXECUTED)\b)", re.IGNORECASE)
END_MARK = "PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF END"


def rsearch(pattern: re.Pattern, lines: list[str]):
    for line in reversed(lines):
        match = pattern.search(line)
        if match:
            return match
    return None


def clean_old_summaries(raw: str) -> str:
    # Ignore summaries from earlier invocations for evidence checks.
    pattern = re.compile(
        rf"(?ms)^{re.escape(BEGIN)}\r?\n.*?^{re.escape(END)}\r?\n?")
    return pattern.sub("", raw)


def extract_run(raw: str) -> list[str]:
    lines = clean_old_summaries(raw).splitlines()
    last = [i for i, line in enumerate(lines) if START.search(line)]
    return lines[last[-1]:] if last else lines


def observed(pattern: str, lines: list[str], flags=0) -> bool:
    rx = re.compile(pattern, flags)
    return any(rx.search(line) for line in lines)


def summarize(raw: str, input_name: str, test: str = "auto"):
    lines = extract_run(raw)
    all_text = "\n".join(lines)
    complete = any(END_MARK in line for line in lines)
    xbe = observed(r"PHASE 6DQ EXACT RETAIL VERIFICATION: PASS", lines)
    xenos = observed(r"PHASE 6DQ XENOS DEVICE RESULT: PASS", lines)
    guest_device = observed(
        r"PASS: Phase 6DQ native D3D CreateDevice handoff", lines)
    init = observed(r"\bXPP D5574 ENTRY\b", lines)
    changes = observed(r"\bXPP 002D559B ENTRY\b", lines)
    get_entry = observed(r"\bXPP D54AC ENTRY\b", lines)
    get = rsearch(GSTATE, lines)
    get_result = get.group(1).upper() if get else None
    set_entry = observed(r"\bXPP D551F ENTRY\b", lines)
    set_call = rsearch(SSTATE, lines)
    close_entry = observed(r"\bXPP D52C8 ENTRY\b", lines)
    dsp = [int(m.group(1)) for line in lines
           for m in DISPLAY.finditer(line)]
    fb = [m.group(1).upper() for line in lines for m in FB.finditer(line)]
    display_count = max(dsp, default=0)
    framebuffer = next((x for x in reversed(fb) if int(x, 16) != 0), None)
    swap = any(SWAP_ENTRY.search(line) for line in lines)
    native_present = any(
        "NATIVE PRESENT SUCCESS" in line.upper()
        or "REAL PRESENT PASS" in line.upper()
        for line in lines)
    present_count = max((int(m.group(1)) for line in lines
                         for m in FRAME.finditer(line)), default=0)
    # A measured nonzero native-present count can establish a Present call;
    # framebuffer presence alone never proves a rendered/presented frame.
    presented = native_present or present_count > 0
    audio_path = observed(
        r"(?:PASS: Phase 6DQ entered DSOUND owner|P6DQ XACTENG ROOT: entries=[1-9])",
        lines)
    stop = rsearch(STOP, lines)
    boundary = rsearch(BOUNDARY, lines)
    fault = rsearch(FAULT, lines)
    last_ticks = (int(stop.group(5)) if stop else
                  int(boundary.group(4)) if boundary else None)
    target = (stop.group(3).upper() if stop else
              boundary.group(3).upper() if boundary else None)
    kind = boundary.group(1) if boundary else (
        "HARD_STOP_KIND_" + stop.group(1) if stop else None)
    no_fault = fault.group(1) == "0" if fault else None
    nt207_gate = observed(r"K1NT207 FRAME GATE:.*guarded=1$", lines)
    nt207_raw0 = observed(r"K1NT207 FRAME RAW0:.*ret=[0-9A-Fa-f]{8}", lines)
    nt207_raw1 = observed(r"K1NT207 FRAME RAW1:.*a9=[0-9A-Fa-f]{8}", lines)
    nt207_captured = observed(r"K1NT207 FRAME CAPTURED:.*original_ordinal=207", lines)
    nt207_probe = observed(r"K1NT207 PROBE ONLY:.*hard stop preserved", lines)
    nt207_full = all((nt207_gate, nt207_raw0, nt207_raw1, nt207_captured, nt207_probe))
    if test not in ("auto", "xpp", "nt207"):
        raise ValueError("Unknown test: " + test)
    if test == "auto":
        test = "nt207" if nt207_probe or nt207_gate else "xpp"
    # The milestone is "native GetState was actually called and returned".
    # A disconnected controller result is not a native-call failure; list
    # SUCCESS status separately. No state trace -> no success banner.
    input_ok = get_entry and get is not None
    if test == "nt207":
        if nt207_full:
            verdict = "PASS"
            reason = ("Original ordinal 207 ten-argument frame captured on Xbox. "
                      "Diagnostic succeeded; directory service is STILL BLOCKED.")
        elif stop and complete:
            verdict = "BLOCKED"
            reason = ("Ordinal 207 live frame was not completely captured; "
                      "hardware hard stop remains.")
        else:
            verdict = "INCONCLUSIVE"
            reason = "Ordinal 207 probe evidence or run completion is insufficient."
    elif input_ok:
        verdict = "PASS"
        reason = "Real XInputGetState entry and native return were observed."
    elif stop and complete:
        verdict = "BLOCKED"
        reason = ("No observed D54AC native GetState; an earlier "
                  "hardware hard stop ended the run.")
    else:
        verdict = "INCONCLUSIVE"
        reason = ("No observed D54AC native GetState; "
                  "run completion / runtime evidence insufficient.")
    details = {
        "kind": "Merc360 post-run HOST analysis, not emitted by Xbox runtime",
        "input_log": input_name,
        "test": "NT207-FRAME-CAPTURE" if test == "nt207" else "XPP-INPUT-FAMILY-GETSTATE",
        "verdict": verdict,
        "reason": reason,
        "completed": complete,
        "milestones": {
            "retail_xbe_verified": xbe,
            "native_xenos_initialized": xenos,
            "guest_d3d_create_device_handoff": guest_device,
            "xpp_init_devices_entry": init,
            "xpp_device_changes_entry": changes,
            "xpp_getstate_guest_entry": get_entry,
            "xpp_getstate_native_return": get is not None,
            "xpp_getstate_native_status": get_result,
            "xpp_getstate_native_status_success": get_result == "00000000",
            "xpp_setstate_guest_entry": set_entry,
            "xpp_setstate_native_return": set_call is not None,
            "xpp_close_guest_entry": close_entry,
            "nt207_original_directory_frame_capture": nt207_full,
            "nt207_native_directory_enumeration": False,
            "audio_code_path_reached_not_audible_proof": audio_path,
            "guest_av_display_call_reached": display_count > 0,
            "guest_display_calls_max": display_count,
            "guest_framebuffer_nonzero": framebuffer is not None,
            "guest_framebuffer_observed": framebuffer,
            "guest_d3d_swap_entry": swap,
            "native_present_recorded": presented,
            "native_present_count_max": present_count,
        },
        "stop": {
            "kind": kind,
            "target": "0x" + target if target else None,
            "ticks": last_ticks,
            "fault_zero": no_fault,
            "caller": "0x" + stop.group(2).upper() if stop else None,
        },
    }
    return details


def render(result: dict) -> str:
    m = result["milestones"]
    stop = result["stop"]
    label = result["verdict"]
    frame_probe = result["test"] == "NT207-FRAME-CAPTURE"
    lines = [BEGIN, BAR, BAR,
             "MERCENARIES 360  |  END-OF-RUN MILESTONE VERDICT",
             BAR, BAR]
    if label == "PASS":
        lines += ["", "!" * 72,
                  ("!!!   SUCCESS!!!   ORDINAL 207 LIVE FRAME CAPTURED   !!!"
                   if frame_probe else
                   "!!!   SUCCESS!!!   XPP INPUT GETSTATE NATIVE CALL PROVED   !!!"),
                  "!" * 72]
    else:
        lines += ["", "#" * 72,
                  (f"###  {label}: ORDINAL 207 FRAME NOT PROVEN  ###" if frame_probe
                   else f"###  {label}: XPP INPUT GETSTATE NOT PROVEN  ###"),
                  "#" * 72]
    lines += ["", "CURRENT TEST: " + result["test"],
              "RESULT: " + label, "WHY: " + result["reason"], "", BAR,
              "MILESTONE BOARD (success means observed, never inferred)",
              BAR]

    def milestone(yes: bool, title: str, extra: str = ""):
        prefix = "[SUCCESS!!!]" if yes else "[NOT REACHED]"
        lines.append(f"{prefix:<16} {title}{extra}")
    milestone(m["retail_xbe_verified"], "Exact retail XBE verified")
    milestone(m["native_xenos_initialized"], "Native Xenos device initialized")
    milestone(m["guest_d3d_create_device_handoff"],
              "Guest D3D CreateDevice handoff")
    milestone(m["xpp_init_devices_entry"], "Guest XPP InitDevices entry")
    milestone(m["xpp_device_changes_entry"], "Guest XPP DeviceChanges entry")
    milestone(m["xpp_getstate_guest_entry"], "Guest XPP GetState entry")
    milestone(m["xpp_getstate_native_return"],
              "Real native XInputGetState returned",
              " status=" + (m["xpp_getstate_native_status"] or "UNKNOWN"))
    milestone(m["xpp_getstate_native_status_success"],
              "Native GetState returned ERROR_SUCCESS")
    milestone(m["xpp_setstate_guest_entry"], "Guest XPP SetState entry")
    milestone(m["xpp_setstate_native_return"], "Native XInputSetState returned")
    milestone(m["xpp_close_guest_entry"], "Guest XPP Close entry")
    milestone(m["nt207_original_directory_frame_capture"],
              "Xbox original NtQueryDirectoryFile argument frame captured")
    milestone(m["nt207_native_directory_enumeration"],
              "Native NtQueryDirectoryFile enumeration completed")
    milestone(m["guest_av_display_call_reached"],
              "REAL guest AvSetDisplayMode / display call",
              " count=" + str(m["guest_display_calls_max"]))
    milestone(m["guest_framebuffer_nonzero"],
              "REAL guest framebuffer nonzero",
              " value=" + (m["guest_framebuffer_observed"] or "00000000"))
    milestone(m["guest_d3d_swap_entry"], "REAL guest D3D Swap entry")
    milestone(m["native_present_recorded"],
              "REAL native Present call observed")
    lines += ["", "AUDIO PATH: " + ("REACHED (NOT audible-output proof)"
                                    if m["audio_code_path_reached_not_audible_proof"]
                                    else "NOT PROVEN"),
              "VISIBLE PIXELS: NOT AUTOMATICALLY CLAIMED; verify capture output.",
              "", BAR, "STOP / FRONTIER EVIDENCE", BAR,
              "Last ticks: " + (str(stop["ticks"]) if stop["ticks"] is not None else "UNKNOWN"),
              "Boundary: " + (stop["kind"] or "UNKNOWN"),
              "Target: " + (stop["target"] or "UNKNOWN"),
              "Guest fault=0: " + ("YES" if stop["fault_zero"] is True
                                   else "NO" if stop["fault_zero"] is False
                                   else "UNKNOWN"),
              "Completed log: " + ("YES" if result["completed"] else "NO"),
              "", "VERDICT RULE: success requires proof of selected TEST,",
              "not tick increases or static source coverage.",
              ("Ordinal207 frame capture is DIAGNOSTIC ONLY; native directory"
               if frame_probe else "XPP GetState success requires actual entry")
              + (" enumeration still blocked." if frame_probe
                 else " and native return."),
              "Tick increases alone never cause SUCCESS.",
              "This board is added by a PC log analyzer; it does not",
              "retroactively change what the running Xbox executed.",
              BAR, END]
    return "\n".join(lines) + "\n"


def main() -> int:
    p = argparse.ArgumentParser()
    p.add_argument("--log", type=Path, required=False,
                   help="Finished xbWatson text log")
    p.add_argument("--test", choices=["auto", "xpp", "nt207"], default="auto",
                   help="Select expected hardware test; auto recognizes ordinal207 probe")
    p.add_argument("--self-test", action="store_true",
                   help="Run synthetic PASS/BLOCKED marker regressions without XDK")
    p.add_argument("--no-append", action="store_true",
                   help="Only print and write sibling reports")
    args = p.parse_args()
    if args.self_test:
        header = "[Merc360:P5] PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START\n"
        footer = "[Merc360:P5] PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF END\n"
        blocked = header + (
            "[Merc360:P5] XPP D5574 ENTRY n=1\n"
            "[Merc360:P5] P6DQ ROCKET HARD STOP kind=2 caller=0023A3CE "
            "target=800000CF esp=008BF644 ticks=27108191\n"
            "[Merc360:P5] P6DQ AV FAMILY: display_calls=0 "
            "framebuffer=00000000\n"
        ) + footer
        b = summarize(blocked, "synthetic")
        assert b["verdict"] == "BLOCKED"
        assert b["stop"]["target"] == "0x800000CF"
        assert b["stop"]["ticks"] == 27108191
        assert not b["milestones"]["guest_d3d_swap_entry"]
        assert not b["milestones"]["guest_av_display_call_reached"]
        assert "SUCCESS!!!   XPP INPUT GETSTATE" not in render(b)
        passed = header + (
            "[Merc360:P5] XPP D54AC ENTRY n=1\n"
            "[Merc360:P5] XPP XINPUT state: handle=1 port=0 "
            "status=00000000 out=008BF000 packet=12\n"
            "[Merc360:P5] P6DQ AV FAMILY: display_calls=1 "
            "framebuffer=02628000\n"
            "[Merc360:P5] D3DDevice_Swap ENTRY n=1\n"
            "[Merc360:P5] native_present_calls=1\n"
        ) + footer
        ok = summarize(passed, "synthetic")
        assert ok["verdict"] == "PASS"
        assert ok["milestones"]["guest_av_display_call_reached"]
        assert ok["milestones"]["guest_framebuffer_nonzero"]
        assert ok["milestones"]["guest_d3d_swap_entry"]
        assert ok["milestones"]["native_present_recorded"]
        assert "SUCCESS!!!   XPP INPUT GETSTATE" in render(ok)
        mismatch = passed.replace("XPP D54AC ENTRY", "XPP 002D559B ENTRY")
        assert summarize(mismatch, "synthetic")["verdict"] != "PASS"
        static_false = header + (
            "[Merc360:P5] static D3DDevice_Swap 0x0028BDB0\n"
            "[Merc360:P5] P6DQ AV FAMILY: display_calls=0 "
            "framebuffer=00000000 swap_calls=8\n"
        ) + footer
        sf = summarize(static_false, "synthetic")
        assert not sf["milestones"]["guest_d3d_swap_entry"]
        assert not sf["milestones"]["native_present_recorded"]
        assert not sf["milestones"]["guest_av_display_call_reached"]
        nt207_log = header + (
            "[Merc360:P5] K1NT207 FRAME GATE: ordinal=207 NtQueryDirectoryFile "
            "caller=0023A3CE call_esp=008BF618 saved_esp=008BF644 "
            "delta=44 expected=44 guarded=1\n"
            "[Merc360:P5] K1NT207 FRAME RAW0: ret=00000000 a0=48000001 "
            "a1=00000000 a2=00000000 a3=00000000 a4=008BF794\n"
            "[Merc360:P5] K1NT207 FRAME RAW1: a5=008BF7D4 a6=00001000 "
            "a7=00000000 a8=00000000 a9=00000001\n"
            "[Merc360:P5] K1NT207 FRAME CAPTURED: original_ordinal=207 "
            "ret=00000000 handle=48000001\n"
            "[Merc360:P5] K1NT207 PROBE ONLY: NtQueryDirectoryFile "
            "NOT handled; original hard stop preserved\n"
            "[Merc360:P5] P6DQ ROCKET HARD STOP kind=2 caller=0023A3CE "
            "target=800000CF esp=008BF644 ticks=27108191\n"
        ) + footer
        nt = summarize(nt207_log, "synthetic", test="auto")
        assert nt["test"] == "NT207-FRAME-CAPTURE"
        assert nt["verdict"] == "PASS"
        assert nt["milestones"]["nt207_original_directory_frame_capture"]
        assert not nt["milestones"]["nt207_native_directory_enumeration"]
        assert "SUCCESS!!!   ORDINAL 207 LIVE FRAME CAPTURED" in render(nt)
        assert "DIAGNOSTIC ONLY" in render(nt)
        assert summarize(nt207_log.replace("guarded=1", "guarded=0"),
                         "synthetic", test="nt207")["verdict"] != "PASS"
        assert summarize(nt207_log, "synthetic", test="xpp")["verdict"] != "PASS"
        print("[MERC360-VERDICT] SELFTEST PASS: BLOCKED, PASS, graphics anti-false-positive")
        return 0
    if args.log is None:
        p.error("--log is required except when --self-test is used")
    if not args.log.is_file():
        p.error("Log file missing: " + str(args.log))
    raw = args.log.read_text(encoding="utf-8-sig", errors="replace")
    result = summarize(raw, str(args.log), test=args.test)
    board = render(result)
    txt = Path(str(args.log) + ".verdict.txt")
    js = Path(str(args.log) + ".verdict.json")
    txt.write_text(board, encoding="utf-8")
    js.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    print(board, end="")
    if not args.no_append:
        # Re-running the analyzer on a completed log is idempotent.
        # If a newer Xbox session was appended since our last report,
        # this creates a NEW final verdict at the bottom.
        prior = raw.rsplit(BEGIN, 1)[-1] if BEGIN in raw else None
        already_at_end = (prior is not None and
                          (BEGIN + prior).rstrip() == board.rstrip())
        if already_at_end:
            print("[MERC360-VERDICT] Already appended; leaving original log unchanged.")
        else:
            try:
                with args.log.open("a", encoding="utf-8", newline="") as fp:
                    if raw and not raw.endswith(("\n", "\r")):
                        fp.write("\n")
                    fp.write(board)
                print("[MERC360-VERDICT] APPENDED TO END OF LOG: " + str(args.log))
            except OSError as e:
                print("[MERC360-VERDICT] Cannot append; separate report saved: " + str(e),
                      file=sys.stderr)
                return 2
    print("[MERC360-VERDICT] REPORT: " + str(txt))
    print("[MERC360-VERDICT] JSON:   " + str(js))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
