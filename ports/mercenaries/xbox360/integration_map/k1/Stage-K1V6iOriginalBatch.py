#!/usr/bin/env python3
"""V6i: stage source-authentic function 001FA000 and bounded dependency closure.

Build input is the hardware-tested V6h candidate. Do not touch originals,
retail guest state, D3D fences, APC, or the frozen 64 TrueTUs.
"""
from pathlib import Path
import hashlib, json, re, sys

ROOT=Path.cwd()
TAG="[K1-V6i]"
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_camera_vec3_v6h"
DEST=ROOT/"build/phase6_integration_map/k1_pixel_camera_batch_v6i_helperfenced"
SRC=ROOT/"build/phase3n_final_abi_scale/runtime/gen/recomp_0010.c"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
V6G=ROOT/"build/phase6_integration_map/k1_pixel_camera_batch_v6g_sinebridge/v6g-manifest.json"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
SEED="sub_001FA000"
MAX_FUNCS=48
LOW,HIGH=0x001F9E00,0x001FA900
MARK="K1-V6I-ORIGINAL-001FA000-CLOSURE-20261105"

def digest(b): return hashlib.sha256(b).hexdigest()
def require(ok,why):
    if not ok: raise ValueError(why)

def definitions(src):
    defs={}
    for m in re.finditer(r"(?m)^void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{.*?^\}",src,re.M|re.S):
        require(m.group(1) not in defs,"Duplicate source function "+m.group(1))
        defs[m.group(1)]=m.group(0)
    return defs

def calls(fn):
    return set(re.findall(r"\b(sub_[0-9A-Fa-f]{8})\s*\(",fn))

def close(name,defs,known,staged,trail):
    if name in known or name in staged or name in trail: return {},None
    if name not in defs: return {},"source_missing:"+name
    fn=defs[name]
    unsafe=sorted(set(re.findall(r"\b(recomp_[A-Za-z_0-9]+)\s*\(",fn)))
    if unsafe: return {},name+" unsupported host helper: "+",".join(unsafe)
    if "return;" not in fn: return {},name+" missing translator return"
    result={name:fn}
    for dep in sorted(calls(fn)-{name}-known-staged.keys()):
        extra,why=close(dep,defs,known,{**staged,**result},trail|{name})
        if why: return {},name+" -> "+why
        result.update(extra)
        if len(staged)+len(result)>MAX_FUNCS: return {},"closure cap:"+name
    return result,None

