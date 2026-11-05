#!/usr/bin/env python3
"""K1 V6k: batched original-function coverage from the 0x001ED160 hardware frontier.

Only add complete, source-authentic translated functions with bounded closure.
No fake functions, no return-value spoofing, no tick skipping or fence relaxation.
Unresolved required dependency => hard stop before XDK build.
"""
from pathlib import Path
import hashlib, json, re, sys

ROOT=Path.cwd()
TAG="[K1-V6k]"
FRONTIER="sub_002033E0"
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_camera_source_batch_v6j_retail"
DEST=ROOT/"build/phase6_integration_map/k1_pixel_camera_source_batch_v6k_retail"
GEN=ROOT/"build/phase3n_final_abi_scale/runtime/gen"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
MARK="K1-V6K-RETAIL-SOURCE-CLOSURE-002033E0-20261105"
MAX_FUNCS=192
# Prioritize genuine source-neighbors to the witnessed math/camera call path;
# candidates outside these zones can still enter through required dependencies.
WINDOWS=((0x00202000,0x00208000),(0x001EC000,0x001F1000))
FUNC_RE=re.compile(r"(?m)^void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{.*?^\}",re.M|re.S)
CALL_RE=re.compile(r"\b(sub_[0-9A-Fa-f]{8})\s*\(")
HELPER_RE=re.compile(r"\b(recomp_[A-Za-z_0-9]+)\s*\(")
KNOWN_RE=re.compile(r"(?m)^\s*void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{")
TRUSTED_MANUAL={
    "sub_001F9D70":("PUSH32(esp, 0); sub_001F9D70(); /* call 0x001F9D70 */",
                    "PUSH32(esp, 0); phase4c_direct_frontier(0x001F9D70u); /* call 0x001F9D70 */",
                    "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;"),
    "sub_0022F51C":("PUSH32(esp, 0); sub_0022F51C(); /* call 0x0022F51C */",
                    "PUSH32(esp, 0); phase4c_direct_frontier(0x0022F51Cu); /* call 0x0022F51C */",
                    "case 0x0022F51Cu: return phase6v6h_retail_vec3_0022f51c;"),
}
def sha(x): return hashlib.sha256(x).hexdigest()
def require(condition,why):
    if not condition: raise RuntimeError(why)
def callnames(fn): return set(CALL_RE.findall(fn))
def helpers(fn): return set(HELPER_RE.findall(fn))

def function_inventory():
    files=sorted(p for p in GEN.glob("recomp_*.c") if p.name!="recomp_dispatch.c")
    require(len(files)>=12,"Generated C corpus too small: %d" % len(files))
    definitions={}
    sources={}
    for file in files:
        data=file.read_bytes()
        content=data.decode("utf-8-sig").replace("\r\n","\n")
        for m in FUNC_RE.finditer(content):
            name=m.group(1)
            require(name not in definitions,"Original duplicated definition "+name)
            definitions[name]=m.group(0)
            sources[name]=file.name
    require(FRONTIER in definitions,"Hardware frontier 002033E0 not found in generated C definitions")
    return definitions,sources,len(files)

