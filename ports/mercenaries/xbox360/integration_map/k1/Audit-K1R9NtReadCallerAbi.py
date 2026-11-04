#!/usr/bin/env python3
"""K1-R9: read-only audit of hardware NtReadFile 44-byte frame and original caller.

No generated C, retail XBE, guest stack, native bridge, XDK, or XEX is modified.
Evidence is explicitly identified as the recorded K1-R8 hardware snapshot.
"""
from __future__ import annotations
import argparse, hashlib, json, re
from pathlib import Path

CALLER = 0x0023A3CE
THUNK = 0x800000DB
FINGERPRINT = "K1-R8-NTREAD-44-PROOF-8D29EA80D45BFD1F"
WORDS = [0,0x48000003,0,0x800000E8,0x00221F00,0x00424DA8,
         0x01B33300,0x00025000,0x008BF78C,0x08EC8000,0]
CALL_ESP = 0x008BF768
SAVED_ESP = 0x008BF794
RETAIL_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"

def digest(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest().upper()

def validate_log(log:Path)->dict:
    s=log.read_text(encoding="utf-8-sig",errors="replace")
    a=re.findall(r"K1-R8 NTREAD 44-RAW A:[^\r\n]*",s)
    b=re.findall(r"K1-R8 NTREAD 44-RAW B:[^\r\n]*",s)
    if FINGERPRINT not in s or not a or not b:
        raise ValueError("R8 fingerprint or matched raw stack evidence missing")
    pairs=list(zip(a,b))
    def get(line,key):
        m=re.search(r"\b"+re.escape(key)+r"=([0-9A-Fa-f]{8})\b",line)
        if not m: raise ValueError("Missing hardware evidence word: "+key)
        return int(m.group(1),16)
    matching=[]
    for x,y in pairs:
        wa=[get(x,"w"+str(i)) for i in range(6)]
        wb=[get(y,"w"+str(i)) for i in range(6,11)]
        if (get(x,"call")==CALL_ESP and get(x,"saved")==SAVED_ESP
            and get(x,"owner")==CALLER and get(y,"call")==CALL_ESP
            and wa+wb==WORDS):
            matching.append((x,y))
    if not matching: raise ValueError("R8 hardware words differ from pinned observed frame")
    if ("NtReadFile FRAME MISMATCH:" not in s or
        "BOUNDARY: kind=KERNEL_FRAME" not in s):
        raise ValueError("Original 36-byte ABI hard fence not present in hardware log")
    return {"verified_actual_log":True,"sha256":digest(log),"matching_frames":len(matching)}

def source_evidence(main:Path)->dict:
    data=main.read_bytes()
    s=data.decode("utf-8")
    signature=re.findall(r"(?m)^(?:static )?void phase5h_nt_read_file\(uint32_t savedEsp\)\s*\{",s)
    if len(signature)!=1 or s.count("if (savedEsp != callEsp + 36u)")!=1:
        raise ValueError("R8 native NtReadFile original frame guard changed/missing")
    if FINGERPRINT not in s or "K1-R8 NTREAD 44-RAW A:" not in s:
        raise ValueError("This is not the specific R8 instrumented source")
    lines=s.splitlines()
    hits=[i for i,l in enumerate(lines) if
          ("0x0023A3CE" in l or "0x0023a3ce" in l or
           "sub_0023A3CE" in l or "sub_0023a3ce" in l)]
    contexts=[]
    for i in hits[:24]:
        contexts.append({"line":i+1,"excerpt":"\n".join(
            "%d: %s"%(k+1,lines[k]) for k in range(max(i-5,0),min(i+6,len(lines))))})
    return {"sha256":hashlib.sha256(data).hexdigest(),"caller_mentions":len(hits),
            "caller_excerpts":contexts}

def retail_evidence(xbe:Path)->dict:
    if digest(xbe)!=RETAIL_SHA:
        raise ValueError("XBE SHA-256 does not match original supported retail image")
    # Do not assume VA-to-raw mapping; require explicit parsing of actual XBE section.
    b=xbe.read_bytes()
    base=int.from_bytes(b[0x104:0x108],"little")
    n=int.from_bytes(b[0x11C:0x120],"little")
    table=int.from_bytes(b[0x120:0x124],"little")
    if not 0<n<=64 or base!=0x10000:
        raise ValueError("Unexpected retail XBE header/section count")
    offset=table-base
    if not 0<=offset<len(b)-n*56:
        raise ValueError("Retail section table out of range")
    matches=[]
    for i in range(n):
        h=offset+i*56
        va=int.from_bytes(b[h+4:h+8],"little")
        vsize=int.from_bytes(b[h+8:h+12],"little")
        raw=int.from_bytes(b[h+12:h+16],"little")
        rsize=int.from_bytes(b[h+16:h+20],"little")
        if va<=CALLER<va+min(vsize,rsize):
            at=raw+CALLER-va
            if at+128>len(b): raise ValueError("Retail caller bytes beyond file")
            matches.append((i,at))
    if len(matches)!=1: raise ValueError("Retail caller section not uniquely mapped")
    i,at=matches[0]
    try:
        from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    except ImportError as e:
        raise ValueError("Capstone required: python -m pip install capstone") from e
    dis=Cs(CS_ARCH_X86,CS_MODE_32)
    instructions=[{"va":"%08X"%x.address,"bytes":x.bytes.hex().upper(),
                   "instruction":x.mnemonic+" "+x.op_str}
                  for x in dis.disasm(b[at:at+96],CALLER)]
    return {"sha256":RETAIL_SHA,"section_index":i,"raw_offset":at,
            "caller_disassembly_first_96_bytes":instructions,
            "note":"Entry-point window only, not an entire callsite or ABI conclusion."}

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--r8-main",type=Path,required=True)
    p.add_argument("--output",type=Path,required=True)
    p.add_argument("--xbox-log",type=Path)
    p.add_argument("--retail-xbe",type=Path)
    a=p.parse_args()
    report={"status":"K1_R9_ORIGINAL_CALLER_ABI_AUDIT_NO_ABI_CHANGE",
        "hardware_snapshot_source":"Previously captured R8 xbWatson; independently verify with --xbox-log",
        "caller":"%08X"%CALLER,"kernel_thunk":"%08X"%THUNK,
        "call_esp":"%08X"%CALL_ESP,"saved_esp":"%08X"%SAVED_ESP,
        "observed_delta":SAVED_ESP-CALL_ESP,"canonical_delta":36,
        "extra_bytes_unexplained":8,
        "raw_words":[{"offset":4*i,"hex":"%08X"%w} for i,w in enumerate(WORDS)],
        "frame_hypotheses":["extra caller arguments","caller stack lifetime",
            "generated saved-ESP accounting"],"abi_proven":False,
        "xdk_built":False,"xbox_run_performed":False,
        "native_ntread_changed":False,"unsafe_44_byte_acceptance":False}
    report["r8_source"]=source_evidence(a.r8_main)
    if a.xbox_log: report["hardware_log"]=validate_log(a.xbox_log)
    if a.retail_xbe: report["retail_source"]=retail_evidence(a.retail_xbe)
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("[K1-R9] READ-ONLY AUDIT PASS; 44-byte frame captured, ABI NOT YET PROVEN")
    print("[K1-R9] Caller=0023A3CE thunk=800000DB frame=44 expected=36")
    print("[K1-R9] Original caller mentions in R8 main:",report["r8_source"]["caller_mentions"])
    print("[K1-R9] Retail caller disassembly:",bool(a.retail_xbe))
    print("[K1-R9] Hardware log separately verified:",bool(a.xbox_log))
    print("[K1-R9] Report:",a.output)
    print("[K1-R9] NO XDK; NO GUEST STACK PATCH; NO HARD FENCE BYPASS")

if __name__=="__main__":
    main()
