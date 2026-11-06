#!/usr/bin/env python3
"""K1-V7X: exact A/B rollback of V7U TLS pair into known V7I behavior.

This tests regression causality. NOT a retail-authentic final TLS replacement.
SHA-pins both V7I and V7U locally; changes only the original two bodies plus
a one-shot startup watermark. No memory fence / I/O / graphics change.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,sys
from pathlib import Path
MARK="K1-V7X-TLS-AB-RECOVERY-20261106"
BOOT='    trace("PASS: exact retail XBE data + Phase-2E TIB/TLS/stack environment active");'
def sha(data):return hashlib.sha256(data).hexdigest()
def check(v,why):
    if not v:raise ValueError(why)
def import_v7u(path):
    spec=importlib.util.spec_from_file_location("k1v7u_stage",path)
    check(spec is not None and spec.loader is not None,"V7U staging module absent")
    mod=importlib.util.module_from_spec(spec);spec.loader.exec_module(mod)
    return mod
def patch(u,mod,baseline):
    check(u.startswith("/* "+mod.MARK+" */\n"),"V7U source watermark differs")
    check(u.count(mod.NEW_GET)==1 and u.count(mod.NEW_SET)==1,
          "V7U retail TLS function bodies no longer unique")
    recovered=u.replace(mod.NEW_GET,mod.OLD_GET,1).replace(mod.NEW_SET,mod.OLD_SET,1)
    recovered=recovered.replace("/* "+mod.MARK+" */\n","",1)
    check(recovered==baseline,"V7U differs from V7I outside two exact TLS bodies")
    check(baseline.count(BOOT)==1,"Unique original boot trace missing")
    stamped=recovered.replace(BOOT,BOOT+'\n    trace("'+MARK+' BOOT");',1)
    check(stamped.replace('\n    trace("'+MARK+' BOOT");',"",1)==baseline,
          "A/B instrumentation changed content besides runtime watermark")
    return stamped
def main():
    p=argparse.ArgumentParser()
    for key in ("v7i","v7i_manifest","v7u","v7u_manifest","module","out","out_manifest"):
        p.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    vi=a.v7i.read_bytes(); vu=a.v7u.read_bytes()
    mi=json.loads(a.v7i_manifest.read_text(encoding="utf-8-sig"))
    mu=json.loads(a.v7u_manifest.read_text(encoding="utf-8-sig"))
    check(mi.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY"
          and mi.get("source_sha256")==sha(vi)
          and mu.get("stage")=="V7U_RETAIL_X86_TLS_PAIR_IN_V7I_SOURCE_ONLY"
          and mu.get("source_sha256")==sha(vu)
          and mu.get("parent_v7i_sha256")==sha(vi)
          and mu.get("replaced_two_exact_v7i_maintained_tls_shims") is True
          and mu.get("apc_and_storage_fences_unchanged") is True
          and mu.get("no_guest_abi_bypass") is True
          and len(mi.get("true_tu_sha256",{}))==64
          and mi.get("true_tu_sha256")==mu.get("true_tu_sha256"),
          "V7I/V7U SHA, ABI and 64 TrueTU provenance mismatch")
    check((b"\r\n" in vi)==(b"\r\n" in vu),"Newline styles differ")
    newline="\r\n" if b"\r\n" in vi else "\n"
    baseline=vi.decode("utf-8").replace("\r\n","\n")
    v7u=vu.decode("utf-8").replace("\r\n","\n")
    mod=import_v7u(a.module)
    stamped=patch(v7u,mod,baseline).replace("\n",newline).encode("utf-8")
    meta=dict(mi)
    meta.update({"stage":"V7X_CONTROLLED_REVERT_V7U_TLS_TO_V7I_AB_SOURCE_ONLY",
                 "source_sha256":sha(stamped),
                 "parent_v7i_sha256":sha(vi),"parent_v7u_sha256":sha(vu),
                 "runtime_fingerprint":MARK,
                 "retail_tls_replacement_active":False,
                 "maintained_v7i_last_error_handlers_active":True,
                 "only_differences_from_v7i":"single startup fingerprint trace",
                 "only_differences_from_v7u":"two exact TLS bodies and startup fingerprint",
                 "retail_authentic_tls_final_fix":False,
                 "apc_and_storage_fences_unchanged":True,
                 "xdk_compiled":False,"hardware_verified":False})
    manifest=(json.dumps(meta,indent=2)+"\n").encode("utf-8")
    for file,data in ((a.out,stamped),(a.out_manifest,manifest)):
        check(not file.exists() or file.read_bytes()==data,
              "Existing output differs; refusing overwrite: "+str(file))
    for file,data in ((a.out,stamped),(a.out_manifest,manifest)):
        file.parent.mkdir(parents=True,exist_ok=True)
        if not file.exists():file.write_bytes(data)
    check(a.v7i.read_bytes()==vi and a.v7u.read_bytes()==vu,
          "Parent source changed while staging")
    print("[K1-V7X] EXACT A/B SOURCE PASS: V7U -> V7I TLS pair recovered byte-for-byte")
    print("[K1-V7X] V7I + unique runtime boot watermark; 64 TrueTUs identical")
    print("[K1-V7X] NO XDK, NO HARDWARE; NOT retail-authentic final TLS implementation")
    print("[K1-V7X] OUTPUT "+str(a.out))
if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("[K1-V7X] HARD FENCE "+str(ex),file=sys.stderr);sys.exit(1)
