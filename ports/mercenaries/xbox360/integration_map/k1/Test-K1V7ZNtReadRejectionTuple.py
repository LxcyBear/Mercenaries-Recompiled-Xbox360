#!/usr/bin/env python3
"""V7Z synthetic exact insertion + fail closed."""
from __future__ import annotations
import importlib.util
from pathlib import Path
p=Path(__file__).with_name("Stage-K1V7ZNtReadRejectionTuple.py")
s=importlib.util.spec_from_file_location("v7z",p)
assert s and s.loader
m=importlib.util.module_from_spec(s);s.loader.exec_module(m)
baseline='''void boot()
{
    trace("K1-V7X-TLS-AB-RECOVERY-20261106 BOOT");
}
void phase5h_nt_read_file()
{
    if (savedEsp != callEsp + 36u) { PHASE4C_BOUNDARY_KERNEL_FRAME; }
    /* K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105 */
    if (!k1V5ObservedApc) {
'''+m.REJECT+'''
    }
}
'''
out=m.patch(baseline)
assert out.replace(m.DIAG,"",1).replace('\n    trace("'+m.MARK+' BOOT");',"",1)==baseline
assert out.count("PHASE4C_BOUNDARY_STORAGE_IO")==baseline.count("PHASE4C_BOUNDARY_STORAGE_IO")
assert out.count("K1-V7Z NTREAD REJECT")==1
for wrong in (baseline.replace("36u","44u"),
              baseline.replace("if (!k1V5ObservedApc)","if (k1V5ObservedApc)"),
              baseline.replace(m.REJECT,'trace("no guard");'),
              baseline.replace(m.PARENT,'other'),
              out):
    try:m.patch(wrong)
    except ValueError:pass
    else:raise AssertionError("V7Z accepted source drift")
print("[K1-V7Z] SELFTEST PASS: only boot and one-shot rejected argument logging")
print("[K1-V7Z] Reject and 36-byte hard fence retained, NO XDK / NO XBOX")
