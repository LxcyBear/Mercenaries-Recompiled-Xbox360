#!/usr/bin/env python3
"""Phase 6DQ frozen integration map: source/retail imports/fault-ledger, no patches."""
from __future__ import annotations
import argparse
import csv
import hashlib
import json
import re
import struct
from collections import Counter
from pathlib import Path

EXPECTED_XBE_SHA = 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7'
THUNK_VA, THUNK_COUNT = 0x002DBCE0, 111
KNOWN = {24:'ExQueryNonVolatileSetting',
         40:'HalDiskCachePartitionCount (DATA)',
         41:'HalDiskModelNumber (DATA)',
         42:'HalDiskSerialNumber (DATA)',
         44:'HalGetInterruptVector',
         47:'HalRegisterShutdownNotification', 98:'KeConnectInterrupt',
         99:'KeDelayExecutionThread',107:'KeInitializeDpc',109:'KeInitializeInterrupt',
         113:'KeInitializeTimerEx',128:'KeQuerySystemTime',
         139:'KeRestoreFloatingPointState',142:'KeSaveFloatingPointState',
         149:'KeSetTimer',151:'KeStallExecutionProcessor',
         156:'KeTickCount (DATA)',
         164:'LaunchDataPage (DATA)',
         173:'MmGetPhysicalAddress', 184:'NtAllocateVirtualMemory',
         196:'NtDeviceIoControlFile',202:'NtOpenFile',218:'NtQueryVolumeInformationFile',
         226:'NtSetInformationFile',255:'PsCreateSystemThreadEx',
         277:'RtlEnterCriticalSection',294:'RtlLeaveCriticalSection',
         322:'XboxHardwareInfo (DATA)',
         324:'XboxKrnlVersion (DATA)',
         326:'XeImageFileName (DATA)',
         356:'HalBootSMCVideoMode (DATA)',
         357:'IdexChannelObject (DATA)'}


def sha(data):
    return hashlib.sha256(data).hexdigest().upper()


def import_table(xbe):
    """Use only exact-SHA user-owned retail XBE, export ordinals not game bytes."""
    b = xbe.read_bytes()
    if sha(b) != EXPECTED_XBE_SHA:
        raise ValueError('Retail XBE identity mismatch; refusing unverified input')
    def u32(o):
        if o < 0 or o+4 > len(b): raise ValueError('XBE read out of range')
        return struct.unpack_from('<I', b, o)[0]
    if b[:4] != b'XBEH': raise ValueError('Bad XBE signature')
    base, hdr_len, n, sec_va = (u32(o) for o in (0x104,0x108,0x11C,0x120))
    if not 0 < n <= 64 or not 0 < hdr_len <= len(b):
        raise ValueError('Bad XBE section/header dimensions')
    sections=[]
    for i in range(n):
        off=sec_va-base+i*0x38
        va,virt,raw,size=(u32(off+j) for j in (4,8,12,16))
        if raw+size > len(b):raise ValueError('XBE section exceeds physical file')
        sections.append((va,virt,raw,size))
    def get(va):
        if base<=va and va+4<=base+hdr_len: return u32(va-base)
        for sv,virt,raw,size in sections:
            if sv<=va and va+4<=sv+min(virt,size):return u32(raw+va-sv)
        raise ValueError(f'XBE thunk VA not mapped: {va:08X}')
    d=[get(THUNK_VA+4*i) for i in range(THUNK_COUNT+1)]
    if d[-1]!=0: raise ValueError('XBE thunk terminator must be zero')
    out=[]
    for i,v in enumerate(d[:-1]):
        if v == 0: ordinal=None
        elif v&0x80000000 and (v&0x7fffffff)<1024:ordinal=v&0x7fffffff
        else: raise ValueError(f'Unexpected import entry #{i}: {v:08X}')
        out.append({'slot':i,'address':f'{THUNK_VA+4*i:08X}','ordinal':ordinal})
    return out


