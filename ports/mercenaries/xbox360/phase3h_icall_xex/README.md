# Phase 3H — First bounded translated indirect-call dispatch

**Status: source ready; local ICALL candidate selection + modified Xbox 360 hardware run pending.**

Phase 3G proved a real translated direct x86 `CALL`. Phase 3H moves to a
real translated function-pointer call lowered through `RECOMP_ICALL_SAFE`.

## What this gate proves

The maintained runtime's stack-safe indirect dispatcher must:

- record the guest target VA
- preserve Xbox x86 callee-saved `EBX/ESI/EDI`
- reject middle-range garbage VAs before lookup
- try manual, generated, then kernel dispatch sources
- enter the resolved translated target with the synthetic zero return slot
- restore the saved pre-argument ESP and force `EAX=0` when resolution fails

## Candidate selection

The prep workflow scans actual retail-generated functions for one real
`RECOMP_ICALL_SAFE` site.

The earlier Phase 3F candidate `0x00034AE0` is checked first, but the selector
may choose a smaller genuine Mercenaries ICALL site if the preferred function
is too broad for this first isolated gate.

The first candidate must be:

- mechanically translated from the exact supported retail XBE
- compact and linear
- exactly one `RECOMP_ICALL_SAFE`
- no direct translated calls
- no indirect tail call
- no guest argument pushes before the ICALL dummy return slot
- no unrelated PUSH/POP traffic
- exactly one plain translated RET
- no SEH bridge dependency
- no x87/SSE/MMX dependency
- no flag-sensitive branch machinery
- no kernel/runtime-copy/RDTSC/debugbreak dependency
- no caller modification of `EBX/ESI/EDI`

The ICALL target expression must also be simple enough to seed deterministically
as either a register or `GUEST_READ32(register [+ constant])`.

## Dispatch target

Resolved dispatch targets the already hardware-proven translated function:

```text
0x0004CFF0
```

The prep workflow lifts that retail function again locally and renames its body
for the harness. A thin dispatch wrapper records entry ESP/[ESP], executes the
real translated body, then deliberately clobbers `EBX/ESI/EDI`.

A successful real `RECOMP_ICALL_SAFE` must restore all three caller values.

## Three runtime modes

Each deterministic input is executed in all three modes.

### Resolved

Guest target:

```text
0x0004CFF0
```

Dispatch path:

```text
manual lookup -> miss
generated lookup -> translated 0x0004CFF0
```

Required:
- translated target enters exactly once
- target entry ESP = caller ESP - 4
- guest `[ESP] = 0`
- kernel lookup is not reached
- `EBX/ESI/EDI` are restored after deliberate target clobber

### Unresolved

Guest target remains:

```text
0x0004CFF0
```

Generated lookup is deliberately disabled.

Required:
- manual/generated/kernel lookup all execute and miss
- translated target is never entered
- saved pre-call ESP is restored
- `EAX=0`

### Range reject

Guest target becomes:

```text
0x00400000
```

This is inside the runtime's rejected middle range
`[0x00400000, 0xFE000000)`.

Required:
- no lookup source is entered
- translated target is never entered
- saved pre-call ESP is restored
- `EAX=0`

## Differential reference

The locally generated reference caller is the exact same translated caller with
only the generated:

```c
PUSH32(esp, 0);
RECOMP_ICALL_SAFE(target, _icall_esp);
```

operation replaced by an independent helper.

The helper manually creates the zero guest return slot, directly executes the
known translated target for resolved mode, independently restores callee-saved
registers, and reproduces the documented safe-failure stack/EAX contract.

The real and reference paths are compared across:

- EAX/ECX/EDX
- ESP
- EBX/ESI/EDI
- translated trace
- ICALL target/count
- target-entry probe
- guest-memory access-fault state
- complete 64 MiB guest-RAM digest

The real path additionally verifies exact lookup-chain counts.

