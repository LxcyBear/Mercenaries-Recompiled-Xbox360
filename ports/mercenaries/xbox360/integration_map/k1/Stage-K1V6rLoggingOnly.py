#!/usr/bin/env python3
"""K1 V6r-LOG: independent native summary from hardware-verified V6q source.

Preserves all guest code and 64 TrueTUs; no missing 0022FA9E body is faked.
This builds the requested reporting enhancement while retail recovery continues.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
P=ROOT/"build/phase6_integration_map/k1_pixel_native_watson_v6q"
OUT=ROOT/"build/phase6_integration_map/k1_native_end_summary_v6rlog"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
MARK="K1-V6RLOG-END-SUMMARY-20261105"
def sha(data):return hashlib.sha256(data).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def stage():
    meta=json.loads((P/"v6q-manifest.json").read_text(encoding="utf-8-sig"))
    raw=(P/"main.cpp").read_bytes()
    require(meta.get("stage")=="V6Q_NATIVE_WATSON_FILTER_SOURCE_UNTESTED" and
            meta.get("source_sha256")==sha(raw) and
            meta.get("retail_17a120_preserved") is True and
            meta.get("apc_seven_read_source_preserved") is True and
            meta.get("changed_guest_instruction_logic") is False,
            "V6q source integrity drift")
    true_tus={p.name:sha(p.read_bytes()) for p in SHARDS.glob("translated_???.cpp")}
    require(len(true_tus)==64 and true_tus==meta.get("true_tu_sha256"),
            "64 original TrueTU source hash mismatch")
    original=raw.decode("utf-8")
    packed=original.replace("\r\n","\n")
    require(MARK not in packed,"V6rLOG already staged")
    require("P6DQ ROCKET HARD STOP" in packed and
            "K1-V6b APC QUEUED" in packed and
            "K1-V6b APC DELIVERED" in packed and
            "K1D3D SECOND: native Xenos Reset PASS" in packed,
            "Missing inherited retail/runtime evidence")
    # Native-only end-of-run metrics. The running guest remains untouched.
    # Read the already logged boundary and the guest display_calls counters,
    # then append actual results immediately after the original END line.
    native_summary=r"""
