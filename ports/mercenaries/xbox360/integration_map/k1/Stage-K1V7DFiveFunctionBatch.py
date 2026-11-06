#!/usr/bin/env python3
"""Offline faithful opcode to recomp-style C source translation for five retail XBE functions.

Uses verified V7B opcode JSON, maintained recompiler SIMD helper patterns,
and original TrueTU infrastructure. Fail-closed on unknown opcode/ABI.
"""
from __future__ import annotations
import hashlib, importlib.util, json, re, sys
from pathlib import Path
ROOT=Path.cwd()
K1=ROOT/'ports/mercenaries/xbox360/integration_map/k1'
EVID=ROOT/'build/phase6_integration_map/k1_batch_recomp_recovery_v7/v7b_five_function_recomp_inputs.json'
BASE=ROOT/'build/phase3n_final_abi_scale'
PARENT=ROOT/'build/phase6_integration_map/k1_pixel_retail_22f9bc_v6z'
SHARDS=ROOT/'build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards'
OUT=ROOT/'build/phase6_integration_map/k1_pixel_retail_five_batch_v7d'
SHA='AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7'
TARGETS=(0x0022F49E,0x0022F51C,0x0022F5A7,0x0022F6A5,0x0022F7C6)
LOOKUP=re.compile(r'(?m)^(?:static[ \t]+)?recomp_func_t phase4c_lookup_pack_func\(uint32_t xbox_va\)\n\{')
CANON='static recomp_func_t phase4c_lookup_pack_func(uint32_t xbox_va)\n{'
OPT='#pragma optimize("", on)'
PLACE='/* K1_V7D_PACK_OPT_ON_HIDDEN */'
MARK='K1-V7D-RETAIL-FIVE-FUNCTION-BATCH-OPCODE-LIFT'
def need(v,msg):
    if not v:raise ValueError(msg)
def sha(b):return hashlib.sha256(b).hexdigest()
def module(path,name):
    spec=importlib.util.spec_from_file_location(name,path)
    need(spec is not None and spec.loader is not None,'Missing module: '+str(path))
    obj=importlib.util.module_from_spec(spec);spec.loader.exec_module(obj)
    return obj

def mem(x):
    m=re.fullmatch(r'(?:dword|qword|xmmword) ptr \[(.*?)\]',x.strip())
    need(m,'Unsupported guest memory syntax '+repr(x))
    v=m.group(1)
    mat=re.fullmatch(r'(eax|ebp|ecx|edx|esp)(?: ([+-]) (0x[0-9a-f]+|[0-9]+))?',v)
    need(mat,'Unsupported guest address '+v)
    r,op,off=mat.groups()
    return r if op is None else r+' '+op+' '+off+'u'
def xmm(x):
    need(bool(re.fullmatch(r'xmm[0-7]',x)),'Unknown x86 SSE register '+x)
    return x+'v'
def imm(x):
    need(bool(re.fullmatch(r'(?:0x[0-9a-f]+|[0-9]+)',x)),'Unsupported immediate '+x)
    return x+'u'
