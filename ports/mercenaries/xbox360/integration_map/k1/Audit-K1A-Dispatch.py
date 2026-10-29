#!/usr/bin/env python3
"""Read-only K1A guest ABI/dispatch audit for frozen Phase6 R76 source.

No game-file export, source mutation, XDK build or console side effects.
Report only focused code contexts needed to attach one clock bridge.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

MARKER = 'P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029'
NEEDLES = re.compile(
    r'(?:phase4c_system_time_100ns|phase5bc_dispatch_packed_icall|'
    r'PHASE4C_BOUNDARY_ICALL_SAFE|phase4c_escape|0x80000080|'
    r'savedEsp|g_esp|RECOMP_ICALL_SAFE|GUEST_READ32|GUEST_WRITE32|'
    r'RECOMP_ITAIL|phase4c_lookup_pack_func)')

def macro(lines: list[str], name: str) -> tuple[int, list[str]]:
    candidates = [i for i,l in enumerate(lines)
        if re.match(r'\s*#\s*define\s+' + re.escape(name) + r'\s*\(', l)]
    if len(candidates) != 1:
        raise ValueError(f'{name}: expected exactly one macro, got {len(candidates)}')
    i = candidates[0]
    # Preprocessor continuation ends on the first line lacking a backslash.
    j=i
    while j<len(lines)-1 and lines[j].rstrip().endswith('\\'):
        j+=1
    return i+1,lines[i:j+1]

def function(lines:list[str], name:str) -> tuple[int,list[str]]:
    matches=[i for i,l in enumerate(lines)
        if re.search(r'\b'+re.escape(name)+r'\s*\(',l)
        and re.search(r'\b(?:static\s+)?(?:inline\s+)?(?:void|uint64_t|ULONGLONG|unsigned\s+__int64)\s+',l)]
    if len(matches)!=1:
        raise ValueError(f'{name}: expected one function definition, got {len(matches)}')
    i=matches[0];opens=0;started=False
    for j in range(i,min(i+3000,len(lines))):
        v=lines[j];opens+=v.count('{');opens-=v.count('}')
        if '{' in v:started=True
        if started and opens==0:return i+1,lines[i:j+1]
    raise ValueError(f'{name}: unmatched function braces')

def focus(label:str, start:int, lines:list[str], max_lines:int=160)->list[str]:
    output=[f'## {label}: source line {start}, total {len(lines)} lines']
    if len(lines)<=max_lines:
        selected=range(len(lines))
    else:
        found={0,len(lines)-1}
        for n,line in enumerate(lines):
            if NEEDLES.search(line):
                found.update(range(max(n-2,0),min(n+3,len(lines))))
        selected=sorted(found)[:max_lines]
    prev=-1
    for i in selected:
        if i>prev+1:output.append(f'... skipped {i-prev-1} source lines ...')
        output.append(f'{start+i:06d}: {lines[i]}')
        prev=i
    if selected and selected[-1]<len(lines)-1:
        output.append(f'... remaining {len(lines)-1-selected[-1]} source lines omitted ...')
    return output

def audit(main:str,source:str)->str:
    if MARKER not in main:raise ValueError('expected R76 main.cpp watermark missing')
    if 'P6DQ R59 FC4A ABI RESTORE:' not in source:
        raise ValueError('expected R59 source identity missing')
    ml=main.splitlines();sl=source.splitlines()
    parts=[
        '# K1A EXACT GUEST CLOCK ABI DISPATCH AUDIT',
        'This is source evidence, not hardware confirmation or an XDK build.',
        'Hardware R76 reported target=80000080, 26,720,251 ticks.',
        'DO NOT treat guessed ABI or a matching route as hardware PASS.',
        '',
    ]
    for n in ('RECOMP_ICALL_SAFE','RECOMP_ITAIL'):
        i,l=macro(ml,n);parts.extend(focus(n,i,l,180));parts.append('')
    for n in ('phase4c_system_time_100ns','phase5bc_dispatch_packed_icall'):
        i,l=function(ml,n);parts.extend(focus(n,i,l,160));parts.append('')
    symbols=['GUEST_READ16','GUEST_WRITE16','GUEST_READ32','GUEST_WRITE32',
             'phase4c_system_time_100ns','0x80000080u','KeQuerySystemTime']
    parts.extend(['## Shared helper / type references'])
    for s in symbols:
        positions=[i+1 for i,x in enumerate(ml) if s in x]
        parts.append(f'{s}: count={len(positions)} first_lines={positions[:16]}')
    parts.append('')
    # R59 caller site is known from genuine R76 stop; the exact entry may be
    # somewhere inside a translated block and not at its start.
    parts.append('## R59 known caller and ordinal-128 references')
    for token in ('sub_002A5293','0x80000080','RECOMP_ICALL_SAFE'):
        positions=[i for i,x in enumerate(sl) if token in x]
        parts.append(f'{token}: count={len(positions)}')
        for k in positions[:6]:
            parts.extend(focus(f'R59 {token}',k+1,sl[k:min(k+8,len(sl))],8))
    return '\n'.join(parts)+'\n'

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument('--main',type=Path,required=True)
    p.add_argument('--source',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    for path in (a.main,a.source):
        if not path.is_file():p.error(f'missing file: {path}')
    report=audit(a.main.read_text(encoding='utf-8',errors='replace'),
                 a.source.read_text(encoding='utf-8',errors='replace'))
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(report,encoding='utf-8')
    print('[K1A] ABI AUDIT PASS: true R76 main + R59 translated caller inspected')
    print('[K1A] No guest source modified; no XDK build')
    print(f'[K1A] report={a.out}')
if __name__=='__main__':main()
