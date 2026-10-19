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

Build tag: `P4C-FAULTPROBE-20261019-B`.


##### Phase 4C-I Build A diagnostic harness correction

The first provenance probe reached the real startup callback but then hung
before producing the expected fault record. Review found the diagnostic
transform searched loosely for accessor names such as
`recomp_guest_read32(`, which can occur before the accessor definition in
support code. That made the rewrite position-sensitive.

Build B replaces only exact accessor definition/body fragments and emits
`FAULT ACCESS IMMEDIATE: READ|WRITE width=N guest=XXXXXXXX` inside the
rejecting accessor before the existing fault path continues. Guest mapping
semantics are unchanged.

Build tag: `P4C-FAULTPROBE-20261019-B`.


### Phase 4C-I revision B

The first I hardware run reached the confirmed callback but stalled before a
bounded result. This is classified as a diagnostic-harness issue rather than a
new title-startup result.

Revision B:
- matches exact guest accessor function bodies;
- records the first rejected address, width and direction;
- arms immediate fault escape only after the driver's `setjmp` is active;
- immediately exits with `GUEST_FAULT` from the failing accessor;
- does not broaden or alter guest-memory mappings.

Build tag: `P4C-FAULTPROBE-20261019-B`.


#### Phase 4C-I Build B — First rejected guest-access provenance
**Status: PASS on real Xbox 360 hardware.**

```text
FAULT ACCESS IMMEDIATE: READ width=4 guest=80000142
BOUNDARY: kind=GUEST_FAULT caller=0022C4DF target=80000142
FAULT ACCESS: READ width=4 guest=80000142 translated_caller=0022C4DF
trace[5]=002295D6
trace[6]=0022C4DF
```

`0x80000142` is the raw Xbox kernel ordinal token for decimal ordinal 322,
`XboxHardwareInfo`, a DATA export. The production bridge's
`kernel_data_va_for_ordinal(322)` maps that export into guest kernel data.

The Phase-2E execution environment already initializes the corresponding
`XboxHardwareInfo` bytes at guest VA `0x0087E000`:
Flags=0 (retail), GPU revision=0xA1, MCP revision=0xB1.

This identifies the blocker as a missing original-Xbox loader data-thunk
relocation, not a bad translated pointer or a missing generic RAM region.

#### Phase 4C-J — XboxHardwareInfo data-thunk relocation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-J.ps1`

The J gate performs only the hardware-proven ordinal-322 relocation:
- verify the exact Mercenaries thunk table starts at `0x002DBCE0`;
- inspect exactly 111 import slots and require a zero terminator;
- require exactly one raw `0x80000142` token;
- replace only that slot with `0x0087E000`;
- verify `XboxHardwareInfo` readback before translated execution;
- leave callable ordinal tokens untouched;
- retain immediate first-fault provenance for the next unresolved dependency.

Build tag: `P4C-HWINFO-20261019-A`.


#### Phase 4C-J — XboxHardwareInfo relocation
**Status: PASS on real Xbox 360 hardware.**

```text
DATA THUNK FIXUP:
  ordinal=322
  XboxHardwareInfo
  slot=002DBE0C
  old=80000142
  new=0087E000

PASS: XboxHardwareInfo thunk points at initialized guest kernel data

FAULT ACCESS IMMEDIATE:
  READ width=2
  guest=80000148

BOUNDARY:
  caller=0022C4DF
  target=80000148
  ecx=80000144
  fault=1
```

The new fault is not ordinal 328. Register ECX holds raw token
`0x80000144` = ordinal 324, `XboxKrnlVersion`; the READ16 occurs at
`ECX + 4`, exactly the Build field of `XBOX_KRNL_VERSION`.

Phase-2E already initializes `XboxKrnlVersion` at `0x0087E010` with
version 1.0.5849.0.

#### Phase 4C-K — initialized startup kernel-data thunk set
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-K.ps1`

4C-K relocates only DATA exports that the stripped Phase-2E environment
already constructs:
- ordinal 156 `KeTickCount` -> `0x0087E020`;
- ordinal 322 `XboxHardwareInfo` -> `0x0087E000`;
- ordinal 324 `XboxKrnlVersion` -> `0x0087E010`.

It requires exactly one of each in the exact 111-import table, requires the
zero terminator, validates the initialized hardware/version bytes, leaves every
other import token unchanged, and preserves Build-B immediate first-fault
provenance.

Build tag: `P4C-KDATA3-20261019-A`.


#### Phase 4C-K — initialized startup kernel-data thunk set
**Status: PASS on real Xbox 360 hardware.**

```text
DATA THUNK FIXUP: ordinal=156 slot=002DBD58 old=8000009C new=0087E020
DATA THUNK FIXUP: ordinal=322 slot=002DBE0C old=80000142 new=0087E000
DATA THUNK FIXUP: ordinal=324 slot=002DBE14 old=80000144 new=0087E010