def read_dispatch_routes(main):
    """Route existence != implemented service or hardware pass."""
    m=re.search(r'(?s)#define RECOMP_ICALL_SAFE\b(.*?)#define RECOMP_ITAIL\b',main)
    if not m:raise ValueError('No current RECOMP_ICALL_SAFE macro found')
    routes={}
    pattern=r'(?:_phase4c_target|target)\s*==\s*0x8000([0-9a-fA-F]{4})u'
    for raw in re.findall(pattern,m.group(1)):
        routes.setdefault(int(raw,16),set()).add('RECOMP_ICALL_SAFE')
    definition=re.search(
        r'(?s)\bvoid\s+phase5bc_dispatch_packed_icall\s*\([^)]*\)\s*\{',main)
    if not definition:raise ValueError('Packed-ICALL dispatcher definition missing')
    start=definition.start()
    brace=main.find('{',definition.start(),definition.end())
    depth=0
    for j in range(brace,len(main)):
        if main[j]=='{':depth+=1
        elif main[j]=='}':
            depth-=1
            if depth==0:break
    if depth:raise ValueError('Dispatcher braces unbalanced')
    for raw in re.findall(pattern,main[start:j+1]):
        routes.setdefault(int(raw,16),set()).add('PACKED_ICALL')
    return routes


def scan_guest(source):
    pattern=r'(?m)^\s*(?:static\s+)?void\s+sub_([0-9a-fA-F]{8})\(void\)\s*\{'
    starts=list(re.finditer(pattern,source))
    funcs=len(starts)
    direct=len(re.findall(r'\bsub_[0-9a-fA-F]{8}\(\);',source))
    indirect=len(re.findall(r'\b(?:PHASE6DJ_ICALL_SAFE|RECOMP_ICALL_SAFE)\s*\(',source))
    ords=Counter(int(x,16) for x in re.findall(r'\b0x8000([0-9a-fA-F]{4})u?\b',source))
    mmio=Counter()
    for value in re.findall(r'\b0x(F[CE][0-9a-fA-F]{6})u?\b',source):
        mmio[value.upper()]+=1
    # The x86 translator also prints 0xFE80200C as signed -25157620.
    # Only candidate literals: an immediate may also be an offset, not MMIO.
    for signed in re.findall(r'(?<![\w])-\d{7,10}\b',source):
        raw=int(signed)&0xFFFFFFFF
        if (raw>>24) in (0xFC,0xFE):mmio[f'{raw:08X}']+=1
    # Static guest-to-guest calls for the *systemic* caller/callee ABI audit.
    edges=Counter()
    for i,m in enumerate(starts):
        end=starts[i+1].start() if i+1<len(starts) else len(source)
        caller=m.group(1).upper()
        for callee in re.findall(r'\bsub_([0-9a-fA-F]{8})\(\);',source[m.end():end]):
            edges[(caller,callee.upper())]+=1
    return funcs,direct,indirect,ords,mmio,edges

def fault_ledger(paths,old):
    if old.is_file():
        state=json.loads(old.read_text(encoding='utf-8'))
        if state.get('schema')!=1: raise ValueError('Unexpected ledger schema')
    else: state={'schema':1,'seen_log_sha':[],'faults':{}}
    for p in paths:
        data=p.read_bytes(); h=sha(data)
        if h in state['seen_log_sha']:continue
        text=data.decode('utf-8',errors='replace')
        if text.lstrip().startswith('[Phase6R77]'):
            raise ValueError('R77 is a source audit, not an Xbox runtime log')
        patterns=(
            (r'JOURNAL HARD\[\d+\].*?kind=(\d+).*?caller=([0-9A-Fa-f]{8}).*?target=([0-9A-Fa-f]{8}).*?hits=(\d+)', 'hard_stop'),
            (r'BOUNDARY:\s*kind=([A-Z_]+).*?caller=([0-9A-Fa-f]{8}).*?target=([0-9A-Fa-f]{8})', 'boundary'),
            (r'(?:READ|WRITE)(?:8|16|32|64)\s+guest=([0-9A-Fa-f]{8})','memory_fault'))
        for rx,typ in patterns:
            for m in re.finditer(rx,text):
                g=m.groups()
                if typ=='hard_stop': sub,caller,target,hits=g;hits=int(hits)
                elif typ=='boundary':sub,caller,target=g;hits=1
                else:sub='unknown';caller='unknown';target=g[0];hits=1
                caller=caller.upper();target=target.upper()
                key=f'{typ}:{sub}:{caller}:{target}'
                row=state['faults'].setdefault(key,{
                    'kind':typ,'subtype':sub,'caller':caller,'target':target,
                    'hits':0,'triage':'unreviewed','evidence_log_sha':[]})
                row['hits']+=hits
                if h not in row['evidence_log_sha']:row['evidence_log_sha'].append(h)
        state['seen_log_sha'].append(h)
    return state


