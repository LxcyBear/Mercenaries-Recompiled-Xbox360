#!/usr/bin/env python3
"""Source-only staged XPP 002D5272 / retail XInputOpen on native Xbox 360.

Hardware: D559B/D5579 success, next DIRECT caller=0023A3CE target=002D5272,
ticks=27107599, fault=0, display_calls=0. Preserve D559B parent exactly.
Only the retail-source-backed XInputOpen helper is accepted. No guest-source
material is published to GitHub. Real native XInputGetState, not a dummy handle.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
from pathlib import Path

MARKER="XPP-D5272-NATIVE-XINPUTOPEN-20261031"
PARENT="XPP-D559B-DEVICE-CHANGES-20261030"
TARGET=0x002D5272
RANGE_END=0x002D52C8
HELPER="recomp_xinput_open"
ORIGIN="recomp_0013.c"
HEADER='#include "translated_runtime.h"'
FENCE="phase4c_direct_frontier(0x002D5272u);"
CALL="sub_002D5272();"
BRIDGE="XPP-D5272-NATIVE-XINPUTOPEN-20261031"
SHARD=re.compile(r"translated_\d{3}\.cpp\Z")
DEFINITION=re.compile(
    r"(?m)^[ \t]*(static[ \t]+)?void[ \t]+(sub_[0-9A-Fa-f]{8})"
    r"[ \t]*\([ \t]*void[ \t]*\)\s*\{")
LABEL=re.compile(r"(?m)^[ \t]*loc_([0-9a-fA-F]{8})\s*:\s*;")
SUBCALL=re.compile(r"\b(sub_[0-9a-fA-F]{8})\s*\(\s*\)")
HELPERCALL=re.compile(r"\b(recomp_[A-Za-z_0-9]+)\s*\(")
NATIVE=r'''/* XPP-D5272-NATIVE-XINPUTOPEN-20261031; source-matched retail ABI */
static uint32_t recomp_xinput_open(uint32_t port)
{
    /* Upstream Mercenaries-Recompiled: a valid port has handle port+1. */
    if (port >= 4u)
        return 0u;
    XINPUT_STATE state;
    ZeroMemory(&state,sizeof(state));
    if (XInputGetState((DWORD)port,&state)!=ERROR_SUCCESS)
        return 0u;
    static unsigned xpp_open_calls=0u;
    if (++xpp_open_calls<=8u)
    {
        char line[128];
        sprintf(line,"XPP XINPUT native open: port=%u handle=%u",
            (unsigned)port,(unsigned)(port+1u));
        trace(line);
    }
    return port+1u;
}
'''

def sha(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()

def sha_text(data):
    return hashlib.sha256(data.encode("utf-8")).hexdigest()

def normalized_newline(text):
    if text.count("\r")!=text.count("\r\n"):
        raise ValueError("Unsupported mixed CRLF")
    return "\r\n" if "\r\n" in text else "\n"

def load(path,name):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:
        raise ValueError("Cannot load original user-local translation helper")
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def normalize_original(source,base):
    head=(r"(?m)^[ \t]*(?:static[ \t]+)?(?:__forceinline[ \t]+)?"
          r"void[ \t]+sub_002D5272[ \t]*\([ \t]*void[ \t]*\)\s*\{")
    hits=list(re.finditer(head,source))
    if len(hits)!=1:
        raise ValueError("Expected exactly one generated 002D5272 function header")
    m=hits[0]
    prefix=source[:m.start()]
    if re.sub(r"/\*.*?\*/|//[^\n]*","",prefix,flags=re.S).strip():
        raise ValueError("Unexpected executable prefix before original XPP function")
    clean=prefix+"void sub_002D5272(void)\n{"+source[m.end():]
    masked=base.mask_noncode(clean)
    if len(re.findall(r"\bRECOMP_TRACE_FUNC\(\s*0x002D5272u\s*\);",masked))!=1:
        raise ValueError("Original XPP trace anchor missing")
    if len(re.findall(r"\beax\s*=\s*recomp_xinput_open\s*\(",masked))!=1:
        raise ValueError("Retail XInputOpen EAX return helper mismatch; review original source")
    if len(re.findall(r"\brecomp_xinput_open\s*\(",masked))!=1:
        raise ValueError("Unexpected multiple XInputOpen helper sites")
    # The original translator's RET stack operations are preserved byte-for-byte;
    # never infer ESP cleanup from xboxrecomp ABI heuristics.
    if not re.search(r"\besp\s*(?:\+=|=)\s*[^;\n]+;\s*return;",masked):
        raise ValueError("Original translated XInputOpen guest ESP return shape not proven")
    body=[]
    entry_ticks=0
    for line in clean.splitlines():
        body.append(line.replace("__debugbreak()","PHASE4C_DEBUGBREAK()"))
        if re.fullmatch(r"\s*RECOMP_TRACE_FUNC\(\s*0x002D5272u\s*\);\s*",line):
            body.extend([
                "    PHASE4C_BUDGET_TICK(0x002D5272u);",
                "    {",
                "        static unsigned xpp_d5272_entries=0u;",
                "        if (++xpp_d5272_entries<=8u)",
                "        {",
                "            char msg[128];",
                '            sprintf(msg,"XPP D5272 ENTRY n=%u esp=%08X eax=%08X",',
                "                (unsigned)xpp_d5272_entries,(unsigned)esp,(unsigned)eax);",
                "            trace(msg);",
                "        }",
                "    }",
            ])
            entry_ticks+=1
        loc=re.match(r"^\s*loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$",line)
        if loc and int(loc.group(1),16)!=TARGET:
            body.append("    PHASE4C_BUDGET_TICK(0x%08Xu);"%int(loc.group(1),16))
    if entry_ticks!=1:
        raise ValueError("No exact original guest entry for D5272")
    translated="\n".join(body)+"\n"
    # Hard check that the original EAX assignment and guest ESP/ret survived.
    if not re.search(r"\beax\s*=\s*recomp_xinput_open\s*\(",translated):
        raise ValueError("Generated XInputOpen EAX return vanished")
    return translated,masked

def rewrite(text,is_host=False):
    count=text.count(FENCE)
    if not count:
        return text,0
    if not is_host and HEADER not in text:
        raise ValueError("Original source-caller TrueTU has no runtime header")
    nl=normalized_newline(text)
    prototype="void sub_002D5272(void);"
    if prototype not in text:
        if HEADER in text:
            text=text.replace(HEADER,HEADER+nl+prototype,1)
        else:
            text=prototype+nl+text
    text=text.replace(FENCE,CALL)
    if FENCE in text:
        raise ValueError("Hardware-observed frontier still fenced after stage")
    return text,count

def stage(args):
    for item in (args.shards,args.parent_main,args.parent_manifest,
                 args.generated,args.functions,args.emitter):
        if not item.exists():
            raise ValueError("Required already-generated original input missing: "+str(item))
    parent=json.loads(args.parent_manifest.read_text(encoding="utf-8-sig"))
    if (parent.get("marker")!=PARENT
        or parent.get("status")!="SOURCE_CLOSED_STAGED_NO_XDK"
        or parent.get("hardware_target")!="0x002D559B"
        or parent.get("native_input_backend")!="XPP-D559B-NATIVE-DEVICE-CHANGES-20261030"
        or parent.get("mmio_fences")!="UNCHANGED"
        or parent.get("hard_fences")!="UNCHANGED"
        or parent.get("guest_display_calls_injected") is not False
        or Path(parent.get("staged_directory","MISSING")).resolve()!=args.shards.resolve()
        or Path(parent.get("staged_main","MISSING")).resolve()!=args.parent_main.resolve()
        or sha(args.parent_main)!=parent.get("new_main_sha")):
        raise ValueError("Verified successful D559B parent manifest/host changed")
    files=sorted(p for p in args.shards.iterdir() if SHARD.fullmatch(p.name))
    headers=list(args.shards.glob("*.h"))
    if len(files)!=64 or not (args.shards/"translated_runtime.h").is_file():
        raise ValueError("Expected exactly 64 intact TrueTUs and shared header")
    for item in files+headers:
        expected=parent.get("new_owner_hashes",{}).get(
            item.name,parent.get("original_owner_hashes",{}).get(item.name))
        if not expected or sha(item)!=expected:
            raise ValueError("Original working D559B TrueTU hash drifted: "+item.name)
    previous={p.name:p.read_text(encoding="utf-8") for p in files}
    host=args.parent_main.read_text(encoding="utf-8")
    if (sum("XPP 002D559B ENTRY" in s for s in previous.values())!=1
        or sum("XPP D5574 ENTRY" in s for s in previous.values())!=1
        or sum("XPP-D559B-NATIVE-DEVICE-CHANGES-20261030" in s
               for s in previous.values())!=1
        or "K1S HALGETVECTOR44 ESI SLOT:" not in previous["translated_044.cpp"]
        or "P6DQ-R51-MM173-FRAME-20261029-A" not in host):
        raise ValueError("Hardware-proven native input, K1S or D3D host baseline missing")
    owner=parent.get("owner")
    if owner not in previous or previous[owner].count("#include <xtl.h>")!=1:
        raise ValueError("Previous native XInput owner with XDK header missing")
    if any(BRIDGE in text for text in previous.values()):
        raise ValueError("Already has a D5272 native XInputOpen bridge")
    original=load(args.emitter,"xpp_d5272_local_original")
    ranges,by_name=original.load_ranges(args.functions)
    generated=original.load_generated(args.generated,by_name)
    item=ranges.get(TARGET)
    entry=generated.get(TARGET)
    if not item or item["start"]!=TARGET or item["end"]!=RANGE_END:
        raise ValueError("XPP 002D5272 exact retail function range mismatch")
    if not entry or entry["file"]!=ORIGIN:
        raise ValueError("XPP 002D5272 user-local original generated body missing")
    src=entry["source"]
    body,masked=normalize_original(src,original)
    def pattern(va):
        return re.compile(r"(?m)^\s*(?:static\s+)?void\s+sub_%08X"%va
            +r"\s*\(\s*void\s*\)\s*\{")
    if any(pattern(TARGET).search(t) for t in [host]+list(previous.values())):
        raise ValueError("D5272 already defined, refusing duplicate compiled guest body")
    helper_pattern=re.compile(r"(?m)^\s*(?:static\s+)?uint32_t\s+recomp_xinput_open"
                              r"\s*\([^;{}]*\)\s*\{")
    if any(helper_pattern.search(t) for t in [host]+list(previous.values())):
        raise ValueError("XInputOpen helper exists in a compiled source already")
    compiled={}
    for file_name,text in previous.items():
        for m in DEFINITION.finditer(text):
            compiled[int(m.group(2),16)]=(file_name,bool(m.group(1)))
    for m in DEFINITION.finditer(host):
        compiled[int(m.group(2),16)]=("main.cpp",bool(m.group(1)))
    deps=sorted({int(m.group(1)[4:],16) for m in SUBCALL.finditer(masked)})
    unresolved=[a for a in deps if a not in compiled]
    cross_static=[a for a in deps if a in compiled and compiled[a][1]
                  and compiled[a][0]!=owner]
    helper_calls=sorted(set(HELPERCALL.findall(masked)))
    extra_helpers=[h for h in helper_calls if h!=HELPER]
    # Audit is always written BEFORE attempting to stage source.
    audit=[
        "[XPP-D5272] REAL HARDWARE: DIRECT 0023A3CE -> 002D5272",
        "Hardware ticks=27107599 fault=0 display_calls=0",
        "Retail upstream patch: XInputOpen; recomp_xinput_open(port) -> port+1 or 0",
        "Exact generated function=0x002D5272..0x002D52C8",
        "Local source file="+entry["file"],
        "Original local source sha256="+sha_text(src),
        "Original translated direct children="+",".join("0x%08X"%x for x in deps),
        "Uncompiled direct children="+",".join("0x%08X"%x for x in unresolved),
        "Cross-TU internal-linkage children="+",".join("0x%08X"%x for x in cross_static),
        "Recomp helpers="+",".join(helper_calls),
        "Extra helper review required="+",".join(extra_helpers),
        "Source-driven RET/ESP statements="+str(re.findall(
            r"\besp\s*(?:\+=|=)\s*[^;\n]+;",masked)),
        "Already compiled guest bodies="+str(len(compiled)),
        "XInput native backend: XInputGetState(real port) -> port+1 or 0",
        "SAFE: no guest display injection, no VP/MMIO relaxation.",
        "ORIGINAL GAME SOURCE EXCERPT IS USER-LOCAL ONLY, NOT IN GITHUB.",
        "",
    ]
    args.audit.parent.mkdir(parents=True,exist_ok=True)
    args.audit.write_text("\n".join(audit)+"\n",encoding="utf-8")
    args.private.parent.mkdir(parents=True,exist_ok=True)
    args.private.write_text(
        "PRIVATE ORIGINAL GENERATED 002D5272 SOURCE (DO NOT COMMIT TO GITHUB)\n\n"
        +src,encoding="utf-8")
    if unresolved or cross_static or extra_helpers:
        raise ValueError(
            "D5272 needs caller/dependency ABI review. Upload local audit and private excerpt. "
            "No XDK build was attempted.")
    # A no-extra-helper exact generated body is source-closed here: only the
    # proven native XInputOpen helper is new, so keep the other 63 TUs verbatim.
    n=normalized_newline(previous[owner])
    if previous[owner].count("#include <xtl.h>"+n)!=1:
        raise ValueError("Native XInput owner insertion anchor not unique")
    expanded=previous[owner].replace(
        "#include <xtl.h>"+n,
        "#include <xtl.h>"+n+NATIVE.replace("\n",n)+n,1)
    expanded=expanded.rstrip("\r\n")+n+n+(
        "/* "+MARKER+" original guest source 0x002D5272 */"+n
        +body.replace("\n",n))
    altered={}
    callsites=0
    for name,text in previous.items():
        latest=expanded if name==owner else text
        latest,count=rewrite(latest)
        callsites+=count
        if latest!=text:
            altered[name]=latest.encode("utf-8")
    new_main,host_calls=rewrite(host,is_host=True)
    callsites+=host_calls
    if callsites<1 or not altered or len(altered)>12:
        raise ValueError("D5272 genuine frontier absent or changed too many TUs")
    if sum("XPP D5272 ENTRY" in v.decode("utf-8") for v in altered.values())!=1:
        raise ValueError("Original D5272 guest entry instrumentation duplicate/missing")
    if sum(BRIDGE in v.decode("utf-8") for v in altered.values())!=1:
        raise ValueError("Native XInputOpen is not unique")
    if args.out.resolve()==args.shards.resolve() or args.out_main.resolve()==args.parent_main.resolve():
        raise ValueError("Refusing to overwrite working D559B source")
    expected={p.name:altered.get(p.name,p.read_bytes()) for p in files+headers}
    args.out.mkdir(parents=True,exist_ok=True)
    if {p.name for p in args.out.iterdir()} not in (set(),set(expected)):
        raise ValueError("Previous staged D5272 file inventory differs")
    for name,content in expected.items():
        destination=args.out/name
        if destination.exists() and destination.read_bytes()!=content:
            raise ValueError("Existing D5272 staged source hash differs: "+name)
        if not destination.exists():
            destination.write_bytes(content)
    main_bytes=new_main.encode("utf-8")
    args.out_main.parent.mkdir(parents=True,exist_ok=True)
    if args.out_main.exists() and args.out_main.read_bytes()!=main_bytes:
        raise ValueError("Prior D5272 main.cpp stage differs")
    if not args.out_main.exists():
        args.out_main.write_bytes(main_bytes)
    manifest={
        "marker":MARKER,"status":"SOURCE_CLOSED_STAGED_NO_XDK",
        "hardware_target":"0x002D5272","hardware_seed_ticks":27107599,
        "native_bridge":BRIDGE,"native_real_input":True,
        "guest_display_calls_injected":False,
        "mmio_fences":"UNCHANGED","hard_fences":"UNCHANGED",
        "function_original_sha256":sha_text(src),
        "original_file":entry["file"],
        "original_stack_statements":re.findall(
            r"\besp\s*(?:\+=|=)\s*[^;\n]+;",masked),
        "direct_callees":["0x%08X"%a for a in deps],
        "modified_true_tus":sorted(altered),
        "original_owner_hashes":{p.name:sha(p) for p in files+headers},
        "new_owner_hashes":{n:hashlib.sha256(c).hexdigest() for n,c in altered.items()},
        "staged_directory":str(args.out.resolve()),
        "staged_main":str(args.out_main.resolve()),
        "new_main_sha":hashlib.sha256(main_bytes).hexdigest(),
        "caller_direct_replacements":callsites,
        "previous_manifest":str(args.parent_manifest),
    }
    args.manifest.parent.mkdir(parents=True,exist_ok=True)
    args.manifest.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    print("[XPP-D5272] SOURCE CLOSED: original XInputOpen + real 360 port bridge")
    print("[XPP-D5272] Original EAX return and ESP cleanup preserved")
    print("[XPP-D5272] Direct callsites=%d changed TrueTUs=%s"%
          (callsites,",".join(sorted(altered))))
    print("[XPP-D5272] NO XDK BUILD staged; original source remains LOCAL")


def synthetic():
    assert TARGET==0x002D5272
    assert RANGE_END-TARGET==86
    assert "XInputGetState((DWORD)port,&state)!=ERROR_SUCCESS" in NATIVE
    assert "port >= 4u" in NATIVE and "return port+1u;" in NATIVE
    assert "return 0u;" in NATIVE
    for nl in ("\n","\r\n"):
        input_src=(HEADER+nl+"void caller(void)"+nl+
                   "{ "+FENCE+" }"+nl)
        output,count=rewrite(input_src)
        assert count==1 and CALL in output and FENCE not in output
        assert output.count("void sub_002D5272(void);")==1
        out2,c2=rewrite(output)
        assert c2==0 and out2==output
        wrong=input_src.replace(FENCE,"phase4c_direct_frontier(0x002D5273u);")
        unchanged,c3=rewrite(wrong)
        assert c3==0 and unchanged==wrong
    print("[XPP-D5272] SYNTHETIC PASS: source boundary, native real input, exact fence rewrite")


def main():
    parser=argparse.ArgumentParser()
    parser.add_argument("--self-test",action="store_true")
    for opt in ("shards","parent_main","parent_manifest","generated",
                "functions","emitter","out","out_main","manifest","audit","private"):
        parser.add_argument("--"+opt.replace("_","-"),type=Path)
    args=parser.parse_args()
    if args.self_test:
        synthetic()
        return
    for opt in ("shards","parent_main","parent_manifest","generated",
                "functions","emitter","out","out_main","manifest","audit","private"):
        if getattr(args,opt) is None:
            parser.error("--"+opt.replace("_","-")+" is required")
    try:
        stage(args)
    except ValueError as error:
        print("[XPP-D5272] NO XDK: "+str(error),flush=True)
        if args.audit.exists():
            print("[XPP-D5272] METADATA AUDIT: "+str(args.audit),flush=True)
        if args.private.exists():
            print("[XPP-D5272] PRIVATE SOURCE: "+str(args.private),flush=True)
        raise SystemExit(3)

if __name__=="__main__":
    main()
