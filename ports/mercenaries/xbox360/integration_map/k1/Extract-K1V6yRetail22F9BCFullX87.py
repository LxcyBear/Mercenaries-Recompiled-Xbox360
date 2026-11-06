#!/usr/bin/env python3
"""K1 V6y: full retail 22F9BC x87 instruction / dependency report.

Uses verified V6x retail audit; never adds a fake translation or builds XEX.
Preserves order of all 87 x86 instructions, identifies callees and returns.
"""
from __future__ import annotations
import hashlib,json,sys
from pathlib import Path
ROOT=Path.cwd()
D=ROOT/"build/phase6_integration_map/k1_retail_22f9bc_recovery"
SRC=D/"retail_22f9bc_audit.json"
OUT=D/"v6y_full_x87_instruction_and_abi_report.txt"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
def need(v,msg):
    if not v: raise ValueError(msg)
def run():
    j=json.loads(SRC.read_text(encoding="utf-8-sig"))
    need(j["retail_xbe_sha256"]==SHA and
         j["function_entry"]=="0x0022F9BC" and
         j["function_end_exclusive"]=="0x0022FA9E",
         "Not the pinned 22F9BC retail function")
    cfg=j["control_flow"]
    ins=cfg["instructions"]
    need(len(ins)==87 and cfg["decoded_instruction_count"]==87 and
         cfg["function_size"]==226 and cfg["hazards"]==[],
         "Unexpected instructions or CFG hazards")
    b=bytes.fromhex(j["source_bytes_hex"])
    need(len(b)==226 and hashlib.sha256(b).hexdigest()==j["source_bytes_sha256"],
         "Original retail bytes differ from V6x evidence")
    names={x["mnemonic"].lower() for x in ins}
    xfpu=[x for x in ins if x["mnemonic"].lower().startswith("f")]
    calls=[x for x in cfg["edges"] if x["kind"] in ("call","indirect_call")]
    rets=[x for x in ins if x["mnemonic"].lower().startswith("ret")]
    lines=[
      "[K1-V6y] EXACT RETAIL XBE 0x0022F9BC..0x0022FA9E",
      "[K1-V6y] SHA256: "+SHA,
      "[K1-V6y] Function bytes SHA256: "+j["source_bytes_sha256"],
      "[K1-V6y] Complete original instruction stream (87 decoded instructions):",
    ]
    for row in ins:
        lines.append("%s %-20s %-8s %s"%(
            row["va"],row["bytes"],row["mnemonic"],row["operands"]))
    lines.extend([
      "",
      "[K1-V6y] X87 / ABI FACTS",
      "x87 instruction count: %d"%len(xfpu),
      "Distinct mnemonics: "+", ".join(sorted(names)),
      "Original ret instructions: "+str([(x["va"],x["mnemonic"],x["operands"]) for x in rets]),
      "Call edges: "+str(calls),
      "All control-flow edges: "+str(cfg["edges"]),
      "Unmapped bytes (may be dead code/data/padding): "+str(cfg["unmapped_bytes"]),
      "Original generated C present: "+str(j.get("original_generated_c_exists")),
      "Original generated C source file: "+str(j.get("original_generated_c_file")),
      "[K1-V6y] NO SOURCE PATCH; NO XDK; NO HARDWARE CLAIM",
    ])
    OUT.write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("[K1-V6y] 22F9BC ORIGINAL X87 INVENTORY PASS")
    print("[K1-V6y] instructions=%d x87=%d calls=%d returns=%d hazards=0"%
          (len(ins),len(xfpu),len(calls),len(rets)))
    print("[K1-V6y] ORIGINAL RETURN ABI: "+repr([(x["mnemonic"],x["operands"]) for x in rets]))
    print("[K1-V6y] CALL EDGES: "+repr(calls))
    print("[K1-V6y] LAST 30 INSTRUCTIONS:")
    for row in ins[-30:]:
        print("[K1-V6y] %s %-8s %s"%(row["va"],row["mnemonic"],row["operands"]))
    print("[K1-V6y] REPORT: "+str(OUT))
if __name__=="__main__":
    try:run()
    except Exception as exc:
        print("[K1-V6y] HARD FENCE: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
