#!/usr/bin/env python3
"""V6m: admit one hardware-observed locked.dsk APC read to existing completed-read/APC path.

This is NOT general async I/O. It extends V6l's already hardware-tested bounded
sync-backed read + deferred APC model by one fully matched I/O signature. All
unknown requests remain fenced, including other handles/offsets/lengths.
"""
from pathlib import Path
import hashlib,json,sys

ROOT=Path.cwd()
BASE=ROOT/"build/phase6_integration_map/k1_pixel_audio_world_batch_v6l"
DEST=ROOT/"build/phase6_integration_map/k1_pixel_locked_dsk_apc_v6m"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
TAG="[K1-V6m]"
MARK="K1-V6M-LOCKED-DSK-APC-262144-003800-20261105"
OLD_HANDLE="handleToken == 0x48000003u"
NEW_HANDLE=("((handleToken == 0x48000003u) ||\n"
            "     (handleToken == 0x48000006u && offsetLow == 0x00003800u &&\n"
            "      length == 262144u && bufferVa == 0x01B18300u))")
OLD_OFFSET=("(offsetLow == 0x0ACE8000u && length == 153600u &&\n"
            "      bufferVa == 0x01B32B00u)) &&")
NEW_OFFSET=("(offsetLow == 0x0ACE8000u && length == 153600u &&\n"
            "      bufferVa == 0x01B32B00u) ||\n"
            "     (offsetLow == 0x00003800u && length == 262144u &&\n"
            "      bufferVa == 0x01B18300u && handleToken == 0x48000006u)) &&")
def sha(b):return hashlib.sha256(b).hexdigest()
def need(c,msg):
    if not c:raise RuntimeError(msg)
def replace_once(s,old,new):
    need(s.count(old)==1,"Expected exactly one audited APC predicate: "+repr(old[:100]))
    return s.replace(old,new,1)
def stage():
    mf=BASE/"v6l-manifest.json"; src=BASE/"main.cpp"
    need(mf.is_file() and src.is_file(),"V6l staged main and manifest missing; build V6l first")
    m=json.loads(mf.read_text(encoding="utf-8-sig"))
    parent=src.read_bytes()
    need(m.get("stage")=="V6L_RETAIL_SOURCE_BATCH_HARDWARE_UNTESTED",
         "V6l parent stage identity changed")
    need(m.get("retail_xact_checkpoint_restore_001fe7d0") is True,
         "V6l SHA-verified XACT retail root restoration absent")
    need(m.get("retail_sha256")=="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7",
         "Retail identity drift")
    need(sha(parent)==m.get("source_sha256"),"V6l staged source SHA mismatch")
    tus=sorted(SHARDS.glob("translated_???.cpp"))
    need(len(tus)==64,"Expected 64 translated TrueTUs")
    hashes={p.name:sha(p.read_bytes()) for p in tus}
    need(hashes==m.get("true_tu_sha256"),"V6l TrueTU hashes changed")
    old=parent.decode("utf-8-sig").replace("\r\n","\n")
    for required in ("K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                     "s_k1v6Delivered >= 16u",
                     "apcRoutine == 0x800000E8u",
                     "apcContext == 0x00221F00u",
                     "ioStatusVa == 0x00424DA8u",
                     "((unsigned __int64)bufferVa + (unsigned __int64)length) == 0x01B58300ui64;",
                     "P6DQ ROCKET HARD STOP"):
        need(required in old,"Inherited APC safety/delivery invariant missing: "+required)
    need(MARK not in old,"V6m patch already present")
    # Ensure both modifications touch the same bounded APC admission function.
    first=old.index(OLD_HANDLE)
    second=old.index(OLD_OFFSET)
    need(abs(first-second)<2000,"Handle and offset guards are not in the same bounded admission predicate")
    modified=replace_once(old,OLD_HANDLE,NEW_HANDLE)
    modified=replace_once(modified,OLD_OFFSET,NEW_OFFSET)
    modified=replace_once(modified,
        'trace("K1-V6b APC QUEUED: bounded completed stream read");',
        'trace("K1-V6b APC QUEUED: bounded completed stream read"); /* '+MARK+' */')
    # Exact round trip guarantees no other gameplay/kernel paths changed.
    verified=modified.replace(NEW_HANDLE,OLD_HANDLE,1).replace(NEW_OFFSET,OLD_OFFSET,1)
    verified=verified.replace(' /* '+MARK+' */',"",1)
    need(verified==old,"V6m changed unrelated source")
    need(modified.count(MARK)==1,"V6m marker count mismatch")
    new_bytes=modified.replace("\n","\r\n").encode("utf-8") if b"\r\n" in parent else modified.encode("utf-8")
    # Never rewrite the staged parent or changed output.
    need(src.read_bytes()==parent,"Parent changed during validation")
    dest=DEST/"main.cpp"
    meta=DEST/"v6m-manifest.json"
    report={"stage":"V6M_EXACT_LOCKED_DSK_APC_SOURCE_UNTESTED",
            "parent_v6l_sha256":sha(parent),
            "source_sha256":sha(new_bytes),
            "retail_sha256":m["retail_sha256"],
            "original_true_tu_count":64,
            "true_tu_sha256":hashes,
            "new_request":{"path":"game:\\dataxbox\\locked.dsk",
              "handle":"0x48000006","options":"0x00000048",
              "event":"0x00000000","apc":"0x800000E8",
              "apc_context":"0x00221F00","iosb":"0x00424DA8",
              "buffer":"0x01B18300","length":262144,
              "offset":"0x00003800","buffer_end_exclusive":"0x01B58300"},
            "prior_five_apc_reads_preserved":True,
            "retail_root_and_true_tus_unchanged":True,
            "unmatched_async_reads_still_fenced":True,
            "apc_callback_delivery_unmodified":True,
            "hardware_tested":False,"marker":MARK}
    payloads=((dest,new_bytes),(meta,(json.dumps(report,indent=2)+"\n").encode()))
    for p,data in payloads:
        need(not p.exists() or p.read_bytes()==data,
             "Refusing overwrite of changed stage: "+str(p))
    DEST.mkdir(parents=True,exist_ok=True)
    for p,data in payloads:
        if not p.exists():p.write_bytes(data)
    need(src.read_bytes()==parent,"Parent modified during staging")
    need(hashes=={p.name:sha(p.read_bytes()) for p in tus},"TrueTU drift after stage")
    print(TAG+" SOURCE PASS: exact locked.dsk read 0x3800/262144, handle 0x48000006")
    print(TAG+" Prior callback queue+delivery, complete read, 64 TrueTUs and unknown fences unchanged")
    print(TAG+" MAIN: "+str(dest))
    print(TAG+" SHA256: "+sha(new_bytes))
    print(TAG+" SOURCE ONLY: XDK and hardware still UNTESTED")
def selftest():
    s="before "+OLD_HANDLE+" between "+OLD_OFFSET+" after"
    c=replace_once(replace_once(s,OLD_HANDLE,NEW_HANDLE),OLD_OFFSET,NEW_OFFSET)
    assert c.replace(NEW_HANDLE,OLD_HANDLE).replace(NEW_OFFSET,OLD_OFFSET)==s
    assert "handleToken == 0x48000006u" in c
    assert "length == 262144u" in c
    print(TAG+" SELFTEST PASS")
if __name__=="__main__":
    try:
        if "--selftest" in sys.argv:selftest()
        else:stage()
    except Exception as e:
        print(TAG+" BLOCKED: "+str(e),file=sys.stderr)
        sys.exit(1)
