#!/usr/bin/env python3
"""K1 V6v: retail-faithful x86 22FA9E lift from pinned retail XBE.

The original corpus omitted this 129-byte function. Its 56 instructions
and three already-compiled x87 callees have been audited against SHA-verified
original retail bytes. We insert only a bounded source-derived translation
with original x87 flags, call ESP conventions and ret 8. No fake helper.
Uses the maintained TrueTU packer and V6rLOG hardware-verified parent.
"""
from __future__ import annotations
import hashlib,importlib.util,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
BASE=ROOT/"build/phase3n_final_abi_scale"
PARENT=ROOT/"build/phase6_integration_map/k1_native_end_summary_v6rlog"
SHARDS=ROOT/"build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards"
EVIDENCE=ROOT/"build/phase6_integration_map/k1_retail_22fa9e_recovery"
OUT=ROOT/"build/phase6_integration_map/k1_pixel_retail_22fa9e_v6v"
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
TARGET=0x0022FA9E
END=0x0022FB1F
CALLEES=(0x0022F3C1,0x0022F3F3,0x0022F364)
MARK="K1-V6V-RETAIL22FA9E-X87-20261105"
LOOKUP=re.compile(r'(?m)^(?:static[ \t]+)?recomp_func_t phase4c_lookup_pack_func\(uint32_t xbox_va\)\n\{')
CANON="static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{"
OPT='#pragma optimize("", on)'
PLACE="/* K1_V6V_PACK_OPT_ON_HIDDEN */"
SOURCE=r"""
void sub_0022FA9E(void)
{
    int _fpu_cmp = 0;
    #define fp_push(v) (g_fp_stack[--g_fp_top & 7u] = (v))
    #define fp_pop() (g_fp_top++)
    #define fp_top() g_fp_stack[g_fp_top & 7u]
    RECOMP_TRACE_FUNC(0x0022FA9Eu);

loc_0022FA9E: ;
    PUSH32(esp, ebp); /* push ebp */
    ebp = esp; /* mov ebp,esp */
    esp -= 0x10u; /* sub esp,0x10 */
    PUSH32(esp, esi);
    esi = GUEST_READ32(ebp + 0xCu);
    PUSH32(esp, edi);
    PUSH32(esp, esi);
    PUSH32(esp, 0); sub_0022F3C1(); /* call 0x0022F3C1 */
    GUEST_WRITEF32(ebp + 0xCu, (float)fp_top()); fp_pop(); /* fstp */

loc_0022FAB2: ;
    PUSH32(esp, ecx);
    fp_push(1.0); /* fld1 */
    PUSH32(esp, ecx);
    GUEST_WRITEF32(esp + 4u, (float)fp_top()); fp_pop(); /* fstp */
    fp_push(GUEST_READF32(ebp + 0xCu)); /* fld */
    GUEST_WRITEF32(esp, (float)fp_top()); fp_pop(); /* fstp */
    PUSH32(esp, 0); sub_0022F3F3(); /* call 0x0022F3F3 */
    if (eax == 0u) goto loc_0022FAD8; /* test eax,eax; je */

loc_0022FAC9: ;
    eax = GUEST_READ32(ebp + 8u);
    if (eax == esi) goto loc_0022FB19;

loc_0022FAD0: ;
    edi = eax;
    GUEST_WRITE32(edi, GUEST_READ32(esi)); edi += 4u; esi += 4u; /* movsd */
    GUEST_WRITE32(edi, GUEST_READ32(esi)); edi += 4u; esi += 4u; /* movsd */
    GUEST_WRITE32(edi, GUEST_READ32(esi)); edi += 4u; esi += 4u; /* movsd */
    GUEST_WRITE32(edi, GUEST_READ32(esi)); edi += 4u; esi += 4u; /* movsd */
    goto loc_0022FB19;

loc_0022FAD8: ;
    fp_push(GUEST_READF32(ebp + 0xCu));
    { double a = fp_top(); double b = GUEST_READF32(0x00302E44u);
      _fpu_cmp = (isnan(a) || isnan(b)) ? 2 : (a < b) ? -1 : (a > b) ? 1 : 0;
      g_x87_status_word = (uint16_t)((g_x87_status_word & ~0x4500u) |
          ((_fpu_cmp == 2) ? 0x4500u : (_fpu_cmp < 0) ? 0x0100u :
           (_fpu_cmp == 0) ? 0x4000u : 0u));
      fp_pop();
    } /* fcomp [0x302E44] */
    SET_LO16(eax, g_x87_status_word); /* fnstsw ax */
    if ((HI8(eax) & 0x41u) != 0u) goto loc_0022FB03; /* test ah,41; jne */

loc_0022FAE8: ;
    fp_push(GUEST_READF32(ebp + 0xCu));
    PUSH32(esp, ecx);
    fp_top() = sqrt(fp_top()); /* fsqrt */
    eax = ebp - 0x10u;
    ecx = esi;
    GUEST_WRITEF32(esp, (float)fp_top()); fp_pop();
    PUSH32(esp, eax);
    PUSH32(esp, 0); sub_0022F364(); /* call 0x0022F364 */
    esi = eax;
    eax = GUEST_READ32(ebp + 8u);
    goto loc_0022FAD0;

loc_0022FB03: ;
    eax = GUEST_READ32(ebp + 8u);
    GUEST_WRITEF32(eax, 0.0f);
    GUEST_WRITEF32(eax + 4u, 0.0f);
    GUEST_WRITEF32(eax + 8u, 0.0f);
    GUEST_WRITEF32(eax + 0xCu, 0.0f);

loc_0022FB19: ;
    POP32(esp, edi);
    POP32(esp, esi);
    esp = ebp; /* leave */
    POP32(esp, ebp);
    esp += 12u; return; /* ret 8 */
    #undef fp_push
    #undef fp_pop
    #undef fp_top
}
"""
def digest(b):return hashlib.sha256(b).hexdigest()
def need(ok,msg):
    if not ok:raise ValueError(msg)
