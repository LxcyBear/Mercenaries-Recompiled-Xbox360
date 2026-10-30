# Phase 6 — Kernel Core Batch K1 (implementation contract)

**2026-10-29. Phase6DQ diagnostic baseline FROZEN. Gate 6 OPEN.**

This is the first subsystem-level implementation work order, not another
Phase 6DQ micro-revision. Grounded in the SHA-verified 111-slot original Xbox
retail import table and the R76 hardware boundary. An imported callable
without a detected route is NOT automatically a broken runtime service.

## Implemented K1A foundation — source stage (2026-10-29)

- Pure C++ UTC/FILETIME 100ns conversion core written and committed:
  `k1/KernelClockCore.h`.
- Guest memory/query bridge for ordinals 128, 304, 305 implemented using
  a mockable memory adapter: `k1/KernelClockGuestBridge.h`.
- Native GCC and Clang test runs PASS for calendar and guest-memory
  fixtures, including invalid pointers and absolute timestamp anchors.
- `k1/Audit-K1A-Dispatch.py` and `k1/Test-K1A-Audit.py` committed
  for fail-closed, read-only R76 source/ABI reconciliation.
- Three-ordinal route injector now committed: `k1/Stage-K1A-ClockBatch.py`.
  Produces a separate staged `main.cpp` with handlers for 128, 304, 305;
  `k1/Test-K1A-Stage.py` checks synthetic route/ABI and immutability guards.
  Local R76 real-source preflight is pending; stage is NOT a hardware result.
- **NOT YET INTEGRATED** into generated main.cpp, native Xbox XDK executable,
  or the physical Xbox 360. Correct register/stack and real runtime guest
  address validation are acceptance gates; preserve current R76 XEX.
- K1B event/synchronization runtime is not implemented yet.
## Hardware evidence — first K1A Xbox 360 test (2026-10-29)

**K1A ordinal 128 was executed and the previous kernel hard stop was passed.**

- Native Xbox boot message contains exact
  `P6K1A-BOOT-CLOCK128-304-305-20261029` (not merely inherited R76).
- Xbox log reports `P6K1A KESYSTEMTIME128: calls=1 output=008BF954
  caller=0023A3CE saved_esp=008BF940`.
- Original R76 boundary was ordinal 128, tick **26,720,251**.
- K1A ran until tick **27,029,593**, +309,342 ticks, then stopped at
  `GUEST_FAULT READ32 EFEE0EC4`, `ESI=EFEE0EC0`, same translated
  caller `0023A3CE`. This is a new failure family, NOT evidence that
  clock/date APIs 304/305 were exercised; those remain unverified on hardware.
- XACT async-stream I/O and subsequent allocation/device setup ran past
  the ordinal-128 site. No guest display handoff:
  `display_calls=0 framebuffer=00000000`.
- Keep the new guest address hard fenced, with no synthetic success or
  invented MMIO mapping. Inspect translated VA ring and ESI provenance
  using `k1/Investigate-K1A-NextRead32.py`.
- Exact R59 VA `002A6624` is inside `sub_002A6595`, after
  `ESI = ECX + EDX*8` from guest locals `[EBP-4]` and `[EBP-12]`.
  The faulting read is `[ESI+4]`. Hardware post-call values
  `ECX=024A8000`, `EDX=FDB471D8` produce `ESI=EFEE0EC0`
  modulo 2^32. Register snapshot is *after* `MmGetPhysicalAddress`;
  these are consistent, not proven identical, pre-call values.
- `k1/Audit-K1A-DsoundTableIndex.py` now extracts the entire function,
  local-variable ancestry and upstream caller to distinguish broken index,
  pointer translation and guest call-frame corruption. No new XDK build yet.
- The R76 source/TrueTU base and prior executable are unchanged.

### New source proof: DSOUND table-index operands

