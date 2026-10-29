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