def csv_out(path,rows,fields):
    with path.open('w',encoding='utf-8',newline='') as f:
        writer=csv.DictWriter(f,fieldnames=fields,extrasaction='ignore')
        writer.writeheader();writer.writerows(rows)


def main():
    p=argparse.ArgumentParser()
    for flag in ('main','source','out'):p.add_argument('--'+flag,type=Path,required=True)
    p.add_argument('--retail-xbe',type=Path)
    p.add_argument('--hardware-log',type=Path,action='append',default=[])
    a=p.parse_args()
    for path in (a.main,a.source,*a.hardware_log):
        if not path.is_file():raise ValueError(f'Input missing: {path}')
    maintext=a.main.read_text(encoding='utf-8',errors='replace')
    source=a.source.read_text(encoding='utf-8',errors='replace')
    if 'P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029' not in maintext:
        raise ValueError('R76 frozen source watermark missing')
    if 'P6DQ R59 FC4A ABI RESTORE:' not in source:
        raise ValueError('R59 guest source identity changed')
    funcs,direct,indirect,literals,mmio,edges=scan_guest(source)
    if funcs<13000:raise ValueError(f'Incomplete guest corpus: only {funcs} functions')
    routes=read_dispatch_routes(maintext)
    imports=import_table(a.retail_xbe) if a.retail_xbe else []
    candidates=({e['ordinal'] for e in imports if e['ordinal'] is not None}
                if imports else set(routes)|set(literals))
    kernel=[{'ordinal':n,'name':KNOWN.get(n,'UNKNOWN'),
             'retail_import_verified':bool(imports),'route_present':bool(routes.get(n)),
             'route_sources':';'.join(sorted(routes.get(n,()))),
             'static_literal_mentions':literals.get(n,0),
             'semantics_tested':'NOT_ASSESSED',
             'confidence':'exact_xbe_import' if imports else 'static_candidate_only'}
            for n in sorted(candidates)]
    mmio_rows=[{'address':addr,'literal_mentions':count,
                'subsystem':'APU_CORE' if addr.startswith('FE80') else
                'APU_VP' if addr.startswith('FE82') else
                'OTHER_MMIO','status':'STATIC_CANDIDATE_ONLY'}
               for addr,count in sorted(mmio.items())]
    a.out.mkdir(parents=True,exist_ok=True)
    ledger_path=a.out/'fault-ledger.json'
    ledger=fault_ledger(a.hardware_log,ledger_path)
    ledger_path.write_text(json.dumps(ledger,indent=2)+'\n',encoding='utf-8')
    csv_out(a.out/'kernel-coverage.csv',kernel,[
        'ordinal','name','retail_import_verified','route_present','route_sources',
        'static_literal_mentions','semantics_tested','confidence'])
    csv_out(a.out/'mmio-literals.csv',mmio_rows,[
        'address','literal_mentions','subsystem','status'])
    csv_out(a.out/'guest-call-edges.csv',
            [{'caller_va':a,'callee_va':b,'static_callsites':count,
              'abi_status':'UNTESTED_CANDIDATE'}
             for (a,b),count in sorted(edges.items())],
            ['caller_va','callee_va','static_callsites','abi_status'])
    payload={
        'schema':1,'status':'phase6DQ_diagnostic_baseline_frozen_NOT_gate6',
        'last_hardware_boundary':{'kind':'ICALL_SAFE','target':'80000080','ticks':26720251},
        'observations':{'dsound_pool':'R72 hardware PASS','apu_xgscnt':'R76 hardware PASS',
                        'xact_init':'hardware success','display_calls':0,'framebuffer':'00000000'},
        'counts':{'guest_functions':funcs,'direct_calls':direct,'indirect_markers':indirect,
                  'static_kernel_candidates':len(kernel),'explicit_kernel_routes':len(routes),
                  'literal_mmio_addresses':len(mmio_rows),'guest_call_edges':len(edges),'distinct_logged_faults':len(ledger['faults'])},
        'import_inventory':{'expected':THUNK_COUNT,'verified':bool(imports),'rows':imports},
        'notice':'Route present != behavior verified; literal != runtime hit. No user XBE/log bytes included.',
        'waves':['kernel imports and timing/synchronization',
                 'systemic guest x86 ABI','APU/AC97/MMIO semantics',
                 'guest D3D to Xenos first real frame','storage/assets/input']}
    (a.out/'phase6-integration-map.json').write_text(json.dumps(payload,indent=2)+'\n',encoding='utf-8')
    md=['# Mercenaries — Phase 6 Integration Map','',
        '**6DQ frozen as diagnostic baseline, NOT graphics completion.**','',
        f'- Guest functions: {funcs:,}; direct calls: {direct:,}; indirect markers: {indirect:,}',
        f'- Kernel route ordinals: {len(routes)}; static candidates: {len(kernel)}',
        f'- Unique guest direct call edges: {len(edges):,} (ABI untested)',
        f'- 111-slot verified owned retail XBE: {"YES" if imports else "NOT PROVIDED"}',
        f'- Possible MMIO literal addresses: {len(mmio_rows)} (computed accesses excluded)',
        f'- Distinct captured fault signatures: {len(ledger["faults"])}','',
        '## Hardware baseline',
        '- R72 DSOUND pool and XACT initialization: success.',
        '- R76 FE80200C / NV_PAPU_XGSCNT read: successful route.',
        '- Current unresolved boundary: ICALL_SAFE 80000080 (kernel ordinal 128), tick 26,720,251.',
        '- No guest display calls or valid guest framebuffer proven.','',
        '## The next batch (not one fault at a time)',
        '1. Verify exact retail import identities (optional local original XBE);',
        '   classify data/function imports and kernel ABI contracts.',
        '2. Fix root causes in translator ABI: callee-saved registers, stack frames,',
        '   and pointer preservation; test nested-call fixtures.',
        '3. Group APU/AC97/NV2A MMIO by block and documented semantics; fence unknowns.',
        '4. Validate actual guest D3D display, surface and presentation milestones.',
        '5. One complete batch, offline tests, one incremental XDK build, one Xbox run.','',
        '**Evidence rules:** route != implementation != hardware PASS.',
        'This scanner never writes guest code, edits fences, or exports retail bytes.']
    (a.out/'PHASE6_MAP.md').write_text('\n'.join(md)+'\n',encoding='utf-8')
    print('[IntegrationMap] PASS: offline kernel/ABI/MMIO map and fault ledger')
    print(f'[IntegrationMap] output={a.out}')
    print(f'[IntegrationMap] kernel_static_candidates={len(kernel)} explicit_routes={len(routes)}')
    print(f'[IntegrationMap] exact_retail_imports={"YES" if imports else "NOT PROVIDED"}')
    print(f'[IntegrationMap] fault_signatures={len(ledger["faults"])}')

if __name__=='__main__':main()