The complete `sub_002A6595` R59 function now proves:
`[EBP-12]=DWORD[EBX]-DWORD[EBX+4]`,
`[EBP-4]=DWORD[0x002BB240]`,
and `ESI=[EBP-4]+[EBP-12]*8`. Fault-time `EBX=00041D70`
is inside the verified retail `.text` section. The next **offline**
proof is a two-dword differential using the user's exact SHA-gated retail
XBE: `k1/Check-K1A-EbxTextBytes.py`. Its output will distinguish
whether the observed `FDB471D8` index is consistent with reading
original code-section bytes at the fault-time EBX. This does NOT prove
whether EBX was wrong on entry or clobbered later. No runtime bypass,
new Xbox build, or relaxed guest memory fences.
### XBE byte-differential result: NO match (2026-10-29)

- The owned exact-SHA XBE original `.text` dwords at guest EBX
  `00041D70` are `00041D59` and `04020100`.
- Their difference is `FC021C59`, NOT the fault-time
  `[EBP-12]` / EDX value `FDB471D8`. Therefore the narrow hypothesis
  that unmodified original code bytes at fault-time EBX generated this
  index is **NOT CONFIRMED**.
- Do not jump from that negative result to a proven ABI corruption.
  The function captures its index **before** calling allocation and
  physical-memory services, while fault-time EBX is **after** those calls.
  Guest memory mutation is also unexcluded.
- One-shard diagnostic stage `k1/Stage-K1A-DsoundIndexTrace.py` now
  snapshots the object dwords, original index/base, computed ESI, and
  registers before/after ordinal 173. It leaves 63 TrueTU shards
  SHA-identical and the original 64-shard build intact.
- Synthetic stage test and fail-closed incremental builder are committed;
  no one-shard diagnostic Xbox run has been claimed as successful yet.
### 2026-10-30: DSINDEX on-hardware operand proof

- New `ENTRY`/`LEA`/`PRE173`/`POST173` checkpoints all reached Xbox.
- Original `[00041D70]` XBE first dword `00041D59` became live
  `01B672D8` while `[00041D74]` stayed `04020100`. Their difference
  is exactly `FDB471D8`; the audio page table base `024A8000` plus
  eight times this negative index gives faulting ESI `EFEE0EC0`.
- PRE173/POST173 EBX/ESI/ESP all **identical**. Ordinal 173 is
  definitively not the source of those changed registers at this site.
- The index is already bad before the 393216-byte allocation and
  physical-memory calls. Need determine why guest `[00041D70]` changed.
- New `k1/Stage-K1A-DsoundWriterWatch.py` and
  `k1/Build-K1A-DsoundWriterWatch.ps1`: watch guest writes overlapping
  `00041D70..00041D77` in all three scalar widths while retaining
  K1A and DSINDEX. No build/runtime pass has been claimed yet.

### 2026-10-30 DSOBJECT writer-watch console outcome

- The attached xbWatson run still fences at **27,029,593 ticks**,
  `READ32 EFEE0EC4` with `ESI EFEE0EC0` and `EBX 00041D70`.
- All four DSINDEX checkpoints execute, with the same bad entry
  `obj_first=01B672D8 obj_second=04020100 delta=FDB471D8`.
- **Zero `K1A DSOBJECT WRITE` records** are present in the 3,402-line
  console log. The run prints the K1A clock boot marker but no
  distinct DSOBJECT boot marker; the missing writes are therefore
  NOT proof that no write happened or that a native memcpy caused it.
- No further guest display progress: `display_calls=0`,
  `framebuffer=00000000`, no game pixels.
- The previous instrumentation was restricted to APU write helpers.
  An additional read-only source audit
  `k1/Audit-K1A-DsoundWriterCoverage.py` enumerates separate
  `GUEST_WRITE*`, other host writer and bulk-copy call sites in the
  actual staged 64 TrueTUs and runtime header before attempting
  another expensive XDK compilation. Its counts are lexical,
  NOT executed-write evidence.
