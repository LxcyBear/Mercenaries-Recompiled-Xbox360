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

## Active

### Phase 4B-B — Native file/handle service slice
**Status: hardware gate A ready for real-Xenon validation.**

Hardware gate:
`ports/mercenaries/xbox360/phase4b_native_file_handles_xex`

Build marker:
`P4B-FILE-20261019-A`

Convert and hardware-prove the cohesive file/handle surface, expected to include:
- `NtCreateFile`
- `NtOpenFile`
- `NtReadFile`
- `NtWriteFile`
- `NtSetInformationFile`
- `NtQueryInformationFile`
- `NtQueryDirectoryFile`
- `NtQueryFullAttributesFile`
- `NtClose`

Goals:
1. preserve Xbox guest path/layout semantics;
2. isolate XDK file/handle primitives behind a platform boundary;
3. prove representative create/open/read/write/query/close behavior on Xenon;
4. rerun the exact retail surface audit and regressions;
5. reduce the remaining direct host-backed count without weakening fallbacks or ABI checks.

## Next

### Phase 4B-C — Remaining memory/protection and residual host surface
Expected focus:
- `NtFreeVirtualMemory`
- `MmSetAddressProtect`
- any residual semantic host calls left after the file/handle migration

The exact worklist must come from the current audit after 4B-B; do not assume the baseline list remains unchanged.

### Phase 4C — Native translated-game startup path
Begin linking/executing the real translated Mercenaries startup path with the migrated Xenon service layer.

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
