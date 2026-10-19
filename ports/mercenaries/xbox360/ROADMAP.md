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
