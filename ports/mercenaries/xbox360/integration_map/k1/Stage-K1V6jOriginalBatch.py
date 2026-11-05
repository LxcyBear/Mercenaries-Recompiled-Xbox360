#!/usr/bin/env python3
"""K1 V6j: batched original-function coverage from the 0x001ED160 hardware frontier.

Only add complete, source-authentic translated functions with bounded closure.
No fake functions, no return-value spoofing, no tick skipping or fence relaxation.
Unresolved required dependency => hard stop before XDK build.
"""
from pathlib import Path
import hashlib, json, re, sys

ROOT=Path.cwd()
TAG="[K1-V6j]"
FRONTIER="sub_001ED160"
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_camera_batch_v6i_sseallowed"
DEST=ROOT/"build/phase6_integration_map/k1_pixel_camera_source_batch_v6j_retail"
GEN=ROOT/"build/phase3n_final_abi_scale/runtime/gen"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
MARK="K1-V6J-RETAIL-SOURCE-CLOSURE-001ED160-20261105"
# Retail and generated-code identity pinned by the 2026-11-05 source audit.
XBE=ROOT/"game_files/mercenaries-retail/default.xbe"
ROOT_GEN_SHA="b6b075e2c0f199ac8b0a8abb6264bbc6aa3e688f5cb4f44ab605796bc9b3411e"
ROOT_GEN_FILE="recomp_0009.c"
# Retail instructions at 001ED240: push 320.0f, push 120.0f,
# push 0x1000, call 001EC880. No PC options behavior exists in retail.
RETAIL_PUSH_BYTES=bytes.fromhex("68 00 00 A0 43 68 00 00 F0 42 68 00 10 00 00 E8 2C F6 FF FF")
PC_HOOK=(
    "    { int recomp_options_begin_world_load(void);\n"
    "      void recomp_options_refresh_retail_camera_projection(void);\n"
    "      if (recomp_options_begin_world_load())\n"
    "          recomp_options_refresh_retail_camera_projection(); }\n"
)
PC_DISTANCE=(
    "    esp -= 4u;\n"
    "    GUEST_WRITEF32(esp, 300.0f * recomp_options_object_distance_multiplier() + 20.0f); /* largest scenery radius + grid margin */"
)

MAX_FUNCS=192
# Prioritize genuine source-neighbors to the witnessed math/camera call path;
# candidates outside these zones can still enter through required dependencies.
WINDOWS=((0x001EC000,0x001F1000),(0x001F8000,0x001FC000))
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
    require(FRONTIER in definitions,"Hardware frontier 001ED160 not found in generated C definitions")
    return definitions,sources,len(files)

def retail_root_restore(fn):
    """Restore exactly two PC-injected sites; no generic stripping allowed."""
    xbe=XBE.read_bytes()
    require(sha(xbe).upper()==RETAIL,"Retail XBE SHA mismatch; abort")
    require(xbe[:4]==b"XBEH","Retail XBE magic mismatch")
    import struct
    word=lambda off:struct.unpack_from("<I",xbe,off)[0]
    base=word(0x104); count=word(0x11C); table=word(0x120)-base
    require(0<count<=64 and table>=0 and table+count*0x38<=len(xbe),
            "Retail XBE section-table malformed")
    owners=[]
    va=0x001ED240
    for i in range(count):
        h=table+i*0x38
        mem,vs,raw,rs=word(h+4),word(h+8),word(h+12),word(h+16)
        if mem<=va and va+len(RETAIL_PUSH_BYTES)<=mem+min(vs,rs):
            off=raw+(va-mem)
            if off+len(RETAIL_PUSH_BYTES)<=len(xbe):
                owners.append(xbe[off:off+len(RETAIL_PUSH_BYTES)])
    require(len(owners)==1 and owners[0]==RETAIL_PUSH_BYTES,
            "Retail 001ED240 push/call bytes drifted")
    require(fn.count(PC_HOOK)==1,"Expected PC world-load block exactly once")
    require(fn.count(PC_DISTANCE)==1,"Expected PC distance expression exactly once")
    fn=fn.replace(PC_HOOK,"",1)
    fn=fn.replace(PC_DISTANCE,"    PUSH32(esp, 0x43A00000); /* retail push 320.0f */",1)
    require(not any(x.startswith("recomp_options_") for x in helpers(fn)),
            "PC options helper survived retail restoration")
    return fn

def main():
    v6i=json.loads((PARENT/"v6i-manifest.json").read_text(encoding="utf-8-sig"))
    parent=(PARENT/"main.cpp").read_bytes()
    require(v6i["retail_sha256"]==RETAIL,"V6i retail identity drift")
    require(sha(parent)==v6i["source_sha256"],"V6i source provenance drift")
    tus=sorted(SHARDS.glob("translated_???.cpp"))
    require(len(tus)==64,"64 TrueTUs missing")
    hashes={p.name:sha(p.read_bytes()) for p in tus}
    require(hashes==v6i["true_tu_sha256"],"64 TrueTU source hashes changed")
    defs,sources,filecount=function_inventory()
    require(sources[FRONTIER]==ROOT_GEN_FILE,"Root generated owner changed")
    require(sha((GEN/ROOT_GEN_FILE).read_bytes())==ROOT_GEN_SHA,
            "Generated recomp_0009.c SHA mismatch: do not patch unknown source")
    root_original=defs[FRONTIER]
    defs[FRONTIER]=retail_root_restore(root_original)
    require(sha((GEN/ROOT_GEN_FILE).read_bytes())==ROOT_GEN_SHA,
            "Generated original mutated during staging")

    base=parent.decode("utf-8-sig").replace("\r\n","\n")
    eol="\r\n" if b"\r\n" in parent else "\n"
    known=set(KNOWN_RE.findall(base))
    for tu in tus:
        known.update(KNOWN_RE.findall(tu.read_text(encoding="utf-8-sig",errors="replace")))
    require(FRONTIER not in known,"Frontier 001ED160 already compiled")
    for manual in TRUSTED_MANUAL.values():
        require(manual[2] in base,"Previous trusted manual dispatch missing: "+manual[2])

    # The prior V6i Xbox test compiled recomp_xmm_* helper operations.
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
    require(err is None,"REQUIRED 001ED160 closure blocked: "+str(err))
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
        "retail_restored_pc_options_at_root":True,
        "retail_root_original_generated_sha256":ROOT_GEN_SHA,
        "retail_root_push_001ed240":"0x43A00000 (320.0f)",
        "stage":"V6J_RETAIL_SOURCE_BATCH_HARDWARE_UNTESTED",
        "retail_sha256":RETAIL,
        "hardware_frontier":"0x001ED160",
        "previous_frontier_tick":58665978,
        "parent_v6i_sha256":sha(parent),
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
              (DEST/"v6j-manifest.json",(json.dumps(report,indent=2)+"\n").encode("utf-8")))
    for target,data in payloads:
        if target.exists(): require(target.read_bytes()==data,
                                    "Refusing overwrite existing V6j stage "+str(target))
    DEST.mkdir(parents=True,exist_ok=True)
    for target,data in payloads:
        if not target.exists(): target.write_bytes(data)
    require((PARENT/"main.cpp").read_bytes()==parent,"V6i parent modified")
    print(TAG+" RETAIL RESTORE PASS: PC camera hooks removed; 001ED240 PUSH 320.0f exact XBE bytes")
    print(TAG+" SOURCE PASS: 001ED160 plus %d dependency-closed real functions" % (len(names)-1))
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
