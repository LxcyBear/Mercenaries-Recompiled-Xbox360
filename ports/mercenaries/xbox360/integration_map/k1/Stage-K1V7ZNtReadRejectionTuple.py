#!/usr/bin/env python3
"""K1-V7Z: one-shot hard-fenced NtReadFile APC rejection evidence.

Do not accept a new APC form. Only log rejected arguments at the existing
STORAGE_IO boundary. Adds a unique XEX boot marker on exactly V7X source.
"""
from __future__ import annotations
import argparse,hashlib,json,sys
from pathlib import Path
MARK="K1-V7Z-NTREAD-REJECT-TUPLE-20261106"
PARENT="K1-V7X-TLS-AB-RECOVERY-20261106"
BOOT='    trace("'+PARENT+' BOOT");'
REJECT='''        trace("STORAGE IO UNSUPPORTED: NtReadFile Event/APC callback form");
        phase4c_escape(
            PHASE4C_BOUNDARY_STORAGE_IO,
            0x800000DBu,
            savedEsp);'''
DIAG='''        /* K1-V7Z: one-shot, read-only rejected NtReadFile argument tuple.
         * Keep the original reject, hard escape, and no-APC policy intact. */
        {
            static uint32_t k1v7zRejectedReports = 0u;
            if (k1v7zRejectedReports++ == 0u)
            {
                sprintf(
                    line,
                    "K1-V7Z NTREAD REJECT: handle=%08X event=%08X apc=%08X context=%08X iosb=%08X buffer=%08X length=%u offptr=%08X offhi=%08X offlo=%08X saved=%08X call=%08X ret=%08X",
                    (unsigned int)handleToken,
                    (unsigned int)eventToken,
                    (unsigned int)apcRoutine,
                    (unsigned int)apcContext,
                    (unsigned int)ioStatusVa,
                    (unsigned int)bufferVa,
                    (unsigned int)length,
                    (unsigned int)offsetVa,
                    (unsigned int)offsetHigh,
                    (unsigned int)offsetLow,
                    (unsigned int)savedEsp,
                    (unsigned int)callEsp,
                    (unsigned int)returnSlot);
                trace(line);
            }
        }
'''
def sha(data):return hashlib.sha256(data).hexdigest()
def need(ok,msg):
    if not ok:raise ValueError(msg)
def patch(code):
    need(MARK not in code,"V7Z already present")
    need(code.count(BOOT)==1,"Unique V7X boot fingerprint missing")
    need(code.count(REJECT)==1,"Existing NtReadFile rejection block differs")
    for tag in ("if (savedEsp != callEsp + 36u)",
                "if (!k1V5ObservedApc)",
                "STORAGE IO UNSUPPORTED: NtReadFile Event/APC callback form",
                "PHASE4C_BOUNDARY_STORAGE_IO",
                "K1-V6O-LOCKED-DSK-EXACT-LOWER-BUFFER-20261105"):
        need(tag in code,"Required source fence absent: "+tag)
    result=code.replace(BOOT,BOOT+'\n    trace("'+MARK+' BOOT");',1)
    result=result.replace(REJECT,DIAG+REJECT,1)
    need(result.replace(DIAG,"",1).replace('\n    trace("'+MARK+' BOOT");',"",1)==code,
         "V7Z altered non-diagnostic source")
    need(result.count("PHASE4C_BOUNDARY_STORAGE_IO")==code.count("PHASE4C_BOUNDARY_STORAGE_IO"),
         "STORAGE_IO fence count changed")
    return result
def main():
    p=argparse.ArgumentParser()
    for key in ("parent","manifest","out","out_manifest"):
        p.add_argument("--"+key.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    original=a.parent.read_bytes()
    parent=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    need(parent.get("stage")=="V7X_CONTROLLED_REVERT_V7U_TLS_TO_V7I_AB_SOURCE_ONLY" and
         parent.get("source_sha256")==sha(original) and
         parent.get("runtime_fingerprint")==PARENT and
         parent.get("maintained_v7i_last_error_handlers_active") is True and
         parent.get("apc_and_storage_fences_unchanged") is True and
         len(parent.get("true_tu_sha256",{}))==64,
         "Parent V7X identity/64 TrueTU/source safeguards absent")
    newline="\r\n" if b"\r\n" in original else "\n"
    source=original.decode("utf-8").replace("\r\n","\n")
    output=patch(source).replace("\n",newline).encode("utf-8")
    m=dict(parent)
    m.update({
        "stage":"V7Z_NTREAD_APC_REJECTION_TUPLE_EVIDENCE_SOURCE_ONLY",
        "source_sha256":sha(output),
        "parent_v7x_sha256":sha(original),
        "runtime_fingerprint":MARK,
        "one_shot_rejected_ntread_tuple":True,
        "no_new_apc_forms_admitted":True,
        "ntread_frame_guard_unchanged":True,
        "ntread_storage_io_hard_fence_unchanged":True,
        "all_guest_logic_unchanged":True,
        "xdk_compiled":False,
        "hardware_verified":False})
    meta=(json.dumps(m,indent=2)+"\n").encode("utf-8")
    for path,data in ((a.out,output),(a.out_manifest,meta)):
        need(not path.exists() or path.read_bytes()==data,
             "Refusing changed existing output "+str(path))
    for path,data in ((a.out,output),(a.out_manifest,meta)):
        path.parent.mkdir(parents=True,exist_ok=True)
        if not path.exists():path.write_bytes(data)
    need(a.parent.read_bytes()==original,"Parent V7X changed during staging")
    print("[K1-V7Z] SOURCE PASS: unique BOOT + first rejected NtReadFile argument tuple")
    print("[K1-V7Z] 36-byte ABI, Event/APC rejection, 64 TrueTUs unchanged")
    print("[K1-V7Z] NO XDK / NO XBOX, no new request admitted")
    print("[K1-V7Z] OUTPUT "+str(a.out))
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("[K1-V7Z] HARD FENCE "+str(exc),file=sys.stderr);sys.exit(1)
