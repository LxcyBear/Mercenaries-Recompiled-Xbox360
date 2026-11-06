#!/usr/bin/env python3
"""V7R read-only discovery of real V7I guest FS/flags/return interfaces.

Inspects only the user's local generated V7I main and original TrueTU header.
Never guesses FS base or uses native Xenon TLS. No generated code or XDK.
The concise summary is shareable metadata; implementation excerpts remain local.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path

MARKERS={
    "fs_access":r"(?i)\b(?:fs(?:_|[.:\[])|tib|tls|teb|thread_local|segment_base|thread_info)\w*",
    "cpu_flags":r"\b(?:eflags|rflags|zf|cf|sf|of|af|pf|flag_zf|flag_cf|flags_|cmp_flags|set_flags)\b",
    "guest_memory":r"\b(?:GUEST_READ8|GUEST_READ32|GUEST_WRITE32|GUEST_READ16|GUEST_WRITE16)\s*\(",
    "guest_stack":r"\b(?:g_esp|savedEsp|ret_esp|guest_esp|ESP_OFFSET)\b",
    "packed_route":r"\b(?:phase4c_lookup_pack_func|phase4c_dispatch|phase5bc_dispatch_packed_icall)\s*\(",
}
def need(ok,msg):
    if not ok:raise ValueError(msg)
def summary(path,code):
    lines=code.splitlines()
    result={}
    for kind,pattern in MARKERS.items():
        rx=re.compile(pattern)
        hits=[(i+1,x.strip()) for i,x in enumerate(lines) if rx.search(x)]
        result[kind]={"total_lines":len(hits),
            "first_locations":[i for i,_ in hits[:30]],
            "example_identifiers":sorted({m.group(0) for _,line in hits[:100]
                                          for m in rx.finditer(line)})[:30]}
    return result
def local_excerpts(path,src,pattern,max_hits):
    lines=src.splitlines()
    rx=re.compile(pattern)
    indices=[i for i,x in enumerate(lines) if rx.search(x)]
    selected=indices[:max_hits]
    parts=["======== "+str(path)+" : "+pattern+" ========"]
    for i in selected:
        parts.append("--- source line "+str(i+1)+" ---")
        for j in range(max(0,i-3),min(len(lines),i+4)):
            parts.append("%6d  %s"%(j+1,lines[j]))
    parts.append("total matching lines="+str(len(indices)))
    return "\n".join(parts)
def main():
    parser=argparse.ArgumentParser()
    for n in ("main","manifest","shards","output","private_excerpts"):
        parser.add_argument("--"+n.replace("_","-"),type=Path,required=True)
    a=parser.parse_args()
    main_bytes=a.main.read_bytes()
    manifest=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    need(manifest.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY" and
         manifest.get("source_sha256")==hashlib.sha256(main_bytes).hexdigest(),
         "Current V7I parent identity changed; no guessing")
    main=main_bytes.decode("utf-8",errors="replace")
    need("GUEST_READ32" in main and "phase4c_lookup_pack_func" in main,
         "Expected guest memory or dispatch primitives missing")
    path=a.shards/"translated_runtime.h"
    need(path.is_file(),"Missing original 64 TrueTU runtime header")
    header=path.read_text(encoding="utf-8",errors="replace")
    shards=sorted(a.shards.glob("translated_???.cpp"))
    need(len(shards)==64,"Not 64 TrueTU translation units")
    report={
        "stage":"K1_V7R_REAL_GUEST_FS_FLAGS_RUNTIME_DISCOVERY",
        "parent_sha256":hashlib.sha256(main_bytes).hexdigest(),
        "true_tus":len(shards),
        "main":summary(a.main,main),
        "runtime_header":summary(path,header),
        "retail_tls_targets":["0x0022B150","0x0022B178"],
        "binding_safety":"UNRESOLVED: manual inspection required; never invent FS or flag semantics",
        "xdk_build":False,"xbox_run":False,
    }
    a.output.parent.mkdir(parents=True,exist_ok=True)
    a.private_excerpts.parent.mkdir(parents=True,exist_ok=True)
    need(a.output.resolve()!=a.private_excerpts.resolve(),"Shareable and private paths overlap")
    a.output.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    data=[]
    for name,regex in MARKERS.items():
        if name=="guest_stack":continue
        data.append("======== "+name+" ========")
        data.append(local_excerpts(a.main,main,regex,18))
        data.append(local_excerpts(path,header,regex,15))
    a.private_excerpts.write_text("\n\n".join(data)+"\n",encoding="utf-8")
    print("[K1-V7R] V7I SHA PASS, 64 TrueTUs PASS")
    for name in ("fs_access","cpu_flags","guest_memory","packed_route"):
        m=report["main"][name]["total_lines"]
        h=report["runtime_header"][name]["total_lines"]
        print("[K1-V7R] %-14s main_match_lines=%d header_match_lines=%d"%(name,m,h))
    print("[K1-V7R] REPORT "+str(a.output))
    print("[K1-V7R] PRIVATE ORIGINAL SOURCE EXCERPTS "+str(a.private_excerpts))
    print("[K1-V7R] NO RUNTIME PATCH / NO XDK / NO XBOX")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7R] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
