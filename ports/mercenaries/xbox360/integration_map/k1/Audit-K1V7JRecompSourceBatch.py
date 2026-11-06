#!/usr/bin/env python3
"""K1-V7J: batch offline frontier inventory across retail, xboxrecomp and TrueTUs.

Read-only. Accepts local xboxrecomp analysis zip (16,662 original functions),
generated-C range metadata, and 64 staged TrueTUs. No guessed implementations,
no guest bytes in shareable metadata; no XDK, Xbox, or tick mining.
"""
from __future__ import annotations
import argparse,hashlib,importlib.util,json,re,sys,zipfile
from collections import deque
from pathlib import Path
RETAIL="AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7"
# Observed hardware path + graphics/audio completion roots.
SEEDS=(0x0023A3CE,0x0022F5A7,0x0022F51C,0x0028BDB0,
       0x0028A530,0x0028CAA0,0x00289E20,0x0027DB5C,
       0x00280141,0x002D54AC)
FUNC=re.compile(r'(?m)^[ \t]*(?:static[ \t]+)?(?:__forceinline[ \t]+)?void[ \t]+sub_([0-9A-Fa-f]{8})[ \t]*\([ \t]*void[ \t]*\)\s*\{')
CALL=re.compile(r'\bsub_([0-9A-Fa-f]{8})\s*\(')
def hx(v):return "0x%08X"%v
def number(v):
    try:return int(str(v),0)
    except (TypeError,ValueError):return None
def need(v,msg):
    if not v:raise ValueError(msg)
