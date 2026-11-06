#!/usr/bin/env python3
"""K1-V7F offline retail import / kernel bridge / V7E stop provenance audit.

A bounded READ-ONLY evidence collector. Never guesses ordinal 0x63's name
without a matching repository source or actual retail import declaration.
Does not compile, patch frames, downgrade fences, or invoke Xbox.
"""
from __future__ import annotations
import hashlib,json,re,sys
from pathlib import Path
ROOT=Path.cwd()
OUT=ROOT/"build/phase6_integration_map/k1_storage_boundary_v7f"
M=ROOT/"build/phase6_integration_map/k1_pixel_retail_five_batch_v7e"
SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
SLOTS=("0x80000063","80000063","0x00000063","ordinal 99","ordinal_99","ord 99",
       "STORAGE_IO","PHASE4C_BOUNDARY_KERNEL_FRAME")
ROOTCALL="0x0023A3CE"
def need(v,msg):
    if not v:raise ValueError(msg)
def h(b):return hashlib.sha256(b).hexdigest()
def find_patterns(s):
    # Include both the direct kernel thunk value and C++ dispatcher constants.
    return [p for p in SLOTS if p.casefold() in s.casefold()]
def extract(path,patterns,limit=40,window=5):
    txt=path.read_text(encoding="utf-8",errors="replace").splitlines()
    idx=[i for i,line in enumerate(txt) if any(p.casefold() in line.casefold() for p in patterns)]
    snippets=[]
    for i in idx[:limit]:
        snippets.append({"line":i+1,"text":"\n".join(
            "%d: %s"%(j+1,txt[j]) for j in range(max(0,i-window),min(len(txt),i+window+1)))})
    return {"path":str(path.relative_to(ROOT)),"hit_count":len(idx),"snippets":snippets}
def main():
    manifest=json.loads((M/"v7e-manifest.json").read_text(encoding="utf-8-sig"))
    b=(M/"main.cpp").read_bytes()
    need(manifest["stage"]=="V7E_FIVE_RETAIL_FUNCTIONS_UNIQUE_DISPATCH_SOURCE_ONLY"
         and manifest["source_sha256"]==h(b)
         and manifest["retail_xbe_sha256"]==SHA
         and manifest["remaining_duplicate_cases"]==0,
         "V7E staged baseline drift; refusing unsupported comparison")
    src=b.decode("utf-8",errors="replace")
    # Preserve direct observations, don't assume an import name for ordinal 99.
    evidence=[]
    evidence.append(extract(M/"main.cpp",
         ["80000063","0x63u","0x63:","STORAGE_IO",
          "phase6dq_dispatch_kernel","phase5h_nt_read_file",
          "PHASE4C_BOUNDARY_KERNEL_FRAME","case 0x80000063"],limit=75,window=4))
    k1=ROOT/"ports/mercenaries/xbox360/integration_map/k1"
    roots=[ROOT/"ports/mercenaries/xbox360/phase4c_native_startup",
           ROOT/"ports/mercenaries/xbox360/phase5_subsystem_bringup",
           ROOT/"ports/mercenaries/xbox360/phase6_native_graphics",
           k1]
    files=[]
    # Scope to relevant hand-authored sources rather than hundreds of generated shards.
    for d in roots:
        if d.is_dir():
            for p in d.rglob("*"):
                if p.is_file() and p.suffix.lower() in (".py",".cpp",".h",".ps1",".json"):
                    if p.stat().st_size<=1_500_000:files.append(p)
    # First pass is bounded, source-only. Identify all relevant files; extract
    # just context from strongest hits, retaining exact paths for follow-on.
    matches=[]
    for p in sorted(set(files)):
        t=p.read_text(encoding="utf-8",errors="replace")
        terms=find_patterns(t)
        if terms:
            matches.append({"path":str(p.relative_to(ROOT)),
                            "match_terms":terms})
    preferred=[x for x in matches if "80000063" in x["match_terms"] or
               "ordinal 99" in x["match_terms"] or
               "ordinal_99" in x["match_terms"] or
               "ord 99" in x["match_terms"]]
    for x in preferred[:20]:
        evidence.append(extract(ROOT/x["path"],["80000063","ordinal 99","ordinal_99","ord 99"],limit=15,window=4))
    # Retail caller original x86 disassembly, when present. This is a
    # provenance check only; not a synthetic decoded implementation.
    corpus=ROOT/"build/phase3n_final_abi_scale/analysis/disasm/functions.json"
    retail_entry=None
    if corpus.exists():
        try:
            j=json.loads(corpus.read_text(encoding="utf-8"))
            # Corpus layouts vary; don't pretend an unverified parser found it.
            retail_entry={"present":True,"sha256":h(corpus.read_bytes()),
                          "note":"Available for detailed function-level investigation"}
        except Exception as exc:
            retail_entry={"present":True,"parse_error":str(exc)}
    # Existing hardware artifacts may be from different test versions; do not
    # assert equivalence without actual logs with phase tags.
    report={"stage":"V7F_ORIGINAL_STORAGE_BOUNDARY_SOURCE_PROVENANCE_ONLY",
            "v7e_sha256":h(b),
            "observed":{"boundary":"STORAGE_IO","target":"0x80000063",
                        "caller":ROOTCALL,"ticks":62777793,
                        "7_async_read_successes":True,"display_calls":0},
            "hypothesis":"Kernel import ordinal 0x63 (99) likely; import identity and ABI unverified",
            "retail_original_inventory":retail_entry,
            "matching_source_files":matches,"focused_evidence":evidence,
            "patch_applied":False,"xdk_invoked":False,"xbox_invoked":False,
            "safe_to_bypass_boundary":False}
    OUT.mkdir(parents=True,exist_ok=True)
    target=OUT/"v7f_storage_kernel_source_audit.json"
    target.write_text(json.dumps(report,indent=2)+"\n",encoding="utf-8")
    print("[K1-V7F] VERIFIED V7E SOURCE: "+h(b))
    print("[K1-V7F] HARDWARE STOP: STORAGE_IO target=80000063 caller=0023A3CE tick=62777793")
    print("[K1-V7F] REPO SOURCES MATCHING KERNEL/STORAGE PATTERNS: %d"%len(matches))
    for x in preferred[:12]:
        print("[K1-V7F] DIRECT SOURCE: "+x["path"]+" "+",".join(x["match_terms"]))
    print("[K1-V7F] OUTPUT: "+str(target))
    print("[K1-V7F] READ-ONLY: NO XDK; NO XBOX; NO ABI FENCE BYPASS")
if __name__=="__main__":
    try:main()
    except Exception as e:
        print("[K1-V7F] HARD FENCE: "+str(e),file=sys.stderr);sys.exit(1)