def load(p,n):
    spec=importlib.util.spec_from_file_location(n,p)
    need(spec is not None and spec.loader is not None,"Missing maintained module "+str(p))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj);return obj
def validate_retail():
    evidence=json.loads((EVIDENCE/"retail_22fa9e_audit.json").read_text(encoding="utf-8-sig"))
    deps=json.loads((EVIDENCE/"callee_abi_audit.json").read_text(encoding="utf-8-sig"))
    need(evidence["retail_xbe_sha256"]==RETAIL and
         evidence["function_entry"]=="0x0022FA9E" and
         evidence["function_end_exclusive"]=="0x0022FB1F" and
         evidence["original_generated_c_exists"] is False and
         evidence["control_flow"]["decoded_instruction_count"]==56 and
         not evidence["control_flow"]["hazards"],"Retail function provenance/CFG drift")
    need(deps["retail_sha256"]==RETAIL and
         deps["all_callees_compiled"] and deps["all_callees_have_generated_c"] and
         {int(i["address"],16) for i in deps["retail_direct_callees"]}==set(CALLEES),
         "Compiled retail call dependencies drift")
    xbe=[p for p in [Path.home()/"OneDrive/Desktop/My Xbox/default.xbe",
                      Path.home()/"Desktop/My Xbox/default.xbe"]
         if p.is_file() and digest(p.read_bytes()).upper()==RETAIL]
    need(xbe,"SHA-verified original default.xbe missing")
    auditor=load(K1/"Audit-K1D3DSwitchCases.py","v6v_xbe")
    blob,sections=auditor.get_retail_sections(xbe[0])
    raw=auditor.bytes_at(blob,sections,TARGET,END-TARGET)
    need(digest(raw)==evidence["source_bytes_sha256"] and
         raw.hex().upper()==evidence["source_bytes_hex"],
         "Live retail function bytes differ from V6s 56-insn audit")
    # Compare root's exact opcode stream and call destinations, never the
    # recompiler's inferred source file name.
    calls={int(x["to"],16) for x in evidence["control_flow"]["edges"]
           if x["kind"]=="call" and x.get("to")}
    need(calls==set(CALLEES),"Original x86 direct-call edges changed")
    expected={
      0x0022FA9E:"push",0x0022FAAA:"call",0x0022FAAF:"fstp",
      0x0022FAC0:"call",0x0022FAC7:"je",0x0022FAD2:"movsd",
      0x0022FAD3:"movsd",0x0022FAD4:"movsd",0x0022FAD5:"movsd",
      0x0022FADB:"fcomp",0x0022FAE1:"fnstsw",0x0022FAE6:"jne",
      0x0022FAEC:"fsqrt",0x0022FAF7:"call",0x0022FB1B:"leave",
      0x0022FB1C:"ret"}
    got={int(i["va"],16):i["mnemonic"] for i in evidence["control_flow"]["instructions"]}
    need(all(got.get(a)==m for a,m in expected.items()),"Pinned x86 opcode/branch evidence drift")
    return evidence,deps