def imported(p):
    spec=importlib.util.spec_from_file_location("v7j_reader",p)
    need(spec and spec.loader,"Existing reader not importable")
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module
def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--recon",type=Path,help="optional local xboxrecomp inventory zip")
    ap.add_argument("--ranges",required=True,type=Path,help="generated-C metadata range file")
    ap.add_argument("--generated",required=True,type=Path,help="original generated C folder")
    ap.add_argument("--emitter",required=True,type=Path,help="original load_ranges/load_generated reader")
    ap.add_argument("--shards",required=True,type=Path,help="64 TrueTU folder")
    ap.add_argument("--current-main",required=True,type=Path,help="V7I verified generated main.cpp")
    ap.add_argument("--current-manifest",required=True,type=Path,help="V7I source manifest")
    ap.add_argument("--out",type=Path,default=Path("build/phase6_integration_map/k1_v7j_source_batch"))
    ap.add_argument("--depth",type=int,default=3)
    ap.add_argument("--cap",type=int,default=400)
    args=ap.parse_args()
    need(1<=args.depth<=5 and 10<=args.cap<=2000,"Unsupported graph budget")
    reader=imported(args.emitter)
    verified_ranges,by_name=reader.load_ranges(args.ranges)
    need(len(verified_ranges)>=13000,"Original disassembly function range inventory incomplete")
    if args.recon is not None:
        with zipfile.ZipFile(args.recon) as z:
            manifest=json.loads(z.read("xboxrecomp_manifest.json"))
            summary=z.read("merc360_frontier_summary.txt").decode("utf-8-sig")
        need(manifest.get("functions")==16662 and manifest.get("no_raw_game_bytes") is True and
             RETAIL in summary,"Wrong/incomplete retail xboxrecomp inventory")
        inventory={number(row.get("address")):row for row in manifest["function_list"]}
        need(len(inventory)==16662,"Incomplete cached xboxrecomp inventory")
        provenance="xboxrecomp_zip_verified_retail_summary"
    else:
        # Existing original disassembler inventory is a different artifact:
        # it has range metadata, not all xboxrecomp call graph/ABI fields.
        # Do not claim to have verified 16,662 cached function rows.
        inventory=verified_ranges
        provenance="local_original_disasm_ranges_without_xboxrecomp_zip"
    need(all(seed in inventory for seed in SEEDS[:2]),
         "Original source inventory lacks hardware-frontier roots")
    sources=reader.load_generated(args.generated,by_name)
    need(len(sources)>=10000,"Generated C inventory incomplete")
    shard_files=sorted(args.shards.glob("translated_???.cpp"))
    need(len(shard_files)==64,"64 original TrueTU shards required, found "+str(len(shard_files)))
    current_bytes=args.current_main.read_bytes()
    current_manifest=json.loads(args.current_manifest.read_text(encoding="utf-8-sig"))
    need(current_manifest.get("stage")=="V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY" and
         current_manifest.get("source_sha256")==hashlib.sha256(current_bytes).hexdigest(),
         "V7I main/manifest identity drift")
    current_text=current_bytes.decode("utf-8",errors="replace")
    main_defs={int(x,16) for x in FUNC.findall(current_text)}
    recovered={int(x,16) for x in current_manifest.get("functions",[])}
    need(len(recovered)==5,"V7E recovered function inventory missing")
    for va in recovered:
        need(("case 0x%08Xu: return sub_%08X;"%(va,va)) in current_text,
             "Recovered function lacks current main dispatch route "+hx(va))
    main_defs |= recovered
    pack_entries=re.findall(r'case\s+0x([0-9A-Fa-f]{8})u\s*:\s*return\s+sub_([0-9A-Fa-f]{8})\s*;', current_text)
    pack_routes=set()
    for va_text,callee_text in pack_entries:
        need(va_text.lower()==callee_text.lower(),
             "Malformed original function dispatch route "+va_text)
        va=int(va_text,16)
        need(va not in pack_routes,"Duplicate original function dispatch "+hx(va))
        pack_routes.add(va)
    need(recovered.issubset(pack_routes),
         "V7E recovered functions absent from original dispatch")
    main_defs |= pack_routes
    staged={}
    for shard in shard_files:
        for hit in FUNC.finditer(shard.read_text(encoding="utf-8",errors="replace")):
            staged.setdefault(int(hit.group(1),16),[]).append(shard.name)
    # Priority queue with bounded expansion. Source calls are actual original
    # generated C references; cached graph edges are useful but NOT proof.
    todo=deque((seed,0,seed) for seed in SEEDS)
    done={}
    while todo and len(done)<args.cap:
        at,level,root=todo.popleft()
        if at in done:continue
        original=inventory.get(at,{})
        generated=sources.get(at)
        body=generated.get("source","") if generated else ""
        masked=reader.mask_noncode(body) if body else ""
        src_calls={int(x,16) for x in CALL.findall(masked)}-{at}
        cached_calls={v for x in original.get("calls_to",[]) if (v:=number(x)) is not None}
        # Prefer verified generated-C call targets; fall back to metadata graph
        # while labeling uncertainty instead of silently assuming execution.
        edges=src_calls if generated else cached_calls
        done[at]={
            "va":hx(at),"root":hx(root),"depth":level,
            "retail_present":at in inventory,
            "original_section":original.get("section"),
            "original_size":original.get("size"),
            "estimated_params":original.get("estimated_params"),
            "calling_convention_heuristic":original.get("calling_convention"),
            "generated_body_present":bool(generated),
            "generated_source_sha256":hashlib.sha256(body.encode()).hexdigest() if body else None,
            "in_true_tus":staged.get(at,[]),
            "in_current_main":at in main_defs,
            "already_compiled":bool(staged.get(at)) or at in main_defs,
            "actual_generated_direct_calls":[hx(v) for v in sorted(src_calls)][:100],
            "cached_recomp_callees":[hx(v) for v in sorted(cached_calls)][:100],
            "graph_edges_basis":"generated_source" if generated else "cached_inventory_only",
            "missing_source":not bool(generated),
            "not_in_original_inventory":at not in inventory,
        }
        if level<args.depth:
            for v in sorted(edges):
                if v not in done and v in inventory:todo.append((v,level+1,root))
    candidates=sorted(done.values(),key=lambda r:(
        0 if r["generated_body_present"] and not r["already_compiled"] else
        1 if r["missing_source"] and r["retail_present"] else 2,
        r["depth"],r["va"]))
    counts={
        "visited":len(done),
        "generated_missing":sum(x["missing_source"] for x in done.values()),
        "generated_present_not_staged":sum(x["generated_body_present"] and not x["already_compiled"] for x in done.values()),
        "already_staged_true_tu":sum(bool(x["in_true_tus"]) for x in done.values()),
        "already_in_main":sum(x["in_current_main"] for x in done.values()),
        "remaining_queue":len(todo),
    }
    report={
        "phase":"K1_V7J_RETAIL_XBOXRECOMP_TRUE_TU_SOURCE_BATCH_READ_ONLY",
        "retail_sha256":RETAIL,"v7i_main_sha256":hashlib.sha256(current_bytes).hexdigest(),
        "inventory_provenance":provenance,"inventory_functions":len(inventory),
        "xboxrecomp_functions":len(inventory) if args.recon is not None else None,
        "generated_source_functions":len(sources),"true_tus":len(shard_files),
        "roots":[hx(v) for v in SEEDS],"depth":args.depth,"budget":args.cap,
        "counts":counts,"candidate_priority":candidates,
        "hardware_fact":"V7I seventh APC delivered; next kind17 NtReadFile Event/APC unsupported target 0x800000DB",
        "limits":["Cached xrefs are static hints, not runtime provenance",
                  "Source presence does not prove execution or ABI",
                  "No game source bytes exported in metadata",
                  "APC callback ABI must be verified before accepting new shapes",
                  "Without xboxrecomp ZIP: original function ranges are unverified cache, not equivalent to retail SHA-verified graph"],
        "xdk_built":False,"xbox_run":False}
    args.out.mkdir(parents=True,exist_ok=True)
    path=args.out/"v7j_batch_frontiers.json"
    path.write_text(json.dumps(report,indent=2,default=str)+"\n",encoding="utf-8")
    print("[K1-V7J] INVENTORY MODE "+provenance)
    print("[K1-V7J] Source corpus / current main / 64 TrueTUs analyzed; no retail bytes emitted")
    print("[K1-V7J] scanned=%(visited)d new_generated_not_staged=%(generated_present_not_staged)d missing_body=%(generated_missing)d TrueTU=%(already_staged_true_tu)d main=%(already_in_main)d" % counts)
    print("[K1-V7J] PRIORITY CANDIDATES (NO ABI CLAIM):")
    for c in candidates[:20]:
        if (c["generated_body_present"] and not c["already_compiled"]) or c["missing_source"]:
            print("[K1-V7J] %s depth=%d generated=%s TrueTU=%s root=%s"%(
                  c["va"],c["depth"],c["generated_body_present"],bool(c["in_true_tus"]),c["root"]))
    print("[K1-V7J] REPORT "+str(path))
    print("[K1-V7J] READ ONLY / NO XDK / NO XBOX / NO KERNEL FENCE BYPASS")
if __name__=="__main__":
    try:main()
    except Exception as exc:
        print("[K1-V7J] HARD FENCE "+str(exc),file=sys.stderr);sys.exit(1)
