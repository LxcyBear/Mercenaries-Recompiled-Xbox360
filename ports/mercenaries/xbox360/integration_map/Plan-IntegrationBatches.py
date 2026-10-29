#!/usr/bin/env python3
"""Convert Phase 6 integration-map outputs into evidence-labelled batch backlog.

NO runtime patches, game data or XDK assets. A static candidate is NOT an
import; an import is NOT a tested implementation; a route is NOT a PASS.
"""
from __future__ import annotations
import argparse
import csv
import json
from collections import Counter, defaultdict
from pathlib import Path

DATA_EXPORTS={40,41,42,156,164,322,324,326,356,357}
TIME_FAMILY={99,113,128,149,151,156}
FPU_FAMILY={139,142}
THREAD_SYNC={98,107,109,129,139,142,160,161,255,277,291,294}
MEMORY={14,15,17,23,173,184,185}
FILES={187,196,202,218,226,236}
PRIORITY={128:0,151:1,113:2,149:3}

def csv_read(path:Path):
    with path.open(newline="",encoding="utf-8") as f:
        return list(csv.DictReader(f))

def csv_write(path:Path,rows:list[dict],fields:list[str]):
    with path.open("w",newline="",encoding="utf-8") as f:
        w=csv.DictWriter(f,fieldnames=fields,extrasaction="ignore")
        w.writeheader();w.writerows(rows)

def family(n:int,name:str)->str:
    if name.startswith("Xc"):return "CRYPTOGRAPHY"
    if name.startswith("Dbg") or "BugCheck" in name or name in (
        "RtlRaiseException","RtlRaiseStatus","RtlUnwind","RtlAssert"):
        return "DEBUG_EXCEPTIONS"
    if name in ("MmClaimGpuInstanceMemory",):return "GRAPHICS_MEMORY"
    if name.startswith("Hal") or name.startswith("Av"):return "HARDWARE_PLATFORM"
    if name in ("ExQueryNonVolatileSetting",):return "CONFIGURATION"
    if name.startswith(("Io","Iof")):return "IO_MANAGER"
    if name.startswith("NtWait") or name.startswith("NtUserIoApc"):
        return "THREAD_SYNCHRONIZATION"
    if name.startswith("Nt") and ("File" in name or "Directory" in name or
                                  "Buffers" in name or "Volume" in name or
                                  "FsControl" in name):return "STORAGE_IO"
    if name.startswith("Nt") and ("VirtualMemory" in name or "Memory" in name):
        return "GUEST_MEMORY"
    if name.startswith("Nt") and "Event" in name:return "THREAD_SYNCHRONIZATION"
    if name.startswith("Ps"):return "THREAD_LIFECYCLE"
    if name.startswith("RtlTime"):return "TIME_CONVERSION"
    if name.startswith("Rtl"):return "RUNTIME_HELPERS"
    if name.startswith("Mm"):return "GUEST_MEMORY"
    if name.startswith("Ke") and ("Timer" in name or "Time" in name):
        return "TIME_SCHEDULING"
    if n in TIME_FAMILY:return "TIME_SCHEDULING"
    if n in FPU_FAMILY:return "FLOATING_POINT_CONTEXT"
    if n in THREAD_SYNC or name.startswith("Ke"):return "THREAD_SYNCHRONIZATION"
    if n in MEMORY:return "GUEST_MEMORY"
    if n in FILES:return "STORAGE_IO"
    return "OTHER_KERNEL"

