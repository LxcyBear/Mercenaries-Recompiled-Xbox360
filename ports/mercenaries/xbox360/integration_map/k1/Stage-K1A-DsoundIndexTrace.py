#!/usr/bin/env python3
"""Stage ONE-shard, read-only K1A DSOUND register/stack ancestry telemetry.

The frozen R76 true-TU shard inputs are never mutated. The output directory
contains copies of all 64 .cpp shards, only one changed. No guest reads or
writes are added: the probe snapshots values already read by original code
and only calls existing host trace/sprintf after existing instruction sites.

No address whitelists, synthetic successful kernel calls or MMIO policy edits.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

FUNCTION="sub_002A6595"
MARK="K1A-DSINDEX-ONE-SHARD-20261029"
REQUIRED=(
 "uint32_t ebp;",
 "    ebx = ecx;",
 "    phase6ch_apu_write32(ebp + -12, eax);",
 "    eax = phase6ch_apu_read32(0x2BB240);\n    phase6ch_apu_write32(ebp + -4, eax);",
 "    esi = ecx + edx * 8;",
 "loc_002A6617: ;",
 "    eax = eax + phase6ch_apu_read32(ebp + 8);",
 "loc_002A6624: ;",
 "    phase6ch_apu_write32(esi + 4, phase6ch_apu_read32(esi + 4) & 0);",
)
DECL="""    /* K1A DSOUND forensic snapshots only: these are host C++ locals. */
    uint32_t k1a_ds_object = 0u;
    uint32_t k1a_ds_end = 0u;
    uint32_t k1a_ds_delta = 0u;
    uint32_t k1a_ds_table = 0u;
    uint32_t k1a_ds_before173_ebx = 0u;
    uint32_t k1a_ds_before173_esi = 0u;
    uint32_t k1a_ds_before173_esp = 0u;
    uint32_t k1a_ds_log_this = 0u;
    static uint32_t k1a_ds_visit_count = 0u;
"""
# All log lines run *outside* guest call argument sequences. Never modify any
# guest register. Existing host trace and sprintf declarations must be present
# in the existing true-TU build environment.
ENTRY="""    k1a_ds_end = edx;
    k1a_ds_delta = eax;
    k1a_ds_object = ebx;
"""
TABLE="""    k1a_ds_table = eax;
    if (++k1a_ds_visit_count <= 4u) {
        char k1a_line[224];
        sprintf(k1a_line,
            "K1A DSINDEX ENTRY: n=%u object=%08X obj_first=%08X obj_second=%08X delta=%08X table=%08X ebp=%08X esp=%08X",
            (unsigned)k1a_ds_visit_count, (unsigned)k1a_ds_object,
            (unsigned)(k1a_ds_delta + k1a_ds_end),
            (unsigned)k1a_ds_end, (unsigned)k1a_ds_delta,
            (unsigned)k1a_ds_table, (unsigned)ebp, (unsigned)g_esp);
        trace(k1a_line);
    }
"""
LEA="""    k1a_ds_log_this = (k1a_ds_visit_count <= 4u || (esi & 0xF0000000u) == 0xE0000000u) ? 1u : 0u;
    if (k1a_ds_log_this) {
        char k1a_line[256];
        sprintf(k1a_line,
            "K1A DSINDEX LEA: object0=%08X object_now=%08X original_delta=%08X local_delta=%08X original_table=%08X local_table=%08X esi=%08X loop_count=%u ebp=%08X esp=%08X",
            (unsigned)k1a_ds_object,(unsigned)ebx,
            (unsigned)k1a_ds_delta,(unsigned)edx,
            (unsigned)k1a_ds_table,(unsigned)ecx,(unsigned)esi,
            (unsigned)eax,(unsigned)ebp,(unsigned)g_esp);
        trace(k1a_line);
    }
"""
PRE="""    k1a_ds_before173_ebx = ebx;
    k1a_ds_before173_esi = esi;
    k1a_ds_before173_esp = g_esp;
    if (k1a_ds_log_this) {
        char k1a_line[224];
        sprintf(k1a_line,
            "K1A DSINDEX PRE173: ebx=%08X esi=%08X ecx=%08X edx=%08X eax=%08X esp=%08X ebp=%08X",
            (unsigned)ebx,(unsigned)esi,(unsigned)ecx,(unsigned)edx,
            (unsigned)eax,(unsigned)g_esp,(unsigned)ebp);
        trace(k1a_line);
    }
"""
POST="""    if (k1a_ds_log_this) {
        char k1a_line[256];
        sprintf(k1a_line,
            "K1A DSINDEX POST173: ebx=%08X was=%08X esi=%08X was=%08X ecx=%08X edx=%08X eax=%08X esp=%08X was=%08X ebp=%08X",
            (unsigned)ebx,(unsigned)k1a_ds_before173_ebx,
            (unsigned)esi,(unsigned)k1a_ds_before173_esi,
            (unsigned)ecx,(unsigned)edx,(unsigned)eax,
            (unsigned)g_esp,(unsigned)k1a_ds_before173_esp,
            (unsigned)ebp);
        trace(k1a_line);
    }
