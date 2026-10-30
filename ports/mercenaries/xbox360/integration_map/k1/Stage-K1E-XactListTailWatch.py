#!/usr/bin/env python3
"""K1E: instrument one original XACTENG list-link site without guest mutations.

K1C hardware observed WRITE32 guest[00041D70] = 01B672D8
and last-tick VA 0027DD0C. K1D original translation shows that
sub_0027DC5B uses [ebx+74] as a list head and stores its old
[head+4] tail's Flink via GUEST_WRITE32(ecx,eax).

This diagnostic logs existing guest-register and already-loaded tail
values before the original store. It does NOT repair guest pointers,
change original guest reads/writes, or bypass the EFEE0EC4 hard fence.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG="K1E-XACT-TAIL-EDGE-20261030"
SOURCE_FILE="translated_029.cpp"
FUNCTION="sub_0027DC5B"
LABEL="loc_0027DD0C: ;"
# All of these occur in order, once in the actual compiled translation.
ANCHOR=(
    "    ecx = GUEST_READ32(edx + 4);\n"
    "    GUEST_WRITE32(eax + 4, ecx);\n"
    "    GUEST_WRITE32(ecx, eax);"
)
PROBE="""    /* K1E-XACT-TAIL-EDGE-20261030: pre-write list-tail forensic sample. */
    {
        static uint32_t k1e_list_edge_visits = 0u;
        ++k1e_list_edge_visits;
        if (k1e_list_edge_visits <= 8u || ecx == 0x00041D70u ||
            (edx + 4u) == 0x00041D70u)
        {
            char k1e_line[320];
            sprintf(k1e_line,
                "K1E XACT LIST PRE: n=%u va=0027DD0C head=%08X tail=%08X node=%08X head_blink_addr=%08X tail_hits_41D70=%u head_hits_41D70=%u ebx=%08X edi=%08X eventcount=%08X esp=%08X",
                (unsigned)k1e_list_edge_visits,
                (unsigned)edx, (unsigned)ecx, (unsigned)eax,
                (unsigned)(edx + 4u),
                (unsigned)(ecx == 0x00041D70u),
                (unsigned)(edx + 4u == 0x00041D70u),
                (unsigned)ebx, (unsigned)edi,
                (unsigned)s_phase6dqXactInitEventCount, (unsigned)g_esp);
            trace(k1e_line);
        }
    }
