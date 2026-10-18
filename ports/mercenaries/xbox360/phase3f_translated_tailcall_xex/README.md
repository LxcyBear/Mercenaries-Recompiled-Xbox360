# Phase 3F — First bounded translated tail-call chain

**Status: source ready; local generation + modified Xbox 360 hardware run pending.**

Phase 3E proved one real mechanically translated Mercenaries function on
Xenon. Phase 3F escalates to two real translated functions connected by the
game's own direct tail-call control flow.

## Candidate pair

~~~text
0x00034AD0  reviewed wrapper
0x00034AE0  translated callee
~~~

The reviewed seed documents the wrapper as:

~~~text
ECX += 0x78
tail-call 0x00034AE0
~~~

The maintained lifter lowers that external x86 JMP as a direct C call followed
by return, with **no synthetic guest return-address push**. The existing guest
return slot is therefore consumed by the callee's translated RET, matching
x86 tail-call behavior.

## Differential reference

Phase 3F deliberately does not duplicate the callee's internal logic in the
harness. Instead it compares two executions from identical guest state:

~~~text
Reference path:
    ECX = BASE + 0x78
    sub_00034AE0()

Tail-call path:
    ECX = BASE
    sub_00034AD0()
      -> adjusts ECX by 0x78
      -> tail-calls sub_00034AE0()
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
3. confirms the call graph links the wrapper to the callee,
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
[Merc360:P3F] BUILD TAG: P3F-TAILCALL-20261018-A
[Merc360:P3F] Wrapper VA: 0x00034AD0
[Merc360:P3F] Callee VA:  0x00034AE0
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