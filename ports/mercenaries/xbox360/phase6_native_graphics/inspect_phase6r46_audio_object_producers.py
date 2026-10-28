#!/usr/bin/env python3
"""R46 zero-build provenance audit for the second AC97 channel object.

Examines the generated R45 translated source.  Does not mutate code, build a
XEX, or change guest runtime behavior.
"""
from __future__ import annotations

import argparse
from pathlib import Path
from inspect_phase6r44_bad_audio_object import functions, print_body

TARGETS = (
    0x002A7818,  # channel-object setup; bad pointer observed at 002A78A2
    0x002A6B98,  # calls setup twice, with different pointer producers
    0x002A7605,  # preceding channel setup
    0x002A766D,  # preceding channel setup
    0x0029FEED,  # 256-byte allocation-side caller
    0x0029CBD2,  # pairing/cleanup helper bypassed by R45 containment
)
CALLEES = ("sub_002A6B98", "sub_002A7818")
MAX_CALLERS_PER_CALLEE = 18


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--source", type=Path, required=True)
    args = ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R46] missing generated source: {args.source}")
    text = args.source.read_text(encoding="utf-8", errors="replace")
    all_functions = functions(text)
    by_va = {entry["va"]: entry for entry in all_functions}
    print("[Phase6R46] AUDIO OBJECT PRODUCER ZERO-BUILD AUDIT")
    print("[Phase6R46] Source:", args.source)
    print("[Phase6R46] Hardware: first 002A78A2 object=024900B4, second=00040000")
    print("[Phase6R46] R45: 002A7712 containment occurred; next WRITE8 fault=DEA8510B")
    print("[Phase6R46] source mutation=0 build=0 xbox_run=0")
    missing = []
    for va in TARGETS:
        entry = by_va.get(va)
        if entry is None:
            missing.append(f"{va:08X}")
            print(f"[Phase6R46] MISSING: sub_{va:08X}")
        else:
            print_body("PRODUCER/HELPER BODY", entry)
    for callee in CALLEES:
        needle = callee + "();"
        count = 0
        printed = 0
        print("=" * 90)
        print(f"[Phase6R46] CALLERS OF {callee}")
        for caller in all_functions:
            lines = caller["body"].splitlines()
            for idx, line in enumerate(lines):
                if needle not in line:
                    continue
                count += 1
                if printed >= MAX_CALLERS_PER_CALLEE:
                    continue
                printed += 1
                lo, hi = max(0, idx-22), min(len(lines), idx+12)
                print(f"[Phase6R46] CALL {count} owner={caller['name']} owner_va={caller['va']:08X} source_line={idx+1}")
                for j in range(lo, hi):
                    mark = ">>" if j == idx else "  "
                    print(f"[Phase6R46] {mark} {j+1:04d}: {lines[j]}")
        print(f"[Phase6R46] CALLER SUMMARY target={callee} total={count} printed={printed}")
    target = by_va.get(0x002A76FE)
    if target:
        body = target["body"]
        bypass = "goto loc_002A776D;" in body
        cleanup_start = body.find("loc_002A7765: ;")
        epilogue_start = body.find("loc_002A776D: ;")
        cleanup_call = (
            cleanup_start >= 0 and epilogue_start > cleanup_start
            and "sub_0029CBD2();" in body[cleanup_start:epilogue_start]
        )
        print("=" * 90)
        print(f"[Phase6R46] R45 CONTAINMENT CHECK: early_epilogue_jump={int(bypass)} cleanup_before_epilogue={int(cleanup_call)}")
        if bypass and cleanup_call:
            print("[Phase6R46] FINDING: bad-signature jump bypasses the matching 0029CBD2 cleanup call")
            print("[Phase6R46] NOTE: do not assume safe lock state or suppress additional faults")
    if missing:
        raise SystemExit("[Phase6R46] STOP: missing required functions " + ",".join(missing))
    print("[Phase6R46] AUDIT COMPLETE. Hardware pointer origin still requires live callsite identification.")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
