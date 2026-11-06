#!/usr/bin/env python3
"""K1-V6r: prove hardware DIRECT 0022FA9E and stage original C only if safe.

No guest helper stubs, no hand-written x86 ABI, no unknown target skipping.
Uses the already-maintained retail function inventory/packer; source-only,
and refuses unsafe interior labels, incomplete dependency closure and drift.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys
from collections import deque
from pathlib import Path
TARGET=0x0022FA9E
BASELINE=61948779
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PARENT_STAGE="V6Q_NATIVE_WATSON_FILTER_SOURCE_UNTESTED"
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
ORIG=ROOT/"build/phase3n_final_abi_scale"
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_native_watson_v6q"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_direct_22fa9e_v6r"
MARK="K1-V6R-0022FA9E-REAL-RETAIL-C-20261105"
FUNC=re.compile(r'(?m)^\s*(?:static\s+)?void\s+(sub_[0-9A-Fa-f]{8})\s*\(\s*void\s*\)\s*\{')
CASE=re.compile(r'\bcase\s+0x([0-9A-Fa-f]{8})u\s*:\s*return\s+(sub_[0-9A-Fa-f]{8})\s*;')
LOOKUP=re.compile(r'(?m)^(?:static[ \t]+)?recomp_func_t phase4c_lookup_pack_func\(uint32_t xbox_va\)\n\{')
CANON="static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
OPT='#pragma optimize("", on)'
PLACE="/* K1_V6R_PACK_OPT_ON_HIDDEN */"
def sha(b):return hashlib.sha256(b).hexdigest()
def require(ok,msg):
    if not ok:raise ValueError(msg)
def load(p,name):
    spec=importlib.util.spec_from_file_location(name,p)
    require(spec is not None and spec.loader is not None,"Missing maintained module: "+str(p))
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod);return mod
def verify():
    m=json.loads((PARENT/"v6q-manifest.json").read_text(encoding="utf-8-sig"))
    raw=(PARENT/"main.cpp").read_bytes()
    require(m.get("stage")==PARENT_STAGE and m.get("source_sha256")==sha(raw),"V6q source provenance mismatch")
    require(m.get("apc_seven_read_source_preserved") is True and m.get("retail_17a120_preserved") is True
            and m.get("changed_guest_instruction_logic") is False,"V6q guest/APC invariant lost")
    shards=sorted(SHARDS.glob("translated_???.cpp"))
    require(len(shards)==64 and (SHARDS/"translated_runtime.h").is_file(),"64 TrueTUs/runtime header missing")
    hashes={p.name:sha(p.read_bytes()) for p in shards}
    require(hashes==m.get("true_tu_sha256"),"64 TrueTU hashes mismatch")
    require("K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105" in raw.decode("utf-8"),"V6o live fix marker absent")
    require("P6DQ ROCKET HARD STOP" in raw.decode("utf-8"),"Hard-stop logger absent")
    require("K1-V6b APC QUEUED" in raw.decode("utf-8"),"Proven APC queue path absent")
    require("K1D3D SECOND: native Xenos Reset PASS" in raw.decode("utf-8"),"Native Reset path absent")
    cache=ORIG/"analysis/disasm/.disasm_cache.json"
    require(cache.is_file(),"Retail disassembly cache missing")
    c=json.loads(cache.read_text(encoding="utf-8-sig"))
    require(c.get("xbe_hash","").upper()==RETAIL,"Retail XBE SHA cache mismatch")
    return raw,m,hashes
def stage():
    raw,m,hashes=verify()
    base=load(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py","k1v6r_base")
    bb=load(ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bb_frontier22dda4.py","k1v6r_bb")
    bc=load(ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bc_broad_sweep.py","k1v6r_bc")
    planner=load(K1/"Plan-K1NextICallBatch.py","k1v6r_owner")
    by_va,by_name=base.load_ranges(ORIG/"analysis/disasm/functions.json")
    generated=base.load_generated(ORIG/"runtime/gen",by_name)
    origin=planner.classify(TARGET,by_va,generated)
    print("[K1-V6r] RETAIL target class=%s owner=%s source=%s"%(origin["kind"],origin["owner"],origin["source_file"]))
    require(origin["kind"]=="exact_source_entry","Not an exact function entry; interior VA requires separate ABI/label repair")
    require(0x00011000<=TARGET<by_va[TARGET]["end"]<=0x00255620,"Function outside original retail .text")
    original=raw.decode("utf-8").replace("\r\n","\n")
    owner,info=planner.owner_inventory(original,SHARDS)
    compiled=info["compiled_in_64_or_main"]
    require(TARGET not in compiled and TARGET not in info["main_pack_lookup_vas"],"Function already compiled/routed: audit dispatch instead")
    require(MARK not in original,"Already staged V6r")
    require(len(LOOKUP.findall(original))==1,"Pack-lookup declaration not uniquely recognized")
    names={v["name"]:k for k,v in generated.items()}
    q=deque([(TARGET,0)]);seen=set();members=[];missing=[];cap=16
    while q:
        va,depth=q.popleft()
        if va in seen or va in compiled:continue
        seen.add(va)
        require(va in generated,"Missing original generated C for 0x%08X"%va)
        if len(members)>=cap:missing.append(va);continue
        require(va in by_va and by_va[va]["start"]==va,"Dependency not real retail entry: 0x%08X"%va)
        members.append(va)
        calls=set(base.CALL_RE.findall(base.mask_noncode(generated[va]["source"])))
        deps=sorted({names[x] for x in calls if x in names and names[x] not in compiled})
        if depth>=4:
            missing.extend(deps)
        else:
            q.extend((v,depth+1) for v in deps)
    require(not missing,"Dependency closure exceeds depth 4 / cap 16: "+",".join("0x%08X"%x for x in missing))
    require(members and members[0]==TARGET,"Missing original target root")
    print("[K1-V6r] ORIGINAL C closure: "+", ".join("%08X"%v for v in members))
    new=original.replace(LOOKUP.search(original).group(),CANON,1)
    require(new.count(CANON)==1 and OPT in new,"Cannot prepare canonical pack lookup")
    new=new.replace(OPT,PLACE)
    new+='\n#pragma optimize("", off)\n#pragma optimize("", on)\n'
    old_root=bc.SWEEP_ROOT;old_entry=bc.instrument_root_entry
    support=base.support_symbols
    available={"sub_%08X"%va for va in compiled}
    available.update(support((SHARDS/"translated_runtime.h").read_text(encoding="utf-8",errors="replace")))
    old_standard=base.STANDARD_CALLS.copy()
    try:
        bc.SWEEP_ROOT=TARGET
        bc.instrument_root_entry=lambda rendered,name:rendered
        base.support_symbols=lambda t:support(t)|available
        base.STANDARD_CALLS.update(("sin","cos"))
        packed,rendered,frontiers,pruned=bc.insert_pack_members(
            new,base,bb,generated,members,compiled|set(members),require_sweep_root=True)
    finally:
        bc.SWEEP_ROOT=old_root;bc.instrument_root_entry=old_entry
        base.support_symbols=support
        base.STANDARD_CALLS.clear();base.STANDARD_CALLS.update(old_standard)
    require(not pruned and all(va in rendered for va in members),"Packer rejected source dependencies: "+repr(pruned))
    require(packed.count(CANON)==1 and packed.count(PLACE)>=1,"Packer corrupted lookup/optimization guards")
    packed=packed.replace(CANON,LOOKUP.search(original).group(),1)
    packed=packed.replace(PLACE,OPT)
    for va in members:
        lookup="case 0x%08Xu: return sub_%08X;"%(va,va)
        require(packed.count(lookup)==1,"Missing exact original retail lookup: "+lookup)
    # Do not introduce an unknown-guest-target fallback or any fake return.
    for must in ("K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105",
                 "K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                 "K1D3D SECOND: native Xenos Reset PASS","P6DQ ROCKET HARD STOP"):
        require(packed.count(must)==original.count(must),"Inherited source drift: "+must)
    # Unique runtime fingerprint, at already-established hard-stop formatter.
    lit=re.compile(r'"P6DQ ROCKET HARD STOP kind=%u caller=%08X target=%08X[^"\n]*"')
    matches=list(lit.finditer(packed))
    require(len(matches)==1,"Cannot insert unique runtime XEX fingerprint")
    old=matches[0].group()
    finger="K1-V6R-RETAIL22FA9E-"+sha(packed.encode())[:12].upper()
    replacement=old[:-1]+" v6r_xex="+finger+'"'
    packed=packed.replace(old,replacement,1)
    require(len(replacement)<350,"Fingerprint risks overflowing hard-stop trace buffer")
    packed="/* "+MARK+" */\n"+packed
    result=packed.replace("\n","\r\n").encode("utf-8") if b"\r\n" in raw else packed.encode("utf-8")
    report={"stage":"V6R_RETAIL_DIRECT_0022FA9E_SOURCE_UNTESTED",
            "target":"0x0022FA9E","hardware_ticks_before":BASELINE,
            "parent_v6q_sha256":sha(raw),"source_sha256":sha(result),
            "retail_sha256":RETAIL,"true_tu_sha256":hashes,
            "retail_17a120_preserved":True,
            "original_generated_functions":["0x%08X"%v for v in members],
            "source_files":{("0x%08X"%v):generated[v]["file"] for v in members},
            "original_source_sha256":{("0x%08X"%v):sha(generated[v]["source"].encode()) for v in members},
            "unpacked_next_frontiers":["0x%08X"%v for v in sorted(frontiers)],
            "runtime_fingerprint":finger,"unknown_frontiers_fenced":True,
            "apc_reads_7_preserved_in_source":True,"hardware_tested":False}
    files=[(OUT/"main.cpp",result),
           (OUT/"v6r-manifest.json",(json.dumps(report,indent=2)+"\n").encode())]
    for p,b in files:require(not p.exists() or p.read_bytes()==b,"Staged output already differs: "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,b in files:
        if not p.exists():p.write_bytes(b)
    require((PARENT/"main.cpp").read_bytes()==raw,"V6q source drifted during stage")
    print("[K1-V6r] SOURCE PASS: authentic retail 0022FA9E + bounded dependency closure")
    print("[K1-V6r] XEX FINGERPRINT: "+finger)
    print("[K1-V6r] 7 APC source paths, D3D Reset, native Watson, hard fences, 64 TrueTUs preserved. NO XDK/HARDWARE PROOF YET")
if __name__=="__main__":
    try:stage()
    except Exception as exc:
        print("[K1-V6r] HARD FENCE: "+str(exc),file=sys.stderr)
        sys.exit(1)
