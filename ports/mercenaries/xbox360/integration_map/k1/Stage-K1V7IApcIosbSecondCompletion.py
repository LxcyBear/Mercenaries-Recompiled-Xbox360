#!/usr/bin/env python3
"""K1-V7I: exact observed APC IOSB identity repair from the V7E hardware run.

The genuine seventh NtReadFile completion (handle 48000006, 57344 bytes)
used IO_STATUS_BLOCK 0x00424D58 while the V6 APC guard only allowlisted
0x00424DA8. Preserve ALL status/byte-count/stack/pending-APC checks;
extend only the allowlist to cover the second directly observed address.
No synthetic completions, ABI bypass, unknown frames, XDK or Xbox.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7e"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_apc_iosb_v7i"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
MARK="K1-V7I-APC-IOSB-SECOND-REAL-COMPLETION-20261106"
OLD="s_k1v6Iosb != 0x00424DA8u ||"
NEW="(s_k1v6Iosb != 0x00424DA8u && s_k1v6Iosb != 0x00424D58u) ||"
FENCE='trace("K1-V6 FENCE: completion IOSB or stack mismatch");'
FOLLOW=(
 "GUEST_READ32(s_k1v6Iosb) != 0u ||",
 "GUEST_READ32(s_k1v6Iosb + 4u) != s_k1v6LastBytes ||",
 "savedEsp < 0x00880020u ||",
 "savedEsp > 0x008BFFF0u",
 "phase4c_escape(PHASE4C_BOUNDARY_STORAGE_IO,0x80000063u,savedEsp);",
)
def need(v,msg):
    if not v:raise ValueError(msg)
def digest(x):return hashlib.sha256(x).hexdigest()
def main():
    parent_bytes=(PARENT/"main.cpp").read_bytes()
    manifest=json.loads((PARENT/"v7e-manifest.json").read_text(encoding="utf-8-sig"))
    need(manifest["stage"]=="V7E_FIVE_RETAIL_FUNCTIONS_UNIQUE_DISPATCH_SOURCE_ONLY" and
         digest(parent_bytes)==manifest["source_sha256"] and
         manifest["retail_xbe_sha256"]==RETAIL and
         manifest["remaining_duplicate_cases"]==0 and
         manifest["native_summary_preserved"] and
         manifest["seven_async_reads_preserved_in_source"] and
         manifest["unknown_frontiers_fenced"] and
         len(manifest["true_tu_sha256"])==64 and
         sum(manifest["original_opcode_counts"].values())==197,
         "V7E baseline, retail, TrueTU, or 197-instruction evidence drift")
    need(manifest["source_sha256"]==
         "54c8901b0024d3fa2da393944df9ffed337ff70950343af0b97a188088844042",
         "Unexpected V7E parent; review hardware-proven source before patch")
    nl="\r\n" if b"\r\n" in parent_bytes else "\n"
    src=parent_bytes.decode("utf-8").replace("\r\n","\n")
    need(MARK not in src and src.count(OLD)==1 and src.count(NEW)==0,
         "Expected exactly one unmodified original V6 APC IOSB address guard")
    start=src.index(OLD)
    body=src[start:start+1500]
    need(FENCE in body and all(x in body for x in FOLLOW),
         "Existing APC frame / bytes / status / stack fence differs; no patch")
    # Verify the address check is within the established pending APC wait.
    prefix=src[max(0,start-550):start]
    need(re.search(r'if\s*\(\s*s_k1v6Pending\s*&&\s*waitMode\s*==\s*1u\s*&&\s*alertable\s*==\s*1u\s*&&\s*interval\s*==\s*0\s*\)',prefix),
         "Canonical alertable APC wait guard missing")
    patched=src.replace(OLD,NEW,1)
    need(patched.replace(NEW,OLD,1)==src,
         "Modification beyond one verified IOSB allowlist expression")
    for mark in ("K1-V7E-DISPATCH-DEDUP-22F51C",
                 "K1-V7D-RETAIL-FIVE-FUNCTION-BATCH-OPCODE-LIFT",
                 "K1-V6Z-RETAIL22F9BC-X87-OPCODE-LIFT",
                 "K1-V6W-RETAIL22FA9E-X87-EBP-20261105",
                 "K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                 "P6DQ ROCKET HARD STOP"):
        need(src.count(mark)>0 and src.count(mark)==patched.count(mark),
             "Existing guest/kernel invariant drift "+mark)
    for va in (0x0022F49E,0x0022F51C,0x0022F5A7,0x0022F6A5,0x0022F7C6):
        line="case 0x%08Xu: return sub_%08X;"%(va,va)
        need(src.count(line)==1 and patched.count(line)==1,
             "Existing five-function route drift "+line)
    patched="/* "+MARK+" */\n"+patched
    b=patched.replace("\n",nl).encode()
    newmanifest=dict(manifest)
    newmanifest.update({
        "stage":"V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY",
        "source_sha256":digest(b),"parent_v7e_sha256":digest(parent_bytes),
        "retail_original_xbe_sha256":RETAIL,
        "apc_iosb_allowlist":["0x00424DA8","0x00424D58"],
        "last_hardware_observed_read":{"handle":"0x48000006",
          "iosb":"0x00424D58","bytes":57344,"call_index":7},
        "apc_pending_wait_guard_preserved":True,
        "completion_status_check_preserved":True,
        "completion_byte_count_check_preserved":True,
        "stack_range_check_preserved":True,
        "no_new_apc_synthesis":True,
        "no_guest_abi_bypass":True,
        "xdk_compiled":False,"hardware_verified":False})
    outputs=[(OUT/"main.cpp",b),
             (OUT/"v7i-manifest.json",(json.dumps(newmanifest,indent=2)+"\n").encode())]
    for p,data in outputs:
        need(not p.exists() or p.read_bytes()==data,
             "Existing V7I output differs; refuse overwrite: "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,data in outputs:
        if not p.exists():p.write_bytes(data)
    need((PARENT/"main.cpp").read_bytes()==parent_bytes,
         "Parent V7E source changed")
    print("[K1-V7I] SOURCE FIX PASS: original hardcoded IOSB + verified seventh IOSB")
    print("[K1-V7I] preserved: pending alertable wait, status, byte count, stack, fences")
    print("[K1-V7I] TrueTUs=64, retail originals=197, five-function batch unchanged")
    print("[K1-V7I] XDK NOT BUILT; XBOX NOT RUN; GPU DIAGNOSTICS STILL REQUIRE CAUTION")
    print("[K1-V7I] OUTPUT: "+str(OUT/"main.cpp"))
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7I] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
