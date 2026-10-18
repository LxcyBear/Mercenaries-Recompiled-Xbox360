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
