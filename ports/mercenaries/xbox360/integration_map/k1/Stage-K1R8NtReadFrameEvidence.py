#!/usr/bin/env python3
"""K1-R8 evidence-only ABI probe: Xbox NtReadFile 44-byte vs 36-byte frame.

Hardware r7 had 31 successful 36-byte NtReadFile calls, then a legitimate
fail-closed KERNEL_FRAME on 44 bytes (saved=008BF794, call=008BF768).
THIS STAGE DOES NOT ACCEPT 44 AS 36. It prints the 11 raw guest stack
words, preserving the native read branch, status, stack, guest registers,
and the hard-stop. Only a future proof-backed ABI fix may alter execution.

Source: exact SHA-pinned r7 main + manifest + 64 original translated TrueTUs.
Fingerprints are anchored to the original rocket diagnostic, not dead data.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

RETAIL_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
R7_STATUS="K1_R7_222190_REAL_ORIGINAL_DIRECT_SOURCE_FINGERPRINT_NO_XDK"
STATUS="K1_R8_NTREAD44_ABI_EVIDENCE_ONLY_NO_44_BYTE_BYPASS"
PROC="static void phase5h_nt_read_file(uint32_t savedEsp)"
FENCE='if (savedEsp != callEsp + 36u)'
BOUNDARY='PHASE4C_BOUNDARY_KERNEL_FRAME'
PROBE="K1-R8 NTREAD 44-RAW"
R7_TAG="K1-R7-222190-XEX-PROOF-"
R8_TAG="K1-R8-NTREAD-44-PROOF-"
# The original hardware-verified guest stack begins at 0x00880000 and
# finishes at 0x008BFFF0. This probe refuses to read outside that range.
STACK_MIN=0x00880000
STACK_MAX=0x008BFFF0

def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()

def get_owner(source:str)->tuple[int,int]:
    # The maintained generated main defines this native helper as plain
    # 'void', while small historical fixtures used 'static void'.
    # Accept either linkage without weakening unique-owner validation.
    sig=re.compile(r'(?m)^(?:static )?void phase5h_nt_read_file\(uint32_t savedEsp\)\s*\{')
    matches=list(sig.finditer(source))
    if len(matches)!=1:
        raise ValueError("Exact native NtReadFile implementation missing/duplicated")
    start=matches[0].start()
    # Top-level function braces are at column zero; nested blocks are
    # indented. Do not depend on the next function's return type/linkage.
    closing=list(re.finditer(r'(?m)^\}[ \t]*(?=\r?$)',source[matches[0].end():]))
    if not closing:
        raise ValueError("Native NtReadFile closing brace not found")
    finish=matches[0].end()+closing[0].end()
    func=source[start:finish]
    if func.count("phase5h_nt_read_file(")!=1:
        raise ValueError("Native NtReadFile owner ambiguous")
    return start,finish

def probe_only(source:str)->tuple[str,dict]:
    start,end=get_owner(source)
    func=source[start:end]
    original=(
        "    if (savedEsp != callEsp + 36u)\n"
        "    {\n"
        "        sprintf(\n"
        "            line,\n"
        '            "NtReadFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=36",\n'
    )
    if func.count(original)!=1:
        raise ValueError("Original 36-byte NtReadFile guard/fence message no longer matches r7")
    if func.count("phase4c_escape(\n            PHASE4C_BOUNDARY_KERNEL_FRAME,\n            0x800000DBu,\n            savedEsp);")<1:
        raise ValueError("Original NtReadFile KERNEL_FRAME escape missing")
    if func.count('g_esp = savedEsp;')!=1 or func.count("ReadFile(")<1:
        raise ValueError("Original NtReadFile successful branch or stack restoration altered")
    if PROBE in source:
        raise ValueError("R8 44-byte evidence already inserted; no double instrumentation")
    addition=(
        "        /* K1-R8: READ-ONLY evidence for original 44-byte rejected ABI.\n"
        "         * Existing 36-byte NtReadFile and hard-stop paths are unchanged.\n"
        "         * No storage action, fallback, stack adjustment or fake read.\n"
        "         */\n"
        "        if (savedEsp == callEsp + 44u &&\n"
        "            callEsp >= 0x00880000u &&\n"
        "            savedEsp <= 0x008BFFF0u &&\n"
        "            (callEsp & 3u) == 0u)\n"
        "        {\n"
        "            sprintf(\n"
        "                line,\n"
        '                "K1-R8 NTREAD 44-RAW A: call=%08X saved=%08X owner=%08X w0=%08X w1=%08X w2=%08X w3=%08X w4=%08X w5=%08X",\n'
        "                (unsigned int)callEsp,\n"
        "                (unsigned int)savedEsp,\n"
        "                (unsigned int)phase4c_current_caller(),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 0u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 4u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 8u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 12u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 16u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 20u));\n"
        "            trace(line);\n"
        "            sprintf(\n"
        "                line,\n"
        '                "K1-R8 NTREAD 44-RAW B: call=%08X w6=%08X w7=%08X w8=%08X w9=%08X w10=%08X eax=%08X ecx=%08X edx=%08X",\n'
        "                (unsigned int)callEsp,\n"
        "                (unsigned int)GUEST_READ32(callEsp + 24u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 28u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 32u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 36u),\n"
        "                (unsigned int)GUEST_READ32(callEsp + 40u),\n"
        "                (unsigned int)g_eax,\n"
        "                (unsigned int)g_ecx,\n"
        "                (unsigned int)g_edx);\n"
        "            trace(line);\n"
        "        }\n"
    )
    patched=func.replace(original,original.replace("        sprintf(\n","",1).replace(
        "            line,\n",'',1).replace(
        '            "NtReadFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=36",\n','',1)+addition+
        "        sprintf(\n"
        "            line,\n"
        '            "NtReadFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=36",\n',1)
    # Ensure we did not move any instruction in the original branch:
    if patched.replace(addition,"",1)!=func:
        raise ValueError("R8 diagnostic insertion modified existing NtReadFile C")
    result=source[:start]+patched+source[end:]
    if (result.count(PROBE)!=2 or
        result.count(FENCE)!=source.count(FENCE) or
        result.count("NtReadFile FRAME MISMATCH")!=source.count("NtReadFile FRAME MISMATCH") or
        result.count("phase4c_escape(")!=source.count("phase4c_escape(") or
        result.count("ReadFile(")!=source.count("ReadFile(")):
        raise ValueError("R8 non-ABI instrumentation changed native read control flow")
    return result,{"probe_line_count":len(addition.splitlines()),
                   "capture_words":11,
                   "capture_offsets_bytes":list(range(0,44,4)),
                   "guard_delta":44,
                   "canonical_delta":36,
                   "read_only":True,
                   "all_original_36_byte_reads_untouched":True,
                   "existing_kernel_frame_fence_untouched":True}

def tag_runtime(source:str,parent_tag:str)->tuple[str,str]:
    old="r7_xex="+parent_tag
    if source.count(old)!=1 or not parent_tag.startswith(R7_TAG):
        raise ValueError("Actual r7 rocket hard-stop runtime fingerprint missing")
    token=R8_TAG+sha(source.encode("utf-8"))[:16].upper()
    new="r8_xex="+token
    if len(new)>len(old):
        raise ValueError("R8 runtime fingerprint would grow existing logger")
    body=source.replace(old,new,1)
    if body.replace(new,old,1)!=source or body.count(token)!=1:
        raise ValueError("Non-rocket source changed while fingerprinting")
    return body,token

def stage(args):
    parent_data=args.parent.read_bytes()
    parent_meta_data=args.parent_manifest.read_bytes()
    meta=json.loads(parent_meta_data.decode("utf-8-sig"))
    if (meta.get("status")!=R7_STATUS or meta.get("retail_sha256")!=RETAIL_SHA or
        meta.get("r7_source_sha256")!=sha(parent_data) or
        meta.get("original_64_true_tus_unchanged") is not True or
        meta.get("retail_002228F0_branch_restoration_preserved") is not True or
        meta.get("previous_r4_hardware_fences_preserved") is not True or
        meta.get("no_dummy_abi_or_pc_helper_stubs") is not True or
        meta.get("new_original_generated_C",[])[0]!="0x00222190" or
        meta.get("pc_stream_idle_patch_279_restored_to_retail",{}).get("pc_only_host_helper_removed") is not True):
        raise ValueError("Original r7 retail source/222190/64 TrueTUs provenance invalid")
    shard_files=sorted(args.shards.glob("translated_???.cpp"))
    if len(shard_files)!=64:
        raise ValueError("Expected exactly the original 64 TrueTUs")
    hashes={p.name:sha(p.read_bytes()) for p in shard_files}
    if hashes!=meta.get("original_64_true_tu_sha256"):
        raise ValueError("Original Xbox 64 TrueTU hashes changed")
    old_tag=meta.get("runtime_xex_fingerprint","")
    source=parent_data.decode("utf-8")
    if (source.count("P6DQ ROCKET HARD STOP kind=")<1 or
        "K1-R8 NTREAD 44-RAW" in source or
        "recomp_stream_admit_idle" in source):
        raise ValueError("Original r7 guest/fence/fingerprint preflight failed")
    traced,frame_proof=probe_only(source)
    candidate,new_tag=tag_runtime(traced,old_tag)
    result=candidate.encode("utf-8")
    report={
        "status":STATUS,
        "original_r7_main_sha256":sha(parent_data),
        "original_r7_manifest_sha256":sha(parent_meta_data),
        "original_64_true_tus_sha256":hashes,
        "original_64_true_tus_unchanged":True,
        "original_retail_sha256":RETAIL_SHA,
        "r7_22190_original_guest_function_preserved":True,
        "r7_streaming_patch_279_retail_branch_preserved":True,
        "new_r8_main_sha256":sha(result),
        "old_r7_hardware_fingerprint":old_tag,
        "new_r8_hardware_fingerprint":new_tag,
        "runtime_fingerprint_location":"P6DQ ROCKET HARD STOP kind= runtime format",
        "frame_evidence":frame_proof,
        "r8_ntread_44_byte_frame_handled":False,
        "r8_ntread_36_byte_normal_path_unchanged":True,
        "fenced_mismatched_frames":True,
        "no_guest_stack_adjustment":True,
        "no_unknown_abi_bridge":True,
        "no_fake_pixels":True,
        "xdk_built":False,
        "xbox_hardware_executed":False,
        "next":"Capture 44-RAW A/B and original KERNEL_FRAME in xbWatson; prove caller/pushes before changing NtReadFile ABI.",
    }
    if args.output.resolve()==args.parent.resolve() or args.manifest.resolve()==args.parent_manifest.resolve():
        raise ValueError("Refuse to overwrite r7 sources/manifest")
    args.output.parent.mkdir(parents=True,exist_ok=True)
    for dest,data in ((args.output,result),(args.manifest,(json.dumps(report,indent=2)+"\n").encode())):
        if dest.exists() and dest.read_bytes()!=data:
            raise ValueError("Refusing to overwrite distinct existing r8 build candidate: "+str(dest))
        if not dest.exists():
            dest.write_bytes(data)
    if args.parent.read_bytes()!=parent_data or args.parent_manifest.read_bytes()!=parent_meta_data:
        raise ValueError("Original r7 main/manifest changed while deriving r8")
    print("[K1-R8] ORIGINAL r7 retail + streaming 279 + 64 TrueTUs SHA PASS")
    print("[K1-R8] READ-ONLY 44-byte NtReadFile stack capture staged, 36-byte valid path unmodified")
    print("[K1-R8] NtReadFile 44-byte KERNEL_FRAME HARD STOP PRESERVED; no guest ABI guess")
    print("[K1-R8] Xbox runtime fingerprint: "+new_tag)
    print("[K1-R8] Source-only candidate: "+str(args.output))
    print("[K1-R8] NO XDK / NO HARDWARE YET")

def selftest():
    src=(
        "static void phase5h_nt_read_file(uint32_t savedEsp)\n"
        "{\n"
        "    const uint32_t callEsp = g_esp;\n"
        "    char line[768];\n"
        "    if (savedEsp != callEsp + 36u)\n"
        "    {\n"
        "        sprintf(\n"
        "            line,\n"
        '            "NtReadFile FRAME MISMATCH: esp=%08X saved_esp=%08X delta=%u expected=36",\n'
        "            (unsigned int)callEsp);\n"
        "        trace(line);\n"
        "        phase4c_escape(\n"
        "            PHASE4C_BOUNDARY_KERNEL_FRAME,\n"
        "            0x800000DBu,\n"
        "            savedEsp);\n"
        "        return;\n"
        "    }\n"
        "    ReadFile(0,0,0,0,0);\n"
        "    g_esp = savedEsp;\n"
        "}\n"
        "static void next_func(void){}\n"
        'static char msg[]="P6DQ ROCKET HARD STOP kind=%u caller=%08X r7_xex='+
        R7_TAG+"0123456789ABCDEF"+'";\n'
    )
    out,info=probe_only(src)
    # Regression: actual r7 main.cpp owner uses plain 'void', not 'static void'.
    plain=src.replace("static void phase5h_nt_read_file", "void phase5h_nt_read_file", 1)
    plain_out,plain_info=probe_only(plain)
    assert plain_info==info and plain_out.count(PROBE)==2
    # A second owner must still fail closed, irrespective of linkage.
    try:
        probe_only(plain+"\n"+src)
    except ValueError:
        pass
    else:
        raise AssertionError("Duplicate NtReadFile native owners accepted")
    assert info["capture_offsets_bytes"]==[0,4,8,12,16,20,24,28,32,36,40]
    assert out.count(PROBE)==2
    assert out.replace(out[out.index("        /* K1-R8:"):out.index("        sprintf(",out.index("        /* K1-R8:")+1)],"")!=src  # only explicit probe removal is permitted below
    tag,marker=tag_runtime(out,R7_TAG+"0123456789ABCDEF")
    assert marker.startswith(R8_TAG) and tag.count(marker)==1
    assert "r7_xex=" not in tag
    for changed in (
        src.replace("callEsp + 36u","callEsp + 44u"),
        src.replace("NtReadFile FRAME MISMATCH","NtReadFile FRAME IGNORED"),
        src.replace("PHASE4C_BOUNDARY_KERNEL_FRAME","PHASE4C_BOUNDARY_STORAGE_IO"),
        src.replace("g_esp = savedEsp;","g_esp = 0u;"),
        src.replace("ReadFile(","NoRealFile("),
    ):
        try:
            probe_only(changed)
        except ValueError:
            pass
        else:
            raise AssertionError("Original NtReadFile ABI/fence mutation not rejected")
    print("[K1-R8] SELFTEST PASS: 44-byte 11-word read-only original stack evidence, 36-byte path and KERNEL_FRAME fence unchanged, xbWatson fingerprint, NO XDK")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for x in ("parent","parent-manifest","shards","output","manifest"):
        p.add_argument("--"+x,type=Path)
    a=p.parse_args()
    if a.self_test:
        selftest()
        return
    if any(getattr(a,x) is None for x in ("parent","parent_manifest","shards","output","manifest")):
        p.error("Need all original r7 parent/manifest/64 TrueTU and r8 paths")
    stage(a)

if __name__=="__main__":
    main()
