#!/usr/bin/env python3
"""Offline, metadata-only cross-check of xboxrecomp and TGP482/XboxXBERecomp.

No XBE parsing, host/guest code publishing, internet access, or console action.
Uses user's existing metadata ZIP plus upstream XDK 5849 signatures/layout,
optionally TGP482's user-local x86_func_mapping.cpp after independent recomp.
This script does NOT identify a function by length alone.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import subprocess
import zipfile
from collections import Counter
from pathlib import Path

EXPECTED_FUNCTIONS=16662
RETAIL_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
FOCUS=[
    0x002D52D4, # newest hardware direct frontier after XInputOpen PASS
    0x002D5272, # hardware-proven XInputOpen
    0x002D559B, # hardware-proven XGetDeviceChanges
    0x002D5579, # hardware-proven XGetDevices
    0x0028A530, # already-compiled D3D AvSetDisplayMode caller
    0x0028B430, # already-compiled D3D AvSetDisplayMode caller
    0x002888A0, # missing D3D with many compiled incoming callers
    0x00288F80, 0x00288B30, 0x00289E20, 0x0028A090, 0x00288960,
    0x0029C13E, # XGRPH missing child D9B9D0
]
SIG=re.compile(r'(?m)^([A-Za-z][A-Za-z0-9_]*)\s*=\s*\{sec\s*=\s*"([^"]+)",\s*len\s*=\s*(0x[0-9A-Fa-f]+|\d+)(.*)$')
RET=re.compile(r'\bret\s*=\s*(\d+)')
XTLID=re.compile(r'\bxtlid\s*=\s*(0x[0-9A-Fa-f]+|\d+)')
LAYOUT=re.compile(r'(?m)^([A-Za-z][A-Za-z0-9_]*)\s*=\s*(0x[0-9A-Fa-f]+|\d+)\s*(?:#.*)?$')
MAPPING=re.compile(r'(?m)^\s*\{0x([0-9A-Fa-f]+)u,\s*sub_[0-9A-Fa-f]+\},\s*$')

def parse_signatures(path):
    content=path.read_text(encoding="utf-8")
    if "[symbols]" not in content or "XInputOpen" not in content:
        raise ValueError("Unexpected XDK signature database")
    signatures={}
    for match in SIG.finditer(content.split("[symbols]",1)[1].split("\n[data]",1)[0]):
        name,section,raw,tail=match.groups()
        m=RET.search(tail)
        x=XTLID.search(tail)
        signatures[name]={"name":name,"section":section,
                          "length":int(raw,0),"stack_pop":int(m.group(1)) if m else None,
                          "xtlid":x.group(1) if x else None}
    if len(signatures)<80 or "XInputOpen" not in signatures:
        raise ValueError("XDK 5849 signature parsing incomplete: %d"%len(signatures))
    return signatures

def load_manifest(path):
    with zipfile.ZipFile(path) as z:
        name="xboxrecomp_manifest.json"
        if name not in z.namelist():
            raise ValueError("Expected original xboxrecomp metadata-only ZIP")
        m=json.loads(z.read(name))
    if (m.get("no_raw_game_bytes") is not True or
        m.get("functions")!=EXPECTED_FUNCTIONS or
        len(m.get("function_list",[]))!=EXPECTED_FUNCTIONS):
        raise ValueError("Missing valid known 16662-function xboxrecomp metadata inventory")
    entries={}
    for x in m["function_list"]:
        v=int(x["address"],16)
        if v in entries:
            raise ValueError("Duplicate original function address")
        entries[v]=x
    return entries

def load_layout(path):
    data=path.read_text(encoding="utf-8")
    if "[layout]" not in data:
        raise ValueError("XDK 5849 layout table absent")
    return {a:int(b,0) for a,b in LAYOUT.findall(data.split("[layout]",1)[1])}

def parse_map(path):
    if not path or not path.exists():
        return None
    text=path.read_text(encoding="utf-8")
    if "X86FuncMappings[]" not in text:
        raise ValueError("TGP482 emitted mapping is not an X86FuncMappings table")
    matches={int(x,16) for x in MAPPING.findall(text)}
    if len(matches)<100:
        raise ValueError("No plausible independent TGP482 emitted function inventory")
    return matches

def get_commit(sdk):
    p=subprocess.run(["git","-C",str(sdk),"rev-parse","HEAD"],capture_output=True,text=True,check=False)
    return p.stdout.strip() if p.returncode==0 else "unavailable"

def examine_function(va,entries,signatures):
    x=entries.get(va)
    if not x:
        return None
    sect=x["section"]
    size=int(x["size"])
    candidates=sorted(
        (s for s in signatures.values() if s["section"].lower()==sect.lower()),
        key=lambda s:(abs(s["length"]-size),s["name"]),
    )
    return {
        "address":x["address"],"section":sect,"size":size,
        "end":x.get("end"),
        "translated_in_old_pixel_batch":bool(x.get("present_in_pixel_true_tus")),
        "static_callees":x.get("calls_to",[]),
        "static_callers":x.get("called_by",[]),
        "size_nearby_signatures":[{
            "name":s["name"],"length":s["length"],"stack_pop":s["stack_pop"],
            "delta":s["length"]-size,
            "size_only_not_identity":True
        } for s in candidates[:5]],
    }

def audit(a):
    sdk=a.sdk.resolve()
    sigfile=sdk/"xdk"/"5849"/"signatures.toml"
    layoutfile=sdk/"xdk"/"5849"/"layout.toml"
    for p in (sigfile,layoutfile,a.recon_zip):
        if not p.is_file():
            raise ValueError("Missing local original metadata or cloned upstream SDK file: "+str(p))
    entries=load_manifest(a.recon_zip)
    signatures=parse_signatures(sigfile)
    layout=load_layout(layoutfile)
    actual=parse_map(a.mapping)
    info={ "source":"TGP482/XboxXBERecomp (independent read-only sidecar)",
        "upstream_commit":get_commit(sdk),
        "xdk_signatures":len(signatures),
        "xdk_build":5849,
        "previous_xboxrecomp_function_inventory":len(entries),
        "retail_sha_expected":RETAIL_SHA,
        "last_xbox_frontier":"0x002D52D4",
        "last_hardware_ticks":27107602,
        "last_hardware_xinput_open":"port=0 handle=1",
        "important_functions":[z for v in FOCUS if (z:=examine_function(v,entries,signatures))],
        "xdk_layout":{k:layout.get(k) for k in (
            "CDevice_RenderTarget","CDevice_BackBuffer",
            "CDevice_FrontBuffer","CDevice_SwapCount","CDevice_DisplayFlags",
            "XPP_Current","XPP_Changed","XPP_Previous")},
    }
    if "XInputOpen" in signatures:
        info["xinput_open_signature"]=signatures["XInputOpen"]
    if actual is not None:
        old=set(entries)
        new=actual-old
        missed=old-actual
        info["independent_recomp"]={
            "functions":len(actual),"overlap":len(actual&old),
            "discovered_only_by_tgp":len(new),
            "only_in_xboxrecomp":len(missed),
            "discovered_only_by_tgp_sample":[f"0x{x:08X}" for x in sorted(new)[:60]],
            "only_in_xboxrecomp_sample":[f"0x{x:08X}" for x in sorted(missed)[:60]],
            "focus_found_by_tgp":{f"0x{x:08X}":x in actual for x in FOCUS},
            "warning":"Different analysis boundaries may cause false differences; inspect before using addresses."
        }
    lines=[
        "[TGP-XBR] =====================================================",
        "[TGP-XBR]    XBOX XBE RECOMP SECOND-OPINION METADATA AUDIT",
        "[TGP-XBR] =====================================================",
        "[TGP-XBR] Upstream: TGP482/XboxXBERecomp @ "+info["upstream_commit"],
        "[TGP-XBR] XDK signatures: build 5849, entries="+str(len(signatures)),
        "[TGP-XBR] First xboxrecomp inventory="+str(len(entries))+" functions",
        "[TGP-XBR] LIVE: XInputOpen port=0 handle=1 PASS; 27,107,602 ticks",
        "[TGP-XBR] NEXT REAL DIRECT_FRONTIER: 0x002D52D4",
        "[TGP-XBR] WARNING: XBE kernel version 5849 does NOT prove XDK library version 5849",
        "[TGP-XBR] WARNING: EQUAL FUNCTION SIZE DOES NOT PROVE LIBRARY IDENTITY",
        "",
        "[TGP-XBR] XDK5849 XInputOpen: length=%d ret-pop=%s"%(
            signatures["XInputOpen"]["length"],signatures["XInputOpen"]["stack_pop"]),
        "[TGP-XBR] The original XBE D5272 has size=%d; independent signature scan is still required."%
            entries[0x002D5272]["size"],
        "[TGP-XBR] NEW D52D4=472 bytes: no near-length XPP symbol in this SDK's 5849 database.",
        "[TGP-XBR] TGP HLE has APIs without signatures; missing name is NOT missing code.",
        "",
    ]
    if actual is None:
        lines.append("[TGP-XBR] Independent codegen NOT YET RUN; no new-function claims.")
    else:
        r=info["independent_recomp"]
        lines.extend([
            "[TGP-XBR] Independent recompiler finished: %d functions"%r["functions"],
            "[TGP-XBR] Exact-address overlap: %d"%r["overlap"],
            "[TGP-XBR] TGP-only addresses: %d"%r["discovered_only_by_tgp"],
            "[TGP-XBR] xboxrecomp-only addresses: %d"%r["only_in_xboxrecomp"],
            "[TGP-XBR] TGP-only sample: "+", ".join(r["discovered_only_by_tgp_sample"][:20]),
            "",
        ])
    for x in info["important_functions"]:
        lines.append("[TGP-XBR] %s section=%s size=%d end=%s old_compile=%s"%
            (x["address"],x["section"],x["size"],x["end"],x["translated_in_old_pixel_batch"]))
        lines.append("    Calls: "+", ".join(x["static_callees"][:12]))
        near=[v for v in x["size_nearby_signatures"] if abs(v["delta"])<=16]
        if near:
            lines.append("    UNVERIFIED near-length signature candidates (within 16 bytes): "+
                "; ".join("%s=%d (delta %+d,ret=%s)"%
                    (v["name"],v["length"],v["delta"],v["stack_pop"]) for v in near))
        else:
            lines.append("    NO XDK5849 signature within 16 bytes; unknown identity.")
        lines.append("    Closest known signature by size (NOT identity): "+
            ("; ".join("%s=%d (delta %+d)"%
                (v["name"],v["length"],v["delta"])
                for v in x["size_nearby_signatures"][:2])))
    lines.append("")
    lines.append("[TGP-XBR] XDK5849 object layout REFERENCES ONLY; must verify against Mercenaries:")
    for k,v in info["xdk_layout"].items():
        lines.append("    "+k+"="+("unavailable" if v is None else "0x%X"%v))
    lines.extend([
        "",
        "[TGP-XBR] POLICY: metadata report only, no original game bytes/code in GitHub.",
        "[TGP-XBR] No XDK build, no Xbox run, no synthetic presentation calls."
    ])
    a.report.parent.mkdir(parents=True,exist_ok=True)
    a.report.write_text("\n".join(lines)+"\n",encoding="utf-8")
    a.json_out.parent.mkdir(parents=True,exist_ok=True)
    a.json_out.write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
    print("\n".join(lines))
    print("[TGP-XBR] REPORT="+str(a.report))
    print("[TGP-XBR] JSON="+str(a.json_out))

def main():
    parser=argparse.ArgumentParser()
    for field in ("sdk","recon_zip","report","json_out"):
        parser.add_argument("--"+field.replace("_","-"),type=Path,required=True)
    parser.add_argument("--mapping",type=Path)
    audit(parser.parse_args())

if __name__=="__main__":
    main()
