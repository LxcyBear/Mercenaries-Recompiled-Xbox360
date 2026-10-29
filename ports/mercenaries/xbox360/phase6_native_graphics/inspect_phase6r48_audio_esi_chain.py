#!/usr/bin/env python3
"""Phase6R48 zero-build audit: which call loses the second channel slot base?

R47 hardware:
  sub_002A7605 channel-store: ESI=0 for both channel writes, despite
  sub_002A6B98 first setting ESI=EBX+0x14.
  slot0 pointer=024900B4, slot1 pointer=024900F4.
  first load through [ESI] works; second through [EBX+0x18] gives 00040000.
  R47 cleanup path executed; later WRITE8 DEA8510B still fenced.

This audit intentionally does not fix or guess calling convention semantics.
"""
from __future__ import annotations
import argparse
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions, print_body

TARGETS = (
    0x002A6B98, # caller: ESI = EBX+14, calls A7B73/A7605
    0x002A7B73, # first suspected ESI clobber
    0x002A7605, # channel slot writer
    0x0029FF54, # allocation helper between ESI setup and slot write
    0x0029CBB0, # acquire scope helper
    0x0029CBD2, # cleanup helper
    0x002A739F, # upstream caller
)
def main() -> int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R48] Missing generated source: {args.source}")
    entries=functions(args.source.read_text(encoding="utf-8",errors="replace"))
    by_va={entry["va"]:entry for entry in entries}
    print("[Phase6R48] ZERO-BUILD CHANNEL POINTER / ESI-PRESERVATION AUDIT")
    print(f"[Phase6R48] source={args.source}")
    print("[Phase6R48] hardware: second store EAX=024900F4 ECX=1 ESI=00000000")
    print("[Phase6R48] hardware: second load [EBX+18]=00040000, EBX=008BFF8C")
    print("[Phase6R48] hardware: R47 cleanup PASS, WRITE8 DEA8510B still fenced")
    print("[Phase6R48] no build, no source mutation, no Xbox run")
    missing=[]
    for va in TARGETS:
        f=by_va.get(va)
        if not f:
            missing.append(f"{va:08X}")
            print(f"[Phase6R48] MISSING sub_{va:08X}")
            continue
        print_body("ESI CALL CHAIN",f)
        body=f["body"]
        lines=body.splitlines()
        esi_ops=[(i+1,s.strip()) for i,s in enumerate(lines)
                 if ("esi =" in s or "esi=" in s
                     or "PUSH32(esp, esi)" in s or "POP32(esp, esi)" in s)]
        print(f"[Phase6R48] ESI TOUCHES sub_{va:08X} count={len(esi_ops)}")
        for lineno,line in esi_ops:
            print(f"[Phase6R48]   L{lineno:04d}: {line}")
    f=by_va.get(0x002A6B98)
    if f:
        print("[Phase6R48] CHECK A6B98 initialization and downstream calls:")
        for token in ("esi = ebx + 0x14;", "sub_002A7B73();",
                      "sub_002A7605();", "ecx = phase6ch_apu_read32(ebx + 0x18);"):
            print(f"[Phase6R48]   {token}: {'PRESENT' if token in f['body'] else 'MISSING'}")
    f=by_va.get(0x002A7605)
    if f:
        print("[Phase6R48] CHECK A7605 ESI setup and write:")
        for token in ("esi = ecx;", "sub_0029CBB0();",
                      "sub_0029FF54();", "phase6ch_apu_write32(esi + ecx * 4, eax);"):
            print(f"[Phase6R48]   {token}: {'PRESENT' if token in f['body'] else 'MISSING'}")
    if missing:
        raise SystemExit("[Phase6R48] STOP missing translated functions: "+", ".join(missing))
    print("[Phase6R48] AUDIT COMPLETE. Confirm exact ESI clobber before proposing guest repair.")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
