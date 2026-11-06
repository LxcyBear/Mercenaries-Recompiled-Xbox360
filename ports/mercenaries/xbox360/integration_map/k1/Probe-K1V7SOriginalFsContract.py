#!/usr/bin/env python3
"""K1 V7S: original-runtime guest FS/TIB/flags contract discovery.

Probe ORIGINAL generated C and verified V7I source for a concrete TLS binding.
No guest source text in metadata, no source mutation, no XDK or Xbox.
"""
from __future__ import annotations
import argparse,hashlib,json,re,sys
from pathlib import Path

KEYS={
  "fs_segment":r"(?i)(?:\bfs\s*:\s*\[|\b(?:recomp|guest|xbox|phase\w+)_(?:fs|tls|tib|teb)\w*\s*\(|\bfs_(?:base|read|write)\b|\b(?:fs_base|tib_base|teb_base)\b)",
  "tls_index":r"(?i)(?:0x0*869118\b|\b(?:fs|tls|tib|teb)\s*[:\[]\s*(?:0x)?(?:24|28|04)\b)",
  "guest_flags":r"(?i)\b(?:eflags|recomp_(?:flags|cmp|setcc|condition)\w*|guest_flags|flag_(?:zf|cf|sf|of|pf|af)|(?:zf|cf|sf|of|pf|af))\b",
  "guest_memory":r"\b(?:GUEST_READ32|GUEST_WRITE32|recomp_guest_read32|recomp_guest_write32)\s*\(",
}
def check(cond,msg):
    if not cond:raise ValueError(msg)
def inspect(path,patterns,limit=120):
    text=path.read_text(encoding="utf-8",errors="replace")
    rows=text.splitlines()
    out={}
    for name,regex in patterns.items():
        rx=re.compile(regex)
        found=[i for i,line in enumerate(rows) if rx.search(line)]
        out[name]={
            "hit_lines":len(found),
            "line_numbers":[v+1 for v in found[:limit]],
        }
    return out,text
def main():
    p=argparse.ArgumentParser()
    for name in ("main","manifest","generated","shard_header","out","local"):
        p.add_argument("--"+name.replace("_","-"),required=True,type=Path)
    a=p.parse_args()
    mb=a.main.read_bytes()
    m=json.loads(a.manifest.read_text(encoding="utf-8-sig"))
    check(m.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY" and
          m.get("source_sha256")==hashlib.sha256(mb).hexdigest(),
          "V7I identity mismatch")
    check(a.generated.is_dir() and a.shard_header.is_file(),"Original generated C or TrueTU header missing")
    files=sorted(x for x in a.generated.glob("recomp_*.c") if x.is_file())
    check(len(files)>10,"Original generated C corpus absent")
    parent={}
    excerpts=[]
    top={}
    # Only relevant matches; never publish original game source code.
    targets=[("v7i_main",a.main),("true_tu_header",a.shard_header)]
    for label,path in targets:
        info,code=inspect(path,KEYS)
        parent[label]={"file_sha256":hashlib.sha256(path.read_bytes()).hexdigest(),
                       "signals":info}
        lines=code.splitlines()
        for kind in ("fs_segment","tls_index","guest_flags"):
            for i in info[kind]["line_numbers"][:20]:
                low=max(0,i-3); high=min(len(lines),i+2)
                excerpts.append("=== %s %s line %d ==="%(label,kind,i))
                excerpts.extend("%d %s"%(j+1,lines[j]) for j in range(low,high))
    # Wider search looks for actual segment implementations rather than
    # treating mentions of the word "TLS" in trace strings as an API.
    candidates=[]
    for path in files:
        matches,body=inspect(path,{k:v for k,v in KEYS.items() if k!="guest_memory"},20)
        meaningful=sum(matches[k]["hit_lines"] for k in ("fs_segment","tls_index"))
        if meaningful:
            candidates.append({
                "file":path.name,
                "fs_matches":matches["fs_segment"]["hit_lines"],
                "tls_matches":matches["tls_index"]["hit_lines"],
                "flags_matches":matches["guest_flags"]["hit_lines"],
                "fs_lines":matches["fs_segment"]["line_numbers"][:20],
                "tls_lines":matches["tls_index"]["line_numbers"][:20],
            })
            lines=body.splitlines()
            indices=sorted(set(matches["fs_segment"]["line_numbers"][:8]+matches["tls_index"]["line_numbers"][:8]))
            for i in indices:
                excerpts.append("=== original C %s line %d ==="%(path.name,i))
                excerpts.extend("%d %s"%(j+1,lines[j]) for j in range(max(0,i-3),min(len(lines),i+2)))
    report={
        "stage":"K1_V7S_ORIGINAL_GUEST_FS_TIB_BINDING_DISCOVERY",
        "v7i_sha256":hashlib.sha256(mb).hexdigest(),
        "original_c_files_scanned":len(files),
        "parent_signals":parent,
        "source_files_with_fs_or_tls_signals":candidates,
        "binding_verified":False,
        "next_gate":"Review local source excerpts against original Xbox TIB layout. Do not bind until guest FS4/FS24/FS28 and CPU flags ownership are proven.",
        "source_only":True,"xdk_built":False,"xbox_run":False}
    check(a.out.resolve()!=a.local.resolve(),"Private excerpts and metadata must differ")
    for path in (a.out,a.local):path.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    a.local.write_text("PRIVATE ORIGINAL GENERATED SOURCE / DO NOT COMMIT\n"+"\n".join(excerpts)+"\n",encoding="utf-8")
    print("[K1-V7S] V7I SOURCE SHA PASS. Original generated C files scanned=%d"%len(files))
    print("[K1-V7S] Original C files with FS/TLS evidence=%d"%len(candidates))
    for f in candidates[:15]:
        print("[K1-V7S] %s FS=%d TLS=%d FLAGS=%d"%(f["file"],f["fs_matches"],f["tls_matches"],f["flags_matches"]))
    print("[K1-V7S] SHAREABLE METADATA "+str(a.out))
    print("[K1-V7S] LOCAL-ONLY EXCERPTS "+str(a.local))
    print("[K1-V7S] NO STAGING / NO XDK / NO XBOX / FS BINDING NOT ASSUMED")
if __name__=="__main__":
    try:main()
    except Exception as ex:
        print("[K1-V7S] HARD FENCE "+str(ex),file=sys.stderr)
        sys.exit(1)
