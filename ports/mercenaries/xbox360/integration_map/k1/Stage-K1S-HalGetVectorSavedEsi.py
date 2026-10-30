#!/usr/bin/env python3
"""K1S: guarded one-TU correction of Xbox-proven ordinal-44 saved ESI slot.

K1R hardware directly proved:
  A7B73 HALGETVECTOR44/ICALL_2 returns ESP=008BF880, unchanged.
  A7B73 EBP=008BF888, ESP should remain EBP-12=008BF87C
  because the preceding PUSH32(esp, esi) is balanced by the later
  POP32(esp, esi) at loc_002A7C49.
  The incorrect EBP-8 instead slides all remaining POP32 restores;
  A6B98->A7B73 then returns ESP +8 vs +4 and EBX=008BFF8C.
This narrow caller-edge repair executes only after ordinal-44's
HALGETVECTOR call, only when ESP matches the proven extra-pop shape.
It does NOT patch the kernel handler globally. All guest MMIO/VP
hard fences, guest reads/writes and other 63 TrueTUs stay unchanged.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG="K1S-HALGETVECTOR44-SAVED-ESI-20261030"
BASE="K1R-A6B98-A7B73-STACK-PATH-20261030"
OWNER="translated_044.cpp"
FUNCTION="sub_002A7B73"
ENTRY=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+sub_002A7B73"
                 r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{")
END=re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
MEM=re.compile(r"\b(?:phase6ch_apu_(?:read|write)|GUEST_(?:READ|WRITE))(?:8|16|32|64|128)\s*\(",re.I)
CALL=re.compile(r"\bsub_[0-9a-fA-F]{8}\s*\(\s*\)")
ICALL=re.compile(r"\bPHASE6DJ_ICALL_SAFE\s*\(")
PUSHPOP=re.compile(r"\b(?:PUSH32|POP32)\s*\(")

INJECTION="""    /* K1S-HALGETVECTOR44-SAVED-ESI-20261030:
       K1R Xbox: ordinal 44 cleanup returns EBP-8 even though
       PUSH ESI at 002A7BD1 must remain on the stack until its
       matching POP ESI at 002A7C49. This code path ran on
       hardware with EBP=008BF888, ESP=008BF880. Strictly
       correct only that precise one-word over-cleaned slot.
       No guest memory reads/writes or global kernel changes. */
    {
        const uint32_t k1s_raw_esp = esp;
        const uint32_t k1s_saved_esi_slot = ebp - 12u;
        const bool k1s_exact_drift = (k1s_raw_esp == ebp - 8u);
        if (k1s_exact_drift)
            esp = k1s_saved_esi_slot;
        static uint32_t k1s_hits = 0u;
        ++k1s_hits;
        if (k1s_hits <= 4u || !k1s_exact_drift)
        {
            char k1s_line[256];
            sprintf(k1s_line,
                "K1S HALGETVECTOR44 ESI SLOT: n=%u ebp=%08X raw_esp=%08X expected_esp=%08X repaired=%u final_esp=%08X esi=%08X ebx=%08X",
                (unsigned)k1s_hits, (unsigned)ebp,
                (unsigned)k1s_raw_esp, (unsigned)k1s_saved_esi_slot,
                (unsigned)k1s_exact_drift, (unsigned)esp,
                (unsigned)esi, (unsigned)ebx);
            trace(k1s_line);
        }
    }
