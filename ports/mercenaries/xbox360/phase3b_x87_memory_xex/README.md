# Phase 3B — Signed + x87 guest-memory ABI

**Status: source ready; modified Xbox 360 hardware run pending.**

Phase 3A proved explicit unsigned scalar guest reads/writes and RMW behavior on
real Xenon hardware. Phase 3B removes the next host-endian assumptions from
the maintained lifter: signed scalar loads and x87 float/double memory.

Normal PC generation remains unchanged unless the explicit guest-memory ABI is
selected.

## New explicit helpers

~~~text
GUEST_SREAD8/16/32/64
GUEST_READF32 / GUEST_WRITEF32
GUEST_READF64 / GUEST_WRITEF64
~~~

Signed helpers interpret the already-proven explicit integer reads. Float and
double helpers preserve IEEE-754 bits through explicit little-endian guest
integer reads/writes instead of dereferencing native float/double pointers.

## Maintained lifter paths migrated

- MOVSX memory sources
- FILD
- FIST / FISTP integer destinations
- FIADD/FISUB/FISUBR/FIMUL/FIDIV/FIDIVR memory sources
- FLD float/double memory
- FST/FSTP float/double memory
- FADD/FSUB/FSUBR/FMUL/FDIV/FDIVR memory operands
- FCOM/FCOMP/FUCOM/FUCOMP memory operands

SSE/XMM, MMX and REP/string helper migration are intentionally later Phase 3
slices.

## Build

Use the same VS17 + Xbox 360 XDK diagnostic project.

1. Replace its source with main.cpp from this directory.
2. No retail default.xbe is required.
3. Clean, rebuild and deploy to modified Xbox 360 hardware.
4. Require this tag:

~~~text
[Merc360:P3B] BUILD TAG: P3B-X87MEM-20261018-A
~~~

## Hardware fixture

The fixture checks:
- signed 8/16/32/64-bit guest reads and sign extension,
- unaligned signed loads,
- unaligned float32/float64 round-trips,
- exact little-endian IEEE-754 byte layouts,
- FILD-style signed integer load into double domain,
- FIADD-style signed integer-memory arithmetic,
- FLD/FADD/FSTP-style explicit floating memory path,
- FIST-style explicit integer destination write,
- FCOM-style memory comparison,
- float mirror coherence and double KSEG0 coherence,
- MMIO rejection through float32 helper,
- cross-64MiB rejection through float64 helper.

## Expected finish

~~~text
[Merc360:P3B] PASS: FLD/FADD/FSTP-style explicit floating memory path
[Merc360:P3B] PASS: float64 coherent through KSEG0 alias
[Merc360:P3B] PHASE 3B X87 MEMORY ABI RESULT: PASS
~~~

Send the full xbWatson trace.

A PASS closes signed/x87 guest-memory semantics. SSE/XMM, MMX, string helpers
and manual legacy-memory sites still remain before translated Mercenaries code
is allowed to execute.