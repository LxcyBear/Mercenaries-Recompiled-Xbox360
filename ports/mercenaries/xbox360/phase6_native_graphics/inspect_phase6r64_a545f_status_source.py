#!/usr/bin/env python3
"""Phase 6R64 — zero-build actual DirectSound HRESULT producer audit.

R63 real Xbox log (2026-10-29):
  F0C6_AFTER_A58C0 EAX=00000000
  F0C6_AFTER_F03A  EAX=00000000
  F0C6_AFTER_A5770 EAX=8007000E
  F0C6_FINAL_STATUS EAX=8007000E
  Final guest fault EC83F0E4 at tick 27,027,014; no pixels.

R61 translated code proves A5770 is only 25 lines:
  edx = read32(ecx+0x80); eax=0; write32(ecx+0x148,0);
  if (read8(edx+0xA) & 4) return;
  else tail-jump sub_002A545F.
The negative return makes A545F's path the prime suspect; the source
needs inspection before any semantic repair or another XEX build.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions

ROOT = 0x002A545F
WRAPPER = 0x002A5770
PARENT = 0x0029F0C6
INTEREST = re.compile(
    r"(?i)(8007000E|800700|C0000017|0x8000|0x2BAA|Allocate|Free|"
    r"Memory|Heap|Pool|sub_[0-9a-f]{8}\(\)|PHASE6DJ_ICALL_SAFE|"
    r"phase4c_direct_frontier|GUEST_READ|GUEST_WRITE|"
    r"phase6ch_apu_(?:read|write)|if \(|goto |return|ret |eax =)"
)
CALLEE = re.compile(r"\bsub_([0-9a-fA-F]{8})\(\)")

def dump(row, label, full_cap=240, head=110, tail=48):
    src=row["body"].splitlines()
    count=len(src)
    print("="*100)
    print(f"[Phase6R64] {label} sub_{row['va']:08X} lines={count}")
    if count<=full_cap:
        indices=range(count)
    else:
        selected=set(range(min(head,count)))|set(range(max(0,count-tail),count))
        hits=[i for i,line in enumerate(src) if INTEREST.search(line)]
        for i in hits[:36]:
            selected.update(range(max(0,i-2),min(count,i+4)))
        indices=sorted(selected)
    previous=-2
    for i in indices:
        if i>previous+1:
            print(f"[Phase6R64]  ... omitted {i-previous-1} source lines ...")
        print(f"[Phase6R64] {i+1:04d}: {src[i]}")
        previous=i
    print(f"[Phase6R64] END {label}")

def get_children(row):
    direct=[]
    for name in CALLEE.findall(row["body"]):
        address=int(name,16)
        if address!=row["va"] and address not in direct:
            direct.append(address)
    return direct

def main():
    arg=argparse.ArgumentParser()
    arg.add_argument("--source",type=Path,required=True)
    opt=arg.parse_args()
    if not opt.source.is_file():
        raise SystemExit(f"[Phase6R64] Missing R59 source: {opt.source}")
    content=opt.source.read_text(encoding="utf-8",errors="replace")
    if "P6DQ R59 FC4A ABI RESTORE:" not in content:
        raise SystemExit("[Phase6R64] R59 ABI baseline missing; refuse to audit unrelated source")
    rows=functions(content)
    byva={row["va"]:row for row in rows}
    for va in (PARENT,WRAPPER,ROOT):
        if va not in byva:
            raise SystemExit(f"[Phase6R64] Missing translated function sub_{va:08X}")
    print("[Phase6R64] ================================================================")
    print("[Phase6R64]   ACTUAL DIRECTSOUND 8007000E STATUS SOURCE: A545F")
    print("[Phase6R64] ================================================================")
    print(f"[Phase6R64] cached_source={opt.source} bodies={len(rows)}")
    print("[Phase6R64] R63 hardware: F03A=0, A5770=8007000E, XACT=8007000E")
    print("[Phase6R64] R61: A5770 returns 0 if bit2 set, else tail-calls A545F")
    print("[Phase6R64] OBSERVED FAULT: EC83F0E4 @ 27027014 ticks; display_calls=0")
    print("[Phase6R64] 0 changes, 0 re-shard, 0 VS/XDK compilation")
    print("[Phase6R64] 1/3 EXACT A5770 WRAPPER / TAIL DISPATCH")
    dump(byva[WRAPPER],"A5770 WRAPPER",full_cap=60)
    print("[Phase6R64] 2/3 COMPLETE A545F STATUS-PRODUCER BODY")
    dump(byva[ROOT],"A545F ROOT",full_cap=650,head=180,tail=80)
    direct=get_children(byva[ROOT])
    print(f"[Phase6R64] A545F direct_callees={len(direct)} "+
          " ".join(f"{v:08X}" for v in direct))
    print("[Phase6R64] 3/3 FIRST-HOP A545F HELPERS / ALLOCATION SOURCES")
    for addr in direct[:15]:
        row=byva.get(addr)
        if row is None:
            print(f"[Phase6R64] CALLEE {addr:08X} NOT TRANSLATED")
            continue
        print(f"[Phase6R64] CALLEE {addr:08X} lines={len(row['body'].splitlines())} "+
              f"children={','.join(f'{v:08X}' for v in get_children(row)[:12])}")
        dump(row,"A545F FIRST-HOP",full_cap=100,head=30,tail=15)
    if len(direct)>15:
        print(f"[Phase6R64] additional_callees_not_dumped={len(direct)-15}")
    parent=byva[PARENT]
    print("[Phase6R64] PARENT F0C6 callsite context:")
    src=parent["body"].splitlines()
    for i,line in enumerate(src):
        if "sub_002A5770();" in line:
            for j in range(max(0,i-8),min(len(src),i+14)):
                print(f"[Phase6R64] F0C6 {j+1:04d}: {src[j]}")
    print("[Phase6R64] ACTION: determine A545F branch/allocator HRESULT source.")
    print("[Phase6R64] Do NOT force successful status, fake allocations, bypass guest fences, or skip legitimate teardown.")
    print("[Phase6R64] AUDIT COMPLETE")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