"""

def sha(b:bytes)->str:
    return hashlib.sha256(b).hexdigest()

def modify(text:str)->str:
    if MARK in text:raise ValueError("diagnostic overlay already applied")
    start=re.search(r"(?m)^\s*(?:static\s+)?void\s+sub_002A6595\s*\(\s*void\s*\)\s*\{",text)
    if not start:
        # Some true TU generators put the opening brace on the next line.
        start=re.search(r"(?m)^\s*(?:static\s+)?void\s+sub_002A6595\s*\(\s*void\s*\)\s*\n\s*\{",text)
    if not start:raise ValueError("exact DSOUND function definition not found")
    begin=start.start()
    # Only this function receives forensic telemetry.
    nextfn=re.search(r"(?m)^\s*(?:static\s+)?void\s+sub_[0-9A-Fa-f]{8}\s*\(\s*void\s*\)",text[start.end():])
    stop=start.end()+nextfn.start() if nextfn else len(text)
    body=text[begin:stop]
    # Path.write_text translates LF to CRLF on Windows; real cached TrueTU
    # shards may be CRLF too. Match source-native lines without rewriting
    # or normalizing ANY unmodified guest translation or shard content.
    crlf=body.count("\r\n")
    lf=body.count("\n")
    if crlf and crlf!=lf:
        raise ValueError("mixed source line endings in DSOUND translated body")
    newline="\r\n" if crlf else "\n"
    for fragment in REQUIRED:
        native=fragment.replace("\n",newline)
        if body.count(native)!=1:
            raise ValueError("staged shard source drift/missing exact statement: "+fragment)
    for old,new in (
        ("uint32_t ebp;", "uint32_t ebp;\n"+DECL),
        ("    phase6ch_apu_write32(ebp + -12, eax);",
         "    phase6ch_apu_write32(ebp + -12, eax);\n"+ENTRY),
        ("    eax = phase6ch_apu_read32(0x2BB240);\n    phase6ch_apu_write32(ebp + -4, eax);",
         "    eax = phase6ch_apu_read32(0x2BB240);\n    phase6ch_apu_write32(ebp + -4, eax);\n"+TABLE),
        ("    esi = ecx + edx * 8;", "    esi = ecx + edx * 8;\n"+LEA),
        ("    eax = eax + phase6ch_apu_read32(ebp + 8);",
         "    eax = eax + phase6ch_apu_read32(ebp + 8);\n"+PRE),
        ("loc_002A6624: ;\n    PHASE4C_BUDGET_TICK(0x002A6624u);",
         "loc_002A6624: ;\n    PHASE4C_BUDGET_TICK(0x002A6624u);\n"+POST),
    ):
        native_old=old.replace("\n",newline)
        native_new=new.replace("\n",newline)
        if body.count(native_old)!=1:
            raise ValueError("non-unique insertion point: "+old)
        body=body.replace(native_old,native_new,1)
    body="/* "+MARK+": only guest function "+FUNCTION+" modified */"+newline+body
    return text[:begin]+body+text[stop:]

def stage(source:Path,out:Path)->dict:
    source=source.resolve();out=out.resolve()
    if source==out or source in out.parents or out in source.parents:
        raise ValueError("source and output directories must be independent")
    inputs=sorted(source.glob("translated_*.cpp"))
    if len(inputs)!=64:raise ValueError(f"Expected 64 translated_*.cpp TrueTU source files, got {len(inputs)}")
    # The VS2017 TrueTU builder uses *.h from GeneratedShardDir. Omitting
    # translated_runtime.h caused C1083 in translated_060.cpp. Preserve every
    # source header byte-for-byte, and fail BEFORE XDK if this one is absent.
    headers=sorted(source.glob("*.h"))
    if not any(p.name=="translated_runtime.h" for p in headers):
        raise ValueError("required translated_runtime.h absent from original TrueTU source")
    header_hashes={p.name:sha(p.read_bytes()) for p in headers}
    candidates=[]
    snapshots={}
    for f in inputs:
        data=f.read_bytes()
        snapshots[f.name]=sha(data)
        if re.search(rb"(?m)^\s*(?:static\s+)?void\s+sub_002A6595\s*\(\s*void\s*\)\s*\{",data):
            candidates.append(f)
    if len(candidates)!=1:raise ValueError(f"expected exact ONE shard owning {FUNCTION}; got {len(candidates)}")
    target=candidates[0]
    if out.exists() and any(out.iterdir()):
        # Older one-shard stages copied only .cpp files; the first XDK build
        # then failed when translated_runtime.h was missing. Replay is allowed
        # ONLY after checking all 64 staged cpp byte hashes and every existing
        # header. Supply missing headers from the SAME frozen source.
        manifest=out.parent/"k1a-dsound-index-trace-manifest.json"
        if not manifest.is_file():
            raise ValueError("nonempty stage dir has no forensic manifest")
        doc=json.loads(manifest.read_text(encoding="utf-8"))
        expected_names={p.name for p in inputs}
        expected_header_names={p.name for p in headers}
        actual_names={p.name for p in out.iterdir()}
        if (doc.get("marker")!=MARK or
            doc.get("status")!="STAGED_ONLY_NO_XDK_BUILD" or
            doc.get("modified_shards")!=[target.name] or
            doc.get("original_modified_shard_sha256")!=snapshots[target.name] or
            doc.get("source_directory")!=str(source) or
            doc.get("staged_directory")!=str(out) or
            not expected_names.issubset(actual_names) or
            not actual_names.issubset(expected_names|expected_header_names) or
            doc.get("staged_modified_shard_sha256")!=
              sha(modify(target.read_bytes().decode("utf-8")).encode("utf-8"))):
            raise ValueError("staged output identity mismatch or stale mixed shards")
        old_headers=doc.get("header_sha256")
        if old_headers is not None and old_headers!=header_hashes:
            raise ValueError("frozen header identities changed since original stage")
        for f in inputs:
            actual=sha((out/f.name).read_bytes())
            if actual!=(doc["staged_modified_shard_sha256"] if f==target else snapshots[f.name]):
                raise ValueError("staged TrueTU content drift: "+f.name)
        for f in headers:
            dest=out/f.name
            if dest.exists() and sha(dest.read_bytes())!=header_hashes[f.name]:
                raise ValueError("staged runtime header drift: "+f.name)
        copied=0
        for f in headers:
            dest=out/f.name
            if not dest.exists():
                shutil.copy2(f,dest)
                copied+=1
            if sha(dest.read_bytes())!=header_hashes[f.name]:
                raise RuntimeError("staged runtime header copy failed: "+f.name)
        for f in headers:
            if sha(f.read_bytes())!=header_hashes[f.name]:
                raise RuntimeError("original runtime header mutated: "+f.name)
        doc["header_sha256"]=header_hashes
        doc["header_count"]=len(headers)
        doc["auxiliary_headers"]=sorted(header_hashes)
        manifest.write_text(json.dumps(doc,indent=2)+"\n",encoding="utf-8")
        print(f"[K1A-DSINDEX] REUSE PASS: 64 staged cpp hashes + {len(headers)} header SHA(s); restored={copied}")
        return doc
    out.mkdir(parents=True,exist_ok=True)
    changed=[]
    for f in inputs:
        data=f.read_bytes()
        if f==target:
            patched=modify(data.decode("utf-8")).encode("utf-8")
            (out/f.name).write_bytes(patched)
            changed.append(f.name)
        else:
            shutil.copy2(f,out/f.name)
    if len(changed)!=1:raise AssertionError("expected one modified shard")
    for f in headers:
        shutil.copy2(f,out/f.name)
        if sha((out/f.name).read_bytes())!=header_hashes[f.name]:
            raise RuntimeError("staged runtime header SHA mismatch: "+f.name)
    for f in headers:
        if sha(f.read_bytes())!=header_hashes[f.name]:
            raise RuntimeError("original runtime header mutated: "+f.name)
    for f in inputs:
        if sha(f.read_bytes())!=snapshots[f.name]:
            raise RuntimeError("frozen TrueTU input was unexpectedly modified: "+f.name)
        if f!=target and sha((out/f.name).read_bytes())!=snapshots[f.name]:
            raise RuntimeError("copied unmodified shard SHA mismatch: "+f.name)
    record={"status":"STAGED_ONLY_NO_XDK_BUILD","marker":MARK,
            "original_shards":64,"modified_shards":changed,
            "original_modified_shard_sha256":snapshots[target.name],
            "staged_modified_shard_sha256":sha((out/target.name).read_bytes()),
            "unchanged_shards":63,"hard_fences":"PRESERVED",
            "header_count":len(headers),"header_sha256":header_hashes,
            "auxiliary_headers":sorted(header_hashes),
            "guest_register_writes_added":0,
            "source_directory":str(source),"staged_directory":str(out)}
    (out.parent/"k1a-dsound-index-trace-manifest.json").write_text(
        json.dumps(record,indent=2)+"\n",encoding="utf-8")
    return record

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--shards",required=True,type=Path)
    p.add_argument("--out",required=True,type=Path)
    args=p.parse_args()
    m=stage(args.shards,args.out)
    print("[K1A-DSINDEX] PASS: only "+m["modified_shards"][0]+" instrumented")
    print(f"[K1A-DSINDEX] 63 other TrueTU .cpp files SHA-identical; {m['header_count']} header(s) byte-identical")
    print("[K1A-DSINDEX] R76 originals, K1A XEX and guest fences UNCHANGED")
    print("[K1A-DSINDEX] Stage only: NO XDK compilation; report="+str(args.out.parent/"k1a-dsound-index-trace-manifest.json"))

if __name__=="__main__":main()
