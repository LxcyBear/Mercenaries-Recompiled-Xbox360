#!/usr/bin/env python3
"""Plan a *single* bounded native XPP input family build, before hardware runs.

Combines three independent local witnesses:
 - xboxrecomp original 16,662-function cross-reference manifest
 - user's original generated C functions (never exports any source)
 - current 64 TrueTU staged source and optional TGP482 symbol metadata

The planner does NOT compile, inject guest code, reinterpret XDK APIs,
relax hard fences or conclude anything was executed from a static graph.
It emits metadata-only JSON and a human report for a guarded batch stage.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
import zipfile
from collections import defaultdict, deque
from pathlib import Path

RETAIL_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
EXPECTED_PARENT="XPP-D54AC-NATIVE-GETSTATE-20261031"
XPP_LO=0x002D4300
XPP_HI=0x002DBCC8
ROOT=0x002D54AC
# Public compat layer implements exactly these 8. Only the first six have
# native implementations proven/staged by the previous controller chain.
HELPERS={
    "recomp_xinput_init_devices":"PREVIOUS_NATIVE",
    "recomp_xinput_get_devices":"PREVIOUS_NATIVE",
    "recomp_xinput_get_device_changes":"PREVIOUS_NATIVE",
    "recomp_xinput_open":"PREVIOUS_NATIVE",
    "recomp_xinput_close":"NEEDS_NATIVE_SOURCE_REVIEW",
    "recomp_xinput_get_capabilities":"PREVIOUS_NATIVE",
    "recomp_xinput_get_state":"CURRENT_D54AC_NATIVE",
    "recomp_xinput_set_state":"NEEDS_NATIVE_SOURCE_REVIEW",
}
KNOWN={
    0x002D5574:"recomp_xinput_init_devices",
    0x002D5579:"recomp_xinput_get_devices",
    0x002D559B:"recomp_xinput_get_device_changes",
    0x002D5272:"recomp_xinput_open",
    0x002D52D4:"recomp_xinput_get_capabilities",
    0x002D54AC:"recomp_xinput_get_state",
}
DECL=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")
CALL=re.compile(r"\bsub_([0-9A-Fa-f]{8})\s*\(")
HELPERCALL=re.compile(r"\b(recomp_xinput_[A-Za-z_0-9]+)\s*\(")
RET=re.compile(r"\besp\s*\+=\s*(\d+)u?\s*;\s*return\s*;")
LITERAL_DIRECT=re.compile(r"phase4c_direct_frontier\(\s*0x([0-9A-Fa-f]{8})u\s*\)\s*;")
SUPPORTED_SHA={
    0x002D52D4:"80aa0150e3d680d11925e2b2c3465509930b557fc511f625bafbbdea39e09ed5",
    0x002D54AC:"48e4ccc7ccc0ae3bfa852d584996f6f1ed034d0491f05433722054038f42a0e2",
    0x002D5272:"e70c09fe6c1504d570d88b7bf2e98f339f7279e8a690b7cd3a3beefdaa7a5af7",
}
PRIORITY=("recomp_xinput_get_state","recomp_xinput_set_state","recomp_xinput_close")

def addr(x):
    try:
        return int(str(x),0)
    except (ValueError,TypeError):
        return None

def hx(x):
    return "0x%08X"%x

def source_reader(emitter,ranges,generated):
    spec=importlib.util.spec_from_file_location("xpp_predict_reader",str(emitter))
    if spec is None or spec.loader is None:
        raise ValueError("Original generated-source loader unavailable")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    a,by_name=mod.load_ranges(ranges)
    funcs=mod.load_generated(generated,by_name)
    if len(funcs)<10000: raise ValueError("Incomplete original generated C corpus")
    return a,funcs,mod

def read_manifest(path):
    with zipfile.ZipFile(path) as z:
        data=json.loads(z.read("xboxrecomp_manifest.json"))
        summary=z.read("merc360_frontier_summary.txt").decode("utf-8-sig")
    if (data.get("functions")!=16662 or
        data.get("no_raw_game_bytes") is not True or
        RETAIL_SHA not in summary):
        raise ValueError("Static inventory does not authenticate retail title")
    funcs={addr(x["address"]):x for x in data["function_list"]}
    if len(funcs)!=16662:
        raise ValueError("Old static inventory has duplicate guest VA")
    return funcs

def get_parent(path,stage,main):
    d=json.loads(path.read_text(encoding="utf-8-sig"))
    if (d.get("marker")!=EXPECTED_PARENT or
        d.get("status")!="SOURCE_CLOSED_STAGED_NO_XDK" or
        d.get("hardware_target")!="0x002D54AC" or
        d.get("original_function_sha256")!=SUPPORTED_SHA[ROOT] or
        d.get("native_state_buffer_bytes")!=22 or
        d.get("guest_display_calls_injected") is not False or
        d.get("hard_fences")!="UNCHANGED" or
        d.get("mmio_fences")!="UNCHANGED" or
        Path(d.get("staged_directory","BAD")).resolve()!=stage.resolve() or
        Path(d.get("staged_main","BAD")).resolve()!=main.resolve() or
        hashlib.sha256(main.read_bytes()).hexdigest()!=d.get("new_main_sha")):
        raise ValueError("D54AC verified parent metadata/host hash drift")
    shards=sorted(stage.glob("translated_???.cpp"))
    if len(shards)!=64:
        raise ValueError("Expected exactly 64 current TRUE TUs")
    compiled=defaultdict(set)
    direct_sites=defaultdict(set)
    for p in shards:
        content=p.read_text(encoding="utf-8")
        expected=d.get("new_owner_hashes",{}).get(
            p.name,d.get("original_owner_hashes",{}).get(p.name))
        if hashlib.sha256(p.read_bytes()).hexdigest()!=expected:
            raise ValueError("Inherited TrueTU drift: "+p.name)
        for match in DECL.finditer(content):
            compiled[int(match.group(1),16)].add(p.name)
        for match in LITERAL_DIRECT.finditer(content):
            direct_sites[int(match.group(1),16)].add(p.name)
    for match in LITERAL_DIRECT.finditer(main.read_text(encoding="utf-8")):
        direct_sites[int(match.group(1),16)].add("main.cpp")
    return compiled,direct_sites

def source_helper(item,reader):
    text=item["source"]
    declared=DECL.search(text)
    if declared is None:
        return None
    # Never scan the own declaration as a recursive call.
    masked=reader.mask_noncode(text)
    m=DECL.search(masked)
    if m is None:
        return None
    body=masked[m.end():]
    helpers=sorted(set(HELPERCALL.findall(body)))
    calls=sorted(set(int(n,16) for n in CALL.findall(body)))
    return helpers,calls,sorted(set(RET.findall(body)))

def scan(a):
    for p in (a.parent_manifest,a.parent_main,a.recon,a.emitter,a.ranges,a.generated):
        if not p.exists(): raise ValueError("Missing private local input: "+str(p))
    compiled,direct_sites=get_parent(a.parent_manifest,a.shards,a.parent_main)
    old=read_manifest(a.recon)
    ranges,source,reader=source_reader(a.emitter,a.ranges,a.generated)
    # Optional signature info: use only a real scanner symbol assignment, not
    # string guessing or a fabricated inference about what the XDK executes.
    scanner={}
    if a.tgp_config and a.tgp_config.is_file():
        active=None
        for line in a.tgp_config.read_text(encoding="utf-8-sig").splitlines():
            line=line.strip()
            if line.startswith("[") and line.endswith("]"):
                active=line[1:-1]
                continue
            if active=="symbols":
                m=re.match(r"^(XInput[A-Za-z0-9_]+)\s*=\s*(0x[0-9A-Fa-f]+|\d+)(?:\s*#.*)?$",line)
                if m:
                    scanner[m.group(1)]=addr(m.group(2))
    detected=[]
    inventory_count=0
    for at,item in source.items():
        if not XPP_LO<=at<XPP_HI: continue
        inventory_count+=1
        detail=source_helper(item,reader)
        if detail is None: continue
        helpers,calls,returns=detail
        if len(helpers)!=1 or helpers[0] not in HELPERS: continue
        name=helpers[0]
        if calls: continue
        snippet=item["source"]
        digest=hashlib.sha256(snippet.encode("utf-8")).hexdigest()
        meta=old.get(at,{})
        known_name=KNOWN.get(at)
        if known_name and known_name!=name:
            raise ValueError("Source vs proven XPP helper mismatch at "+hx(at))
        if at in SUPPORTED_SHA and digest!=SUPPORTED_SHA[at]:
            raise ValueError("Retail known XPP function SHA drift at "+hx(at))
        cached_edges=[addr(v) for v in meta.get("calls_to",[])]
        caller_count=len(meta.get("called_by",[]))
        status=HELPERS[name]
        if at in compiled:
            disposition="ALREADY_STAGED_SOURCE"
        elif status=="NEEDS_NATIVE_SOURCE_REVIEW":
            disposition="CANDIDATE_REQUIRES_NATIVE_BRIDGE_SOURCE_ABI_PROOF"
        elif status=="PREVIOUS_NATIVE" or status=="CURRENT_D54AC_NATIVE":
            disposition="CANDIDATE_REQUIRES_DIRECT_FRONTIER_AND_ABI_PROOF"
        else:
            disposition="HARD_FENCE_UNSUPPORTED"
        detected.append({
            "va":hx(at),"helper":name,
            "status":disposition,
            "original_source_sha256":digest,
            "original_source_file":item["file"],
            "ret_esp_deltas":returns,
            "static_caller_count":caller_count,
            "static_callees":[hx(v) for v in cached_edges if v is not None],
            "stage_source_owner":sorted(compiled.get(at,[])),
            "current_direct_frontier_sites":sorted(direct_sites.get(at,[])),
            "scanner_symbol_names":sorted(n for n,va in scanner.items() if va==at),
            "previous_hardware_proven":at in (0x002D5272,0x002D52D4),
            "native_bridge_implementation":status
        })
    order={x:i for i,x in enumerate(PRIORITY)}
    detected.sort(key=lambda d:(0 if d["current_direct_frontier_sites"] else 1,
                               order.get(d["helper"],10),
                               -d["static_caller_count"],d["va"]))
    report={
        "marker":"K1-XPP-CROSS-REPO-PREDICTIVE-20261031",
        "mode":"READ_ONLY_NO_XDK_NO_XBOX",
        "retail_title_id":"0x4C410015",
        "retail_xbe_sha256":RETAIL_SHA,
        "original_function_count":len(source),
        "xboxrecomp_function_count":len(old),
        "xpp_original_function_count":inventory_count,
        "staged_true_tus":64,
        "live_hardware_frontier":hx(ROOT),
        "live_hardware_ticks":27107620,
        "live_framebuffer_display_calls":0,
        "no_raw_game_bytes":True,
        "tgp482_symbol_count":len(scanner),
        "candidates":detected,
        "warnings":[
            "A static direct-call edge is NOT proof of a guest runtime path",
            "Previously staged TrueTUs do NOT imply the Xbox has executed a function",
            "Do NOT generate XPP functions from library signatures alone",
            "Unknown helper, indirect call, MMIO/VP, or unproved ABI stays fenced",
            "Only source-closed XPP wrappers get eligible for a multi-function next XEX"
        ]
    }
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.json.parent.mkdir(parents=True,exist_ok=True)
    a.json.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    lines=[
        "[XPP-PREDICT] =====================================================",
        "[XPP-PREDICT] STATIC CROSS-REPO ONE-BUILD INPUT FRONTIER PLANNER",
        "[XPP-PREDICT] =====================================================",
        "[XPP-PREDICT] PASS: Xboxrecomp 16662 original funcs, generated C %d, XPP %d"%
            (len(source),inventory_count),
        "[XPP-PREDICT] PASS: inherited 64 TrueTUs and exact D54AC parent manifest",
        "[XPP-PREDICT] TGP482 scanner matching input symbols loaded=%d"%len(scanner),
        "[XPP-PREDICT] Detected %d source-backed XPP one-helper wrappers"%len(detected),
    ]
    for row in detected:
        lines.append(
            "[XPP-PREDICT] %s helper=%s status=%s caller_count=%d ret_esp=%s direct_sites=%s stage=%s source_sha256=%s"%
            (row["va"],row["helper"],row["status"],
             row["static_caller_count"],",".join(row["ret_esp_deltas"]) or "?",
             ",".join(row["current_direct_frontier_sites"]) or "NONE",
             ",".join(row["stage_source_owner"]) or "NOT_STAGED",
             row["original_source_sha256"]))
    lines.extend([
        "[XPP-PREDICT] RECOMMENDATION: pack independently source/ABI-closed XPP wrappers in a single bounded incremental build",
        "[XPP-PREDICT] NEVER infer execution from the static graph; preserve guest fences and exact native return semantics",
        "[XPP-PREDICT] Share metadata report only, not the original guest-generated C source.",
        "[XPP-PREDICT] JSON="+str(a.json),
        "[XPP-PREDICT] END.",
    ])
    a.report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("\n".join(lines))

def self_test():
    assert len(HELPERS)==8 and len(set(HELPERS))==8
    assert ROOT==0x002D54AC and ROOT in KNOWN
    assert addr("0x002D54AC")==ROOT
    assert len(SUPPORTED_SHA[ROOT])==64
    assert RET.findall("eax=1; esp += 12u; return;")==["12"]
    assert HELPERCALL.findall("eax=recomp_xinput_get_state(a,b);")==["recomp_xinput_get_state"]
    assert CALL.findall("sub_002D52D4();")==["002D52D4"]
    assert DECL.findall("void sub_002D54AC(void)\n{\n}")==["002D54AC"]
    print("[XPP-PREDICT] SELFTEST PASS: eight exact publicly implemented native Xbox input helpers")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for arg in ("parent_manifest","parent_main","shards","recon","emitter","ranges",
                "generated","tgp_config","report","json"):
        p.add_argument("--"+arg.replace("_","-"),type=Path)
    a=p.parse_args()
    if a.self_test:
        self_test()
        return
    for arg in ("parent_manifest","parent_main","shards","recon","emitter",
                "ranges","generated","report","json"):
        if getattr(a,arg) is None:p.error("--"+arg.replace("_","-")+" required")
    scan(a)

if __name__=="__main__":
    main()
