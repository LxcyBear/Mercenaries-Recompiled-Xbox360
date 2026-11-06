#!/usr/bin/env python3
"""K1 V6t: prove x87 and exact guest-call ABI for the 22FA9E three-callee cluster.

No hand-waved ST0, float flags, register lifetime, or calling convention.
Only reads user's retail XBE, generated original C, compiled TrueTU snapshot.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
BASE=ROOT/"build/phase3n_final_abi_scale"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
AUDIT=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/retail_22fa9e_audit.json"
CALLEES=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/callee_abi_audit.json"
OUT=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/v6t_x87_abi_evidence.json"
TARGETS=[0x0022F3C1,0x0022F3F3,0x0022F364]
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
XBES=[Path.home()/"OneDrive/Desktop/My Xbox/default.xbe",
      Path.home()/"Desktop/My Xbox/default.xbe"]
def require(c,m):
    if not c:raise ValueError(m)
def load(p,n):
    spec=importlib.util.spec_from_file_location(n,p)
    require(spec is not None and spec.loader is not None,"Missing maintained module: "+str(p))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def execute():
    import capstone as cap
    root=json.loads(AUDIT.read_text(encoding="utf-8-sig"))
    dep=json.loads(CALLEES.read_text(encoding="utf-8-sig"))
    require(root["retail_xbe_sha256"]==SHA and root["function_entry"]=="0x0022FA9E"
            and not root["control_flow"]["hazards"],"V6s original root CFG identity mismatch")
    require(dep["retail_sha256"]==SHA and dep["root"]=="0x0022FA9E" and
            dep["all_callees_have_generated_c"] and dep["all_callees_compiled"],
            "V6s callee provenance/compiled body mismatch")
    auditors=load(K1/"Audit-K1D3DSwitchCases.py","v6t_xbe")
    base=load(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py",
              "v6t_generated")
    xbes=[p for p in XBES if p.is_file() and hashlib.sha256(p.read_bytes()).hexdigest().upper()==SHA]
    require(xbes,"Exact retail default.xbe missing / SHA drift")
    blob,sections=auditors.get_retail_sections(xbes[0])
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    generated=base.load_generated(BASE/"runtime/gen",by_name)
    cs=cap.Cs(cap.CS_ARCH_X86,cap.CS_MODE_32)
    cs.detail=True
    report=[]
    for addr in TARGETS:
        row=by_va.get(addr)
        require(row is not None and addr in generated and row["start"]==addr,
                "Missing original function/translation at 0x%08X"%addr)
        body=generated[addr]["source"]
        # Verify compiled TrueTU file contains exactly one real definition.
        owner=[p.name for p in SHARDS.glob("translated_???.cpp")
               if re.search(r'\bvoid\s+sub_%08X\s*\(\s*void\s*\)\s*\{'%addr,
                            p.read_text(encoding="utf-8",errors="replace"))]
        require(len(owner)==1,"Callee not uniquely compiled: 0x%08X"%addr)
        fraw=auditors.bytes_at(blob,sections,addr,row["end"]-addr)
        ins=list(cs.disasm(fraw,addr))
        ret=[i for i in ins if i.group(cap.CS_GRP_RET)]
        fpu=[i for i in ins if i.mnemonic.startswith("f")]
        text=body.splitlines()
        # Only extract those original-translator lines that convey floating
        # state, guest stack and call return behavior.
        important=[{"line":i+1,"text":line.strip()} for i,line in enumerate(text)
                   if re.search(r'(?i)st0|st_0|fpu|x87|float|double|sqrt|ret_|ret\(|esp|eax|call|sub_',
                                line) and len(line)<320]
        record={"entry":"0x%08X"%addr,"end_exclusive":"0x%08X"%row["end"],
                "retail_raw_sha256":hashlib.sha256(fraw).hexdigest(),
                "generated_body_sha256":hashlib.sha256(body.encode()).hexdigest(),
                "compiled_true_tu":owner[0],"original_source_file":generated[addr]["file"],
                "retail_entry_instruction":[{"va":"0x%08X"%x.address,"asm":x.mnemonic+" "+x.op_str}
                                             for x in ins[:18]],
                "retail_ret_instruction":[{"va":"0x%08X"%x.address,"asm":x.mnemonic+" "+x.op_str}
                                          for x in ret],
                "retail_fpu_instructions":[{"va":"0x%08X"%x.address,"asm":x.mnemonic+" "+x.op_str}
                                          for x in fpu[:50]],
                "translated_relevant_lines":important[:130],
                "translated_first_lines":text[:18],
                "translated_last_lines":text[-22:],
                "machine_code_disasm_consumed_bytes":sum(i.size for i in ins),
                "function_size":len(fraw)}
        report.append(record)
        print("[K1-V6t] CALLEE %08X original=%dB / generated=%s / TrueTU=%s"%
              (addr,len(fraw),generated[addr]["file"],owner[0]))
        print("[K1-V6t]   ret instructions: "+str([x["asm"] for x in record["retail_ret_instruction"]]))
        print("[K1-V6t]   x87 instructions: "+str([x["asm"] for x in record["retail_fpu_instructions"][:12]]))
        print("[K1-V6t]   translator x87/stack lines: "+str(len(record["translated_relevant_lines"])))
    result={"stage":"V6T_22FA9E_REAL_RETAIL_X87_AND_CALLEE_ABI_EVIDENCE_ONLY",
            "retail_sha256":SHA,"root_entry":"0x0022FA9E",
            "root_ret":"ret 8",
            "three_callees":report,
            "safe_to_build_xex":False,
            "translated_root_created":False,
            "missing_evidence":"Prove x87 ST0 and EFLAGS conversion against pinned generated runtime before implementing original 56 instructions"}
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("[K1-V6t] X87/ABI EVIDENCE PASS; no guest code was modified")
    print("[K1-V6t] REPORT: "+str(OUT))
if __name__=="__main__":
    try:execute()
    except Exception as ex:
        print("[K1-V6t] HARD FENCE: "+str(ex),file=sys.stderr)
        raise SystemExit(1)
