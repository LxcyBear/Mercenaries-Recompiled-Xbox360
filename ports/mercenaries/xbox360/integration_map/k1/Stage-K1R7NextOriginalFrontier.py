#!/usr/bin/env python3
"""R7: add source-authentic hardware DIRECT 00222190 and clean direct dependencies.

Input is EXACT source-only r5 retail-restored derived main + its untouched
64 TrueTUs. The new stage never overwrites r5. The original XBE and
retail-generated C prove original entry ownership; PC-only helpers
must be explicitly implemented or removed by verified retail restoration,
NEVER guessed.

An extra runtime fingerprint prints inside the EXISTING hard-stop logger,
so xbWatson can prove which candidate was actually executed.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
import re
from collections import deque
from pathlib import Path

TARGET=0x00222190
RETAIL_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
R5_MARKER="K1-TEXT-DIRECT-002228C0-20261103"
R7_MARKER="K1-TEXT-DIRECT-00222190-20261103"
R5_STATUS="K1_TEXT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY_NO_XDK"
STATUS="K1_R7_222190_REAL_ORIGINAL_DIRECT_SOURCE_FINGERPRINT_NO_XDK"
PC_SHA="f513ae4e041401b7b032410016940971488d523b"
MAX_NEW=16
MAX_DEPTH=4
PRESERVE_LOOKUPS=(
    0x001F7620,0x001F7520,0x002228C0,
)
PRESERVE_TRACE=(
    "P6DQ ROCKET HARD STOP",
    "K1D3D SECOND: native Xenos Reset PASS",
    "K1STATE MAIN CHECKPOINT:",
    "P6DQ PIXEL CHASE",
)


def digest(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def load(path:Path,alias:str):
    spec=importlib.util.spec_from_file_location(alias,path)
    if not spec or not spec.loader:
        raise ValueError("Missing original maintained source helper "+str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def verify_parent(meta:dict,blob:bytes,shards:dict[str,bytes])->str:
    expected={
        "status":R5_STATUS,
        "marker":R5_MARKER,
        "original_retail_xbe_sha256":RETAIL_SHA,
        "original_function_address":"0x002228C0",
        "original_generated_c":"recomp_0011.c",
        "true_tu_count":64,
        "original_true_tus_unchanged":True,
        "runtime_header_unchanged":True,
        "six_case_verified_owner":"translated_052.cpp",
        "native_xenos_reset_source_preserved":True,
        "unknown_direct_and_indirect_hard_fences_preserved":True,
        "dummy_guest_data":False,
        "new_xdk_verified":False,
        "new_hardware_verified":False,
    }
    bad={k:(value,meta.get(k)) for k,value in expected.items()
         if meta.get(k)!=value}
    if bad:
        raise ValueError("Original r5 retail/Xbox fence parent mismatch "+repr(bad))
    if meta.get("new_main_sha256")!=digest(blob):
        raise ValueError("Derived r5 main.cpp differs from proven source manifest")
    if (len(shards)!=64 or
        meta.get("original_true_tu_hashes_sha256")!=
        {name:digest(content) for name,content in shards.items()}):
        raise ValueError("Original 64 Xbox translated TrueTUs changed")
    pc=meta.get("pc_developer_patch_reverted_to_original_retail",{})
    if (meta.get("pc_reference_git_commit")!=PC_SHA or
        pc.get("status")!="PINNED_PC_DEVELOPER_ONLY_PATCH_RESTORED_TO_RETAIL" or
        pc.get("arbitrary_helper_stub_used") is not False or
        pc.get("x86_retail_cmp_jne_proof",{}).get("original_002228f0_x86_cmp_jne") is not True):
        raise ValueError("Original 002228F0 retail CMP/JNE PC patch restoration proof absent")
    text=blob.decode("utf-8")
    if text.count("/* "+R5_MARKER+" */")!=1:
        raise ValueError("Original r5 marker duplicated/missing")
    if "recomp_dev_region_import_active()" in text:
        raise ValueError("PC-only developer region helper slipped into r5")
    for va in PRESERVE_LOOKUPS:
        source="case 0x%08Xu: return sub_%08X;"%(va,va)
        if text.count(source)!=1:
            raise ValueError("Previously routed original retail function missing: "+source)
    for marker in PRESERVE_TRACE:
        if not text.count(marker):
            raise ValueError("Preserved original diagnostics missing: "+marker)
    return text


def original_entry_proof(retail_xbe:Path,auditor_path:Path,functions:dict)->dict:
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    audit=load(auditor_path,"k1_r7_existing_retail_section_audit")
    blob,sections=audit.get_retail_sections(retail_xbe)
    data=audit.bytes_at(blob,sections,TARGET,24)
    inst=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(data,TARGET,count=3))
    if (len(inst)<2 or inst[0].address!=TARGET or
        any(i.mnemonic in ("int3","ud2") for i in inst) or
        any(i.address < TARGET or i.address >= functions[TARGET]["end"] for i in inst)):
        raise ValueError("Original retail XBE entry does not decode as valid 00222190 instructions")
    if not (0x00011000<=TARGET<functions[TARGET]["end"]<=0x00255620):
        raise ValueError("222190 retail .text function ownership/section invalid")
    return {
        "retail_sha256":RETAIL_SHA,
        "guest_entry":"0x00222190",
        "first_bytes_hex":data[:sum(i.size for i in inst)].hex().upper(),
        "original_x86_instructions":[{"va":"0x%08X"%i.address,
                                      "mnemonic":i.mnemonic,"op_str":i.op_str} for i in inst],
    }


def direct_closure(generated:dict,compiled:set[int],base)->tuple[list[int],list[str]]:
    if TARGET not in generated or TARGET in compiled:
        raise ValueError("New frontier is not missing standalone original C")
    names={item["name"]:va for va,item in generated.items()}
    selected=[]
    queue=deque([(TARGET,0)])
    seen=set()
    frontier=[]
    while queue:
        va,depth=queue.popleft()
        if va in seen or va in compiled:
            continue
        seen.add(va)
        if va not in generated:
            raise ValueError("No original generated source for dependency %08X"%va)
        if len(selected)==MAX_NEW:
            frontier.append("0x%08X"%va)
            continue
        selected.append(va)
        calls=base.CALL_RE.findall(base.mask_noncode(generated[va]["source"]))
        deps=sorted({names[name] for name in calls
                     if name in names and names[name] not in compiled})
        if depth>=MAX_DEPTH:
            frontier.extend("0x%08X"%d for d in deps)
        else:
            queue.extend((v,depth+1) for v in deps)
    if not selected or selected[0]!=TARGET:
        raise ValueError("Missing original 00222190 root was not selected first")
    return selected, sorted(set(frontier))


def add_hardware_fingerprint(source:str,parent_source:str)->tuple[str,str]:
    """Only new operation outside the source pack: an inert diagnostic trace.

    Place the tag INSIDE the maintained hard-stop function (not a
    metadata string or a dead const). The Xbox emits this at a hard stop.
    No changes to original guest registers, return values, D3D or APU.
    """
    start_pat=re.compile(r"static void phase6dq_note_hard_stop\s*\(")
    matches=list(start_pat.finditer(source))
    if len(matches)!=1:
        raise ValueError("Original rocket hard-stop logger not uniquely found")
    loc=matches[0].end()
    opener=source.find("{",loc)
    if opener<0 or opener-loc>180:
        raise ValueError("Hard-stop logger body signature changed")
    close=source.find("static void ",opener+1)
    if close<0:
        close=len(source)
    body=source[opener+1:close]
    if body.count("P6DQ ROCKET HARD STOP kind=")!=1:
        raise ValueError("Original hardware hard-stop logger no longer matches verified format")
    if body.count("trace(line);")<2:
        raise ValueError("Original hard-stop logger no longer reports both trace records")
    seed=digest(source.encode("utf-8"))[:16].upper()
    marker="K1-R7-222190-XEX-PROOF-"+seed
    injection="\n    trace(\""+marker+"\"); /* K1-R7 real hardware build fingerprint */"
    output=source[:opener+1]+injection+source[opener+1:]
    if output.count(marker)!=1 or parent_source.count(marker)!=0:
        raise ValueError("Runtime proof string duplicate or leaked to r5")
    if source[:opener+1]!=output[:opener+1] or source[opener+1:]!=output[opener+1+len(injection):]:
        raise ValueError("Non-logger source changed during fingerprint instrumentation")
    return output,marker


def stage(a):
    parent_blob=a.parent.read_bytes()
    parent_meta_blob=a.parent_manifest.read_bytes()
    parent_meta=json.loads(parent_meta_blob.decode("utf-8-sig"))
    shard_files=sorted(a.shards.glob("translated_???.cpp"))
    if len(shard_files)!=64 or not (a.shards/"translated_runtime.h").is_file():
        raise ValueError("Original 64 translated TrueTUs/runtime header not available")
    shard_blobs={p.name:p.read_bytes() for p in shard_files}
    parent=verify_parent(parent_meta,parent_blob,shard_blobs)
    base=load(a.base,"k1_r7_original_base")
    bb=load(a.bb,"k1_r7_original_bb")
    bc=load(a.bc,"k1_r7_original_bc")
    previous=load(a.previous,"k1_r7_original_owner_inventory")
    packer=load(a.packer,"k1_r7_original_two_root_packer")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated,by_name)
    classify=previous.classify(TARGET,by_va,generated)
    if (classify.get("kind")!="exact_source_entry" or
        classify.get("owner")!="0x00222190" or
        TARGET not in generated):
        raise ValueError("Hardware 222190 direct frontier is not standalone retail original generated C: "+repr(classify))
    entry=original_entry_proof(a.retail_xbe,a.retail_auditor,by_va)
    if generated[TARGET]["file"]!="recomp_0011.c":
        raise ValueError("Original 00222190 generated source file unexpectedly changed")
    _,info=previous.owner_inventory(parent,a.shards)
    compiled=info["compiled_in_64_or_main"]
    if (TARGET in compiled or TARGET in info["main_pack_lookup_vas"] or
        any(va not in compiled for va in PRESERVE_LOOKUPS)):
        raise ValueError("Cannot duplicate target or lost previous original main roots")
    members,frontier=direct_closure(generated,compiled,base)
    # No PC-only fabricated helpers: exact generated C is passed directly
    # through the maintained existing packer with full support resolution.
    packer.ROOT=TARGET
    packer.MEMBERS=tuple(members)
    packer.MARKER=R7_MARKER
    packer.OPT_PLACEHOLDER="/* K1_R7_00222190_OPT_ON_HIDDEN */"
    support=base.support_symbols
    externals={"sub_%08X"%va for va in compiled}
    externals.update(support((a.shards/"translated_runtime.h").read_text(
        encoding="utf-8",errors="replace")))
    base.support_symbols=lambda t:support(t)|externals
    output,rewritten_frontiers,pruned=packer.pack(
        parent,generated,compiled,base,bb,bc)
    if pruned or output.count("/* "+R7_MARKER+" */")!=1:
        raise ValueError("Original 00222190 direct dependency C pack rejected; NO XDK")
    for va in members:
        lookup="case 0x%08Xu: return sub_%08X;"%(va,va)
        if output.count(lookup)!=1:
            raise ValueError("Missing/duplicate real original generated C lookup: "+lookup)
    for v in PRESERVE_TRACE:
        if output.count(v)!=parent.count(v):
            raise ValueError("Original D3D/APU/rocket logger changed: "+v)
    for va in PRESERVE_LOOKUPS:
        lookup="case 0x%08Xu: return sub_%08X;"%(va,va)
        if output.count(lookup)!=parent.count(lookup):
            raise ValueError("Original r5 previous retail lookup regression: "+lookup)
    if "recomp_dev_region_import_active()" in output:
        raise ValueError("Original r5 PC-only developer patch accidentally reintroduced")
    if output.count("K1D3D SECOND: native Xenos Reset PASS")!=parent.count(
        "K1D3D SECOND: native Xenos Reset PASS"):
        raise ValueError("Native Xenos Reset source changed")
    output,fingerprint=add_hardware_fingerprint(output,parent)
    blob=output.encode("utf-8")
    meta={
        "status":STATUS,
        "marker":R7_MARKER,
        "retail_sha256":RETAIL_SHA,
        "original_entry_proof":entry,
        "r5_source_sha256":digest(parent_blob),
        "r5_manifest_sha256":digest(parent_meta_blob),
        "r7_source_sha256":digest(blob),
        "new_original_generated_C":["0x%08X"%va for va in members],
        "new_original_generated_C_count":len(members),
        "original_C_inputs_sha256":{
            "0x%08X"%va:digest(generated[va]["source"].encode("utf-8"))
            for va in members},
        "new_source_direct_frontiers":[
            "0x%08X"%va for va in sorted(set(
                [int(x,16) for x in frontier]+list(rewritten_frontiers)))],
        "runtime_xex_fingerprint":fingerprint,
        "runtime_xex_fingerprint_location":"phase6dq_note_hard_stop",
        "original_64_true_tu_sha256":{n:digest(b) for n,b in shard_blobs.items()},
        "original_64_true_tus_unchanged":True,
        "original_sixcase_owner":"translated_052.cpp",
        "retail_002228F0_branch_restoration_preserved":True,
        "previous_r4_hardware_fences_preserved":True,
        "new_build_and_hardware_verified":False,
        "new_guest_display_calls":None,
        "no_dummy_abi_or_pc_helper_stubs":True,
        "hard_stop_for_unproven_guest_targets_preserved":True,
        "source_only":True,
        "safe_to_claim_guest_pixels":False,
    }
    if (a.output.resolve()==a.parent.resolve() or
        a.output.parent.resolve()==a.parent.parent.resolve()):
        raise ValueError("Refuse overwrite of r5 or adjacent original staging directory")
    a.output.parent.mkdir(parents=True,exist_ok=True)
    dest=((a.output,blob),(a.manifest,(json.dumps(meta,indent=2)+"\n").encode("utf-8")))
    for path,body in dest:
        if path.exists() and path.read_bytes()!=body:
            raise ValueError("Existing r7 source/manifest differs; no silent overwrite: "+str(path))
        if not path.exists():
            path.write_bytes(body)
    if parent_blob!=a.parent.read_bytes() or parent_meta_blob!=a.parent_manifest.read_bytes():
        raise ValueError("Original r5 main/manifest mutated during derived stage")
    if any(p.read_bytes()!=shard_blobs[p.name] for p in shard_files):
        raise ValueError("An original 64 TrueTU was modified")
    print("[K1-R7] RETAIL 00222190 exact original .text/XBE instruction proof PASS")
    print("[K1-R7] Original C packed members=%d, direct guarded exits=%d" %
          (len(members),len(meta["new_source_direct_frontiers"])))
    print("[K1-R7] Original six-case D3D/Xenos Reset/audio plus all 64 TrueTUs unchanged")
    print("[K1-R7] PC developer import restored in r5; no dummy helper or fake pixel path")
    print("[K1-R7] Runtime xbWatson hardware fingerprint: "+fingerprint)
    print("[K1-R7] Original source-only output: "+str(a.output))
    print("[K1-R7] NO XDK YET. NO PIXELS OR TICK GAIN CLAIMED.")


def selftest():
    parent={
        "status":R5_STATUS,
        "marker":R5_MARKER,
        "original_retail_xbe_sha256":RETAIL_SHA,
        "original_function_address":"0x002228C0",
        "original_generated_c":"recomp_0011.c",
        "true_tu_count":64,
        "original_true_tus_unchanged":True,
        "runtime_header_unchanged":True,
        "six_case_verified_owner":"translated_052.cpp",
        "native_xenos_reset_source_preserved":True,
        "unknown_direct_and_indirect_hard_fences_preserved":True,
        "dummy_guest_data":False,
        "new_xdk_verified":False,
        "new_hardware_verified":False,
        "pc_reference_git_commit":PC_SHA,
        "pc_developer_patch_reverted_to_original_retail":{
            "status":"PINNED_PC_DEVELOPER_ONLY_PATCH_RESTORED_TO_RETAIL",
            "arbitrary_helper_stub_used":False,
            "x86_retail_cmp_jne_proof":{
                "original_002228f0_x86_cmp_jne":True,
            },
        },
    }
    fixture=(
        "/* "+R5_MARKER+" */\n"+
        "\n".join("case 0x%08Xu: return sub_%08X;"%(va,va)
                  for va in PRESERVE_LOOKUPS)+"\n"+
        "\n".join(PRESERVE_TRACE)+"\n"+
        "static void phase6dq_note_hard_stop(uint32_t kind)\n"
        "{\n"
        "    char line[448];\n"
        "    sprintf(line, \"P6DQ ROCKET HARD STOP kind=%u\",kind);\n"
        "    trace(line);\n"
        "    trace(line);\n"
        "}\n"
    ).encode("utf-8")
    shards={"translated_%03d.cpp"%i:b"fixture" for i in range(64)}
    parent["new_main_sha256"]=digest(fixture)
    parent["original_true_tu_hashes_sha256"]={
        k:digest(v) for k,v in shards.items()}
    txt=verify_parent(parent,fixture,shards)
    out,mark=add_hardware_fingerprint(txt,txt)
    assert mark.startswith("K1-R7-222190-XEX-PROOF-")
    assert out.count(mark)==1 and out.count("trace(line);")==2
    for broken in (
        {**parent,"new_main_sha256":"not verified"},
        {**parent,"dummy_guest_data":True},
        {**parent,"pc_developer_patch_reverted_to_original_retail":{"status":"FAKE"}},
    ):
        try:
            verify_parent(broken,fixture,shards)
        except ValueError:
            pass
        else:
            raise AssertionError("Unsafe original parent allowed")
    try:
        add_hardware_fingerprint(txt.replace("P6DQ ROCKET HARD STOP kind=",
                                             "K1 SCHEMA MOVED"),txt)
    except ValueError:
        pass
    else:
        raise AssertionError("Original hard stop source missing yet accepted")
    # Closure must include missing direct target + original C callee but
    # not a compiled original C body.
    class Base:
        CALL_RE=re.compile(r"\b([A-Za-z_]\w*)\s*\(")
        mask_noncode=staticmethod(lambda s:s)
    generated={
        TARGET:{"name":"sub_00222190","source":"void sub_00222190(void) { sub_002221A0(); }"},
        TARGET+16:{"name":"sub_002221A0","source":"void sub_002221A0(void) { sub_002221B0(); }"},
        TARGET+32:{"name":"sub_002221B0","source":"void sub_002221B0(void) {return;}"},
    }
    members,frontiers=direct_closure(generated,{TARGET+32},Base)
    assert members==[TARGET,TARGET+16] and not frontiers
    print("[K1-R7] SELFTEST PASS: exact r5 source/64 TrueTU contract, original frontier closure, real runtime fingerprint, hard-stop intact")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for key in ("parent","parent-manifest","shards","base","bb","bc",
                "previous","packer","retail-xbe","retail-auditor",
                "functions","generated","output","manifest"):
        p.add_argument("--"+key,type=Path)
    a=p.parse_args()
    if a.self_test:
        selftest()
        return
    for key in ("parent","parent_manifest","shards","base","bb","bc",
                "previous","packer","retail_xbe","retail_auditor",
                "functions","generated","output","manifest"):
        if getattr(a,key) is None:
            p.error("Missing --"+key.replace("_","-"))
    stage(a)


if __name__=="__main__":
    main()
