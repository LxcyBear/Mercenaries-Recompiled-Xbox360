#!/usr/bin/env python3
from pathlib import Path
import importlib.util
p=Path(__file__).with_name('Audit-K1A-Dispatch.py')
spec=importlib.util.spec_from_file_location('merc_k1_audit',p)
module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
main='''P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029
#define RECOMP_ICALL_SAFE(a, b) \
  do { phase4c_escape(PHASE4C_BOUNDARY_ICALL_SAFE, a, b); } while(0)
#define RECOMP_ITAIL(a) do { } while(0)
static uint64_t phase4c_system_time_100ns(void) { return 0; }
static void phase5bc_dispatch_packed_icall(uint32_t target, uint32_t savedEsp) {
 if (target == 0x80000080u) return;
}
'''
source='''P6DQ R59 FC4A ABI RESTORE:
static void sub_002A5293(void) { RECOMP_ICALL_SAFE(0x80000080u, 4); }
'''
report=module.audit(main,source)
for token in ('RECOMP_ICALL_SAFE','phase4c_system_time_100ns','phase5bc_dispatch_packed_icall','sub_002A5293'):
    assert token in report,token
assert 'source line' in report
for bad_main in (main.replace('P6DQ-R76-XGSCNT-CENTRAL-ROUTE-20261029',''),main+'\n#define RECOMP_ICALL_SAFE(a) x\n'):
    try:module.audit(bad_main,source)
    except ValueError:pass
    else:raise AssertionError('Audit accepted untrusted source identity/macro')
print('[K1A] PASS: strict R76 identity, macro/function extraction and negative guards')
