#!/usr/bin/env python3
"""K1-V7V: one-shot XEX identity + TLS entry witnesses from exact V7U.

Retains every V7U guest instruction, all old routes and all fault fences.
No runtime timing flood, fake MMIO mapping, or speculative ABI repair.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
MARK="K1-V7V-ORANGE-EARLY-FAULT-WITNESS-20261106"
BOOT='    trace("PASS: exact retail XBE data + Phase-2E TIB/TLS/stack environment active");'
GET='    RECOMP_TRACE_FUNC(0x0022B150u);\n    const uint8_t selector'
SET='    RECOMP_TRACE_FUNC(0x0022B178u);\n    const uint8_t selector'
def need(ok,why):
    if not ok:raise ValueError(why)
def sha(x):return hashlib.sha256(x).hexdigest()
def replace_once(text,old,new,label):
    need(text.count(old)==1,"Expected exactly one "+label+"; got "+str(text.count(old)))
    return text.replace(old,new,1)
def patch(text):
    need(MARK not in text,"Already V7V-marked")
    for token in ("K1-V7U-RETAIL-TLS-X86-PAIR-20261106",
                  "case 0x0022B150u: return sub_0022B150;",
                  "case 0x0022B178u: return sub_0022B178;",
                  "P6DQ ROCKET HARD STOP",
                  "P6DQ ASYNC STREAM READ"):
        need(token in text,"Missing baseline source token: "+token)
    boot=BOOT+'\n    trace("'+MARK+' BOOT");'
    text=replace_once(text,BOOT,boot,"entry-point boot witness")
    text=replace_once(text,GET,
        '    RECOMP_TRACE_FUNC(0x0022B150u);\n'
        '    { static uint32_t k1v7v_tls_get_hits = 0u;\n'
        '      if (k1v7v_tls_get_hits++ == 0u)\n'
        '          trace("'+MARK+' TLS_GET_ENTER"); }\n'
        '    const uint8_t selector',"TLS getter entry")
    text=replace_once(text,SET,
        '    RECOMP_TRACE_FUNC(0x0022B178u);\n'
        '    { static uint32_t k1v7v_tls_set_hits = 0u;\n'
        '      if (k1v7v_tls_set_hits++ == 0u)\n'
        '          trace("'+MARK+' TLS_SET_ENTER"); }\n'
        '    const uint8_t selector',"TLS setter entry")
    return text
def main():
    p=argparse.ArgumentParser()
    for key in ("parent","manifest","out","out_manifest"):
        p.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    orig=a.parent.read_bytes()
    manifest=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    need(manifest.get("stage")=="V7U_RETAIL_X86_TLS_PAIR_IN_V7I_SOURCE_ONLY" and
         manifest.get("source_sha256")==sha(orig) and
         manifest.get("replaced_two_exact_v7i_maintained_tls_shims") is True and
         manifest.get("original_lookup_routes_preserved") is True and
         manifest.get("apc_and_storage_fences_unchanged") is True and
         manifest.get("no_guest_abi_bypass") is True and
         len(manifest.get("true_tu_sha256",{}))==64,
         "V7U source/ABI/TrueTU provenance changed")
    newline="\r\n" if b"\r\n" in orig else "\n"
    before=orig.decode("utf-8").replace("\r\n","\n")
    after=patch(before)
    # Verify exact inverse, including all guest logic and original fences.
    def remove_probe(s):
        s=s.replace(BOOT+'\n    trace("'+MARK+' BOOT");',BOOT,1)
        s=s.replace(
            '    RECOMP_TRACE_FUNC(0x0022B150u);\n'
            '    { static uint32_t k1v7v_tls_get_hits = 0u;\n'
            '      if (k1v7v_tls_get_hits++ == 0u)\n'
            '          trace("'+MARK+' TLS_GET_ENTER"); }\n'
            '    const uint8_t selector',GET,1)
        s=s.replace(
            '    RECOMP_TRACE_FUNC(0x0022B178u);\n'
            '    { static uint32_t k1v7v_tls_set_hits = 0u;\n'
            '      if (k1v7v_tls_set_hits++ == 0u)\n'
            '          trace("'+MARK+' TLS_SET_ENTER"); }\n'
            '    const uint8_t selector',SET,1)
        return s
    need(remove_probe(after)==before,"Instrumentation changed guest source outside three witnesses")
    output=after.replace("\n",newline).encode("utf-8")
    meta=dict(manifest)
    meta.update({"stage":"V7V_UNIQUE_XEX_AND_TLS_ENTRY_WITNESSES_SOURCE_ONLY",
                 "source_sha256":sha(output),
                 "parent_v7u_sha256":sha(orig),
                 "runtime_fingerprint":MARK,
                 "unique_boot_marker":True,"one_shot_tls_entry_markers":True,
                 "all_guest_logic_unchanged":True,
                 "apc_and_storage_fences_unchanged":True,
                 "xdk_compiled":False,"hardware_verified":False})
    for path,data in ((a.out,output),
                      (a.out_manifest,(json.dumps(meta,indent=2)+"\n").encode("utf-8"))):
        need(not path.exists() or path.read_bytes()==data,
             "Refusing overwrite of mismatching existing stage: "+str(path))
    for path,data in ((a.out,output),
                      (a.out_manifest,(json.dumps(meta,indent=2)+"\n").encode("utf-8"))):
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(data)
    need(a.parent.read_bytes()==orig,"Parent V7U source changed")
    print("[K1-V7V] SOURCE PASS: unique boot fingerprint + one-shot TLS getter/setter witnesses")
    print("[K1-V7V] Original guest semantics, 64 TrueTUs, fault/APC/GPU fences preserved")
    print("[K1-V7V] FINGERPRINT "+MARK)
    print("[K1-V7V] OUTPUT "+str(a.out))
    print("[K1-V7V] NO XDK / NO XBOX")
if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("[K1-V7V] HARD FENCE "+str(ex),file=sys.stderr)
        sys.exit(1)
