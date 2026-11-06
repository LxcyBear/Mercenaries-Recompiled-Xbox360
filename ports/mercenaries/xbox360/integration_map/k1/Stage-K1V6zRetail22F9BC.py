#!/usr/bin/env python3
"""V6z: lift ALL verified retail 22F9BC x87 instructions, stage with V6w.

Unlike a guessed matrix formula, each emitted source statement comes from
the SHA-verified exact XBE opcode stream. Whitelist-only x86/x87 lifter.
Conserves V6w, 64 real TrueTUs, seven stream reads and native log summary.
Hard fences unsupported opcodes, unbalanced x87 or stack, missing source.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
BASE=ROOT/"build/phase3n_final_abi_scale"
EVIDENCE=ROOT/"build/phase6_integration_map/k1_retail_22f9bc_recovery/retail_22f9bc_audit.json"
PARENT=ROOT/"build/phase6_integration_map/k1_pixel_retail_22fa9e_v6w"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_retail_22f9bc_v6z"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGET=0x0022F9BC
END=0x0022FA9E
MARK="K1-V6Z-RETAIL22F9BC-X87-OPCODE-LIFT"
LOOKUP=re.compile(r'(?m)^(?:static[ \t]+)?recomp_func_t phase4c_lookup_pack_func\(uint32_t xbox_va\)\n\{')
CANON="static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
OPT='#pragma optimize("", on)'
PLACE="/* K1_V6Z_PACK_OPT_ON_HIDDEN */"
def need(v,m):
    if not v:raise ValueError(m)
def sha(v):return hashlib.sha256(v).hexdigest()
def load(p,n):
    spec=importlib.util.spec_from_file_location(n,p)
    need(spec is not None and spec.loader is not None,"Missing maintained module: "+str(p))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

# Address operands used by original code are exact x86 register-relative or
# absolute 32-bit addresses, NOT host addresses.
def addr(x):
    x=x.lower().strip()
    m=re.fullmatch(r'(?:dword ptr )?\[(.+)\]',x)
    need(m,"Unexpected x86 memory operand: "+x)
    inside=m.group(1).strip()
    if re.fullmatch(r'0x[0-9a-f]+',inside):
        return inside+"u"
    m=re.fullmatch(r'(eax|ebp)(?: ([+-]) (0x[0-9a-f]+|[0-9]+))?',inside)
    need(m,"Unsupported memory base/index: "+inside)
    base,sign,off=m.groups()
    if not sign:return base
    return "%s %s %su"%(base,sign,off)

def f32(x):return "GUEST_READF32("+addr(x)+")"
def dst(x):return "GUEST_WRITEF32("+addr(x)+", (float)fp_top());"
def emit(ins, state):
    op=ins["mnemonic"].lower()
    operand=ins["operands"].lower().strip()
    va=int(ins["va"],16)
    v="0x%08X"%va
    stm=[]
    if op=="push" and operand=="ebp":
        need(state["esp"]==0,"Unexpected second EBP prologue")
        state["esp"]=-4
        stm=["PUSH32(esp, ebp);"]
    elif op=="mov" and operand=="ebp, esp":
        need(state["esp"]==-4,"EBP prologue unexpectedly ordered")
        stm=["ebp = esp;"]
    elif op=="sub" and operand=="esp, 0x10":
        need(state["esp"]==-4,"Unexpected ESP subtraction")
        state["esp"]-=16
        stm=["esp -= 0x10u;"]
    elif op=="mov" and operand in ("eax, dword ptr [ebp + 0xc]","eax, dword ptr [ebp + 8]"):
        stm=["eax = GUEST_READ32("+addr(operand.split(", ",1)[1])+");"]
    elif op=="fld":
        if operand=="":need(False,"Unknown empty FLD at "+v)
        if operand=="st(0)" or re.fullmatch(r'st\([0-7]\)',operand):
            n=int(operand[3])
            stm=["{ double _fp_copy = fp_st(%du); fp_push(_fp_copy); }"%n]
        else:
            stm=["fp_push("+f32(operand)+");"]
        state["fp"]+=1
    elif op=="fld1":
        need(not operand,"Unexpected FLD1 operand")
        stm=["fp_push(1.0);"]
        state["fp"]+=1
    elif op=="fldz":
        need(not operand,"Unexpected FLDZ operand")
        stm=["fp_push(0.0);"]
        state["fp"]+=1
    elif op in ("fmul","fadd","fsub"):
        rhs=None
        if re.fullmatch(r'st\([0-7]\)',operand):
            index=int(operand[3])
            need(state["fp"]>index,"x87 stack underflow %s at %s"%(operand,v))
            rhs="fp_st(%du)"%index
        else:rhs=f32(operand)
        need(state["fp"]>0,"x87 arithmetic with empty stack at "+v)
        sign={"fmul":"*","fadd":"+","fsub":"-"}[op]
        stm=["fp_top() %s= %s;"%(sign,rhs)]
    elif op=="fst" or op=="fstp":
        need(state["fp"]>0,"x87 store with empty stack at "+v)
        if op=="fstp" and operand=="st(0)":
            stm=["fp_pop();"]
        else:
            need(operand.startswith("dword ptr ["),"Unsupported x87 store: "+operand)
            stm=[dst(operand)]
            if op=="fstp":stm.append("fp_pop();")
        if op=="fstp":state["fp"]-=1
    elif op=="leave":
        need(state["esp"]==-20,"Unexpected x86 frame at LEAVE")
        need(state["fp"]==0,"Unbalanced x87 stack depth at LEAVE: "+str(state["fp"]))
        stm=["esp = ebp;", "POP32(esp, ebp);"]
        state["esp"]=0
    elif op=="ret" and operand=="8":
        need(state["esp"]==0 and state["fp"]==0,"Unbalanced x86/x87 at return")
        stm=["esp += 12u; return; /* ret 8 */"]
    else:need(False,"Unsupported retail opcode %s %s at %s"%(op,operand,v))
    return ["    "+part+" /* "+v+" "+op+" "+operand+" */" for part in stm]

def lifter(e):
    ins=e["control_flow"]["instructions"]
    need(len(ins)==87 and not e["control_flow"]["hazards"],
         "Expected 87 original CFG-safe instructions")
    # For a linear function, sorted instruction addresses must cover all
    # 226 bytes. This also rejects data holes / unseen cold branch paths.
    cursor=TARGET
    for insn in ins:
        need(int(insn["va"],16)==cursor,
             "V6z refuses holes/branches in x87 stream at %08X"%cursor)
        cursor+=insn["size"]
    need(cursor==END,"V6z x87 instruction stream does not reach retail ret")
    state={"fp":0,"esp":0}
    result=["void sub_0022F9BC(void)","{",
        "    uint32_t ebp = 0u; /* local emulated x86 frame register */",
        "    #define fp_push(v) (g_fp_stack[--g_fp_top & 7u] = (v))",
        "    #define fp_pop() (g_fp_top++)",
        "    #define fp_top() g_fp_stack[g_fp_top & 7u]",
        "    #define fp_st(i) g_fp_stack[(g_fp_top + (uint32_t)(i)) & 7u]",
        "    RECOMP_TRACE_FUNC(0x0022F9BCu);",
        "loc_0022F9BC: ;"]
    for i in ins:
        result.extend(emit(i,state))
    result+=["    #undef fp_push","    #undef fp_pop","    #undef fp_top",
             "    #undef fp_st","}"]
    need(state=={"fp":0,"esp":0},"Unbalanced generated x87 or x86 stack")
    return "\n".join(result)+"\n"

def run():
    a=json.loads(EVIDENCE.read_text(encoding="utf-8-sig"))
    need(a["retail_xbe_sha256"]==SHA and
         a["function_entry"]=="0x0022F9BC" and
         a["function_end_exclusive"]=="0x0022FA9E" and
         a["original_generated_c_exists"] is False and
         a["control_flow"]["decoded_instruction_count"]==87 and
         a["control_flow"]["function_size"]==226 and
         not a["control_flow"]["hazards"],
         "Original SHA-verified retail V6x evidence mismatch")
    old=load(K1/"Audit-K1D3DSwitchCases.py","v6z_xbe")
    xbes=[p for p in [Path.home()/"OneDrive/Desktop/My Xbox/default.xbe",
                      Path.home()/"Desktop/My Xbox/default.xbe"]
          if p.is_file() and sha(p.read_bytes()).upper()==SHA]
    need(xbes,"Original SHA-verified default.xbe missing")
    blob,sections=old.get_retail_sections(xbes[0])
    raw=old.bytes_at(blob,sections,TARGET,END-TARGET)
    need(sha(raw)==a["source_bytes_sha256"] and
         raw.hex().upper()==a["source_bytes_hex"],
         "Original function bytes changed since V6x")
    lifted=lifter(a)
    pm=json.loads((PARENT/"v6w-manifest.json").read_text(encoding="utf-8-sig"))
    orig=(PARENT/"main.cpp").read_bytes()
    need(pm["stage"]=="V6W_ORIGINAL_RETAIL_22FA9E_X87_TRANSLATION_SOURCE_UNTESTED" and
         pm["source_sha256"]==sha(orig) and
         pm["root_entry"]=="0x0022FA9E" and
         pm["original_instruction_count"]==56 and
         pm["native_summary_preserved"] and
         pm["unknown_frontiers_fenced"] and
         pm["seven_async_reads_preserved_in_source"],
         "V6w proven-parent source/ABI drift")
    hashes={p.name:sha(p.read_bytes()) for p in SHARDS.glob("translated_???.cpp")}
    need(len(hashes)==64 and hashes==pm["true_tu_sha256"],
         "64 original TrueTU files changed")
    base=load(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py","v6z_base")
    bb=load(ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bb_frontier22dda4.py","v6z_bb")
    bc=load(ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bc_broad_sweep.py","v6z_bc")
    planner=load(K1/"Plan-K1NextICallBatch.py","v6z_owner")
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    generated=base.load_generated(BASE/"runtime/gen",by_name)
    need(TARGET in by_va and by_va[TARGET]["end"]==END and
         TARGET not in generated and by_va[TARGET]["name"]=="sub_0022F9BC",
         "Retail function inventory or generated body changed")
    source=orig.decode("utf-8").replace("\r\n","\n")
    owners,counts=planner.owner_inventory(source,SHARDS)
    compiled=counts["compiled_in_64_or_main"]
    need(TARGET not in compiled and TARGET not in counts["main_pack_lookup_vas"] and
         0x0022FA9E in compiled and 0x0022FA9E in counts["main_pack_lookup_vas"],
         "New retail target already compiled OR V6w root not dispatchable")
    generated[TARGET]={"name":"sub_0022F9BC","source":lifted,
                       "file":"V6z-retail-x87-87-exact-instruction-lift"}
    need(len(LOOKUP.findall(source))==1 and OPT in source,
         "V6w pack lookup/optimization fence drift")
    new=source.replace(LOOKUP.search(source).group(),CANON,1).replace(OPT,PLACE)
    new+='\n#pragma optimize("", off)\n#pragma optimize("", on)\n'
    old_root,old_entry=bc.SWEEP_ROOT,bc.instrument_root_entry
    old_support=base.support_symbols
    old_standard=base.STANDARD_CALLS.copy()
    available={"sub_%08X"%v for v in compiled}
    available.update(old_support((SHARDS/"translated_runtime.h").read_text(
        encoding="utf-8",errors="replace")))
    try:
        bc.SWEEP_ROOT=TARGET
        bc.instrument_root_entry=lambda rendered,name:rendered
        base.support_symbols=lambda t:old_support(t)|available
        packed,rendered,frontiers,pruned=bc.insert_pack_members(
            new,base,bb,generated,[TARGET],compiled|{TARGET},require_sweep_root=True)
    finally:
        bc.SWEEP_ROOT,bc.instrument_root_entry=old_root,old_entry
        base.support_symbols=old_support
        base.STANDARD_CALLS.clear();base.STANDARD_CALLS.update(old_standard)
    need(not pruned and TARGET in rendered and not frontiers,
         "V6z original x87 translation unsafe: "+repr((pruned,frontiers)))
    need(packed.count(CANON)==1 and PLACE in packed,
         "V6z pack lookup/optimization drift")
    packed=packed.replace(CANON,LOOKUP.search(source).group(),1).replace(PLACE,OPT)
    lookup="case 0x0022F9BCu: return sub_0022F9BC;"
    need(packed.count(lookup)==1 and
         packed.count("case 0x0022FA9Eu: return sub_0022FA9E;")==1,
         "Lost V6w root dispatch or new V6z retail lookup")
    for literal in ("K1-V6W-RETAIL22FA9E-X87-EBP-20261105",
                    "K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105",
                    "K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                    "K1D3D SECOND: native Xenos Reset PASS",
                    "P6DQ ROCKET HARD STOP",
                    "OLD TICK COUNT: 61948779",
                    "GUEST DISPLAY CALLS: %u",
                    "DISPLAY_CALLS > 0: YES"):
        need(source.count(literal)>0 and packed.count(literal)==source.count(literal),
             "V6w native/guest invariant drift: "+literal)
    packed="/* "+MARK+" */\n"+packed
    result=packed.replace("\n","\r\n").encode() if b"\r\n" in orig else packed.encode()
    manifest={
      "stage":"V6Z_ORIGINAL_RETAIL_22F9BC_X87_SOURCE_UNTESTED",
      "parent_v6w_sha256":sha(orig),"source_sha256":sha(result),
      "retail_sha256":SHA,"function_entry":"0x0022F9BC",
      "function_end_exclusive":"0x0022FA9E",
      "function_bytes_sha256":a["source_bytes_sha256"],
      "original_instruction_count":87,"x87_instruction_count":80,
      "original_ret_esp":8,"new_direct_callees":0,
      "retained_v6w_function":"0x0022FA9E",
      "true_tu_sha256":hashes,"native_summary_preserved":True,
      "seven_async_reads_preserved_in_source":True,
      "unknown_frontiers_fenced":True,
      "hardware_tested":False,"guest_display_calls_verified":False}
    candidates=[(OUT/"main.cpp",result),
                (OUT/"v6z-manifest.json",(json.dumps(manifest,indent=2)+"\n").encode())]
    for p,data in candidates:
        need(not p.exists() or p.read_bytes()==data,
             "Existing V6z candidate differs; no overwrite: "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,data in candidates:
        if not p.exists():p.write_bytes(data)
    need((PARENT/"main.cpp").read_bytes()==orig,"Parent V6w source mutated")
    print("[K1-V6z] SOURCE PASS: SHA-pinned retail 22F9BC 87/87 instruction lift")
    print("[K1-V6z] x87 stack balanced; ret8; V6w 22FA9E preserved")
    print("[K1-V6z] 64 TrueTUs, 7-read streaming and native end summary unchanged")
    print("[K1-V6z] SOURCE ONLY. XDK / Xbox hardware not yet verified.")
if __name__=="__main__":
    try:run()
    except Exception as exc:
        print("[K1-V6z] HARD FENCE: "+str(exc),file=sys.stderr)
        raise SystemExit(1)