PASS: startup data imports 156/322/324 point at initialized guest kernel data

DIRECT FRONTIER:
  caller=0022C4DF
  target=0022C47B
  esp=008BFF4C
  saved_esp=008BFF4C
  ticks=24
  fault=0
```

This proves the startup callback advanced beyond both previously observed raw
DATA-import failures. The next blocker is no longer missing kernel data; it is
the deliberately bounded translated direct-call frontier at `0x0022C47B`.

#### Phase 4C-L — promote first live direct frontier
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-L.ps1`

4C-L preserves the 49-body proven pack and adds only
`0x0022C47B`, the exact target observed on real hardware in 4C-K.
Calls from that function to translated targets not already packed remain
`DIRECT_FRONTIER` escapes. Startup DATA relocations 156/322/324 and
immediate first-fault provenance remain active.

Build tag: `P4C-DIRECTC47B-20261019-A`.


#### Phase 4C-L — promoted direct frontier
**Status: PASS on real Xbox 360 hardware.**

```text
PASS: hardware-observed direct target 0022C47B is packed for translated execution

FAULT ACCESS IMMEDIATE:
  READ width=4
  guest=8001003C

BOUNDARY:
  kind=GUEST_FAULT
  caller=0022C47B
  target=8001003C
  esp=008BFF40
  saved_esp=008BFF40
  ticks=25
  fault=1

trace[6]=0022C4DF
trace[7]=0022C47B
```

The promoted body executed successfully and exposed a new runtime dependency.
`0x8001003C` is not a kernel ordinal token. It falls inside the deliberately
fenced `0x80010000-0x80010FFF` original-Xbox kernel image page.

The original Xbox kernel image base is `0x80010000`; offset `0x3C` is the
PE/DOS `e_lfanew` field. Known Xbox recompilation work documents a RenderWare
startup/cache path that reads this exact address and can safely proceed with a
minimal synthetic PE header containing zero sections.

#### Phase 4C-M — synthetic xboxkrnl PE-header surface
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-M.ps1`

4C-M does **not** remove the kernel-page fence or alias it to title RAM.
Instead it maps only `0x80010000-0x80010FFF` to a separate 4 KiB synthetic
kernel-header page and seeds:
- DOS signature `MZ`;
- `e_lfanew = 0x80`;
- NT signature `PE\0\0`;
- machine = i386;
- `NumberOfSections = 0`.

The zero-section model intentionally makes section-scanning startup code exit
without requiring the real kernel binary. Startup DATA relocations 156/322/324,
the promoted `0x0022C47B` body, and immediate first-fault provenance remain
active.

Build tag: `P4C-KHDR-20261019-A`.


#### Phase 4C-M — synthetic xboxkrnl PE-header surface
**Status: PASS on real Xbox 360 hardware.**

```text
KERNEL HEADER MODEL:
  base=80010000
  e_lfanew=00000080
  sections=0
  size=4096

PASS: synthetic xboxkrnl PE header is readable through the fenced kernel-image page

BOUNDARY:
  kind=ICALL_SAFE
  caller=0022C28B
  target=8000002F
  esp=008BFEFC
  saved_esp=008BFF08
  ticks=28
  fault=0

trace[7]=0022C47B
trace[8]=0022C28B
```

The `0x8001003C` blocker is gone. Startup advanced through the promoted
`0x0022C47B` function into another translated function, `0x0022C28B`,
before reaching a real kernel call.

Target `0x8000002F` is kernel ordinal 47. Production bridge dispatch and ABI
metadata agree that ordinal 47 is
`HalRegisterShutdownNotification(PVOID ShutdownRegistration, BOOLEAN Register)`
with 8 argument bytes. The hardware frame delta is 12 bytes, exactly
8 argument bytes plus the translated synthetic CALL return slot.

The production host implementation records/logs the shutdown registration but
never invokes it because the recompiled runtime does not perform an Xbox-style
shutdown callback sequence.

#### Phase 4C-N — ordinal-47 shutdown-registration continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-N.ps1`

