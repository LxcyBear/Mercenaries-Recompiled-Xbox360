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


#### Phase 4C-X — promoted 0x0022D980
**Status: HARDWARE PASS.**

Build `P4C-D980-CLOSURE-20261019-A` executed translated root
`0x0022D980`, re-entered `0x00239BE8`, and advanced with `fault=0` to
`DIRECT_FRONTIER 0x00238C00`. The hardware trace reached 15 translated
entries.

#### Phase 4C-Y — hardware-observed root 0x00238C00
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-Y.ps1`

4C-Y preserves all prior direct roots and kernel continuations and promotes
only `0x00238C00`. Deeper direct, dynamic, kernel, timer-DPC, and guest-fault
boundaries remain fenced.

Build tag: `P4C-DIRECT38C00-20261019-A`.


### Phase 4C-Y support dependency — recomp_crt_memmove

The root-only Y preparation exposed one genuine non-direct dependency from
`0x00238C00`: `recomp_crt_memmove`.

This is not a guessed shim. The maintained production port already implements
the exact cdecl helper in `ports/mercenaries/src/recomp_manual.c`, and
`tools/recomp/test_crt_memmove_native.py` exercises the real CRT entry across
overlapping-copy cases and ABI preservation.

Phase 4C-Y now embeds the same guest-visible contract:

- arguments: destination/source/length at ESP+4/+8/+12;
- cdecl cleanup: consume only the translated dummy return slot;
- overlap-safe `memmove`;
- return destination in EAX;
- preserve caller EBX/ESI/EDI/SEH-EBP;
- reject out-of-range guest copies through the existing Phase-4C fault fence.

Hardware output will include `CRT memmove LIVE FRAME` and a matching PASS
before startup continues to the next real boundary.


#### Phase 4C-Y — translated CRT memmove path
**Status: HARDWARE PASS.**

Build `P4C-DIRECT38C00-20261019-A` executed translated root
`0x00238C00`. The maintained `recomp_crt_memmove` helper received
`dest=0x008BFE70 src=0x008BFF14 len=48`, returned the destination with the
expected cdecl cleanup, and startup advanced with `fault=0` to
`ICALL_SAFE target=0x800000B8`, ordinal 184 `NtAllocateVirtualMemory`.
The hardware trace reached 16 translated entries.

#### Phase 4C-Z — NtAllocateVirtualMemory continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-Z.ps1`

4C-Z validates the observed 24-byte full frame and continues ordinal 184 for
reserve+commit and commit-existing-region modes. Reserve-without-commit remains
an explicit `VM_UNSUPPORTED` boundary until per-page inaccessible state is
modeled in the focused startup harness.

Build tag: `P4C-NTALLOC184-20261019-A`.


#### Phase 4C-Z — NtAllocateVirtualMemory continuation
**Status: HARDWARE PASS / next required VM mode identified.**

Build `P4C-NTALLOC184-20261019-A` validated the exact 24-byte live frame and
captured a real `NtAllocateVirtualMemory` request for a 1 MiB
`MEM_RESERVE`, `PAGE_READWRITE` region with no base hint. The boundary
remained `fault=0` and stopped explicitly at `VM_UNSUPPORTED` because the
focused startup arena does not yet model reserved-but-uncommitted guest pages.

#### Phase 4C-AA — reserved guest virtual-memory state
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AA.ps1`

AA now implements explicit reserved/uncommitted and committed guest-page state
for the hardware-observed ordinal-184 path. Page-backed ranges grow downward
from the top of the 64 MiB guest arena, matching the production runtime's
allocator direction, while the existing bounded ordinary heap remains below.

The exact Z request — 1 MiB, MEM_RESERVE, PAGE_READWRITE, Base=NULL — will now
receive a persistent reserved VA. Later MEM_COMMIT calls preserve that VA,
zero newly committed pages, and update per-page protection metadata. Accesses
to reserved/uncommitted pages remain fenced.

Build tag: `P4C-VMRESERVE-AA-20261019-A`.

This remains the current Phase-4C blocker; Phase 5 begins once the native
startup path is established and starts demanding its runtime subsystems.


#### Phase 4C-AA — reserved guest virtual-memory state
**Status: HARDWARE PASS.**

Build `P4C-VMRESERVE-AA-20261019-A` handled the exact live ordinal-184 path:
the title reserved 1 MiB at `0x03F00000`, then committed the first 4 KiB at
that same VA. Both calls returned STATUS_SUCCESS, the reservation remained
stable across the commit, and startup advanced with `fault=0` to
`ICALL_SAFE target=0x80000123`.

#### Phase 4C-AB — RtlInitializeCriticalSection continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AB.ps1`

`0x80000123` is ordinal 291, `RtlInitializeCriticalSection`. AB validates
the observed 8-byte full frame and applies the maintained serialized-guest
critical-section behavior: no native host lock mapping, EAX=0, stdcall cleanup.

All AA VM reserve/commit state remains active.

Build tag: `P4C-RTL291-AB-20261019-A`.


#### Phase 4C-AB — RtlInitializeCriticalSection continuation
**Status: HARDWARE PASS.**

Build `P4C-RTL291-AB-20261019-A` validated the exact 8-byte ordinal-291
frame, applied the maintained serialized-guest critical-section semantics,
and advanced with `fault=0` to
`DIRECT_FRONTIER caller=0x00238C00 target=0x0022D431`.

#### Phase 4C-AC — promote live target 0x0022D431
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AC.ps1`

AC preserves all AB invariants, including the working 1 MiB reserve -> 4 KiB
commit state, and promotes only the exact hardware-observed translated target
`0x0022D431`. Preparation fails explicitly if D431 is a mid-function/split
entry rather than a generated function start.

Build tag: `P4C-DIRECTD431-AC-20261019-A`.


#### Phase 4C-AC — promoted 0x0022D431
**Status: HARDWARE PASS.**

Build `P4C-DIRECTD431-AC-20261019-A` executed translated root
`0x0022D431` and advanced with `fault=0` to
`DIRECT_FRONTIER caller=0x0022D431 target=0x0022CA2B`. The translated
hardware trace reached 17 entries.

#### Phase 4C-AD — promote live target 0x0022CA2B
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AD.ps1`

