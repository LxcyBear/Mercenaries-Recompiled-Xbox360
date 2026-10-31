#!/usr/bin/env python3
"""Read-only retail Mercenaries XPP frontier source/ABI witness.

Reads user-local xboxrecomp inventory + original translated C corpus.
Writes a shareable METADATA report and a separate LOCAL-ONLY SOURCE excerpt.
No Xbox build, guest source modification, new disassembly or fake pixels.
"""
from __future__ import annotations
import argparse
import hashlib
import importlib.util
import json
import re
import zipfile
from pathlib import Path

EXPECTED_SHA="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
FOCUS=(0x002D52D4,0x002D6B3E,0x002D7620,0x002D79B6,
       0x0023A3CE,0x002D5272,0x0028BDB0,0x0020FAE0,0x0010C790)
FUNC=re.compile(r"(?m)^[ \t]*(?:static[ \t]+)?(?:__forceinline[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{")
DIRECT=re.compile(r"\bsub_([0-9A-Fa-f]{8})\s*\(")
HELPER=re.compile(r"\b(recomp_[A-Za-z0-9_]+)\s*\(")

def va(x):
    try: return int(str(x),0)
    except (ValueError,TypeError): return None

def hx(x):
    return "0x%08X"%x

def original_sources(ranges,generated,emitter):
    spec=importlib.util.spec_from_file_location("merc360_original_reader",str(emitter))
    if not spec or not spec.loader:
        raise ValueError("Original generator reader unavailable")
    reader=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(reader)
    _,by_name=reader.load_ranges(ranges)
    sources=reader.load_generated(generated,by_name)
    if len(sources)<10000:
        raise ValueError("Original translated C corpus incomplete")
    return sources,reader

def staged_sources(folder):
    if folder is None or not folder.is_dir():
        return None,"not supplied/absent; current translated coverage UNKNOWN"
    paths=sorted(folder.glob("translated_???.cpp"))
    if len(paths)!=64:
        return None,"not 64 TrueTUs; current translated coverage UNKNOWN"
    result={}
    for path in paths:
        for match in FUNC.finditer(path.read_text(encoding="utf-8",errors="replace")):
            result.setdefault(int(match.group(1),16),[]).append(path.name)
    return result,"source-only TrueTU coverage; deployed XEX NOT verified"

