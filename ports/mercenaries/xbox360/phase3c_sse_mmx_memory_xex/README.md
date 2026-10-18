# Phase 3C — SSE/XMM + MMX guest-memory ABI

**Status: source ready; modified Xbox 360 hardware run pending.**

Phase 3A proved explicit scalar integer memory and Phase 3B proved signed/x87
memory. Phase 3C migrates SIMD guest-memory transfers without changing normal
PC generation by default.

## Maintained lifter changes

In explicit guest-memory mode:
- MMX memory operands use `GUEST_READ64` / `GUEST_WRITE64`.
- scalar SSE memory operands use the Phase 3B float/double helpers.
- MOVSS memory stores no longer emit a native `MEMF` lvalue.
- packed XMM moves still call the existing runtime helper names, but the
  Xbox 360 runtime branch performs endian-safe checked guest transfers.

## Runtime XMM transfer rules

When `RECOMP_EXPLICIT_GUEST_MEMORY_ABI` is defined:
- full 128-bit XMM loads/stores use one checked 16-byte guest transfer,
- MOVSS uses one checked 32-bit transfer,
- MOVSD/MOVQ/MOVLPS/MOVHPS use one checked 64-bit transfer,
- each 32-bit XMM lane is reconstructed from raw x86 lane bits.

The 16-byte transfer is intentionally atomic at the routing layer. Four
independent dword reads would incorrectly allow a packed access near the end
of one 64 MiB RAM window to wrap into the next mirror.

## Build

Use the same VS17 + Xbox 360 XDK diagnostic project.

1. Replace its source with `main.cpp` from this directory.
2. No retail `default.xbe` is required.
3. Clean, rebuild and deploy to modified Xbox 360 hardware.
4. Require:

~~~text
[Merc360:P3C] BUILD TAG: P3C-SIMD-20261018-A
~~~

## Hardware fixture

The fixture validates:
- Xenon big-endian host order,
- unaligned full 128-bit XMM load/store,
- four packed float lane values and lane order,
- MOVSS low-lane load + upper-lane zeroing,
- MOVSD/MOVQ raw low-64 payload preservation,
- MOVLPS/MOVHPS lane replacement and store behavior,
- ADDPS-style packed arithmetic with a memory source,
- XORPS-style raw lane-bit behavior,
- MMX MOVQ/PAND-style 64-bit memory paths,
- XMM mirror coherence,
- MMX-width KSEG0 coherence,
- rejection of a 128-bit transfer crossing a 64 MiB window,
- rejection of an 8-byte SIMD/MMX transfer crossing a window,
- rejection of NV2A MMIO as ordinary XMM RAM.

## Expected finish

~~~text
[Merc360:P3C] PASS: 128-bit XMM helper rejects cross-64MiB transfer
[Merc360:P3C] PASS: 128-bit XMM helper rejects NV2A MMIO as RAM
[Merc360:P3C] PHASE 3C SIMD MEMORY ABI RESULT: PASS
~~~

Send the complete xbWatson trace.

A PASS closes the principal SSE/XMM + MMX memory-transfer endian/routing
contract. REP/string helpers, shared PUSH/POP runtime macros and remaining
manual legacy-memory sites still need cleanup before a translated Mercenaries
function is allowed to execute.

## Hardware result — PASS

Build tag `P3C-SIMD-20261018-A` passed the complete functional Phase 3C SIMD
fixture on modified Xbox 360 hardware.

Verified:
- unaligned 128-bit XMM lane reconstruction/store
- MOVSS/MOVSD/MOVLPS/MOVHPS memory semantics
- packed arithmetic + raw bitwise lanes
- MMX 64-bit memory semantics
- mirror + KSEG0 coherence
- checked 128-bit / 64-bit boundary rejection
- NV2A MMIO rejection

The observed trace contains:
`[Merc360:P3C] PHASE 3C SIMD MEMORY ABI RESULT: PASS`

The pasted excerpt ends during post-test heartbeats, so this record does not
claim an unshown final XAPI return value.

**Phase 3C is complete.**