AD preserves all AC invariants, including the working virtual-memory
reserve/commit state and ordinal-291 continuation, retains `0x0022D431`, and
promotes only the exact hardware-observed translated target `0x0022CA2B`.
Preparation fails explicitly if CA2B is a mid-function/split entry rather than
a generated function start.

Build tag: `P4C-DIRECTCA2B-AD-20261019-A`.


#### Phase 4C-AD — promoted 0x0022CA2B
**Status: HARDWARE PASS.**

Build `P4C-DIRECTCA2B-AD-20261019-A` executed translated root
`0x0022CA2B` and advanced with `fault=0` to
`DIRECT_FRONTIER caller=0x0022CA2B target=0x0022C8EA`. The translated
hardware trace reached 18 entries.

#### Phase 4C-AE — promote live target 0x0022C8EA
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AE.ps1`

AE preserves all AD invariants, including the working virtual-memory
reserve/commit state and ordinal-291 continuation, retains `0x0022D431` and
`0x0022CA2B`, and promotes only the exact hardware-observed translated
target `0x0022C8EA`. Preparation fails explicitly if C8EA is a
mid-function/split entry rather than a generated function start.

Build tag: `P4C-DIRECTC8EA-AE-20261019-A`.


#### Phase 4C-AE — promoted 0x0022C8EA
**Status: HARDWARE PASS.**

Build `P4C-DIRECTC8EA-AE-20261019-A` executed translated root
`0x0022C8EA` and advanced with `fault=0` to
`DIRECT_FRONTIER caller=0x0022C8EA target=0x0022CEEE`. The translated
hardware trace reached 19 entries.

#### Phase 4C-AF — promote live target 0x0022CEEE
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AF.ps1`

AF preserves all AE invariants, including the working virtual-memory
reserve/commit state and ordinal-291 continuation, retains `0x0022D431`,
`0x0022CA2B`, and `0x0022C8EA`, and promotes only the exact
hardware-observed translated target `0x0022CEEE`. Preparation fails
explicitly if CEEE is a mid-function/split entry rather than a generated
function start.

Build tag: `P4C-DIRECTCEEE-AF-20261019-A`.


#### Phase 4C-AF — translated startup reaches storage/content
**Status: HARDWARE PASS — PHASE 4 COMPLETE.**

Build `P4C-DIRECTCEEE-AF-20261019-A` executed translated root
`0x0022CEEE`, flowed through `0x00239C23`, `0x0022C27A`, and
`0x0022BD2D`, then reached `ICALL_SAFE target=0x800000CA` with
`fault=0`. The translated trace reached 23 entries.

`0x800000CA` is ordinal 202 `NtOpenFile`, and the observed 28-byte full
frame matches six stdcall arguments plus the translated synthetic return.

The live boot path is now demanding storage/content I/O, satisfying the
Phase-4 exit criterion and entering Phase 5.


#### Phase 5A — first live storage/content request capture
**Status: package preparation ready.**

Branch: `xbox360/phase5-native-subsystems`

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5A.ps1`

5A preserves the complete Phase-4 hardware baseline and intercepts ordinal 202
`NtOpenFile`. It validates the exact 28-byte frame and captures the guest
`OBJECT_ATTRIBUTES`, `ANSI_STRING` path, access mask, share access, open
options, handle pointer, and I/O-status pointer.

5A is capture-only: it stops at `STORAGE_OPEN` without fabricating a handle
or file status. The captured path and flags drive the first native Xbox 360
storage/content implementation gate.

Build tag: `P5A-NTOPEN202-CAPTURE-20261019-A`.

Cookie: `P5A1 / 0x50354131`.


#### Phase 5A — captured first live NtOpenFile
**Status: HARDWARE PASS.**

Build `P5A-NTOPEN202-CAPTURE-20261019-A` captured the first runtime storage
request with `fault=0`:

```text
path=\Device\Harddisk0\partition1\
access=0x00100001
share=0x00000003
options=0x00800021
caller=0x0022BD2D
```

The 28-byte live frame and guest OBJECT_ATTRIBUTES / ANSI_STRING decoding both
matched the expected ordinal-202 ABI.

#### Phase 5B — native NtOpenFile continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5B.ps1`

5B maps the observed Partition1 tree to
`game:\merc360-partition1`, performs the open using native Xenon/XDK file
primitives, returns a tagged 32-bit guest handle + IO_STATUS_BLOCK, and resumes
the translated boot path.

Build tag: `P5B-NTOPEN202-NATIVE-20261019-A`.

Cookie: `P5B1 / 0x50354231`.


#### Phase 5B — native NtOpenFile hardware pass
**Status: HARDWARE PASS.**

Build `P5B-NTOPEN202-NATIVE-20261019-A` mapped the observed
`\Device\Harddisk0\partition1\` request to
`game:\merc360-partition1`, returned STATUS_SUCCESS with tagged guest handle
`0x48000001`, and resumed translated execution with `fault=0`.

The next live dependency is `ICALL_SAFE target=0x800000DA`, ordinal 218
`NtQueryVolumeInformationFile`, with an exact 24-byte full frame.

#### Phase 5C — native volume query + handle close
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5C.ps1`

5C resolves the tagged guest handle to its native Xenon handle, services
`XboxFileFsSizeInformation` from native `game:` free/total space using
512-byte sectors and 32 sectors per allocation unit, then resumes execution.

Ordinal 187 `NtClose` is also armed for the tagged native handle lifecycle.

Build tag: `P5C-VOLUME218-NATIVE-20261019-A`.

Cookie: `P5C1 / 0x50354331`.


#### Phase 5C — native volume query hardware pass
**Status: HARDWARE PASS.**

Build `P5C-VOLUME218-NATIVE-20261019-A` successfully completed the native
Partition1 storage lifecycle:

- `NtOpenFile` returned token `0x48000001`;
- `NtQueryVolumeInformationFile` class 3 returned native-backed free/total
  space with 512-byte sectors and 32 sectors per allocation unit;
- `NtClose` released the tagged Xenon handle.

The next live dependency is `ICALL_SAFE target=0x80000043`, ordinal 67
`IoCreateSymbolicLink`, with `fault=0` and an exact 12-byte full frame.

#### Phase 5D — native symbolic-link mount
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5D.ps1`

5D decodes the live guest symbolic-link name and device target, records the
mapping with maintained Xbox collision/resource semantics, integrates
guest-created `\??\X:` aliases into storage path translation, and resumes
the real boot path.

Ordinal 69 `IoDeleteSymbolicLink` is also armed.

Build tag: `P5D-SYMLINK67-NATIVE-20261019-A`.

Cookie: `P5D1 / 0x50354431`.


#### Phase 5D — symbolic-link mount hardware pass
**Status: HARDWARE PASS.**

Build `P5D-SYMLINK67-NATIVE-20261019-A` preserved the native Partition1
open/query/close lifecycle and successfully handled ordinal 67
`IoCreateSymbolicLink`.

Retail hardware evidence:

```text
\??\D: -> \Device\CdRom0
status=0x00000000
```

Translated execution then advanced with `fault=0` to
`DIRECT_FRONTIER caller=0x0022BD2D target=0x0022C1C0`.

#### Phase 5E — promote post-mount root 0x0022C1C0
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5E.ps1`

5E retains the complete native storage/mount stack and promotes only the exact
hardware-observed translated root `0x0022C1C0`. Preparation fails closed for
a split/mid-function target or missing generated body.

Build tag: `P5E-DIRECTC1C0-20261020-A`.

Cookie: `P5E1 / 0x50354531`.


#### Phase 5E — post-mount translated helper hardware pass
**Status: HARDWARE PASS.**

Build `P5E-DIRECTC1C0-20261020-A` retained the complete native storage and
`D:` mount stack, executed translated root `0x0022C1C0`, and advanced with
`fault=0` to
`DIRECT_FRONTIER caller=0x0022C1C0 target=0x002370B8`.

The translated hardware trace reached 24 entries.

#### Phase 5F — promote next retail root 0x002370B8
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5F.ps1`

5F retains the complete native storage/mount stack and promotes only the exact
hardware-observed translated root `0x002370B8`. Preparation fails closed for
a split/mid-function target or missing generated body.

Build tag: `P5F-DIRECT370B8-20261020-A`.

Cookie: `P5F1 / 0x50354631`.


#### Phase 5F — next retail helper hardware pass
**Status: HARDWARE PASS.**

Build `P5F-DIRECT370B8-20261020-A` retained the complete native
storage/mount stack, executed translated root `0x002370B8`, and expanded the
live translated trace from 24 to 45 entries.

The path traversed repeated execution through already-packed retail helpers,
including `0x0023F150` and `0x0023A3CE`, before reaching:

```text
DIRECT_FRONTIER caller=0x0023A3CE target=0x0022BE8C
fault=0
```

#### Phase 5G — promote next retail root 0x0022BE8C
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5G.ps1`

5G retains the full native storage/mount stack and every previously proven
translated root, and promotes only the exact hardware-observed translated root
`0x0022BE8C`. Preparation fails closed for a split/mid-function target or
missing generated body.

Build tag: `P5G-DIRECTBE8C-20261020-A`.

Cookie: `P5G1 / 0x50354731`.


#### Phase 5G — NtCreateFile boundary hardware pass
**Status: HARDWARE PASS.**

Build `P5G-DIRECTBE8C-20261020-A` retained the complete native storage/mount
stack, executed translated root `0x0022BE8C`, and reached:

```text
ICALL_SAFE caller=0x0022BE8C target=0x800000BE
fault=0
trace=46
```

Target `0x800000BE` is ordinal 190 `NtCreateFile`. The observed full frame
is 40 bytes, matching nine stdcall arguments plus the synthetic return.

#### Phase 5H — native NtCreateFile + synchronous read
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5H.ps1`

5H services `NtCreateFile` through native Xenon/XDK file primitives while
reusing the proven symbolic-link/path translator and tagged guest-handle table.
It also arms ordinal 219 `NtReadFile` for synchronous native-backed reads;
event/APC forms remain fenced.

Build tag: `P5H-NTCREATE190-NATIVE-20261020-A`.

Cookie: `P5H1 / 0x50354831`.


#### Phase 5H — TDATA NtCreateFile hardware pass
**Status: HARDWARE PASS.**

Build `P5H-NTCREATE190-NATIVE-20261020-A` preserved the complete native
storage/mount stack and successfully serviced ordinal 190 `NtCreateFile` for:

```text
\Device\Harddisk0\partition1\TDATA
    -> game:\merc360-partition1\TDATA
disposition=FILE_OPEN_IF
status=0x00000000
```

The tagged handle was then closed successfully. `NtReadFile` was armed but
not reached in this hardware run.

The next live dependency is `0x80000121`, ordinal 289
`RtlInitAnsiString`, with an exact 12-byte full frame and `fault=0`.

#### Phase 5I — maintained RtlInitAnsiString continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5I.ps1`

5I performs bounded guest C-string scanning, initializes the Xbox
`ANSI_STRING` layout in guest memory, logs a bounded printable source preview,
and resumes the live retail path.

Build tag: `P5I-RTLINITANSI289-20261020-A`.

Cookie: `P5I1 / 0x50354931`.


#### Phase 5I — title-storage hierarchy hardware pass
**Status: HARDWARE PASS.**

Build `P5I-RTLINITANSI289-20261020-A` preserved the complete native storage
and mount stack, serviced ordinal 289 `RtlInitAnsiString`, and exposed the
exact title-id storage paths.

Hardware then successfully created/opened:

```text
\Device\Harddisk0\partition1\TDATA\4c410015
\Device\Harddisk0\partition1\UDATA
\Device\Harddisk0\partition1\UDATA\4c410015
```