"""


def sha(data:bytes)->str:
    return hashlib.sha256(data).hexdigest()


def modify(text:str)->str:
    if TAG in text: raise ValueError("K1E already present in target")
    crlf=text.count("\r\n")
    # Reject CRCRLF (from writing CRLF text with Windows newline
    # translation), bare CR, and mixed LF/CRLF. Do not silently
    # normalize generated guest code.
    if text.count("\r")!=crlf or (crlf and crlf!=text.count("\n")):
        raise ValueError("invalid/mixed generated TU line endings (CRCRLF or bare CR)")
    nl="\r\n" if crlf else "\n"
    # Generated TrueTU sources can contain a forward declaration AND
    # a later implementation of the same guest function. Only the
    # implementation with an opening brace owns translated instructions.
    # Requiring exactly one spelling of the function name incorrectly
    # rejected the real K1D-proven translated_029.cpp.
    owner=re.compile(
        r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+"
        +re.escape(FUNCTION)+
        r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
    )
    definitions=list(owner.finditer(text))
    if len(definitions)!=1:
        raise ValueError(
            "expected exactly one XACTENG function BODY, got "
            +str(len(definitions))
        )
    begin=definitions[0].start()
    # The emitted C++ guest function ends at an unindented closing
    # brace. Unlike 'next void sub_' this never mistakes intervening
    # forward declarations for the end of the function.
    closing=re.search(r"(?m)^\}[ \t]*(?:\r?\n|$)",text[definitions[0].end():])
    if closing is None:
        raise ValueError("XACTENG function body has no top-level closing brace")
    end=definitions[0].end()+closing.end()
    body=text[begin:end]
    if body.count(LABEL)!=1 or body.count("PHASE4C_BUDGET_TICK(0x0027DD0Cu);")!=1:
        raise ValueError("XACTENG loc_0027DD0C site missing or duplicated")
    exact=ANCHOR.replace("\n",nl)
    if body.count(exact)!=1:
        raise ValueError("K1D linked-list instruction triple drift")
    # Emit AFTER already-existing tail read, immediately BEFORE the
    # observed write. Preserve all guest instruction statements verbatim.
    start=(
        "    ecx = GUEST_READ32(edx + 4);"+nl
        +"    GUEST_WRITE32(eax + 4, ecx);"
    )
    replacement=start+nl+PROBE.strip("\n").replace("\n",nl)
    body=body.replace(start,replacement,1)
    if body.count(TAG)!=1 or body.count(ANCHOR.split("\n")[-1])!=1:
        raise ValueError("incorrect K1E source replacement shape")
    if body.index("K1E XACT LIST PRE")>body.index("    GUEST_WRITE32(ecx, eax);"):
        raise ValueError("K1E witness must precede original list-tail write")
    return text[:begin]+body+text[end:]


def stage(source:Path,out:Path)->dict:
    source=source.resolve()
    out=out.resolve()
    if source==out or source in out.parents or out in source.parents:
        raise ValueError("source and staged directory must be independent")
    originals=sorted(source.glob("translated_*.cpp"))
    headers=sorted(source.glob("*.h"))
    if len(originals)!=64 or "translated_runtime.h" not in {f.name for f in headers}:
        raise ValueError("expected exactly 64 TrueTUs + translated_runtime.h")
    owner=[p for p in originals if p.name==SOURCE_FILE]
    if len(owner)!=1:
        raise ValueError("K1D proved translated_029.cpp owner missing")
    files=[*originals,*headers]
    hashes={f.name:sha(f.read_bytes()) for f in files}
    patched=modify(owner[0].read_bytes().decode("utf-8")).encode("utf-8")
    names={f.name for f in files}
    if out.exists() and any(out.iterdir()):
        if {f.name for f in out.iterdir()}!=names:
            raise ValueError("staged shard set drift")
        for f in files:
            actual=(out/f.name).read_bytes()
            expected_hash=sha(patched) if f==owner[0] else hashes[f.name]
            if sha(actual)!=expected_hash:
                raise ValueError("staged TrueTU SHA mismatch: "+f.name)
        print("[K1E-XACT] REUSE PASS: 64 staged C++ shards and all headers SHA-identical")
    else:
        out.mkdir(parents=True,exist_ok=True)
        for f in files:
            dest=out/f.name
            if f==owner[0]: dest.write_bytes(patched)
            else: shutil.copy2(f,dest)
    if any(sha(f.read_bytes())!=hashes[f.name] for f in files):
        raise RuntimeError("frozen original shards changed unexpectedly")
    if any(sha((out/f.name).read_bytes()) !=
           (sha(patched) if f==owner[0] else hashes[f.name]) for f in files):
        raise RuntimeError("copied K1E source SHA failure")
    record={
        "status":"STAGED_ONLY_NO_XDK_BUILD",
        "marker":TAG,
        "source_directory":str(source),
        "staged_directory":str(out),
        "original_shards":64,
        "unchanged_shards":63,
        "modified_shards":[SOURCE_FILE],
        "old_owner_sha256":hashes[SOURCE_FILE],
        "staged_owner_sha256":sha(patched),
        "header_count":len(headers),
        "header_shas":{h.name:hashes[h.name] for h in headers},
        "observed_original_store":"GUEST_WRITE32(ecx, eax)",
        "guest_store_statements_changed":0,
        "guest_read_statements_changed":0,
        "guest_register_writes_added":0,
        "unknown_memory_fences":"UNCHANGED",
        "event_source":"XACTENG loc_0027DD0C",
    }
    manifest=out.parent/"k1e-xact-tail-manifest.json"
    manifest.write_text(json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record


def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shards",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    doc=stage(a.shards,a.out)
    print("[K1E-XACT] PASS: only "+doc["modified_shards"][0]+" has forensic telemetry")
    print("[K1E-XACT] PASS: other 63 TU and every generated header byte-for-byte unchanged")
    print("[K1E-XACT] Guest memory reads/stores and hard-fences UNCHANGED")
    print("[K1E-XACT] Manifest="+str(a.out.parent/"k1e-xact-tail-manifest.json"))


if __name__=="__main__":
    main()