## Local preparation

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3h_icall_xex\Prepare-Phase3H.ps1"
```

The workflow reuses the reviewed Phase 3E disassembly when available.

Successful preparation ends with:

```text
[Phase3H] SELECTED
...
[Phase3H] READY
[Phase3H] Caller: ...
[Phase3H] ICALL expression: ...
[Phase3H] Dispatch target: sub_0004CFF0 @ 0x0004CFF0
[Phase3H] Modes: resolved / unresolved / range reject
[Phase3H] XDK source: ...\build\phase3h_translated_icall\main.cpp
```

Compile the generated local `main.cpp` in the same VS17/XDK diagnostic
project. Do not compile `main_template.cpp` directly.

## Expected hardware marker

Build tag:

```text
P3H-ICALL-20261018-A
```

Functional jackpot:

```text
[Merc360:P3H] PHASE 3H TRANSLATED INDIRECT-CALL RESULT: PASS
```

A complete clean run should also reach the normal timeout/exit path and
`[XAPI RETURN VALUE] 0`.

After Phase 3H, the next step is a broader translated execution slice before
attempting guarded game-entry/startup execution.


## First local selector pass — 11 real ICALL functions found

The first local prep scanned 1,600 compact translated functions and found 11
real `RECOMP_ICALL_SAFE` callers. None passed the original gate because:

- 7 also contained a direct translated call
- 2 contained branching control flow
- 2 contained a tail jump

The selector has therefore been loosened in one narrow direction: it may now
carry exactly one small ordinary translated helper call alongside the ICALL.

That helper must itself be linear, plain-RET, stack-simple, free of ICALL/ITAIL
and other runtime dependencies, and must not modify EBX/ESI/EDI. Its generated
body is injected locally and explicit-memory audited before XDK compilation.

The hardware fixture was also strengthened:
- full reference/real translated traces are compared, so an optional direct
  helper does not invalidate the fixture
- the indirect target must still appear exactly once only in resolved mode
- saved ESP, immediate post-ICALL ESP and immediate post-ICALL EAX are recorded
  at the dispatch boundary
- unresolved and range-rejected modes therefore prove saved-ESP restoration and
  EAX=0 at the ICALL itself, independent of later caller instructions

If no candidate survives the relaxed gate, the selector now prints each early
ICALL caller VA with its exact rejection reason.

## Second selector pass — runtime target discovery

The second local diagnostic identified two especially useful real callers:

- `0x0008DE60`
- `0x0008DE70`

Both survived the bounded ICALL gate except for one selector-only rule: their
ICALL base register `EAX` is modified before the call.

That rule has been removed. Phase 3H no longer forces or predicts the guest
function pointer. Instead:

1. an unresolved discovery prepass executes the exact transformed translated
   caller and records the single guest VA produced at the real ICALL site
2. state is reset identically
3. resolved mode maps that exact observed guest VA through generated lookup to
   translated `0x0004CFF0`
4. state is reset again
5. unresolved mode leaves the same observed VA unresolved and verifies the full
   manual/generated/kernel miss chain

This preserves the caller's real pointer-building instructions and proves the
same deterministic target is reproduced across runs.

The production middle-range guard remains unchanged. Its `0x00400000` test is
now a separate direct macro-vs-reference fixture rather than an artificial
rewrite of the selected caller's target expression.

The resolved and unresolved real-caller paths still compare architecture,
translated trace, immediate ICALL saved/post ESP and EAX observations, target
entry, callee-saved-register restoration, fault state and the complete 64 MiB
guest-RAM digest.

## Hardware result — Phase 3H-A dispatcher mechanics PASS

Build tag `P3H-ICALL-20261018-A` executed real translated caller
`0x0008DE60` on modified Xbox 360 hardware.

The caller's deterministic discovery target was `0x00000000` in all three
cases. The resolved fixture intentionally mapped that observed guest key to the
already-proven translated target `0x0004CFF0`.

Every dispatcher-mechanics check passed:
- resolved target entry
- zero synthetic return slot
- generated lookup after manual miss
- EBX/ESI/EDI restoration after deliberate target clobber
- unresolved manual/generated/kernel miss chain
- immediate unresolved saved-ESP restoration and EAX=0
- independent `0x00400000` range rejection before lookup
- translated trace equality
- no guest-memory faults
- complete 64 MiB RAM-hash equality

Observed per-case RAM hashes:
- case 0: `C503958C0C6B32E5`
- case 1: `D5199677916B32E5`
- case 2: `857097D1B66B32E5`

Observed final marker:
`[Merc360:P3H] PHASE 3H TRANSLATED INDIRECT-CALL RESULT: PASS`

The supplied log excerpt ends during post-test heartbeats, so no unseen XAPI
exit status is claimed.

This is recorded as **Phase 3H-A PASS**, not final Phase 3H completion, because
the real caller's synthetic seed produced a NULL guest function pointer. The
next refinement will discover the caller's naturally computed guest pointer
slot and seed that slot with a nonzero translated code VA before rerunning the
unchanged real caller.

## Phase 3H-B — nonzero real guest function-pointer slot

Build tag: `P3H-ICALL-20261018-B`.

3H-A proved the dispatcher mechanics but its deterministic caller state read a
NULL guest function pointer. The B fixture removes that caveat without changing
the real translated caller.

For a `GUEST_READ32(...)` ICALL operand, a local discovery copy exposes only
the guest slot address while preserving every mechanically translated
instruction that computes it. The harness then:

1. records the real guest function-pointer slot address
2. resets identical state
3. writes `0x0004CFF0` into that exact slot
4. runs the unchanged translated caller
5. requires the real ICALL trace itself to equal nonzero `0x0004CFF0`
6. resolves that VA through generated lookup to translated `sub_0004CFF0`
7. reruns unresolved mode with the same seeded slot and unchanged caller

The discovery caller is also run through the explicit guest-memory audit before
XDK compilation.

## Hardware result — Phase 3H-B PASS / Phase 3H COMPLETE

Build tag `P3H-ICALL-20261018-B` executed successfully on modified Xbox 360
hardware.

Real translated caller:
- `0x0008DE60`

Real discovered guest function-pointer slot:
- `0x00000034`

Seeded nonzero translated code VA:
- `0x0004CFF0`

The unchanged translated caller read `0x0004CFF0` from its own discovered
guest slot and passed that nonzero VA through the real
`RECOMP_ICALL_SAFE` path.

Resolved mode passed:
- no guest-memory faults
- nonzero ICALL target reproduced exactly
- translated target entered once
- zero synthetic guest return slot
- manual miss -> generated lookup hit
- EBX/ESI/EDI restored after deliberate target clobber
- final ESP correct
- translated trace matched the independent reference
- complete 64 MiB RAM hash matched

Unresolved mode passed:
- same unchanged caller read the same nonzero `0x0004CFF0`
- target not entered
- immediate saved-ESP restoration
- immediate EAX=0
- manual/generated/kernel lookup chain exhausted
- final state, translated trace and complete RAM hash matched

The independent `0x00400000` range-guard test also passed with no lookup,
saved-ESP restoration, EAX=0 and full RAM equality.

Observed hashes:
- case 0: `5FEC0A1C02F3BEE5`
- case 1: `BB6103599BF3BEE5`
- case 2: `64F113F868F3BEE5`

Observed final markers:
`[Merc360:P3H] PHASE 3H TRANSLATED INDIRECT-CALL RESULT: PASS`
`[XAPI RETURN VALUE] 0`

**Phase 3H is complete.**