and mounted:

```text
\??\T: -> \Device\Harddisk0\partition1\TDATA\4c410015
```

The next live dependency is
`DIRECT_FRONTIER caller=0x0022BE8C target=0x0022F026` with `fault=0`;
the translated trace reached 47 entries.

#### Phase 5J — promote post-title-storage root 0x0022F026
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5J.ps1`

5J retains all proven native storage, `D:`/`T:` mounts, TDATA/UDATA
hierarchy and RTL string behavior, and promotes only the exact
hardware-observed translated root `0x0022F026`.

Build tag: `P5J-DIRECTF026-20261020-A`.

Cookie: `P5J1 / 0x50354A31`.


#### Phase 5J — XBE section-name path hardware pass
**Status: HARDWARE PASS.**

Build `P5J-DIRECTF026-20261020-A` passed with the phase-specific
main/environment linker cookie, retained the complete native title-storage
stack, and executed translated root `0x0022F026`.

The live path initialized `ANSI_STRING` values for `$$XTINFO` and
`.text`, then reached:

```text
ICALL_SAFE caller=0x0022F026 target=0x80000117
fault=0
trace=48
```

Target `0x80000117` is ordinal 279 `RtlEqualString`; the observed full
frame is 16 bytes.

#### Phase 5K — maintained RtlEqualString continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5K.ps1`

5K performs bounded guest-memory `ANSI_STRING` equality with the maintained
case-insensitive behavior, logs bounded previews of both live operands, returns
the BOOLEAN result in EAX, and resumes the retail XBE/image-inspection path.

Build tag: `P5K-RTLEQUAL279-20261020-A`.

Cookie: `P5K1 / 0x50354B31`.

Link-time guard: `phase5k_env_build_cookie`.


#### Phase 5K — XBE section scan hardware pass
**Status: HARDWARE PASS.**

Build `P5K-RTLEQUAL279-20261020-A` retained the complete native title-storage
stack and serviced ordinal 279 `RtlEqualString`.

Retail helper `0x0022F026` compared `$$XTINFO` case-insensitively against
all 14 loaded XBE section names. Every comparison returned false, matching the
actual supported retail section table.

The next live dependency is:

```text
DIRECT_FRONTIER caller=0x0022F026 target=0x0022B178
fault=0
trace=48
```

#### Phase 5L — maintained SetLastError root 0x0022B178
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5L.ps1`

5L retains all proven native storage, D:/T: mounts, title-data setup and RTL
section-name scanning, and executes exact hardware-observed root `0x0022B178`
through the reviewed maintained `SetLastError` body from `recomp_manual.c`.
The Stage-3 generated tree remains frozen; all unrelated missing bodies still
fail closed.

Build tag: `P5L-DIRECTB178-20261020-A`.

Cookie: `P5L1 / 0x50354C31`.

Link-time guard: `phase5l_env_build_cookie`.


#### Phase 5L — maintained SetLastError hardware pass
**Status: HARDWARE PASS.**

Build `P5L-DIRECTB178-20261020-A` retained the complete native storage,
D:/T: mount, title-data and RTL section-scan stack. The support-owned
maintained `SetLastError` root `0x0022B178` executed on real hardware with:

```text
value=0x00000490
calls=1
new_esp=0x008BFC14
```

Retail startup then continued through the XBE image-section path, matched
`$$XTIMAGE` and `$$XSIMAGE` against their live section names, opened
`\Device\Harddisk0\partition1\UDATA\4c410015\TitleMeta.xbx` successfully
as tagged guest handle `0x48000002`, and advanced with `fault=0` to:

```text
ICALL_SAFE caller=0x00239C23 target=0x800000D3
esp=0x008BFC24 saved_esp=0x008BFC3C
trace=54
```

`0x800000D3` is original-Xbox ordinal 211 `NtQueryInformationFile`. The
observed 24-byte full frame matches five stdcall arguments plus the translated
synthetic return.

#### Phase 5M — NtQueryInformationFile live-frame capture
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5M.ps1`

5M preserves every 5L-proven subsystem and intercepts only ordinal 211. It
captures the exact live file handle, `IO_STATUS_BLOCK` pointer, output-buffer
pointer, requested length and `FILE_INFORMATION_CLASS`, then stops at an
explicit `FILE_INFORMATION` boundary. No file-information payload is
fabricated until hardware identifies the class requested by Mercenaries.

Build tag: `P5M-NTQUERYINFO211-CAPTURE-20261020-A`.

Cookie: `P5M1 / 0x50354D31`.

Link-time guard: `phase5m_env_build_cookie`.


#### Phase 5M — NtQueryInformationFile capture hardware pass
**Status: HARDWARE PASS.**

Build `P5M-NTQUERYINFO211-CAPTURE-20261020-A` preserved the complete 5L
runtime stack and captured the first live ordinal-211 request with `fault=0`:

```text
handle = 0x48000002
iosb   = 0x008BFEB4
info   = 0x008BFE68
len    = 56
class  = 34
caller = 0x00239C23
trace  = 54
```

The handle is the native-backed token returned for
`\Device\Harddisk0\partition1\UDATA\4c410015\TitleMeta.xbx`.

Class 34 is `FileNetworkOpenInformation`; the live 56-byte request matches
the `FILE_NETWORK_OPEN_INFORMATION` layout exactly.