def op_lower(ins, state):
    mn=ins['mnemonic'].lower()
    arg=ins['operands'].lower().strip()
    parts=arg.split(', ') if arg else []
    va=int(ins['va'],16)
    def result(*statements):return ['    '+st+' /* %08X %s %s */'%(va,mn,arg) for st in statements]
    if mn=='push':
        need(len(parts)==1 and parts[0] in ('ebp','ecx'),'Unsupported push '+arg)
        state['esp']-=4
        return result('PUSH32(esp, '+parts[0]+');')
    if mn=='sub' and arg=='esp, 0x10':
        state['esp']-=16
        return result('esp -= 0x10u;')
    if mn=='mov':
        need(len(parts)==2,'Bad mov '+arg)
        a,b=parts
        if a=='ebp' and b=='esp':return result('ebp = esp;')
        if a in ('eax','ecx','edx') and b.startswith('dword ptr ['):
            return result(a+' = GUEST_READ32('+mem(b)+');')
        if a.startswith('dword ptr [') and b in ('eax','ecx','edx'):
            return result('GUEST_WRITE32('+mem(a)+', '+b+');')
        need(False,'Unsupported MOV operands '+arg)
    if mn=='lea':
        need(len(parts)==2 and parts[0] in ('eax','ecx','edx'),'Unsupported lea '+arg)
        return result(parts[0]+' = '+mem('dword ptr '+parts[1])+';')
    if mn=='movaps':
        need(len(parts)==2,'Bad MOVAPS '+arg)
        a,b=parts
        if a.startswith('xmm') and b.startswith('xmmword ptr ['):
            return result('recomp_xmm_load('+xmm(a)+', '+mem(b)+');')
        if a.startswith('xmmword ptr [') and b.startswith('xmm'):
            return result('recomp_xmm_store('+mem(a)+', '+xmm(b)+');')
        if a.startswith('xmm') and b.startswith('xmm'):
            return result('recomp_xmm_copy('+xmm(a)+', '+xmm(b)+');')
        need(False,'Unsupported MOVAPS operands '+arg)
    if mn=='movss':
        need(len(parts)==2,'Bad MOVSS '+arg)
        a,b=parts
        if a.startswith('xmm') and b.startswith('dword ptr ['):
            return result('recomp_xmm_loadss('+xmm(a)+', '+mem(b)+');')
        if a.startswith('dword ptr [') and b.startswith('xmm'):
            return result('GUEST_WRITEF32('+mem(a)+', '+b+');')
        need(False,'Unsupported MOVSS operands '+arg)
    if mn=='shufps':
        need(len(parts)==3,'Bad SHUFPS '+arg)
        return result('recomp_xmm_shufps('+xmm(parts[0])+', '+xmm(parts[1])+', (uint8_t)'+imm(parts[2])+');')
    if mn in ('mulps','addps'):
        need(len(parts)==2,'Bad SSE arithmetic '+arg)
        a,b=parts
        sym='*' if mn=='mulps' else '+'
        if b.startswith('xmmword ptr ['):
            return result('recomp_xmm_load(_v7d_memv, '+mem(b)+');',
                          'RECOMP_XMM_BINARY_RR('+xmm(a)+', _v7d_memv, '+sym+');')
        if b.startswith('xmm'):
            return result('RECOMP_XMM_BINARY_RR('+xmm(a)+', '+xmm(b)+', '+sym+');')
        need(False,'Unsupported arithmetic source '+arg)
    if mn in ('movlps','movhps'):
        need(len(parts)==2 and parts[0].startswith('qword ptr [') and parts[1].startswith('xmm'),
             'Unexpected SSE partial load; only verified stores in batch '+arg)
        address=mem(parts[0]); src=xmm(parts[1])
        if mn=='movlps':return result('recomp_xmm_movlps_store('+address+', '+src+');')
        # movhps STORE = high two lanes only. Use a local XMM scratch array:
        # shufps(a,a,0xEE) yields [a2,a3,a2,a3]. Source register unchanged.
        return result('recomp_xmm_copy(_v7d_memv, '+src+');',
                      'recomp_xmm_shufps(_v7d_memv, _v7d_memv, (uint8_t)0xEE);',
                      'recomp_xmm_movlps_store('+address+', _v7d_memv);')
    if mn=='movhlps':
        need(len(parts)==2,'Bad MOVHLPS '+arg)
        return result('recomp_xmm_movhlps('+xmm(parts[0])+', '+xmm(parts[1])+');')
    if mn in ('unpcklps','unpckhps'):
        need(len(parts)==2,'Bad unpack '+arg)
        return result('recomp_xmm_'+mn+'('+xmm(parts[0])+', '+xmm(parts[1])+');')
    if mn in ('fld','fld1','fldz'):
        state['fp']+=1
        if mn=='fld1':need(not arg,'Unexpected FLD1');return result('fp_push(1.0);')
        if mn=='fldz':need(not arg,'Unexpected FLDZ');return result('fp_push(0.0);')
        if re.fullmatch(r'st\([0-7]\)',arg):
            depth=int(arg[3]);need(state['fp']-1>depth,'Invalid FLD st stack depth at %08X'%va)
            return result('{ double _v7d_fp_tmp = fp_st(%du); fp_push(_v7d_fp_tmp); }'%depth)
        return result('fp_push(GUEST_READF32('+mem(arg)+'));')
    if mn=='fsincos':
        need(state['fp']>=1 and not arg,'Invalid FSINCOS')
        state['fp']+=1
        return result('{ double _v7d_a = fp_top(); fp_top() = sin(_v7d_a); fp_push(cos(_v7d_a)); }')
    if mn=='fchs':
        need(state['fp']>=1,'FCHS with empty FPU')
        return result('fp_top() = -fp_top();')
    if mn in ('fst','fstp'):
        need(state['fp']>=1,'FST(P) without FPU value')
        if arg=='st(0)' and mn=='fstp':
            state['fp']-=1
            return result('fp_pop();')
        need(arg.startswith('dword ptr ['),'Unknown x87 store '+arg)
        if mn=='fstp':state['fp']-=1
        return result('GUEST_WRITEF32('+mem(arg)+', (float)fp_top());'+(' fp_pop();' if mn=='fstp' else ''))
    if mn=='call':
        need(len(parts)==1 and re.fullmatch(r'0x[0-9a-f]+',arg),'Indirect CALL not proven')
        target=int(arg,16)
        need(target in (0x0022F3F3,0x0022F31D),'Unexpected original direct callee '+arg)
        # x86 call pushes 4-byte return slot, callee RET imm performs cleanup
        return result('PUSH32(esp, 0); sub_%08X();'%target)
    if mn=='test':
        need(arg=='eax, eax','Unproven x86 TEST semantics')
        state['test_eax']=True
        return result('/* test eax,eax: next conditional directly evaluates eax */')
    if mn=='jne':
        need(state.get('test_eax',False),'Unpaired JNE flags')
        dest=int(arg,16)
        need(dest==0x0022F515,'Unexpected JNE label')
        state['test_eax']=False
        return result('if (eax != 0u) goto loc_0022F515;')
    if mn=='leave':
        need(state['fp']==0,'x87 not balanced on LEAVE')
        return result('esp = ebp;', 'POP32(esp, ebp);')
    if mn=='ret':
        val=int(arg,0)
        need(val in (8,12) and state['fp']==0,'x87/ABI return hazard')
        return result('esp += %du; return; /* RET %d */'%(val+4,val))
    need(False,'Unknown retail instruction %08X %s %s'%(va,mn,arg))

