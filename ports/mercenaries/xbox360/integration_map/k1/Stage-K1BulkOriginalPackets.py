#!/usr/bin/env python3
"""Prepare an r6 source-only original-Xbox graphics/audio batch, NOT an XEX.

Consumes the pinned r4 global source-class packet plan but stages against
the r5 retail-restored *derived* main.cpp. Never changes the r5 main,
any TrueTU, the original runtime header, or the XDK output. All candidate
original C roots and their main lookup addresses must be unique and
support-clean. No source/ABI whitelists, no mock PC host return values.
"""
from __future__ import annotations

import argparse
import hashlib
import importlib.util
import json
from pathlib import Path

STATUS = "K1_ORIGINAL_BULK_GRAPHICS_R6_SOURCE_ONLY_XDK_BLOCKED"
MARK = "K1-ORIGINAL-SUPPORT-CLEAN-BULK-R6-20261103"
PARENT_MARK = "K1-TEXT-DIRECT-002228C0-20261103"
RETAIL = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
PC_SHA = "f513ae4e041401b7b032410016940971488d523b"


def sha(x: bytes) -> str:
    return hashlib.sha256(x).hexdigest()


def load(path, name):
    spec = importlib.util.spec_from_file_location(name, path)
    if not spec or not spec.loader:
        raise ValueError("Missing maintained original source module: "+str(path))
    m = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def verify_r5(meta, main: bytes, shards: dict[str, bytes]):
    checks = {
        "status": "K1_TEXT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY_NO_XDK",
        "marker": PARENT_MARK,
        "original_retail_xbe_sha256": RETAIL,
        "original_function_address": "0x002228C0",
        "original_generated_c": "recomp_0011.c",
        "source_only_staged_new_functions": 1,
        "original_r4_bodies_preserved": ["0x001F7620", "0x001F7520"],
        "true_tu_count": 64,
        "original_true_tus_unchanged": True,
        "runtime_header_unchanged": True,
        "six_case_verified_owner": "translated_052.cpp",
        "native_xenos_reset_source_preserved": True,
        "unknown_direct_and_indirect_hard_fences_preserved": True,
        "dummy_guest_data": False,
        "new_xdk_verified": False,
        "new_hardware_verified": False,
    }
    errors = {k:(v,meta.get(k)) for k,v in checks.items()
              if meta.get(k)!=v}
    if errors:
        raise ValueError("Original r5 unmodified source/guest hard fence proof: "+repr(errors))
    if meta.get("new_main_sha256") != sha(main):
        raise ValueError("r5 main is not the original source staging artifact")
    if (meta.get("pc_reference_git_commit") != PC_SHA or
        meta.get("pc_developer_patch_reverted_to_original_retail",{}).get("status") !=
        "PINNED_PC_DEVELOPER_ONLY_PATCH_RESTORED_TO_RETAIL" or
        meta.get("pc_developer_patch_reverted_to_original_retail",{}).get("arbitrary_helper_stub_used") is not False or
        meta.get("pc_developer_patch_reverted_to_original_retail",{}).get(
            "x86_retail_cmp_jne_proof",{}).get("original_002228f0_x86_cmp_jne") is not True):
        raise ValueError("Original r5 PC-only developer patch not proven retail-reverted")
    if len(shards)!=64 or {name:sha(data) for name,data in shards.items()} != meta.get("original_true_tu_hashes_sha256"):
        raise ValueError("64 original TrueTUs differ from r5 input source")
    source=main.decode("utf-8", errors="replace")
    for x in ("/* "+PARENT_MARK+" */",
              "case 0x001F7620u: return sub_001F7620;",
              "case 0x001F7520u: return sub_001F7520;",
              "case 0x002228C0u: return sub_002228C0;"):
        if source.count(x)!=1:
            raise ValueError("Original r5 retail source/lookup lost or duplicated: "+x)
    # Diagnostics are allowed to occur multiple times in the original
    # hardware-working inherited source; never change their occurrence count.
    for diagnostic in ("K1D3D SECOND: native Xenos Reset PASS",
                       "P6DQ ROCKET HARD STOP", "K1STATE MAIN CHECKPOINT:"):
        if source.count(diagnostic)<1:
            raise ValueError("Original hardware diagnostic/fence lost: "+diagnostic)
    if "recomp_dev_region_import_active()" in source:
        raise ValueError("Unjustified PC developer hook has returned in r5 main")
    return source