#### Phase 5N — native NtQueryInformationFile class 34
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5N.ps1`

5N extends the tagged guest-handle lifecycle with a remembered native Xenon
path. Ordinal 211 class 34 is serviced from `GetFileAttributesExA` metadata
and returned as the exact 56-byte guest `FILE_NETWORK_OPEN_INFORMATION`
layout. `IO_STATUS_BLOCK.Information` is set to 56 on success.

AllocationSize is rounded to the already-proven 16 KiB FATX-style allocation
unit. XAM exposes creation/access/write time but no independent change time in
`WIN32_FILE_ATTRIBUTE_DATA`, so the maintained 5N bridge mirrors last-write
time into ChangeTime. Unobserved information classes remain fenced.

Build tag: `P5N-NTQUERYINFO211-NATIVE-20261020-A`.

Cookie: `P5N1 / 0x50354E31`.

Link-time guard: `phase5n_env_build_cookie`.


#### Phase 5M — NtQueryInformationFile capture hardware pass
**Status: HARDWARE PASS.**

Build `P5M-NTQUERYINFO211-CAPTURE-20261020-A` preserved the complete 5L runtime stack and captured ordinal 211 with `fault=0`:

```text
handle=0x48000002 iosb=0x008BFEB4 info=0x008BFE68 len=56 class=34
caller=0x00239C23 trace=54
```

The handle is the native-backed token for `TitleMeta.xbx`. Class 34 is
`FileNetworkOpenInformation`, and the 56-byte request matches
`FILE_NETWORK_OPEN_INFORMATION`.

#### Phase 5N — native NtQueryInformationFile class 34
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5N.ps1`

5N remembers the native Xenon path associated with each tagged guest handle
and services ordinal 211 class 34 from `GetFileAttributesExA`. It writes the
56-byte guest `FILE_NETWORK_OPEN_INFORMATION` and sets
`IO_STATUS_BLOCK.Information=56` on success. AllocationSize uses the proven
16 KiB FATX-style unit; ChangeTime mirrors LastWriteTime. Unobserved classes
remain fenced.

Build tag: `P5N-NTQUERYINFO211-NATIVE-20261020-A`.
Cookie: `P5N1 / 0x50354E31`.
Link-time guard: `phase5n_env_build_cookie`.


#### Phase 5N — native NtQueryInformationFile class 34 hardware pass
**Status: HARDWARE PASS.**

Build `P5N-NTQUERYINFO211-NATIVE-20261020-A` serviced the captured
`TitleMeta.xbx` class-34 request successfully:

```text
handle=0x48000002
class=34
length=56
status=0x00000000
eof=0
allocation=0
attributes=0x00000080
```

The native path was
`game:\merc360-partition1\UDATA\4c410015\TitleMeta.xbx`.
Retail execution resumed with `fault=0` and immediately reached:

```text
DIRECT_FRONTIER caller=0x00239C23 target=0x00239B78
esp=0x008BFC18 trace=54
```

#### Phase 5O — post-TitleMeta direct root 0x00239B78
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5O.ps1`

5O retains every hardware-proven Phase-5 subsystem and promotes only exact
hardware-observed translated root `0x00239B78` at depth zero. Preparation
fails closed if the address is not an exact function start or if the frozen
Stage-3 generated set has no body. Deeper direct callees remain fenced.

Build tag: `P5O-DIRECT239B78-20261020-A`.

Cookie: `P5O1 / 0x50354F31`.

Link-time guard: `phase5o_env_build_cookie`.


#### Phase 5O — post-TitleMeta direct root 0x00239B78 hardware pass
**Status: HARDWARE PASS.**

Build `P5O-DIRECT239B78-20261020-A` retained the complete native
`TitleMeta.xbx` class-34 metadata continuation. Root `0x00239B78` executed
as translated trace entry 54, then reached a new direct frontier with
`fault=0`:

```text
caller=0x00239B78
target=0x0023DDDD
esp=0x008BFBE0
trace=55
```

Harness result: `PHASE 5O DIRECT239B78 RESULT: PASS`.

#### Phase 5P — post-TitleMeta direct root 0x0023DDDD
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5P.ps1`

5P retains root `0x00239B78` and promotes only exact hardware-observed
translated root `0x0023DDDD` at depth zero. Preparation fails closed if the
address is not an exact function start or if the frozen Stage-3 generated set
has no body. Deeper direct callees remain fenced for hardware discovery.

Build tag: `P5P-DIRECT23DDDD-20261020-A`.
Cookie: `P5P1 / 0x50355031`.
Link-time guard: `phase5p_env_build_cookie`.


#### Phase 5P — post-TitleMeta direct root 0x0023DDDD hardware pass
**Status: HARDWARE PASS.**

Build `P5P-DIRECT23DDDD-20261020-A` retained the native
`TitleMeta.xbx` class-34 metadata continuation. Root `0x0023DDDD`
executed as translated trace entry 55, then reached a new direct frontier with
`fault=0`:

```text
caller=0x0023DDDD
target=0x0023DD7B
esp=0x008BF76C
trace=56
```

Harness result: `PHASE 5P DIRECT23DDDD RESULT: PASS`.

#### Phase 5Q — post-TitleMeta direct root 0x0023DD7B
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5Q.ps1`

5Q retains roots `0x00239B78` and `0x0023DDDD`, then promotes only exact
hardware-observed root `0x0023DD7B` at depth zero. Because the new target is
only 0x62 bytes below the preceding root, preparation explicitly rejects a
split/mid-function target. A missing frozen Stage-3 body also fails closed.

Build tag: `P5Q-DIRECT23DD7B-20261020-A`.
Cookie: `P5Q1 / 0x50355131`.
Link-time guard: `phase5q_env_build_cookie`.


#### Phase 5Q — post-TitleMeta direct root 0x0023DD7B hardware pass
**Status: HARDWARE PASS.**

Build `P5Q-DIRECT23DD7B-20261020-A` retained the complete native
`TitleMeta.xbx` class-34 metadata continuation. Root `0x0023DD7B`
executed as translated trace entry 56, then reached a new direct frontier with
`fault=0`:

```text
caller=0x0023DD7B
target=0x0023DDA0
esp=0x008BF774
trace=57
```

Harness result: `PHASE 5Q DIRECT23DD7B RESULT: PASS`.

#### Phase 5R — post-TitleMeta direct root 0x0023DDA0
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5R.ps1`

5R retains roots `0x00239B78`, `0x0023DDDD`, and `0x0023DD7B`, then
promotes only exact hardware-observed root `0x0023DDA0` at depth zero. The
new target is only 0x25 bytes above `0x0023DD7B`, so preparation explicitly
rejects a split/mid-function target. A missing frozen Stage-3 body also fails
closed.

