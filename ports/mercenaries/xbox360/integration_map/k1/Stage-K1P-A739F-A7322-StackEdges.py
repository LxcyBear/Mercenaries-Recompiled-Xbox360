#!/usr/bin/env python3
"""K1P: stage host-only return-edge traces inside A739F and A7322.

From K1J's hardware-tested 64-TU stage (including K1E/G/J witnesses),
change only original functions:
  sub_002A739F (translated_009.cpp): all 9 direct callsites.
  sub_002A7322 (translated_057.cpp): 5 nested callsites + A7AE8 tail.
The trace measures caller ESP just before synthetic return push and
after return. Expected delta is argument cleanup (0 or +4).
The A7AE8 tail is special: it receives the existing synthetic return
address, so the expected delta after the tail function is +4.
No guest CPU register writes, guest memory accesses, or fence changes.
"""
from __future__ import annotations
import argparse
import hashlib
import json
import re
import shutil
from pathlib import Path

TAG = "K1P-DSOUND-STACK-EDGE-20261030"
BASE = "K1J-DSOUND-RETURN-EBX-20261030"
OWNER_29 = "translated_029.cpp"
TARGETS = {
    "translated_009.cpp": (
        "sub_002A739F",
        [("002A7322",0,1),("002A70AA",0,1),("002A6FDD",0,1),
         ("002A67E2",0,1),("002A6B98",0,1),("002A6EE9",0,1),
         ("002A6D1A",1,1),("002A77BE",1,2)]
    ),
    "translated_057.cpp": (
        "sub_002A7322",
        [("002A722A",1,1),("002A6C51",1,1),
         ("002A6C88",1,1),("002A6CBF",1,1),("002A6D1A",1,1)]
    ),
}
ENTRY_RE = re.compile(
    r"(?m)^[ \t]*(?:static[ \t]+)?void[ \t]+(sub_[0-9a-fA-F]{8})"
    r"[ \t]*\([ \t]*void[ \t]*\)[ \t]*(?:\r?\n[ \t]*)?\{"
)
END_RE = re.compile(r"(?m)^\}[ \t]*(?:\r?\n|$)")
GUEST_OP = re.compile(
    r"\b(?:phase6ch_apu_(?:read|write)(?:8|16|32|64)|GUEST_(?:READ|WRITE)(?:8|16|32|64))\s*\(",
    re.I)
GUEST_REG_WRITE = re.compile(r"\b(?:eax|ebx|ecx|edx|esi|edi|ebp|esp|g_esp)\s*(?:=|\+=|-=|\+\+|--)")
TAIL = "    g_seh_ebp = ebp; sub_002A7AE8(); return; /* tail jmp 0x002A7AE8 */"


