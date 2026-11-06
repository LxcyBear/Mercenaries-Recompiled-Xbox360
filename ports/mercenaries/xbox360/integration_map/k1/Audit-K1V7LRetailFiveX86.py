#!/usr/bin/env python3
"""K1-V7L offline retail XBE five-frontier x86 proof + generated C ABI triage.

No guest source/retail bytes in report. No auto lifting/stubbing or bypass.
Capstone is only an instruction-boundary witness, not proof of perfect CFG.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,struct,sys
from pathlib import Path

SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGETS=(0x0022B150,0x0022B178,0x0022DDA4,0x0022E51F,0x00288F80)
def require(test,msg):
    if not test:raise ValueError(msg)
def hx(i):return "0x%08X"%i
def load(path):
    spec=importlib.util.spec_from_file_location("v7l_reader",path)
    require(spec is not None and spec.loader is not None,"original generated-source reader unavailable")
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def sections(b):
    require(b[:4]==b"XBEH" and len(b)>0x130,"Invalid retail XBE header")
    base,count,table=struct.unpack_from("<III",b,0x104)[0],struct.unpack_from("<I",b,0x11c)[0],struct.unpack_from("<I",b,0x120)[0]
    require(base==0x10000 and count==14,"Unexpected retail sections/base")
    require(base<=table and table-base+count*0x38<=len(b),"Section headers outside XBE")
    result=[]
    for i in range(count):
        off=table-base+i*0x38
        va,vs,raw,size=struct.unpack_from("<IIII",b,off+4)
        require(raw+size<=len(b),"Section bytes exceed retail XBE")
        result.append((va,vs,raw,size))
    return result
def extract(b,ss,va,size):
    owners=[x for x in ss if x[0]<=va and va+size<=x[0]+min(x[1],x[3])]
    require(len(owners)==1,"Requested function bytes not uniquely contained in original raw section "+hx(va))
    base,_,raw,_=owners[0]
    return b[raw+(va-base):raw+(va-base)+size]
def validate_one(code,va):
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    dis=Cs(CS_ARCH_X86,CS_MODE_32);dis.detail=True
    seq=list(dis.disasm(code,va))
    consumed=sum(i.size for i in seq)
    # linear sweep is ambiguous when code intermixes embedded data.
    return {
        "linear_decoded_bytes":consumed,
        "raw_function_bytes":len(code),
        "linear_consumes_all":consumed==len(code),
        "linear_instruction_count":len(seq),
        "first_instruction":seq[0].mnemonic if seq else None,
        "last_instruction":seq[-1].mnemonic if seq else None,
        "ret_instruction_count":sum(i.mnemonic.startswith("ret") for i in seq),
        "call_instruction_count":sum(i.mnemonic=="call" for i in seq),
        "jump_instruction_count":sum(i.group(1) for i in seq),
        "possible_float_or_simd_instruction_count":sum(i.mnemonic.startswith(("f","xmm","movss","movsd","addss","mulss","subss")) for i in seq),
        "linear_sweep_is_not_cfg_proof":True,
    }
def main():
    p=argparse.ArgumentParser()
    for key in ("xbe","v7k","ranges","generated","emitter","v7i_main","v7i_manifest","out"):
        p.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    retail=a.xbe.read_bytes()
    require(hashlib.sha256(retail).hexdigest().upper()==SHA,"Retail XBE SHA mismatch (no analysis)")
    ss=sections(retail)
    v7k=json.loads(a.v7k.read_text(encoding="utf-8-sig"))
    require(v7k.get("stage")=="V7K_FIVE_FUNCTION_TARGETED_METADATA_ONLY","V7K evidence manifest mismatch")
    manifest=json.loads(a.v7i_manifest.read_text(encoding="utf-8-sig"))
    mainhash=hashlib.sha256(a.v7i_main.read_bytes()).hexdigest()
    require(manifest.get("source_sha256")==mainhash and
            v7k.get("parent_v7i_sha256")==mainhash,
            "V7I source identity drift")
    reader=load(a.emitter)
    ranges,byname=reader.load_ranges(a.ranges)
    generated=reader.load_generated(a.generated,byname)
    require(len(generated)>10000,"Source corpus incomplete")
    bycandidate={int(x["address"],16):x for x in v7k["candidates"]}
    require(set(bycandidate)==set(TARGETS),"V7K candidate set changed")
    results=[]
    for va in TARGETS:
        entry=bycandidate[va]
        r=ranges.get(va)
        require(r and r["end"]>va and r["end"]-va==entry["original_range"]["size"],
                "Original x86 function ranges changed at "+hx(va))
        blob=extract(retail,ss,va,r["end"]-va)
        linear=validate_one(blob,va)
        gen=generated.get(va)
        orig=gen.get("source","") if gen else ""
        masked=reader.mask_noncode(orig)
        src_calls=sorted({int(v,16) for v in re.findall(r"\bsub_([0-9a-fA-F]{8})\s*\(",masked)}-{va})
        # Only categorize evidence. Never generate a translated function
        # directly from a linear sweep of mixed retail code and data.
        results.append({
            "address":hx(va),"retail_function_size":len(blob),
            "retail_function_sha256":hashlib.sha256(blob).hexdigest(),
            "disassembly":linear,
            "original_generated_source":bool(gen),
            "source_sha256":hashlib.sha256(orig.encode()).hexdigest() if orig else None,
            "generated_direct_calls":[hx(c) for c in src_calls],
            "generated_source_file":gen.get("file") if gen else None,
            "stage_candidate":bool(gen) and entry["source_only_candidate"],
            "needs_manual_cfg_and_stack_abi_proof":not bool(gen),
            "output_contains_original_game_bytes":False,
        })
    report={
        "status":"K1_V7L_EXACT_RETAIL_FIVE_FUNCTION_X86_WITNESS_SOURCE_ONLY",
        "retail_sha256":SHA,"v7i_source_sha256":mainhash,
        "v7k_metadata_sha256":hashlib.sha256(a.v7k.read_bytes()).hexdigest(),
        "count":len(results),"targets":results,
        "limits":["Capstone linear decode is NOT exact control-flow recovery",
                  "Non-returning branches, indirect jumps, embedded data and SEH need individual checks",
                  "Stack cleanup, x87 and register effects must match actual x86 before staging",
                  "No unsupported Event/APC NtReadFile form admitted"],
        "source_only":True,"xdk_build":False,"xbox_run":False,
    }
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7L] EXACT RETAIL XBE SHA PASS; five function raw spans independently hashed")
    for row in results:
        d=row["disassembly"]
        print("[K1-V7L] %s bytes=%d linear=%d/%d calls=%d ret=%d generated=%s ready_for_manual_ABI=%s"%(
            row["address"],row["retail_function_size"],d["linear_decoded_bytes"],
            d["raw_function_bytes"],d["call_instruction_count"],
            d["ret_instruction_count"],row["original_generated_source"],row["stage_candidate"]))
    print("[K1-V7L] METADATA REPORT "+str(a.out))
    print("[K1-V7L] NO XDK / NO XBOX / NO GAME BYTES EXPORTED / NO STUBS")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7L] HARD FENCE "+str(e),file=sys.stderr);sys.exit(1)
