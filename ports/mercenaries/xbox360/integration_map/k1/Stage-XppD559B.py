#!/usr/bin/env python3
"""Stage source-fingerprinted XPP D559B and D5579 from user-local originals.

NEXT Xbox result: D5574 native XInput PASS; D559B DIRECT at 27,107,590.
Copies the known-good D5574 64-TrueTU batch; patches only exact guest
direct-frontier callsites, preserves every original XPP body and return, and
never commits original game content or changes guest display/MMIO behavior.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

TAG="XPP-D559B-DEVICE-CHANGES-20261030"
PARENT="XPP-D5574-DIRECT-CLOSURE-20261030"
ROOT=0x002D559B
SECOND=0x002D5579
VAs=(ROOT,SECOND)
SOURCE_SHA={
    ROOT:"aabfce6d989330cb54fd9c282dc4d48ca2b74d9529c03f28adb87cc67e183dde",
    SECOND:"91e8bbfd788397209415b8afedbf4a7b28fb63382eb532a3e18fb9fba439085b",
}
END={ROOT:0x002D5608,SECOND:0x002D559B}
SHAPE={
 ROOT:(r"eax\s*=\s*recomp_xinput_get_device_changes\(\s*"
       r"GUEST_READ32\(esp\s*\+\s*8u\)\s*,\s*"
       r"GUEST_READ32\(esp\s*\+\s*12u\)\s*\);\s*"
       r"esp\s*\+=\s*16u;\s*return;"),
 SECOND:(r"eax\s*=\s*recomp_xinput_get_devices\(\s*\);\s*"
         r"esp\s*\+=\s*8u;\s*return;"),
}
HEADER='#include "translated_runtime.h"'
BRIDGE="XPP-D559B-NATIVE-DEVICE-CHANGES-20261030"
SHARD=re.compile(r"translated_\d{3}\.cpp\Z")
# Native XDK wrapper mirrors original recomp_manual.c device-change semantics.
# Four real pad state probes; persistent previous mask; input/output pointers
# strictly fenced through the existing guest memory-access machinery.
NATIVE=r'''/* XPP-D559B-NATIVE-DEVICE-CHANGES-20261030: real native XInput */
static uint32_t xpp_native_previous_device_mask=0u;
static uint32_t xpp_native_device_scan(void)
{
    uint32_t mask=0u;
    for (DWORD port=0u; port<4u; ++port)
    {
        XINPUT_STATE state;
        ZeroMemory(&state,sizeof(state));
        if (XInputGetState(port,&state)==ERROR_SUCCESS)
            mask|=(1u<<port);
    }
    return mask;
}
static uint32_t recomp_xinput_get_devices(void)
{
    const uint32_t current=xpp_native_device_scan();
    xpp_native_previous_device_mask=current;
    return current;
}
static uint32_t recomp_xinput_get_device_changes(uint32_t insertions_address,
                                                 uint32_t removals_address)
{
    const uint32_t previous=xpp_native_previous_device_mask;
    const uint32_t current=xpp_native_device_scan();
    const uint32_t inserted=current & ~previous;
    const uint32_t removed=previous & ~current;
    if (insertions_address>=0x00010000u && insertions_address<=0x03FFFFFCu)
        GUEST_WRITE32(insertions_address,inserted);
    if (removals_address>=0x00010000u && removals_address<=0x03FFFFFCu)
        GUEST_WRITE32(removals_address,removed);
    xpp_native_previous_device_mask=current;
    static uint32_t logs=0u;
    if (++logs<=8u)
    {
        char line[192];
        sprintf(line,"XPP XINPUT changes prev=%08X cur=%08X inserted=%08X removed=%08X",
                previous,current,inserted,removed);
        trace(line);
    }
    return (inserted|removed)!=0u ? 1u : 0u;
}
'''

def sha(p):
    return hashlib.sha256(p.read_bytes()).hexdigest()

def digest(s):
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def newline(s):
    if s.count("\r")!=s.count("\r\n"):
        raise ValueError("Mixed CRLF in original TrueTU")
    return "\r\n" if "\r\n" in s else "\n"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if not spec or not spec.loader:
        raise ValueError("Local original translator helper not available")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def normalized_original(va,original,base):
    if digest(original)!=SOURCE_SHA[va]:
        raise ValueError("Original XPP function SHA changed: 0x%08X"%va)
    header=(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_%08X"%va
           +r"[ \t]*\([ \t]*void[ \t]*\)\s*\{")
    matches=list(re.finditer(header,original))
    if len(matches)!=1:
        raise ValueError("Original XPP function header ambiguous")
    match=matches[0]
    prefix=original[:match.start()]
    if re.sub(r"/\*.*?\*/|//[^\n]*","",prefix,flags=re.S).strip():
        raise ValueError("Unexpected pre-function source statement")
    canonical=prefix+"void sub_%08X(void)\n{"%va+original[match.end():]
    masked=base.mask_noncode(canonical)
    shape=(r"\s*void\s+sub_%08X\s*\(void\)\s*\{\s*"%va
           +r"RECOMP_TRACE_FUNC\(0x%08Xu\);\s*"%va
           +SHAPE[va]+r"\s*\}\s*")
    if not re.fullmatch(shape,masked):
        raise ValueError("Unverified original XPP EAX/ESP and pointer ABI: %08X"%va)
    result=[]
    sites=0
    for line in canonical.splitlines():
        result.append(line)
        if re.fullmatch(r"\s*RECOMP_TRACE_FUNC\(0x%08Xu\);\s*"%va,line):
            result.extend([
                "    PHASE4C_BUDGET_TICK(0x%08Xu);"%va,
                "    {",
                "        static uint32_t xpp_entries=0u;",
                "        if (++xpp_entries<=8u)",
                "        {",
                "            char msg[128];",
                '            sprintf(msg,"XPP %08X ENTRY n=%%u esp=%%08X",'%va,
                "                    (unsigned)xpp_entries,(unsigned)esp);",
                "            trace(msg);",
                "        }",
                "    }",
            ])
            sites+=1
    translated="\n".join(result)+"\n"
    if sites!=1 or not re.search(SHAPE[va],base.mask_noncode(translated)):
        raise ValueError("Guest return register/stack was altered")
    return translated

def rewrite(text,vas,is_host=False):
    counts={}
    for va in vas:
        fence="phase4c_direct_frontier(0x%08Xu);"%va
        n=text.count(fence)
        counts["0x%08X"%va]=n
        if not n:
            continue
        if not is_host and HEADER not in text:
            raise ValueError("Translated caller lacks runtime header")
        proto="void sub_%08X(void);"%va
        if proto not in text:
            if HEADER in text:
                text=text.replace(HEADER,HEADER+newline(text)+proto,1)
            else:
                text=proto+newline(text)+text
        text=text.replace(fence,"sub_%08X();"%va)
        if fence in text:
            raise ValueError("Unreplaced original DIRECT frontier")
    return text,counts

def stage(a):
    for p in (a.shards,a.parent_manifest,a.parent_main,a.generated,a.functions,a.emitter):
        if not p.exists():
            raise ValueError("Missing user-local generated source: "+str(p))
    parent=json.loads(a.parent_manifest.read_text(encoding="utf-8-sig"))
    if (parent.get("marker")!=PARENT
        or parent.get("status")!="SOURCE_CLOSED_STAGED_NO_XDK"
        or parent.get("native_xinput_init")!="XINPUTGETSTATE_4PORTS_REAL_HARDWARE"
        or parent.get("guest_display_calls_injected") is not False
        or parent.get("mmio_fences")!="UNCHANGED"
        or parent.get("hard_fences")!="UNCHANGED"
        or Path(parent.get("staged_directory","MISSING")).resolve()!=a.shards.resolve()
        or Path(parent.get("staged_main","MISSING")).resolve()!=a.parent_main.resolve()
        or sha(a.parent_main)!=parent.get("new_main_sha")):
        raise ValueError("Verified D5574 hardware source stage/provenance mismatch")
    files=sorted(p for p in a.shards.iterdir() if SHARD.fullmatch(p.name))
    headers=list(a.shards.glob("*.h"))
    if len(files)!=64 or not (a.shards/"translated_runtime.h").is_file():
        raise ValueError("Known-good D5574 stage must contain 64 TrueTUs and runtime header")
    for p in files+headers:
        expected=parent.get("new_owner_hashes",{}).get(
            p.name,parent.get("original_owner_hashes",{}).get(p.name))
        if not expected or sha(p)!=expected:
            raise ValueError("D5574 TrueTU changed unexpectedly: "+p.name)
    sources={p.name:p.read_text(encoding="utf-8") for p in files}
    host=a.parent_main.read_text(encoding="utf-8")
    if (sum("XPP D5574 ENTRY" in s for s in sources.values())!=1
        or sum("XPP-D5574-NATIVE-XINPUT-INIT-20261030" in s for s in sources.values())!=1
        or "K1S HALGETVECTOR44 ESI SLOT:" not in sources["translated_044.cpp"]
        or "P6DQ-R51-MM173-FRAME-20261029-A" not in host):
        raise ValueError("Original XPP init, K1S or host build identity differs")
    owner=parent.get("owner")
    if owner not in sources:
        raise ValueError("Original XInput helper owner is unknown")
    if sources[owner].count("#include <xtl.h>")!=1:
        raise ValueError("Original owner's native XInput include not unique")
    if any(BRIDGE in s for s in sources.values()):
        raise ValueError("XPP device-change helper already present")
    base=load(a.emitter,"xpp559b_original_source")
    ranges,names=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated,names)
    bodies={}
    for va in VAs:
        row=ranges.get(va)
        source=generated.get(va)
        if not row or row["start"]!=va or row["end"]!=END[va]:
            raise ValueError("Verified retail XPP range differs: %08X"%va)
        if not source or source["file"]!="recomp_0013.c":
            raise ValueError("Original XPP generated body unavailable")
        bodies[va]=normalized_original(va,source["source"],base)
        signature=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_%08X"%va
                             +r"\s*\(void\)\s*\{")
        if any(signature.search(t) for t in sources.values()):
            raise ValueError("Duplicate original XPP function already compiled")
    for helper in ("recomp_xinput_get_devices","recomp_xinput_get_device_changes"):
        definition=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?"
            r"(?:uint32_t|DWORD|unsigned)[ \t]+"+helper+r"\s*\([^;{}]*\)\s*\{")
        if any(definition.search(s) for s in list(sources.values())+[host]):
            raise ValueError("Conflicting native input helper "+helper)
    n=newline(sources[owner])
    owned=sources[owner].replace(
        "#include <xtl.h>"+n,
        "#include <xtl.h>"+n+NATIVE.replace("\n",n)+n,1)
    for va in VAs:
        owned=(owned.rstrip("\r\n")+n+n
               +"/* "+TAG+" local-source 0x%08X */"%va+n
               +bodies[va].replace("\n",n))
    altered={}
    calls=0
    for name,text in sources.items():
        candidate=owned if name==owner else text
        candidate,counts=rewrite(candidate,VAs)
        calls+=counts["0x%08X"%ROOT]
        if candidate!=text:
            altered[name]=candidate.encode("utf-8")
    newhost,hostcounts=rewrite(host,VAs,is_host=True)
    calls+=hostcounts["0x%08X"%ROOT]
    if calls<1 or not altered or len(altered)>12:
        raise ValueError("No exact D559B live DIRECT frontier or excessive TU changes")
    if sum("XPP 002D559B ENTRY" in b.decode("utf-8") for b in altered.values())!=1:
        raise ValueError("Original D559B traced entry not unique")
    if sum(BRIDGE in b.decode("utf-8") for b in altered.values())!=1:
        raise ValueError("Native XInput device-change backend missing or duplicated")
    if a.out.resolve()==a.shards.resolve() or a.out_main.resolve()==a.parent_main.resolve():
        raise ValueError("Would overwrite proven D5574 stage")
    expected={p.name:altered.get(p.name,p.read_bytes()) for p in files+headers}
    a.out.mkdir(parents=True,exist_ok=True)
    if {p.name for p in a.out.iterdir()} not in (set(),set(expected)):
        raise ValueError("Existing D559B stage has incompatible file inventory")
    for name,data in expected.items():
        target=a.out/name
        if target.exists() and target.read_bytes()!=data:
            raise ValueError("Existing D559B stage differs; refusing overwrite")
        if not target.exists():
            target.write_bytes(data)
    outbytes=newhost.encode("utf-8")
    a.out_main.parent.mkdir(parents=True,exist_ok=True)
    if a.out_main.exists() and a.out_main.read_bytes()!=outbytes:
        raise ValueError("Previous D559B main.cpp differs")
    if not a.out_main.exists():
        a.out_main.write_bytes(outbytes)
    info={
        "marker":TAG,"status":"SOURCE_CLOSED_STAGED_NO_XDK",
        "hardware_target":"0x002D559B","hardware_seed_ticks":27107590,
        "previous_manifest":str(a.parent_manifest),
        "staged_directory":str(a.out.resolve()),"staged_main":str(a.out_main.resolve()),
        "owner":owner,"new_guest_bodies":["0x%08X"%v for v in VAs],
        "changed_true_tus":sorted(altered),"frontier_callsite_patches":calls,
        "original_owner_hashes":{p.name:sha(p) for p in files+headers},
        "new_owner_hashes":{k:hashlib.sha256(v).hexdigest() for k,v in altered.items()},
        "new_main_sha":hashlib.sha256(outbytes).hexdigest(),
        "source_sha256":{"0x%08X"%v:SOURCE_SHA[v] for v in VAs},
        "native_input_backend":BRIDGE,
        "guest_display_calls_injected":False,
        "mmio_fences":"UNCHANGED","hard_fences":"UNCHANGED",
    }
    a.manifest.parent.mkdir(parents=True,exist_ok=True)
    a.manifest.write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
    print("[XPP-D559B] ORIGINAL SOURCE PASS: D559B EAX/+16 and D5579 EAX/+8")
    print("[XPP-D559B] REAL XINPUT: 4-port device scan, persistent masks, fenced writes")
    print("[XPP-D559B] Direct callsites="+str(calls)+" changed TrueTUs="+",".join(sorted(altered)))
    print("[XPP-D559B] NO XDK BUILD; no MMIO relaxation; manifest="+str(a.manifest))

def main():
    p=argparse.ArgumentParser()
    for arg in ("shards","parent_manifest","parent_main","generated",
                "functions","emitter","out","out_main","manifest"):
        p.add_argument("--"+arg.replace("_","-"),required=True,type=Path)
    stage(p.parse_args())

if __name__=="__main__":
    main()
