#!/usr/bin/env python3
"""Read-only K1A DSOBJECT write coverage audit of locally generated TrueTU sources.

Audit what the current APU-only watch can and cannot see. This does not
claim the write origin, adjust guest memory, or trigger any XDK compilation.
"""
from __future__ import annotations
import argparse
import json
import re
from pathlib import Path

CLOCK = 'P6K1A-BOOT-CLOCK128-304-305-20261029'
WATCH = 'P6K1A-DSOUND-OBJECT-WRITER-WATCH-20261030'
TERMS = {
    'APU_HELPER_WRITES': r'\bphase6ch_apu_write(?:8|16|32)\s*\(',
    'DIRECT_GUEST_WRITE': r'\bGUEST_WRITE(?:8|16|32)\s*\(',
    'HOST_GUEST_WRITE': r'\b(?:recomp_guest_write|guest_write)(?:8|16|32)\s*\(',
    'BULK_GUEST_MEMORY': r'\b(?:memcpy|memmove|memset|ZeroMemory|CopyMemory|RtlCopyMemory|RtlMoveMemory)\s*\(',
    'ADDRESS_41D70': r'(?i)\b(?:0x)?0*41D7[0-7]\b',
}

def extract(main:Path, shard_dir:Path)->dict:
    main=main.resolve(); shard_dir=shard_dir.resolve()
    shards=sorted(shard_dir.glob('translated_*.cpp'))
    if len(shards)!=64:
        raise ValueError('expected 64 exact translated_*.cpp TrueTU shards, found '+str(len(shards)))
    runtime=shard_dir/'translated_runtime.h'
    if not runtime.is_file():
        raise ValueError('expected generated translated_runtime.h')
    files=[main,runtime,*shards]
    text={p:p.read_text(encoding='utf-8',errors='replace') for p in files}
    if text[main].count(CLOCK)!=1:
        raise ValueError('exact K1A clock marker missing from staged main')
    owners=[p.name for p,t in text.items() if t.count(WATCH)==3]
    if len(owners)!=1:
        raise ValueError('exactly one instrumented writer owner required, got '+str(owners))
    summary={k:0 for k in TERMS};bytype={k:[] for k in TERMS}
    for file,content in text.items():
        for k,pattern in TERMS.items():
            matches=list(re.finditer(pattern,content))
            if not matches:continue
            summary[k]+=len(matches)
            if file==main:area='main.cpp'
            elif file==runtime:area='translated_runtime.h'
            else:area='translated_shards'
            row=next((r for r in bytype[k] if r['area']==area),None)
            if row is None:
                row={'area':area,'count':0,'sample':[]};bytype[k].append(row)
            row['count']+=len(matches)
            for m in matches[:2]:
                if len(row['sample'])<6:
                    line=content.count('\n',0,m.start())+1
                    row['sample'].append(f'{file.name}:{line}')
    return {
        'status':'READ_ONLY_LEXICAL_AUDIT',
        'watch_owner':owners[0],
        'clock_boot_marker':CLOCK,
        'original_apu_writer_hooks':3,
        'translated_cpp_count':len(shards),
        'matching_function_calls_are_not_runtime_traces':True,
        'counts':summary,'locations':bytype,
        'limitations':[
            'Only lexical call-site counts, not proof that a write executed or reached 00041D70.',
            'APU helper hooks do not automatically intercept GUEST_WRITE* calls elsewhere.',
            'Untracked host bulk-memory copying can bypass both kinds of helpers.',
            'A missing K1A DSOBJECT WRITE log requires verifying boot XEX and actual compiled writer hooks.',
            'Do not whitelist EFEE0EC4 or infer a physical-memory/MMIO mapping.',
        ]
    }

def main():
    p=argparse.ArgumentParser()
    p.add_argument('--main',type=Path,required=True)
    p.add_argument('--shards',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    args=p.parse_args()
    if args.out.resolve() in [args.main.resolve(),*(v.resolve() for v in args.shards.glob('*'))]:
        p.error('refuse source overwrite')
    obj=extract(args.main,args.shards)
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(json.dumps(obj,indent=2)+'\n',encoding='utf-8')
    print('[K1A-COVERAGE] PASS: 64 TrueTU sources + runtime header scanned, no source changed')
    print('[K1A-COVERAGE] writer owner: '+obj['watch_owner'])
    for label,n in obj['counts'].items():
        print(f'[K1A-COVERAGE] {label} lexical matches={n}')
        for row in obj['locations'][label]:
            print(f'  {row["area"]}: {row["count"]} (example: {", ".join(row["sample"][:3])})')
    print('[K1A-COVERAGE] This is NOT a runtime writer proof; output='+str(args.out))

if __name__=='__main__': main()
