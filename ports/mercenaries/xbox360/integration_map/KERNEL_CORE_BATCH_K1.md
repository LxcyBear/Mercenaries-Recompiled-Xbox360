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

### K1B source-level causality candidate (2026-10-30)

Offline exact source report confirms `recomp_guest_write8/16/32/64/128`
as five central store implementations in K1A staged `main.cpp`.
`GUEST_WRITE*` macros route there. The two literal address references
are a descriptor payload `GUEST_WRITE32(eax+8,0x41D70)` and an
unrelated jump-table lookup byte at `0x41D74`; neither is direct
proof of a write to `0x41D70`.

New K1B runtime-watch stage and XDK wrapper are committed with an
independently boot-visible mark. Preserves R76, K1A, 64 TrueTUs,
DSINDEX checkpoints and `EFEE0EC4` hard fence. Actual Xbox
compiler/hardware success remains UNVERIFIED until user runs it.

### K1B HARDWARE PASS -> K1C writer-site diagnosis (2026-10-30)

- Real Xbox boot identifies K1B; one central `recomp_guest_write32`
  executed at guest `00041D70`, changing `00041D59 -> 01B672D8`.
- Value matches `RtlAllocateHeap(2400) result=01B672B0 + 0x28`.
- Previous trace-ring caller `0023A3CE` is not an exact instruction VA.
- No increase over `ticks=27029593 trace=1072569`; same hard
  fence at `READ32 EFEE0EC4`, display still uninitialized.
- K1C staged as isolated main-only diagnostic XEX with 5 writer
  probes logging `guest_va` from existing `s_phase6cpCurrentVa`.
  Candidate VA is a last-translated-VA tracker, not proof of
  exact store-site PC until verified against translated body.
- Preflight and build scripts preserve R76/K1B provenance, the
  64 true TU files, and hard-fenced memory rules. Pending real
  VS2017 build and hardware run; no milestone claimed yet.

### K1C pre-XDK source mismatch corrected (2026-10-30)

The initial K1C stage failed before Xbox build, despite passing the
synthetic test: the actual K1B generated source defines global
`s_phase6cpCurrentVa` **after** the central writer functions.
The corrected stage keeps that state declaration in place and adds
one earlier prototype for a later-defined read-only helper. Five
central logging messages call it to sample the last guest VA.
Tests now model actual late tracker placement and the original early
fixture; staging and XDK/hardware validation are still pending.
The 27,029,593-tick hard fence and no-pixels status remain unchanged.

### K1C Xbox PASS / K1D targeted source audit (2026-10-30)

K1C executed on hardware with its unique boot marker. At the previously
identified `recomp_guest_write32` to `00041D70`, captured
`guest_va=0027DD0C` (within retail XACTENG section). Wrote
`01B672D8`, exactly heap allocation `01B672B0+0x28`. The
old `trace_caller=0023A3CE` is broad; the guest-VA tick
is much narrower but still not proven to be the exact store PC.
Destination lies within original retail .text. Need identify
destination register arithmetic and verify whether this is an
expected data write or an ABI/pointer bug. No memory bypass.

The SAME hard fault `READ32 EFEE0EC4` remains at
`ticks=27029593 trace=1072569`, no display/framebuffer.
`Inspect-K1D-XactWriteSite.py` + synthetic test are committed
for an **offline, read-only** window around `loc_0027DD0C`
across the frozen 64 translated shards, with input SHA checks.
Await actual source report before code mutation or another XDK build.

### K1D list-link source explanation; K1E one-shard tail-value witness

K1D confirms `loc_0027DD0C` in `translated_029.cpp`,
function `sub_0027DC5B`: translates XACTENG linked-list
insertion into a newly allocated entry `eax=heap+0x28`.
The original code loads the previous tail through
`ecx = GUEST_READ32(ebx+0x78)`, writes
`GUEST_WRITE32(ecx,eax)`, then writes the new entry into
`GUEST_WRITE32(ebx+0x78,eax)` (head->Blink). K1C
witnessed destination `00041D70` in the original XBE
`.text`, but both stores share the same last-tick VA.
K1E distinguishes the two candidate destinations with
`tail_hits_41D70` / `head_hits_41D70`, BEFORE choosing
whether old tail or list head is wrong. This does NOT yet
prove the root cause of the later `EFEE0EC4` fault.

K1E synthetic + staging/build scripts now target the precise
source statement in **one** of the 64 true TUs, log `ebx/head/`
`tail/node` before the write, and preserve the original guest
load and store. All other translated files are hash-verified
unchanged, with no XDK Clean requested. Actual local staging,
VS17 compiler, console runtime and tick improvements are
pending user verification. Hard fence remains active.

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
