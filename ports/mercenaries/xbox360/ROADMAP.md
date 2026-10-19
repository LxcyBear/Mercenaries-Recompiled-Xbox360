# Mercenaries Xbox 360 Native Port Roadmap

Snapshot: 2026-10-19.

This roadmap tracks the native Xbox 360/Xenon port of *Mercenaries: Playground of Destruction*.
Milestones are evidence-based: a hardware harness proves only the bounded surface it executes;
full translated-game startup is a separate gate.

## Completed

### Phase 1-2 — Xenon bring-up and execution environment
- Established the XDK/XEX hardware test path on a modified Xbox 360.
- Proved guest-memory ownership/mapping and the execution-environment foundations used by later translated-code gates.

### Phase 3 — Recompiler ABI
- Completed on real Xenon hardware.
- Final Phase 3N-B gate compiled/linked a 128-function audited translated-code scale pack.
- Verified translated anchors live in the loaded XEX.
- Passed maintained x87 rounding/exception checks.
- Passed six independent-reference executions of retail function `0x00208F30`.
- Returned through XAPI with result 0.

### Phase 4A — Guest kernel surface and ABI audit
**Status: locked PASS.**

Verified against retail XBE SHA-256:

`AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7`

Locked baseline:
- 111 exact retail kernel imports
- 74 explicit guest bridges
- 11 guest data exports
- 26 return-zero fallbacks
- 0 missing guest argument-cleanup entries
- 0 guest argument-cleanup mismatches
- 0 statically referenced fallbacks in the preserved Phase-3N generated tree
- 17 genuine semantic host-backed callable paths after exact call-path filtering

### Phase 4B-A — Native Xenon timing/synchronization hardware proof
**Status: PASS on real Xbox 360 hardware.**

Build: `P4B-TIMESYNC-20261019-B`

Hardware evidence:
- QPC frequency: 50,000,000 Hz and monotonic
- 20 ms relative delay: 20,304 us
- 2 ms processor stall: 2,000 us
- 20 ms wait timeout: 20,062 us
- one-shot timer request-to-signal: 39,748 us
- event signal/wait/auto-reset behavior: PASS
- one-shot timer delivery: PASS

Covered imported service paths:
- `KeQuerySystemTime`
- `KeSetTimer`
- `KeDelayExecutionThread`
- `KeSetEvent`
- `KeWaitForSingleObject`
- `KeStallExecutionProcessor`

### Phase 4B-A2 — Integrate hardware-proven timing/sync backend
**Status: PASS.**

The six timing/synchronization paths are routed through
`src/platform/kernel_time_sync.*` via `merc_platform_*` calls.

Verification result:
- 11 remaining direct semantic host-backed imports
- 6 Phase-4B platform-bound imports
- 0 ABI metadata errors
- 0 statically referenced fallbacks
- 7,722 precise deadline/phase cases: PASS
- guest-kernel ABI regression: PASS
- Phase-4B platform-boundary regressions: PASS

Gate:
`ports/mercenaries/xbox360/phase4b_native_time_sync_xex/Verify-Phase4B-A2.ps1`

Phase 4B-A/A2 is complete.

### Phase 4B-B — Native file/handle service slice
**Status: PASS on real Xbox 360 hardware.**

Hardware gate:
`ports/mercenaries/xbox360/phase4b_native_file_handles_xex`

Build marker:
`P4B-FILE-20261019-A`

Hardware PASS covered:
- test directory create/existing;
- create/overwrite;
- write + flush;
- size and handle-information query;
- absolute seek and current-position observation;
- full and explicit-offset reads;
- EOF truncate and preserved size after reopen;
- path attributes;
- directory enumeration;
- missing-file failure/not-found semantics;
- file/enumeration close and cleanup.

The cohesive retail file/handle surface includes:
- `NtCreateFile`
- `NtOpenFile`
- `NtReadFile`
- `NtWriteFile`
- `NtSetInformationFile`
- `NtQueryInformationFile`
- `NtQueryDirectoryFile`
- `NtQueryFullAttributesFile`
- `NtClose`

Phase 4B-B hardware proof is complete.

### Phase 4B-B2 — Integrate hardware-proven file/handle backend
**Status: PASS.**

