#!/usr/bin/env python3
"""Retail-authentic reversal of pinned PC patch 279 at x86 0x002221CD.

The PC recompilation deliberately extends the original streaming idle
budget policy by invoking recomp_stream_admit_idle(esi, edi). The Xbox
recompilation cannot call that PC-only feature. Restore the *retail* jge
if and only if:
  (1) pinned PC patch 279 before/after SHA matches maintained inventory;
  (2) original SHA-verified retail XBE disassembles to MOV/ADD/CMP/JGE;
  (3) source has precisely the known changed branch, label and no extra
      guest operations, allowing only the known phase4c budget tick;
  (4) no PC helper calls remain.
No arbitrary helper stub, no constant-return substitution.
"""
from __future__ import annotations

import hashlib
import importlib.util
import json
import re
from pathlib import Path

PC_SHA = "f513ae4e041401b7b032410016940971488d523b"
RETAIL_SHA = "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
NAME = "streaming idle budget deadlock recovery"
HELPER = "recomp_stream_admit_idle"
INDEX = 279
START = 0x002221CD
END = 0x002221DD
DEST = 0x00222236
BEFORE_SHA = "45ba494ec4ec756e55429e53aee9873e1baa7496ede916f64cac95be77b814c5"
AFTER_SHA = "2310de3627cf2bcd0f16179f042a032d9699a61e677a96667d92a99ee3b43a86"
PC_SCRIPT = "ports/mercenaries/scripts/Patch-Generated.py"
PC_INVENTORY = "ports/mercenaries/data/generated-patch-inventory.json"

def digest(s:str)->str:
    return hashlib.sha256(s.encode("utf-8")).hexdigest()

def load(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,path)
    if spec is None or spec.loader is None:
        raise ValueError("Retail section auditor missing: "+str(path))
    module=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module

def templates(root:Path)->tuple[str,str,dict]:
    inventory=json.loads((root/PC_INVENTORY).read_text(encoding="utf-8"))
    if inventory.get("retail_xbe_sha256","").upper()!=RETAIL_SHA:
        raise ValueError("PC patch inventory original retail XBE SHA changed")
    hits=[row for row in inventory.get("transformations",[])
          if row.get("name")==NAME]
    if len(hits)!=1:
        raise ValueError("PC original streaming patch absent/duplicated")
    item=hits[0]
    if (item.get("index")!=INDEX or
        item.get("guest_sites")!=["002221CD","00222236"] or
        item.get("host_helpers")!=[HELPER] or
        item.get("before_sha256")!=BEFORE_SHA or
        item.get("after_sha256")!=AFTER_SHA):
        raise ValueError("Original PC patch 279 guest/retail inventory mismatch")
    code=(root/PC_SCRIPT).read_text(encoding="utf-8")
    pattern=(r'GeneratedPatch\(\s*"' + re.escape(NAME) +
             r'"\s*,\s*"""(?P<before>.*?)"""\s*,\s*"""(?P<after>.*?)"""\s*,\s*\)')
    matches=list(re.finditer(pattern,code,re.DOTALL))
    if len(matches)!=1:
        raise ValueError("Pinned PC patch 279 before/after templates missing or duplicated")
    before,after=matches[0].group("before","after")
    if digest(before)!=BEFORE_SHA or digest(after)!=AFTER_SHA:
        raise ValueError("PC source transformations differ from retail SHA inventory")
    if (not before.startswith("loc_002221CD: ;\n") or
        before.count("CMP_GE(ebx, 0x7D000)")!=1 or
        "goto loc_00222236;" not in before or
        HELPER in before or
        not after.startswith("loc_002221CD: ;\n") or
        after.count(HELPER+"(esi, edi)")!=1 or
        not after.count("CMP_GE(ebx, 0x7D000)")):
        raise ValueError("PC original streaming patch semantics changed")
    return before,after,item

def validate_instructions(insns:list)->dict:
    if len(insns)!=4 or insns[0].address!=START or (
        any(insns[i+1].address!=insns[i].address+insns[i].size
            for i in range(3))):
        raise ValueError("Retail original streaming site has noncontiguous x86 instructions")
    mov,add,cmp,jge=insns
    if (mov.mnemonic!="mov" or
        not re.fullmatch(r"ebx, (?:dword ptr )?\[esi \+ 0x3b4\]",mov.op_str) or
        add.mnemonic!="add" or add.op_str!="ebx, edi" or
        cmp.mnemonic!="cmp" or
        cmp.op_str not in ("ebx, 0x7d000","ebx, 512000") or
        jge.mnemonic not in ("jge","jnl") or
        int(jge.op_str,16)!=DEST or
        jge.address+jge.size!=END):
        raise ValueError(
            "Retail original 002221CD instruction MOV [esi+3B4] / ADD ebx,edi / "
            "CMP ebx,0x7D000 / JGE 00222236 not proven: "+repr(
                [(i.address,i.mnemonic,i.op_str) for i in insns]))
    )
    return {
        "retail_sha256":RETAIL_SHA,
        "original_002221cd_mov_add_cmp_jge":True,
        "first_va":"0x002221CD",
        "fallthrough_va":"0x002221DD",
        "jge_target":"0x00222236",
        "instructions":[{"va":"0x%08X"%i.address,
                         "mnemonic":i.mnemonic,"operands":i.op_str}
                         for i in insns],
    }

