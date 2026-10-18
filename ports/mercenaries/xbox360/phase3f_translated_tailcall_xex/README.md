# Phase 3F — First bounded translated tail-call chain

**Status: source ready; local generation + modified Xbox 360 hardware run pending.**

Phase 3E proved one real mechanically translated Mercenaries function on
Xenon. Phase 3F escalates to two real translated functions connected by the
game's own direct tail-call control flow.

## Candidate pair

~~~text
0x001EF850  translated wrapper / tail caller
0x0021AB90  reviewed scalar transform setter / callee
~~~

The reviewed seed documents `0x0021AB90` as a scalar transform setter that writes the float argument to `this + 0xDC` and returns with `ret 4`. The project also documents it as being tail-called by `sub_001EF850`.

The maintained lifter lowers that external x86 JMP as a direct C call followed
by return, with **no synthetic guest return-address push**. The existing guest
return slot is therefore consumed by the callee's translated RET, matching
x86 tail-call behavior.

## Differential reference

Phase 3F deliberately does not duplicate the callee's internal logic in the
harness. Instead it compares two executions from identical guest state:

~~~text
Reference path:
    run a locally derived copy of translated 0x001EF850
    stop exactly at its real generated tail-call boundary
    then call translated 0x0021AB90 directly

Tail-call path:
    reset identical guest state
    run unmodified translated 0x001EF850
      -> real generated tail-call
      -> translated 0x0021AB90
~~~

If wrapper translation and tail-call semantics are correct, the two paths must
finish with the same architectural register state and identical guest RAM.

The harness hashes the complete 64 MiB guest arena after each execution, not
just the object under ECX.

## Local preparation

From the repository root:

~~~powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3f_translated_tailcall_xex\Prepare-Phase3F.ps1"
~~~

The script reuses the Phase 3E reviewed-seed disassembly when available.
Otherwise it regenerates the analysis from the exact supported retail XBE.

It then:

1. verifies the pinned retail SHA-256,
2. confirms both 0x00034AD0 and 0x00034AE0 are detected,
3. confirms both reviewed function boundaries are present,
4. lifts both functions with `--explicit-guest-memory`,
5. requires exactly one direct wrapper -> callee call,
6. requires the generated tail-jump marker,
7. rejects PUSH32 in the wrapper tail call,
8. rejects third translated-function calls, ICALL/ITAIL, kernel/runtime-copy,
   RDTSC/debugbreak, and x87/SSE/MMX dependencies for this first chain,
9. runs the legacy-memory audit on both generated functions, and
10. injects both local retail-derived bodies into a gitignored XDK harness.

Successful preparation ends with:

~~~text
[Phase3F] READY
[Phase3F] XDK source: ...\build\phase3f_translated_tailcall\main.cpp
~~~

## Build

Compile:

~~~text
build\phase3f_translated_tailcall\main.cpp
~~~

in the same VS17/XDK diagnostic project used for the earlier hardware tests.

No `default.xbe` is required beside the XEX after local source generation.

## Hardware checks

The harness runs three deterministic cases. For each case it:

- resets all 64 MiB of guest RAM,
- seeds the same effective object bytes and auxiliary guest bytes,
- seeds all architectural integer registers and the guest return slot,
- runs the callee directly with `ECX = BASE + 0x78`,
- hashes all 64 MiB of resulting guest RAM,
- resets to identical initial guest state,
- runs the translated wrapper with `ECX = BASE`,
- hashes all 64 MiB again,
- compares EAX/ECX/EDX/ESP/EBX/ESI/EDI and the SEH EBP bridge,
- requires both paths to restore ESP to the same stack top,
- requires no guest-memory access fault,
- requires trace sequence `[callee]` for the reference,
- requires trace sequence `[wrapper, callee]` for the translated chain, and
- requires identical complete guest-RAM hashes.

## Expected start

~~~text
[Merc360:P3F] PHASE 3F TRANSLATED TAIL-CALL CHAIN START
[Merc360:P3F] BUILD TAG: P3F-TAILCALL-20261018-B
[Merc360:P3F] Candidate B wrapper VA: 0x001EF850
[Merc360:P3F] Candidate B callee VA:  0x0021AB90
~~~

Expected finish:

~~~text
[Merc360:P3F] PHASE 3F TRANSLATED TAIL-CALL RESULT: PASS
~~~

If the prep script rejects the pair, send the full PowerShell output. If the
generated XDK source fails to compile, send the first real compiler error. If
it builds, send the complete xbWatson trace.

A PASS proves a real translated Mercenaries caller -> callee tail chain and
guest-stack return behavior on Xenon. The next escalation is a normal direct
CALL (with its synthetic guest return-address push), followed by indirect-call
dispatch.

## First local candidate attempt — dependency gate rejection

The first prep run successfully detected and lifted:
- wrapper `0x00034AD0`: 12 bytes / 3 instructions
- callee `0x00034AE0`: 108 bytes / 36 instructions

The strict dependency audit rejected the callee before XDK compilation because
its generated output matched the guarded ICALL/kernel/runtime-copy dependency
class. No Xbox 360 hardware test occurred.