def translate(f):
    addr=int(f['entry'],16)
    state={'fp':0,'esp':0}
    lines=['void sub_%08X(void)'%addr,'{',
        '    uint32_t ebp = 0u;',
        '    float _v7d_memv[4]; /* original recomp XMM helper representation */',
        '    #define fp_push(v) (g_fp_stack[--g_fp_top & 7u] = (v))',
        '    #define fp_pop() (g_fp_top++)',
        '    #define fp_top() g_fp_stack[g_fp_top & 7u]',
        '    #define fp_st(i) g_fp_stack[(g_fp_top + (uint32_t)(i)) & 7u]',
        '    RECOMP_TRACE_FUNC(0x%08Xu);'%addr]
    cursor=addr
    for ins in f['instructions']:
        need(int(ins['va'],16)==cursor,'Missing/overlap bytes at %08X'%cursor)
        cursor+=ins['size']
        if cursor>int(f['end'],16):raise ValueError('Crossed retail boundary')
        if int(ins['va'],16)==0x0022F515:lines.append('loc_0022F515: ;')
        lines.extend(op_lower(ins,state))
        need(0<=state['fp']<=8,'x87 depth overflow at %s'%ins['va'])
    need(cursor==int(f['end'],16),'Missing terminal retail bytes')
    need(state['fp']==0,'FPU leaked across original ret')
    lines+=['    #undef fp_push','    #undef fp_pop','    #undef fp_top','    #undef fp_st','}']
    return '\n'.join(lines)+'\n'