def main():
    v6g=json.loads(V6G.read_text(encoding="utf-8-sig"))
    manifest=json.loads((PARENT/"v6h-manifest.json").read_text(encoding="utf-8-sig"))
    parent=(PARENT/"main.cpp").read_bytes()
    require(manifest["retail_sha256"]==RETAIL==v6g["retail_sha256"],
            "Retail XBE provenance differs")
    require(digest(parent)==manifest["source_sha256"],"V6h parent main.cpp changed")
    raw=SRC.read_bytes()
    require(digest(raw)==v6g["original_recomp_0010_sha256"],
            "Original recomp_0010.c changed since V6g")
    tus=sorted(SHARDS.glob("translated_???.cpp"))
    require(len(tus)==64,"Expected 64 TrueTUs")
    hashes={p.name:digest(p.read_bytes()) for p in tus}
    require(hashes==manifest["true_tu_sha256"],
            "Inherited V6h TrueTU sources differ")
    parent_text=parent.decode("utf-8-sig")
    eol="\r\n" if "\r\n" in parent_text else "\n"
    base=parent_text.replace("\r\n","\n")
    defs=definitions(raw.decode("utf-8-sig").replace("\r\n","\n"))
    known=set(re.findall(r"(?m)^\s*void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{",base))
    for tu in tus:
        known.update(re.findall(r"(?m)^\s*void (sub_[0-9A-Fa-f]{8})\(void\)\s*\{",
            tu.read_text(encoding="utf-8-sig",errors="replace")))
    require(SEED not in known,"Frontier already compiled; reject duplicate")
    require(SEED in defs,"Original 001FA000 source function absent")
    require("case 0x0022F51Cu: return phase6v6h_retail_vec3_0022f51c;" in base,
            "V6h vector dispatch provenance absent")
    sine="sub_001F9D70"
    vec="sub_0022F51C"
    # These two real, manual support functions are already owned by V6h.
    # The existing caller convention pushes a synthetic return word and uses
    # phase4c_direct_frontier, exactly as V6g successfully did for sine.
    manual={
        sine:("PUSH32(esp, 0); sub_001F9D70(); /* call 0x001F9D70 */",
              "PUSH32(esp, 0); phase4c_direct_frontier(0x001F9D70u); /* call 0x001F9D70 */"),
        vec:("PUSH32(esp, 0); sub_0022F51C(); /* call 0x0022F51C */",
             "PUSH32(esp, 0); phase4c_direct_frontier(0x0022F51Cu); /* call 0x0022F51C */")
    }
    require("case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;" in base,
            "V6h sine dispatch ownership changed")
    known.update(manual)
    selected,why=close(SEED,defs,known,{},set())
    require(why is None,"REQUIRED root dependency unverified: "+str(why))
    require(SEED in selected,"Missing required 001FA000")
    skipped={}
    for candidate in sorted(defs):
        addr=int(candidate[4:],16)
        if not LOW<=addr<HIGH or candidate in known or candidate in selected: continue
        subset,issue=close(candidate,defs,known,selected,set())
        if issue: skipped[candidate]=issue
        elif len(selected)+len(subset)<=MAX_FUNCS: selected.update(subset)
        else: skipped[candidate]="batch cap"
    bridge_counts={}
    for name,fn in list(selected.items()):
        for dep,(old,new) in manual.items():
            seen=len(re.findall(r"\b"+dep+r"\s*\(",fn))
            count=fn.count(old)
            require(count==seen,"Nonstandard manual call frame in "+name+" -> "+dep)
            if count:
                fn=fn.replace(old,new)
                bridge_counts[name+":"+dep]=count
        require(not (calls(fn)&set(manual)),"Unconverted manual call in "+name)
        selected[name]=fn
    require(len(selected)<=MAX_FUNCS,"Batch exceeded cap")
    # A missing host-side recomp_* hook must never be faked on Xbox.
    # Fail source staging before invoking MSBuild if any escaped the closure filter.
    forbidden=sorted(set(re.findall(r"\b(recomp_[A-Za-z_0-9]+)\s*\(",
                                    "\n".join(selected.values()))))
    require(not forbidden,"Unsupported PC-only recomp helper(s) in staged batch: "+", ".join(forbidden))
    for name in selected:
        require(name not in known,"Duplicate compiled symbol "+name)
        require("case 0x"+name[4:].upper()+"u:" not in base,
                "Dispatch already owned: "+name)
    prototypes="\n".join("void "+name+"(void);" for name in sorted(selected))
    bodies="\n\n".join(selected[name] for name in sorted(selected))
    anchor="    case 0x001F8F10u: return sub_001F8F10;"
    require(base.count(anchor)==1,"V6h lookup anchor changed")
    pos=base.index(anchor)
    scope=list(re.finditer(
        r"(?m)^[ \t]*(?:(?:static|inline)\s+)*recomp_func_t\s+"
        r"[A-Za-z_][A-Za-z_0-9]*\s*\([^;{}]*\)\s*\{",base[:pos]))
    require(scope and "switch" in base[scope[-1].end():pos],
            "Function lookup scope unverified")
    at=scope[-1].start()
    dispatches="\n".join("    case 0x"+name[4:].upper()+"u: return "+name+";"
                         for name in sorted(selected))
    patched=base[:at]+"/* "+MARK+" */\n"+prototypes+"\n\n"+bodies+"\n\n"+base[at:]
    patched=patched.replace(anchor,anchor+"\n"+dispatches,1)
    for name in selected:
        require(patched.count("case 0x"+name[4:].upper()+"u:")==1,
                "New dispatch count incorrect: "+name)
    for token in ("P6DQ ROCKET HARD STOP","K1-V6b APC DELIVERED",
                  "0x0ACE8000u","phase6v6h_retail_vec3_0022f51c",
                  "K1-V6H-RETAIL-SSE-VEC3-0022F51C-20261105"):
        require(patched.count(token)==base.count(token),
                "Inherited hardware evidence changed: "+token)
    output=patched.replace("\n",eol).encode("utf-8")
    report={
        "stage":"V6I_ORIGINAL_SOURCE_ONLY_HARDWARE_UNTESTED",
        "retail_sha256":RETAIL,
        "hardware_seed":"0x001FA000",
        "parent_v6h_sha256":digest(parent),
        "original_recomp_0010_sha256":digest(raw),
        "source_sha256":digest(output),
        "true_tu_count":64,"true_tu_sha256":hashes,
        "included":sorted(selected),"dispatch_count":len(selected),
        "manual_bridges":bridge_counts,
        "optional_skipped":skipped,
        "marker":MARK,"hardware_tested":False,
        "guest_state_or_tick_skipped":False,
        "hard_fences_unchanged":True}
    payloads=[(DEST/"main.cpp",output),
              (DEST/"v6i-manifest.json",(json.dumps(report,indent=2)+"\n").encode())]
    for p,data in payloads:
        if p.exists(): require(p.read_bytes()==data,"Refusing overwrite "+str(p))
    DEST.mkdir(parents=True,exist_ok=True)
    for p,data in payloads:
        if not p.exists(): p.write_bytes(data)
    require((PARENT/"main.cpp").read_bytes()==parent,"V6h parent mutated")
    print(TAG+" SOURCE PASS: 001FA000 + "+str(len(selected)-1)+" original functions")
    print(TAG+" INCLUDED: "+", ".join(sorted(selected)))
    print(TAG+" MANUAL BRIDGES: "+str(bridge_counts))
    print(TAG+" OPTIONAL SKIPS: "+str(len(skipped))+" (manifest)")
    print(TAG+" 64 TrueTUs, hard fences and V6h vector path unchanged")
    print(TAG+" SOURCE: "+str(DEST/"main.cpp"))
    print(TAG+" XDK/HARDWARE UNTESTED")
if __name__=="__main__":
    try: main()
    except Exception as e:
        print(TAG+" BLOCKED: "+str(e),file=sys.stderr)
        sys.exit(1)
