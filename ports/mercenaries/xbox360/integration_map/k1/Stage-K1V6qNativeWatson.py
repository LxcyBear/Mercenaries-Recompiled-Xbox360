#!/usr/bin/env python3
"""K1 V6q source-level native Watson filter; no guest logic changes.

Patch ONLY the exact main.cpp trace(const char*) function entry. If it is
not uniquely recognizable, refuse to create a build. All existing hard-stop
code, original 64 TrueTUs, D3D/APC/guest logic remain byte-identical.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path
P=Path("build/phase6_integration_map/k1_pixel_direct_17a120_v6p")
OUT=Path("build/phase6_integration_map/k1_pixel_native_watson_v6q")
MARK="K1-V6Q-NATIVE-WATSON-MUX-20261105"
ENTRY=re.compile(r'(?m)^([ \t]*(?:static[ \t]+)?void[ \t]+trace[ \t]*\([ \t]*(?:const[ \t]+)?char[ \t]*\*[ \t]*(\w+)[ \t]*\)[ \t]*\{)')
DECL=re.compile(r'(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+trace[ \t]*\(')
FILTER=r'''
/* Native xbWatson output filter ONLY. Never changes guest execution.
 * MERC360_NATIVE_LOG_VERBOSE=1 retains the entire pre-V6q stream.
 * On default 0, all hard stops, boundaries, errors, fault and final
 * graphics/APC summaries remain visible. No allocations on hot path.
 */
#include <string.h>
#ifndef MERC360_NATIVE_LOG_VERBOSE
#define MERC360_NATIVE_LOG_VERBOSE 0
#endif
static unsigned int s_k1v6q_muted_lines = 0;
static unsigned int s_k1v6q_lines = 0;
static bool k1v6q_native_watson_allow(const char* line) {
    if (!line) return true;
#if MERC360_NATIVE_LOG_VERBOSE
    return true;
#else
    ++s_k1v6q_lines;
    /* Fail open on warnings, errors, faults and all boundary evidence. */
    if (strstr(line,"HARD STOP") || strstr(line,"BOUNDARY:") ||
        strstr(line,"FAULT") || strstr(line,"ERROR") ||
        strstr(line,"FAILED") || strstr(line,"MISMATCH") ||
        strstr(line,"UNSUPPORTED") || strstr(line,"ASSERT") ||
        strstr(line,"WATCHDOG") || strstr(line,"FATAL") ||
        strstr(line,"STOPPED"))
        return true;
    /* Compact native milestones & summary; keep original exact fields. */
    if (strstr(line,"K1-V6b APC QUEUED") ||
        strstr(line,"K1-V6b APC DELIVERED") ||
        strstr(line,"XACT async NtReadFile immediate completion") ||
        strstr(line,"P6DQ ASYNC STREAM READ:") ||
        strstr(line,"P6DQ PIXEL CHASE:") ||
        strstr(line,"P6DQ PRESENT PROXIMITY:") ||
        strstr(line,"PHASE 6DQ XENOS DEVICE RESULT:") ||
        strstr(line,"PHASE 6DQ VERIFIED XBE LOAD RESULT:") ||
        strstr(line,"PHASE 6DQ EXECUTION ENVIRONMENT RESULT:") ||
        strstr(line,"PHASE 6DQ ENVIRONMENT RESULT:") ||
        strstr(line,"native D3D CreateDevice handoff") ||
        strstr(line,"K1D3D SECOND: native Xenos Reset PASS") ||
        strstr(line,"entered XACTENG frontier") ||
        strstr(line,"entered DSOUND owner") ||
        strstr(line,"P6DQ HOT PROFILE:") ||
        strstr(line,"P6DQ ROCKET JOURNAL HARD[") ||
        strstr(line,"P6DQ ITAIL SATURATION:") ||
        strstr(line,"P6DQ D3D DEVICE:") ||
        strstr(line,"K1QUIET MILESTONE SUMMARY:") ||
        strstr(line,"K1PERF LAST_TO_FAULT:") ||
        strstr(line,"P6DQ SPIN SAMPLE tick=") ||
        strstr(line,"K1PERF WINDOW:") ||
        strstr(line,"PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF END"))
        return true;
    ++s_k1v6q_muted_lines;
    return false;
#endif
}
'''
def die(message):raise ValueError(message)
def sha(b):return hashlib.sha256(b).hexdigest()
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--verbose",action="store_true",help="compile with full native Watson output")
    ap.add_argument("--self-test",action="store_true")
    args=ap.parse_args()
    if args.self_test:
        test();return
    meta=json.loads((P/"v6p-manifest.json").read_text(encoding="utf-8-sig"))
    raw=(P/"main.cpp").read_bytes()
    if(meta.get("stage")!="V6P_RETAIL_DIRECT_0017A120_SOURCE_UNTESTED"
       or meta.get("source_sha256")!=sha(raw)
       or meta.get("apc_reads_7_preserved_in_source") is not True
       or meta.get("unknown_frontiers_fenced") is not True
       or len(meta.get("true_tu_sha256",{}))!=64
       or meta.get("retail_asset_checkpoint_429_restore",{}).get("retail_original_guest_instructions_restored") is not True):
        die("V6p certified source/retail/APC/64 TrueTU manifest drift")
    text=raw.decode("utf-8")
    result,info=patch(text,args.verbose)
    outbytes=result.encode("utf-8")
    manifest={"stage":"V6Q_NATIVE_WATSON_FILTER_SOURCE_UNTESTED",
              "parent_sha256":sha(raw),"source_sha256":sha(outbytes),
              "trace_function_signature":info,"native_verbose":args.verbose,
              "changed_guest_instruction_logic":False,
              "retail_17a120_preserved":True,
              "apc_seven_read_source_preserved":True,
              "true_tu_sha256":meta["true_tu_sha256"],
              "first_pixels_verified":False,"hardware_tested":False}
    targets=[(OUT/"main.cpp",outbytes),
             (OUT/"v6q-manifest.json",(json.dumps(manifest,indent=2)+"\n").encode())]
    for f,b in targets:
        if f.exists() and f.read_bytes()!=b:die("Existing V6q output differs; no overwrite: "+str(f))
    OUT.mkdir(parents=True,exist_ok=True)
    for f,b in targets:
        if not f.exists():f.write_bytes(b)
    if (P/"main.cpp").read_bytes()!=raw:die("Parent mutated")
    print("[K1-V6q] NATIVE WATSON SOURCE PASS: trace() ingress, guest logic untouched")
    print("[K1-V6q] Mode: "+("FULL VERBOSE" if args.verbose else "MILESTONES + BLOCKERS"))
    print("[K1-V6q] XDK and hardware NOT YET VERIFIED")
def patch(src,verbose=False):
    if MARK in src:die("Already native-filtered")
    normalized=src.replace("\r\n","\n")
    matches=list(ENTRY.finditer(normalized))
    if len(matches)!=1:
        # Do not guess at a different C++ signature. Print the original
        # definition candidates so the exact emitter can be targeted safely.
        candidates=[]
        for match in re.finditer(r'\\btrace\\s*\\(',normalized):
            snippet=normalized[max(0,match.start()-90):match.start()+130]
            if "void" in snippet or "inline" in snippet:
                candidates.append(repr(snippet))
            if len(candidates)>=8:break
        die("Cannot locate ONE native trace(const char*) definition; count=%d; candidates=%s" %
            (len(matches),"; ".join(candidates)))
    # Require the trace implementation on the source-only main. Do not patch
    # a trace() call or a declaration, and never patch 64 translated shards.
    entry=matches[0]; arg=entry.group(2)
    if not re.match(r'^[A-Za-z_]\w*$',arg):die("Unsafe trace parameter")
    pos=entry.end()
    filter_code=FILTER.replace("MERC360_NATIVE_LOG_VERBOSE 0",
                               "MERC360_NATIVE_LOG_VERBOSE "+("1" if verbose else "0"))
    modified=(normalized[:entry.start()]+
              "/* "+MARK+" */\n"+filter_code+"\n"+
              normalized[entry.start():pos]+
              "\n    if (!k1v6q_native_watson_allow("+arg+")) return;\n"+
              normalized[pos:])
    if (modified.replace("\n    if (!k1v6q_native_watson_allow("+arg+")) return;\n","",1)
         .replace("/* "+MARK+" */\n"+filter_code+"\n","",1)!=normalized):
        die("Non-logger source bytes modified")
    # The logging allowlist intentionally mentions some original message
    # strings, so counting signatures in the whole modified file would
    # falsely report a change. Compare the recovered original source instead.
    recovered=(modified.replace(
        "\n    if (!k1v6q_native_watson_allow("+arg+")) return;\n","",1)
        .replace("/* "+MARK+" */\n"+filter_code+"\n","",1))
    if recovered!=normalized:
        die("Native Watson patch changed code outside trace ingress")
    for sig in ("K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105",
                "K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                "P6DQ ROCKET HARD STOP","P6DQ PIXEL CHASE",
                "K1D3D SECOND: native Xenos Reset PASS"):
        if recovered.count(sig)!=normalized.count(sig):
            die("Missing or modified original guest milestone: "+sig)
    if "\r\n" in src:modified=modified.replace("\n","\r\n")
    return modified,entry.group(1)
def test():
    fixture=("void trace(const char* line) {\n"
             "    OutputDebugStringA(line);\n"
             "}\n"
             "K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105\n"
             "K1-V6b APC QUEUED\nK1-V6b APC DELIVERED\n"
             "P6DQ ROCKET HARD STOP\nP6DQ PIXEL CHASE\n"
             "K1D3D SECOND: native Xenos Reset PASS\n")
    got,sign=patch(fixture)
    assert "if (!k1v6q_native_watson_allow(line)) return;" in got
    assert "MERC360_NATIVE_LOG_VERBOSE 0" in got
    full,_=patch(fixture,True)
    assert "MERC360_NATIVE_LOG_VERBOSE 1" in full
    try:patch(got)
    except ValueError:pass
    else:raise AssertionError("Double patch accepted")
    print("[K1-V6q] SELFTEST PASS: trace ingress, verbose switch, guest source preservation")
if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("[K1-V6q] HARD FENCE: "+str(ex),file=sys.stderr);sys.exit(1)