def stage(a):
    parent_bytes=a.parent.read_bytes()
    manifest_bytes=a.parent_manifest.read_bytes()
    parent_meta=json.loads(manifest_bytes.decode("utf-8-sig"))
    shard_paths=sorted(a.shards.glob("translated_???.cpp"))
    if not (a.shards/"translated_runtime.h").is_file():
        raise ValueError("Missing original compiled runtime header")
    shard_blobs={p.name:p.read_bytes() for p in shard_paths}
    source=verify_r5(parent_meta,parent_bytes,shard_blobs)
    packets=json.loads(a.packet_plan.read_text(encoding="utf-8-sig"))
    if (packets.get("status") !=
        "K1_GLOBAL_MISSING_ORIGINAL_SOURCE_BATCH_PACKETS_NO_XDK" or
        packets.get("original_retail_xbe_sha256")!=RETAIL or
        packets.get("pinned_pc_commit")!=PC_SHA or
        packets.get("original_64_true_tus_modified") is not False or
        packets.get("safe_to_deploy_unverified_xex") is not False or
        packets.get("xdk_invoked") is not False):
        raise ValueError("Original source 404-packet map provenance changed")
    candidates=[int(x,16) for x in packets.get(
        "source_clean_eligible_members_selected",[])]
    if not candidates or len(candidates)>24 or len(set(candidates))!=len(candidates):
        raise ValueError("Original bounded source packet is empty/duplicate/too large")
    base=load(a.base,"k1_r6_original_base")
    bb=load(a.bb,"k1_r6_original_bb")
    bc=load(a.bc,"k1_r6_original_bc")
    prev=load(a.previous,"k1_r6_original_owner_inventory")
    packer=load(a.packer,"k1_r6_previous_support_clean_packer")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated,by_name)
    original,info=prev.owner_inventory(source,a.shards)
    compiled=info["compiled_in_64_or_main"]
    if (any(x in compiled or x not in generated or x not in by_va
            for x in candidates) or
        0x002228C0 not in compiled or 0x001F7620 not in compiled or
        0x001F7520 not in compiled):
        raise ValueError("Selected original functions duplicated, absent or missing r5 roots")
    real_input_hashes = {"0x%08X"%va:sha(generated[va]["source"].encode("utf-8"))
                         for va in candidates}
    # The source-only planner's content hashes must still match this source.
    plan_hashes = {}
    for row in packets.get("bounded_source_clean_packet_candidates",[]):
        plan_hashes.update(row.get("original_generated_c_sha256",{}))
    for va in candidates:
        key="0x%08X"%va
        if plan_hashes.get(key)!=real_input_hashes[key]:
            raise ValueError("Source packet candidate hash differs from original C: "+key)
    support=base.support_symbols
    originals={"sub_%08X"%va for va in compiled}
    header=(a.shards/"translated_runtime.h").read_text(
        encoding="utf-8",errors="replace")
    originals.update(support(header))
    base.support_symbols=lambda text: support(text)|originals
    packer.ROOT=candidates[0]
    packer.MEMBERS=tuple(candidates)
    packer.MARKER=MARK
    packer.OPT_PLACEHOLDER="/* K1_R6_BULK_OPT_ON_HIDDEN */"
    output, frontiers, pruned = packer.pack(
        source, generated, compiled, base, bb, bc)
    if pruned or output.count("/* "+MARK+" */")!=1:
        raise ValueError("Source-clean packet failed final original pack support gate")
    for va in candidates:
        item="case 0x%08Xu: return sub_%08X;"%(va,va)
        if output.count(item)!=1:
            raise ValueError("Original function missing exact main lookup: "+item)
    for required in ("/* "+PARENT_MARK+" */",
                     "case 0x001F7620u: return sub_001F7620;",
                     "case 0x001F7520u: return sub_001F7520;",
                     "case 0x002228C0u: return sub_002228C0;",
                     "K1D3D SECOND: native Xenos Reset PASS",
                     "P6DQ ROCKET HARD STOP"):
        if output.count(required)!=source.count(required):
            raise ValueError("r5 source regression in batched main: "+required)
    output_blob=output.encode("utf-8")
    if (a.out.resolve()==a.parent.resolve() or
        a.out.parent.resolve()==a.parent.parent.resolve()):
        raise ValueError("Refuse overwrite of original r5 source")
    summary={
        "status":STATUS,"marker":MARK,"original_retail_xbe_sha256":RETAIL,
        "pinned_pc_commit":PC_SHA,
        "r5_main_sha256":sha(parent_bytes),
        "r5_manifest_sha256":sha(manifest_bytes),
        "r6_derived_main_sha256":sha(output_blob),
        "new_original_generated_C_members":["0x%08X"%x for x in candidates],
        "new_member_count":len(candidates),
        "unmodified_original_TrueTU_hashes":{
            k:sha(v) for k,v in shard_blobs.items()},
        "unmodified_original_TrueTU_count":64,
        "r4_hardware_proven_source_fences_preserved":True,
        "six_case_true_tu_owner":"translated_052.cpp",
        "original_r5_retail_branch_preserved":True,
        "original_frontiers":["0x%08X"%va for va in frontiers],
        "original_source_packet_hashes":real_input_hashes,
        "zero_dummy_host_helpers":True,
        "unproven_indirect_targets_remain_fenced":True,
        "r5_xdk_verified":False,
        "r5_hardware_verified":False,
        "r6_xdk_verified":False,
        "r6_hardware_verified":False,
        "r6_display_calls":None,
        "source_only":True,
        "safe_to_deploy":False,
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    dest=((a.out,output_blob),
          (a.manifest,(json.dumps(summary,indent=2)+"\n").encode("utf-8")))
    for path,data in dest:
        if path.is_file() and path.read_bytes()!=data:
            raise ValueError("Existing r6 derived source differs; no overwrite")
        if not path.exists():
            path.write_bytes(data)
    if a.parent.read_bytes()!=parent_bytes or (
        a.parent_manifest.read_bytes()!=manifest_bytes):
        raise ValueError("r5 parent mutated while staging")
    for p in shard_paths:
        if p.read_bytes()!=shard_blobs[p.name]:
            raise ValueError("One original 64 TrueTU changed during r6 stage")
    print("[K1-BULK-R6] ORIGINAL SOURCE BATCH STAGED: %d exact retail C functions"%(len(candidates)))
    print("[K1-BULK-R6] Parent r5 main, original 002228F0 retail branch, two original text roots, six-case D3D all preserved")
    print("[K1-BULK-R6] 64 original TrueTUs unchanged. No unknown helpers, no fake pixels.")
    print("[K1-BULK-R6] R5 hardware and r6 XDK/hardware UNVERIFIED. DO NOT COPY TO XBOX.")
    print("[K1-BULK-R6] Source-only manifest: "+str(a.manifest))


def selftest():
    fake= {
        "status":"K1_TEXT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY_NO_XDK",
        "marker":PARENT_MARK,"original_retail_xbe_sha256":RETAIL,
        "original_function_address":"0x002228C0",
        "original_generated_c":"recomp_0011.c",
        "source_only_staged_new_functions":1,
        "original_r4_bodies_preserved":["0x001F7620","0x001F7520"],
        "true_tu_count":64,"original_true_tus_unchanged":True,
        "runtime_header_unchanged":True,
        "six_case_verified_owner":"translated_052.cpp",
        "native_xenos_reset_source_preserved":True,
        "unknown_direct_and_indirect_hard_fences_preserved":True,
        "dummy_guest_data":False,"new_xdk_verified":False,
        "new_hardware_verified":False,
        "pc_reference_git_commit":PC_SHA,
        "pc_developer_patch_reverted_to_original_retail":{
            "status":"PINNED_PC_DEVELOPER_ONLY_PATCH_RESTORED_TO_RETAIL",
            "arbitrary_helper_stub_used":False,
            "x86_retail_cmp_jne_proof":{
                "original_002228f0_x86_cmp_jne":True}},
    }
    source="\n".join(
        ["/* "+PARENT_MARK+" */",
         "case 0x001F7620u: return sub_001F7620;",
         "case 0x001F7520u: return sub_001F7520;",
         "case 0x002228C0u: return sub_002228C0;",
         "K1D3D SECOND: native Xenos Reset PASS",
         "P6DQ ROCKET HARD STOP",
         "K1STATE MAIN CHECKPOINT:",
        ]).encode("utf-8")
    shards={"translated_%03d.cpp"%i:b"test" for i in range(64)}
    fake["new_main_sha256"]=sha(source)
    fake["original_true_tu_hashes_sha256"]={
        k:sha(v) for k,v in shards.items()}
    assert verify_r5(fake,source,shards)
    repeated=source.replace(b"P6DQ ROCKET HARD STOP",
                            b"P6DQ ROCKET HARD STOP\nP6DQ ROCKET HARD STOP")
    fake_repeated={**fake,"new_main_sha256":sha(repeated)}
    assert verify_r5(fake_repeated,repeated,shards)
    for broken in (
        {**fake,"new_main_sha256":"000"},
        {**fake,"new_hardware_verified":True},
        {**fake,"dummy_guest_data":True},
        {**fake,"pc_developer_patch_reverted_to_original_retail":{
            "status":"GUESSED_HELPER_STUB"}},
    ):
        try:
            verify_r5(broken,source,shards)
        except ValueError:
            pass
        else:
            raise AssertionError("R6 accepted r5 source provenance regression")
    print("[K1-BULK-R6] SELFTEST PASS: source-only r5 provenance, retail branch, 64 TrueTUs, six-case and hard fences")


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for key in ("parent","parent-manifest","shards","packet-plan","base","bb",
                "bc","previous","packer","functions","generated","out","manifest"):
        p.add_argument("--"+key,type=Path)
    a=p.parse_args()
    if a.self_test:
        selftest()
        return
    for key in ("parent","parent_manifest","shards","packet_plan","base",
                "bb","bc","previous","packer","functions","generated","out","manifest"):
        if getattr(a,key) is None:
            p.error("Missing --"+key.replace("_","-"))
    stage(a)


if __name__=="__main__":
    main()