- Next instrumented build MUST contain a unique runtime-visible
  DSOBJECT boot watermark and validate the writer owner in the
  actual compiled source; do not bypass the guest-memory hard fence.

## K1A — system clock and calendar conversion (one 100ns model)

| Ordinal | Export | Original Xbox export stack hint | Evidence |
|---|---|---:|---|
| 128 | KeQuerySystemTime | 4 bytes | Actual R76 hardware stop, target 80000080, tick 26,720,251 |
| 304 | RtlTimeFieldsToTime | 8 bytes | Imported; no explicit current route detected |
| 305 | RtlTimeToTimeFields | 8 bytes | Imported; no explicit current route detected |

- Reuse existing phase4c_system_time_100ns() semantics rather than inventing
  a second epoch, force-zero clock or blanket-success return.
- Date/time conversion and system-time query share one tested signed 64-bit
  100ns epoch (January 1, 1601 UTC). Check actual TIME_FIELDS structure.
- Verify each **guest** callsite's stack, post-call ESP, output pointer, return
  registers and guest-memory bounds before generated-code changes.
- The original Xbox stdcall decoration is an argument-size HINT only.
- Test leap-year boundaries, invalid calendar values, null/unmapped pointer
  hard fences and 100ns round trips before any XDK compilation.
- Implement as one central typed subsystem bridge, not 3 quickpatches.

## K1B — event, timer, DPC and thread lifecycle (shared state)

| Ordinal | Export | Initial coverage |
|---|---|---|
| 97 | KeCancelTimer | No explicit detected route |
| 119 | KeInsertQueueDpc | No explicit detected route |
| 137 | KeRemoveQueueDpc | No explicit detected route |
| 145 | KeSetEvent | No explicit detected route |
| 159 | KeWaitForSingleObject | No explicit detected route |
| 225 | NtSetEvent | No explicit detected route |
| 233 | NtWaitForSingleObject | No explicit detected route |
| 234 | NtWaitForSingleObjectEx | No explicit detected route |
| 258 | PsTerminateSystemThread | No explicit detected route |

- Reconcile existing runtime/host services first. Do not duplicate working
  handlers or mistake uncalled services for observed faults.
- Model event signaled/reset state, wait result and timeouts, DPC queue
  membership and thread exit coherently across these APIs.
- Distinguish real success, timeout and unsupported blocking/callback state.
- Test nested guest ABI and state transitions; preserve unknown hard fences.
- Do not fake interrupt delivery, callbacks or guest-thread scheduling.

## Separate compatibility waves (not part of the clock patch)

- IO manager and file operations: IRP queues, completion, directory/FSCTL.
- GPU memory and APU/NV2A MMIO: real registers and device state.
- Crypto SHA/HMAC: all four exports with standard public test vectors;
  never log or invent Xbox private key material.
- Data exports such as XboxHDKey: audit pointer/value relocation, not calls.
- Fatal exceptions and hardware shutdown: preserve fail-stop semantics.

## Acceptance criteria for first executable batch

1. Audit ALL K1A/K1B callers and existing dispatcher/host handler routes.
2. Write one time/date core and one event/wait core with exact guest ABI.
3. Pass offline regression fixtures for the **entire class**, including
   100ns values, stack deltas, pointer boundaries and object transitions.
4. Apply changes through a central compatibility layer over the existing
   R76-tested main, leaving the 64 TrueTU translated shards untouched.
5. Compile incrementally once and perform one Xbox hardware integration
   test. Prove R72 DirectSound and R76 APU regressions remain cleared.
6. Update the existing map/ledger. Explicitly mark any unsupported
   callbacks, waits and interrupt paths as OPEN, never successful.

Not a claim that these functions have been implemented or hardware-tested.
Phase 6 completes only with genuine rendered game graphics and reproducible
menu/scene behavior, not raw translated ticks.
