#!/usr/bin/env python3
"""V6u: capture exact source ABI for translating retail x87 function 22FA9E.

Outputs only original generated callee implementations and relevant x87
runtime definitions, never modifies the guest or builds an XEX.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
BASE=ROOT/"build/phase3n_final_abi_scale"
RUNTIME=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
FRONTIER="0x0022FA9E"
CALLEES=(0x0022F3C1,0x0022F3F3,0x0022F364)
OUT=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/v6u_exact_translation_context.txt"
def require(v,msg):
    if not v:raise ValueError(msg)
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    require(spec and spec.loader,"Missing source module "+str(path))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def run():
    audit=json.loads((ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/retail_22fa9e_audit.json").read_text(encoding="utf-8-sig"))
    dep=json.loads((ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery/callee_abi_audit.json").read_text(encoding="utf-8-sig"))
    require(audit["function_entry"]==FRONTIER and not audit["control_flow"]["hazards"],
            "Retail root disassembly not proven")
    require(dep["all_callees_compiled"] and dep["all_callees_have_generated_c"],
            "Callee owner/translation drift")
    base=module(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py",
                "v6u_orig_source")
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    original=base.load_generated(BASE/"runtime/gen",by_name)
    report=["[K1-V6u] VERIFIED TRANSLATED CALLEE CONTEXT FOR 0x0022FA9E",
            "[K1-V6u] RETAIL_ROOT_INSTRUCTIONS"]
    for i in audit["control_flow"]["instructions"]:
        report.append("%s %s %-8s %s"%(i["va"],i["bytes"],i["mnemonic"],i["operands"]))
    for addr in CALLEES:
        require(addr in original,"Missing original generated C: %08X"%addr)
        src=original[addr]["source"]
        report.append("")
        report.append("[K1-V6u] TRANSLATED_CALLEE_%08X SHA256=%s"%(addr,hashlib.sha256(src.encode()).hexdigest()))
        report.extend(src.splitlines())
    # Find actual x87 register/flag helper definitions without exporting the
    # enormous runtime header; show exact source segments and nearby context.
    paths=[RUNTIME/"translated_runtime.h"]
    for path in paths:
        require(path.is_file(),"Missing TrueTU runtime: "+str(path))
        lines=path.read_text(encoding="utf-8",errors="replace").splitlines()
        chosen=set()
        for i,line in enumerate(lines):
            if re.search(r'(?i)\b(?:fpu|x87|st0|st_0|st1|st_1|fcom|fcomp|fnstsw|fstp|fld|fsub|fsqrt|float_to|cmp_float)\b',
                         line):
                chosen.update(range(max(0,i-4),min(len(lines),i+7)))
        report.append("")
        report.append("[K1-V6u] RUNTIME_HEADER_X87_CONTEXT %s matching_lines=%d"%
                      (path.name,len(chosen)))
        for i in sorted(chosen):
            report.append("%5d %s"%(i+1,lines[i]))
    report.append("[K1-V6u] END OF EVIDENCE; NO XEX OR GUEST PATCH")
    OUT.parent.mkdir(parents=True,exist_ok=True)
    OUT.write_text("\n".join(report)+"\n",encoding="utf-8")
    print("[K1-V6u] Exact retail root instructions: %d"%len(audit["control_flow"]["instructions"]))
    for addr in CALLEES:
        print("[K1-V6u] Callee %08X translated source ready"%addr)
    print("[K1-V6u] OUTPUT: "+str(OUT))
    print("[K1-V6u] Source extraction PASS; no guest modifications, no XDK")
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("[K1-V6u] HARD FENCE: "+str(e),file=sys.stderr)
        sys.exit(1)