The nine file/handle import paths route through
`src/platform/kernel_file_io.*` via `merc_platform_file_*`.

Verification result:
- 2 remaining direct semantic host-backed imports;
- 15 Phase-4B platform-bound imports;
- 0 ABI metadata errors;
- 0 statically referenced fallbacks;
- 7,722-case timing/deadline regression: PASS;
- guest-kernel ABI regression: PASS;
- time/sync platform-boundary regression: PASS;
- file/handle platform-boundary regression: PASS.

Gate:
`ports/mercenaries/xbox360/phase4b_native_file_handles_xex/Verify-Phase4B-B2.ps1`

Phase 4B-B/B2 is complete.

### Phase 4B-C — Remaining memory/protection and residual host surface
**Status: PASS on real Xbox 360 hardware.**

Hardware gate:
`ports/mercenaries/xbox360/phase4b_native_memory_protection_xex`

Build marker:
`P4B-MEMPROT-20261019-B`

Current exact worklist:
- `NtFreeVirtualMemory`
- `MmSetAddressProtect`

Build A passed all substantive guest-owned memory/protection semantics; its lone final failure was a test-ordering bug because the released VA had already been reused. Build B corrected that ordering and passed completely. The hardware proof covers:
- page-aligned bounded guest allocation;
- logical page protection metadata;
- multi-page protection updates;
- logical decommit/recommit state;
- whole-allocation release;
- released-range reuse and zero initialization;
- invalid-range and double-release rejection.

Phase 4B-C hardware proof is complete.

### Phase 4B-C2 — Final memory/protection runtime integration
**Status: PASS.**

The real guest bridge now:
- allocates virtual memory from the page-rounded/page-backed guest allocator;
- commits/decommits logical guest pages through guest metadata;
- releases virtual memory through the same tracked guest allocator;
- applies `MmSetAddressProtect` to page-granular guest protection metadata.

Final verification result:
- 0 direct semantic host-backed imports;
- 15 Phase-4B platform-bound imports;
- 2 guest-native memory/protection imports;
- 0 ABI metadata errors;
- 0 referenced fallbacks;
- 7,722-case timing/deadline regression: PASS;
- guest-kernel ABI regression: PASS;
- time/sync platform-boundary regression: PASS;
- file/handle platform-boundary regression: PASS;
- six guest-memory ownership regressions: PASS.

Gate:
`ports/mercenaries/xbox360/phase4b_native_memory_protection_xex/Verify-Phase4B-C2.ps1`

**Phase 4B service migration is complete.** The 17 semantic host-backed paths
from the locked Phase-4A baseline now account as 15 platform-bound + 2
guest-native + 0 direct host-backed.

## Active

### Phase 4C — Native translated-game startup path
Begin linking/executing the real translated Mercenaries startup path with the migrated Xenon service layer.

#### Phase 4C-A — Retail entry-rooted startup preflight
**Status: PASS.**

Entry:
`0x0022964A`

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Analyze-Phase4C-A.ps1`

The preflight reuses the exact locked Phase-3N-A generated tree and refuses to
continue unless the Phase-4B final service audit remains
`0 direct / 15 platform-bound / 2 guest-native`.

Result:
- retail entry: `0x0022964A`;
- exact translated symbol: `xbe_entry_point`;
- 40 directly reachable translated bodies;
- maximum direct-call depth 8;
- 5,918 guest code bytes;
- 111,376 generated source bytes;
- 0 missing direct translated dependencies;
- 14 bodies containing dynamic/indirect dispatch boundaries.

No retail code was executed by 4C-A.

#### Phase 4C-B — First bounded real translated startup execution
**Status: PASS on real Xbox 360 hardware.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-B.ps1`

The local emitter combines:
- the exact Phase-2E retail XBE loader/TIB/TLS/stack/kernel-data environment;
- the hardware-proven Phase-3N translated ABI/runtime support;
- all 40 entry-rooted translated bodies from the locked local generated tree.

The first runtime intentionally escapes at the first live `RECOMP_ICALL`,
`RECOMP_ICALL_SAFE`, `RECOMP_ITAIL`, or `RECOMP_ITAIL_SAFE` boundary.
That makes the first dynamic target, caller, stack and register state the next
deterministic xbWatson evidence instead of silently stubbing unresolved startup
behavior.