def kernel_rows(rows, hardware_ordinal=None):
    out=[]
    for r in rows:
        n=int(r["ordinal"])
        imported=r["retail_import_verified"].strip().lower()=="true"
        routed=r["route_present"].strip().lower()=="true"
        isdata=r.get("export_kind","")=="DATA" or (
            not r.get("export_kind") and (n in DATA_EXPORTS or "DATA" in r["name"].upper()))
        if not imported and n==hardware_ordinal:
            disposition="HARDWARE_OBSERVED_IMPORT_SLOT_UNVERIFIED"
        elif not imported:
            disposition="STATIC_CANDIDATE_ONLY"
        elif isdata:
            disposition="IMPORTED_DATA_EXPORT_NEEDS_AUDIT"
        elif not routed:
            disposition="IMPORTED_CALLABLE_NO_ROUTE_IDENTIFIED"
        else:
            disposition="IMPORTED_ROUTED_SEMANTICS_UNVERIFIED"
        if n==hardware_ordinal:priority="P0_ACTIVE_HARDWARE_STOP"
        elif imported and not isdata and not routed:priority="P1_VERIFIED_MISSING_ROUTE"
        elif imported and not isdata and routed:priority="P2_TEST_SEMANTICS_ABI"
        elif imported and isdata:priority="P2_DATA_SEMANTICS_AUDIT"
        else:priority="P3_STATIC_TRIAGE"
        out.append({
            "ordinal":n,"name":r["name"],
            "family":family(n,r["name"]),"priority":priority,
            "disposition":disposition,
            "retail_import_verified":imported,
            "route_present":routed,
            "route_sources":r["route_sources"],
            "static_literal_mentions":r["static_literal_mentions"],
            "next_step":(
                "Verify ordinal-128 guest stack frame, 8-byte output pointer, and 100ns clock"
                if n==128 else
                "Confirm observed kernel target call frame and typed side effects; verify import slot separately"
                if n==hardware_ordinal and not imported else
                "Confirm presence in exact 111-slot import table before assigning data or callable status"
                if not imported else
                "Audit how the guest consumes this imported data value; verify pointer relocation/readback when applicable"
                if isdata else
                "Validate call ABI, guest side effects, error codes and return value"
                if routed else
                "Implement typed bridge with offline fixture; preserve unknown dispatch fence")
        })
    def rank(r):
        p=r["priority"]
        return (0 if p.startswith("P0") else 1 if p.startswith("P1") else 2 if p.startswith("P2") else 3,
                PRIORITY.get(r["ordinal"],999),r["ordinal"])
    return sorted(out,key=rank)

def abi_rows(edges,limit=150):
    callers=Counter();callees=Counter()
    for r in edges:
        n=int(r["static_callsites"])
        callers[r["caller_va"]]+=n;callees[r["callee_va"]]+=n
    scores=[]
    for va in callers.keys()|callees.keys():
        incoming=callees[va];outgoing=callers[va]
        scores.append({"guest_va":va,"static_incoming_calls":incoming,
                       "static_outgoing_calls":outgoing,
                       "static_degree":incoming+outgoing,
                       "status":"ABI_RISK_CANDIDATE_NOT_FAULT"})
    scores.sort(key=lambda x:(-x["static_degree"],x["guest_va"]))
    return scores[:limit],len(scores)

def hardware_rows(mmio):
    families=defaultdict(lambda:{"unique_addresses":0,"literal_mentions":0})
    for r in mmio:
        addr=r["address"]
        n=int(r["literal_mentions"])
        # Distinguish APU central/VP and other FE/FC. Widths/dynamic accesses
        # remain UNKNOWN until disassembly/runtime has independently proven them.
        if addr.startswith("FE80"):group="APU_CORE"
        elif addr.startswith("FE82"):group="APU_VP"
        elif addr.startswith("FE"):group="OTHER_FE_MMIO"
        elif addr.startswith("FC"):group="FC_MMIO"
        else:group="OTHER"
        families[group]["unique_addresses"]+=1
        families[group]["literal_mentions"]+=n
    return [{"family":key,**value,"semantic_status":"STATIC_LITERALS_ONLY"}
            for key,value in sorted(families.items())]