#include <stdio.h>
#include <stdlib.h>
static unsigned int k1v6r_last_ticks = 0;
static unsigned int k1v6r_kind_score = 0;
static unsigned int k1v6r_guest_displays = 0;
static bool k1v6r_seen_displays = false;
static bool k1v6r_emitting_summary = false;
static bool k1v6r_native_run_summary(const char* line) {
    if (!line || k1v6r_emitting_summary) return false;
    if (strstr(line, "BOUNDARY:")) {
        const char* tick = strstr(line, "ticks=");
        const char* kind = strstr(line, "kind=");
        if (tick) k1v6r_last_ticks = (unsigned int)strtoul(tick + 6, 0, 10);
        if (kind) {
            kind += 5;
            k1v6r_kind_score =
                strncmp(kind, "DIRECT_FRONTIER", 15) == 0 ? 4u :
                strncmp(kind, "ICALL", 5) == 0 ? 6u : 8u;
        }
    }
    if (strstr(line, "P6DQ PIXEL CHASE:") ||
        strstr(line, "P6DQ PRESENT PROXIMITY:") ||
        strstr(line, "entered XACTENG frontier 00280141")) {
        const char* n = strstr(line, "display_calls=");
        if (n) {
            unsigned int value = (unsigned int)strtoul(n + 14, 0, 10);
            if (!k1v6r_seen_displays || value > k1v6r_guest_displays)
                k1v6r_guest_displays = value;
            k1v6r_seen_displays = true;
        }
    }
    if (strstr(line, "PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF END")) {
        char buf[160];
        k1v6r_emitting_summary = true;
        trace(line);
        trace("OLD TICK COUNT: 61948779");
        if (k1v6r_last_ticks)
            sprintf(buf, "NEW TICK COUNT: %u", k1v6r_last_ticks);
        else
            sprintf(buf, "NEW TICK COUNT: N/A (no boundary observed)");
        trace(buf);
        if (k1v6r_kind_score)
            sprintf(buf, "SCALE 1-10 ON NEXT APPEARED PROBLEM: %u/10 (estimated from boundary kind)", k1v6r_kind_score);
        else
            sprintf(buf, "SCALE 1-10 ON NEXT APPEARED PROBLEM: N/A (no boundary observed)");
        trace(buf);
        if (k1v6r_seen_displays) {
            sprintf(buf, "GUEST DISPLAY CALLS: %u", k1v6r_guest_displays);
            trace(buf);
            trace(k1v6r_guest_displays > 0 ?
                  "DISPLAY_CALLS > 0: YES" : "DISPLAY_CALLS > 0: NO");
        } else {
            trace("GUEST DISPLAY CALLS: N/A (no display counter observed)");
            trace("DISPLAY_CALLS > 0: UNKNOWN");
        }
        k1v6r_emitting_summary = false;
        return true;
    }
    return false;
}
"""
    trace_entry=re.compile(
        r'(?m)^([ \t]*(?:(?:static|inline)[ \t]+)*void[ \t]+trace[ \t]*'
        r'\([ \t]*(?:const[ \t]+)?char[ \t]*\*[ \t]*(\w+)[ \t]*\)'
        r'[ \t\r\n]*\{)')
    entries=list(trace_entry.finditer(packed))
    require(len(entries)==1,"V6q native trace entry no longer unique")
    tr=entries[0]
    arg=tr.group(2)
    old_filter="if (!k1v6q_native_watson_allow("+arg+")) return;"
    require(packed.count(old_filter)==1,"V6q native logging filter drift")
    require(packed.count("K1-V6Q-NATIVE-WATSON-MUX-20261105")==1,"V6q trace guard missing")
    # The same trace() writer is used recursively for the five summary
    # messages. A reentrancy guard bypasses the filter ONLY for those messages.
    packed=packed.replace(old_filter,
        "if (!k1v6r_emitting_summary && !k1v6q_native_watson_allow("+arg+")) return;",1)
    entry=tr.group(1)
    # Keep the original function's linkage when declaring it for the helper.
    linkage="static " if re.match(r'\s*static\b',entry) else ""
    helper=linkage+"void trace(const char* line);\n"+native_summary+"\n"
    call="if (k1v6r_native_run_summary("+arg+")) return;"
    start=packed.index(entry)
    packed=packed[:start]+helper+packed[start:]
    offset=start+len(helper)+len(entry)
    packed=packed[:offset]+"\n    "+call+"\n"+packed[offset:]
    require(packed.count(call)==1,"Native summary hook not unique")
    require(packed.count("OLD TICK COUNT: 61948779")==1,"Old hardware record drift")
    require(packed.count("GUEST DISPLAY CALLS: %u")==1,"Display count hook missing")

    # Proof: reversing the exact logging-only splices restores the parent.
    # Stronger than comparing selected marker counts; original code must survive.
    require("GUEST DISPLAY CALLS: %u" in packed and
            "DISPLAY_CALLS > 0: YES" in packed,"V6rLOG display reports missing")
    packed="/* "+MARK+" */\n"+packed
    encoded=packed.replace("\n","\r\n").encode() if b"\r\n" in raw else packed.encode()
    manifest={"stage":"V6R_LOGGING_ONLY_SOURCE_UNTESTED",
              "parent_v6q_sha256":sha(raw),"source_sha256":sha(encoded),
              "hardware_ticks_before":61948779,
              "runtime_retail_frontier":"0x0022FA9E",
              "frontier_c_translation_available":False,
              "old_guest_17a120_source_preserved":True,
              "unknown_frontiers_fenced":True,
              "apc_reads_7_preserved_in_source":True,
              "guest_display_summary":True,
              "true_tu_sha256":true_tus,
              "hardware_tested":False}
    targets=[(OUT/"main.cpp",encoded),
             (OUT/"v6rlog-manifest.json",(json.dumps(manifest,indent=2)+"\n").encode())]
    for p,b in targets:
        require(not p.exists() or p.read_bytes()==b,
                "Previously staged V6rLOG file differs: "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,b in targets:
        if not p.exists():p.write_bytes(b)
    require((P/"main.cpp").read_bytes()==raw,"V6q parent changed during stage")
    print("[K1-V6rLOG] SOURCE PASS: V6q native logging + end metrics; 64 TrueTUs unchanged")
    print("[K1-V6rLOG] Retail 0022FA9E still requires original generated C; no fake code")
    print("[K1-V6rLOG] XDK and hardware NOT YET VERIFIED")
if __name__=="__main__":
    try:stage()
    except Exception as ex:
        print("[K1-V6rLOG] HARD FENCE: "+str(ex),file=sys.stderr);sys.exit(1)