Required evidence:
- real retail-derived translated entry/startup code executes;
- required guest-kernel calls resolve through native/platformized paths;
- deterministic xbWatson checkpoints identify progress/failure boundaries;
- no claim of gameplay until the title reaches its own runtime milestones.

### Phase 5 — Subsystem bring-up under native game execution
After native startup is established, advance the title through the runtime subsystems demanded by the real boot path:
- storage/content and saves
- threading/async completion
- graphics/NV2A/D3D presentation
- input
- audio/APU/XACT/DirectSound
- movie/XMV
- remaining kernel/platform behavior discovered by live execution

Prioritize blockers observed on real hardware rather than porting unused desktop/runtime surfaces.

### Phase 6 — First interactive native milestone
Target a reproducible title-controlled state on Xbox 360 hardware, such as:
- boot/logo/movie path;
- main menu;
- or another deterministic interactive checkpoint reached by the real translated game.

The exact milestone depends on the first stable startup path reached in Phase 5.

### Phase 7 — Gameplay and compatibility hardening
Once real gameplay executes:
- mission/world streaming
- save/load
- audio/video synchronization
- rendering correctness
- controller behavior
- memory pressure/fragmentation
- long-session stability
- performance profiling and optimization

## Evidence rules

- Static audit PASS is not hardware execution.
- Standalone XEX hardware PASS proves only the bounded services tested by that XEX.
- Runtime platformization is not complete until regressions/audit are green.
- Native translated-game startup is not gameplay.
- Gameplay claims require the real translated title path to reach and sustain an interactive game state on hardware.
- Update this roadmap and `CODE_MAP.md` whenever a phase gate changes state.


#### Phase 4C-C — First startup-thread handoff
**Status: active.**

Phase 4C-B hardware evidence:

```text
[Merc360:P4C] PASS: entering real translated xbe_entry_point now
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022B4D7 target=800000FF esp=008BFF98 saved_esp=008BFFC4 ticks=5 trace=2
[Merc360:P4C] BOUNDARY REGISTERS: ... fault=0
[Merc360:P4C] trace[0]=0022964A
[Merc360:P4C] trace[1]=0022B4D7
[Merc360:P4C] PHASE 4C-B BOUNDED REAL STARTUP RESULT: PASS
```

`0x800000FF` is Xbox kernel ordinal 255, `PsCreateSystemThreadEx`.
The observed stack delta is `0x2C` bytes, exactly matching its 40 bytes of
stdcall arguments plus the synthetic four-byte CALL return slot.

4C-C will decode that live frame, log the actual StartRoutine and two contexts,
write the synthetic thread handle, enter the translated first thread routine
synchronously using the production bridge model, and stop at the next live
dynamic/kernel boundary.


4C-C preparation gate:

`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-C.ps1`

The 4C-C emitter preserves the hardware-proven 4C-B package and writes a new
two-source package under `build/phase4c_native_startup/thread_xdk`. It packs
the maintained startup roots `0x0022B43F` and `0x002295D6` plus their direct
generated closures. Runtime still validates the actual ordinal-255 StartRoutine
before entering it.


### 4C-C scope correction

The first 4C-C emitter recursively packed both maintained startup candidates and
therefore pulled a very large portion of the title graph into the XDK package
before hardware had identified the live StartRoutine. Its helper-surface audit
correctly refused to emit.

4C-C is now intentionally narrower:

- reuse the exact 40-body 4C-B translated entry closure;
- intercept only `0x800000FF` / ordinal 255;
- require the already hardware-proven 44-byte frame shape;
- decode and log all ten `PsCreateSystemThreadEx` arguments;
- capture the actual StartRoutine, context1, and context2;
- stop successfully at a `THREAD_TARGET` evidence boundary.

Build tag: `P4C-THREAD-20261019-B`.

The following phase will package only the StartRoutine actually observed on
hardware, avoiding speculative expansion into renderer/audio/XACT/XInput code.


#### Phase 4C-C — Live startup-thread handoff capture
**Status: PASS on real Xbox 360 hardware.**

Hardware result:

```text
PsCreateSystemThreadEx LIVE FRAME:
  handle_ptr=008BFFD0
  extra=0
  kstack=262144
  tls=20
  tid_ptr=00000000
  ctx1=002295D6
  ctx2=00000000
  suspended=0
  debug=0
  routine=0022B43F

BOUNDARY: kind=THREAD_TARGET caller=0022B4D7 target=0022B43F
fault=0
PHASE 4C-C LIVE THREAD-HANDOFF CAPTURE RESULT: PASS
```

The live hardware frame exactly matches the maintained startup metadata:
`0x0022B43F` is the routine passed to `PsCreateSystemThreadEx`, while
`0x002295D6` is its first context.

#### Phase 4C-D — Hardware-observed first title-thread preflight
**Status: ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Analyze-Phase4C-D.ps1`

4C-D roots only at the hardware-observed StartRoutine `0x0022B43F`. It
measures that routine's direct translated closure, dynamic/indirect boundaries,
and non-translated helper surface before emitting the first thread-execution
slice. Context values are pinned to the live 4C-C result:
`ctx1=0x002295D6`, `ctx2=0`.


#### Phase 4C-D — Hardware-observed first title-thread preflight
**Status: PASS.**

Report:
`build/phase4c_native_startup/phase4c-thread-routine.txt`

Result:

```text
StartRoutine: 0x0022B43F
Context1:     0x002295D6
Context2:     0x00000000
Entry resolution: exact_function
Reachable direct translated bodies: 6
Maximum direct-call depth: 2
Reachable retail guest bytes: 460
Reachable generated source bytes: 8556
Missing direct translated dependencies: 0
Dynamic/indirect boundary bodies: 5
STRUCTURAL RESULT: PASS
```

The raw helper inventory is limited to the already-proven translated ABI/support
surface plus the canonical manual `SetLastError` wrapper, guest REP MOVS and
bounded debug-break support. No new broad renderer/audio/XACT/XInput closure is
required for this gate.

#### Phase 4C-E — First real title-thread execution slice
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-E.ps1`

The package unions the 40-body Phase-4C-B entry closure with the 6-body
hardware-observed thread closure. Three translated bodies are new beyond the
already hardware-proven entry pack, for 43 unique translated bodies total.

Runtime policy:
- verify/load the exact supported retail XBE;
- enter real translated `xbe_entry_point`;
- intercept only the first `0x800000FF` / `PsCreateSystemThreadEx`;
- require the live handoff to remain
  StartRoutine=`0x0022B43F`, ctx1=`0x002295D6`, ctx2=0;
- enter `0x0022B43F` synchronously with the production bridge stack shape;
- stop at the first subsequent live ICALL/ITAIL boundary.

Build tag: `P4C-THREADRUN-20261019-A`.


#### Phase 4C-E — First real title-thread execution
**Status: PASS on real Xbox 360 hardware.**

Hardware trace:

```text
trace[0]=0022964A
trace[1]=0022B4D7
trace[2]=0022B43F
trace[3]=00239BE8
trace[4]=0022B363

BOUNDARY:
  kind=ICALL_SAFE
  caller=0022B363
  target=80000115
  esp=008BFF3C
  saved_esp=008BFF44
  ticks=11
  trace=5
  fault=0
```

`0x80000115` is kernel ordinal 277,
`RtlEnterCriticalSection(PRTL_CRITICAL_SECTION)`.

The observed stack delta is exactly 8 bytes:
- 4-byte critical-section argument;
- 4-byte synthetic CALL return slot.

The maintained kernel runtime intentionally implements guest critical-section
enter/leave/initialize as no-ops while guest execution is serialized. It does
not pass guest critical-section storage to host locks.

#### Phase 4C-F — Continue through first critical-section call
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-F.ps1`

4C-F validates the live ordinal-277 frame, records the guest critical-section
VA, performs the maintained serialized-guest no-op behavior, consumes the
synthetic CALL return and one stdcall argument exactly, and requires
`g_esp == saved_esp` before continuing.

Build tag: `P4C-CRITCONT-20261019-A`.


#### Phase 4C-F — Continue through first critical-section enter
**Status: PASS on real Xbox 360 hardware.**

Hardware evidence:

```text
RtlEnterCriticalSection LIVE FRAME:
  cs=00312FC0
  esp=008BFF3C
  saved_esp=008BFF44