Build tag: `P5R-DIRECT23DDA0-20261020-A`.
Cookie: `P5R1 / 0x50355231`.
Link-time guard: `phase5r_env_build_cookie`.


#### Phase 5R — post-TitleMeta direct root 0x0023DDA0 hardware pass
**Status: HARDWARE PASS.**

Build `P5R-DIRECT23DDA0-20261020-A` preserved the complete native
`TitleMeta.xbx` metadata continuation. Root `0x0023DDA0` executed twice
as translated trace entries 57 and 58, then reached a new direct frontier with
`fault=0`:

```text
caller=0x0023DDA0
target=0x0023DD56
esp=0x008BF764
trace=59
```

Harness result: `PHASE 5R DIRECT23DDA0 RESULT: PASS`.

#### Phase 5S — post-TitleMeta direct root 0x0023DD56
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5S.ps1`

5S retains roots `0x00239B78`, `0x0023DDDD`, `0x0023DD7B`, and
`0x0023DDA0`, then promotes only exact hardware-observed root
`0x0023DD56` at depth zero. Preparation explicitly rejects a split or
mid-function target and fails closed if the frozen Stage-3 generated set lacks
a body.

Build tag: `P5S-DIRECT23DD56-20261020-A`.
Cookie: `P5S1 / 0x50355331`.
Link-time guard: `phase5s_env_build_cookie`.


#### Phase 5S — post-TitleMeta direct root 0x0023DD56 hardware pass
**Status: HARDWARE PASS.**

Build `P5S-DIRECT23DD56-20261020-A` preserved the complete native
`TitleMeta.xbx` metadata continuation. Root `0x0023DD56` executed as
translated trace entry 59, then reached a new direct frontier with `fault=0`:

```text
caller=0x0023DD56
target=0x0023F8CB
esp=0x008BF758
trace=60
```

Harness result: `PHASE 5S DIRECT23DD56 RESULT: PASS`.

#### Phase 5T — post-TitleMeta direct root 0x0023F8CB
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5T.ps1`

5T retains roots `0x00239B78`, `0x0023DDDD`, `0x0023DD7B`,
`0x0023DDA0`, and `0x0023DD56`, then promotes only exact
hardware-observed root `0x0023F8CB` at depth zero. Preparation fails closed
if the target is not an exact function start or if the frozen Stage-3
generated set lacks a body. Deeper direct callees remain fenced.

Build tag: `P5T-DIRECT23F8CB-20261020-A`.
Cookie: `P5T1 / 0x50355431`.
Link-time guard: `phase5t_env_build_cookie`.


#### Phase 5T — post-TitleMeta direct root 0x0023F8CB hardware pass
**Status: HARDWARE PASS.**

Build `P5T-DIRECT23F8CB-20261020-A` preserved the complete native
`TitleMeta.xbx` metadata continuation. Root `0x0023F8CB` entered the
TitleMeta serialization loop and repeatedly alternated with `0x0023DD56`.
The translated trace advanced to 119 before reaching a new kernel boundary
with `fault=0`:

```text
caller=0x0023F8CB
target=0x800000EC
kind=ICALL_SAFE
esp=0x008BFC18
saved_esp=0x008BFC3C
trace=119
```

Ordinal `0xEC / 236` is `NtWriteFile`; its Xbox `@32` ABI matches the
observed 36-byte full frame exactly.

Harness result: `PHASE 5T DIRECT23F8CB RESULT: PASS`.

#### Phase 5U — native NtWriteFile ordinal 236
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5U.ps1`

5U retains the complete Phase-5 storage/runtime stack and post-TitleMeta
direct-root chain through `0x0023F8CB`. It services synchronous ordinal-236
`NtWriteFile` through the existing tagged native Xenon HANDLE table using a
real `WriteFile` call and writes guest `IO_STATUS_BLOCK.Status` plus the
transferred byte count.

Supported byte-offset forms are absolute offsets,
`FILE_USE_FILE_POINTER_POSITION`, and `FILE_WRITE_TO_END_OF_FILE`.
Event/APC forms and other negative/special offsets remain fenced.

Build tag: `P5U-NTWRITEFILE236-NATIVE-20261020-A`.
Cookie: `P5U1 / 0x50355531`.
Link-time guard: `phase5u_env_build_cookie`.


#### Phase 5U — native NtWriteFile ordinal 236 hardware pass
**Status: HARDWARE PASS.**

Build `P5U-NTWRITEFILE236-NATIVE-20261020-A` preserved the exact supported
retail environment and full native title-storage stack. The live write request
was serviced synchronously:

```text
handle=0x48000002
buffer=0x008BFC48
length=48
offset_ptr=0x00000000
status=0x00000000
bytes=48
requested=48
```

`NtClose` then succeeded for the same handle, and retail execution advanced
to a new direct frontier with no guest fault:

```text
caller=0x0023F8CB
target=0x0022BDA5
esp=0x008BFC28
trace=119
fault=0
```

Harness result: `PHASE 5U NTWRITEFILE236 NATIVE RESULT: PASS`.

#### Phase 5V — post-write direct root 0x0022BDA5
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5V.ps1`

5V preserves the native ordinal-236 write bridge and the complete prior
translated stack, then promotes only exact hardware-observed root
`0x0022BDA5` at depth zero. Because 5U persisted a 48-byte
`TitleMeta.xbx`, 5V is state-aware: a successful write is no longer required
on every boot. The new root carries explicit execution instrumentation so its
hardware proof is independent of preceding loop iteration count.

Build tag: `P5V-DIRECT22BDA5-20261020-A`.
Cookie: `P5V1 / 0x50355631`.
Link-time guard: `phase5v_env_build_cookie`.


#### Phase 5V — post-write direct root 0x0022BDA5 hardware proof
**Status: HARDWARE PASS (harness false-negative identified).**