def audit(args):
    for p in (args.recon,args.ranges,args.generated,args.emitter):
        if not p.exists(): raise ValueError("User-local input absent: "+str(p))
    if args.out.resolve()==args.excerpts.resolve():
        raise ValueError("Metadata and local source outputs cannot be the same file")
    with zipfile.ZipFile(args.recon) as z:
        manifest=json.loads(z.read("xboxrecomp_manifest.json"))
        summary=z.read("merc360_frontier_summary.txt").decode("utf-8-sig")
    if (manifest.get("functions")!=16662 or
        manifest.get("no_raw_game_bytes") is not True or EXPECTED_SHA not in summary):
        raise ValueError("Saved static inventory does not prove expected retail XBE")
    originals={va(row["address"]):row for row in manifest["function_list"]}
    if len(originals)!=16662 or 0x002D52D4 not in originals:
        raise ValueError("Incomplete original function inventory")
    sources,reader=original_sources(args.ranges,args.generated,args.emitter)
    stage,status=staged_sources(args.stage_shards)
    lines=[
        "[K1-XPP] ====================================================",
        "[K1-XPP] ORIGINAL XPP D52D4 SOURCE/ABI - NO XDK OR XBOX RUN",
        "[K1-XPP] ====================================================",
        "[K1-XPP] Source function count=%d; original xboxrecomp count=%d"%(len(sources),len(originals)),
        "[K1-XPP] Stage: "+status,
        "[K1-XPP] HARDWARE LAST: DIRECT 0023A3CE -> 002D52D4 tick=27,107,602",
        "[K1-XPP] REAL Swap=0028BDB0 scanned by TGP482; guest display_calls=0",
        "[K1-XPP] Cached metadata is not evidence of a function executing on Xbox.",
        ""
    ]
    private=[
        "LOCAL ONLY: original generated Mercenaries guest code.",
        "NEVER commit this excerpt to GitHub; user owns this private data.",
        ""
    ]
    for at in FOCUS:
        rec=originals.get(at,{})
        source=sources.get(at)
        body=source["source"] if source else ""
        masked=reader.mask_noncode(body) if body else ""
        children=[va(v) for v in rec.get("calls_to",[])]
        callers=[va(v) for v in rec.get("called_by",[])]
        helper_names=sorted(set(HELPER.findall(masked)))
        source_calls=sorted(set(int(v,16) for v in DIRECT.findall(masked))-{at})
        active=stage.get(at,[]) if stage is not None else None
        lines.extend([
            "[K1-XPP] %s section=%s original_size=%s old_pixel_batch=%s"%
                (hx(at),rec.get("section","NOT_FOUND"),rec.get("size","N/A"),
                 rec.get("present_in_pixel_true_tus","UNKNOWN")),
            "    exact_original_generated_body=%s original_source_file=%s"%
                (bool(source),source["file"] if source else "MISSING"),
            "    source_sha256=%s"%(
                hashlib.sha256(body.encode("utf-8")).hexdigest() if body else "NO_BODY"),
            "    staged_true_tus=%s"%(
                "UNKNOWN" if active is None else ",".join(active) if active else "NOT_PRESENT"),
            "    estimated_params=%s abi_heuristic=%s stack_frame_size=%s"%
                (rec.get("estimated_params","UNKNOWN"),
                 rec.get("calling_convention","UNKNOWN"),
                 rec.get("stack_frame_size","UNKNOWN")),
            "    cached_direct_callers=%d old_direct_callees=%s"%
                (len(callers),",".join(hx(v) for v in children if v is not None) or "NONE"),
            "    actual_generated_callees="+(",".join(hx(v) for v in source_calls) or "NONE"),
            "    original_host_helpers="+(",".join(helper_names[:30]) or "NONE"),
            "    source_last_120_chars="+repr(body[-120:] if body else ""),
            ""
        ])
        if at in FOCUS[:4]:
            private.extend(["== ORIGINAL "+hx(at)+" "+
                            (source["file"] if source else "NO_BODY")+" ==",
                            body if body else "MISSING SOURCE BODY",""])
    if 0x002D52D4 not in sources:
        lines.append("[K1-XPP] HARD BLOCK: D52D4 ORIGINAL BODY MISSING; never synthesize it.")
    elif stage is None or 0x002D52D4 not in stage:
        lines.append("[K1-XPP] Next: verify exact source/ABI before staged direct-frontier translation; no fake stubs.")
    else:
        lines.append("[K1-XPP] Next: verify current deployed XEX identity and D52D4 ABI before patching.")
    lines.extend([
        "[K1-XPP] LOCAL-ONLY original XPP source written separately.",
        "[K1-XPP] UNKNOWN VP/MMIO READS: HARD FENCE. No synthetic Swap.",
        "[K1-XPP] END."
    ])
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.excerpts.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text("\n".join(lines)+"\n",encoding="utf-8")
    args.excerpts.write_text("\n".join(private)+"\n",encoding="utf-8")
    print("\n".join(lines))
    print("[K1-XPP] SHAREABLE METADATA="+str(args.out))
    print("[K1-XPP] LOCAL-ONLY GUEST SOURCE="+str(args.excerpts))

def main():
    p=argparse.ArgumentParser()
    p.add_argument("--self-test",action="store_true")
    for key in ("recon","ranges","generated","emitter","stage_shards","out","excerpts"):
        p.add_argument("--"+key.replace("_","-"),type=Path)
    a=p.parse_args()
    if a.self_test:
        assert va("0x002D52D4")==0x002D52D4
        assert FUNC.findall("void sub_002D52D4(void)\n{\n}\n")==["002D52D4"]
        assert DIRECT.findall("sub_002D6B3E();")==["002D6B3E"]
        assert HELPER.findall("recomp_guest_read32(esp);")==["recomp_guest_read32"]
        assert len(FOCUS)==9 and len(set(FOCUS))==len(FOCUS)
        print("[K1-XPP] SELFTEST PASS")
        return
    for key in ("recon","ranges","generated","emitter","out","excerpts"):
        if getattr(a,key) is None: p.error("--"+key.replace("_","-")+" required")
    audit(a)

if __name__=="__main__":
    main()
