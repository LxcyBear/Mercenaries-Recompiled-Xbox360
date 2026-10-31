#!/usr/bin/env python3
"""Stage the EXACT post-pixel-batch XPP direct frontier, only if source-closed.

Hardware: 27,107,567 ticks, caller 0023A3CE, DIRECT_FRONTIER 002D5574,
fault=0, XACT 64-entry pass, display_calls=0. No fake guest hardware.
The generated XPP bodies and all resulting TrueTUs stay LOCAL under build/.
This never publishes retail XBE bytes, relaxes VP/MMIO fences or edits the
indirect/ITAIL dispatcher. A failed source guard generates a useful report.
"""
from __future__ import annotations

import argparse
import collections
import hashlib
import importlib.util
import json
import re
import shutil
from pathlib import Path

TARGET=0x002D5574
NAME="sub_002D5574"
XPP_FIRST=0x002D4300
XPP_END=0x002DBCC8
MARKER="XPP-D5574-DIRECT-CLOSURE-20261030"
PARENT="PIXEL-A3A5A-DIRECT-APU-20261030"
FENCE="phase4c_direct_frontier(0x002D5574u);"
CALL="sub_002D5574();"
HEADER='#include "translated_runtime.h"'
SHARD=re.compile(r"translated_\d{3}\.cpp$")
FUNC=re.compile(r"(?m)^\s*(static\s+)?void\s+(sub_[0-9A-Fa-f]{8})"
                r"\s*\(\s*void\s*\)\s*\{")
LABEL=re.compile(r"^(\s*)loc_([0-9A-Fa-f]{8})\s*:\s*;\s*$")
DIRECT=re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(\s*\)")
RET=re.compile(r"esp\s*(?:\+=|=)\s*[^;\n]+;\s*return;\s*/\*\s*ret\s+\d+\s*\*/")
PROTOTYPE="void sub_002D5574(void);"

def sha_bytes(v:bytes)->str:
    return hashlib.sha256(v).hexdigest()

def sha(p:Path)->str:
    return sha_bytes(p.read_bytes())

