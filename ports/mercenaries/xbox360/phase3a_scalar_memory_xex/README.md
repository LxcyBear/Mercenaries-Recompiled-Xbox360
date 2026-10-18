# Phase 3A — Explicit scalar guest-memory ABI

**Status: source ready; modified Xbox 360 hardware run pending.**

Phase 2 is complete. Phase 3 now starts changing the generated-code ABI rather
than the guest-memory layout.

The historical lifter emits assignable native-pointer lvalues such as:

~~~c
MEM32(ecx + 4) = MEM32(ecx + 4) + eax;
~~~

That happens to match a little-endian PC host but is not a valid portable ABI
for big-endian Xenon.

Phase 3A adds an **opt-in** scalar-memory mode to the maintained lifter. Normal
PC generation remains unchanged by default. In explicit mode the same RMW
becomes:

~~~c
GUEST_WRITE32(ecx + 4, GUEST_READ32(ecx + 4) + eax);
~~~

The target then owns address routing, little-endian byte semantics and access
failure behavior.

## Scope of 3A

Included now:
- scalar integer 8/16/32/64-bit reads,
- scalar integer writes,
- ordinary read-modify-write instructions routed through the central operand formatters,
- stack memory helper contract,
- CMPXCHG-style scalar access shape.

Not yet claimed safe:
- x87 float/double memory,
- SSE/XMM memory loads/stores,
- MMX memory operations,
- REP/string-copy runtime helpers,
- every manual/patch-site use of legacy MEM lvalues,
- actual translated Mercenaries function execution.

Those are later Phase 3 slices.

## Build

Use the same VS17 + Xbox 360 XDK diagnostic project.

1. Replace its source with main.cpp from this directory.
2. No retail default.xbe is required for this fixture.
3. Clean, rebuild and deploy to modified Xbox 360 hardware.
4. Require:

~~~text
[Merc360:P3A] BUILD TAG: P3A-SCALAR-20261018-A
~~~

## Hardware fixture

The XEX supplies the same helper shape declared by recomp_types.h:

~~~text
recomp_guest_read8/16/32/64
recomp_guest_write8/16/32/64
~~~

and drives them through the exact GUEST_READ* / GUEST_WRITE* macros that
explicit generated scalar code will use.

It checks:
- Xenon is big-endian,
- generated-style 32-bit MOV,
- 32-bit ADD RMW,
- unaligned 16-bit RMW,
- 8-bit XOR RMW,
- unaligned 64-bit access,
- little-endian byte layout for 32/64-bit values,
- RAM mirror + KSEG0/KSEG1 coherence,
- CMPXCHG-style equal and mismatch paths,
- PUSH32 source evaluation before ESP decrement,
- POP32 value/ESP restoration,
- rejection of NV2A MMIO as ordinary RAM,
- rejection of a cross-64MiB dword write.

## Expected finish

~~~text
[Merc360:P3A] PASS: explicit PUSH32 evaluates memory source before ESP decrement
[Merc360:P3A] PASS: explicit helper rejects NV2A MMIO as ordinary RAM
[Merc360:P3A] PHASE 3A SCALAR MEMORY ABI RESULT: PASS
~~~

Send the full xbWatson trace.

A PASS means the first generated-code memory slice is valid on the actual Xbox
360 compiler/CPU. It does **not** mean the complete translated ABI is ready yet.

## Hardware result — PASS

Build tag `P3A-SCALAR-20261018-A` passed the complete Phase 3A fixture on
modified Xbox 360 hardware.

Verified:
- Xenon big-endian host order
- explicit 8/16/32/64-bit guest reads/writes
- generated-style MOV and RMW
- unaligned scalar accesses
- little-endian 32/64-bit guest bytes
- mirror + KSEG0/KSEG1 coherence
- CMPXCHG-style paths
- PUSH source evaluation order + POP restoration
- MMIO/cross-window rejection
- clean cleanup/timeout + `[XAPI RETURN VALUE] 0`

**Phase 3A is complete.**