The prep script now prints every exact generated line that triggers this guard.
Rerun after updating the branch and send those lines.

## Candidate A rejection and Candidate B pivot

Candidate A (`0x00034AD0 -> 0x00034AE0`) was rejected before compilation
because the callee contains a real guest indirect call:

`PUSH32(esp, 0); RECOMP_ICALL_SAFE(GUEST_READ32(eax), _icall_esp);`

That would combine tail-call validation with indirect-call dispatch, so it is
intentionally deferred to the later ICALL milestone.

Candidate B uses `0x001EF850 -> 0x0021AB90`. To avoid inventing the wrapper's
pre-tail behavior, the prep script creates a local reference-prefix copy of the
exact translated wrapper and replaces only its generated tail-call statement
with a native return after the generated EBP bridge. Hardware then compares:

- translated wrapper prefix + direct translated callee
- unmodified translated wrapper + real translated tail call

Both start from identical guest state, use the same retail-derived translated
code, and are compared across registers, guest ESP, access-fault state, trace
sequence, and a digest of the complete 64 MiB guest arena.

## Candidate B scalar XMM0 refinement

The first Candidate B prep stopped on:

`GUEST_WRITEF32(ecx + 0xDC, xmm0); /* movss */`

This is an expected scalar SSE path already proven by Phase 3C, not a new
unsupported subsystem. The guard has therefore been narrowed rather than
removed.

Candidate B is now accepted only if the generated shape contains:
- wrapper scalar load: `recomp_xmm_loadss(g_xmm0, esp + 4)`
- callee scalar store: `GUEST_WRITEF32(ecx + 0xDC, xmm0)`

Every broader SIMD/x87 form remains rejected. The hardware harness also seeds,
captures and compares all four XMM0 lanes between the differential reference
and the unmodified translated tail-call chain.

## Candidate B wrapper shape — confirmed from local generated output

The local lift showed the complete wrapper body is only:

`ecx = ecx + 0x28;`

followed by the generated direct tail invocation of `sub_0021AB90()`.

There is no wrapper-side MOVSS load. XMM0 is already live at wrapper entry.
The prep workflow and Xenon harness were simplified accordingly.

The differential is now:
- direct translated `0x0021AB90` with `ECX = BASE + 0x28`
- translated `0x001EF850` with `ECX = BASE`, which performs the real
  `+0x28` adjustment and tail call

Both receive identical live XMM0 state and identical guest stack contents.
The harness also explicitly checks that the XMM0 lane-0 bits are stored at the
common effective `this + 0xDC` address and that `ret 4` restores guest ESP.

## Candidate B callee stack-MOVSS shape — confirmed

The generated callee itself performs the scalar load from guest `[ESP+4]`
before storing to `this + 0xDC`. The prior rule that rejected a callee-side
`recomp_xmm_loadss` was therefore incorrect.

Phase 3F now requires:
- wrapper: `ECX += 0x28`, direct tail call, no synthetic `PUSH32`
- callee: `recomp_xmm_loadss(g_xmm0, esp + 4)`
- callee: `GUEST_WRITEF32(ecx + 0xDC, xmm0)`
- callee: translated `ret 4`

The hardware harness poisons XMM0 before entry and places the real scalar only
on the guest stack. A PASS therefore proves the translated callee really loads
the stack scalar, applies the already-proven memory-form MOVSS lane semantics,
stores it at the correct effective object field, and cleans the guest stack.

## Generated XMM alias correction

Local output confirmed the callee exactly as:
- `recomp_xmm_loadss(xmm0v, esp + 4)`
- `GUEST_WRITEF32(ecx + 0xDC, xmm0)`
- translated `ret 4`

The prep checker had expected `g_xmm0` directly, but generated code uses the
runtime's canonical vector alias `xmm0v`. The checker now requires `xmm0v`,
and the Phase 3F XDK harness defines `xmm0v` as `g_xmm0` just like the real
runtime.

## Hardware result — PASS

Build tag `P3F-TAILCALL-20261018-B` executed the real translated chain
`0x001EF850 -> 0x0021AB90` on modified Xbox 360 hardware.

Observed cases:
- `1.0f` bits `0x3F800000`
- `-2.5f` bits `0xC0200000`
- `~1/3` bits `0x3EAAAAAB`

For all three cases:
- direct translated callee and translated wrapper-tail-call paths completed
  without guest-memory faults
- wrapper `ECX += 0x28` produced the same effective object
- trace order was direct `[callee]` versus real `[wrapper, callee]`
- callee loaded the exact guest `[ESP+4]` scalar into XMM0 lane 0
- memory-form MOVSS zeroed XMM0 lanes 1-3
- the scalar was stored at effective `this + 0xDC`
- translated `ret 4` restored ESP to `0x008BFFF0`
- all integer state and all four XMM0 lanes matched
- complete 64 MiB guest-RAM hashes matched

Observed final functional marker:
`[Merc360:P3F] PHASE 3F TRANSLATED TAIL-CALL RESULT: PASS`

The supplied excerpt ends during post-test heartbeats, so no unshown final XAPI
exit line is claimed.

**Phase 3F is complete.** The next bounded escalation is a real translated
normal CALL chain with the synthetic guest return-address push.