def load_tool(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:
        raise ValueError("No original translator helper at "+str(path))
    mod=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod

def newline(text:str)->str:
    cr=text.count("\r\n")
    if text.count("\r")!=cr:
        raise ValueError("Mixed source line endings")
    return "\r\n" if cr else "\n"

def compiled_defs(sources:dict[str,str])->dict[str,tuple[str,bool]]:
    result={}
    for filename,text in sources.items():
        for m in FUNC.finditer(text):
            key=m.group(2).upper()
            if key in result:
                raise ValueError("Duplicate existing TrueTU function body "+key)
            result[key]=(filename,bool(m.group(1)))
    return result

def direct_calls(src:str,base)->list[str]:
    masked=base.mask_noncode(src)
    return sorted(set(s.upper() for s in DIRECT.findall(masked)))

def normalize_generated_header(src:str,va:int)->str:
    """Use the source loader's accepted header syntax; preserve the guest body.

    The original generated function may be static and/or __forceinline. These
    are C/C++ linkage/codegen qualifiers, not guest x86 stack semantics.
    The new function is a cross-TU direct-call target, so emit one extern-
    linkable definition, exactly void sub_XXXXXXXX(void), while preserving the
    entire original body and protecting the source provenance in the report.
    Unsupported return types, arguments, attributes, or duplicate signatures
    remain hard stops. Do NOT substitute an inferred jump or ret.
    """
    name="sub_%08X"%va
    header=(r"^\\s*(?:static\\s+)?(?:__forceinline\\s+)?void\\s+"
            +re.escape(name)+r"\\s*\\(\\s*void\\s*\\)\\s*\\{")
    match=re.match(header,src)
    if not match:
        first=src.splitlines()[0][:140] if src.splitlines() else "<EMPTY>"
        raise ValueError(
            "Unsupported original generated signature for %s: %r"%(name,first))
    canonical="void "+name+"(void)\\n{"
    normalized=canonical+src[match.end():]
    if normalized.count("void "+name+"(void)")!=1:
        raise ValueError("Duplicate source symbol declaration: "+name)
    return normalized


def source_prelude(src:str,va:int,base)->tuple[str,int]:
    name="sub_%08X"%va
    src=normalize_generated_header(src,va)
    if src.count("RECOMP_TRACE_FUNC(")!=1:
        raise ValueError("Original generated trace count differs: "+name)
    if "#include" in src:
        raise ValueError("Unexpected external include in generated guest function")
    out=[]
    count=0
    entry=0
    for line in src.splitlines():
        out.append(line.replace("__debugbreak()","PHASE4C_DEBUGBREAK()"))
        label=LABEL.fullmatch(line)
        if label:
            addr=int(label.group(2),16)
            count+=1
            out.append(label.group(1)+"    PHASE4C_BUDGET_TICK(0x%08Xu);"%addr)
            if addr==va:
                entry+=1
                if va==TARGET:
                    out.extend([
                        "    {",
                        "        static uint32_t xpp_d5574_entries=0u;",
                        "        ++xpp_d5574_entries;",
                        "        if (xpp_d5574_entries<=4u)",
                        "        {",
                        "            char xpp_d5574_line[192];",
                        '            sprintf(xpp_d5574_line,"XPP D5574 ENTRY n=%u esp=%08X ecx=%08X",',
                        "               (unsigned)xpp_d5574_entries,(unsigned)esp,(unsigned)ecx);",
                        "            trace(xpp_d5574_line);",
                        "        }",
                        "    }",
                    ])
    if entry!=1 or count<1:
        raise ValueError("Original exact entry label missing or duplicate: "+name)
    if RET.findall(src) and len(RET.findall(src))!=len(RET.findall("\n".join(out))):
        raise ValueError("Guest stack-return bytes changed unexpectedly")
    return "\n".join(out)+"\n",count

def patch_direct(text:str,decls:list[str],include_tag:bool)->tuple[str,int]:
    n=text.count(FENCE)
    if not n:
        return text,0
    if HEADER not in text:
        raise ValueError("Caller TU missing existing shared runtime include")
    nl=newline(text)
    declaration="\n".join("void "+s+"(void);" for s in decls
                           if ("void "+s+"(void);") not in text)
    modified=text.replace(FENCE,CALL)
    if declaration:
        modified=modified.replace(HEADER,HEADER+nl+declaration.replace("\n",nl),1)
    if n != modified.count(CALL)-text.count(CALL):
        raise ValueError("Exact original DIRECT_FRONTIER callsite rewrite failed")
    return modified,n

def patch_host(text:str)->tuple[str,int]:
    # Existing K1C host may not own a packed lookup. Preserve it verbatim.
    n=text.count(FENCE)
    if not n:
        return text,0
    if "P6DQ-R51-MM173-FRAME-20261029-A" not in text:
        raise ValueError("Host build identity changed from working pixel batch")
    if FUNC.search(text) and any(m.group(2).upper()==NAME.upper() for m in FUNC.finditer(text)):
        raise ValueError("Host unexpectedly already defines XPP target")
    proto=PROTOTYPE
    nl=newline(text)
    if proto not in text:
        text=proto+nl+text
    changed=text.replace(FENCE,CALL)
    if changed.count(FENCE):
        raise ValueError("Remaining unfixed direct XPP caller")
    return changed,n

def add_guest_bodies(owner_text:str,bodies:dict[int,str],base,compiled:dict,
                     owner_name:str)->str:
    if HEADER not in owner_text:
        raise ValueError("Chosen TrueTU lacks shared runtime header")
    nl=newline(owner_text)
    names={"sub_%08X"%x for x in bodies}
    for name in names:
        if name.upper() in compiled:
            raise ValueError("A generated guest function already defined: "+name)
    # Keep the shared header untouched to avoid 64-TU full recompilation.
    prototypes=set(names)
    for va,src in bodies.items():
        for name in direct_calls(src,base):
            if name in compiled:
                where,static=compiled[name]
                if static and where!=owner_name:
                    raise ValueError("Cross-TU callee has internal linkage: "+name)
                # A local compiled definition is already visible above the
                # appended original bodies, and may be static. Adding an
                # unconditional extern would break C++ linkage.
                if where==owner_name:
                    continue
            prototypes.add("sub_"+name[4:])
    # Every original generated direct call must have a real C++ declaration.
    declarations=[]
    for name in sorted(prototypes):
        p="void "+name+"(void);"
        if p not in owner_text:
            declarations.append(p)
    expanded=owner_text
    if declarations:
        expanded=expanded.replace(HEADER,HEADER+nl+nl.join(declarations),1)
    for va in sorted(bodies):
        body,labels=source_prelude(bodies[va],va,base)
        expanded=expanded.rstrip("\r\n")+nl+nl+(
            "/* "+MARKER+" source-proven original guest "+f"0x{va:08X}"+" */"
            +nl+body.replace("\n",nl))
    return expanded

def report_lines(info:dict,generated:dict,closure:list[int])->str:
    lines=[
        "XPP D5574 - SOURCE/ABI FRONTIER AUDIT, NO RETAIL BYTES COMMITTED",
        "Hardware source: DIRECT_FRONTIER caller=0023A3CE target=002D5574",
        "Hardware last record: ticks=27107567, fault=0, display_calls=0",
        "Preserve working A3A5A path and K1S four-byte ESI correction.",
        "Source-derived decision: "+info["status"],
        "Reason: "+info.get("reason","none"),
        "Existing direct callers: "+str(info.get("caller_sites","UNKNOWN")),
        "Closure size: "+str(len(closure)),
        "Unknown helpers: "+", ".join(info.get("unknown_helpers",[])),
        "Missing generated callees: "+", ".join(info.get("missing_callees",[])),
        "Origin file: "+str(info.get("original_file","UNAVAILABLE")),
        "Source SHA256: "+str(info.get("source_sha256","UNAVAILABLE")),
        "Selected TrueTU owner: "+str(info.get("owner","UNDECIDED")),
        "",
        "EXACT SOURCE EXCERPTS (LOCAL ONLY; DO NOT COMMIT THIS REPORT):",
    ]
    for va in closure[:24]:
        row=generated.get(va)
        if row is None:
            continue
        body=row["source"]
        lines.extend([
            "",
            f"== sub_{va:08X} from {row['file']} ==",
            f"Body SHA256={sha_bytes(body.encode('utf-8'))} lines={len(body.splitlines())}",
            "Direct original callees: "+", ".join(info.get("deps",{}).get(
                f"0x{va:08X}",[])),
        ])
        for n,line in enumerate(body.splitlines()[:400],1):
            lines.append(f"{n:4d} {line}")
        if len(body.splitlines())>400:
            lines.append(f"... {len(body.splitlines())-400} additional source lines omitted")
    return "\n".join(lines)+"\n"

def stage(a:argparse.Namespace)->dict:
    baseline=a.shards.resolve()
    mainfile=a.main.resolve()
    dest=a.out.resolve()
    outmain=a.out_main.resolve()
    evidence=a.report.resolve()
    manifestfile=a.manifest.resolve()
    for path in (baseline,mainfile,a.functions,a.emitter,a.generated_root,
                 manifestfile):
        if not path.exists():
            raise ValueError("Required original local source missing: "+str(path))
    if dest in baseline.parents or baseline in dest.parents or dest==baseline:
        raise ValueError("Cannot overwrite the working Pixel A3A5A TrueTUs")
    if outmain==mainfile or outmain in baseline.parents or outmain in dest.parents:
        raise ValueError("Cannot overwrite working host main or TrueTUs")
    parent=json.loads(manifestfile.read_text(encoding="utf-8-sig"))
    if (parent.get("marker")!=PARENT or parent.get("translated_shards")!=64
        or parent.get("preserved_k1s_esi_fix") is not True
        or parent.get("guest_display_call_injected") is not False
        or parent.get("guest_memory_fences")!="UNCHANGED"
        or parent.get("mmio_fences")!="UNCHANGED"
        or Path(parent.get("staged_shards","MISSING")).resolve()!=baseline
        or Path(parent.get("staged_main","MISSING")).resolve()!=mainfile):
        raise ValueError("Working PIXEL / K1S source manifest mismatch")
    files=sorted(p for p in baseline.iterdir() if SHARD.fullmatch(p.name))
    headers=sorted(baseline.glob("*.h"))
    if len(files)!=64 or not (baseline/"translated_runtime.h").is_file():
        raise ValueError("Expected exact 64 working PIXEL TrueTUs and unchanged header")
    for p in files+headers:
        expected=parent.get("new_owner_hashes",{}).get(
            p.name,parent.get("original_owner_hashes",{}).get(p.name))
        if not expected or sha(p)!=expected:
            raise ValueError("Working PIXEL TrueTU provenance hash changed: "+p.name)
    if "K1S HALGETVECTOR44 ESI SLOT:" not in (
        baseline/"translated_044.cpp").read_text(encoding="utf-8"):
        raise ValueError("Verified K1S stack fix missing from PIXEL baseline")
    if sum("PIXEL A3A5A ENTRY" in p.read_text(encoding="utf-8")
           for p in files)!=1:
        raise ValueError("Compiled PIXEL batch function missing or duplicated")
    main=mainfile.read_text(encoding="utf-8")
    text_by_file={p.name:p.read_text(encoding="utf-8") for p in files}
    compiled=compiled_defs({**text_by_file,"main.cpp":main})
    base=load_tool(a.emitter,"xpp_original_generated")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated_root,by_name)
    start=by_va.get(TARGET)
    info={
        "marker":MARKER,"status":"BLOCKED_SOURCE_REVIEW",
        "hardware_target":"0x002D5574","previous_ticks":27107567,
        "caller_sites":0,"unknown_helpers":[],"missing_callees":[],
        "deps":{},"source_sha256":None,"original_file":None,
        "guest_display_calls_injected":False,"mmio_fences":"UNCHANGED",
        "hard_fences":"UNCHANGED","modified_true_tus":[],
    }
    closure=[]
    try:
        if not start or start["start"]!=TARGET or not (
            XPP_FIRST<=TARGET<XPP_END):
            raise ValueError("Target is not an exact known XPP function start")
        if TARGET not in generated:
            raise ValueError("Target has no original generated complete function")
        root=generated[TARGET]
        info["original_file"]=root["file"]
        info["source_sha256"]=sha(a.generated_root/root["file"])
        if NAME.upper() in compiled:
            raise ValueError("Original XPP function already has a compiled body; inspect routing")
        # Static source roots / other guest calls may be exact only.
        if "P6DQ-R51-MM173-FRAME-20261029-A" not in main:
            raise ValueError("Host P6DQ startup tag differs from proven run")
        n_main=main.count(FENCE)
        caller_files={name:text.count(FENCE) for name,text in text_by_file.items()
                      if FENCE in text}
        info["caller_sites"]=n_main+sum(caller_files.values())
        info["caller_files"]=caller_files
        info["caller_main"]=n_main
        if info["caller_sites"]<1:
            raise ValueError("No literal hardware-observed DIRECT_FRONTIER callsite in working PIXEL source")
        if len(caller_files)>12:
            raise ValueError("Too many candidate TrueTUs for one incremental build")
        provided=base.support_symbols(main)
        provided.update(base.support_symbols(
            (baseline/"translated_runtime.h").read_text(encoding="utf-8")))
        provided.update(base.STANDARD_CALLS)
        # Existing maintained XPP/math paths use both normal C math calls.
        provided.update(("sin","cos"))
        queue=collections.deque([TARGET])
        selected=set()
        missing=set()
        unknown=set()
        while queue:
            va=queue.popleft()
            if va in selected:
                continue
            if len(selected)>=a.max_new:
                raise ValueError("XPP original direct-call closure exceeds max new-function budget")
            if va not in generated:
                missing.add(f"0x{va:08X}")
                continue
            item=generated[va]
            text=item["source"]
            normalize_generated_header(text,va) # exact source-loader ABI form
            if "loc_%08X: ;"%va not in text:
                raise ValueError("Generated function has no exact first guest label: %08X"%va)
            selected.add(va)
            deps=direct_calls(text,base)
            info["deps"][f"0x{va:08X}"]=deps
            masked=base.mask_noncode(text)
            own=set(base.DEFINE_RE.findall(text))
            supplied=provided|own|{f"sub_{n:08X}" for n in selected}
            called=set(base.CALL_RE.findall(masked))
            for call in sorted(called):
                if call.startswith("sub_") and re.fullmatch(r"sub_[0-9A-Fa-f]{8}",call):
                    sub=int(call[4:],16)
                    if call.upper() in compiled:
                        # Visibility/linkage is checked once the original
                        # direct-caller owner is selected (below).
                        continue
                    if sub not in selected:
                        queue.append(sub)
                elif call not in supplied and call!=f"sub_{va:08X}":
                    unknown.add(call)
        closure=sorted(selected)
        info["missing_callees"]=sorted(missing)
        info["unknown_helpers"]=sorted(unknown)
        if missing:
            raise ValueError("Original XPP direct child function has no generated body")
        if unknown:
            raise ValueError("XPP contains helpers not proven callable by host/TrueTU shared header")
        # Choose original caller TU to avoid changing new or shared headers.
        owner=min(caller_files,key=lambda k:(-caller_files[k],len(text_by_file[k]),k)) if caller_files else "translated_063.cpp"
        info["owner"]=owner
        for va in closure:
            for call in direct_calls(generated[va]["source"],base):
                if call.upper() in compiled:
                    filename,static=compiled[call.upper()]
                    if static and filename!=owner:
                        raise ValueError("Existing callee has internal linkage in different TU: "+call)
        # No silent rewriting of indirect dispatch or backend MMIO.
        bodies={va:generated[va]["source"] for va in closure}
        expanded=add_guest_bodies(text_by_file[owner],bodies,base,compiled,owner)
        new_main,main_edges=patch_host(main)
        transformed={}
        for p in files:
            text=text_by_file[p.name]
            if p.name==owner:
                text=expanded
            updated,n=patch_direct(text,[NAME],True)
            if n!=caller_files.get(p.name,0):
                raise ValueError("Caller count mismatch after direct-edge patch: "+p.name)
            if updated!=text_by_file[p.name]:
                transformed[p.name]=updated.encode("utf-8")
        if not transformed or len(transformed)>12:
            raise ValueError("Changed TrueTU count outside incremental budget")
        if new_main.count(FENCE) or any(FENCE in v.decode("utf-8")
                                       for v in transformed.values()):
            raise ValueError("Hardware-observed frontier still unresolved")
        if len([p for p in transformed.values()
                if "XPP D5574 ENTRY" in p.decode("utf-8")])!=1:
            raise ValueError("New XPP instrumented body missing or duplicated")
        # All source/hash and call/ABI gates PASSED. Write only now.
        expected={p.name:transformed.get(p.name,p.read_bytes())
                  for p in files+headers}
        if dest.exists() and any(dest.iterdir()):
            if {p.name for p in dest.iterdir()}!=set(expected):
                raise ValueError("Prior staged XPP file inventory differs; do not overwrite")
            for filename,data in expected.items():
                if (dest/filename).read_bytes()!=data:
                    raise ValueError("Prior staged XPP source differs; preserve previous results")
        else:
            dest.mkdir(parents=True,exist_ok=True)
            for filename,data in expected.items():
                (dest/filename).write_bytes(data)
        out_bytes=new_main.encode("utf-8")
        if outmain.exists() and outmain.read_bytes()!=out_bytes:
            raise ValueError("Prior XPP main.cpp differs; do not overwrite")
        outmain.parent.mkdir(parents=True,exist_ok=True)
        outmain.write_bytes(out_bytes)
        info.update({
            "status":"SOURCE_CLOSED_STAGED_NO_XDK",
            "reason":"All exact generated body, helper, child, K1S and caller guards passed",
            "owner":owner,"new_guest_bodies":[f"0x{x:08X}" for x in closure],
            "modified_true_tus":sorted(transformed),
            "original_owner_hashes":{p.name:sha(p) for p in files+headers},
            "new_owner_hashes":{key:sha_bytes(value) for key,value in transformed.items()},
            "staged_directory":str(dest),
            "staged_main":str(outmain),
            "previous_main_sha":sha(mainfile),
            "new_main_sha":sha_bytes(out_bytes),
            "baseline_manifest":str(manifestfile),
            "guest_display_calls_injected":False,
            "caller_host_rewires":main_edges,
        })
        out_manifest=dest.parent/"xpp-d5574-batch-manifest.json"
        out_manifest.write_text(json.dumps(info,indent=2)+"\n",encoding="utf-8")
        return info
    except ValueError as exc:
        info["reason"]=str(exc)
        info["status"]="BLOCKED_SOURCE_REVIEW"
        return info
    finally:
        evidence.parent.mkdir(parents=True,exist_ok=True)
        evidence.write_text(report_lines(info,generated,closure or [TARGET]),
                            encoding="utf-8")