def verify_x86(xbe:Path,retail_auditor:Path)->dict:
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    audit=load(retail_auditor,"k1_r7_retail_streaming_279_xbe")
    blob,sections=audit.get_retail_sections(xbe)
    data=audit.bytes_at(blob,sections,START,24)
    insns=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(data,START,count=4))
    proof=validate_instructions(insns)
    proof["instruction_bytes_hex"]=data[:END-START].hex().upper()
    return proof

def normalized(code:str)->str:
    code=re.sub(r"/\*.*?\*/","",code,flags=re.DOTALL)
    code=re.sub(r"//[^\n]*","",code)
    return re.sub(r"\s+","",code)

def restore(source:str,root:Path,*,proof:dict)->tuple[str,dict]:
    before,after,item=templates(root)
    if (proof.get("original_002221cd_mov_add_cmp_jge") is not True or
        proof.get("retail_sha256")!=RETAIL_SHA or
        proof.get("fallthrough_va")!="0x002221DD" or
        proof.get("jge_target")!="0x00222236"):
        raise ValueError("Retail XBE instruction provenance for original 221CD branch absent")
    src=source.replace("\r\n","\n")
    if src.count(HELPER+"(esi, edi)")!=1 or src.count(HELPER)!=1:
        raise ValueError("PC-only streaming helper call absent/duplicated/unrecognized")
    labels={}
    for addr in ("002221CD","002221DD"):
        ms=list(re.finditer(r"(?m)^[ \t]*loc_"+addr+r":[ \t]*;[ \t]*(?:\n|$)",src))
        if len(ms)!=1:
            raise ValueError("Original streaming x86 code label "+addr+" absent/duplicated")
        labels[addr]=ms[0]
    first,last=labels["002221CD"],labels["002221DD"]
    if first.end()>=last.start() or last.start()-first.end()>750:
        raise ValueError("Original label ownership/window changed around retail 221CD")
    window=src[first.end():last.start()]
    budget=re.compile(r"(?m)^[ \t]*PHASE4C_BUDGET_TICK\s*\(\s*0x002221CDu\s*\)\s*;[ \t]*(?:\n|$)")
    budget_ticks=budget.findall(window)
    if len(budget_ticks)>1:
        raise ValueError("More than one original guest budget instrumentation checkpoint")
    cleaned=budget.sub("",window)
    after_body=after.split("\n",1)[1]
    dialect="GUEST_READ32" if "GUEST_READ32(" in cleaned else "MEM32"
    expected=after_body.replace("MEM32(",dialect+"(")
    if normalized(cleaned)!=normalized(expected):
        raise ValueError(
            "Generated original 002221CD branch does not match exactly "
            "the PC SHA-verified developer patch after-template; "
            "window_sha256=%s, expected_sha256=%s" % (
                digest(normalized(cleaned)),digest(normalized(expected))))
    restored_body=before.split("\n",1)[1].replace("MEM32(",dialect+"(")
    # Preserve only the proven local tick instrumentation, not the
    # PC-only comment/hook that adds nonretail branching.
    restored_window=("".join(budget_ticks)+restored_body)
    out=src[:first.end()]+restored_window+src[last.start():]
    if (HELPER in out or
        normalized(out[first.end():first.end()+len(restored_window)])!=
            normalized(restored_window) or
        out.count("if (CMP_GE(ebx, 0x7D000)) goto loc_00222236;")!=1 or
        out[:first.end()]!=src[:first.end()] or
        out[first.end()+len(restored_window):]!=src[last.start():]):
        raise ValueError("Nonretail PC helper not uniquely reversed / unexpected guest mutation")
    return out,{
        "status":"PINNED_PC_PATCH_279_RESTORED_TO_ORIGINAL_RETAIL",
        "pc_reference_git_commit":PC_SHA,
        "pc_patch_index":INDEX,
        "pc_patch_name":NAME,
        "original_guest_site":"0x002221CD",
        "retail_original_branch":"CMP_GE(ebx, 0x7D000) / JGE 0x00222236",
        "before_template_sha256":digest(before),
        "after_template_sha256":digest(after),
        "input_xbox_generated_C_sha256":digest(src),
        "output_retail_restored_C_sha256":digest(out),
        "generated_source_dialect":dialect,
        "budget_tick_preserved":len(budget_ticks)==1,
        "x86_retail_proof":proof,
        "pc_only_host_helper_removed":True,
        "mock_host_helper_or_guest_abi_used":False,
    }

