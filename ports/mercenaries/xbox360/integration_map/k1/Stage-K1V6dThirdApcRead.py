#!/usr/bin/env python3
"""V6d: retain V6c original PblJoystick function and add ONE hardware-observed
third streaming read to the bounded APC allowlist. Source-only; no XDK or Xbox.
Retail C and all 64 TrueTUs stay unmodified. Unknown reads remain fenced.
"""
from pathlib import Path
import hashlib
import json
import re
import sys

TAG = "[K1-V6d]"
MARKER = "K1-V6D-THIRD-APC-0ACE8000-20261104"
RETAIL = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
OLD_OFFSET = ("    offsetLow >= 0x08000000u &&\n"
              "    offsetLow <= 0x09000000u &&")
NEW_OFFSET = ("    ((offsetLow >= 0x08000000u && offsetLow <= 0x09000000u) ||\n"
              "     (offsetLow == 0x0ACE8000u && length == 153600u &&\n"
              "      bufferVa == 0x01B32B00u)) &&")
OLD_ALIGN = "    (length & 4095u) == 0u &&"
NEW_ALIGN = ("    (((length & 4095u) == 0u) ||\n"
             "     (offsetLow == 0x0ACE8000u && length == 153600u &&\n"
             "      bufferVa == 0x01B32B00u)) &&")

def hash_bytes(data):
    return hashlib.sha256(data).hexdigest()

def die(msg):
    raise RuntimeError(TAG + " " + msg)

def one_replace(source, old, new):
    if source.count(old) != 1:
        die("Source predicate not unique or V6c has drifted: " + repr(old[:80]))
    return source.replace(old, new, 1)

def main():
    repo=Path.cwd().resolve()
    root=repo/"build/phase6_integration_map"
    prior=root/"k1_pixel_ntread_apc_direct_v6c"
    base=root/"k1_pixel_ntread_apc_stream_v6b"
    target=root/"k1_pixel_ntread_apc_third_v6d"
    in_main=prior/"main.cpp"
    in_manifest=prior/"v6c-20eb00-manifest.json"
    shards=base/"translated_shards"
    for p in (in_main,in_manifest,shards/"translated_runtime.h"):
        if not p.is_file():
            die("Missing required previous output: "+str(p))
    manifest=json.loads(in_manifest.read_text(encoding="utf-8-sig"))
    orig=in_main.read_bytes()
    if (manifest.get("stage")!="SOURCE_ONLY_NOT_HARDWARE_TESTED" or
        manifest.get("target")!="0x0020EB00" or
        manifest.get("retail_sha256")!=RETAIL or
        manifest.get("staged_sha256")!=hash_bytes(orig) or
        manifest.get("source_count")!=1 or
        manifest.get("true_tus")!=64 or
        manifest.get("v6b_input_not_modified") is not True):
        die("V6c manifest or staged source hash/identity mismatch")
    true_tus=sorted(shards.glob("translated_???.cpp"))
    if len(true_tus)!=64:
        die("Expected exactly 64 original TrueTUs")
    tus_hash={p.name:hash_bytes(p.read_bytes()) for p in true_tus}
    if tus_hash != manifest.get("original_true_tu_sha256"):
        die("V6c recorded TrueTU hashes do not match V6b parent")
    raw=orig.decode("utf-8-sig")
    normalized=raw.replace("\r\n","\n")
    for required in ("K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                     "case 0x0020EB00u: return sub_0020EB00;",
                     "K1-V6C-REAL-20EB00-SOURCE-ONLY-20261104",
                     "P6DQ ROCKET HARD STOP",
                     "((unsigned __int64)bufferVa + (unsigned __int64)length) == 0x01B58300ui64;",
                     "s_k1v6Delivered >= 16u",
                     "apcRoutine == 0x800000E8u",
                     "apcContext == 0x00221F00u",
                     "handleToken == 0x48000003u",
                     "ioStatusVa == 0x00424DA8u"):
        if required not in normalized:
            die("Required working V6c/V6b code missing: "+required)
    if MARKER in normalized:
        die("Third-read signature already added")
    # Exact-match BOTH conditions with all other callback/handle/IOSB/buffer limits intact.
    changed=one_replace(normalized,OLD_OFFSET,NEW_OFFSET)
    changed=one_replace(changed,OLD_ALIGN,NEW_ALIGN)
    # Keep source recognizable in a hardware run without touching gameplay.
    changed=one_replace(changed,
        'trace("K1-V6b APC QUEUED: bounded completed stream read");',
        'trace("K1-V6b APC QUEUED: bounded completed stream read"); /* '+MARKER+' */')
    if raw.count("\r\n") and not raw.count("\n")-raw.count("\r\n"):
        changed=changed.replace("\n","\r\n")
    payload=changed.encode("utf-8")
    if payload == orig:
        die("No source change")
    if changed.count(MARKER)!=1 or changed.count("0x0ACE8000u")!=2:
        die("Unexpected instrumentation/allowlist edit")
    if changed.count("case 0x0020EB00u: return sub_0020EB00;")!=normalized.count(
        "case 0x0020EB00u: return sub_0020EB00;"):
        die("Retail function dispatch changed")
    if changed.count("K1-V6b APC DELIVERED")!=normalized.count("K1-V6b APC DELIVERED"):
        die("APC callback delivery changed")
    target.mkdir(parents=True,exist_ok=True)
    out=target/"main.cpp"
    record={
      "stage":"V6D_SOURCE_ONLY_NOT_BUILT_OR_HARDWARE_TESTED",
      "retail_sha256":RETAIL,"marker":MARKER,
      "observed_third_read":{"handle":"0x48000003","apc":"0x800000E8",
          "context":"0x00221F00","iosb":"0x00424DA8",
          "buffer":"0x01B32B00","length":153600,"offset":"0x0ACE8000",
          "end_exclusive":"0x01B58300"},
      "parent_v6c_sha256":hash_bytes(orig),"staged_v6d_sha256":hash_bytes(payload),
      "parent_v6c_manifest_sha256":hash_bytes(in_manifest.read_bytes()),
      "true_tu_count":64,"true_tu_sha256":tus_hash,
      "v6c_retail_0020EB00_preserved":True,
      "prior_v6b_callback_predicate_preserved":True,
      "unknown_async_hard_fence_preserved":True,
      "hardware_tested":False,"display_calls_proven":False
    }
    files=((out,payload),(target/"v6d-third-apc-manifest.json",
        (json.dumps(record,indent=2)+"\n").encode("utf-8")))
    for p,data in files:
        if p.exists() and p.read_bytes()!=data:
            die("Refuse overwrite of changed candidate: "+str(p))
        if not p.exists():
            p.write_bytes(data)
    if in_main.read_bytes()!=orig or tus_hash!={p.name:hash_bytes(p.read_bytes()) for p in true_tus}:
        die("Parent source or TrueTUs changed during stage")
    print(TAG+" SOURCE PASS: verified exact third read at offset 0x0ACE8000, 153600 bytes")
    print(TAG+" Original two stream read guards preserved; third exception exact buffer/length/offset")
    print(TAG+" Original PblJoystick 0x0020EB00 lookup, V6b APC, 64 TrueTUs and hard fences preserved")
    print(TAG+" SOURCE-ONLY: XDK and Xbox hardware not tested")
    print(TAG+" MAIN: "+str(out))
    print(TAG+" MANIFEST: "+str(target/"v6d-third-apc-manifest.json"))

if __name__=="__main__":
    try: main()
    except Exception as exc:
        print(TAG+" BLOCKED: "+str(exc),file=sys.stderr)
        sys.exit(1)