4C-N:
- requires `savedEsp-callEsp == 12`;
- reads the registration VA and 32-bit BOOLEAN stack slot;
- logs the live frame;
- mirrors production no-callback semantics;
- returns `eax=0`;
- performs exact 8-byte stdcall argument cleanup plus synthetic return cleanup;
- requires ordinal 47 to have been handled before a later boundary can PASS.

All prior DATA relocations, the kernel-header model, promoted
`0x0022C47B`, and first-fault provenance remain active.

Build tag: `P4C-HAL47-20261019-A`.


#### Phase 4C-N — HalRegisterShutdownNotification continuation
**Status: PASS on real Xbox 360 hardware.**

```text
HalRegisterShutdownNotification LIVE FRAME:
  registration=003134C0
  register_raw=00000001
  register=1
  esp=008BFEFC
  saved_esp=008BFF08

PASS: ordinal 47 HalRegisterShutdownNotification matched production no-callback semantics

DIRECT FRONTIER:
  caller=0022C28B
  target=0022F128
  esp=008BFF04
  saved_esp=008BFF04
  ticks=29
  fault=0
```

The live frame exactly matched the production ABI: 8 argument bytes plus the
translated synthetic return slot. The registration was accepted with
Register=1, the handler returned `eax=0`, and translated startup resumed.

#### Phase 4C-O — promote live target 0x0022F128
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-O.ps1`

4C-O preserves every N invariant and adds only the exact hardware-observed
direct target `0x0022F128`. The previous `0x0022F128` boundary is explicitly
forbidden from counting as progress; deeper calls remain evidence boundaries.

Build tag: `P4C-DIRECTF128-20261019-A`.


#### Phase 4C-O — promoted 0x0022F128
**Status: PASS on real Xbox 360 hardware.**

```text
BOUNDARY:
  kind=ICALL_SAFE
  caller=0022F128
  target=8000006B
  esp=008BFEE4
  saved_esp=008BFEF4
  ticks=30
  trace=10
  fault=0

trace[9]=0022F128
```

The promoted body executed successfully. Kernel target `0x8000006B` is
ordinal 107, `KeInitializeDpc`. The observed frame delta is 16 bytes:
12 bytes of arguments plus the translated synthetic CALL return slot.

Production bridge semantics:
- zero the 32-byte Xbox KDPC;
- write Type `0x13` at offset 0;
- write DeferredRoutine at offset +12;
- write DeferredContext at offset +16;
- return `eax=0`.

#### Phase 4C-P — KeInitializeDpc continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-P.ps1`

4C-P requires the exact 16-byte live frame, logs all three guest arguments,
reproduces the production 32-byte KDPC initialization, validates the guest
readback, performs exact stdcall cleanup, requires ordinal 107 to have been
handled before later progress can PASS, and preserves all prior Phase 4C
startup invariants.

The prep wrapper now validates both freshly generated `main.cpp` and
`phase4c_env.cpp` phase markers to prevent stale-source pairing.

Build tag: `P4C-DPC107-20261019-A`.


#### Phase 4C-P — KeInitializeDpc continuation
**Status: PASS on real Xbox 360 hardware.**

```text
KeInitializeDpc LIVE FRAME:
  dpc=00869580
  routine=0022F116
  context=00000000
  esp=008BFEE4
  saved_esp=008BFEF4

PASS: ordinal 107 KeInitializeDpc matched production guest-KDPC initialization semantics

BOUNDARY:
  kind=ICALL_SAFE
  caller=0022F128
  target=80000071
  esp=008BFEE8
  saved_esp=008BFEF4
  ticks=31
  fault=0
```

The live DPC frame matched the production 12-byte ABI plus synthetic return.
The guest KDPC was initialized exactly as the production bridge expects:
32 bytes zeroed, Type=0x13, DeferredRoutine at +12, DeferredContext at +16.

The next target, `0x80000071`, is ordinal 113,
`KeInitializeTimerEx(PKTIMER, TIMER_TYPE)`. The live frame delta is 12 bytes,
matching its 8 argument bytes plus the translated synthetic return.

#### Phase 4C-Q — KeInitializeTimerEx continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-Q.ps1`

4C-Q reproduces the production guest-visible timer initialization:
- require `savedEsp-callEsp == 12`;
- read Timer VA and TimerType;
- zero 40-byte guest KTIMER;
- set 16-bit Type to `0x08 + (TimerType & 1)`;
- validate the complete guest KTIMER readback;
- return `eax=0` and clean 8 argument bytes plus synthetic return;
- require ordinal 113 to be handled before later progress can PASS.