def selftest():
    from tempfile import TemporaryDirectory
    before=(
        "loc_002221CD: ;\n"
        "    ebx = MEM32(esi + 0x3B4);\n"
        "    ebx = ebx + edi;\n"
        "    if (CMP_GE(ebx, 0x7D000)) goto loc_00222236; /* jge: greater or equal (signed >=) */\n"
    )
    after=(
        "loc_002221CD: ;\n"
        "    ebx = MEM32(esi + 0x3B4);\n"
        "    ebx = ebx + edi;\n"
        "    /* Permit one bounded read when pinned completed buffers leave disk idle. */\n"
        "    if (CMP_GE(ebx, 0x7D000) && !recomp_stream_admit_idle(esi, edi)) goto loc_00222236;\n"
    )
    assert digest(before)==BEFORE_SHA and digest(after)==AFTER_SHA
    inventory={
        "retail_xbe_sha256":RETAIL_SHA,
        "transformations":[{
            "index":INDEX,"name":NAME,
            "guest_sites":["002221CD","00222236"],
            "host_helpers":[HELPER],
            "before_sha256":digest(before),"after_sha256":digest(after),
        }]
    }
    proof={
        "retail_sha256":RETAIL_SHA,
        "original_002221cd_mov_add_cmp_jge":True,
        "fallthrough_va":"0x002221DD",
        "jge_target":"0x00222236",
    }
    with TemporaryDirectory() as tmp:
        root=Path(tmp)
        code=root/PC_SCRIPT
        inventory_file=root/PC_INVENTORY
        code.parent.mkdir(parents=True)
        inventory_file.parent.mkdir(parents=True)
        code.write_text(
            'GeneratedPatch(\n    "'+NAME+'",\n"""'+before+
            '""",\n"""'+after+'""",\n)\n',encoding="utf-8")
        inventory_file.write_text(json.dumps(inventory),encoding="utf-8")
        for dialect in ("MEM32","GUEST_READ32"):
            source=("void sub_00222190(void) {\n"+
                    after.replace("MEM32(",dialect+"(")+
                    "loc_002221DD: ;\n"
                    "  eax = 42;\n}\n")
            if dialect=="GUEST_READ32":
                source=source.replace(
                    "loc_002221CD: ;\n",
                    "loc_002221CD: ;\n    PHASE4C_BUDGET_TICK(0x002221CDu);\n")
            restored,meta=restore(source,root,proof=proof)
            assert HELPER not in restored
            assert "if (CMP_GE(ebx, 0x7D000)) goto loc_00222236;" in restored
            assert restored.count("eax = 42;")==1
            assert meta["pc_only_host_helper_removed"] and not meta["mock_host_helper_or_guest_abi_used"]
            assert meta["budget_tick_preserved"]==(dialect=="GUEST_READ32")
            for unsafe in (
                source.replace("0x7D000","0x7D001"),
                source.replace("ebx = ebx + edi;","ebx = ebx - edi;"),
                source.replace("loc_00222236","loc_00222237"),
                source.replace(HELPER+"(esi, edi)","false"),
                source.replace("loc_002221DD: ;","loc_002221DF: ;"),
                source.replace("loc_002221DD: ;",
                               "GUEST_WRITE32(esp, eax);\nloc_002221DD: ;"),
                source.replace("loc_002221DD: ;",
                               "loc_002221DD: ;\nloc_002221DD: ;"),
            ):
                try:
                    restore(unsafe,root,proof=proof)
                except ValueError:
                    pass
                else:
                    raise AssertionError("Unsafe original Xbox streaming source accepted")
            try:
                restore(source,root,proof={**proof,"jge_target":"0x00222237"})
            except ValueError:
                pass
            else:
                raise AssertionError("Unverified retail x86 destination accepted")
        # Synthetic original x86 regression (MOV ebx,[esi+3B4] ; ADD ebx,edi;
        # CMP ebx,0007D000 ; JGE short +59 => original fallthrough 221DD).
        from capstone import Cs,CS_ARCH_X86,CS_MODE_32
        code=bytes.fromhex("8B9EB403000001FB81FB00D007007D59")
        inst=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(code,START))
        assert validate_instructions(inst)["original_002221cd_mov_add_cmp_jge"]
        mutated=bytes.fromhex("8B9EB403000029FB81FB00D007007D59")
        try:
            validate_instructions(list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(mutated,START)))
        except ValueError:
            pass
        else:
            raise AssertionError("Wrong ADD operation accepted as retail")
    print("[K1-R7-RETAIL] SELFTEST PASS: PC patch 279 SHA before/after, XBE MOV/ADD/CMP/JGE, Xbox GUEST_READ32, guest tick, no fake streaming helper or XDK")

if __name__=="__main__":
    selftest()
