#!/usr/bin/env python3
from pathlib import Path
import hashlib,json,sys
R=Path.cwd()
P=R/"build/phase6_integration_map/k1_pixel_locked_dsk_apc_chain_v6n"
O=R/"build/phase6_integration_map/k1_pixel_locked_dsk_apc_range_v6o"
T=R/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
A="""    bufferVa >= 0x01B18000u &&
    bufferVa <= 0x01B57300u &&"""
B="""    (((bufferVa >= 0x01B18000u && bufferVa <= 0x01B57300u) ||
      (handleToken == 0x48000006u && offsetLow == 0x00040000u &&
       offsetHigh == 0u && length == 57344u &&
       bufferVa == 0x01B0A300u && ioStatusVa == 0x00424D58u &&
       apcRoutine == 0x800000E8u && apcContext == 0x00221F00u))) &&
    /* K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105 */"""
def h(b):return hashlib.sha256(b).hexdigest()
def req(p,msg):
    if not p:raise ValueError(msg)
def main():
    mpath=P/"v6n-manifest.json";src=P/"main.cpp"
    req(mpath.is_file() and src.is_file(),"Run V6n staging first")
    m=json.loads(mpath.read_text(encoding="utf-8-sig"))
    raw=src.read_bytes()
    req(m.get("stage")=="V6N_EXACT_NESTED_APC_SOURCE_UNTESTED","V6n identity drift")
    req(h(raw)==m.get("source_sha256"),"V6n source SHA mismatch")
    req(m.get("unknown_apc_reads_fenced") is True and m.get("callback_delivery_unchanged") is True,"V6n safety flags changed")
    tus=sorted(T.glob("translated_???.cpp"))
    req(len(tus)==64,"64 TrueTUs required")
    hashes={p.name:h(p.read_bytes()) for p in tus}
    req(hashes==m.get("true_tu_sha256"),"TrueTU hashes changed")
    old=raw.decode("utf-8-sig").replace("\r\n","\n")
    req(old.count(A)==1,"Expected unique V6n guest buffer range guard")
    req("K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105" not in old,"V6o already staged")
    req("bufferVa == 0x01B0A300u && length == 57344u" in old,"V6n exact APC end guard missing")
    req("ioStatusVa == 0x00424D58u" in old,"V6n IOSB guard missing")
    i=old.index(A)
    req("const bool k1V5ObservedApc" in old[max(0,i-2200):i],"Range guard not inside APC predicate")
    changed=old.replace(A,B,1)
    req(changed.replace(B,A,1)==old,"Unrelated changes detected")
    new=changed.replace("\n","\r\n").encode("utf-8") if b"\r\n" in raw else changed.encode("utf-8")
    req(src.read_bytes()==raw,"V6n source changed during staging")
    record={"stage":"V6O_EXACT_APC_BUFFER_RANGE_SOURCE_UNTESTED",
      "parent_v6n_sha256":h(raw),"source_sha256":h(new),
      "original_true_tu_count":64,"true_tu_sha256":hashes,
      "new_buffer":"0x01B0A300","length":57344,"offset":"0x40000",
      "handle":"0x48000006","iosb":"0x00424D58",
      "unknown_apc_reads_fenced":True,"callback_delivery_unchanged":True,
      "hardware_tested":False}
    files=[(O/"main.cpp",new),(O/"v6o-manifest.json",(json.dumps(record,indent=2)+"\n").encode("utf-8"))]
    for p,b in files:req(not p.exists() or p.read_bytes()==b,"Existing output differs: "+str(p))
    O.mkdir(parents=True,exist_ok=True)
    for p,b in files:
        if not p.exists():p.write_bytes(b)
    print("[K1-V6o] SOURCE PASS: exact nested APC buffer below old minimum")
    print("[K1-V6o] Prior stream guards and 64 TrueTUs preserved; hardware UNTESTED")
if __name__=="__main__":
    try:main()
    except Exception as e:print("[K1-V6o] BLOCKED: "+str(e),file=sys.stderr);sys.exit(1)
