#!/usr/bin/env python3
"""Recover retail-original RsMain 0017A302 from PC developer patch 429.

The PC port adds an instrumentation-only recomp_asset_dispatch_checkpoint
before the original LEA/PUSH. Its helper has no original Xbox ABI.
Require exact PC patch-template hashes AND original XBE x86 evidence,
then remove only this exact single call. No fake helper or return value.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re
from pathlib import Path
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
INDEX=429
NAME="RsMain asset dispatch checkpoint"
HELPER="recomp_asset_dispatch_checkpoint"
START=0x0017A302
BEFORE_SHA="9edc6249afd13a8f599f5bc7d4827a665b8779463411d8a99851dfb62e051c52"
AFTER_SHA="0a14ed695710013c87627dca55ffb11658c5ea207b1683bc9f55b5e8851decb3"
SCRIPT="ports/mercenaries/scripts/Patch-Generated.py"
INVENTORY="ports/mercenaries/data/generated-patch-inventory.json"
def digest(s):return hashlib.sha256(s.encode("utf-8")).hexdigest()
def need(ok,why):
    if not ok:raise ValueError(why)
def load(path):
    spec=importlib.util.spec_from_file_location("v6p_retail_asset_xbe",path)
    need(spec is not None and spec.loader is not None,"Retail XBE auditor missing")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def templates(root):
    obj=json.loads((root/INVENTORY).read_text(encoding="utf-8-sig"))
    need(obj.get("retail_xbe_sha256","").upper()==RETAIL,"PC inventory retail identity changed")
    rows=[x for x in obj["transformations"] if x.get("name")==NAME]
    need(len(rows)==1,"PC patch 429 absent/duplicated")
    row=rows[0]
    need(row.get("index")==INDEX and row.get("guest_sites")==["0017A302"] and
         row.get("host_helpers")==[HELPER] and
         row.get("before_sha256")==BEFORE_SHA and row.get("after_sha256")==AFTER_SHA,
         "PC patch 429 inventory diverged")
    txt=(root/SCRIPT).read_text(encoding="utf-8")
    rgx=(r'GeneratedPatch\(\s*"'+re.escape(NAME)+r'"\s*,\s*"""(?P<before>.*?)"""\s*,\s*"""(?P<after>.*?)"""\s*,\s*\)')
    matches=list(re.finditer(rgx,txt,re.DOTALL))
    need(len(matches)==1,"PC patch 429 template absent/duplicated")
    before,after=matches[0].group("before","after")
    need(digest(before)==BEFORE_SHA and digest(after)==AFTER_SHA,
         "PC patch 429 templates SHA mismatch")
    need(before=="loc_0017A302: ;\n    edx = esp + 0x48;\n    PUSH32(esp, edx);\n",
         "Unexpected original retail template")
    need(after=="loc_0017A302: ;\n    recomp_asset_dispatch_checkpoint(ebx, esi, esp + 0x48u);\n    edx = esp + 0x48;\n    PUSH32(esp, edx);\n",
         "Unexpected instrumented PC template")
    return before,after
def xbe_proof(xbe,auditor):
    from capstone import Cs,CS_ARCH_X86,CS_MODE_32
    audit=load(auditor)
    blob,sections=audit.get_retail_sections(xbe)
    b=audit.bytes_at(blob,sections,START,16)
    instructions=list(Cs(CS_ARCH_X86,CS_MODE_32).disasm(b,START,count=2))
    need(len(instructions)==2 and instructions[0].address==START and
         instructions[0].mnemonic=="lea" and
         re.fullmatch(r"edx, \[esp \+ 0x48\]",instructions[0].op_str) is not None and
         instructions[1].mnemonic=="push" and instructions[1].op_str=="edx" and
         instructions[1].address==START+instructions[0].size,
         "Retail XBE at 0017A302 is not LEA edx,[esp+48] / PUSH edx: "+str(
             [(i.mnemonic,i.op_str) for i in instructions]))
    return {"retail_sha256":RETAIL,"va":"0x0017A302",
            "original_x86":[{"va":"0x%08X"%i.address,"instruction":i.mnemonic+" "+i.op_str}
                            for i in instructions]}
def restore(source,root,proof):
    need(proof.get("retail_sha256")==RETAIL and proof.get("va")=="0x0017A302",
         "Missing original XBE proof")
    before,after=templates(root)
    normalized=source.replace("\r\n","\n")
    need(normalized.count(HELPER)==1,"PC checkpoint call absent/duplicated")
    loc="loc_0017A302: ;"
    need(normalized.count(loc)==1,"Original retail location label not unique")
    exact_after=after.replace("MEM32(","GUEST_READ32(")
    site=normalized.index(loc)
    tick="    PHASE4C_BUDGET_TICK(0x0017A302u);\n"
    if normalized.startswith(loc+"\n"+tick,site):
        old=loc+"\n"+tick+after.split("\n",1)[1]
        new=loc+"\n"+tick+before.split("\n",1)[1]
    else:
        old=exact_after
        new=before
    need(normalized.count(old)==1 and normalized[site:site+len(old)]==old,
         "Translated PC checkpoint differs from SHA-pinned template")
    changed=normalized.replace(old,new,1)
    need(HELPER not in changed and changed.replace(new,old,1)==normalized,
         "Retail restoration escaped exact checkpoint site")
    return changed,{"index":INDEX,"site":"0x0017A302","original_xbe_proof":proof,
                    "before_sha256":BEFORE_SHA,"after_sha256":AFTER_SHA,
                    "no_fabricated_helper":True,"retail_original_guest_instructions_restored":True}
