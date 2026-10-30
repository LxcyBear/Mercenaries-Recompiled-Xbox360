#!/usr/bin/env python3
"""Synthetic coverage audit regression; contains no retail XBE bytes."""
import importlib.util
from pathlib import Path
from tempfile import TemporaryDirectory
spec=importlib.util.spec_from_file_location('coverage',Path(__file__).with_name('Audit-K1A-DsoundWriterCoverage.py'))
m=importlib.util.module_from_spec(spec);spec.loader.exec_module(m)
with TemporaryDirectory() as tmp:
    root=Path(tmp); (root/'shards').mkdir()
    main=root/'main.cpp'
    main.write_text('// '+m.CLOCK+'\nGUEST_WRITE32(0x00041D70, 1);\n')
    header=root/'shards'/'translated_runtime.h'
    header.write_text(('// '+m.WATCH+'\n')*3+'void f(){ phase6ch_apu_write32(4,1); }\n')
    for i in range(64):
        (root/'shards'/f'translated_{i:03d}.cpp').write_text('GUEST_WRITE32(eax,edx);\n')
    data=m.extract(main,root/'shards')
    assert data['watch_owner']=='translated_runtime.h'
    assert data['counts']['DIRECT_GUEST_WRITE']==65,data
    assert data['counts']['APU_HELPER_WRITES']==1,data
    assert data['counts']['ADDRESS_41D70']==1,data
    main.write_text('missing marker')
    try:m.extract(main,root/'shards')
    except ValueError:pass
    else:raise AssertionError('accepted bad main')
    main.write_text('// '+m.CLOCK)
    header.write_text('no watch')
    try:m.extract(main,root/'shards')
    except ValueError:pass
    else:raise AssertionError('accepted missing hooks')
print('[K1A-COVERAGE] PASS: synthetic 64-source lexical coverage and fail-closed stage identity')