4C-Q also introduces a link-time `phase4c_env_build_cookie` symbol/value shared
between the freshly generated main/env pair. An older env file does not define
the Q cookie, so a stale XDK project reference should fail to link instead of
silently producing mismatched phase labels.

Build tag: `P4C-TIMER113-20261019-A`.


#### Phase 4C-Q — KeInitializeTimerEx continuation
**Status: PASS on real Xbox 360 hardware.**

```text
PASS: Phase 4C-Q main/env build cookie matches

KeInitializeTimerEx LIVE FRAME:
  timer=008695A0
  type_raw=00000000
  type=0
  esp=008BFEE8
  saved_esp=008BFEF4

PASS: ordinal 113 KeInitializeTimerEx matched production guest-KTIMER initialization semantics

DIRECT FRONTIER:
  caller=0022F128
  target=0022C5A4
  esp=008BFEDC
  saved_esp=008BFEDC
  ticks=33
  fault=0
```

The 40-byte guest KTIMER initialization completed with the production
dispatcher Type value for TimerType 0. The new main/env link-time cookie also
proved the freshly generated Q source pair was linked together.

The next stop is again a deliberately bounded translated direct target,
`0x0022C5A4`, not a kernel ABI or guest-memory failure.

#### Phase 4C-R — promote live target 0x0022C5A4
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-R.ps1`

4C-R preserves all Q invariants, rotates the main/env build cookie, and adds
only the exact hardware-observed direct target `0x0022C5A4`. The prior C5A4
frontier is explicitly forbidden from counting as progress; deeper calls remain
evidence boundaries.

Build tag: `P4C-DIRECTC5A4-20261019-A`.


#### Phase 4C-R — promoted 0x0022C5A4
**Status: HARDWARE PASS.**

Build `P4C-DIRECTC5A4-20261019-A` executed `0x0022C5A4` and advanced
with `fault=0` to `DIRECT_FRONTIER 0x00230060`.

#### Phase 4C-S — promoted 0x00230060
**Status: HARDWARE PASS.**

Build `P4C-DIRECT30060-20261019-A` executed `0x00230060` and advanced
with `fault=0` to `ITAIL 0x80000018`, kernel ordinal 24
`ExQueryNonVolatileSetting`.

#### Phase 4C-T — ExQueryNonVolatileSetting continuation
**Status: HARDWARE PASS.**

Build `P4C-NV24-20261019-A` captured `XC_MISC` with a four-byte value
buffer, returned STATUS_SUCCESS using the guest EEPROM/XConfig semantics, and
advanced to `ICALL_SAFE 0x8000012D`, ordinal 301
`RtlNtStatusToDosError`.

#### Phase 4C-U — RtlNtStatusToDosError continuation
**Status: HARDWARE PASS.**

Build `P4C-RTL301-20261019-A` mapped STATUS_SUCCESS to DOS error 0,
restored the expected 8-byte frame, and advanced with `fault=0` to
`DIRECT_FRONTIER 0x0022F0FB`.

#### Phase 4C-V — bounded direct closure rooted at 0x0022F0FB
**Status: HARDWARE PASS.**

Build `P4C-F0FB-CLOSURE-20261019-A` executed `0x0022F0FB`, extending
the hardware trace to 13 translated functions, and advanced with `fault=0`
to `ICALL_SAFE 0x80000095`, kernel ordinal 149 `KeSetTimer`.

#### Phase 4C-W — KeSetTimer continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-W.ps1`

4C-W validates the live 20-byte frame (dummy return + 16 argument bytes),
uses the Phase-4B-proven Xbox 360 system-time path, reproduces the production
guest KTIMER fields and prior-active return value, and continues to the next
real boundary. An already-due DPC is surfaced explicitly instead of being
silently skipped.

Build tag: `P4C-TIMER149-20261019-A`.


#### Phase 4C-W — KeSetTimer continuation
**Status: HARDWARE PASS.**

Build `P4C-TIMER149-20261019-A` captured the expected 20-byte
`KeSetTimer` frame, armed guest KTIMER `0x008695A0` with DPC
`0x00869580`, returned FALSE for the prior-active state, and advanced with
`fault=0` to `DIRECT_FRONTIER 0x0022D980`.

#### Phase 4C-X — bounded direct closure rooted at 0x0022D980
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-X.ps1`

4C-X preserves all W continuations, retains the proven `0x0022F0FB`
closure, and promotes only the hardware-observed translated root `0x0022D980`.
Deeper direct, dynamic, kernel, timer-DPC, and guest-fault boundaries remain fenced.

Build tag: `P4C-D980-CLOSURE-20261019-A`.