"""


def checksum(p:Path)->str:
    return hashlib.sha256(p.read_bytes()).hexdigest()


def modify(source:str)->str:
    if TAG in source:
        raise ValueError("K1S already staged; refusing double correction")
    crlf=source.count("\r\n")
    if source.count("\r")!=crlf or (crlf and crlf!=source.count("\n")):
        raise ValueError("K1S original TrueTU has inconsistent line endings")
    nl="\r\n" if crlf else "\n"
    entries=list(ENTRY.finditer(source))
    if len(entries)!=1:
        raise ValueError("K1S expected one original A7B73 function definition")
    close=END.search(source,entries[0].end())
    if not close:
        raise ValueError("K1S original A7B73 source function not closed")
    a,b=entries[0].start(),close.end()
    original=source[a:b]
    if original.count("loc_002A7BD1: ;")!=1 or original.count("loc_002A7BDE: ;")!=1:
        raise ValueError("K1S call path labels changed")
    lo=original.index("loc_002A7BD1: ;")
    hi=original.index("loc_002A7BDE: ;")
    if lo>=hi:
        raise ValueError("K1S ordinal call region order changed")
    region=original[lo:hi]
    required=(
        "PUSH32(esp, esi);",
        "PUSH32(esp, eax);",
        "PUSH32(esp, 6);",
        "phase6ch_apu_read32(0x2DBE20)",
        "PHASE6DJ_ICALL_SAFE(",
        "K1R ICALL A7B73_ICALL_2",
        "const uint32_t k1r_A7B73_ICALL_2_before=esp;",
        "const uint32_t k1r_A7B73_ICALL_2_after=esp;",
    )
    if any(region.count(item)!=1 for item in required):
        raise ValueError("K1S ordinal 44 / K1R witness contract differs")
    if original.count("    POP32(esp, esi);")!=1 or original.count(
        "    esp += 8; return; /* ret 4 */")!=1:
        raise ValueError("K1S original ESI return contract differs")
    if original.index("    POP32(esp, esi);")<=hi:
        raise ValueError("K1S original POP ESI must occur after kernel call")
    if not all(x in original for x in (
        "K1R PATH A7B73_BEFORE_POP_ESI",
        "K1R PATH A7B73_BEFORE_POP_EDI",
        "K1R PATH A7B73_BEFORE_RET4"
    )):
        raise ValueError("K1S prior K1R path probes missing")
    anchor="loc_002A7BDE: ;"
    amended=original.replace(anchor,INJECTION.replace("\n",nl)+anchor,1)
    if amended.count(TAG)!=1 or amended.count("esp = k1s_saved_esi_slot;")!=1:
        raise ValueError("K1S inserted no unique caller-specific ESP correction")
    if amended.count("K1R ICALL ")!=original.count("K1R ICALL "):
        raise ValueError("K1S changed K1R raw indirect call witness")
    for expression,description in ((MEM,"guest memory"),(CALL,"direct calls"),
                                   (ICALL,"indirect calls"),(PUSHPOP,"guest stack")):
        if expression.findall(amended)!=expression.findall(original):
            raise ValueError("K1S accidentally changed "+description)
    if amended.count("esp += 8; return; /* ret 4 */")!=original.count(
        "esp += 8; return; /* ret 4 */"):
        raise ValueError("K1S changed return ABI")
    if amended.index("esp = k1s_saved_esi_slot;") < amended.index(
        "K1R ICALL A7B73_ICALL_2"):
        raise ValueError("K1S cannot adjust ESP before raw K1R evidence")
    return source[:a]+amended+source[b:]


def stage(baseline:Path, manifest:Path, k1q:Path, out:Path)->dict:
    baseline,manifest,k1q,out=(p.resolve() for p in (baseline,manifest,k1q,out))
    if (baseline==out or baseline in out.parents or out in baseline.parents
        or out in {manifest,k1q}):
        raise ValueError("K1S cannot overwrite K1R or a source report")
    doc=json.loads(manifest.read_text(encoding="utf-8-sig"))
    if (doc.get("marker")!=BASE or doc.get("status")!="STAGED_ONLY_NO_XDK_BUILD"
        or doc.get("translated_shards")!=64
        or doc.get("modified_from_k1p")!=["translated_005.cpp","translated_044.cpp"]
        or doc.get("probe_count")!=21 or doc.get("unchanged_from_k1p")!=62
        or doc.get("preserved_k1p_k1j_k1g_k1e_watchers") is not True
        or doc.get("hard_fences")!="UNCHANGED"
        or doc.get("guest_memory_ops_added")!=0
        or Path(doc.get("staged_directory","MISSING")).resolve()!=baseline):
        raise ValueError("K1S K1R staged source provenance gate failed")
    report=k1q.read_text(encoding="utf-8-sig")
    if not all(x in report for x in (
        "K1Q READ-ONLY DSOUND A6B98 FIRST CORRUPTED RETURN CHILD AUDIT",
        "### SUB_002A7B73 owner=translated_044.cpp first=21121 last=21290",
        "Lexical mismatch suspects=none",
        "    PUSH32(esp, esi);",
        "    POP32(esp, esi);"
    )):
        raise ValueError("K1S K1Q original source report differs")
    cpp=sorted(baseline.glob("translated_*.cpp"))
    headers=sorted(baseline.glob("*.h"))
    originals=[*cpp,*headers]
    if len(cpp)!=64 or not any(p.name=="translated_runtime.h" for p in headers):
        raise ValueError("K1S requires exactly 64 TrueTUs and header")
    old=baseline/OWNER
    identity=doc.get("owner_hashes",{}).get(OWNER,{})
    if (checksum(old)!=identity.get("staged_sha256")
        or identity.get("original_sha256")==identity.get("staged_sha256")):
        raise ValueError("K1S original K1R owner SHA mismatch")
    payload=modify(old.read_bytes().decode("utf-8")).encode("utf-8")
    unchanged=[p for p in originals if p.name!=OWNER]
    if out.exists() and any(out.iterdir()):
        if {p.name for p in out.iterdir()}!={p.name for p in originals}:
            raise ValueError("K1S existing staged output file set differs")
        for p in originals:
            expected=payload if p.name==OWNER else p.read_bytes()
            if (out/p.name).read_bytes()!=expected:
                raise ValueError("K1S stale output or changed baseline "+p.name)
        print("[K1S] REUSE PASS: existing stage SHA-identical")
    else:
        out.mkdir(parents=True,exist_ok=True)
        for p in originals:
            if p.name==OWNER:
                (out/p.name).write_bytes(payload)
            else:
                shutil.copy2(p,out/p.name)
    if any((out/p.name).read_bytes()!=p.read_bytes() for p in unchanged):
        raise ValueError("K1S modified non-owner TrueTU or header")
    if (out/OWNER).read_bytes()!=payload:
        raise ValueError("K1S owner staged SHA differs")
    record={
        "status":"STAGED_ONLY_NO_XDK_BUILD","marker":TAG,
        "baseline_directory":str(baseline),"staged_directory":str(out),
        "translated_shards":64,"modified_from_k1r":[OWNER],
        "unchanged_from_k1r":63,"guest_memory_ops_added":0,
        "guest_register_writes_added":1,
        "guest_register_write":"conditional ESP=EBP-12 iff ESP=EBP-8 after ordinal 44",
        "hard_fences":"UNCHANGED",
        "preserved_k1r_k1p_k1j_k1g_k1e_watchers":True,
        "original_owner_sha256":checksum(old),
        "staged_owner_sha256":hashlib.sha256(payload).hexdigest()
    }
    manifest_path=out.parent/"k1s-halgetvector44-saved-esi-manifest.json"
    manifest_path.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record


def main()->None:
    parser=argparse.ArgumentParser()
    parser.add_argument("--k1r-shards",required=True,type=Path)
    parser.add_argument("--k1r-manifest",required=True,type=Path)
    parser.add_argument("--k1q-report",required=True,type=Path)
    parser.add_argument("--out",required=True,type=Path)
    opts=parser.parse_args()
    result=stage(opts.k1r_shards,opts.k1r_manifest,opts.k1q_report,opts.out)
    print("[K1S] STAGING PASS: one guarded A7BD1 ordinal-44 saved ESI slot correction")
    print("[K1S] Only translated_044.cpp modified, 63 unchanged TrueTUs + headers")
    print("[K1S] All K1R/P/J/G/E diagnostics, memory ops and hard fences unchanged")
    print("[K1S] Guest ESP adjustment is conditional; diagnostic-only correction")
    print("[K1S] No XDK build; manifest="+str(opts.out.parent/"k1s-halgetvector44-saved-esi-manifest.json"))


if __name__=="__main__":
    main()
