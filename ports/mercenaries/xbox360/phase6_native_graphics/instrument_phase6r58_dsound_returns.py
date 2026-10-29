#!/usr/bin/env python3
"""Phase6R58: overlay bounded DirectSound return telemetry onto an R51 mono source.

R57 forensic evidence:
  XACT stage1_29FDF0=81AEC546, relayed from sub_0029FD83.
  In FD83, the existing-object path preserves ESI=0 and returns EAX=ESI=0.
  Therefore nonzero negative result is consistent with its new-object path,
  barring register/stack corruption. Locate which helper returns the value.
Never fabricate a success status, patch a refcount, resurrect freed objects,
or relax MMIO/VP/guest-memory fault fences.

The generated R51 Rocket source and manifest are READ ONLY. R58 overlays a
separate monolithic source, then existing True TU emits content-stable changes.
"""
from __future__ import annotations

import argparse
import re
from pathlib import Path
from inspect_phase6r44_bad_audio_object import closing_brace

SOURCE_TAG="P6DQ-R51-MM173-FRAME-20261029-A"
OVERLAY_MARKER="P6DQ R58 DSOUND STATUS:"
SUBS=(0x0029FD83,0x0029FC4A)

def log_after(tag:str, first_only:int=5, neg_cap:int=45)->str:
    # No guest reads, guest writes, guest register edits, EFLAGS edits or guest
    # stack changes. Native static counters scoped to this exact callsite.
    return (
        "\n    {\n"
        "        static unsigned int r58_count = 0u;\n"
        "        ++r58_count;\n"
        f"        if (r58_count <= {first_only}u || (((int32_t)eax < 0) && r58_count <= {neg_cap}u))\n"
        "        {\n"
        "            char r58_line[256];\n"
        "            sprintf(r58_line,\n"
        f'                "P6DQ R58 DSOUND STATUS: {tag} call=%u eax=%08X esi=%08X edi=%08X ecx=%08X esp=%08X",\n'
        "                (unsigned int)r58_count, (unsigned int)eax,\n"
        "                (unsigned int)esi, (unsigned int)edi,\n"
        "                (unsigned int)ecx, (unsigned int)esp);\n"
        "            trace(r58_line);\n"
        "        }\n"
        "    }\n"
    )

def patch_function(source:str,va:int,patches:list[tuple[str,str]])->tuple[str,int]:
    name=f"sub_{va:08X}"
    pattern=re.compile(r"(?m)^\s*static void "+name+r"\(void\)\s*\{")
    matches=list(pattern.finditer(source))
    if len(matches)!=1:
        raise SystemExit(f"[Phase6R58] {name}: expected exactly one function, got {len(matches)}")
    match=matches[0]
    brace=source.find("{",match.start(),match.end())
    end=closing_brace(source,brace)
    body=source[match.start():end]
    if OVERLAY_MARKER in body:
        raise SystemExit(f"[Phase6R58] {name} already instrumented; expected clean R51 source")
    for anchor,replacement in patches:
        count=body.count(anchor)
        if count!=1:
            raise SystemExit(f"[Phase6R58] {name} unexpected anchor count={count}: {anchor!r}")
        body=body.replace(anchor,replacement,1)
    return source[:match.start()]+body+source[end:],len(patches)

def after(call:str,tag:str,*,first:int=5)->tuple[str,str]:
    anchor=f"    PUSH32(esp, 0); {call}"
    return anchor,anchor+log_after(tag,first)

def main()->int:
    ap=argparse.ArgumentParser()
    ap.add_argument("--source",type=Path,required=True)
    ap.add_argument("--out",type=Path,required=True)
    args=ap.parse_args()
    if not args.source.is_file():
        raise SystemExit(f"[Phase6R58] original monolithic source missing: {args.source}")
    source=args.source.read_text(encoding="utf-8",errors="replace")
    if source.count(SOURCE_TAG)==0:
        raise SystemExit("[Phase6R58] R51 baseline tag not present")
    if OVERLAY_MARKER in source:
        raise SystemExit("[Phase6R58] refusing to overlay already-instrumented source")
    fd83=[
        (
            "    eax = phase6ch_apu_read32(0x2BB098);",
            "    eax = phase6ch_apu_read32(0x2BB098);"
            +log_after("FD83_ENTRY_2BB098",first_only=6),
        ),
        after("sub_002A41EE(); /* call 0x002A41EE */","FD83_EXISTING_A41EE"),
        after("sub_0029CB9F(); /* call 0x0029CB9F */","FD83_ALLOC_2C"),
        after("sub_0029CF0B(); /* call 0x0029CF0B */","FD83_CONSTRUCT"),
        after("sub_0029FC4A(); /* call 0x0029FC4A */","FD83_FC4A_RESULT"),
        (
            "    eax = esi;\n    POP32(esp, esi);\n    esp += 8; return; /* ret 4 */",
            log_after("FD83_FINAL",first_only=6)
            + "    eax = esi;\n    POP32(esp, esi);\n    esp += 8; return; /* ret 4 */",
        ),
    ]
    source,n1=patch_function(source,0x0029FD83,fd83)
    fc4a=[
        after("sub_0029F4BF(); /* call 0x0029F4BF */","FC4A_F4BF"),
        after("sub_002A0E9D(); /* call 0x002A0E9D */","FC4A_A0E9D"),
        after("sub_002A19FC(); /* call 0x002A19FC */","FC4A_A19FC"),
        after("sub_0029FF54(); /* call 0x0029FF54 */","FC4A_FF54"),
        after("sub_0029F992(); /* call 0x0029F992 */","FC4A_F992",first=3),
        after("sub_0029F495(); /* call 0x0029F495 */","FC4A_F495",first=3),
        after("sub_0029E531(); /* call 0x0029E531 */","FC4A_E531",first=3),
    ]
    source,n2=patch_function(source,0x0029FC4A,fc4a)
    # R58 identity is in the newly compiled functions, without changing
    # the R51 baseline build tag or falsely claiming an R58 Rocket revision.
    source=source.replace(
        '#pragma warning(disable:4146)',
        '#pragma warning(disable:4146)\n/* Phase 6R58 diagnostic overlay: R51 Rocket unchanged */',
        1
    )
    if source.count(OVERLAY_MARKER)!=n1+n2:
        raise SystemExit("[Phase6R58] instrumentation marker count mismatch")
    args.out.parent.mkdir(parents=True,exist_ok=True)
    encoded=source.encode("utf-8")
    if args.out.is_file() and args.out.read_bytes()==encoded:
        print("[Phase6R58] CONTENT-STABLE overlay output retained")
    else:
        args.out.write_bytes(encoded)
        print("[Phase6R58] WROTE overlay; R51 base is untouched")
    print(f"[Phase6R58] instrumented_functions=2 checkpoints={n1+n2}")
    print("[Phase6R58] source_integrity=R51_Rocket_read_only trueTU_incremental_ready=YES")
    print("[Phase6R58] probe never changes guest registers, guest stack, return status, object lifetime, fault policy")
    return 0

if __name__=="__main__":
    raise SystemExit(main())
