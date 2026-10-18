# Phase 3G — First bounded translated normal-CALL chain

**Status: source ready; local candidate selection + modified Xbox 360 hardware run pending.**

Phase 3F proved a real translated tail-call chain. Phase 3G tests the other x86
call shape: a real direct `CALL` whose translated lowering must create a
synthetic guest return-address slot before entering the callee, let the callee
`RET` consume that slot, then resume and return from the translated caller.

## Candidate selection

The Phase 3G prep does not hard-code a guessed pair. It consumes the reviewed
Phase 3E `functions.json` call graph and searches for the smallest isolated
real x86 `CALL` pair that satisfies all first-gate constraints.

The selector requires:
- exactly one direct callee in the caller's disassembler `calls_to` set
- anonymous exact `sub_XXXXXXXX` caller/callee boundaries
- compact caller and callee
- callee with no direct translated callees
- exactly one generated normal-CALL lowering:
  `PUSH32(esp, 0); callee(); /* call ... */`
- no tail jump
- no ICALL/ITAIL
- no kernel/runtime-copy/RDTSC/debugbreak dependency
- no x87/SSE/MMX dependency
- no SEH EBP bridge dependency
- no caller stack mutation before CALL
- no other caller PUSH/POP
- no callee PUSH/POP
- plain translated `RET` rather than `RET N`
- no unknown generated runtime helper outside the bounded harness surface

The first pair satisfying all constraints is generated locally from the exact
supported retail XBE. No retail-derived generated C is committed.

## Differential reference

The real translated caller retains the recompiler's generated normal CALL:

```c
PUSH32(esp, 0);
translated_callee();
```

A local reference copy of the exact same translated caller changes only that
one operation:

```c
uint32_t newEsp = esp - 4;
GUEST_WRITE32(newEsp, 0);
esp = newEsp;
translated_callee();
```

The reference deliberately does not use `PUSH32`. This isolates the generated
CALL-stack operation while preserving the same translated caller instructions,
translated callee, register state and guest memory.

## Callee-entry probe

The generated callee body is renamed locally and called through a tiny
non-semantic probe wrapper. Before entering the real translated callee body the
wrapper records:
- callee entry count
- guest ESP at entry
- guest dword at `[ESP]`

Phase 3G requires both reference and real generated paths to observe:
- exactly one callee entry
- entry ESP = caller initial ESP - 4
- `[ESP] = 0`, the translated dummy return address

The caller and callee are both required to use plain RET, so final guest ESP
must equal caller initial ESP + 4 after callee return and caller return.

## Full-state comparison

Three deterministic cases compare:
- EAX/ECX/EDX/EBX/ESI/EDI
- guest ESP
- SEH bridge sentinel
- access-fault state
- translated trace order `[caller, callee]`
- callee-entry probe
- complete 64 MiB guest-RAM digest

The synthetic return slot is pre-seeded with nonzero data before each run, so
the test proves the CALL path really overwrites it with zero.

## Local preparation

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3g_direct_call_xex\Prepare-Phase3G.ps1"
```

The workflow reuses
`build\phase3e_first_translated\analysis\disasm` when available. Otherwise
it rebuilds the reviewed-seed disassembly from the exact supported retail XBE.

Successful preparation ends with:

```text
[Phase3G] SELECTED
...
[Phase3G] READY
[Phase3G] Caller: ...
[Phase3G] Callee: ...
[Phase3G] XDK source: ...\build\phase3g_translated_direct_call\main.cpp
```

Compile that generated `main.cpp` in the same VS17/XDK diagnostic project.
Do not compile `main_template.cpp` directly.

No `default.xbe` is required beside the console XEX after local generation.

## Expected hardware marker

The generated XEX uses:

```text
[Merc360:P3G] BUILD TAG: P3G-CALL-20261018-A
```

A complete functional PASS ends with:

```text
[Merc360:P3G] PHASE 3G TRANSLATED NORMAL-CALL RESULT: PASS
```

After Phase 3G passes, the next bounded execution gate is indirect translated
call dispatch. The ICALL-heavy Phase 3F Candidate A remains a useful real-game
target for that milestone.


## First local prep attempt — standalone selector import fix

The first Phase 3G prep verified the supported XBE and reused the existing Phase
3E analysis, then stopped before candidate selection with:

`ModuleNotFoundError: No module named 'tools'`

The selector is intentionally launched as a standalone Python file from a
nested port directory. It now inserts the repository root into `sys.path`
before importing `tools.recomp`.

The selector was also tightened to prefer linear, flag-free pairs for this first
normal-CALL proof. No candidate was selected and no hardware run occurred in
the failed attempt.

## Hardware result — PASS

Build tag `P3G-CALL-20261018-A` executed on modified Xbox 360 hardware.

Selected real translated pair:
- caller `0x00050010`
- callee `0x0004CFF0`

All three deterministic cases passed.

Observed on every case:
- no guest-memory fault
- translated callee entered exactly once
- callee entry ESP = `0x008BFDFC` = caller initial ESP - 4
- guest `[ESP]` at callee entry = `0x00000000`
- final ESP = `0x008BFE04`
- translated trace = `[0x00050010, 0x0004CFF0]`
- generated `PUSH32(esp, 0)` matched the independent explicit-stack reference
- complete 64 MiB guest-RAM hashes matched

Case hashes:
- case 0: `BDABF3F60D2792E5`
- case 1: `7BC023EB662792E5`
- case 2: `7D456C28BF2792E5`

Observed final markers:
`[Merc360:P3G] PHASE 3G TRANSLATED NORMAL-CALL RESULT: PASS`
`[XAPI RETURN VALUE] 0`

**Phase 3G is complete.** The next bounded execution gate is real translated
indirect-call dispatch / `RECOMP_ICALL_SAFE`.