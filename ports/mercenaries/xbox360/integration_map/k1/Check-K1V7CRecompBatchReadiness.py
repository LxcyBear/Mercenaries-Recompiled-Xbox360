#!/usr/bin/env python3
"""V7C: offline preflight for five-function recomp-style batch source emission.

Deliberately does NOT lower opcode families into invented APIs. It identifies
source-verified SIMD store helpers, existing callee owners, original ABI and
every source opcode *together*. Ready/blocked is a truthful build gate.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
D=ROOT/"build/phase6_integration_map/k1_batch_recomp_recovery_v7"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
V6Z=ROOT/"build/phase6_integration_map/k1_pixel_retail_22f9bc_v6z"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
INPUT=D/"v7b_five_function_recomp_inputs.json"
OUTPUT=D/"v7c_batch_codegen_gate.json"
TARGETS=(0x0022F49E,0x0022F51C,0x0022F5A7,0x0022F6A5,0x0022F7C6)
def need(ok,msg):
    if not ok:raise ValueError(msg)
def module(p,n):
    spec=importlib.util.spec_from_file_location(n,p)
    need(spec is not None and spec.loader is not None,"Missing module "+str(p))
    m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m);return m
def run():
    raw=INPUT.read_bytes()
    data=json.loads(raw)
    need(data["stage"]=="V7B_FIVE_FUNCTION_EXACT_XBE_AND_RECOMP_TEMPLATE_EVIDENCE"
         and data["retail_sha256"]==SHA and
         data["hardware_root"]=="0x0022F5A7" and
         data["safe_to_build_xex"] is False,"V7B original batch provenance changed")
    items={int(f["entry"],16):f for f in data["source_gaps"]}
    need(set(items)==set(TARGETS),"Expected exactly five missing retail functions")
    base=module(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py","v7c_recomp")
    planner=module(K1/"Plan-K1NextICallBatch.py","v7c_owners")
    by_va,by_name=base.load_ranges(ROOT/"build/phase3n_final_abi_scale/analysis/disasm/functions.json")
    gen=base.load_generated(ROOT/"build/phase3n_final_abi_scale/runtime/gen",by_name)
    parent=V6Z/"main.cpp"
    manifest=json.loads((V6Z/"v6z-manifest.json").read_text(encoding="utf-8-sig"))
    need(manifest["source_sha256"]==hashlib.sha256(parent.read_bytes()).hexdigest(),
         "V6z source hash changed")
    owners,status=planner.owner_inventory(parent.read_text(encoding="utf-8",errors="replace"),SHARDS)
    need(status["parent_64_true_tu_sha256"]==manifest["true_tu_sha256"],
         "Original TrueTU input hashes changed")
    header=(SHARDS/"translated_runtime.h").read_text(encoding="utf-8",errors="replace")
    # Header may only contain extern declarations; real helper implementations
    # may live in main.cpp or support headers. Search all local compiled sources.
    sources=[("main.cpp",parent.read_text(encoding="utf-8",errors="replace")),
             ("translated_runtime.h",header)]
    for p in sorted(SHARDS.glob("translated_???.cpp")):
        sources.append((p.name,p.read_text(encoding="utf-8",errors="replace")))
    # Presence of a call is NOT evidence of a valid implementation. Require a
    # definition-style symbol or a matching macro definition in local sources.
    helpers=("recomp_xmm_movlps_store","recomp_xmm_movhps_store",
             "recomp_xmm_unpckhps","recomp_xmm_unpcklps",
             "recomp_xmm_movhlps","recomp_xmm_shufps",
             "recomp_xmm_load","recomp_xmm_store","RECOMP_XMM_BINARY_RR")
    helper_proofs={}
    for symbol in helpers:
        declarations=[];uses=[]
        escaped=re.escape(symbol)
        def_re=re.compile(
            r'(?m)^\s*(?:#\s*define\s+|(?:static\s+)?(?:inline\s+)?(?:void|int|bool|float|double)\s+)'+escaped+r'\s*\(')
        use_re=re.compile(r'\b'+escaped+r'\s*\(')
        for name,source in sources:
            if def_re.search(source):declarations.append(name)
            if use_re.search(source):uses.append(name)
        helper_proofs[symbol]={"definition_like_sources":declarations[:8],
                               "usage_sources":uses[:8],
                               "proven_defined_in_compiled_sources":bool(declarations)}
    results=[]
    all_callees=set()
    for va in TARGETS:
        f=items[va]
        need(f["instructions"] and
             f["entry"]=="0x%08X"%va and
             by_va[va]["end"]==int(f["end"],16),
             "Function boundary drift %08X"%va)
        calls=[int(e["target"],16) for e in f["edges"] if e["type"]=="direct_call"]
        all_callees.update(calls)
        opcodes=sorted({i["mnemonic"] for i in f["instructions"]})
        needs={
          "x87":any(n.startswith("f") for n in opcodes),
          "sse":any(n in {"movaps","movss","shufps","mulps","addps","movlps","movhps","movhlps","unpcklps","unpckhps"} for n in opcodes),
          "partial_upper_store":any(i["mnemonic"]=="movhps" and i["operands"].startswith("qword ptr [") for i in f["instructions"]),
          "indirect_call":any(e["type"]=="indirect_call" for e in f["edges"])
        }
        result={"entry":f["entry"],"instruction_count":len(f["instructions"]),
                "ret_abi":f["ret_abi"],"opcodes":opcodes,"direct_callees":["0x%08X"%x for x in calls],
                "needs":needs,"already_generated":va in gen,"compiled":va in owners}
        results.append(result)
    callee_proof=[]
    for c in sorted(all_callees):
        x=planner.classify(c,by_va,gen)
        callee_proof.append({"address":"0x%08X"%c,"retail_class":x["kind"],
                             "compiled_owners":owners.get(c,[]),
                             "routed":c in status["main_pack_lookup_vas"]})
    blockers=[]
    if any(x["needs"]["partial_upper_store"] for x in results) and not helper_proofs["recomp_xmm_movhps_store"]["proven_defined_in_compiled_sources"]:
        blockers.append("MOVHPS qword-memory STORE: no definition proven in existing TrueTU/runtime source; source example was LOAD only")
    for row in callee_proof:
        if not row["compiled_owners"] or not row["routed"]:
            blockers.append("Callee not compiled and routed: "+row["address"])
    # Existing template occurrences are examples, not a complete generated
    # translation. They do not prove register liveness, alignment, aliasing,
    # FPU control word, or all original opcode semantics.
    blockers.append("197 retail opcode-specific C translations have not been produced or verified by xboxrecomp")
    result={"stage":"V7C_SSE_X87_RECOMP_FIVE_FUNCTION_SOURCE_READINESS_GATE",
            "retail_sha256":SHA,"verified_inputs_sha256":hashlib.sha256(raw).hexdigest(),
            "functions":results,"callee_closure":callee_proof,
            "runtime_helpers":helper_proofs,
            "blocking_requirements":blockers,
            "ready_for_xdk":False,
            "xbox_hardware_invoked":False,
            "generated_guest_code_modified":False}
    OUTPUT.write_text(json.dumps(result,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7C] VERIFIED FIVE-FUNCTION RECOMP/XBE SOURCE INPUT PASS")
    for row in results:
        print("[K1-V7C] %s instructions=%d ret=%s SSE=%s x87=%s upper_store=%s"%
              (row["entry"],row["instruction_count"],row["ret_abi"],
               row["needs"]["sse"],row["needs"]["x87"],row["needs"]["partial_upper_store"]))
    for row in callee_proof:
        print("[K1-V7C] CALLEE %s compiled=%s routed=%s"%
              (row["address"],",".join(row["compiled_owners"]) or "NO",row["routed"]))
    for b in blockers:print("[K1-V7C] BUILD FENCE: "+b)
    print("[K1-V7C] REPORT: "+str(OUTPUT))
    print("[K1-V7C] NO XDK; NO GUEST SOURCE CHANGE.")
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("[K1-V7C] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