def main():
    ap=argparse.ArgumentParser()
    ap.add_argument("--out",type=Path,required=True)
    a=ap.parse_args()
    out=a.out
    needed=("kernel-coverage.csv","guest-call-edges.csv","mmio-literals.csv",
            "fault-ledger.json","phase6-integration-map.json")
    for n in needed:
        if not (out/n).is_file():raise ValueError(f"Required map input missing: {n}")
    summary=json.loads((out/"phase6-integration-map.json").read_text(encoding="utf-8"))
    ledger=json.loads((out/"fault-ledger.json").read_text(encoding="utf-8"))
    if summary.get("status")!="phase6DQ_diagnostic_baseline_frozen_NOT_gate6":
        raise ValueError("Wrong integration baseline identity")
    imports_verified=summary["import_inventory"]["verified"]
    raw_hardware_target=summary.get("last_hardware_boundary",{}).get("target","")
    hardware_ordinal=None
    if isinstance(raw_hardware_target,str) and len(raw_hardware_target)==8:
        try:
            raw=int(raw_hardware_target,16)
            if (raw&0x80000000) and (raw&0x7FFFFFFF)<1024:
                hardware_ordinal=raw&0x7FFFFFFF
        except ValueError:
            pass
    kernel=kernel_rows(csv_read(out/"kernel-coverage.csv"),hardware_ordinal)
    if imports_verified and summary["import_inventory"].get("expected")!=111:
        raise ValueError("Expected exactly 111 retail import slots")
    abi,abi_nodes=abi_rows(csv_read(out/"guest-call-edges.csv"))
    mmio=hardware_rows(csv_read(out/"mmio-literals.csv"))
    faults=sorted(ledger["faults"].values(),key=lambda r:(-r["hits"],r["target"],r["caller"]))
    csv_write(out/"kernel-batch-priorities.csv",kernel,[
        "ordinal","name","family","priority","disposition",
        "retail_import_verified","route_present","route_sources",
        "static_literal_mentions","next_step"])
    csv_write(out/"guest-abi-hotspots.csv",abi,[
        "guest_va","static_incoming_calls","static_outgoing_calls",
        "static_degree","status"])
    csv_write(out/"mmio-batch-families.csv",mmio,[
        "family","unique_addresses","literal_mentions","semantic_status"])
    missing=sum(x["disposition"]=="IMPORTED_CALLABLE_NO_ROUTE_IDENTIFIED" for x in kernel)
    routed=sum(x["disposition"]=="IMPORTED_ROUTED_SEMANTICS_UNVERIFIED" for x in kernel)
    static=sum(x["disposition"]=="STATIC_CANDIDATE_ONLY" for x in kernel)
    hardware_unverified=sum(x["disposition"]=="HARDWARE_OBSERVED_IMPORT_SLOT_UNVERIFIED" for x in kernel)
    data_exports=sum(x["disposition"]=="IMPORTED_DATA_EXPORT_NEEDS_AUDIT" for x in kernel)
    missing_families=Counter(x["family"] for x in kernel if x["disposition"]=="IMPORTED_CALLABLE_NO_ROUTE_IDENTIFIED")
    lines=[
        "# Phase 6 — batched integration plan","",
        "**Purpose:** map, log, fix root-cause classes, validate, repeat — no more 6DQ micro-revisions.","",
        "## Evidence coverage",
        "",
        f"- Exact owned retail XBE import table: {'VERIFIED (111 slots)' if imports_verified else 'NOT PROVIDED'}",
        f"- Kernel static candidates requiring import reconciliation: {static}",
        f"- Hardware-observed kernel targets with unverified import slot: {hardware_unverified}",
        f"- Verified callable imports with no matching explicit dispatch route: {missing if imports_verified else 'NOT ASSESSED (retail XBE needed)'}",
        f"- Imported DATA exports to audit separately: {data_exports if imports_verified else 'NOT ASSESSED'}",
        f"- Verified routed callable imports requiring semantic/ABI testing: {routed if imports_verified else 'NOT ASSESSED (retail XBE needed)'}",
        f"- Guest ABI graph: {len(csv_read(out/'guest-call-edges.csv')):,} unique static edges across {abi_nodes:,} nodes",
        f"- Distinct hardware fault signatures imported: {len(faults)}",
        "",
        "Route present means only that a source branch exists. **No route is automatically marked hardware PASS.**",
        "",
        "## Priority waves","",
        "1. **Kernel/clock + synchronization (P0/P1).** Validate all 111 exact imports when XBE",
        "   is provided. Handle ordinal 128 with real 100ns output and exact guest",
        "   frame convention, then other imported time/sync functions as a batch.",
        "2. **Guest ABI (P1).** Differential-test preservation of caller/callee-saved registers,",
        "   ESP deltas and nested calls. Rank the graph as *candidates*, not bugs.",
        "3. **Graphics (P1).** Trace real guest D3D -> display mode -> framebuffer -> first present.",
        "4. **MMIO (P2).** Group APU/AC97/NV2A by exact address and width; keep unknowns fenced.",
        "5. **Assets and input (P2).** Batch I/O and callback timing contracts.",
        "",
        "## First kernel candidates (NOT correctness claims)","",
        "| Ordinal | Name | Classification | Priority |",
        "|---|---|---|---|"
    ]
    for row in kernel[:20]:
        lines.append(f"| {row['ordinal']} | {row['name']} | {row['disposition']} | {row['priority']} |")
    lines.extend(["","## Unresolved callable routes by subsystem","",
                  "| Subsystem | Imported callable entries without detected route |",
                  "|---|---:|"])
    for fam,count in sorted(missing_families.items(),key=lambda x:(-x[1],x[0])):
        lines.append(f"| {fam} | {count} |")
    lines.extend(["","## ABI hotspot candidates (NOT proven faults)","",
                  "| Guest VA | Inbound static calls | Outbound static calls |",
                  "|---|---:|---:|"])
    for row in abi[:12]:
        lines.append(f"| {row['guest_va']} | {row['static_incoming_calls']} | {row['static_outgoing_calls']} |")
    lines.extend(["","## MMIO static address groups (not all dynamic accesses)","",
                  "| Family | Unique literals | Occurrences |",
                  "|---|---:|---:|"])
    for row in mmio:
        lines.append(f"| {row['family']} | {row['unique_addresses']} | {row['literal_mentions']} |")
    lines.extend(["","## Top observed runtime faults",""])
    if faults:
        lines.extend(["| Kind | Caller | Target | Hits | Triage |",
                      "|---|---|---|---:|---|"])
        for row in faults[:12]:
            lines.append(f"| {row['kind']} | {row['caller']} | {row['target']} | {row['hits']} | {row.get('triage','unreviewed')} |")
    else:
        lines.append("No hardware logs imported yet. This is an **absence of evidence**, not zero faults.")
    lines.extend(["","## Next batch acceptance gate","",
                  "Import a genuine xbWatson log and optional verified local retail XBE,",
                  "then pin exact kernel and ABI failure contracts and implement them",
                  "as a single reviewed compatibility wave. Do not soften hard stops.",
                  "",
                  "Source used: existing Phase6DQ frozen local generated code.",
                  "No Xbox rebuild, no generated game bytes written or exported."])
    (out/"BATCH_PLAN.md").write_text("\n".join(lines)+"\n",encoding="utf-8")
    print("[BatchPlan] PASS: prioritized kernel/ABI/MMIO/fault backlog produced")
    print(f"[BatchPlan] kernel_candidates={len(kernel)} retail_imports={'VERIFIED' if imports_verified else 'NOT_PROVIDED'}")
    print(f"[BatchPlan] imported_callable_no_route={missing if imports_verified else 'NOT_ASSESSED'} imported_data_exports={data_exports if imports_verified else 'NOT_ASSESSED'} candidates_needing_reconciliation={static}")
    print(f"[BatchPlan] guest_abi_hotspot_nodes={abi_nodes} grouped_mmio_families={len(mmio)}")
    print(f"[BatchPlan] evidence_hardware_faults={len(faults)}")
    print(f"[BatchPlan] observed_hardware_kernel_target={hardware_ordinal if hardware_ordinal is not None else 'NOT_AVAILABLE'}")
    print(f"[BatchPlan] report={out/'BATCH_PLAN.md'}")

if __name__=="__main__":main()