def main():
    v6i=json.loads((PARENT/"v6j-manifest.json").read_text(encoding="utf-8-sig"))
    parent=(PARENT/"main.cpp").read_bytes()
    require(v6i["retail_sha256"]==RETAIL,"V6j retail identity drift")
    require(sha(parent)==v6i["source_sha256"],"V6j source provenance drift")
    tus=sorted(SHARDS.glob("translated_???.cpp"))
    require(len(tus)==64,"64 TrueTUs missing")
    hashes={p.name:sha(p.read_bytes()) for p in tus}
    require(hashes==v6i["true_tu_sha256"],"64 TrueTU source hashes changed")
    defs,sources,filecount=function_inventory()

    base=parent.decode("utf-8-sig").replace("\r\n","\n")
    eol="\r\n" if b"\r\n" in parent else "\n"
    known=set(KNOWN_RE.findall(base))
    for tu in tus:
        known.update(KNOWN_RE.findall(tu.read_text(encoding="utf-8-sig",errors="replace")))
    require(FRONTIER not in known,"Frontier 002033E0 already compiled")
    for manual in TRUSTED_MANUAL.values():
        require(manual[2] in base,"Previous trusted manual dispatch missing: "+manual[2])

    # The V6i/V6j Xbox tests compiled recomp_xmm_* helper operations.
    # Non-SSE recomp_* callbacks (notification checkpoints etc.) are *not*
    # assumed to exist; exclude the entire optional closure or block the root.
    def vetted(name):
        fn=defs.get(name)
        if fn is None: return None,"missing generated source: "+name
        if "return;" not in fn: return None,"unrecognized translator return: "+name
        unsupported=sorted(x for x in helpers(fn) if not x.startswith("recomp_xmm_"))
        if unsupported: return None,"unproven host helper(s) %s: %s" % (name,",".join(unsupported))
        conversions={}
        for manual,(old,new,_dispatch) in TRUSTED_MANUAL.items():
            hits=len(re.findall(r"\b"+manual+r"\s*\(",fn))
            replaced=fn.count(old)
            if hits!=replaced:
                return None,"manual owner call ABI unproven: %s -> %s (%d/%d)" % (name,manual,replaced,hits)
            if replaced: fn=fn.replace(old,new)
            conversions[manual]=replaced
        if callnames(fn)&TRUSTED_MANUAL.keys():
            return None,"unconverted manual owner call: "+name
        return (fn,conversions),None

    # Iteratively materialize a candidate's full direct dependency DAG.
    # A function only becomes eligible if every direct callee is in this
    # batch, in inherited compiled code, or in a proven manual dispatch.
    selected={}
    bridged={}
    failures={}
    def resolve(seed):
        staged={}
        bridges={}
        active=set()
        def visit(name):
            if name in selected or name in staged or name in known or name in TRUSTED_MANUAL:
                return None
            if name in active: return None  # mutual recursion resolved below
            if len(selected)+len(staged)>=MAX_FUNCS: return "function cap %d" % MAX_FUNCS
            result,err=vetted(name)
            if err: return err
            fn,converted=result
            active.add(name)
            for dependency in sorted(callnames(fn)-{name}):
                issue=visit(dependency)
                if issue:
                    active.remove(name)
                    return "%s -> %s" % (name,issue)
            active.remove(name)
            staged[name]=fn
            if any(converted.values()): bridges[name]={k:v for k,v in converted.items() if v}
            return None
        issue=visit(seed)
        if issue: return issue
        if len(selected)+len(staged)>MAX_FUNCS: return "function cap exceeded"
        selected.update(staged)
        bridged.update(bridges)
        return None
    err=resolve(FRONTIER)
    require(err is None,"REQUIRED 002033E0 closure blocked: "+str(err))
    require(FRONTIER in selected,"Required frontier missing from staged roots")

    # Verified optional neighborhoods: close DAGs, not raw neighboring addresses.
    optional=[n for n in defs if any(lo<=int(n[4:],16)<hi for lo,hi in WINDOWS)
              and n not in known and n not in selected and n not in TRUSTED_MANUAL]
    optional.sort(key=lambda n:(abs(int(n[4:],16)-int(FRONTIER[4:],16)),n))
    for name in optional:
        if len(selected)>=MAX_FUNCS: break
        issue=resolve(name)
        if issue: failures[name]=issue

    # Audit that no sub_xxx direct calls escape unresolved, even after optional merges.
    unresolved={}
    for name,fn in selected.items():
        bad=sorted(callnames(fn)-known-selected.keys()-TRUSTED_MANUAL.keys())
        if bad: unresolved[name]=bad
    require(not unresolved,"Unresolved dependency after closure: "+str(unresolved))
    remaining=sorted(set().union(*(helpers(fn) for fn in selected.values())) if selected else ())
    forbidden=sorted(x for x in remaining if not x.startswith("recomp_xmm_"))
    require(not forbidden,"Unsupported host callbacks remain: "+str(forbidden))
    for name in selected:
        require(name not in known,"Duplicate translated owner: "+name)
        require("case 0x"+name[4:].upper()+"u:" not in base,"Duplicate guest dispatch: "+name)
    anchor="    case 0x001F8F10u: return sub_001F8F10;"
    require(base.count(anchor)==1,"Trusted guest dispatch anchor missing")
    pos=base.index(anchor)
    headers=list(re.finditer(
        r"(?m)^[ \t]*(?:(?:static|inline)\s+)*recomp_func_t\s+"
        r"[A-Za-z_][A-Za-z_0-9]*\s*\([^;{}]*\)\s*\{",base[:pos]))
    require(headers and "switch" in base[headers[-1].end():pos],
            "Guest dispatch lookup scope not proven")
    insertion=headers[-1].start()
    names=sorted(selected)
    declarations="\n".join("void "+name+"(void);" for name in names)
    bodies="\n\n".join(selected[name] for name in names)
    all_dispatch="\n".join("    case 0x"+name[4:].upper()+"u: return "+name+";" for name in names)
    output=base[:insertion]+"/* "+MARK+" */\n"+declarations+"\n\n"+bodies+"\n\n"+base[insertion:]
    output=output.replace(anchor,anchor+"\n"+all_dispatch,1)
    for name in names:
        require(output.count("case 0x"+name[4:].upper()+"u:")==1,
                "Missing or duplicate dispatch "+name)
    for legacy in ("P6DQ ROCKET HARD STOP","K1-V6b APC DELIVERED","0x0ACE8000u",
                   "phase6v6h_retail_vec3_0022f51c","K1-V6H-RETAIL-SSE-VEC3-0022F51C-20261105"):
        require(output.count(legacy)==base.count(legacy),
                "Inherited debug fence / guest owner drift: "+legacy)
    out_bytes=output.replace("\n",eol).encode("utf-8")
    report={
        "retail_v6j_fix_inherited":True,
        "stage":"V6K_RETAIL_SOURCE_BATCH_HARDWARE_UNTESTED",
        "retail_sha256":RETAIL,
        "hardware_frontier":"0x002033E0",
        "previous_frontier_tick":58830611,
        "parent_v6j_sha256":sha(parent),
        "source_sha256":sha(out_bytes),
        "generated_files_scanned":filecount,
        "batch_cap":MAX_FUNCS,
        "dispatch_count":len(names),
        "included":names,
        "original_source_ownership":{n:sources[n] for n in names},
        "verified_manual_call_bridges":bridged,
        "allowed_xmm_helpers_requires_xdk_compile":sorted(remaining),
        "optional_rejected":failures,
        "true_tu_count":64,"true_tu_sha256":hashes,
        "hard_fences_unchanged":True,
        "guest_state_or_tick_skipped":False,
        "hardware_tested":False,
        "marker":MARK
    }
    payloads=((DEST/"main.cpp",out_bytes),
              (DEST/"v6k-manifest.json",(json.dumps(report,indent=2)+"\n").encode("utf-8")))
    for target,data in payloads:
        if target.exists(): require(target.read_bytes()==data,
                                    "Refusing overwrite existing V6k stage "+str(target))
    DEST.mkdir(parents=True,exist_ok=True)
    for target,data in payloads:
        if not target.exists(): target.write_bytes(data)
    require((PARENT/"main.cpp").read_bytes()==parent,"V6j parent modified")
    print(TAG+" INHERITED RETAIL V6j source hash PASS")
    print(TAG+" SOURCE PASS: 002033E0 plus %d dependency-closed real functions" % (len(names)-1))
    print(TAG+" SOURCE CORPUS: %d generated files; stage cap %d" % (filecount,MAX_FUNCS))
    print(TAG+" SSE HELPERS (XDK must resolve): "+", ".join(remaining))
    print(TAG+" OPTIONAL REJECTED: %d (manifest has reasons)" % len(failures))
    print(TAG+" TrueTUs 64 / APC / retail / hard fences unchanged")
    print(TAG+" MAIN: "+str(DEST/"main.cpp"))
    print(TAG+" SHA256: "+sha(out_bytes))
    print(TAG+" XDK compilation and Xbox hardware still unverified")
if __name__=="__main__":
    try: main()
    except Exception as e:
        print(TAG+" BLOCKED: "+str(e),file=sys.stderr)
        sys.exit(1)
