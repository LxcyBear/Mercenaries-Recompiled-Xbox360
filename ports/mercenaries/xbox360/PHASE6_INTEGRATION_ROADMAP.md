# Phase 6DQ Diagnostic Freeze — Phase 6 Integration Map

**Decision: October 29, 2026.**

This document closes the Phase 6DQ **micro-revision/debugging loop**, not the
Phase 6 graphics milestone. Preserve the R76 tested runtime and the R77
source-only audit. Do not imply the game is playable or graphics are complete.

## Evidence at the freeze point

- R72 Xbox hardware: true DirectSound free-list head restored, pool allocation
  succeeded, XACT initialization returned success.
- R76 Xbox hardware: FE80200C (NV_PAPU_XGSCNT) read routed through the existing
  APU core shadow; previous guest-memory hard stop eliminated.
- The next hardware stop is ICALL_SAFE target 80000080 at tick 26,720,251.
  The target corresponds to Xbox kernel ordinal 128, KeQuerySystemTime.
- R77 is a zero-build **source audit**, not another hardware test. It found an
  existing FILETIME/100ns clock helper named phase4c_system_time_100ns, a
  111-entry retail kernel import thunk table scanner, and fragmented indirect
  kernel dispatch routing. It found no KeQuerySystemTime handler.
- Guest display_calls=0 and framebuffer=00000000 in the latest hardware result.
  The blue/orange backgrounds are diagnostic screens, NOT game pixels.
- The 64,000,000-block watchdog is a diagnostic limit, not a completion target.

## Map -> Log -> Batch patch -> Validate -> Map

1. **MAP:** Inventory all 111 genuine retail import *slots* (separate data
   imports from callable entries), existing kernel dispatcher routes, MMIO
   addresses and access widths, translated call paths, and ABI-risk sites.
   Distinguish static potential from hardware-observed behavior.
2. **LOG:** Record first unique fault per caller/target/kind, its context,
   frequency, module, build identity and source-log SHA. Deduplicate repeated
   logs; keep known unhandled operations in a persistent backlog.
3. **BATCH PATCH:** Group root causes by (A) kernel imports & timers/sync,
   (B) systemic x86 guest register/stack ABI, (C) APU/AC97/NV2A MMIO,
   (D) storage/asset/streaming, (E) guest D3D to native Xenos. Prefer
   shared service/emitter fixes over one translated function at a time.
4. **VALIDATE:** Offline function/ABI and compatibility fixtures for the
   complete batch, then incremental true-TU build. Require one real Xbox
   integration run to prove the whole group and catch regressions.
5. **RE-MAP:** Update the same coverage map and fault ledger; carry open
   issues forward and do not spawn another 6DQ letter or number for each one.

### Mandatory evidence levels

- IMPORT_PRESENT: exact retail XBE thunk slot exists.
- ROUTE_PRESENT: runtime source has an explicit dispatch path.
- SEMANTICS_TESTED: guest stack, output pointers, return value and state
  changes passed offline fixture tests.
- HARDWARE_PASS: native Xbox 360 test demonstrated correct behavior.
- Subsystem milestone: real game-origin calls and resource state, not a
  diagnostic display. None of these statuses is implied by the prior level.

## Batch acceptance gates

**Kernel:** account for exactly 111 retail import slots, distinguish
callable/data exports and implement used API contracts with real side
effects, including ordinal 128 and any related time/synchronization calls.
Maintain unknown-target hard fencing. The 111 entries do not imply 111
different unimplemented functions.

**Guest ABI:** compare caller/callee register and stack invariants across a
representative set of nested calls including the R72 audio constructor.
Fix genuinely systemic errors at emitter level and verify with independent
fixtures before regenerating the full source corpus.

**MMIO:** cover observed register families and widths in one model, with
documented read/write semantics and clock dependencies; retain hard fences
for unmodeled accesses, never return blanket zero/success.

**Graphics:** phase Gate 6 requires independently confirmed guest D3D
device and display-mode flow, valid game-owned Xenos render surface, an
actual presented game frame on real hardware, and repeatable menu/scene
rendering. Xenos-ready=1 alone does not satisfy this gate.

**Build:** preserve the 64 TrueTU caches; compile only changed units when
possible. Game bytes, translated retail code, XDK contents and full raw
logs must never be committed to the public repository.

## Source references for the freeze

- R76 Xbox log: previously verified runtime watermark and XGSCNT router
  marker, then ICALL_SAFE 80000080.
- R77 audit (2026-10-29): source-only 2328-line report, confirms no
  KeQuerySystemTime implementation in cached main and confirms existing
  phase4c_system_time_100ns helper.
- Phase 6DQ rocket emitter: distinct RECOMP_ICALL_SAFE and packed
  phase5bc_dispatch_packed_icall routes, with individual kernel cases.
- Retail XBE identity SHA256:
  AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7

The first consolidation milestone is the fully reviewed inventory and
batched compatibility plan. It requires no Xbox rebuild, and it is NOT
the same as claiming Phase 6 complete.
