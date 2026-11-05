#!/usr/bin/env python3
"""V6n: exact second locked.dsk read in the previously proven APC callback."""
from pathlib import Path
import hashlib,json,sys
ROOT=Path.cwd()
PRE=ROOT/"build/phase6_integration_map/k1_pixel_locked_dsk_apc_v6m"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_locked_dsk_apc_chain_v6n"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
TAG="[K1-V6n]"
def sha(b):return hashlib.sha256(b).hexdigest()
def check(x,msg):
    if not x:raise ValueError(msg)
def exact(s,a,b):
    check(s.count(a)==1,"Nonunique or changed source predicate: "+a[:80])
    return s.replace(a,b,1)
def run():
    parent=PRE/"main.cpp";meta=PRE/"v6m-manifest.json"
    check(parent.is_file() and meta.is_file(),"Run the V6m stage first")
    m=json.loads(meta.read_text(encoding="utf-8-sig"))
    data=parent.read_bytes()
    check(m.get("stage")=="V6M_EXACT_LOCKED_DSK_APC_SOURCE_UNTESTED","Parent stage mismatch")
    check(sha(data)==m.get("source_sha256"),"Parent hash mismatch")
    check(m.get("apc_callback_delivery_unmodified") is True,"Callback invariant absent")
    tus=sorted(SHARDS.glob("translated_???.cpp"))
    check(len(tus)==64,"Missing 64 original TrueTUs")
    check({p.name:sha(p.read_bytes()) for p in tus}==m.get("true_tu_sha256"),"TrueTU hash mismatch")
    s=data.decode("utf-8-sig").replace("\r\n","\n")
    h_old="""((handleToken == 0x48000003u) ||
     (handleToken == 0x48000006u && offsetLow == 0x00003800u &&
      length == 262144u && bufferVa == 0x01B18300u))"""
    h_new=h_old[:-2]+""" ||
     (handleToken == 0x48000006u && offsetLow == 0x00040000u &&
      length == 57344u && bufferVa == 0x01B0A300u))"""
    o_old="""((offsetLow >= 0x08000000u && offsetLow <= 0x09000000u) ||
     (offsetLow == 0x0ACE8000u && length == 153600u &&
      bufferVa == 0x01B32B00u) ||
     (offsetLow == 0x00003800u && length == 262144u &&
      bufferVa == 0x01B18300u && handleToken == 0x48000006u)) &&"""
    o_new=o_old[:-5]+""" ||
     (offsetLow == 0x00040000u && length == 57344u &&
      bufferVa == 0x01B0A300u && handleToken == 0x48000006u)) &&"""
    end_old="((unsigned __int64)bufferVa + (unsigned __int64)length) == 0x01B58300ui64;"
    end_new="""(((unsigned __int64)bufferVa + (unsigned __int64)length) == 0x01B58300ui64 ||
      (handleToken == 0x48000006u && offsetLow == 0x00040000u &&
       bufferVa == 0x01B0A300u && length == 57344u &&
       ((unsigned __int64)bufferVa + (unsigned __int64)length) == 0x01B18300ui64));"""
    io_old="ioStatusVa == 0x00424DA8u"
    io_new="""(ioStatusVa == 0x00424DA8u ||
      (ioStatusVa == 0x00424D58u && handleToken == 0x48000006u &&
       offsetLow == 0x00040000u && length == 57344u && bufferVa == 0x01B0A300u))"""
    marker="K1-V6N-EXACT-NESTED-LOCKED-DSK-20261105"
    check(marker not in s,"Already patched")
    pairs=[(h_old,h_new),(o_old,o_new),(end_old,end_new),(io_old,io_new)]
    for a,b in pairs:s=exact(s,a,b)
    trace_old='trace("K1-V6b APC QUEUED: bounded completed stream read"); /* K1-V6M-LOCKED-DSK-APC-262144-003800-20261105 */'
    s=exact(s,trace_old,trace_old+" /* "+marker+" */")
    check(all(s.count(b)==1 for a,b in pairs),"Replacement verification failed")
    for a,b in reversed(pairs):s=exact(s,b,a)
    s=exact(s,trace_old+" /* "+marker+" */",trace_old)
    check(s==data.decode("utf-8-sig").replace("\r\n","\n"),"Changes escaped audited predicates")
    s=data.decode("utf-8-sig").replace("\r\n","\n")
    for a,b in pairs:s=exact(s,a,b)
    s=exact(s,trace_old,trace_old+" /* "+marker+" */")
    result=s.replace("\n","\r\n").encode() if b"\r\n" in data else s.encode()
    check(parent.read_bytes()==data,"Parent modified during stage")
    record={"stage":"V6N_EXACT_NESTED_APC_SOURCE_UNTESTED",
       "parent_v6m_sha256":sha(data),"source_sha256":sha(result),
       "original_true_tu_count":64,"true_tu_sha256":m["true_tu_sha256"],
       "request":{"handle":"0x48000006","offset":"0x40000","length":57344,
         "buffer":"0x01B0A300","iosb":"0x00424D58","callback":"0x800000E8",
         "context":"0x00221F00","end":"0x01B18300"},
       "callback_delivery_unchanged":True,"unknown_apc_reads_fenced":True,
       "hardware_tested":False}
    files=((OUT/"main.cpp",result),(OUT/"v6n-manifest.json",(json.dumps(record,indent=2)+"\n").encode()))
    for p,b in files:check(not p.exists() or p.read_bytes()==b,"Changed destination exists: "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,b in files:
        if not p.exists():p.write_bytes(b)
    print(TAG+" SOURCE PASS: second nested locked.dsk APC read admitted under exact signature")
    print(TAG+" Prior reads, callback dispatch, TrueTUs and unknown-read hard fences preserved")
    print(TAG+" Hardware and XDK still UNTESTED")
if __name__=="__main__":
    try:run()
    except Exception as e:print(TAG+" BLOCKED: "+str(e),file=sys.stderr);sys.exit(1)
