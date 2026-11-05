#!/usr/bin/env python3
"""V6f: safely stage original 0x001F8F10, collect targeted execution-cost evidence.
Preserve V6e, 64 TrueTUs, hardware fences and guest instruction semantics.
Does not fast-forward ticks or elide guest-visible effects.
"""
from pathlib import Path
import hashlib, json, re, sys
TAG='[K1-V6f]'
ROOT=Path.cwd()
PARENT=ROOT/'build/phase6_integration_map/k1_pixel_redcamera_direct_v6e'
DEST=ROOT/'build/phase6_integration_map/k1_pixel_camera_followup_v6f'
SRC=ROOT/'build/phase3n_final_abi_scale/runtime/gen/recomp_0010.c'
SHARDS=ROOT/'build/phase6_integration_map/k1_pixel_ntread_apc_stream_v6b/translated_shards'
RET='AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7'
MARKER='K1-V6F-ORIGINAL-001F8F10-20261105'
def sha(b):return hashlib.sha256(b).hexdigest()
def require(condition, message):
    if not condition:raise RuntimeError(message)
def main():
    m=json.loads((PARENT/'v6e-redcamera-manifest.json').read_text(encoding='utf-8-sig'))
    parent=(PARENT/'main.cpp').read_bytes()
    require(m.get('retail_sha256')==RET,'Retail identity mismatch')
    require(m.get('staged_sha256')==sha(parent),'V6e main hash mismatch')
    tus=sorted(SHARDS.glob('translated_???.cpp'))
    require(len(tus)==64,'64 TrueTUs required')
    h={p.name:sha(p.read_bytes()) for p in tus}
    require(h==m['true_tu_sha256'],'V6e TrueTU hash mismatch')
    raw=SRC.read_bytes()
    require(sha(raw)==m['original_recomp_0010_sha256'],'Original generated source hash mismatch')
    source=raw.decode('utf-8-sig').replace('\r\n','\n')
    match=re.search(r'(?m)^void sub_001F8F10\(void\)\s*\{.*?^\}',source,re.S|re.M)
    require(match is not None,'Function sub_001F8F10 not present in original recomp_0010.c')
    fn=match.group(0)
    translated_calls=sorted(set(re.findall(r'\b(sub_[0-9A-Fa-f]{8})\s*\(',fn)))
    translated_calls=[x for x in translated_calls if x!='sub_001F8F10']
    require(not translated_calls,'Function has translated dependencies requiring closure: '+', '.join(translated_calls))
    helper_calls=sorted(set(re.findall(r'\b(recomp_[A-Za-z_0-9]+)\s*\(',fn)))
    unsupported=[x for x in helper_calls if x.startswith('recomp_options_') or x.startswith('recomp_crt_')]
    require(not unsupported,'Function has nonportable runtime helper(s): '+', '.join(unsupported))
    require('return;' in fn,'No recognized original return in function')
    fn=fn.replace('{','{\n    /* '+MARKER+' */',1)
    decoded=parent.decode('utf-8-sig'); eol='\r\n' if '\r\n' in decoded else '\n'
    base=decoded.replace('\r\n','\n')
    require('void sub_001F8F10(void)' not in base,'Already staged')
    require('case 0x001F8F10u:' not in base,'Dispatch already staged')
    require(base.count('    case 0x001F89F0u: return sub_001F89F0;')==1,'V6e dispatch anchor mismatch')
    pos=base.index('    case 0x001F89F0u: return sub_001F89F0;')
    headers=list(re.finditer(r'(?m)^[ \t]*(?:(?:static|inline)\s+)*recomp_func_t\s+[A-Za-z_][A-Za-z_0-9]*\s*\([^;{}]*\)\s*\{',base[:pos]))
    require(headers,'Could not locate dispatcher header')
    at=headers[-1].start()
    require('switch' in base[headers[-1].end():pos],'Not inside expected switch dispatcher')
    patched=base[:at]+fn+'\n\n'+base[at:]
    old='    case 0x001F89F0u: return sub_001F89F0;'
    require(patched.count(old)==1,'V6e dispatch nonunique')
    patched=patched.replace(old,old+'\n    case 0x001F8F10u: return sub_001F8F10;',1)
    for anchor in ('K1-V6b APC QUEUED','K1-V6b APC DELIVERED','0x0ACE8000u',
                   's_k1v6Delivered >= 16u','P6DQ ROCKET HARD STOP',
                   'K1-V6E-RED-CAMERA-001F89F0-20261105'):
        require(patched.count(anchor)==base.count(anchor),'V6e anchor drift '+anchor)
    payload=patched.replace('\n',eol).encode('utf-8')
    result={'stage':'V6F_SOURCE_ONLY_NOT_BUILT_OR_HARDWARE_TESTED','target':'0x001F8F10',
        'retail_sha256':RET,'parent_v6e_sha256':sha(parent),
        'original_recomp_0010_sha256':sha(raw),'source_sha256':sha(payload),
        'translated_dependencies':translated_calls,'runtime_helpers':helper_calls,
        'true_tu_count':64,'true_tu_sha256':h,'marker':MARKER,
        'guest_tick_semantics_unchanged':True,'existing_apc_and_hard_fences_unchanged':True,
        'speedup_claimed':False,'hardware_tested':False}
    perf=('V6f PERFORMANCE EVIDENCE (from 2026-11-05 hardware log)\n'
        'first 4M-tick windows: approx 3.0-3.5M ticks/sec\n'
        'last 26,665,260 ticks: 150,980 ms = 176,614 ticks/sec\n'
        'direct dispatch total: 22,346; indirect dispatch total: 1,136,396\n'
        'quiet log muted lines: 4,372\n'
        'HOT 0x001E ticks: 25,676,405\n'
        'The late slowdown needs instrumentation profiling before fast-forwarding.\n'
        'SAFE BASELINE: V6f retains all diagnostic and execution semantics.\n')
    outputs=((DEST/'main.cpp',payload),
             (DEST/'v6f-manifest.json',(json.dumps(result,indent=2)+'\n').encode()),
             (DEST/'perf-evidence.txt',perf.encode()))
    for path,data in outputs:
        if path.exists():require(path.read_bytes()==data,'Refuse overwrite of modified staged artifact '+str(path))
    DEST.mkdir(parents=True,exist_ok=True)
    for path,data in outputs:
        if not path.exists():path.write_bytes(data)
    require((PARENT/'main.cpp').read_bytes()==parent,'Parent source modified during run')
    print(TAG+' SOURCE PASS: original 0x001F8F10 inserted with exact return/FP semantics')
    print(TAG+' PASS: dispatch, 64 TrueTUs, five-read APC and hard fences preserved')
    print(TAG+' PERF AUDIT: slowdown is real; NO UNSAFE TICK SKIP, acceleration not applied')
    print(TAG+' MAIN: '+str(DEST/'main.cpp'))
    print(TAG+' SHA256: '+sha(payload))
if __name__=='__main__':
    try:main()
    except Exception as e:
        print(TAG+' BLOCKED: '+str(e),file=sys.stderr);sys.exit(1)