def main()->None:
    p=argparse.ArgumentParser()
    for key in ("shards","manifest","main","generated_root","functions",
                "emitter","out","out_main","report"):
        p.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    p.add_argument("--max-new",type=int,default=24)
    args=p.parse_args()
    if args.max_new<1 or args.max_new>32:
        raise SystemExit("[XPP] Max new-function budget must be 1..32")
    state=stage(args)
    print("[XPP] Hardware seed 27,107,567 ticks, fault=0: DIRECT 0023A3CE -> 002D5574")
    print("[XPP] Source decision: "+state["status"])
    print("[XPP] Original local source: "+str(state.get("original_file")))
    print("[XPP] Direct callers: "+str(state.get("caller_sites")))
    print("[XPP] Helper review: "+",".join(state.get("unknown_helpers",[])))
    print("[XPP] Missing child functions: "+",".join(state.get("missing_callees",[])))
    print("[XPP] Full local source/ABI report: "+str(args.report))
    if state["status"]!="SOURCE_CLOSED_STAGED_NO_XDK":
        print("[XPP] NO XDK BUILD - "+state.get("reason","Review needed"))
        raise SystemExit(3)
    print("[XPP] STAGE PASS: original XPP + %d source-backed direct closure bodies"%len(
        state["new_guest_bodies"]))
    print("[XPP] Kept original PIXEL A3A5A, 64 TrueTUs, K1S ESI repair and all VP/MMIO fences")
    print("[XPP] New body owner: "+state["owner"])
    print("[XPP] READY FOR EXACTLY ONE INCREMENTAL XDK BUILD - no clean")

if __name__=="__main__":
    main()