def sha(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def probe(label: str, statement: str, expected_delta: int, nl: str, tail: bool=False) -> str:
    token = "k1p_" + re.sub("[^A-Za-z0-9]", "_",label)
    if tail:
        call = "        g_seh_ebp = ebp; sub_002A7AE8();"
    else:
        call = "        " + statement.strip()
    lines = [
        "    {",
        f"        /* {TAG}: {label}; expected ESP delta={expected_delta} */",
        f"        const uint32_t {token}_before = esp;",
        call,
        f"        const uint32_t {token}_after = esp;",
        f"        static unsigned int {token}_count = 0u;",
        f"        ++{token}_count;",
        f"        const uint32_t {token}_delta = {token}_after - {token}_before;",
        f"        if ({token}_count <= 3u || ({token}_delta != {expected_delta}u && {token}_count <= 16u))",
        "        {",
        "            char k1p_line[240];",
        "            sprintf(k1p_line,",
        f'              "K1P STACK EDGE {label}: n=%u before=%08X after=%08X delta=%08X expected=%08X ebx=%08X esi=%08X edi=%08X",',
        f"              (unsigned){token}_count, (unsigned){token}_before,",
        f"              (unsigned){token}_after, (unsigned){token}_delta,",
        f"              (unsigned){expected_delta}u, (unsigned)ebx,",
        "              (unsigned)esi, (unsigned)edi);",
        "            trace(k1p_line);",
        "        }",
        "    }",
    ]
    if tail:
        lines.append("    return; /* tail jmp 0x002A7AE8 (unchanged guest transfer) */")
    return nl.join(lines)


def modify(filename: str, source: str) -> tuple[str,list[str]]:
    if filename not in TARGETS or TAG in source:
        raise ValueError("Unknown or already-instrumented K1P owner")
    crlf = source.count("\r\n")
    if source.count("\r") != crlf or (crlf and crlf != source.count("\n")):
        raise ValueError("Mixed original C++ line endings")
    nl = "\r\n" if crlf else "\n"
    name,callees = TARGETS[filename]
    entries = [m for m in ENTRY_RE.finditer(source) if m.group(1)==name]
    if len(entries)!=1:
        raise ValueError("Expected exactly one translated implementation of "+name)
    begin = entries[0].start()
    closing=END_RE.search(source,entries[0].end())
    if not closing:
        raise ValueError("Translated function closure missing "+name)
    end=closing.end()
    original=source[begin:end]
    new=original
    ids=[]
    for callee,argc,count in callees:
        call=f"PUSH32(esp, 0); sub_{callee}(); /* call 0x{callee} */"
        if new.count(call)!=count:
            raise ValueError(f"{name} callsite count drift for {callee}: {new.count(call)} vs {count}")
        for index in range(1,count+1):
            label=f"{name[4:].upper()}_{callee}_{index}"
            new=new.replace(call,probe(label,call,argc*4,nl),1)
            ids.append(label)
    if filename=="translated_057.cpp":
        if new.count(TAIL)!=1:
            raise ValueError("Expected one A7322->A7AE8 tail transfer")
        new=new.replace(TAIL,probe("A7322_A7AE8_TAIL",TAIL,4,nl,True),1)
        ids.append("A7322_A7AE8_TAIL")
    if new.count(TAG)!=len(ids):
        raise ValueError("Wrong probe marker count")
    if GUEST_OP.findall(original)!=GUEST_OP.findall(new):
        raise ValueError("Guest read/write instruction sequence changed")
    old_reg = GUEST_REG_WRITE.findall(original)
    new_reg = GUEST_REG_WRITE.findall(new)
    if old_reg!=new_reg:
        raise ValueError("Guest register write sequence changed")
    # Preserve exact original call, push, pop, return-site counts.
    for substring in ("PUSH32(esp, 0); sub_","POP32(esp,","sub_002A7AE8();"):
        if new.count(substring)!=original.count(substring):
            raise ValueError("K1P changed guest control/stack instructions: "+substring)
    return source[:begin]+new+source[end:],ids


def stage(source: Path, source_manifest: Path, k1o_report: Path, out: Path) -> dict:
    source, source_manifest, k1o_report, out = map(
        lambda p:p.resolve(),(source,source_manifest,k1o_report,out))
    if source==out or source in out.parents or out in source.parents:
        raise ValueError("K1P cannot overwrite prior K1J or original TrueTUs")
    doc=json.loads(source_manifest.read_text(encoding="utf-8-sig"))
    report=k1o_report.read_text(encoding="utf-8-sig")
    files=sorted(source.glob("translated_*.cpp"))
    headers=sorted(source.glob("*.h"))
    if (len(files)!=64 or not (source/"translated_runtime.h").is_file()
        or doc.get("marker")!=BASE
        or doc.get("status")!="STAGED_ONLY_NO_XDK_BUILD"
        or doc.get("modified_from_k1g")!=["translated_017.cpp","translated_041.cpp"]
        or doc.get("translated_shards")!=64
        or doc.get("unchanged_from_k1g")!=62
        or doc.get("preserved_k1e_witness") is not True
        or doc.get("preserved_k1g_owner") is not True
        or Path(doc.get("staged_directory","MISSING")).resolve()!=source
        or "K1O READ-ONLY A7322 -> A7AE8 TAIL RETURN CONTRACT" not in report
        or "INLINE_RETURN line=22878 esp_increment=4 arg_cleanup=0" not in report
        or "TAIL_TRANSFER line=25013 next=SUB_002A7AE8" not in report
        or "K1O" not in report):
        raise ValueError("K1P provenance gates failed before source staging")
    all_files=[*files,*headers]
    before={f.name:sha(f) for f in all_files}
    updated={}
    labels=[]
    for filename in TARGETS:
        old=(source/filename).read_bytes().decode("utf-8")
        changed,ids=modify(filename,old)
        updated[filename]=changed.encode("utf-8")
        labels.extend(ids)
    if out.exists() and any(out.iterdir()):
        if {p.name for p in out.iterdir()}!={p.name for p in all_files}:
            raise ValueError("K1P staged file collection drift")
        for item in all_files:
            expected=updated.get(item.name,item.read_bytes())
            if (out/item.name).read_bytes()!=expected:
                raise ValueError("K1P staged source mismatch "+item.name)
        print("[K1P] REUSE PASS: staged TrueTUs/headers identical")
    else:
        out.mkdir(parents=True,exist_ok=True)
        for item in all_files:
            if item.name in updated:
                (out/item.name).write_bytes(updated[item.name])
            else:
                shutil.copy2(item,out/item.name)
    for item in all_files:
        after=out/item.name
        expected=updated.get(item.name,item.read_bytes())
        if after.read_bytes()!=expected or sha(item)!=before[item.name]:
            raise ValueError("K1P source provenance mismatch "+item.name)
    manifest={
        "status":"STAGED_ONLY_NO_XDK_BUILD","marker":TAG,
        "baseline_directory":str(source),"staged_directory":str(out),
        "translated_shards":64,"modified_from_k1j":sorted(TARGETS),
        "unchanged_from_k1j":62,"probe_count":len(labels),
        "probe_labels":labels,
        "guest_memory_ops_added":0,"guest_register_writes_added":0,
        "hard_fences":"UNCHANGED",
        "preserved_k1e_k1g_k1j_watchers":True,
        "changed_owner_hashes":{
            filename:{"original_sha256":before[filename],
                      "staged_sha256":hashlib.sha256(payload).hexdigest()}
            for filename,payload in updated.items()
        }
    }
    manifest_path=out.parent/"k1p-stack-return-edges-manifest.json"
    manifest_path.write_text(json.dumps(manifest,indent=2)+"\n",encoding="utf-8")
    return manifest


def main() -> None:
    p=argparse.ArgumentParser()
    p.add_argument("--k1j-shards",type=Path,required=True)
    p.add_argument("--k1j-manifest",type=Path,required=True)
    p.add_argument("--k1o-report",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    m=stage(a.k1j_shards,a.k1j_manifest,a.k1o_report,a.out)
    print(f"[K1P] STAGING PASS: {m['probe_count']} ESP call-edge probes across 2 new TrueTUs")
    print("[K1P] 62 other TrueTUs and all headers byte-identical to K1J")
    print("[K1P] K1E/G/J witnesses untouched; no new guest memory/CPU mutations")
    print("[K1P] STAGE ONLY (NO XDK build). Manifest="+str(a.out.parent/"k1p-stack-return-edges-manifest.json"))


if __name__=="__main__":
    main()