Build `P5V-DIRECT22BDA5-20261020-A` ran against the persistent state created by
5U. `TitleMeta.xbx` now reports EOF 48 / allocation 16384, so retail skips
the prior metadata serialization/write loop. Root `0x0022BDA5` executed as
trace entry 54, after which retail created/opened `TitleImage.xbx`, queried
its class-34 metadata successfully, and reached a new clean direct frontier:

```text
caller=0x00239C23
target=0x0022F08D
esp=0x008BFBBC
trace=58
fault=0
```

The emitted 5V harness printed `FAIL` only because its pass expression still
required the pre-persistence fixed trace sequence through entries 54..60.
That trace-index assumption is invalid once `TitleMeta.xbx` persists. The
actual hardware exit criterion for 5V was satisfied: `0x0022BDA5` executed
and continued to a new nonfaulting boundary.

#### Phase 5W — TitleImage-path direct root 0x0022F08D
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5W.ps1`

5W retains the complete prior native storage/runtime stack, including
ordinal-236 `NtWriteFile`, and promotes only exact hardware-observed root
`0x0022F08D` at depth zero. Its hardware proof is persistent-state aware:
fixed historical trace indexes are removed and explicit root-entry
instrumentation is authoritative.

Build tag: `P5W-DIRECT22F08D-20261020-A`.
Cookie: `P5W1 / 0x50355731`.
Link-time guard: `phase5w_env_build_cookie`.


#### Phase 5W — TitleImage-path direct root 0x0022F08D hardware pass
**Status: HARDWARE PASS.**

Build `P5W-DIRECT22F08D-20261020-A` validated the state-aware proof model.
The persisted `TitleMeta.xbx` remained at EOF 48, `TitleImage.xbx` was
opened and queried at EOF 0, and translated root `0x0022F08D` executed as
trace entry 58. Retail then reached a new kernel boundary with `fault=0`:

```text
caller=0x0022F08D
target=0x80000147
kind=ICALL_SAFE
esp=0x008BFBB0
saved_esp=0x008BFBB8
trace=59
```

Ordinal `0x147 / 327` is `XeLoadSection@4`; the observed 8-byte full frame
matches one 4-byte argument plus the synthetic return slot.

Harness result: `PHASE 5W DIRECT22F08D RESULT: PASS`.

#### Phase 5X — native XeLoadSection ordinal 327
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5X.ps1`

5X preserves the complete state-aware TitleMeta/TitleImage path and services
ordinal-327 `XeLoadSection`. The Phase-2E environment already preloads all
retail XBE section bytes and zero-fill, so 5X implements the kernel bookkeeping
layer: validate an exact 0x38-byte section-table entry, increment
`SectionReferenceCount`, update distinct shared head/tail page counters on
the 0->1 transition, return `STATUS_SUCCESS`, and resume retail execution.
Malformed/non-table pointers remain fenced.

Build tag: `P5X-XELOADSECTION327-NATIVE-20261020-A`.
Cookie: `P5X1 / 0x50355831`.
Link-time guard: `phase5x_env_build_cookie`.


#### Phase 5X — native XeLoadSection ordinal 327 hardware pass
**Status: HARDWARE PASS.**

Build `P5X-XELOADSECTION327-NATIVE-20261020-A` preserved the exact supported
retail environment and state-aware TitleMeta/TitleImage path. The live
`XeLoadSection` request targeted XBE section 11:

```text
section=0x000105D8
index=11
name=$$XTIMAGE
va=0x00874D40
vsize=10240
file=0x0030E000
fsize=10240
refs=0->1
```

The bookkeeping continuation returned successfully and retail advanced to a
new direct frontier with no guest fault:

```text
caller=0x0022F08D
target=0x0022F0CC
esp=0x008BFBB8
trace=59
fault=0
```

Harness result: `PHASE 5X XELOADSECTION327 NATIVE RESULT: PASS`.

#### Phase 5Y — post-XeLoadSection direct root 0x0022F0CC
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5Y.ps1`

5Y retains the complete native storage/runtime stack plus the proven
ordinal-327 `XeLoadSection` bookkeeping continuation and promotes only the
hardware-observed direct target `0x0022F0CC` at depth zero. Preparation
fails closed if the address is not an exact frozen function start or lacks a
generated translated body. Hardware proof uses explicit root-entry
instrumentation and does not depend on fixed trace indexes.

Build tag: `P5Y-DIRECT22F0CC-20261020-A`.
Cookie: `P5Y1 / 0x50355931`.
Link-time guard: `phase5y_env_build_cookie`.


#### Phase 5Y — post-XeLoadSection direct root 0x0022F0CC hardware proof
**Status: HARDWARE ROOT PASS; next kernel ABI shape captured as unresolved.**

Build `P5Y-DIRECT22F0CC-20261020-A` preserved the exact supported retail
environment and the native ordinal-327 `XeLoadSection` continuation.
`$$XTIMAGE` again loaded successfully with section references `0 -> 1`.
Translated root `0x0022F0CC` then executed as trace entry 59.

The next live dependency is ordinal-236 `NtWriteFile`, but this call site
presents a different full-frame shape from the already proven TitleMeta write:

```text
caller=0x0022F0CC
target=0x800000EC
esp=0x008BFBA0
saved_esp=0x008BFBC0
frame_delta=32
fault=0
```

The existing native continuation requires the previously proven 36-byte full
frame, so it fenced the call as `KERNEL_FRAME`. The final 5Y harness result is
therefore `FAIL`, but the 5Y direct-root exit criterion itself is satisfied:
`0x0022F0CC` executed and exposed the next nonfaulting kernel dependency.

#### Phase 5Z — compact NtWriteFile frame capture
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5Z.ps1`

5Z retains all 74 translated bodies, native storage bridges, and the proven
`XeLoadSection` bookkeeping continuation. The original 36-byte
`NtWriteFile` path remains unchanged. For the hardware-observed 32-byte form
from caller `0x0022F0CC`, 5Z performs no native write: it captures stack
words from offsets `+0x00` through `+0x28`, records the caller/frame size,
and stops at a deliberate kernel-frame boundary. That exact capture is the
5Z PASS criterion.

