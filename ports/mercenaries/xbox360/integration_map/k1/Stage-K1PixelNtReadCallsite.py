#!/usr/bin/env python3
"""K1 Pixel: stage a provenance-pinned NtReadFile 44-byte callsite witness.

The original R8 main and all 64 translated TrueTUs are never modified.
Do not reinterpret or accept 44-byte frames; the existing hard stop remains.
"""
import argparse,hashlib,json,re
from pathlib import Path

OLD='#define PHASE6DJ_ICALL_SAFE(caller, target_expr, saved_esp_expr) \\\n    do { \\\n        uint32_t phase6dj_target_once = (uint32_t)(target_expr); \\\n        uint32_t phase6dj_saved_esp_once = (uint32_t)(saved_esp_expr); \\\n        phase6dj_icall_probe( \\\n            (DWORD)(caller), phase6dj_target_once, phase6dj_saved_esp_once); \\\n        RECOMP_ICALL_SAFE(phase6dj_target_once, phase6dj_saved_esp_once); \\\n    } while (0)'
# Unique source-local filename+line anchor evaluated at macro expansion (the translated call).
MARK="K1-PIXEL NTREAD FRAME SOURCE"
INSERT='''        if (phase6dj_target_once == 0x800000DBu && \\
            phase6dj_saved_esp_once != g_esp + 36u) { \\
            char phase6dj_ntread_witness[512]; \\
            sprintf(phase6dj_ntread_witness, \\
                "K1-PIXEL NTREAD FRAME SOURCE: file=%s line=%u function=%08X target=%08X saved=%08X esp=%08X delta=%u", \\
                __FILE__, (unsigned int)__LINE__, (unsigned int)(caller), \\
                (unsigned int)phase6dj_target_once, \\
                (unsigned int)phase6dj_saved_esp_once, (unsigned int)g_esp, \\
                (unsigned int)(phase6dj_saved_esp_once - g_esp)); \\
            trace(phase6dj_ntread_witness); \\
        } \\
'''
def sha(b):return hashlib.sha256(b).hexdigest()
def stage(parent,manifest,shards,output,report):
    pb=parent.read_bytes()
    meta=json.loads(manifest.read_text(encoding="utf-8-sig"))
    if (meta.get("status")!="K1_R8_NTREAD44_ABI_EVIDENCE_ONLY_NO_44_BYTE_BYPASS" or
        sha(pb)!=meta.get("new_r8_main_sha256") or
        meta.get("original_64_true_tus_unchanged") is not True or
        meta.get("fenced_mismatched_frames") is not True or
        meta.get("r8_ntread_36_byte_normal_path_unchanged") is not True or
        meta.get("no_guest_stack_adjustment") is not True):
        raise ValueError("Exact verified R8 baseline contract missing")
    true_tus=sorted(shards.glob("translated_???.cpp"))
    if len(true_tus)!=64:raise ValueError("Original 64 TrueTUs missing")
    if MARK.encode() in pb:raise ValueError("Parent already has witness")
    s=pb.decode("utf-8")
    if s.count(OLD)!=1:raise ValueError("Exact PHASE6DJ macro differs; no speculative patch")
    if s.count("if (savedEsp != callEsp + 36u)")!=1:raise ValueError("Native NtRead 36-byte fence missing")
    if s.count("phase5h_nt_read_file((uint32_t)(saved_esp))")!=1:raise ValueError("NtRead dispatch not unique")
    patched=OLD.replace('        RECOMP_ICALL_SAFE(',INSERT+'        RECOMP_ICALL_SAFE(')
    if patched.count(MARK)!=1:raise ValueError("Witness insertion invalid")
    result=s.replace(OLD,patched,1)
    if result.replace(patched,OLD,1)!=s:raise ValueError("Other R8 source changed")
    if output.resolve()==parent.resolve():raise ValueError("Output cannot overwrite R8")
    out=result.encode()
    report_data={"status":"K1_PIXEL_NTREAD_44_CALLSITE_WITNESS_ONLY",
      "original_r8_sha256":sha(pb),"candidate_sha256":sha(out),
      "r8_manifest_sha256":sha(manifest.read_bytes()),
      "original_64_true_tus_unchanged":True,"original_64_true_tus_count":64,
      "mismatched_frame_fence_untouched":True,"successful_36_byte_reads_untouched":True,
      "no_abi_fix":True,"no_fake_pixel":True,
      "witness":MARK,"hardware_test_verified":False}
    output.parent.mkdir(parents=True,exist_ok=True)
    if output.exists() and output.read_bytes()!=out:raise ValueError("Candidate exists with DIFFERENT contents, refusing overwrite")
    if not output.exists():output.write_bytes(out)
    report.parent.mkdir(parents=True,exist_ok=True)
    report.write_text(json.dumps(report_data,indent=2)+"\n",encoding="utf-8")
    if sha(parent.read_bytes())!=sha(pb):raise ValueError("R8 parent unexpectedly changed")
    print("[K1-PIXEL] SOURCE PASS: 64 original TrueTUs, R8 baseline SHA, unique PHASE6DJ witness")
    print("[K1-PIXEL] ABNORMAL NtReadFile only: __FILE__ / __LINE__ / ESP delta")
    print("[K1-PIXEL] 36-byte successful reads unchanged; 44-byte KERNEL_FRAME hard stop untouched")
    print("[K1-PIXEL] CANDIDATE:",output)
    print("[K1-PIXEL] NO XDK YET; NO XBOX RUN; NO GUEST ABI MODIFICATION")

def selftest():
    assert OLD.startswith("#define PHASE6DJ_ICALL_SAFE")
    assert OLD.count("RECOMP_ICALL_SAFE(")==1
    assert MARK in INSERT
    assert INSERT.count("trace(")==1
    assert "__FILE__" in INSERT and "__LINE__" in INSERT
    assert "phase6dj_saved_esp_once != g_esp + 36u" in INSERT
    print("[K1-PIXEL] SELFTEST PASS: narrow witness, original dispatcher retained")

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    p.add_argument("--parent",type=Path)
    p.add_argument("--manifest",type=Path)
    p.add_argument("--shards",type=Path)
    p.add_argument("--output",type=Path)
    p.add_argument("--report",type=Path)
    a=p.parse_args()
    if a.self_test:selftest();return
    if any(getattr(a,k) is None for k in ("parent","manifest","shards","output","report")):
        p.error("Need parent, manifest, shards, output, report")
    stage(a.parent,a.manifest,a.shards,a.output,a.report)
if __name__=="__main__":main()
