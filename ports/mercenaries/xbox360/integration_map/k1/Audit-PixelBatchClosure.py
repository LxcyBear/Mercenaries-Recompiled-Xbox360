#!/usr/bin/env python3
"""Read-only LIVE-frontier-first multi-root planning for first genuine display call.

K1S Xbox 2026-10-30:
  Fixed ordinal-44 ESI slot. A7B73 delta +4 (correct), A6B98 delta 0
  (correct), FC4A EBX restored. No GUEST_FAULT; stopped at genuine
  DIRECT_FRONTIER 0x002A3A5A after 27,031,807 translated ticks.
  Native Xenos is alive, guest AvSetDisplayMode calls=0, framebuffer=0.
This tool does NOT invent display calls, skip audio, relax MMIO fences,
rewrite guest code, or trigger the XDK. It inventories potential batches
using original generated source, current K1S 64-TU baseline, and
functions.json, with source-level support screening before a build.
"""
from __future__ import annotations

import argparse
import bisect
import collections
import hashlib
import importlib.util
import json
import re
from pathlib import Path

MARKER="PIXEL-BATCH-ROOTED-CLOSURE-20261030"
K1S="K1S-HALGETVECTOR44-SAVED-ESI-20261030"
LIVE=0x002A3A5A
ROOTS=(
    ("LIVE_DSOUND",LIVE,112),
    ("PRESENT_ROOT",0x0023A3CE,80),
    ("D3D_DEVICE",0x0028E700,64),
    ("D3D_INIT",0x00290895,64),
    ("XGRPH",0x0029C8BE,64),
)
DECL=re.compile(r"\b(?:static\s+)?void\s+(sub_[0-9a-fA-F]{8})\s*\(\s*void\s*\)\s*\{")
DIRECT=re.compile(r"\bsub_([0-9a-fA-F]{8})\s*\(\s*\)")
EXPLICIT=re.compile(r"/\*\s*call\s+0x([0-9a-fA-F]{8})\s*\*/")
LABEL=re.compile(r"\bloc_([0-9a-fA-F]{8})\s*:\s*;")
SHARD_SOURCE=re.compile(r"^translated_\d{3}\.cpp$")


def sha(path:Path)->str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def import_module(path:Path,name:str):
    spec=importlib.util.spec_from_file_location(name,str(path))
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load repo's existing translator support {path}")
    m=importlib.util.module_from_spec(spec)
    spec.loader.exec_module(m)
    return m


def parse_targets(src:str)->list[int]:
    # Only direct translated calls (no inferred indirect targets).
    names={int(s,16) for s in DIRECT.findall(src)}
    names.update(int(s,16) for s in EXPLICIT.findall(src))
    return sorted(names)


def find_enclosing(target:int, starts:list[int], by_va:dict)->dict|None:
    idx=bisect.bisect_right(starts,target)-1
    if idx<0:
        return None
    row=by_va[starts[idx]]
    return row if row["start"]<=target<row["end"] else None


def breadth_first(root:int,budget:int,generated:dict,existing:set[int])->dict[int,int]:
    result={root:0}
    todo=collections.deque([root])
    while todo and len(result)<budget:
        va=todo.popleft()
        entry=generated.get(va)
        if entry is None:
            continue
        for child in parse_targets(entry["source"]):
            if child not in result:
                result[child]=result[va]+1
                if len(result)>=budget:
                    break
                todo.append(child)
    return result


def safe_preview(va:int,generated:dict,base,p5bb,packed:set[int],
                 supplied:set[str])->dict:
    if va not in generated:
        return {"source_supported":False,"status":"NO_ORIGINAL_GENERATED_BODY"}
    obj=generated[va]
    try:
        code=base.localize_and_instrument(obj["source"],obj["name"])
        code,frontiers=p5bb.rewrite_direct_frontier(
            base,code,generated,packed)
        calls=set(base.CALL_RE.findall(base.mask_noncode(code)))
        definitions=set(base.DEFINE_RE.findall(code))
        unknown=sorted(calls-supplied-definitions)
        return {
            "source_supported":not unknown,
            "status":"LEXICAL_SUPPORT_CLEAN" if not unknown
                     else "REQUIRES_SUPPORT",
            "unknown_helper_symbols":unknown[:20],
            "external_direct_frontiers":[f"0x{n:08X}" for n in frontiers[:30]],
            "source_file":obj["file"],
            "direct_callees":[f"0x{v:08X}" for v in parse_targets(obj["source"])[:40]],
        }
    except Exception as exc:
        return {"source_supported":False,"status":"RENDER_REVIEW",
                "reason":str(exc)[:250]}


