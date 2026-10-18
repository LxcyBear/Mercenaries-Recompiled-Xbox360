# Phase 3D — Explicit runtime/string memory cleanup

**Status: source ready; modified Xbox 360 hardware run pending.**

Phase 3A–3C proved the explicit scalar, x87, SSE/XMM and MMX memory slices.
Phase 3D closes the shared runtime/string paths that could still bypass the
checked guest-memory ABI before any translated Mercenaries function executes.

## Generator mode

The recompiler now has a real opt-in switch:

~~~text
--explicit-guest-memory
~~~

When selected, the lifter emits explicit GUEST_READ/GUEST_WRITE forms and
generated C defines RECOMP_EXPLICIT_GUEST_MEMORY_ABI so the shared runtime
selects its checked-memory branches too. Normal PC generation remains the
default.

## Runtime paths migrated

- shared PUSH32 / POP32 macros
- XBOX_MEMCPY
- XBOX_REP_MOVS
- runtime checkpoint reads that previously used MEM32 directly
- non-REP movs/stos/lods string instructions
- REP MOVS/STOS
- REP CMPS/SCAS memory reads
- SSE flag reconstruction memory operands

## Safety audit

Explicit translation now rejects executable legacy accesses such as:

~~~text
MEM8/16/32/64
SMEM8/16/32/64
MEMF / MEMD
XBOX_PTR
~~~

A standalone post-patch scanner is also included:

~~~text
py -m tools.recomp.audit_explicit_guest_memory <generated-file-or-dir>
~~~

Run that after Patch-Generated.py and any mod-extension patch scripts. This is
important because those scripts can modify C after the lifter's per-function
audit has already run.

## Boundary rule

One scalar or SIMD access is checked as its whole width and must not straddle
a 64 MiB window. String/copy instructions are different: they represent a
sequence of individual x86 memory accesses. If ESI/EDI increments from the
end of one mapped RAM window into the next mirror, that sequence is valid and
must retain element-at-a-time ordering.

## Build

Use the same VS17 + Xbox 360 XDK diagnostic project.

1. Replace its source with main.cpp from this directory.
2. No retail default.xbe is required.
3. Clean, rebuild and deploy to modified Xbox 360 hardware.
4. Require:

~~~text
[Merc360:P3D] BUILD TAG: P3D-RUNTIME-20261018-A
~~~

## Hardware fixture

The fixture validates:
- Xenon big-endian host order,
- shared PUSH32 old-ESP source evaluation and POP32 restoration,
- XBOX_MEMCPY aligned dword + byte-tail copying,
- unaligned raw-byte XBOX_MEMCPY,
- REP MOVSB forward copying,
- overlapping REP MOVSB x86 forward-order semantics,
- unaligned REP MOVSW and REP MOVSD element semantics,
- generated-style MOVSD, STOSW and LODSB,
- generated-style REP STOSD,
- backwards REP MOVSD direction behavior,
- CMPSW/SCASB explicit memory reads,
- RAM-mirror and KSEG0 coherence,
- scalar dword boundary rejection,
- element-wise XBOX_MEMCPY progression into a mapped RAM mirror,
- NV2A MMIO rejection through XBOX_REP_MOVS.

## Expected finish

~~~text
[Merc360:P3D] PASS: shared PUSH32 uses explicit guest write and old-ESP source
[Merc360:P3D] PASS: overlapping REP MOVSB x86 forward-order semantics
[Merc360:P3D] PASS: runtime scalar bridge rejects cross-64MiB dword
[Merc360:P3D] PHASE 3D RUNTIME MEMORY ABI RESULT: PASS
~~~

Send the full xbWatson trace.

A PASS closes the shared runtime/string memory gate. The next step is not
another synthetic memory fixture: it is selecting one small audited translated
Mercenaries function, generating it with --explicit-guest-memory, compiling it
into a bounded XDK harness, and comparing its guest-visible result against a
reference fixture before allowing broader translated execution.