Build tag: `P5Z-NTWRITEFILE236-COMPACT-CAPTURE-20261020-A`.
Cookie: `P5Z1 / 0x50355A31`.
Link-time guard: `phase5z_env_build_cookie`.


#### Phase 5Z — NtWriteFile caller 0x0022F0CC ABI capture hardware pass
**Status: HARDWARE PASS.**

Build `P5Z-NTWRITEFILE236-COMPACT-CAPTURE-20261020-A` preserved the exact
supported retail environment and complete state-aware TitleMeta/TitleImage
path. The raw ordinal-236 stack capture proved that caller `0x0022F0CC`
still supplies all eight standard `NtWriteFile` arguments:

```text
+00 return     = 0x00000000
+04 handle     = 0x48000002
+08 event      = 0x00000000
+0C APC        = 0x00000000
+10 context    = 0x00000000
+14 IOSB       = 0x008BFC1C
+18 buffer     = 0x00874D40
+1C length     = 0x00002800
+20 ByteOffset = 0x00000000
```

The buffer/length exactly match XBE section 11 `$$XTIMAGE`
(`VA=0x00874D40`, `VSIZE=0x2800`). The only mismatch is the translated
safe-call continuation value: `savedEsp-callEsp=32`, one dword short of the
true 36-byte full frame. No native I/O was issued in 5Z.

Harness result:
`PHASE 5Z NTWRITEFILE236 COMPACT CAPTURE RESULT: PASS`.

#### Phase 5AA — native TitleImage NtWriteFile saved-ESP repair
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AA.ps1`

5AA keeps the previously proven ordinary 36-byte `NtWriteFile` continuation
unchanged. For caller `0x0022F0CC` only, it validates the exact Phase-5Z
frame (`buffer=0x00874D40`, `length=0x2800`, `ByteOffset=NULL`), repairs
the continuation ESP from `savedEsp` to `savedEsp+4`, performs the real
native write, updates the guest `IO_STATUS_BLOCK`, and resumes retail
execution. Any other 32-byte observation remains fenced.

Build tag: `P5AA-NTWRITEFILE236-XTIMAGE-NATIVE-20261020-A`.
Cookie: `P5AA / 0x50354141`.
Link-time guard: `phase5aa_env_build_cookie`.


#### Phase 5AA — native TitleImage NtWriteFile hardware pass
**Status: HARDWARE PASS.**

Build `P5AA-NTWRITEFILE236-XTIMAGE-NATIVE-20261020-A` preserved the exact
supported retail environment and validated the caller-specific saved-ESP
repair discovered by 5Z. The live ordinal-236 request from caller
`0x0022F0CC` matched the captured frame exactly:

```text
handle=0x48000002
IOSB=0x008BFC1C
buffer=0x00874D40
length=0x2800
ByteOffset=NULL
savedEsp=0x008BFBC0
resumeEsp=0x008BFBC4
```

The bridge wrote all 10,240 bytes successfully with `status=0`. Retail then
continued to a new direct frontier with no guest fault:

```text
caller=0x0022F0CC
target=0x0022F0AE
esp=0x008BFBBC
trace=60
fault=0
```

Harness result: `PHASE 5AA NTWRITEFILE236 XTIMAGE NATIVE RESULT: PASS`.

#### Phase 5AB — post-TitleImage-write direct root 0x0022F0AE
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AB.ps1`

5AB retains the complete native file/storage path, the proven
`XeLoadSection` continuation, and both NtWriteFile forms. Since
`TitleImage.xbx` is now persistent state, the gate does not require
`XeLoadSection` or the 0x2800-byte write to repeat on every boot. It promotes
only exact hardware-observed root `0x0022F0AE` at depth zero and proves
execution with an explicit root-entry flag.

Build tag: `P5AB-DIRECT22F0AE-20261020-A`.
Cookie: `P5AB / 0x50354142`.
Link-time guard: `phase5ab_env_build_cookie`.


#### Phase 5AB — persistent TitleImage branch / SaveImage discovery
**Status: hardware path discovery; overall harness result FAIL at a deliberately fenced write shape.**

Build `P5AB-DIRECT22F0AE-20261020-A` preserved the exact retail environment
and confirmed that the Phase-5AA TitleImage write persisted. Retail observed:

```text
TitleImage.xbx EOF = 10240
SaveImage.xbx  EOF = 0
XeLoadSection index = 12
section name = $$XSIMAGE
section VA = 0x00877540
section size = 0x1000
```

The same translated caller `0x0022F0CC` then reached ordinal-236
`NtWriteFile` with the already-classified one-dword-short saved-ESP shape,
but the 5AA repair guard still allowed only the `$$XTIMAGE` payload. The
handler correctly fenced the new `$$XSIMAGE` case before native I/O:

```text
buffer=0x00877540
length=0x1000
ByteOffset=NULL
fault=0
boundary=KERNEL_FRAME
```

The promoted root `0x0022F0AE` was therefore not reached in this run.

#### Phase 5AC — proven image-section NtWriteFile continuation
**Status: package preparation ready.**

Gate:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AC.ps1`

5AC retains root `0x0022F0AE` and extends the caller-`0x0022F0CC`
saved-ESP repair to exactly two hardware-supported image-section/file pairs:

```text
$$XTIMAGE -> TitleImage.xbx  section=11 VA=0x00874D40 length=0x2800
$$XSIMAGE -> SaveImage.xbx   section=12 VA=0x00877540 length=0x1000
```

The compact path additionally requires a successful matching
`XeLoadSection`, the exact section header/index/VA/length, the expected
native file-path suffix, synchronous event/APC/context fields, and
`ByteOffset=NULL`. All other compact forms remain fenced.

Build tag:
`P5AC-NTWRITEFILE236-IMAGESECTIONS-NATIVE-20261020-A`.

Cookie: `P5AC / 0x50354143`.
Link-time guard: `phase5ac_env_build_cookie`.