def run():
    j=json.loads(EVID.read_text(encoding='utf-8-sig'))
    need(j['stage']=='V7B_FIVE_FUNCTION_EXACT_XBE_AND_RECOMP_TEMPLATE_EVIDENCE' and
         j['retail_sha256']==SHA and not j['safe_to_build_xex'],'V7B evidence drift')
    items={int(f['entry'],16):f for f in j['source_gaps']}
    need(set(items)==set(TARGETS),'Unexpected batch function inventory')
    xbes=[p for p in (Path.home()/'OneDrive/Desktop/My Xbox/default.xbe',
                      Path.home()/'Desktop/My Xbox/default.xbe')
          if p.is_file() and sha(p.read_bytes()).upper()==SHA]
    need(xbes,'Missing pinned retail XBE')
    audit=module(K1/'Audit-K1D3DSwitchCases.py','v7d_xbe')
    blob,sects=audit.get_retail_sections(xbes[0])
    for va,f in items.items():
        b=audit.bytes_at(blob,sects,va,int(f['end'],16)-va)
        need(sha(b)==f['retail_bytes_sha256'],'retail source bytes changed at %08X'%va)
    pm=json.loads((PARENT/'v6z-manifest.json').read_text(encoding='utf-8-sig'))
    base_bytes=(PARENT/'main.cpp').read_bytes()
    need(pm['source_sha256']==sha(base_bytes) and pm['native_summary_preserved']
         and pm['seven_async_reads_preserved_in_source'],'V6z parent drift')
    hashes={p.name:sha(p.read_bytes()) for p in SHARDS.glob('translated_???.cpp')}
    need(len(hashes)==64 and hashes==pm['true_tu_sha256'],'TrueTU source drift')
    base=module(ROOT/'ports/mercenaries/xbox360/phase4c_native_startup/emit_phase4c_startup_slice.py','v7d_base')
    bb=module(ROOT/'ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bb_frontier22dda4.py','v7d_bb')
    bc=module(ROOT/'ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bc_broad_sweep.py','v7d_bc')
    planner=module(K1/'Plan-K1NextICallBatch.py','v7d_owner')
    by_va,by_name=base.load_ranges(BASE/'analysis/disasm/functions.json')
    generated=base.load_generated(BASE/'runtime/gen',by_name)
    source=base_bytes.decode('utf-8').replace('\r\n','\n')
    owners,stats=planner.owner_inventory(source,SHARDS)
    compiled=stats['compiled_in_64_or_main']
    need(all(v in by_va and v not in generated and v not in compiled for v in TARGETS),
         'Function owner/source has changed; do not double-bind')
    need(all(v in compiled and v in stats['main_pack_lookup_vas'] for v in (0x0022F3F3,0x0022F31D)),
         'Direct callee 22F3F3 or 22F31D not compiled and routed')
    defs={}
    for va in TARGETS:
        defs[va]=translate(items[va])
        generated[va]={'name':'sub_%08X'%va,'source':defs[va],
                       'file':'V7D-SHA256-RETAIL-X86-OPCODE-LIFT'}
    need(len(LOOKUP.findall(source))==1 and OPT in source,'Source pack lookup drift')
    prepared=source.replace(LOOKUP.search(source).group(),CANON,1).replace(OPT,PLACE)
    prepared+='\n#pragma optimize("", off)\n#pragma optimize("", on)\n'
    old_root,old_fn=bc.SWEEP_ROOT,bc.instrument_root_entry
    support=base.support_symbols
    standard=base.STANDARD_CALLS.copy()
    available={'sub_%08X'%v for v in compiled}
    available.update(support((SHARDS/'translated_runtime.h').read_text(encoding='utf-8',errors='replace')))
    try:
        bc.SWEEP_ROOT=0x0022F5A7
        bc.instrument_root_entry=lambda rendered,name:rendered
        base.support_symbols=lambda s:support(s)|available
        base.STANDARD_CALLS.update(('sin','cos'))
        packed,rendered,frontiers,pruned=bc.insert_pack_members(
            prepared,base,bb,generated,list(TARGETS),compiled|set(TARGETS),require_sweep_root=True)
    finally:
        bc.SWEEP_ROOT,bc.instrument_root_entry=old_root,old_fn
        base.support_symbols=support
        base.STANDARD_CALLS.clear();base.STANDARD_CALLS.update(standard)
    need(not pruned and len(rendered)==5 and not frontiers,
         'Batch source is not full dependency-closed: %s %s'%(pruned,frontiers))
    packed=packed.replace(CANON,LOOKUP.search(source).group(),1).replace(PLACE,OPT)
    for va in TARGETS:
        need(packed.count('case 0x%08Xu: return sub_%08X;'%(va,va))==1,
             'Compiled guest function lacks lookup %08X'%va)
    for marker in ('K1-V6Z-RETAIL22F9BC-X87-OPCODE-LIFT',
                   'K1-V6W-RETAIL22FA9E-X87-EBP-20261105',
                   'K1-V6b APC QUEUED','K1-V6b APC DELIVERED',
                   'P6DQ ROCKET HARD STOP','DISPLAY_CALLS > 0: YES'):
        need(source.count(marker)>0 and packed.count(marker)==source.count(marker),
             'Existing native/guest invariant drift: '+marker)
    packed='/* '+MARK+' */\n'+packed
    data=packed.replace('\n','\r\n').encode() if b'\r\n' in base_bytes else packed.encode()
    manifest={'stage':'V7D_FIVE_RETAIL_FUNCTIONS_SOURCE_ONLY_UNTESTED',
              'source_sha256':sha(data),'parent_v6z_sha256':sha(base_bytes),
              'retail_xbe_sha256':SHA,'functions':['0x%08X'%v for v in TARGETS],
              'original_opcode_counts':{('0x%08X'%v):len(items[v]['instructions']) for v in TARGETS},
              'true_tu_sha256':hashes,'native_summary_preserved':True,
              'seven_async_reads_preserved_in_source':True,
              'unknown_frontiers_fenced':True,'hardware_verified':False,'xdk_compiled':False}
    outputs=[(OUT/'main.cpp',data),(OUT/'v7d-manifest.json',(json.dumps(manifest,indent=2)+'\n').encode())]
    for p,v in outputs:need(not p.exists() or p.read_bytes()==v,
                            'Existing batch differs, no overwrite: '+str(p))
    OUT.mkdir(parents=True,exist_ok=True)
    for p,v in outputs:
        if not p.exists():p.write_bytes(v)
    print('[K1-V7D] FIVE-FUNCTION SOURCE LIFT PASS: 197 original retail x86 instructions')
    print('[K1-V7D] TrueTU=64, V6w+V6z preserved, existing callees routed')
    print('[K1-V7D] BATCH SOURCE ONLY; XDK and hardware not tested')
    print('[K1-V7D] OUTPUT: '+str(OUT/'main.cpp'))
if __name__=='__main__':
    try:run()
    except Exception as exc:
        print('[K1-V7D] HARD FENCE: '+str(exc),file=sys.stderr)
        sys.exit(1)