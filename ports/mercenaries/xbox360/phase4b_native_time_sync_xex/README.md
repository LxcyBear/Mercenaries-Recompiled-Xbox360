# Phase 4B-A — Native Xenon timing/synchronization gate

**Status: Phase 4B-A hardware PASS; Phase 4B-A2 runtime platformization ready for verification.**

Phase 4A is locked: the verified Mercenaries retail XBE imports 111 kernel
symbols, the translated guest path exposes 74 explicit bridges and 11 guest
data exports, all guest stack-cleanup metadata matches, and the corrected
semantic audit leaves 17 genuinely host-backed callable paths.

Phase 4B removes those host dependencies in bounded hardware-proven slices.
4B-A starts with timing and synchronization because those services are
foundational for later file I/O, worker-thread, and startup work.

## Services represented by this gate

The first conversion slice covers the native primitives needed by:

- `KeQuerySystemTime` (128)
- `KeSetTimer` (149)
- `KeDelayExecutionThread` (99)
- `KeSetEvent` (145)
- `KeWaitForSingleObject` (159)
- `KeStallExecutionProcessor` (151)

Build `P4B-TIMESYNC-20261019-B` passed on real Xenon hardware. Phase 4B-A2
now routes the corresponding runtime clock/sleep/stall/event/wait operations
through `src/platform/kernel_time_sync.*`. The surface audit reports these
imports as Phase-4B platform-bound rather than direct host-backed calls.

## Hardware checks

The gate validates:

- non-zero QueryPerformanceCounter frequency;
- monotonic performance counter;
- system time advances across a bounded sleep;
- original-Xbox negative 100-ns relative interval conversion;
- a ~20 ms relative delay;
- a ~2 ms QPC-backed processor stall;
- auto-reset event creation;
- SetEvent + WaitForSingleObject behavior;
- zero-timeout behavior before and after event consumption;
- a bounded ~20 ms wait timeout;
- one-shot timer delivery through an Xbox 360 worker thread + event;
- timer-event auto-reset behavior.

Timing tolerances are intentionally broad. This is a semantic hardware gate,
not a scheduler benchmark.

## Build marker

```text
P4B-TIMESYNC-20261019-B
```

A successful xbWatson run must include:

```text
[Merc360:P4B] PASS: QueryPerformanceFrequency available
[Merc360:P4B] PASS: performance counter is monotonic
[Merc360:P4B] PASS: system time advances
[Merc360:P4B] PASS: relative 20ms delay
[Merc360:P4B] PASS: 2ms processor stall
[Merc360:P4B] PASS: wait observes signaled event
[Merc360:P4B] PASS: 20ms wait returns timeout
[Merc360:P4B] PASS: one-shot timer signals event
[Merc360:P4B] PHASE 4B-A NATIVE TIME/SYNC RESULT: PASS
[XAPI RETURN VALUE] 0
```

## Preparation

First update to the Phase 4B branch, then from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4b_native_time_sync_xex\Prepare-Phase4B-A.ps1"
```

The preparation command refuses to proceed unless the local Phase-4A JSON
still matches the locked gate:

```text
111 imports
74 explicit bridges
11 guest data exports
26 fallbacks
17 semantic host-backed paths
0 missing argument-cleanup entries
0 argument-cleanup mismatches
0 statically referenced fallbacks
```

It writes the compile-ready source to:

```text
build\phase4b_native_time_sync\main.cpp
```

Compile that `main.cpp` in the existing known-good VS17/XDK diagnostic
project, deploy the resulting XEX, and send the complete xbWatson transcript.

## Stop conditions

Do not wire these backends into the real bridge if:

- QPC/frequency is unavailable or non-monotonic;
- system time does not advance correctly;
- relative delay or timeout semantics fail;
- SetEvent/wait/auto-reset behavior differs;
- the timer worker does not signal reliably;
- the XEX crashes or fails to return normally.

After a hardware PASS, Phase 4B-A2 replaces the six host-backed runtime paths
behind a platform boundary and runs a focused regression/audit before the
file/handle slice.


## Hardware result — October 19, 2026

Build `P4B-TIMESYNC-20261019-B` passed on modified Xbox 360 hardware.

Observed values:

- QPC frequency: 50,000,000 Hz and monotonic;
- 20 ms relative delay: 20,304 us;
- 2 ms processor stall: 2,000 us;
- 20 ms wait timeout: 20,062 us;
- one-shot timer request-to-signal: 39,748 us;
- event set/wait/auto-reset and timer delivery: PASS.

The 39.748 ms one-shot result includes Xenon thread scheduling overhead; the
bounded semantic gate requires correct signal delivery and a plausible due
time, not a scheduler benchmark.

## Phase 4B-A2 verification

After updating the branch, run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4b_native_time_sync_xex\Verify-Phase4B-A2.ps1"
```

The verifier reruns the retail import audit and requires:

```text
host_surface=11
platform_bound=6
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```

It also runs the guest wait-deadline regression, the guest-kernel ABI metadata
regression, and the Phase-4B time/sync platform-boundary regression.
