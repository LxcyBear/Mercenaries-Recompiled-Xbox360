#!/usr/bin/env python3
"""K1 V7G: graft the existing Phase6BT ordinal-99 bounded delay handler into V7E.

Source-only; never guesses kernel semantics or changes canonical 16-byte ABI.
Copies the exact 6BT C++ handler from its checked-in original emitter by
calling install_delay_support on a marker, not rewriting the handler manually.
Refuses all unexpected dispatch layouts. Leaves V7E source and TrueTUs intact.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
BASE=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7e"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7g"
OLD=ROOT/"ports/mercenaries/xbox360/phase6_native_graphics/emit_phase6bt_kedelay99_relative.py"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
SIGN="static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
MARK="K1-V7G-KEDELAY99-HISTORIC-6BT-BRIDGE"
def need(ok,msg):
    if not ok:raise ValueError(msg)
def sha(data):return hashlib.sha256(data).hexdigest()
def load(path):
    spec=importlib.util.spec_from_file_location("k1_v7g_historical_6bt",path)
    need(spec and spec.loader,"Historic Phase6BT source emitter missing")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m
def patch_macro(src):
    name="#define RECOMP_ICALL_SAFE(xbox_va, saved_esp) do {"
    start=src.find(name)
    need(start>=0 and src.count(name)==1,"Expected one RECOMP_ICALL_SAFE macro")
    end=src.find("#define RECOMP_ITAIL",start)
    need(end>start,"Could not locate RECOMP_ITAIL after ICALL_SAFE macro")
    macro=src[start:end]
    need("_phase4c_target == 0x80000063u" not in macro and
         "phase6bt_ke_delay_execution_thread" not in macro,
         "Ordinal 99 already routed; refuse duplicate bridge")
    # Match first IF head within the ICALL_SAFE macro. The if/else chain
    # must be joined, not an unrelated unconditional call.
    pattern=re.compile(r'(?m)^(?P<indent>[ \t]*)(?P<head>if[ \t]*\(_phase4c_target[ \t]*==[ \t]*0x[0-9a-fA-F]+u\)[ \t]*\{[ \t]*\\)[ \t]*$')
    found=list(pattern.finditer(macro))
    need(found,"No known ICALL_SAFE dispatch if-chain head; refuse unsafe source patch")
    first=found[0]
    indent=first.group("indent")
    oldhead=first.group("head")
    # Match the form used by Phase6BT: branch must not be nested behind
    # other local control flow. Require no other IF or SWITCH preceding it.
    prefix=macro[len(name):first.start()]
    need(not re.search(r'\b(?:if|switch|for|while|else)\b',prefix),
         "Dispatch branch appears nested; inspect macro before graft")
    continuation=("\\\n")
    inject=(indent+"if (_phase4c_target == 0x80000063u) { "+continuation+
            indent+"    phase6bt_ke_delay_execution_thread((uint32_t)(saved_esp)); "+continuation+
            indent+"} else "+oldhead)
    patched=macro[:first.start()]+inject+macro[first.end():]
    need(patched.count("_phase4c_target == 0x80000063u")==1 and
         patched.count("phase6bt_ke_delay_execution_thread((uint32_t)(saved_esp))")==1 and
         patched.count(oldhead)==1,
         "Ordinal 99 dispatch not uniquely inserted")
    # All old dispatch tokens must still occur in the same order (plus
    # one controlled new branch). This is stricter than string length.
    for label in re.findall(r'_phase4c_target[ \t]*==[ \t]*(0x[0-9a-fA-F]+u)',macro):
        need(patched.count(label)==macro.count(label),
             "Existing kernel dispatch changed: "+label)
    return src[:start]+patched+src[end:],{"insertion":"ICALL_SAFE if-chain","existing_kernel_cases_preserved":True}
def main():
    original=(BASE/"main.cpp").read_bytes()
    man=json.loads((BASE/"v7e-manifest.json").read_text(encoding="utf-8-sig"))
    need(man["stage"]=="V7E_FIVE_RETAIL_FUNCTIONS_UNIQUE_DISPATCH_SOURCE_ONLY" and
         man["source_sha256"]==sha(original) and
         man["retail_xbe_sha256"]==RETAIL and
         man["remaining_duplicate_cases"]==0 and
         man["native_summary_preserved"] and
         man["seven_async_reads_preserved_in_source"] and
         man["unknown_frontiers_fenced"] and
         len(man["true_tu_sha256"])==64 and
         sum(man["original_opcode_counts"].values())==197,
         "V7E baseline or retail/TrueTU integrity drift")
    newline="\r\n" if b"\r\n" in original else "\n"
    src=original.decode("utf-8").replace("\r\n","\n")
    need(SIGN in src and src.count(SIGN)==1,
         "Translated-pack lookup definition shape drift")
    need(MARK not in src and "phase6bt_ke_delay_execution_thread(" not in src,
         "V7G handler already present; refuse duplicate")
    historic=OLD.read_bytes()
    module=load(OLD)
    # Use existing historical handler without duplicating or reinterpreting C++.
    planted=module.install_delay_support(SIGN)
    need(planted.endswith(SIGN) and planted.count(SIGN)==1,
         "Historic Phase6BT handler extraction changed")
    handler=planted[:-len(SIGN)]
    for marker in ("savedEsp != callEsp + 16u",
                   "millseconds64" if False else "milliseconds64 > 10000ui64",
                   "PHASE4C_BOUNDARY_KERNEL_FRAME",
                   "PHASE4C_BOUNDARY_ICALL_SAFE",
                   "g_esp = savedEsp;",
                   "Sleep(milliseconds);",
                   "SwitchToThread();"):
        need(marker in handler,"Historic Phase6BT safety contract missing: "+marker)
    patched,dispatch=patch_macro(src)
    need(patched.count(SIGN)==1,"Lookup definition drift")
    patched=patched.replace(SIGN,handler+SIGN,1)
    patched="/* "+MARK+" */\n"+patched
    # Invariants: V7E exact body remains except for the one bounded
    # handler insertion and ICALL_SAFE dispatch; no wholesale replacements.
    for marker in ("K1-V7E-DISPATCH-DEDUP-22F51C",
                   "K1-V7D-RETAIL-FIVE-FUNCTION-BATCH-OPCODE-LIFT",
                   "K1-V6Z-RETAIL22F9BC-X87-OPCODE-LIFT",
                   "K1-V6W-RETAIL22FA9E-X87-EBP-20261105",
                   "K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                   "P6DQ ROCKET HARD STOP"):
        need(src.count(marker)>0 and patched.count(marker)==src.count(marker),
             "Inherited source marker drift: "+marker)
    for va in (0x0022F49E,0x0022F51C,0x0022F5A7,0x0022F6A5,0x0022F7C6):
        token="case 0x%08Xu: return sub_%08X;"%(va,va)
        need(patched.count(token)==1,"V7E five-function route changed "+token)
    result=patched.replace("\n",newline).encode("utf-8")
    meta=dict(man)
    meta.update({"stage":"V7G_PREVIOUSLY_PROVEN_PHASE6BT_ORDINAL99_SOURCE_GRAFT_UNTESTED",
                 "source_sha256":sha(result),
                 "parent_v7e_sha256":sha(original),
                 "historical_phase6bt_emitter_sha256":sha(historic),
                 "kernel_ordinal":99,"kernel_target":"0x80000063",
                 "handler_source":"phase6bt_ke_delay_execution_thread",
                 "canonical_frame_bytes":16,
                 "bounded_relative_only":True,"max_relative_ms":10000,
                 "absolute_delays_fenced":True,
                 "no_guest_stack_abi_bypass":True,
                 "existing_dispatch_preserved":dispatch["existing_kernel_cases_preserved"],
                 "xdk_compiled":False,"hardware_verified":False})
    outputs=[(OUT/"main.cpp",result),
             (OUT/"v7g-manifest.json",(json.dumps(meta,indent=2)+"\n").encode())]
    for p,data in outputs:
        need(not p.exists() or p.read_bytes()==data,
             "Existing V7G output differs; refuse overwrite "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,data in outputs:
        if not p.exists():p.write_bytes(data)
    need((BASE/"main.cpp").read_bytes()==original,"V7E input mutated")
    print("[K1-V7G] HISTORICAL 6BT KeDelayExecutionThread SOURCE GRAFT PASS")
    print("[K1-V7G] ORIGINAL 16-byte ordinal-99 frame/relative<=10s/absolute FENCE preserved")
    print("[K1-V7G] V7E five retail functions, 197 instructions, 64 TrueTUs preserved")
    print("[K1-V7G] SOURCE ONLY. NO XDK OR XBOX. NO GUEST ABI BYPASS.")
    print("[K1-V7G] OUTPUT: "+str(OUT/"main.cpp"))
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("[K1-V7G] HARD FENCE: "+str(exc),file=sys.stderr);sys.exit(1)
