#!/usr/bin/env python3
"""PIXEL A3A5A: one source-proven K1S-preserving TrueTU/dispatcher batch.

Goal: enable the exact K1S Xbox DIRECT_FRONTIER 0x002A3A5A, not fake a
display call. Copy one original user-local generated DSOUND function into an
existing TrueTU, resolve its 32-bit APU read/write calls through the existing
phase6ch APU bridge, restore the original direct caller(s), and add the exact
existing pack lookup case. Never commit retail or generated guest code.

The generated original hash and exact helper/wrapper source contracts come
from the local user's pixel_apu_contracts.txt and K1S TrueTU manifest.
Unknown VP reads and MMIO remain hard fenced. Preserve the K1S ESI repair.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG="PIXEL-A3A5A-DIRECT-APU-20261030"
BASE="K1S-HALGETVECTOR44-SAVED-ESI-20261030"
TARGET=0x002A3A5A
NAME="sub_002A3A5A"
ORIGINAL_FILE="recomp_0013.c"
ORIGINAL_SHA="c0808e2f58c27c82e837e29d8e1b448a4745ebb47ec1b549b9b31cb56eecd473"
FRONTIER="phase4c_direct_frontier(0x002A3A5Au);"
# Original lifter's rewritten direct call syntax is preserved byte for byte
# apart from replacing only the artificially inserted frontier call.
CALL_REPLACEMENT="sub_002A3A5A();"
LOOKUP="static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
LOOKUP_DEFAULT="    default: return (recomp_func_t)0;"
EXACT_CALLS=("sub_0029CBB0","sub_002A303C","sub_0029CBD2")
DEFINITION=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})"
                      r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
CLOSE=re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
LOC=re.compile(r"^([ \t]*)loc_([0-9A-Fa-f]{8})[ \t]*:[ \t]*;[ \t]*$",re.M)
HELPER=re.compile(r"\brecomp_apu_(read32|write32)\s*\(")
GUEST_APU=re.compile(r"\bGUEST_(READ|WRITE)(8|16|32)\s*\(")
REG_WRITE=re.compile(r"(?m)^[ \t]*(?:eax|ebx|ecx|edx|esi|edi|ebp|esp|g_esp)"
                     r"[ \t]*(?:=|\+=|-=|\+\+|--)")
SOURCE_OPS=re.compile(r"\b(?:PUSH32|POP32|RECOMP_TRACE_FUNC|sub_[0-9A-Fa-f]{8})\s*\(")
SOURCE_FILES=re.compile(r"translated_\d{3}\.cpp$")
PROTOTYPE="void sub_002A3A5A(void); /* PIXEL A3A5A original retail function */"

def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def sha(path:Path)->str:
    return digest(path.read_bytes())

def nl_for(data:str)->str:
    cr=data.count("\r\n")
    if data.count("\r")!=cr or (cr and cr!=data.count("\n")):
        raise ValueError("Mixed/broken TrueTU line endings; not safe to stage")
    return "\r\n" if cr else "\n"

def find_body(file_text:str,name:str)->str:
    defs=[m for m in DEFINITION.finditer(file_text)
          if "sub_"+m.group(1).upper()==name.upper()]
    if len(defs)!=1:
        raise ValueError(f"Expected one translated {name} body; found {len(defs)}")
    finish=CLOSE.search(file_text,defs[0].end())
    if finish is None:
        raise ValueError("Unterminated translated "+name)
    return file_text[defs[0].start():finish.end()]

def budgeted_body(original:str,nl:str)->tuple[str,dict]:
    if "PIXEL A3A5A" in original:
        raise ValueError("Original source unexpectedly already patched")
    if not original.startswith("void sub_002A3A5A(void)"):
        raise ValueError("A3A5A original source definition is not normal")
    if original.count("recomp_apu_read32(")!=2 or original.count("recomp_apu_write32(")!=6:
        raise ValueError("Unexpected A3A5A original APU helper counts (include extern declarations)")
    if ("recomp_apu_read32((uint32_t)-25034736)" not in original or
        "recomp_apu_write32(0xFE820160u, eax)" not in original or
        "recomp_apu_write32(0xFE82043Cu, eax)" not in original or
        "recomp_apu_write32(0xFE8202F8u, eax)" not in original or
        "recomp_apu_write32(0xFE82031Cu, eax)" not in original or
        "recomp_apu_write32(ebx, edx)" not in original or
        "GUEST_WRITE32(ebp + 8, 0xFE820400u)" not in original or
        "CMP_L(GUEST_READ32(ebp + 8), 0xFE82043Cu)" not in original):
        raise ValueError("Exact A3A5A readiness/VP write-region source differs")
    for func in EXACT_CALLS:
        if original.count(func+"();")!=1:
            raise ValueError("An original A3A5A translated direct dependency changed: "+func)
    # This source is the exact original, with the original return width.
    if original.count("esp += 12; return; /* ret 8 */")!=1:
        raise ValueError("Original A3A5A ret8 / stack contract changed")
    original_ops=SOURCE_OPS.findall(original)
    original_regs=REG_WRITE.findall(original)
    text=original
    text=HELPER.sub(lambda m:"phase6ch_apu_"+m.group(1)+"(",text)
    text=GUEST_APU.sub(lambda m:"phase6ch_apu_"+m.group(1).lower()+m.group(2)+"(",text)
    # Match Rocket R51 routing for DSOUND ordinary guest 8/16/32 accesses.
    if HELPER.search(text):
        raise ValueError("Unresolved recomp_apu_* helper remains")
    if GUEST_APU.search(text):
        raise ValueError("Unrouted DSOUND ordinary guest APU access remains")
    if SOURCE_OPS.findall(text)!=original_ops or REG_WRITE.findall(text)!=original_regs:
        raise ValueError("Original translated call / stack / register instruction sequence changed")
    lines=[]
    tick_sites=0
    for line in text.splitlines():
        lines.append(line)
        match=LOC.fullmatch(line)
        if match:
            va=int(match.group(2),16)
            lines.append("    PHASE4C_BUDGET_TICK(0x%08Xu);"%va)
            tick_sites+=1
            if va==TARGET:
                lines.extend([
                    "    {",
                    "        static uint32_t pixel_a3a5a_entries=0u;",
                    "        ++pixel_a3a5a_entries;",
                    "        if (pixel_a3a5a_entries<=4u)",
                    "        {",
                    "            char pixel_line[192];",
                    '            sprintf(pixel_line,"PIXEL A3A5A ENTRY: n=%u esp=%08X ecx=%08X",',
                    "              (unsigned)pixel_a3a5a_entries,(unsigned)esp,(unsigned)ecx);",
                    "            trace(pixel_line);",
                    "        }",
                    "    }",
                ])
    if tick_sites<8 or sum("PIXEL A3A5A ENTRY" in s for s in lines)!=1:
        raise ValueError("Lost translated guest labels or A3A5A root instrumentation")
    result=nl.join(lines)
    return result,{"source_function_lines":len(original.splitlines()),
                   "budget_tick_sites":tick_sites,
                   "replaced_apu_read32":1,
                   "replaced_apu_write32":5}

def validate_apu_bridge(main:str,header:str)->None:
    needed=(
        "uint32_t phase6ch_apu_read32(uint32_t address)",
        "void phase6ch_apu_write32(uint32_t address, uint32_t value)",
        "address == 0xFE820010u",
        "0x00000080u",
        "phase6dq_note_vp_unknown_read(address, 4u)",
        "phase6dq_note_vp_write(",
        "address >= 0xFE820000u",
        "address < 0xFE830000u",
        "(address & 3u) == 0u",
        "return GUEST_READ32(address);",
        "GUEST_WRITE32(address, value);",
        "phase6ch_apu_core_range(address, 4u, &offset)",
        "phase6ci_dsp_range(address, 4u, &processor, &offset)",
    )
    for key in needed:
        if key not in main:
            raise ValueError("Verified Phase6DQ APU/VP bridge contract absent: "+key)
    for proto in ("phase6ch_apu_read8(", "phase6ch_apu_read16(",
                  "phase6ch_apu_read32(", "phase6ch_apu_write8(",
                  "phase6ch_apu_write16(", "phase6ch_apu_write32("):
        if proto not in header:
            raise ValueError("K1S shared runtime lacks existing APU helper: "+proto)
    if "K1S-HALGETVECTOR44-SAVED-ESI-20261030" in main:
        # Only the K1S source owner contains this marker, never the host main.
        raise ValueError("Cannot mix K1S guest repair into host main")

def patch_main(main:str)->tuple[str,int]:
    if TAG in main:
        raise ValueError("PIXEL already staged in main")
    nl=nl_for(main)
    expected="P6DQ-R51-MM173-FRAME-20261029-A"
    if main.count(expected)<1:
        raise ValueError("Original K1C true-TU main build tag mismatch")
    anchor=LOOKUP.replace("\n",nl)
    if main.count(anchor)!=1:
        raise ValueError("Missing or duplicate existing packed lookup function")
    if main.count("case 0x002A3A5Au:"):
        raise ValueError("A3A5A lookup case already exists; reject duplicate")
    if any(int(m.group(1),16)==TARGET for m in DEFINITION.finditer(main)):
        raise ValueError("A3A5A full function already defined in host main")
    before,after=main.split(anchor,1)
    if LOOKUP_DEFAULT not in after:
        raise ValueError("Original packed lookup case/default contract changed")
    # Global prototype before lookup, and no global rewrite of other dispatch.
    prefix=PROTOTYPE+nl+"/* "+TAG+" lookup binding */"+nl
    after=after.replace(LOOKUP_DEFAULT,
                        "    case 0x002A3A5Au: return sub_002A3A5A;"+nl+LOOKUP_DEFAULT,1)
    # Put the external declaration before ALL original host code. A direct
    # frontier call can occur earlier than the pack lookup definition.
    staged=prefix+before+anchor+after
    # Rewire the exact original direct-frontier call if main owns that caller.
    count=staged.count(FRONTIER)
    staged=staged.replace(FRONTIER,CALL_REPLACEMENT)
    if staged.count("case 0x002A3A5Au:")!=1:
        raise ValueError("New guest exact pack lookup not unique")
    return staged,count

def patch_tu(text:str,change_calls:bool,add_body:str|None)->tuple[str,int]:
    if TAG in text or "PIXEL A3A5A ENTRY" in text:
        raise ValueError("Existing modified TrueTU not reusable with new source")
    nl=nl_for(text)
    count=text.count(FRONTIER)
    patched=text.replace(FRONTIER,CALL_REPLACEMENT) if change_calls else text
    if change_calls and count:
        # The stage must make the restored function visible in the calling TU.
        include='#include "translated_runtime.h"'
        if include in patched:
            patched=patched.replace(include,include+nl+PROTOTYPE,1)
        else:
            # Prototypes may already be inherited via another header, but
            # avoid guessing position/order. Caller/TU must declare it.
            raise ValueError("Caller TrueTU lacks recognized runtime include")
    if add_body is not None:
        # Restoring the direct call above may have just inserted an
        # external forward declaration. Only a full function BODY is a
        # duplicate; never mistake a declaration for a definition.
        existing_bodies=[
            m for m in DEFINITION.finditer(patched)
            if int(m.group(1),16)==TARGET
        ]
        if existing_bodies:
            raise ValueError("New owner already defines A3A5A")
        include='#include "translated_runtime.h"'
        if include not in patched:
            raise ValueError("Guest function owner has no TrueTU runtime include")
        # The original function calls three separately compiled TrueTU
        # functions. Explicit external declarations preserve their linkage
        # without changing the shared runtime header / rebuilding 64 TUs.
        declarations=nl.join("void "+name+"(void);" for name in EXACT_CALLS)
        patched=patched.replace(include,include+nl+declarations,1)
        patched=patched.rstrip("\r\n")+nl+nl+"/* "+TAG+": real generated function */"+nl+add_body+nl
    return patched,(count if change_calls else 0)

def stage(args:argparse.Namespace)->dict:
    baseline=args.k1s_shards.resolve()
    manifest=args.k1s_manifest.resolve()
    main_path=args.main.resolve()
    generated=args.generated.resolve()
    report=args.proof.resolve()
    dest=args.out.resolve()
    outmain=args.out_main.resolve()
    if (dest==baseline or baseline in dest.parents or dest in baseline.parents or
        outmain in baseline.parents or outmain==main_path or
        dest==main_path.parent or outmain in dest.parents or
        outmain in {generated,report,manifest}):
        raise ValueError("PIXEL outputs must not overwrite original K1S or generated source")
    record=json.loads(manifest.read_text(encoding="utf-8-sig"))
    if (record.get("marker")!=BASE or record.get("status")!="STAGED_ONLY_NO_XDK_BUILD"
        or record.get("translated_shards")!=64
        or record.get("modified_from_k1r")!=["translated_044.cpp"]
        or record.get("unchanged_from_k1r")!=63
        or record.get("hard_fences")!="UNCHANGED"
        or Path(record.get("staged_directory","MISSING")).resolve()!=baseline):
        raise ValueError("K1S original 64-TU provenance gate failed")
    files=sorted(p for p in baseline.iterdir() if SOURCE_FILES.fullmatch(p.name))
    headers=sorted(baseline.glob("*.h"))
    if len(files)!=64 or not any(p.name=="translated_runtime.h" for p in headers):
        raise ValueError("Expected original K1S 64 TrueTUs and all headers")
    if sha(baseline/"translated_044.cpp")!=record.get("staged_owner_sha256"):
        raise ValueError("K1S saved ESI correction SHA missing or changed")
    if "K1S HALGETVECTOR44 ESI SLOT:" not in (
            baseline/"translated_044.cpp").read_text(encoding="utf-8"):
        raise ValueError("K1S verified Xbox register fix missing")
    proof=report.read_text(encoding="utf-8-sig")
    if not all(x in proof for x in (
        "PIXEL CONTRACT PROOF", "Generated file=recomp_0013.c",
        f"SHA256={ORIGINAL_SHA}",
        "Source original function=sub_002A3A5A line=42763",
        "recomp_apu_read32: 2 callsites",
        "recomp_apu_write32: 6 callsites",
        "phase6ch_apu_read32: 0 callsites",
        "phase6ch_apu_write32: 0 callsites",
        "0x0022B150", "0x0022B178", "0x0022DDA4",
    )):
        raise ValueError("Expected full user-local APU source proof missing")
    if generated.name!=ORIGINAL_FILE or sha(generated)!=ORIGINAL_SHA:
        raise ValueError("Original generated A3A5A C file SHA or filename mismatch")
    original=find_body(generated.read_text(encoding="utf-8"),NAME)
    if "void "+NAME+"(void)" not in original:
        raise ValueError("Target missing from correct original C file")
    guest_body,body_metrics=budgeted_body(original,"\n")
    main=main_path.read_bytes().decode("utf-8")
    runtime=(baseline/"translated_runtime.h").read_bytes().decode("utf-8")
    validate_apu_bridge(main,runtime)
    staged_main,main_edges=patch_main(main)
    original_hashes={p.name:sha(p) for p in [*files,*headers]}
    if (len(re.findall(r"(?m)^void (sub_[0-9A-Fa-f]{8})\(void\)",guest_body))!=1
        or not guest_body.startswith("void sub_002A3A5A(void)")):
        raise ValueError("Function staging contains anything except A3A5A")
    # The original function's three direct subcalls all exist in EXACTLY
    # one original K1S compiled body; no fabricated return stubs.
    known={}
    for func in EXACT_CALLS:
        body_entries=[]
        pat=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+"
                       +re.escape(func)+r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
        for p in files:
            text=p.read_text(encoding="utf-8")
            if pat.search(text):
                body_entries.append((p.name,len(pat.findall(text))))
        if len(body_entries)!=1 or body_entries[0][1]!=1:
            raise ValueError("A3A5A direct callee not uniquely compiled in K1S: "+func)
        if re.search(r"(?m)^[ \t]*static[ \t]+void[ \t]+"+func+r"\(",(
            baseline/body_entries[0][0]).read_text(encoding="utf-8")):
            raise ValueError("Cross-TU function is static (no external linkage): "+func)
        known[func]=body_entries[0][0]
    caller_files={}
    original_text={}
    for p in files:
        text=p.read_bytes().decode("utf-8")
        original_text[p.name]=text
        count=text.count(FRONTIER)
        if count:
            caller_files[p.name]=count
    caller_total=main_edges+sum(caller_files.values())
    if caller_total<1:
        raise ValueError("No exact original A3A5A DIRECT_FRONTIER callsite found; cannot wire new function")
    # Add function to an existing caller TU when possible to avoid increasing
    # the number of compilation units; pick smallest caller, stable ties.
    owner=min(caller_files,key=lambda k:(-caller_files[k],len(original_text[k]),k)
              ) if caller_files else "translated_063.cpp"
    if any(int(m.group(1),16)==TARGET
           for m in DEFINITION.finditer(original_text[owner])):
        raise ValueError("A3A5A original owner already has a complete function body")
    # Header stays byte-identical: only changed caller TUs plus one new body
    # and a small central main lookup case incur incremental recompilation.
    updated={}
    for p in files:
        copy=original_text[p.name]
        new,edge_count=patch_tu(copy,True,guest_body.replace("\n",nl_for(copy))
                                if p.name==owner else None)
        if edge_count!=caller_files.get(p.name,0):
            raise ValueError("Wrong number of direct caller rewrites in "+p.name)
        if new!=copy:
            updated[p.name]=new.encode("utf-8")
    if len(updated)>12:
        raise ValueError("Unexpectedly broad caller fanout; do not trigger large recompilation")
    if not any("PIXEL A3A5A ENTRY" in payload.decode("utf-8")
               for payload in updated.values()):
        raise ValueError("New original function not installed in chosen TrueTU")
    source_files=[*files,*headers]
    expected={p.name:updated.get(p.name,p.read_bytes()) for p in source_files}
    if dest.exists() and any(dest.iterdir()):
        if {p.name for p in dest.iterdir()}!=set(expected):
            raise ValueError("Previous PIXEL staged TrueTU file inventory differs")
        for name,payload in expected.items():
            if (dest/name).read_bytes()!=payload:
                raise ValueError("Previous PIXEL TrueTU differs: "+name)
        print("[PIXEL-BUILD] REUSE PASS: source-identical staged 64 TrueTUs")
    else:
        dest.mkdir(parents=True,exist_ok=True)
        for p in source_files:
            if p.name in updated:
                (dest/p.name).write_bytes(updated[p.name])
            else:
                shutil.copy2(p,dest/p.name)
    staged_main_bytes=staged_main.encode("utf-8")
    if outmain.exists() and outmain.read_bytes()!=staged_main_bytes:
        raise ValueError("Prior PIXEL main.cpp staged source differs")
    outmain.parent.mkdir(parents=True,exist_ok=True)
    outmain.write_bytes(staged_main_bytes)
    if (any(sha(p)!=original_hashes[p.name] for p in source_files)
        or sha(main_path)!=digest(main.encode("utf-8"))):
        raise ValueError("Original K1S/K1C provenance modified by staging")
    manifest_out={
        "marker":TAG,"status":"STAGED_ONLY_NO_XDK_BUILD",
        "baseline_shards":str(baseline),"staged_shards":str(dest),
        "baseline_main":str(main_path),"staged_main":str(outmain),
        "translated_shards":64,"new_guest_function":f"0x{TARGET:08X}",
        "original_local_generated_file":ORIGINAL_FILE,
        "original_local_generated_sha":ORIGINAL_SHA,
        "new_guest_function_owner":owner,
        "caller_main_sites":main_edges,
        "caller_tu_sites":caller_files,
        "direct_callee_owners":known,
        "patched_true_tu_files":sorted(updated),
        "unchanged_true_tus":64-len(updated),
        "headers_byte_identical":True,
        "preserved_k1s_esi_fix":True,
        "applied_apu_bridge":"phase6ch_apu_read32/write32",
        "apu_macro_route":"DSOUND GUEST_READ/WRITE8/16/32 -> phase6ch_apu_*",
        "guest_display_call_injected":False,
        "guest_memory_fences":"UNCHANGED",
        "mmio_fences":"UNCHANGED",
        "body_metrics":body_metrics,
        "original_owner_hashes":original_hashes,
        "new_owner_hashes":{name:digest(payload) for name,payload in updated.items()},
        "original_main_sha":digest(main.encode("utf-8")),
        "staged_main_sha":digest(staged_main_bytes),
    }
    output=dest.parent/"pixel-a3a5a-batch-manifest.json"
    output.write_text(json.dumps(manifest_out,indent=2)+"\n",encoding="utf-8")
    return manifest_out

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--k1s-shards",type=Path,required=True)
    p.add_argument("--k1s-manifest",type=Path,required=True)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--generated",type=Path,required=True)
    p.add_argument("--proof",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    p.add_argument("--out-main",type=Path,required=True)
    a=p.parse_args()
    m=stage(a)
    print("[PIXEL-BUILD] STAGING PASS: 002A3A5A original translated DSOUND body")
    print("[PIXEL-BUILD] Source read/write32 calls routed through existing APU bridges")
    print("[PIXEL-BUILD] Real caller edges=%u, owner=%s, changed TrueTUs=%u"%(
        m["caller_main_sites"]+sum(m["caller_tu_sites"].values()),
        m["new_guest_function_owner"],len(m["patched_true_tu_files"])))
    print("[PIXEL-BUILD] Existing 3 direct callees located, all headers and K1S ESI fix preserved")
    print("[PIXEL-BUILD] No unknown MMIO/VP read relaxation; display_calls not touched")
    print("[PIXEL-BUILD] NO XDK build; manifest="+str(a.out.parent/"pixel-a3a5a-batch-manifest.json"))

if __name__=="__main__":
    main()