PASS: ordinal 277 RtlEnterCriticalSection matched maintained serialized-guest semantics

BOUNDARY:
  caller=0022B363
  target=80000126
  esp=008BFF3C
  saved_esp=008BFF44
  ticks=14
  trace=5
  fault=0
```

`0x80000126` is kernel ordinal 294,
`RtlLeaveCriticalSection(PRTL_CRITICAL_SECTION)`. The observed frame delta is
again exactly 8 bytes.

#### Phase 4C-G — Continue through first critical-section pair
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-G.ps1`

The 43-body translated slice is unchanged. The gate now handles both ordinal
277 enter and ordinal 294 leave with the maintained serialized-guest no-op
semantics. Each call must have an exact 8-byte translated frame and restore
`g_esp == saved_esp` before execution continues.

Build tag: `P4C-CRITPAIR-20261019-A`.


#### Phase 4C-G — First critical-section pair
**Status: PASS on real Xbox 360 hardware.**

```text
RtlEnterCriticalSection  cs=00312FC0  PASS
RtlLeaveCriticalSection  cs=00312FC0  PASS

BOUNDARY:
  kind=ICALL_SAFE
  caller=0022B363
  target=002295D6
  esp=008BFF50
  saved_esp=008BFF58
  ticks=16
  trace=5
  fault=0
```

The target `0x002295D6` exactly matches the `ctx1` value captured from the
real `PsCreateSystemThreadEx` frame in Phase 4C-C. Hardware has therefore
proved that ctx1 is subsequently invoked as executable title-startup code.

The observed callback call frame is 8 bytes: one dword argument plus the
synthetic translated CALL return.

#### Phase 4C-H — Hardware-confirmed startup callback frontier
**Status: active.**

The full static closure rooted at `0x002295D6` is intentionally not linked as
one package: an earlier speculative attempt demonstrated that it recursively
pulls broad renderer/audio/XACT/XInput/runtime surfaces.

4C-H instead enters the real callback and uses a bounded translated frontier.
Only a small reviewed direct-call slice is packed. A translated direct call
outside that slice becomes a deterministic `DIRECT_FRONTIER` evidence
boundary with its exact target, while ordinary ICALL/ITAIL boundaries remain
observable as before.


4C-H preparation gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-H.ps1`

The package preserves the 43-body hardware-proven entry/thread slice and adds
the hardware-confirmed callback `0x002295D6` plus its immediate translated
callees only (direct depth 1, cap 64). Calls to translated functions outside
that bounded slice are rewritten to deterministic `DIRECT_FRONTIER` escapes
after the real translated argument pushes and synthetic CALL return push have
already occurred.

Build tag: `P4C-CALLBACK-20261019-A`.


#### Phase 4C-H — Hardware-confirmed startup callback entry
**Status: callback entry proven; execution gate blocked by guest-memory fault.**

Real Xbox 360 trace:

```text
STARTUP CALLBACK LIVE FRAME:
  target=002295D6
  arg0=00000000
  esp=008BFF50
  saved_esp=008BFF58

PASS: entering hardware-confirmed translated startup callback 002295D6

BOUNDARY:
  kind=GUEST_FAULT
  caller=0022C4DF
  target=0022C4FF
  esp=008BFF48
  saved_esp=008BFF48
  ticks=19
  trace=7
  fault=1

trace[5]=002295D6
trace[6]=0022C4DF
```

The balanced stack at the fault boundary argues against an immediate
translated-call ABI collapse. The current harness only records the boolean
`s_accessFault`, so `0x0022C4FF` identifies the translated execution point
where the fault is observed, not the rejected guest memory address itself.

#### Phase 4C-I — First guest-fault provenance
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-I.ps1`

4C-I preserves the exact H execution slice and does not broaden guest-memory
mapping. The first rejected access records:
- guest address;
- READ vs WRITE;
- access width (1/2/4/8/16 bytes);
- translated caller captured by the existing boundary trace.

The diagnostic counts as a successful provenance capture only when the real
startup callback was entered and a concrete first-fault width was recorded.

Build tag: `P4C-FAULTPROBE-20261019-A`.
