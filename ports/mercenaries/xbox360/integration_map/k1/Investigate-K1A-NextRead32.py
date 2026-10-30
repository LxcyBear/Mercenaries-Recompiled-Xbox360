#!/usr/bin/env python3
"""K1A hardware READ32 boundary provenance — read-only frozen R59 source audit.

The real 2026-10-29 K1A Xbox run passed KeQuerySystemTime ordinal 128,
then hard-fenced a 4-byte read at EFEE0EC4 (ESI=EFEE0EC0, tick=27029593).
This tool DOES NOT patch the generated source, allow the address or guess
which guest instruction issued the read. It reports relevant exact VA
contexts and nearby ESI assignments so a real root-cause correction can
be reviewed BEFORE any next VS2017/XDK build.
"""
from __future__ import annotations
import argparse
import re
from pathlib import Path

R59_IDENTITY = "P6DQ R59 FC4A ABI RESTORE:"
HARDWARE = {
    "fault": 0xEFEE0EC4,
    "esi": 0xEFEE0EC0,
    "ticks": 27029593,
    "caller": 0x0023A3CE,
    "width": 4,
    "clock_ordinal": 128,
    "clock_called": 1,
    "last_source_va": 0x002A6624,
}
LAST_RING = (
    0x002A2DA0,0x002A2DA3,0x002A2DD8,0x0029CC2C,0x002A2DE8,
    0x0029CBD2,0x0029CBDB,0x0029CBE3,0x0029CBE7,0x002A2DF0,
    0x0029FF69,0x0029FF6F,0x0029FF76,0x0029FF92,0x0029FFB6,
    0x002A0AE0,0x002A0AF1,0x002A6595,0x002A65C1,0x002A65CA,
    0x0029FE8E,0x0029FE9D,0x0029FEA3,0x0029FEAA,0x0029FEB9,
    0x0029FECF,0x002A65E4,0x002A65F2,0x002A6600,0x002A6607,
    0x002A6617,0x002A6624,
)
NEAR = re.compile(r'\b(?:GUEST_READ(?:8|16|32)|MEM(?:8|16|32)|esi\s*=|'
                  r'PUSH32|POP32|PHASE4C_BUDGET_TICK)\b',re.I)
FUNCTION = re.compile(r'(?m)^\s*(?:static\s+)?void\s+sub_([0-9A-Fa-f]{8})\s*\(')
LABEL = re.compile(r'(?m)^\s*loc_([0-9A-Fa-f]{8})\s*:')

def analyze(source:str)->str:
    if R59_IDENTITY not in source:
        raise ValueError("Expected frozen R59 translated-source watermark missing")
    lines=source.splitlines()
    anchors={v:i for i,line in enumerate(lines) for v in
             [int(m.group(1),16) for m in [LABEL.search(line)] if m]}
    functions=[(i,int(m.group(1),16)) for i,line in enumerate(lines)
               for m in [FUNCTION.search(line)] if m]
    out=[
        "# K1A first hardware READ32 after KeQuerySystemTime: source investigation",
        "",
        "OBSERVED: ordinal 128 executed once; later guest READ32 EFEE0EC4 hard-fenced.",
        "OBSERVED: ESI=EFEE0EC0 and access=ESI+4; caller=0023A3CE;",
        "          tick=27029593. This is a guest address, NOT a verified GPU/MMIO register.",
        "OBSERVED: display_calls=0, framebuffer=00000000. No game pixels yet.",
        "INFERENCE ONLY: bad guest pointer or memory translation; origin NOT YET PROVEN.",
        "SAFETY: do not whitelist EFEE0EC4, silence READ32 faults or invent a value.",
        "",
        f"R59 source lines: {len(lines)}. Last-ring addresses: {len(LAST_RING)}.",
        "Address labels below are source matches; trace-ring VA does not necessarily",
        "identify the precise faulting expression.",
        "",
        "## Last-ring address contexts, oldest to newest",
    ]
    for va in LAST_RING:
        start=anchors.get(va)
        if start is None:
            out.append(f"VA {va:08X}: no exact loc_ label (may be a function start/interior)")
            continue
        fn=max(((i,v) for i,v in functions if i<=start),default=None)
        fnname=f"sub_{fn[1]:08X}" if fn else "unresolved"
        out.append(f"\n### VA {va:08X} line {start+1} parent={fnname}")
        left=max(0,start-6)
        right=min(len(lines),start+15)
        for k in range(left,right):
            prefix=">>" if k==start else "  "
            out.append(f"{prefix} {k+1:07d}: {lines[k][:360]}")
    out.extend(["", "## Near final source VA: read expressions and ESI provenance candidates"])
    recent=LAST_RING[-8:]
    context=set()
    for va in recent:
        k=anchors.get(va)
        if k is not None:
            context.update(range(max(0,k-36),min(len(lines),k+35)))
    for k in sorted(context):
        line=lines[k]
        if NEAR.search(line):
            out.append(f"{k+1:07d}: {line[:420]}")
    out.extend(["", "## Literal poison/address occurrences in frozen translated source"])
    for needle in ("EFEE0EC0","EFEE0EC4","0xEFEE","0xEFEE0EC"):
        hits=[i for i,line in enumerate(lines)
              if needle.lower() in line.lower()]
        out.append(f"{needle}: {len(hits)} literal matches")
        for k in hits[:12]:out.append(f"{k+1:07d}: {lines[k][:320]}")
    out.extend(["", "NEXT: identify the exact faulting GUEST_READ32 instruction and",
                "backtrack the ESI definition. Inspect live memory/object ancestry",
                "before fixing any graphics/audio mapping or guest return ABI.",
                "Do not claim a runtime fix from this static audit."])
    return "\n".join(out)+"\n"

def main()->None:
    p=argparse.ArgumentParser()
    p.add_argument("--source",type=Path,required=True)
    p.add_argument("--out",type=Path,required=True)
    args=p.parse_args()
    if not args.source.is_file():
        p.error("Missing local frozen R59 source: "+str(args.source))
    if args.source.resolve()==args.out.resolve():
        p.error("Refusing to overwrite frozen source")
    result=analyze(args.source.read_text(encoding="utf-8",errors="replace"))
    args.out.parent.mkdir(parents=True,exist_ok=True)
    args.out.write_text(result,encoding="utf-8")
    print("[K1A-READ32] PASS: frozen source inspected; NO game runtime mutated")
    print("[K1A-READ32] READ32 EFEE0EC4 remains HARD FENCED")
    print("[K1A-READ32] output="+str(args.out))

if __name__=="__main__":
    main()
