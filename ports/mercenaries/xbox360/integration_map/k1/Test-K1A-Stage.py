#!/usr/bin/env python3
"""K1A offline stage regression: NO real Mercenaries files or Xbox toolchain."""
from __future__ import annotations
import hashlib
import importlib.util
import json
import tempfile
from pathlib import Path

here=Path(__file__).resolve().parent
spec=importlib.util.spec_from_file_location(
    'mercenaries_k1a_stage',here/'Stage-K1A-ClockBatch.py')
module=importlib.util.module_from_spec(spec)
assert spec.loader is not None
spec.loader.exec_module(module)

SYNTHETIC_MAIN='''\
/* PHASE 6DQ REAL TRANSLATED STARTUP BOUNDARY PROOF START | P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029 */
typedef unsigned int uint32_t;
typedef unsigned long long uint64_t;
#define GUEST_READ16(a) fake_read16(a)
#define GUEST_READ32(a) fake_read32(a)
#define GUEST_WRITE16(a,b) fake_write16(a,b)
#define GUEST_WRITE32(a,b) fake_write32(a,b)
#define PHASE4C_BOUNDARY_ICALL_SAFE 2u
uint64_t phase4c_system_time_100ns(void) { return 116444736000000000ULL; }
void phase5bc_dispatch_packed_icall(uint32_t target, uint32_t savedEsp)
{
    recomp_func_t fn = phase4c_lookup_pack_func(target);
    if (!fn) { phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE, target, savedEsp); return; }
    fn();
}
'''

def expect_rejected(text:str,description:str):
    try:module.patch(text,module.inline_components(here))
    except ValueError:return
    raise AssertionError('Accepted unsafe staged source: '+description)

def check():
    with tempfile.TemporaryDirectory(prefix='merc360-k1a-stage-') as scratch:
        temp=Path(scratch)
        source=temp/'main.cpp'
        target=temp/'staged'/'main.cpp'
        source.write_text(SYNTHETIC_MAIN,encoding='utf-8')
        original=source.read_bytes()
        result=module.stage(source,target,here)
        assert source.read_bytes()==original,'R76 input MUTATED'
        assert result['original_main_sha256']==hashlib.sha256(original).hexdigest()
        assert result['staged_main_sha256']==hashlib.sha256(target.read_bytes()).hexdigest()
        assert result['untouched_true_tu_shards']==64
        modified=target.read_text(encoding='utf-8')
        assert modified.startswith(SYNTHETIC_MAIN[:45])
        assert modified.count(module.PATCH_MARKER)==2
        assert modified.count(module.BOOT_MARKER)==1
        assert result["boot_marker"]==module.BOOT_MARKER
        assert modified.count('phase6k1a_ke_query_system_time(savedEsp)')==1
        assert modified.count('phase6k1a_rtl_time_fields_to_time(savedEsp)')==1
        assert modified.count('phase6k1a_rtl_time_to_time_fields(savedEsp)')==1
        assert modified.count('phase4c_system_time_100ns()')==1
        assert modified.index('phase6k1a_ke_query_system_time(savedEsp)') < modified.index(
            'recomp_func_t fn = phase4c_lookup_pack_func(target)')
        for o in (0x80000080,0x80000130,0x80000131):
            assert modified.count(f'if (target == 0x{o:08X}u)')==1
        # Verify callable ABI and return types are not silently rewritten.
        assert 'uint32_t const output = GUEST_READ32(g_esp + 4u);' in modified
        assert 'uint32_t const input = GUEST_READ32(g_esp + 4u);' in modified
        assert 'uint32_t const output = GUEST_READ32(g_esp + 8u);' in modified
        assert 'eax = result;' in modified
        assert 'g_esp = savedEsp;' in modified
        assert 'phase6k1a_clock_fence(0x80000080u,savedEsp);' in modified
        assert 'phase4c_system_time_100ns()' in modified
        assert result['status']=='STAGED_NOT_BUILT'
        meta=json.loads((target.parent/'k1a-stage-manifest.json').read_text())
        assert meta==result
        expect_rejected(modified,'duplicate second K1A injection')
        expect_rejected(SYNTHETIC_MAIN.replace(module.MARKER,'WRONG-R76'),'wrong source watermark')
        expect_rejected(SYNTHETIC_MAIN.replace(
            'recomp_func_t fn = phase4c_lookup_pack_func(target);',
            'if (target == 0x80000080u) return; \n'
            'recomp_func_t fn = phase4c_lookup_pack_func(target);'), 'duplicate ordinal 128')
        expect_rejected(SYNTHETIC_MAIN.replace(
            'void phase5bc_dispatch_packed_icall(',
            'void phase5bc_dispatch_packed_icall('+
            'uint32_t x) {}\nvoid phase5bc_dispatch_packed_icall('),
            'multiple packed dispatchers')
        # Fail on a second function of the SAME signature as well.
        expect_rejected(SYNTHETIC_MAIN.replace(
            'void phase5bc_dispatch_packed_icall(',
            'void phase5bc_dispatch_packed_icall('+
            'uint32_t target, uint32_t savedEsp) {}\n'
            'void phase5bc_dispatch_packed_icall('), 'duplicate exact dispatcher')
        # A stray prototype must also trigger a fail-closed review rather than
        # silently broadening the supported integration surface.
        expect_rejected(SYNTHETIC_MAIN.replace(
            'void phase5bc_dispatch_packed_icall(',
            'void phase5bc_dispatch_packed_icall('+
            'uint32_t target, uint32_t savedEsp);\n'
            'void phase5bc_dispatch_packed_icall('), 'extra dispatcher declaration')
        try:module.stage(source,source,here)
        except ValueError:pass
        else:raise AssertionError('In-place R76 mutation was not rejected')
    print('[K1A] PASS: staged 3 clock routes; packed lookup bypass, ABI hooks, SHA and baseline guards')
    print('[K1A] PASS: wrong source, route duplicates, in-place mutation and repeated patch rejected')
    print('[K1A] TEST DATA: synthetic; no game, retail XBE or Xbox XDK file opened')

if __name__=='__main__':check()