def audit(a:argparse.Namespace)->dict:
    work=a.shards.resolve()
    manifest=a.manifest.resolve()
    main=a.main.resolve()
    for p in (manifest,main,a.functions,a.generated_root,a.base_emitter,
              a.phase5bb_emitter):
        if not p.exists():
            raise ValueError("Missing required locally generated source: "+str(p))
    doc=json.loads(manifest.read_text(encoding="utf-8-sig"))
    if (doc.get("marker")!=K1S or
        doc.get("status")!="STAGED_ONLY_NO_XDK_BUILD" or
        doc.get("translated_shards")!=64 or
        doc.get("unchanged_from_k1r")!=63 or
        doc.get("modified_from_k1r")!=["translated_044.cpp"] or
        doc.get("hard_fences")!="UNCHANGED" or
        Path(doc.get("staged_directory","MISSING")).resolve()!=work):
        raise ValueError("K1S identity/unchanged hard-fence source gate failed")
    files=sorted(p for p in work.iterdir() if SHARD_SOURCE.fullmatch(p.name))
    if len(files)!=64 or not (work/"translated_runtime.h").is_file():
        raise ValueError("Need exactly 64 K1S TrueTU shards and runtime header")
    if sha(work/"translated_044.cpp")!=doc.get("staged_owner_sha256"):
        raise ValueError("K1S corrected owner SHA mismatch")
    original_vas=set()
    owner_count={}
    for p in files:
        source=p.read_text(encoding="utf-8")
        owner_count[p.name]=len(DECL.findall(source))
        original_vas.update(int(name[4:],16) for name in DECL.findall(source))
    if len(original_vas)<12000:
        raise ValueError("K1S TrueTU inventory unexpectedly incomplete")
    base=import_module(a.base_emitter,"pixel_batch_base")
    p5bb=import_module(a.phase5bb_emitter,"pixel_batch_p5bb")
    by_va,by_name=base.load_ranges(a.functions)
    generated=base.load_generated(a.generated_root,by_name)
    if len(generated)<10000:
        raise ValueError("Generated translator corpus incomplete")
    starts=sorted(by_va)
    if LIVE in original_vas:
        raise ValueError("New DIRECT_FRONTIER already exists in the K1S translated body inventory")
    roots={}
    prospective={}
    for label,root,budget in ROOTS:
        walk=breadth_first(root,budget,generated,original_vas)
        roots[label]={
            "root":f"0x{root:08X}",
            "nodes_scanned":len(walk),
            "already_packed":sum(v in original_vas for v in walk),
            "exact_generated":sum(v in generated for v in walk),
            "missing_generated":sum(v not in generated for v in walk),
        }
        for va,depth in walk.items():
            row=prospective.setdefault(va,{"va":f"0x{va:08X}",
                              "root_reachability":[],"min_depth":depth})
            row["root_reachability"].append(label)
            row["min_depth"]=min(row["min_depth"],depth)
    # Always include the exact hardware-fenced target, regardless of root walk.
    prospective.setdefault(LIVE,{"va":f"0x{LIVE:08X}",
                  "root_reachability":["LIVE_DSOUND"],"min_depth":0})
    preferred=sorted(
        (v for v in prospective if v not in original_vas),
        key=lambda v:(
            0 if v==LIVE else 1 if "LIVE_DSOUND" in prospective[v]["root_reachability"] else 2,
            prospective[v]["min_depth"],v
        )
    )[:a.max_candidates]
    # These are screen candidates, NOT a verified compile-ready pack.
    planned=set(preferred)|original_vas
    main_text=main.read_text(encoding="utf-8")
    provided=set(base.support_symbols(main_text))
    provided.update(base.support_symbols((work/"translated_runtime.h").read_text(encoding="utf-8")))
    provided.update(base.STANDARD_CALLS)
    provided.update("sub_%08X"%n for n in planned)
    records=[]
    for va in preferred:
        parent=find_enclosing(va,starts,by_va)
        row=prospective[va]
        state=safe_preview(va,generated,base,p5bb,planned,provided)
        records.append({
            **row,
            "classification":("EXACT_GENERATED_FUNCTION" if va in generated
                 else "MID_FUNCTION_OR_UNTRANSLATED" if parent is not None
                 else "NO_FUNCTION_RANGE"),
            "containing_function":(
                {"va":f"0x{parent['start']:08X}",
                 "end":f"0x{parent['end']:08X}",
                 "name":parent["name"],
                 "generated":parent["start"] in generated,
                 "label_present":bool(parent["start"] in generated and
                    f"loc_{va:08X}" in generated[parent["start"]]["source"])
                } if parent is not None else None),
            **state
        })
    exact=sum(x["classification"]=="EXACT_GENERATED_FUNCTION" for x in records)
    clean=sum(x["status"]=="LEXICAL_SUPPORT_CLEAN" for x in records)
    unresolved=[x for x in records if not x["source_supported"]]
    state={
        "marker":MARKER,
        "intent":"AUTHENTIC_GUEST_DISPLAY_CALL_ONLY",
        "status":"OFFLINE_SOURCE_AUDIT_NOT_BUILD_READY",
        "hardware_seed":{
            "k1s_four_byte_stack_repair":"PASS_ON_XBOX",
            "first_unhandled_direct_target":f"0x{LIVE:08X}",
            "translated_ticks":27031807,
            "guest_display_calls":0,
            "guest_framebuffer":"0x00000000",
            "hard_fences_relaxed":False,
        },
        "verified_baseline":{
            "marker":doc["marker"],
            "shards":len(files),
            "packed_function_bodies":len(original_vas),
            "generated_source_bodies":len(generated),
            "original_owner_sha":doc.get("original_owner_sha256"),
            "corrected_owner_sha":doc.get("staged_owner_sha256"),
        },
        "roots":roots,
        "selected_candidate_count":len(records),
        "exact_source_candidate_count":exact,
        "lexical_support_clean_count":clean,
        "needs_source_or_support_count":len(unresolved),
        "frontier":next((x for x in records if x["va"]==f"0x{LIVE:08X}"),None),
        "candidate_order":records,
        "build_decision":(
            "FULL_BATCH_REQUIRES_REVIEW: never call unsupported or mid-function "
            "targets compiled, and never change display_calls without a real guest "
            "AvSetDisplayMode/guest presentation. Reuse 64 K1S TUs for incremental "
            "build after trusted function additions are proven."
        ),
        "retail_game_bytes_included":False
    }
    return state