def run():
    evidence,deps=validate_retail()
    pmeta=json.loads((PARENT/"v6rlog-manifest.json").read_text(encoding="utf-8-sig"))
    parent=(PARENT/"main.cpp").read_bytes()
    need(pmeta["stage"]=="V6R_LOGGING_ONLY_SOURCE_UNTESTED" and
         pmeta["source_sha256"]==digest(parent) and
         pmeta["unknown_frontiers_fenced"] and
         pmeta["apc_reads_7_preserved_in_source"] and
         pmeta["guest_display_summary"],
         "V6rLOG verified source/summary drift")
    true_tus={p.name:digest(p.read_bytes()) for p in SHARDS.glob("translated_???.cpp")}
    need(len(true_tus)==64 and true_tus==pmeta["true_tu_sha256"],
         "64 TrueTU source drift")
    base=load(ROOT/"ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py","v6v_base")
    bb=load(ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bb_frontier22dda4.py","v6v_bb")
    bc=load(ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bc_broad_sweep.py","v6v_bc")
    planner=load(K1/"Plan-K1NextICallBatch.py","v6v_owner")
    by_va,by_name=base.load_ranges(BASE/"analysis/disasm/functions.json")
    generated=base.load_generated(BASE/"runtime/gen",by_name)
    need(TARGET in by_va and by_va[TARGET]["end"]==END and TARGET not in generated,
         "22FA9E retail owner/translation source changed; avoid double binding")
    source=parent.decode("utf-8").replace("\r\n","\n")
    owners,counts=planner.owner_inventory(source,SHARDS)
    compiled=counts["compiled_in_64_or_main"]
    need(TARGET not in compiled and TARGET not in counts["main_pack_lookup_vas"],
         "22FA9E already compiled or routed")
    need(all(va in compiled and va in counts["main_pack_lookup_vas"] for va in CALLEES),
         "Three original translated x87 callees not compiled/dispatched")
    name=by_va[TARGET]["name"]
    need(name=="sub_0022FA9E",
         "Unrecognized original name for exact function: "+name)
    generated[TARGET]={"name":name,"source":SOURCE,"file":"RETAIL-XBE-SHA256-V6s-56INSTRUCTIONS"}
    need(len(LOOKUP.findall(source))==1 and OPT in source,"Original pack lookup/optimization guard drift")
    new=source.replace(LOOKUP.search(source).group(),CANON,1).replace(OPT,PLACE)
    new+='\n#pragma optimize("", off)\n#pragma optimize("", on)\n'
    old_root,old_entry=bc.SWEEP_ROOT,bc.instrument_root_entry
    original_support=base.support_symbols
    original_standard=base.STANDARD_CALLS.copy()
    available={"sub_%08X"%v for v in compiled}
    available.update(original_support((SHARDS/"translated_runtime.h").read_text(encoding="utf-8",errors="replace")))
    try:
        bc.SWEEP_ROOT=TARGET
        bc.instrument_root_entry=lambda rendered,name:rendered
        base.support_symbols=lambda t:original_support(t)|available
        base.STANDARD_CALLS.update(("sin","cos"))
        packed,rendered,frontiers,pruned=bc.insert_pack_members(
            new,base,bb,generated,[TARGET],compiled|{TARGET},
            require_sweep_root=True)
    finally:
        bc.SWEEP_ROOT,bc.instrument_root_entry=old_root,old_entry
        base.support_symbols=original_support
        base.STANDARD_CALLS.clear();base.STANDARD_CALLS.update(original_standard)
    need(not pruned and TARGET in rendered and not frontiers,
         "22FA9E translation not dependency-closed: "+repr((pruned,frontiers)))
    need(packed.count(CANON)==1 and PLACE in packed,"Packed lookup/optimization drift")
    packed=packed.replace(CANON,LOOKUP.search(source).group(),1).replace(PLACE,OPT)
    lookup="case 0x0022FA9Eu: return sub_0022FA9E;"
    need(packed.count(lookup)==1,"Missing exact retail 22FA9E dispatch")
    for must in ("K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105",
                 "K1-V6b APC QUEUED","K1-V6b APC DELIVERED",
                 "K1D3D SECOND: native Xenos Reset PASS","P6DQ ROCKET HARD STOP",
                 "OLD TICK COUNT: 61948779","GUEST DISPLAY CALLS: %u",
                 "DISPLAY_CALLS > 0: YES"):
        need(source.count(must)>0 and packed.count(must)==source.count(must),
             "Original retail stream/graphics/log invariant drift: "+must)
    need(MARK not in packed,"V6v already staged")
    packed="/* "+MARK+" */\n"+packed
    result=packed.replace("\n","\r\n").encode() if b"\r\n" in parent else packed.encode()
    manifest={
      "stage":"V6V_ORIGINAL_RETAIL_22FA9E_X87_TRANSLATION_SOURCE_UNTESTED",
      "parent_v6rlog_sha256":digest(parent),"source_sha256":digest(result),
      "original_retail_xbe_sha256":RETAIL,
      "retail_function_bytes_sha256":evidence["source_bytes_sha256"],
      "root_entry":"0x0022FA9E","root_end_exclusive":"0x0022FB1F",
      "original_instruction_count":56,"original_ret_esp":8,
      "direct_compiled_callees":["0x%08X"%v for v in CALLEES],
      "root_generated_original_c_was_absent":True,
      "root_translation_sha256":digest(SOURCE.encode()),
      "native_summary_preserved":True,
      "true_tu_sha256":true_tus,
      "seven_async_reads_preserved_in_source":True,
      "unknown_frontiers_fenced":True,
      "hardware_tested":False,"first_pixels_verified":False}
    paths=[(OUT/"main.cpp",result),
           (OUT/"v6v-manifest.json",(json.dumps(manifest,indent=2)+"\n").encode())]
    for p,b in paths:
        need(not p.exists() or p.read_bytes()==b,
             "Existing V6v source differs; no overwrite: "+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,b in paths:
        if not p.exists():p.write_bytes(b)
    need((PARENT/"main.cpp").read_bytes()==parent,"Parent V6rLOG mutated during staging")
    print("[K1-V6v] SOURCE PASS: exact retail 22FA9E / 56 x86 instructions / 3 compiled callees")
    print("[K1-V6v] x87 status, four MOVSD, ret8; 64 TrueTUs and V6rLOG end summary preserved")
    print("[K1-V6v] SOURCE ONLY. XDK/HARDWARE NOT VERIFIED.")
if __name__=="__main__":
    try:run()
    except Exception as e:
        print("[K1-V6v] HARD FENCE: "+str(e),file=sys.stderr)
        sys.exit(1)
