#!/usr/bin/env python3
"""Stage K1A clock integration in a separate main.cpp (NEVER alter R76 input).

Uses exact own R76 translated main from local build, plus the pure K1A
portable core and guest-memory bridge. No retail bytes or game data exported.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
from pathlib import Path

MARKER = "P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029"
PATCH_MARKER = "P6K1A-CLOCK-DISPATCH-BATCH-20261029"
CLOCK_NAME = "phase4c_system_time_100ns"
DISPATCH = "void phase5bc_dispatch_packed_icall("
ORDS = (128,304,305)

ADAPTER = r'''
/* P6K1A: Xbox kernel 100ns clock and calendar, staged guest ABI bridge.
   The import has stdcall-style guest arguments: [ESP+0]=return slot;
   [ESP+4] first pointer; [ESP+8] second pointer. As with the existing
   Phase6DQ kernel handlers, savedEsp is the post-return guest stack.
   The checks below guard null/overflow; GUEST_READ/WRITE keep their
   original mapping/MMIO hard fences for any unbacked guest address.
   RtlTimeFieldsToTime returns BOOLEAN in eax; other APIs are VOID.
   Do not manufacture kernel success for unmapped guest memory. */
struct phase6k1a_guest_memory
{
    bool readable(uint32_t address, uint32_t length) const
    {
        return address != 0u &&
            (uint64_t)address + (uint64_t)length <= UINT64_C(0x100000000);
    }
    bool writable(uint32_t address, uint32_t length) const
    {
        return readable(address,length);
    }
    uint16_t read16(uint32_t address) const { return GUEST_READ16(address); }
    uint32_t read32(uint32_t address) const { return GUEST_READ32(address); }
    void write16(uint32_t address, uint16_t v) { GUEST_WRITE16(address,v); }
    void write32(uint32_t address, uint32_t v) { GUEST_WRITE32(address,v); }
};
static void phase6k1a_clock_fence(uint32_t target, uint32_t savedEsp)
{
    phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE,target,savedEsp);
}
static void phase6k1a_ke_query_system_time(uint32_t savedEsp)
{
    uint32_t const output = GUEST_READ32(g_esp + 4u);
    phase6k1a_guest_memory mem;
    if (!merc360_k1::GuestClock<phase6k1a_guest_memory>::query_system_time(
            mem,output,phase4c_system_time_100ns()))
    {
        phase6k1a_clock_fence(0x80000080u,savedEsp);
        return;
    }
    static uint32_t calls = 0u;
    if (++calls <= 8u)
    {
        char line[192];
        sprintf(line,
          "P6K1A KESYSTEMTIME128: calls=%u output=%08X caller=%08X saved_esp=%08X",
          (unsigned int)calls,(unsigned int)output,
          (unsigned int)phase4c_current_caller(),(unsigned int)savedEsp);
        trace(line);
    }
    // VOID kernel service: preserve caller-visible eax; do not fake an NTSTATUS.
    g_esp = savedEsp;
}
static void phase6k1a_rtl_time_fields_to_time(uint32_t savedEsp)
{
    uint32_t const input = GUEST_READ32(g_esp + 4u);
    uint32_t const output = GUEST_READ32(g_esp + 8u);
    uint32_t result = 0u;
    phase6k1a_guest_memory mem;
    if (!merc360_k1::GuestClock<phase6k1a_guest_memory>::time_fields_to_time(
            mem,input,output,&result))
    {
        phase6k1a_clock_fence(0x80000130u,savedEsp);
        return;
    }
    eax = result;  // BOOLEAN: valid TIME_FIELDS converted successfully.
    g_esp = savedEsp;
}
static void phase6k1a_rtl_time_to_time_fields(uint32_t savedEsp)
{
    uint32_t const input = GUEST_READ32(g_esp + 4u);
    uint32_t const output = GUEST_READ32(g_esp + 8u);
    phase6k1a_guest_memory mem;
    if (!merc360_k1::GuestClock<phase6k1a_guest_memory>::time_to_time_fields(
            mem,input,output))
    {
        phase6k1a_clock_fence(0x80000131u,savedEsp);
        return;
    }
    // VOID: do not overwrite eax.
    g_esp = savedEsp;
}
'''

ROUTES = r'''    /* P6K1A exact retail kernel time/date batch; before generic pack lookup. */
    if (target == 0x80000080u)
    {
        phase6k1a_ke_query_system_time(savedEsp);
        return;
    }
    if (target == 0x80000130u)
    {
        phase6k1a_rtl_time_fields_to_time(savedEsp);
        return;
    }
    if (target == 0x80000131u)
    {
        phase6k1a_rtl_time_to_time_fields(savedEsp);
        return;
    }

'''

def sha(data: bytes) -> str:
    return hashlib.sha256(data).hexdigest()

def assert_once(text:str,fragment:str)->None:
    count=text.count(fragment)
    if count!=1:raise ValueError(f"expected exactly one {fragment!r}, got {count}")

def inline_components(folder:Path)->str:
    core=(folder/'KernelClockCore.h').read_text(encoding='utf-8')
    guest=(folder/'KernelClockGuestBridge.h').read_text(encoding='utf-8')
    for s in ('namespace merc360_k1','to_ticks(','from_ticks('):
        if s not in core:raise ValueError('clock core identity mismatch: '+s)
    for s in ('struct GuestClock','valid_range(','query_system_time(','time_fields_to_time(','time_to_time_fields('):
        if s not in guest:raise ValueError('clock guest bridge identity mismatch: '+s)
    guest=guest.replace('#include "KernelClockCore.h"\n','',1)
    if '#include "KernelClockCore.h"' in guest:
        raise ValueError('clock bridge include duplicate')
    return (f'\n/* {PATCH_MARKER}: Begin full-class clock/time bridge. */\n'
            +core+'\n'+guest+'\n'+ADAPTER+'\n'
            +f'/* {PATCH_MARKER}: End class definitions. */\n')

def patch(text:str,components:str)->str:
    assert_once(text,MARKER)
    if PATCH_MARKER in text:raise ValueError('K1A bridge already staged: refuse duplicate')
    assert_once(text,'uint64_t phase4c_system_time_100ns(void)')
    # The exact R76 packed dispatcher signature was captured by the user's
    # local K1A audit; distinguish actual definitions from forward declarations.
    definition = re.compile(
        r'(?m)^[ 	]*(?:static[ 	]+)?void[ 	]+'
        r'phase5bc_dispatch_packed_icall\s*\(\s*'
        r'uint32_t\s+target\s*,\s*uint32_t\s+savedEsp\s*\)\s*\{')
    matches = list(definition.finditer(text))
    if len(matches)!=1:
        raise ValueError(f'exact R76 packed dispatcher definition count={len(matches)}')
    for x in ('GUEST_READ16','GUEST_WRITE16','GUEST_READ32','GUEST_WRITE32',
              'phase4c_escape','PHASE4C_BOUNDARY_ICALL_SAFE'):
        if x not in text:raise ValueError('missing guest runtime primitive '+x)
    # The original R76 source must not contain handlers for these three targets.
    for n in (0x80000080,0x80000130,0x80000131):
        if re.search(r'(?i)(?:_phase4c_target|_phase4c_tail_target|target)\s*==\s*0x'+f'{n:08X}'+r'u\b',text):
            raise ValueError(f'already routed ordinal {n&0xFFFF}; refusing duplicate')
    i=matches[0].start()
    # Inject immediately before dispatcher definition, AFTER the existing clock
    # helper and guest read/write wrappers are defined in this R76 source.
    if text.index('uint64_t phase4c_system_time_100ns(void)')>i:
        raise ValueError('clock helper appears after dispatcher; cannot stage')
    changed=text[:i]+components+text[i:]
    at=i+len(components)
    brace=changed.find('{',at)
    if brace<0 or brace>at+180:
        raise ValueError('packed dispatcher definition brace missing or distant')
    if brace<0:raise ValueError('dispatcher opening brace missing')
    changed=changed[:brace+1]+'\n'+ROUTES+changed[brace+1:]
    for n in ('phase6k1a_ke_query_system_time(savedEsp)',
              'phase6k1a_rtl_time_fields_to_time(savedEsp)',
              'phase6k1a_rtl_time_to_time_fields(savedEsp)'):
        assert_once(changed,n)
    return changed

def stage(main:Path,out:Path,component_root:Path)->dict:
    if main.resolve()==out.resolve():
        raise ValueError('refuse in-place mutation of the R76 source')
    data=main.read_bytes()
    text=data.decode('utf-8')
    changed=patch(text,inline_components(component_root))
    out.parent.mkdir(parents=True,exist_ok=True)
    staged=changed.encode('utf-8')
    out.write_bytes(staged)
    # Strong local proof original was not touched.
    if sha(main.read_bytes())!=sha(data):
        raise RuntimeError('R76 input changed while staging')
    metadata={'phase':'K1A','status':'STAGED_NOT_BUILT',
              'patch_marker':PATCH_MARKER,
              'import_ordinals':list(ORDS),
              'original_main_sha256':sha(data),'staged_main_sha256':sha(staged),
              'original_bytes':len(data),'staged_bytes':len(staged),
              'original_main_path':str(main.resolve()),
              'staged_main_path':str(out.resolve()),
              'untouched_true_tu_shards':64,
              'guest_memory_contract':'old R76 GUEST_READ/WRITE MMIO hard fences retained'}
    (out.parent/'k1a-stage-manifest.json').write_text(
        json.dumps(metadata,indent=2)+'\n',encoding='utf-8')
    return metadata

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument('--main',type=Path,required=True)
    p.add_argument('--out',type=Path,required=True)
    a=p.parse_args()
    doc=stage(a.main,a.out,Path(__file__).resolve().parent)
    print('[K1A] STAGE PASS: 3 original Xbox clock/calendar API routes inserted')
    print('[K1A] R76 source SHA preserved: '+doc['original_main_sha256'])
    print('[K1A] NO Xbox build, NO altered R76 main or translated TrueTU shard')
    print('[K1A] STAGED MAIN: '+str(a.out))
    print('[K1A] MANIFEST: '+str(a.out.parent/'k1a-stage-manifest.json'))
if __name__=='__main__':main()
