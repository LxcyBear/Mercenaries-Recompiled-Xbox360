#!/usr/bin/env python3
"""K1 V6x: audit next original retail frontier function 0x0022F9BC from retail XBE.

Independent proof: SHA256-verified XBE + exact original functions.json range +
real Capstone x86-32 instruction CFG. Read-only; emits no executable code.
Unknown indirect control flow, overlapping instructions, unmapped branches
or undecoded bytes are reported and fenced, never silently synthesized.
"""
from __future__ import annotations
import argparse
from collections import deque
import hashlib
import importlib.util
import json
from pathlib import Path

TARGET=0x0022F9BC
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
ROOT=Path.cwd()
BASE=ROOT/"build/phase3n_final_abi_scale"
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
DEFAULT_XBES=[
    Path.home()/"OneDrive/Desktop/My Xbox/default.xbe",
    Path.home()/"Desktop/My Xbox/default.xbe",
]
OUTPUT=ROOT/"build/phase6_integration_map/k1_retail_22f9bc_recovery/retail_22f9bc_audit.json"
def must(condition,message):
    if not condition: raise ValueError(message)
def load(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    must(spec is not None and spec.loader is not None,"Missing original audit tool: "+str(path))
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m

def decode(cap,blob,sections,start,end,reader):
    cs=cap.Cs(cap.CS_ARCH_X86,cap.CS_MODE_32)
    cs.detail=True
    seen={}
    owner={}
    hazards=[]
    edges=[]
    q=deque([start])
    budget=4096
    while q and len(seen)<budget:
        pc=q.popleft()
        if pc in seen:continue
        if not(start<=pc<end):
            hazards.append("Control transfer exits function: 0x%08X"%pc)
            continue
        # Never permit an instruction to reach across the function boundary.
        raw=reader(blob,sections,pc,min(15,end-pc))
        insns=list(cs.disasm(raw,pc,count=1))
        if not insns or insns[0].address!=pc:
            hazards.append("Cannot decode instruction at 0x%08X"%pc)
            continue
        ins=insns[0]
        if pc+ins.size>end:
            hazards.append("Instruction at 0x%08X straddles function end"%pc)
            continue
        for i in range(pc,pc+ins.size):
            prior=owner.get(i)
            if prior is not None and prior!=pc:
                hazards.append("Overlapping decode %08X: %08X vs %08X"%(i,prior,pc))
            owner[i]=pc
        d={"va":"0x%08X"%pc,"size":ins.size,"bytes":ins.bytes.hex().upper(),
           "mnemonic":ins.mnemonic,"operands":ins.op_str}
        seen[pc]=d
        nxt=pc+ins.size
        if ins.group(cap.CS_GRP_RET):
            edges.append({"from":d["va"],"kind":"return"})
            continue
        if ins.mnemonic in ("int3","ud2","hlt"):
            hazards.append("Trap instruction at 0x%08X"%pc)
            edges.append({"from":d["va"],"kind":"trap"})
            continue
        if ins.group(cap.CS_GRP_JUMP):
            is_cond=ins.mnemonic not in ("jmp","ljmp")
            immediate=ins.operands and ins.operands[0].type==cap.CS_OP_IMM
            if immediate:
                dest=ins.operands[0].imm & 0xFFFFFFFF
                edges.append({"from":d["va"],"kind":"conditional" if is_cond else "direct_jump",
                              "to":"0x%08X"%dest})
                if start<=dest<end:
                    q.append(dest)
                else:
                    hazards.append("Branch from 0x%08X leaves function to 0x%08X"%(pc,dest))
            else:
                hazards.append("Indirect jump at 0x%08X: %s"%(pc,ins.op_str))
                edges.append({"from":d["va"],"kind":"indirect_jump","operand":ins.op_str})
            if is_cond:
                if nxt<end:q.append(nxt)
                else:hazards.append("Conditional fallthrough exits function at 0x%08X"%nxt)
            continue
        if ins.group(cap.CS_GRP_CALL):
            immediate=ins.operands and ins.operands[0].type==cap.CS_OP_IMM
            dest=(ins.operands[0].imm & 0xFFFFFFFF) if immediate else None
            edges.append({"from":d["va"],"kind":"call" if immediate else "indirect_call",
                          "to":"0x%08X"%dest if dest is not None else None,
                          "operand":ins.op_str})
            if dest is None:
                hazards.append("Indirect call at 0x%08X requires ABI proof"%pc)
        if nxt<end:q.append(nxt)
        else:hazards.append("Sequential fallthrough exits function at 0x%08X"%nxt)
    if q:hazards.append("Instruction budget exceeded")
    return {"instructions":[seen[x] for x in sorted(seen)],"edges":edges,
            "hazards":sorted(set(hazards)),
            "decoded_instruction_count":len(seen),
            "mapped_code_bytes":len(owner),
            "function_size":end-start,
            "unmapped_bytes":(end-start)-len(owner)}

def audit():
    import capstone as cap
    asm=load(K1/"Audit-K1D3DSwitchCases.py","v6x_retail_xbe")
    base=load(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py",
              "v6x_function_inventory")
    xbes=[p for p in DEFAULT_XBES if p.is_file()]
    must(xbes,"Original retail default.xbe not found in supported locations")
    hashes={str(p):hashlib.sha256(p.read_bytes()).hexdigest().upper() for p in xbes}
    valid=[p for p in xbes if hashes[str(p)]==RETAIL]
    must(valid,"No retail default.xbe matches pinned SHA256: "+repr(hashes))
    xbe=valid[0]
    blob,sections=asm.get_retail_sections(xbe)
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    must(TARGET in by_va,"Retail function 0x0022F9BC absent from original function inventory")
    row=by_va[TARGET]
    end=row["end"]
    must(row["start"]==TARGET and TARGET<end<=0x00255620,
         "Function range outside retail .text: "+repr(row))
    funcraw=asm.bytes_at(blob,sections,TARGET,end-TARGET)
    tree=decode(cap,blob,sections,TARGET,end,asm.bytes_at)
    generated=base.load_generated(BASE/"runtime/gen",by_name)
    generated_present=TARGET in generated
    result={
        "stage":"V6X_NEXT_FRONTIER_RETAIL_X86_AUDIT_ONLY",
        "retail_xbe_sha256":RETAIL,
        "retail_xbe_source":str(xbe),
        "function_entry":"0x%08X"%TARGET,
        "function_end_exclusive":"0x%08X"%end,
        "original_function_inventory_name":row.get("name"),
        "original_generated_c_exists":generated_present,
        "original_generated_c_file":generated[TARGET]["file"] if generated_present else None,
        "source_bytes_sha256":hashlib.sha256(funcraw).hexdigest(),
        "source_bytes_hex":funcraw.hex().upper(),
        "control_flow":tree,
        "safe_to_synthesize_guest_code":False,
        "safe_to_build_xex":False,
        "next_step":"Review exact retail instructions, actual call targets, stack/return ABI, and any indirect-control-flow hazards before implementing guest translation",
    }
    OUTPUT.parent.mkdir(parents=True,exist_ok=True)
    OUTPUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("[K1-V6x] RETAIL SHA PASS: "+RETAIL)
    print("[K1-V6x] Exact original function: 0x%08X..0x%08X (%d bytes)"%
          (TARGET,end,end-TARGET))
    print("[K1-V6x] Original generated C: "+("PRESENT: "+generated[TARGET]["file"] if generated_present else "ABSENT (confirmed)"))
    print("[K1-V6x] Decoded: %d instructions; hazards=%d"%(
          tree["decoded_instruction_count"],len(tree["hazards"])))
    for issue in tree["hazards"][:20]:
        print("[K1-V6x] HAZARD: "+issue)
    for ins in tree["instructions"][:60]:
        print("[K1-V6x] %s %-8s %-8s %s"%(
            ins["va"],ins["bytes"],ins["mnemonic"],ins["operands"]))
    if len(tree["instructions"])>60:
        print("[K1-V6x] Remaining instructions available in JSON report")
    print("[K1-V6x] REPORT: "+str(OUTPUT))
    print("[K1-V6x] SOURCE AUDIT COMPLETE. No source patch or XEX generated.")
if __name__=="__main__":
    try:audit()
    except Exception as exc:
        print("[K1-V6x] HARD FENCE: "+str(exc))
        raise SystemExit(1)