def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--shards",type=Path,required=True)
    p.add_argument("--manifest",type=Path,required=True)
    p.add_argument("--main",type=Path,required=True)
    p.add_argument("--generated-root",type=Path,required=True)
    p.add_argument("--functions",type=Path,required=True)
    p.add_argument("--base-emitter",type=Path,required=True)
    p.add_argument("--phase5bb-emitter",type=Path,required=True)
    p.add_argument("--max-candidates",type=int,default=192)
    p.add_argument("--out",type=Path,required=True)
    a=p.parse_args()
    if not 16<=a.max_candidates<=512:
        raise SystemExit("[PIXEL] max-candidates must be 16..512")
    if (a.out.resolve() in {a.manifest.resolve(),a.main.resolve(),
        a.functions.resolve()} or a.shards.resolve() in a.out.resolve().parents
        or a.generated_root.resolve() in a.out.resolve().parents):
        raise SystemExit("[PIXEL] report output cannot overwrite source")
    payload=audit(a)
    a.out.parent.mkdir(parents=True,exist_ok=True)
    a.out.write_text(json.dumps(payload,indent=2)+"\n",encoding="utf-8")
    x=payload["frontier"]
    print("[PIXEL] SOURCE AUDIT PASS: K1S 64 TrueTUs, code bodies and hard fences verified")
    print("[PIXEL] LIVE 002A3A5A: "+str(x["classification"] if x else "NOT_IN_PLAN"))
    if x:
        print("[PIXEL] Live target source support: "+x["status"])
        if x.get("unknown_helper_symbols"):
            print("[PIXEL] Unknown helpers: "+", ".join(x["unknown_helper_symbols"][:8]))
    print("[PIXEL] Multi-root candidates=%u, exact generated=%u, lexical clean=%u, source/support review=%u"%(
        payload["selected_candidate_count"],payload["exact_source_candidate_count"],
        payload["lexical_support_clean_count"],payload["needs_source_or_support_count"]))
    print("[PIXEL] NO XDK BUILD; no retail bytes; no guest patches; display_calls stays honest")
    print("[PIXEL] REPORT="+str(a.out))


if __name__=="__main__":
    main()
