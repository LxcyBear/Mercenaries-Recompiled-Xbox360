# Repository code map

Snapshot: 2026-10-19. Entries are **Verified from current implementation** unless explicitly marked otherwise. Follow symbols as well as paths: generated chunk numbers and line numbers change after regeneration. See [ARCHITECTURE](ARCHITECTURE.md) for evidence definitions.

## Xbox 360 native-port status

The native Xbox 360 port has completed **Phase 3 - Recompiler ABI** on real Xenon hardware. The final 3N-B gate compiled/linked a 128-function audited translated-code scale pack, verified all anchors live in the loaded XEX, passed maintained x87 rounding/exception checks, passed six independent-reference executions of retail function `0x00208F30`, and exited with XAPI return value 0.

**Phase 4 - Host kernel/platform services is active. Phase 4A is locked PASS and Phase 4B service migration is complete; Phase 4C native translated-game startup is active next.** The verified retail Mercenaries XBE exposes 111 kernel imports; the locked Phase-4A baseline is 74 explicit bridges, 11 guest data exports, 26 return-zero fallbacks, zero missing or mismatched guest argument-cleanup entries, zero statically referenced fallbacks, and 17 genuine semantic host-backed callable paths. Phase 4B closes that baseline at 0 direct semantic host-backed paths: 15 platform-bound and 2 guest-native. Build `P4B-TIMESYNC-20261019-B` passed on real Xenon hardware (50 MHz QPC, 20.304 ms relative delay, 2.000 ms stall, 20.062 ms wait timeout, correct event/timer delivery). Phase 4B-A2 then migrated six timing/synchronization import paths through `src/platform/kernel_time_sync.*` and passed the full verification gate: 11 remaining direct semantic host-backed imports, 6 Phase-4B platform-bound imports, 0 ABI metadata errors, 0 referenced fallbacks, the 7,722-case deadline regression, and both platform-boundary regressions. See [phase4a_kernel_surface_audit](ports/mercenaries/xbox360/phase4a_kernel_surface_audit) and [phase4b_native_time_sync_xex](ports/mercenaries/xbox360/phase4b_native_time_sync_xex).


### Xbox 360 phase progression map

| Phase | Status | Proof / purpose |
| --- | --- | --- |
| 3A | Complete | Scalar guest-memory semantics on Xenon. |
| 3B | Complete | x87 guest-memory semantics. |
| 3C | Complete | SSE/MMX guest-memory semantics. |
| 3D | Complete | Runtime guest-memory execution surface. |
| 3E | Complete | First real retail translated function executes in the XDK harness. |
| 3F | Complete | Translated tail-call path. |
| 3G | Complete | Direct translated-call path. |
| 3H | Complete | Indirect-call / ICALL path. |
| 3I | Complete | Composite translated slice. |
| 3J | Complete | Dependency-closed translated cluster on real hardware. |
| 3K | Complete | Wider control/flags plus mixed x87/XMM architectural state. |
| 3L | Complete | Bounded translated loop surface. |
| 3M | Complete | Maintained x87 rounding/exception behavior. |
| 3N / 3N-B | **Phase 3 final PASS** | 128-function audited translated-code scale pack; loaded-XEX anchors, x87 checks, six independent-reference runs of retail `0x00208F30`, XAPI return 0. |
| 4A | **Locked PASS** | Exact 111-import guest kernel surface + ABI audit; 17 semantic host-backed callable paths at baseline. |
| 4B-A | **Hardware PASS** | Native Xenon timing/synchronization primitive gate. |
| 4B-A2 | **Complete PASS** | Six timing/sync paths migrated to `merc_platform_*`; verification passes at 11 direct host-backed + 6 platform-bound, 0 ABI errors, 0 referenced fallbacks, 7,722 deadline cases PASS, and platform-boundary regressions PASS. |
| 4B-B | **Hardware PASS** | `P4B-FILE-20261019-A` passed on real Xenon: create/open/read/write, offsets, size/query, truncate, attributes, enumeration, not-found behavior, and cleanup all PASS. |
| 4B-B2 | **Complete PASS** | Nine file/handle imports route through `merc_platform_file_*`; audit/regressions pass at 2 direct host-backed + 15 platform-bound, 0 ABI errors, and 0 referenced fallbacks. |
| 4B-C | **Hardware PASS** | `P4B-MEMPROT-20261019-B` passed on real Xenon: tracked release/reuse, logical protection, decommit/recommit, zero-init, bounds and stale-release behavior all PASS. |
| 4B-C2 | **Complete PASS** | Final audit/regressions pass at 0 direct host-backed + 15 platform-bound + 2 guest-native, 0 ABI errors and 0 referenced fallbacks. |
| 4C | **Active** | Link and execute the first real retail-derived translated Mercenaries startup path with the migrated Xenon service layer. |
| 4C-A | **Complete PASS** | `xbe_entry_point` at `0x0022964A`; 40 directly reachable translated bodies, depth 8, 5,918 guest bytes, 111,376 generated-source bytes, 0 missing direct dependencies, 14 dynamic/indirect-boundary bodies. |
| 4C-B | **Hardware PASS** | Real `xbe_entry_point` ran on Xenon to the first live dynamic dispatch with no guest fault: `0x0022B4D7 -> 0x800000FF`, identified as `PsCreateSystemThreadEx` ordinal 255. |
| 4C-C | **Hardware PASS** | Real Xenon capture: `PsCreateSystemThreadEx` StartRoutine=`0x0022B43F`, ctx1=`0x002295D6`, ctx2=`0x00000000`, exact 44-byte frame, fault=0. |
| 4C-D | **Complete PASS** | `0x0022B43F` exact function; 6 bodies, depth 2, 460 guest bytes, 8,556 source bytes, 0 missing direct dependencies, 5 dynamic-boundary bodies. |
| 4C-E | **Hardware PASS** | Real entry -> ordinal 255 -> live StartRoutine `0x0022B43F` executed on Xenon; next boundary is `0x0022B363 -> 0x80000115`, fault=0. |
| 4C-F | **Hardware PASS** | Ordinal 277 `RtlEnterCriticalSection` executed with live guest CS `0x00312FC0`, exact 8-byte frame and stack restoration; next live target is `0x80000126`. |
| 4C-G | **Hardware PASS** | Ordinal 277/294 enter/leave pair executed on Xenon with balanced 8-byte frames; next live ICALL is `0x002295D6`, proving the thread ctx1 is the executable startup callback. |
| 4C-H | **Blocked after real callback entry** | Callback `0x002295D6` executed on hardware and reached `0x0022C4DF`; next stop was `GUEST_FAULT` at translated VA `0x0022C4FF`, with `esp == saved_esp`. |
| 4C-I | **Hardware diagnostic PASS** | First rejected guest access is READ32 `0x80000142` from translated caller `0x0022C4DF`; ordinal 322 resolves to guest-visible DATA export `XboxHardwareInfo`. |
| 4C-J | **Hardware PASS** | Live ordinal-322 data relocation succeeded at thunk slot `0x002DBE0C`; callback advanced to READ16 `0x80000148` with ECX=`0x80000144`, identifying ordinal 324 `XboxKrnlVersion` +4. |
| 4C-K | **Hardware PASS** | Startup DATA relocations 156/322/324 succeeded; real callback continued with `fault=0` to `DIRECT_FRONTIER caller=0x0022C4DF target=0x0022C47B`. |
| 4C-L | **Hardware PASS** | Live target `0x0022C47B` executed; first new dependency is READ32 `0x8001003C`, inside the intentionally fenced xboxkrnl image page. |
| 4C-M | **Hardware PASS** | Kernel-header model removed the `0x8001003C` blocker; trace advanced to translated `0x0022C28B` and stopped cleanly at kernel target `0x8000002F` (ordinal 47) with `fault=0`. |
| 4C-N | **Hardware PASS** | Ordinal 47 returned through the exact live 12-byte frame; startup continued with `fault=0` to `DIRECT_FRONTIER caller=0x0022C28B target=0x0022F128`. |
| 4C-O | **Hardware PASS** | `0x0022F128` executed; startup reached kernel target `0x8000006B` with `fault=0` and exact 16-byte frame. |
| 4C-P | **Hardware PASS** | `KeInitializeDpc` guest object initialization succeeded; next boundary is `ICALL_SAFE target=0x80000071` (ordinal 113) from `0x0022F128`, `fault=0`. |
| 4C-Q | **Hardware PASS** | `KeInitializeTimerEx` guest KTIMER initialization succeeded; Q main/env cookie matched and startup reached `DIRECT_FRONTIER caller=0x0022F128 target=0x0022C5A4`, `fault=0`. |
| 4C-R | **Package prep ready** | Add only `0x0022C5A4` to the translated pack; the previous C5A4 boundary is forbidden from counting as progress and the R main/env cookie is unique. |

This table is the continuation of the Phase-3 hardware map: later phases should only advance when their stated evidence gate passes.

## Start with the question

| Need to understand/change | Start here | Then follow |
| --- | --- | --- |
| Installation failure | [setup_launcher.c](ports/mercenaries/src/setup_launcher.c) validation/worker paths | Extractor exit, inventory, marker shortcut and XBE hash. |
| Runtime startup/memory mapping | [main.c](ports/mercenaries/src/main.c): `WinMain`, `host_graphics_init` | [xbox_memory_layout.c](src/kernel/xbox_memory_layout.c), exception/MMIO setup. |
| Wrong instruction result/missing call/stack drift | [recomp_types.h](ports/mercenaries/src/recomp/recomp_types.h), [lifter.py](tools/recomp/lifter.py) | [translator.py](tools/recomp/translator.py), discovery, generated body, [Patch-Generated.py](ports/mercenaries/scripts/Patch-Generated.py). |
| Import arguments/return/callback timing | [kernel_bridge.c](src/kernel/kernel_bridge.c) | [kernel_thunks.c](src/kernel/kernel_thunks.c), lower kernel module. |
| Xbox 360 Phase 4 / native kernel service conversion | [ROADMAP](ports/mercenaries/xbox360/ROADMAP.md), [phase4a_kernel_surface_audit](ports/mercenaries/xbox360/phase4a_kernel_surface_audit) (locked PASS), [phase4b_native_time_sync_xex](ports/mercenaries/xbox360/phase4b_native_time_sync_xex), [kernel_time_sync.c](src/platform/kernel_time_sync.c) | Phase 4B-A/A2, 4B-B/B2 and 4B-C/C2 complete; Phase 4C is now the active translated-startup path. |
| Guest allocation failure | [recomp_manual.c](ports/mercenaries/src/recomp_manual.c) | Layout allocator, title metadata, Lua/XMem fallback ownership. |
| Missing draw/render state/alias surface | [nv2a_pgraph_d3d11.c](src/nv2a/nv2a_pgraph_d3d11.c) | [nv2a_core.c](src/nv2a/nv2a_core.c), D3D resources/states/shaders. |
| FPS cap/stutter/adapter selection | [d3d8_device.c](src/d3d/d3d8_device.c) | [d3d8_frame_timing.h](src/d3d/d3d8_frame_timing.h), host service, options, guest clock patches. |
| Distorted scope/UI/world projection | [recomp_ui.c](ports/mercenaries/src/recomp_ui.c), [menu_layout_guest.h](ports/mercenaries/src/menu_layout_guest.h) | Manual camera hooks, generated sites, viewport/presentation; these are distinct transforms. |
| Silent dialogue/HQ softlock | [recomp_manual.c](ports/mercenaries/src/recomp_manual.c), [voice_callback_queue.h](ports/mercenaries/src/voice_callback_queue.h) | Lua/voice lifecycle hooks, allocation failures, cue notifications, then APU output. |
| Audio volume/clicks/missing channels | [apu_core.c](src/apu/apu_core.c), [apu_vp.c](src/apu/apu_vp.c), [apu_dsp.c](src/apu/apu_dsp.c) | [apu_xaudio2.c](src/apu/apu_xaudio2.c), guest DSOUND/XACT commands. |
| Movie/XMV decode, cadence or volume | Generated XMV functions plus [xmv_fast_helpers.h](ports/mercenaries/src/recomp/xmv_fast_helpers.h) | [kernel_hal.c](src/kernel/kernel_hal.c) field pin, [apu_core.c](src/apu/apu_core.c) XGSCNT/output timing, movie checkpoints/volume hooks in [recomp_manual.c](ports/mercenaries/src/recomp_manual.c), and changing linear textures in PGRAPH. |
| Bindings/context/prompts | [recomp_controls.c](ports/mercenaries/src/recomp_controls.c) | [controls_mapping.h](ports/mercenaries/src/controls_mapping.h), [recomp_prompts.c](ports/mercenaries/src/recomp_prompts.c), [xinput_device.c](src/input/xinput_device.c). |
| Save path/time | [kernel_path.c](src/kernel/kernel_path.c), [kernel_file.c](src/kernel/kernel_file.c) | Bridge handles/layouts and [kernel_xbox.c](src/kernel/kernel_xbox.c) EEPROM. |
| OG Bugs scope | [recomp_original_bugs.c](ports/mercenaries/src/recomp_original_bugs.c) | [ai_boarding.h](ports/mercenaries/src/ai_boarding.h) also reads the option directly. |
| Mod capacity | [mod_compatibility.c](ports/mercenaries/src/mod_compatibility.c), [recomp_world_properties.c](ports/mercenaries/src/recomp_world_properties.c) | Memory initialization and generated pool relocation. |
| Birds/F9 features | [boids.c](ports/mercenaries/src/boids.c), [boids_guest.h](ports/mercenaries/src/boids_guest.h) | [dev_spawn.h](ports/mercenaries/src/dev_spawn.h), [boid_wings.h](ports/mercenaries/src/boid_wings.h). |
| Release/source contents | [Package-Preview.py](ports/mercenaries/scripts/Package-Preview.py) | [Archive-GeneratedProvenance.py](ports/mercenaries/scripts/Archive-GeneratedProvenance.py), [source_package_policy.py](tools/recomp/source_package_policy.py). |
| Tests/known failures | [run_tests.py](tools/recomp/run_tests.py) | [maintenance-validation.md](docs/maintenance-validation.md); CMake alone is insufficient. |

## Directory roles

| Location | Role |
| --- | --- |
| [CMakeLists.txt](CMakeLists.txt), [include/xbox/xboxrecomp.h](include/xbox/xboxrecomp.h) | Runtime build aggregation and umbrella interface. |
| [src/kernel](src/kernel) | Guest bridge, memory, paths/files, synchronization, HAL/EEPROM, crypto, logging. |
| [src/nv2a](src/nv2a) | GPU state, MMIO, pushbuffer interpreter and host PGRAPH. Replay/demo assets are not automatically title runtime inputs. |
| [src/d3d](src/d3d) | D3D8-shaped C API on D3D11; resources/states, shaders/cache, presentation. |
| [src/apu](src/apu), [src/audio](src/audio) | APU processing/output and supplementary DirectSound wrappers respectively. |
| [src/input](src/input), [src/platform](src/platform) | Controller backends/activity and platform wrappers. |
| [ports/mercenaries](ports/mercenaries) | Product build, generated integration, title policies, launcher, resources/data/assets. |
| [ports/mercenaries/xbox360](ports/mercenaries/xbox360) | Native Xenon/XDK hardware gates and the active Phase 4 kernel/platform migration path. Phase 3 proof harnesses are historical evidence; new platform work begins under `phase4a_kernel_surface_audit`. |
| [tools/xbe_parser](tools/xbe_parser), [tools/disasm](tools/disasm), [tools/func_id](tools/func_id), [tools/recomp](tools/recomp) | Offline analysis, discovery, lifting, validation, fixtures and oracles. |
| [tools/diagnostics](tools/diagnostics) | Development capture/replay/inspection; some tools mutate a live process. |
| [tools/debug](tools/debug), [tools/debug_symbols](tools/debug_symbols), [tools/symbols](tools/symbols), [tools/ghidra_naming](tools/ghidra_naming) | Debugging/name evidence tooling, not a second runtime. |
| [tools/linux](tools/linux), [tools/xmv](tools/xmv) | Platform support and movie analysis. |
| [templates](templates) | Recompilation templates, distinct from the title ABI header actually compiled. |
| [third_party](third_party), [src/licenses](src/licenses) | Dependencies, notices and source inventories; root licensing does not supersede component terms. |
| [docs](docs) | Runtime evidence, maintenance/release procedures and validation records. |
| Local artifacts/build/generated/extracted-data trees | Evidence and products, not a public-source inclusion policy. |

## Build/generation entry points

- [Build-From-Iso.ps1](ports/mercenaries/scripts/Build-From-Iso.ps1): extraction, generation, build and provenance orchestration.
- [Recompile.ps1](ports/mercenaries/scripts/Recompile.ps1): supported-XBE check, iterative seed/discovery passes, archival before replacement, reviewed function ranges/manual entries, lifting and patching.
- [__main__.py](tools/recomp/__main__.py): translator CLI. `BatchTranslator` coordinates functions; `FunctionTranslator` handles individual translations. [config.py](tools/recomp/config.py) installs executable-specific globals; concurrent unrelated inputs in one Python process are not an established interface.
- [Patch-Generated.py](ports/mercenaries/scripts/Patch-Generated.py): ordered `GeneratedPatch` operations and larger transformations. A behavioral build stage, not formatting.
- [Build.ps1](ports/mercenaries/scripts/Build.ps1), [port CMake](ports/mercenaries/CMakeLists.txt): Windows toolchain configuration and native target assembly.
- [Generate-Shader-Warmup.py](ports/mercenaries/scripts/Generate-Shader-Warmup.py), [Dev-Vehicle-Catalog.cmake](ports/mercenaries/scripts/Dev-Vehicle-Catalog.cmake), [Mission-Script-Fixes.cmake](ports/mercenaries/scripts/Mission-Script-Fixes.cmake): reviewed input-to-compiled catalog/script generation.
- [Archive-GeneratedProvenance.py](ports/mercenaries/scripts/Archive-GeneratedProvenance.py): generated evidence and maintained source archives.
- [Package-Preview.py](ports/mercenaries/scripts/Package-Preview.py): validated player payload, optional separate source delivery and package verification.

## Important structures and interfaces

| Structure/interface | Definition/use | Meaning |
| --- | --- | --- |
| Register globals, memory macros, `RECOMP_ICALL`, `RECOMP_ITAIL`, `XBOX_REP_MOVS` | [recomp_types.h](ports/mercenaries/src/recomp/recomp_types.h) | Guest ABI/instruction helpers. |
| Thunk table/bridge dispatcher | [kernel_thunks.c](src/kernel/kernel_thunks.c), [kernel_bridge.c](src/kernel/kernel_bridge.c) | Ordinal routes plus argument/handle/layout adaptation. |
| Allocation/mapping records | [xbox_memory_layout.c](src/kernel/xbox_memory_layout.c), [recomp_manual.c](ports/mercenaries/src/recomp_manual.c) | Backing, aliases, title metadata and fallback ownership are separate. The layout heap has a fixed 16,384-record table; the manual CRT heap starts at 16,384 records and grows under an `SRWLOCK`. |
| `NV2AState`, PGRAPH state | [nv2a_state.h](src/nv2a/nv2a_state.h), [nv2a_pgraph_d3d11.c](src/nv2a/nv2a_pgraph_d3d11.c) | GPU register/command state and its host realization. |
| `GuestColorSurface`, `GuestDepthSurface` | [nv2a_pgraph_d3d11.c](src/nv2a/nv2a_pgraph_d3d11.c) | Address/format/pitch, host objects, validity, dimensions and synchronization history. |
| D3D8-shaped COM-style C wrappers | [d3d8_xbox.h](src/d3d/d3d8_xbox.h), [d3d8_internal.h](src/d3d/d3d8_internal.h) | Host renderer interface, not complete desktop D3D8. |
| `MCPXAPUState` | [apu_state.h](src/apu/apu_state.h) | APU registers, VP/GP/EP state, monitor buffer, locks and worker coordination. It does not own the global supplementary software mixer. |
| `APUMixerVoice` | [apu.h](src/apu/apu.h), [apu_core.c](src/apu/apu_core.c) and audio consumers | Global supplementary-mixer slot borrowing PCM from an owner; access is not consistently locked. |
| `DSoundBuffer` | [dsound_device.c](src/audio/dsound_device.c) | Refcounted PCM owner. Release stops/frees the slot first, but `SetBufferData` currently replaces storage without equivalent synchronization. |
| Applied/pending option records | [recomp_options.c](ports/mercenaries/src/recomp_options.c) | Persisted/applied configuration versus staged menu changes. |
| Boid world/wing state | [boids.h](ports/mercenaries/src/boids.h), [boid_wings.h](ports/mercenaries/src/boid_wings.h) | Host motion/animation policy; guest adapter owns actor references. |

## Title integration files that are easy to miss

Many title `.h` files contain implementation with internal linkage and are included into `recomp_manual.c` in meaningful order. Moving them into separate translation units can change static state, macro visibility and cached environment settings.

| Files | Role |
| --- | --- |
| [voice_callback_queue.h](ports/mercenaries/src/voice_callback_queue.h) | Owns copied continuation names and protected-scope/serial cancellation. |
| [stream_admission.h](ports/mercenaries/src/stream_admission.h) | Title stream admission; follow manual/generated consumers before changing policy. |
| [ai_boarding.h](ports/mercenaries/src/ai_boarding.h), [carry_pickup_guest.h](ports/mercenaries/src/carry_pickup_guest.h), [cargo_helicopters.h](ports/mercenaries/src/cargo_helicopters.h) | Narrow interactions using guest object layouts. |
| [turret_camera_roll.h](ports/mercenaries/src/turret_camera_roll.h), [winch_camera_preview.h](ports/mercenaries/src/winch_camera_preview.h), [freecam_streaming.h](ports/mercenaries/src/freecam_streaming.h) | Camera integration/diagnostics, distinct from general render matrices. |
| [dev_player_actor.h](ports/mercenaries/src/dev_player_actor.h), [dev_spawn.h](ports/mercenaries/src/dev_spawn.h), [dev_mission_guest.h](ports/mercenaries/src/dev_mission_guest.h), [dev_battle_guest.h](ports/mercenaries/src/dev_battle_guest.h) | Guest-safe execution of host developer requests. Player lookup is shared. |
| [dev_menu.c](ports/mercenaries/src/dev_menu.c), [dev_overlay.c](ports/mercenaries/src/dev_overlay.c), [free_cam.c](ports/mercenaries/src/free_cam.c), [dev_missions.c](ports/mercenaries/src/dev_missions.c) | Host UI, request and camera side. |
| [ps2_upgrades.c](ports/mercenaries/src/ps2_upgrades.c), [ps2_retail_mix.h](ports/mercenaries/src/ps2_retail_mix.h), [audio_bank_fixes.c](ports/mercenaries/src/audio_bank_fixes.c) | Optional bank/art additions and targeted sound-bank corrections. |
| [mission_script_fixes.c](ports/mercenaries/src/mission_script_fixes.c), [wmd_inspectors.lua](ports/mercenaries/src/wmd_inspectors.lua) | Fingerprint-selected project correction appended to the matching retail script. |
| [chapter_return.c](ports/mercenaries/src/chapter_return.c), [shop_config.c](ports/mercenaries/src/shop_config.c) | Title progression-return coordination and shop configuration. |
| [shader_warmup.c](ports/mercenaries/src/shader_warmup.c) | Catalog-based precompilation; first-use compilation remains. |

## Validation navigation

[run_tests.py](tools/recomp/run_tests.py) discovers `tools/**/test_*.py` by AST and runs isolated subprocesses, choosing pytest or direct script execution. Native fixtures, retail oracles, source-spelling checks, WARP rendering and live-game tests establish different things. [MAINTENANCE](MAINTENANCE.md) describes which evidence is needed for each subsystem. A developer utility or fixture can explain a decision without being a runtime/build dependency.

## Xbox 360 native-port live frontier

Current Phase-5 hardware frontier (2026-10-20):

- `Prepare-Phase5AS.ps1` / `emit_phase5as_direct_22bbc8.py`: hardware PASS.
- Proven translated chain after persistent-cache setup:
  `0022F0D6 -> 00230060 -> 0022BBC8 -> 00237830 -> 0022B74E -> 0022B7B2`.
- Current kernel frontier: `0x800000CB`, original-Xbox ordinal 203
  `NtOpenSymbolicLinkObject`, reached from translated caller `0x0022B7B2`
  with `fault=0`.
- `Prepare-Phase5AT.ps1` / `emit_phase5at_ntopensymlink_capture.py`:
  capture-only next gate. It records the live handle pointer and guest
  `OBJECT_ATTRIBUTES` / `ANSI_STRING` name before any symbolic-link handle
  semantics are implemented.
- Active generated XDK package:
  `build/phase5_subsystem_bringup/post_persist_closure_xdk`.

### Phase-5 symbolic-link object frontier

Phase 5AT hardware proved that translated caller `0x0022B7B2` opens
`\??\D:` through original-Xbox ordinal 203 `NtOpenSymbolicLinkObject`.
That link was already created by the maintained `IoCreateSymbolicLink`
continuation and resolves to `\Device\CdRom0`.

Phase 5AU files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AU.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5au_symlink_object_native.py`

5AU owns a separate `0x53xxxxxx` guest symbolic-link-object handle class,
services ordinals 203 and 215 against the guest link table, and extends
`NtClose` for that handle class. Native file handles remain in the existing
`0x48xxxxxx` table.

### Phase-5 ordinal-215 translated-frame repair

5AU hardware validated `NtOpenSymbolicLinkObject(\??\D:)` and returned
symbolic-link object token `0x53000001`. The next call from
`0x0022B7B2` is ordinal 215 `NtQuerySymbolicLinkObject`, but the translated
callsite reports a 20-byte frame instead of the 16-byte Xbox ABI frame.

Phase 5AV files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AV.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5av_symlink215_savedesp.py`

Repair policy: exact caller `0x0022B7B2` + target `0x800000D7` + observed
20-byte frame only; validate the normal ordinal-215 arguments, record the extra
dword, and resume at `savedEsp - 4`. No global ABI change.

### Phase-5 XeImageFileName data-import frontier

5AV hardware proved the ordinal-215 symbolic-link query repair and guest object
close. Execution then advanced to translated caller `0x00239C23`, which
attempted a 16-bit read from `0x80000146`. That token is Xbox kernel export
ordinal 326, `XeImageFileName`, an ANSI_STRING data object.

Phase 5AW files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AW.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5aw_xeimagefilename_data.py`

Guest data layout:
- `0x0087E040`: ANSI_STRING {Length=26, MaximumLength=27, Buffer=0x0087E050}
- `0x0087E050`: `\Device\CdRom0\default.xbe\0`

Ordinal 326 is relocated in the retail kernel thunk table before translated
execution. The old `0x80000146` fault is explicitly excluded from PASS.

### Phase-5 frontier 0x0023E600

Phase 5AW hardware consumed the relocated ordinal-326 `XeImageFileName`
guest data object and advanced to a fault-free direct call from
`0x00239D6C` to `0x0023E600`.

Phase 5AX files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AX.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5ax_frontier23e600.py`

Policy: exact-function-start validation, generated-body validation, then bounded
depth-2/cap-16 closure promotion. Actual root entry is required and the old
`0x0023E600` boundary is excluded from PASS.

### Phase-5 ordinal-289 caller repair at 0x0022A7A4

Phase 5AX hardware executed `0x0023E600` and advanced to caller
`0x0022A7A4`, which invokes kernel ordinal 289 `RtlInitAnsiString` with a
translated saved-ESP delta of 16 bytes instead of the canonical 12.

Phase 5AY files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AY.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5ay_rtlansi_a7a4.py`

Policy: retain ordinal-289's normal two-argument ABI globally. Repair only exact
caller `0x0022A7A4` with observed frame 16, validate the canonical stack
arguments, resume at `savedEsp-4`, and require a repair proof before PASS.

### Phase-5 Xbox ObDosDevices file namespace

5AY hardware proved the `0x0022A7A4` RtlInitAnsiString repair and exposed the
next dependency: ordinal 190 `NtCreateFile` receives
`OBJECT_ATTRIBUTES.RootDirectory=0xFFFFFFFD` with
`t:\\$u\\contentmeta.xbx`.

`0xFFFFFFFD` is modeled as the Xbox `ObDosDevices` pseudo-root. Phase 5AZ
therefore permits this exact root for NtCreateFile/NtOpenFile and routes
drive-letter paths through the guest-created `\\??\\X:` symbolic-link
table before native sandbox translation. Ordinary nonzero relative root handles
remain fenced.

Phase 5AZ files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5AZ.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5az_obdosdevices.py`

### Phase-5 packed guest ICALL frontier 0x0023D550

5AZ hardware completed the ObDosDevices `t:\\$u\\contentmeta.xbx` path
handling and then reached:

```text
ICALL_SAFE 0x0022C452 -> 0x0023D550
fault=0
```

Phase 5BA files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BA.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5ba_icall23d550.py`

Policy: exact-function-start and generated-body validation, bounded
depth-2/cap-16 closure, target-specific `RECOMP_ICALL_SAFE` packed dispatch,
actual root-entry proof, and exclusion of the old `0x0023D550` boundary from
PASS.

### Phase-5 direct frontier 0x0022DDA4

Phase 5BA hardware proved the runtime-discovered `0x0023D550` indirect entry
and continued through `0x00238533`, `0x00238507`, `0x002384E0`, and
`0x0022B5EF`. The next fault-free direct target is `0x0022DDA4`.

Phase 5BB files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BB.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bb_frontier22dda4.py`

Policy: validate exact function-start identity against the refreshed Phase-3N
baseline, recognize `0x0022DDA4` as a reviewed support-owned manual heap
helper, and pack the coherent `DDA4/E51F/E713` allocate/free/realloc family.
The family reuses the Phase-4C deterministic title heap
`0x008C1000..0x009C0000`. Require actual DDA4 entry plus a maintained
allocation call before PASS, and exclude the old `0x0022DDA4` boundary.


### Phase-5BC broad translated frontier sweep

Phase 5BB hardware entered the maintained `0x0022DDA4` heap allocator,
returned guest allocation `0x008C1000`, then advanced to a new fault-free
safe indirect boundary:

```text
ICALL_SAFE 0x0022C3FA -> 0x00237052
fault=0
esp=0x008BFF48
saved_esp=0x008BFF4C
```

Phase 5BC files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BC.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bc_broad_sweep.py`

5BC changes the Phase-5 progression strategy from one-frontier-per-build to a
bounded broad sweep. It inherits the complete Phase 5BB package, validates
`0x00237052` as an exact generated function start, discovers a depth-6/cap-256
candidate direct closure, then keeps the largest support-clean subset. Candidate
side branches with unresolved non-direct support helpers are pruned from the
pack and remain ordinary runtime fences instead of aborting the whole build;
the hardware-observed seed itself is never pruned or guessed. Safe ICALLs and
previously fenced direct targets may continue automatically only when the exact
target resolves through the retained translated-pack lookup. Ordinary
ICALL/ITAIL boundaries, unknown kernel/device behavior, mid-function targets,
guest faults, ABI/frame anomalies, heap exhaustion, debug breaks, and the
200,000-block execution budget remain hard stops. The goal is to consume
multiple ordinary translated frontiers per hardware run and stop only when
genuinely new runtime knowledge is required.



Hardware result (2026-10-20): PASS. The generic packed ICALL_SAFE dispatcher
entered `0x00237052` from caller `0x0022C3FA`, execution continued through
`0x0023701A`, and the first new hard stop was another fault-free safe indirect
target `0x00237801` from caller `0x0023701A`. This validates the broad-sweep
methodology itself: ordinary packed targets can now be consumed without a new
one-address harness build, while genuinely unknown indirect targets remain
explicit evidence-bearing stops.


### Phase-5BD regional translated sweep

Phase 5BC hardware proved generic packed ICALL_SAFE dispatch by entering
`0x00237052` from `0x0022C3FA`. Execution then continued to `0x0023701A`
and exposed the next fault-free safe indirect target `0x00237801`.

Phase 5BD files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BD.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bd_regional_sweep.py`

5BD deliberately avoids returning to one-address-per-build promotion. It keeps
`0x00237801` as the mandatory hardware-observed seed, adds its bounded
depth-6 direct closure, and pre-packs support-clean exact generated entries in
the nearby `0x00236000..0x00238FFF` region up to 256 new functions total.
The already-proven generic packed ICALL dispatcher can therefore consume
follow-on function-pointer targets in the same startup subsystem when they are
present. Unsupported side branches remain fenced; the mandatory runtime seed,
guest faults, ABI/frame anomalies, kernel/device unknowns, heap exhaustion and
the execution-budget watchdog remain hard stops.


### Phase-5BE forward regional sweep

Phase 5BD hardware passed. The generic dispatcher consumed both
`0x00237052` and `0x00237801` in one run, a second maintained heap
allocation of 128 bytes succeeded at `0x008C1100`, and execution advanced
through `0x00238533 -> 0x00238507 -> 0x002384E0 -> 0x0022B5EF ->
0x0022DDA4` before reaching the next fault-free safe indirect target
`0x00239055`. That target sits only 0x55 bytes beyond the 5BD regional
window, so the stop is treated as a sweep-boundary miss rather than a new
runtime failure.

Phase 5BE files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BE.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5be_forward_sweep.py`

5BE keeps `0x00239055` mandatory, adds its bounded depth-6 direct closure,
and pre-packs a support-clean forward band covering
`0x00239000..0x0023DFFF`, capped at 256 additional functions. The proven
generic packed ICALL/direct dispatcher remains unchanged; unsupported side
branches stay fenced and the mandatory seed is never pruned or guessed.


Phase 5BE hardware passed on 2026-10-20. The generic packed dispatcher
consumed `0x00237052`, `0x00237801`, and `0x00239055` in the same
hardware run. After entering `0x00239055`, the maintained heap allocated
another 2048-byte block at `0x008C1180` with flags `0x8`, translated
execution continued through `0x0023D87C`, and the first new hard stop was the
fault-free safe indirect target `0x0023F22B` from caller `0x0022DDA4`.
This extends the broad-sweep proof beyond the 5BE regional window and confirms
that repeated exact packed ICALL promotion is stable across multiple heap-backed
startup objects in one launch.


### Phase-5BF forward regional sweep

Phase 5BE hardware passed. The generic packed dispatcher consumed
`0x00237052`, `0x00237801`, and `0x00239055` in a single launch.
After the third automatic ICALL promotion, the maintained heap completed a
third allocation (2048 bytes, flags `0x8`) at `0x008C1180`, execution
continued through `0x0023D87C`, and the next hard stop was the fault-free
safe indirect target `0x0023F22B` from caller `0x0022DDA4`.

Phase 5BF files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BF.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bf_forward_sweep.py`

5BF keeps `0x0023F22B` mandatory, adds its bounded depth-6 direct closure,
and pre-packs a support-clean forward band covering
`0x0023E000..0x00245FFF`, capped at 256 additional functions. The inherited
generic packed ICALL/direct dispatcher remains the continuation mechanism;
unsupported side branches stay fenced and the mandatory hardware-observed root
is never pruned or guessed.


### Phase-5BG retail title text-tail sweep

Phase 5BF hardware passed on 2026-10-20. The generic packed dispatcher consumed
four safe indirect translated targets in one launch:
`0x00237052`, `0x00237801`, `0x00239055`, and `0x0023F22B`.
The inherited persistent-storage, VM and maintained-heap proofs remained
stable. Execution then advanced through `0x0022B3F1` and stopped at the next
fault-free safe indirect target `0x002471C0`.

Phase 5BG files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BG.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bg_text_tail_sweep.py`

5BG deliberately widens the next sweep to the remainder of the retail title
`.text` section instead of merely promoting one address. It keeps
`0x002471C0` mandatory, adds its bounded depth-6 direct closure, and
pre-packs support-clean exact generated entries from
`0x00246000..0x0025561F` (the XMV section begins at `0x00255620`), capped
at 256 additional functions. Unsupported side branches remain fenced; the
mandatory hardware-observed seed, guest faults, ABI/frame anomalies,
kernel/device unknowns, heap exhaustion and the execution-budget watchdog
remain hard stops.


### Phase-5BH accumulated direct-frontier mop

Phase 5BG hardware passed on 2026-10-21. The generic packed dispatcher consumed
five safe indirect translated targets in one launch:
`0x00237052`, `0x00237801`, `0x00239055`, `0x0023F22B`, and
`0x002471C0`. The inherited storage, VM, symbolic-link and maintained-heap
proofs remained stable. After entering `0x002471C0`, execution continued
through the translated startup path and stopped fault-free at the direct
boundary `0x0023776D -> 0x0023BE3C`.

Phase 5BH files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BH.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bh_direct_frontier_mop.py`

5BH avoids falling back to one-address direct promotion. It keeps
`0x0023BE3C` mandatory. That address is a reviewed `Recompile.ps1
--manual-function` and the production port supplies it from
`ports/mercenaries/src/recomp_manual.c` as the Xbox CRT `_msize` wrapper,
so the 360 harness routes it through the same maintained semantics over the
Phase-4C title-heap table plus the retail metadata fallback. 5BH also scans the
inherited generated `main.cpp` for every currently fenced
`phase4c_direct_frontier(0x...)` target, filters those to exact generated
unpacked function starts, adds bounded translated closures for them, and packs
the largest support-clean subset while keeping the total new-function cap at
256.
The mandatory hardware-observed root is never pruned or guessed. Unsupported
side branches, guest faults, ABI/frame anomalies, kernel/device unknowns, heap
exhaustion and the execution-budget watchdog remain hard stops.


Phase 5BH hardware passed on 2026-10-21. The maintained Xbox CRT `_msize`
root at `0x0023BE3C` completed repeatedly against the Phase-4C/5BB heap
table, first reporting the 128-byte block at `0x008C1100` and later the
256-byte reallocated block at `0x008C1980`. The run also exercised the
maintained `RtlReAllocateHeap` path successfully. The generic broad-sweep
dispatcher reached 53 safe-ICALL dispatches and 94 direct dispatches in one
launch, including the inherited `0x00237052`, `0x00237801`,
`0x00239055`, `0x0023F22B`, and `0x002471C0` chain plus a large set of
new startup/runtime targets. The first new hard stop was a fault-free
`ICALL_SAFE caller=0x0023A3CE target=0x000B5E50` at tick 15406 with
`fault=0`. This is the strongest hardware proof so far that the broad-sweep
strategy is collapsing many former one-build frontiers into one execution run.


### Phase-5BI low-.text runtime-family sweep

Phase 5BH hardware passed with the strongest broad-sweep result so far:
53 safe-ICALL dispatches, 94 direct dispatches, 15406 translated block ticks,
1190 trace entries, repeated maintained CRT `_msize` execution, and a
successful maintained `RtlReAllocateHeap`. The first new hard stop was
fault-free `ICALL_SAFE caller=0x0023A3CE target=0x000B5E50`.

Phase 5BI files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BI.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bi_low_text_sweep.py`

5BI keeps `0x000B5E50` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining pack budget with nearest support-clean exact
generated entries from `0x000A0000..0x0011FFFF`. The total new-function cap
remains 256. All inherited storage, persistence, VM, heap, CRT-manual and
generic dispatcher proofs remain required; unknown indirect targets,
unsupported kernel/device semantics, guest faults, ABI/frame anomalies, heap
exhaustion and the execution-budget watchdog remain hard stops.

Build tag: `P5BI-LOWTEXTB5E50-20261021-A`.


### Phase-5BJ deep-low retail .text sweep

Phase 5BI hardware passed on 2026-10-21. The low-.text sweep consumed the
mandatory `0x000B5E50` safe-ICALL target repeatedly and continued through a
much larger translated runtime path. The run reached 76 safe-ICALL dispatches,
107 direct dispatches, 18282 translated block ticks, and 1424 trace entries.
The maintained CRT `_msize` path continued to report correct tracked sizes,
and the maintained `RtlReAllocateHeap` path remained healthy. The first new
hard stop was fault-free
`ICALL_SAFE caller=0x0023A3CE target=0x00039B00` with
`esp=0x008BFEF4`, `saved_esp=0x008BFEF8`, and `fault=0`.

Phase 5BJ files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BJ.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bj_deep_low_text_sweep.py`

5BJ keeps `0x00039B00` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
support-clean exact generated functions from the remaining lower retail title
`.text` band `0x00011000..0x0009FFFF`. This complements 5BI's
`0x000A0000..0x0011FFFF` sweep while retaining the same hard-stop policy.

Build tag: `P5BJ-DEEPLOW39B00-20261021-A`.


Phase 5BJ hardware passed on 2026-10-21. The deep-low sweep consumed
`0x00039B00` as safe-ICALL dispatch 77 and continued until the first new
fault-free direct boundary:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x001F2A60`,
with `esp=0x008BFE94`, `saved_esp=0x008BFE94`, `fault=0`,
18578 translated block ticks, and 1445 trace entries. The maintained CRT
`_msize`, `RtlReAllocateHeap`, persistence, filesystem, VM and symbolic-link
proofs remained healthy throughout the run.

The 5BJ preparer had already identified `0x001F2A60` as a support-clean fence
because its translated body calls `recomp_xact_setup_checkpoint`. The
production port implementation of that helper is observational only: with
tracing disabled it does not alter guest state.

### Phase-5BK observational diagnostic mop

Phase 5BK files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BK.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bk_diagnostic_mop.py`

5BK keeps `0x001F2A60` mandatory and supplies maintained tracing-disabled
no-op equivalents for four production diagnostic callbacks:
`recomp_xact_setup_checkpoint`, `recomp_teardown_call_checkpoint`,
`recomp_teardown_item_checkpoint`, and
`recomp_collision_agent_recycle_range`. These helpers are host-side
observability hooks, not gameplay/XACT implementations. After adding them,
5BK re-harvests accumulated exact-generated direct-frontier fences and adds
bounded closures under the existing 256-new-function cap. Unknown subsystem
semantics, ABI/frame anomalies, guest faults, kernel/device gaps, heap
exhaustion and watchdog exhaustion remain hard stops.

Build tag: `P5BK-DIAGMOP1F2A60-20261021-A`.


Phase 5BK hardware passed on 2026-10-21. The diagnostic checkpoint mop cleared
the `0x001F2A60` observational XACT/setup fence and continued dramatically
farther through the translated runtime path. The run reached 316 safe-ICALL
dispatches, 555 direct dispatches, 60852 translated block ticks, 4941 trace
entries, and 229 completed maintained CRT `_msize` calls. The first new hard
stop was fault-free
`ICALL_SAFE caller=0x0023A3CE target=0x0024BC50` with
`esp=0x008BFF40`, `saved_esp=0x008BFF44`, and `fault=0`.
The harness then reported Phase 5BK PASS and returned through XAPI with 0.

### Phase-5BL high retail .text tail saturation sweep

Phase 5BL files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BL.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bl_high_tail_sweep.py`

5BL keeps `0x0024BC50` mandatory, prioritizes its bounded depth-6 direct
closure, then revisits the remaining high retail title `.text` tail
`0x00246000..0x0025561F`. This complements the original 5BG pass, which
could retain only 256 of 733 regional candidates. The remaining pack budget is
filled with the nearest still-unpacked support-clean exact generated entries,
again capped at 256 new functions. All 5BK maintained observational diagnostic
support remains inherited; genuine subsystem/ABI/kernel faults remain fenced.

Build tag: `P5BL-HIGHTAIL24BC50-20261021-A`.


Phase 5BL hardware passed on 2026-10-21. The high-tail saturation sweep
consumed `0x0024BC50` as safe-ICALL dispatch 317 and continued through the
remaining packed high retail `.text` tail to `0x0024CCF0`. The run reached
358 safe-ICALL dispatches, 597 direct dispatches, 61750 translated block
ticks, 5152 trace entries, 270 maintained CRT `_msize` calls, and four
successful maintained `RtlReAllocateHeap` calls. The first new hard stop was
fault-free `ICALL_SAFE caller=0x0023A3CE target=0x000B20C0` with
`esp=0x008BFEEC`, `saved_esp=0x008BFEF0`, and `fault=0`. Phase 5BL
then reported PASS.

### Phase-5BM second-pass low-.text saturation sweep

Phase 5BM files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BM.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bm_low_text_sweep.py`

5BM keeps `0x000B20C0` mandatory, prioritizes its bounded depth-6 direct
closure, then revisits the remaining support-clean low-`.text` band
`0x000A0000..0x0011FFFF`. This complements 5BI, which could retain only 254
support-clean entries from 2178 regional candidates. The remaining budget is
filled with nearest still-unpacked exact generated functions under the same
256-new-function cap. All 5BL persistence, VM, heap, diagnostic-helper and
generic-dispatch proofs remain inherited.

Build tag: `P5BM-LOWTEXTB20C0-20261021-A`.


Phase 5BM hardware passed on 2026-10-21. The second-pass low-.text sweep
proved the reanalysis-promoted `0x000B20C0` function repeatedly through the
generic packed safe-ICALL dispatcher and expanded execution to 807 safe-ICALL
dispatches, 622 direct dispatches, 64101 translated block ticks, 5743 trace
entries, 295 maintained CRT `_msize` calls, and four successful maintained
`RtlReAllocateHeap` calls. The first new hard stop remained fault-free:
`ICALL_SAFE caller=0x0023A3CE target=0x00031080`, with
`esp=0x008BFEF4`, `saved_esp=0x008BFEF8`, and `fault=0`.
The harness reported Phase 5BM PASS and returned through XAPI with 0.

### Phase-5BN second-pass deep-low .text saturation sweep

Phase 5BN files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BN.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bn_deep_low_sweep.py`

5BN keeps `0x00031080` mandatory, prioritizes its bounded depth-6 direct
closure, then revisits the remaining support-clean deep-low retail title
`.text` band `0x00011000..0x0009FFFF`. This is the saturation follow-up
to the original 5BJ pass. The remaining budget is filled with nearest
still-unpacked exact generated functions under the 256-new-function cap.
All 5BM persistence, VM, heap, hardware-promoted low-text, maintained
diagnostic-helper and generic-dispatch proofs remain inherited.

Build tag: `P5BN-DEEPLOW31080-20261021-A`.


### Phase-5 exit gate — Phase 6 subsystem exposure & reconnaissance

After the active Phase-5 translated/runtime saturation sequence is complete,
Phase 5 does **not** close immediately. A mandatory final exit stage will
perform a Phase-6-facing subsystem exposure audit before handoff.

Design contract:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/PHASE5_EXIT_RECON.md`

The exit stage combines a whole-codebase static audit with an observe-only
real-hardware first-touch trace. It must inventory and classify graphics,
audio, movie/video, input, and cross-cutting async/threading/timing/resource
lifecycle boundaries. Genuine unimplemented subsystem operations remain hard
boundaries; the stage may observe them but may not fabricate success or backend
semantics merely to advance execution.

Required handoff content includes:
- subsystem surface inventory;
- hardware first-touch timeline;
- per-boundary ABI/resource/lifecycle evidence;
- first-frame/logo/movie/menu criticality;
- unresolved/high-risk semantics;
- Phase-6 risk map;
- ordered implementation plan for first pixels, startup media, menu/input,
  audio, and later gameplay-only work.

Phase 5 is complete only after both the translated/runtime saturation gate and
this subsystem-reconnaissance exit gate pass. The exit gate is intentionally a
measurement/handoff stage, not a hidden start of Phase 6 implementation.


Phase 5BN hardware passed on 2026-10-21. The second-pass deep-low sweep
consumed `0x00031080` repeatedly through the generic packed safe-ICALL
dispatcher and continued to 843 safe-ICALL dispatches, 626 direct dispatches,
64803 translated block ticks, 5859 trace entries, 299 maintained CRT
`_msize` calls, and four successful maintained `RtlReAllocateHeap` calls.
The first new hard stop was fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x00216BB0`, with
`esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, and `fault=0`.
The harness reported Phase 5BN PASS and returned through XAPI with 0.

### Phase-5BO mid-.text gap saturation sweep

Phase 5BO files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BO.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bo_mid_text_sweep.py`

5BO keeps `0x00216BB0` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x00120000..0x00235FFF`. This interval is the only large retail `.text`
gap that has not yet received a dedicated regional saturation pass: the low
passes stop at `0x0011FFFF`, while Phase 5BD and later forward sweeps begin
at `0x00236000`. All 5BN persistence, VM, heap, diagnostic-helper and
generic-dispatch proofs remain inherited.

Build tag: `P5BO-MIDTEXT216BB0-20261021-A`.


Phase 5BO hardware passed on 2026-10-21. The mid-.text gap sweep consumed
`0x00216BB0` through generic packed direct dispatch and advanced to 845
safe-ICALL dispatches, 630 direct dispatches, 64829 translated block ticks,
5869 trace entries, 301 maintained CRT `_msize` calls, and four successful
maintained `RtlReAllocateHeap` calls. The first new hard stop was fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x000C8140`, with
`esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, and `fault=0`.
The harness reported Phase 5BO PASS, released the guest arena, completed the
post-test heartbeat interval, and returned through XAPI with 0.

### Phase-5BP third-pass low-.text saturation sweep

Phase 5BP files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BP.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bp_low_text_sweep.py`

5BP keeps `0x000C8140` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x000A0000..0x0011FFFF`. This is a third pass over the low-.text family
previously sampled by 5BI and 5BM. All 5BO persistence, VM, filesystem, heap,
diagnostic-helper and generic-dispatch proofs remain inherited.

Build tag: `P5BP-LOWTEXTC8140-20261021-A`.


Phase 5BP hardware passed on 2026-10-21. The third-pass low-.text sweep
consumed `0x000C8140` through generic packed direct dispatch and advanced to
859 safe-ICALL dispatches, 641 direct dispatches, 66991 translated block ticks,
5992 trace entries, 307 maintained CRT `_msize` calls, and four successful
maintained `RtlReAllocateHeap` calls. The first new hard stop was fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x0010B2B0`, with
`esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, and `fault=0`.
The harness reported Phase 5BP PASS, released the guest arena, completed the
post-test heartbeat interval, and returned through XAPI with 0.

### Phase-5BQ fourth-pass low-.text saturation sweep

Phase 5BQ files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BQ.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bq_low_text_sweep.py`

5BQ keeps `0x0010B2B0` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x000A0000..0x0011FFFF`. This is a fourth pass over the same low-.text
family; because 5BP still produced meaningful new execution coverage, the
completion/repeatability gate remains deferred until this frontier family
stops yielding substantive new traversal.

Build tag: `P5BQ-LOWTEXT10B2B0-20261021-A`.


Phase 5BQ hardware passed on 2026-10-21. The fourth-pass low-.text sweep
consumed `0x0010B2B0` through generic packed direct dispatch and advanced to
868 safe-ICALL dispatches, 646 direct dispatches, 67067 translated block ticks,
6018 trace entries, 309 maintained CRT `_msize` calls, and four successful
maintained `RtlReAllocateHeap` calls. The first new hard stop was fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x000F8BB0`, with
`esp=0x008BFF34`, `saved_esp=0x008BFF34`, and `fault=0`.
The harness reported Phase 5BQ PASS, released the guest arena, completed the
post-test heartbeat interval, and returned through XAPI with 0.

Compared with 5BP, 5BQ added only 9 safe-ICALL dispatches, 5 direct dispatches,
2 maintained `_msize` calls, 76 translated block ticks, and 26 trace entries.
That small delta is consistent with late-stage saturation, but the new ordinary
title-code frontier still warrants one more targeted low-.text pass before
moving to repeatability/completion.

### Phase-5BR fifth-pass low-.text saturation sweep

Phase 5BR files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BR.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5br_low_text_sweep.py`

5BR keeps `0x000F8BB0` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x000A0000..0x0011FFFF`. If this pass yields another very small delta or
converges on an already-known/owned boundary, the next planned step is the
Phase-5 completion/repeatability gate rather than another broad saturation
pass.

Build tag: `P5BR-LOWTEXTF8BB0-20261021-A`.


Phase 5BR hardware passed on 2026-10-21. The fifth-pass low-.text sweep
consumed `0x000F8BB0` through generic packed direct dispatch and advanced to
930 safe-ICALL dispatches, 722 direct dispatches, 67954 translated block ticks,
6284 trace entries, 346 maintained CRT `_msize` calls, and four successful
maintained `RtlReAllocateHeap` calls. The first new hard stop was fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x00105020`, with
`esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, and `fault=0`.
The harness reported Phase 5BR PASS and released the guest arena. The captured
log ended during the post-test heartbeat interval before the final proof-end /
XAPI return line, so later completion/repeatability runs should retain the full
tail.

Compared with 5BQ, 5BR added 62 safe-ICALL dispatches, 76 direct dispatches,
37 maintained `_msize` calls, 887 translated block ticks, and 266 trace
entries. This is still meaningful new traversal, so the completion/repeatability
gate remains deferred.

### Phase-5BS sixth-pass low-.text saturation sweep

Phase 5BS files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BS.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bs_low_text_sweep.py`

5BS keeps `0x00105020` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x000A0000..0x0011FFFF`. Completion/repeatability should begin only after
this frontier family stops producing substantive new traversal.

Build tag: `P5BS-LOWTEXT105020-20261021-A`.


Phase 5BS hardware passed on 2026-10-21. The sixth-pass low-.text sweep
consumed `0x00105020` through generic packed direct dispatch and advanced to
1253 safe-ICALL dispatches, 988 direct dispatches, 73303 translated block
ticks, 7280 trace entries, 386 maintained CRT `_msize` calls, and four
successful maintained `RtlReAllocateHeap` calls. The first new hard stop was
fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x00191680`, with
`esp=0x008BFF00`, `saved_esp=0x008BFF00`, and `fault=0`.
The harness reported Phase 5BS PASS, released the guest arena, completed the
post-test heartbeat interval, ended the proof cleanly, and returned through
XAPI with 0.

Compared with 5BR, 5BS added 323 safe-ICALL dispatches, 266 direct dispatches,
40 maintained `_msize` calls, 5349 translated block ticks, and 996 trace
entries. This is substantial new traversal. The new frontier also crossed from
the low-.text band into the mid-.text region previously swept by 5BO.

### Phase-5BT second-pass mid-.text saturation sweep

Phase 5BT files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BT.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bt_mid_text_sweep.py`

5BT keeps `0x00191680` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x00120000..0x00235FFF`. This is a second pass over the mid-.text region;
completion/repeatability remains deferred until this cross-region frontier
family stops producing substantive new traversal.

Build tag: `P5BT-MIDTEXT191680-20261021-A`.


Phase 5BT hardware passed on 2026-10-21. The second-pass mid-.text sweep
consumed `0x00191680` through generic packed direct dispatch and advanced to
1261 safe-ICALL dispatches, 1000 direct dispatches, 73402 translated block
ticks, 7316 trace entries, 394 maintained CRT `_msize` calls, and four
successful maintained `RtlReAllocateHeap` calls. The first new hard stop was
fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x001462E0`, with
`esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, and `fault=0`.
The harness reported Phase 5BT PASS, released the guest arena, completed the
post-test heartbeat interval, ended the proof cleanly, and returned through
XAPI with 0.

Compared with 5BS, 5BT added only 8 safe-ICALL dispatches, 12 direct
dispatches, 8 maintained `_msize` calls, 99 translated block ticks, and 36
trace entries. This is strong convergence evidence, but the newly exposed
ordinary title-code frontier remains unexplained.

### Phase-5BU third-pass mid-.text saturation sweep

Phase 5BU files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BU.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bu_mid_text_sweep.py`

5BU keeps `0x001462E0` mandatory, prioritizes its bounded depth-6 direct
closure, then fills the remaining 256-new-function budget with nearest
still-unpacked support-clean exact generated functions from
`0x00120000..0x00235FFF`. If this pass again produces only a collapsed delta
or lands on an already-known/owned boundary, the next planned step is the
Phase-5 completion/repeatability gate instead of another saturation sweep.

Build tag: `P5BU-MIDTEXT1462E0-20261021-A`.


Phase 5BU hardware passed on 2026-10-21. The third-pass mid-.text sweep
consumed `0x001462E0` through generic packed direct dispatch and advanced
only a collapsed amount beyond 5BT: 1262 safe-ICALL dispatches, 1002 direct
dispatches, 73417 translated block ticks, 7322 trace entries, 395 maintained
CRT `_msize` calls, and four successful maintained `RtlReAllocateHeap`
calls. The first new hard stop remained fault-free:
`DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`, with
`esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, and `fault=0`.
The harness reported Phase 5BU PASS, released the guest arena, completed the
post-test heartbeat interval, ended the proof cleanly, and returned through
XAPI with 0.

Compared with 5BT, 5BU added only one safe-ICALL dispatch, two direct
dispatches, one maintained `_msize` call, 15 translated block ticks, and six
trace entries, with the realloc count unchanged. This is the strongest
late-stage convergence signal so far.

### Phase-5BV frozen-pack repeatability gate

Phase 5BV files:
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5BV.ps1`
- `ports/mercenaries/xbox360/phase5_subsystem_bringup/emit_phase5bv_repeatability.py`

5BV intentionally adds zero translated members. It regenerates the exact 5BU
pack, relabels the harness as a repeatability build, preserves persistent
Partition0 state, and requires three consecutive hardware launches of the same
XEX to reproduce the exact fault-free endpoint candidate
`DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`.

The expected deterministic translated-runtime state for every run is:
1262 safe-ICALL dispatches, 1002 direct dispatches, 395 maintained CRT
`_msize` calls, four successful reallocations ending at 2048 bytes, 73417
translated block ticks, 7322 trace entries, `fault=0`, guest-arena release,
proof-end, and XAPI return 0.

The same XEX must be used for all three runs without rebuilding or deleting
`game:\merc360-partition0\partition0-config.bin`. If the three runs match,
the translated/runtime repeatability gate passes and the project proceeds to
the mandatory Phase-5 exit reconnaissance stage, where the remaining stable
boundary and broader graphics/audio/movie/input surface are classified before
Phase 6.

Build tag: `P5BV-REPEATABILITY-20261021-A`.


### Phase-5BV repeatability gate — hardware PASS

Phase 5BV passed the frozen-pack repeatability gate on real Xbox 360 hardware
on 2026-10-21.

One freshly built `P5BV-REPEATABILITY-20261021-A` XEX was launched three
consecutive times without rebuilding and with persistent Partition0 backing
left intact. All three runs reproduced the same translated/runtime endpoint
and counters exactly:

- boundary: `DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`
- `esp=0x008BFF3C`, `saved_esp=0x008BFF3C`
- safe-ICALL dispatches: 1262
- direct dispatches: 1002
- maintained CRT `_msize` calls: 395
- maintained realloc calls: 4
- final allocation size: 2048 bytes
- translated block ticks: 73417
- trace entries: 7322
- `fault=0`
- guest arena released
- proof end reached
- XAPI return value 0

The third cumulative xbWatson capture contained exactly three 5BV build-tag
starts and exactly three matching `0014CD30` endpoint records / repeatability
PASS records / XAPI-zero returns. This closes the translated/runtime
repeatability requirement.

Phase 5 coverage expansion is now frozen. The next and final Phase-5 exit gate
is the already-defined Phase-6 subsystem exposure & reconnaissance pass in
`ports/mercenaries/xbox360/phase5_subsystem_bringup/PHASE5_EXIT_RECON.md`.
That gate inventories and observe-only traces graphics/display, audio,
movies/video, input, and cross-cutting async/thread/timer/resource/path/endian/
lifecycle surfaces before Phase 6 implementation work begins.


### Phase 5 exit reconnaissance — PASS / PHASE 5 COMPLETE

The mandatory Phase-5 exit reconnaissance gate passed on 2026-10-21.

Command:
`ports/mercenaries/xbox360/phase5_subsystem_bringup/Prepare-Phase5ExitRecon.ps1`

Result:
- `[Phase5Exit] EXIT RECON RESULT: PASS`
- `[Phase5Exit] READY / PASS`
- stable endpoint `DIRECT_FRONTIER 0x0023A3CE -> 0x0014CD30`
- endpoint classified as `exact_generated_title_function`
- generated source: `recomp_0006.c`
- original range: `0x0014CD30-0x0014CD9C`
- direct refs: `0x0014CD30`, `0x001FA0B0`, `0x002370B8`
- five required subsystem families inventoried
- six Phase-6 risks ranked
- no graphics/audio/movie/input backend success fabricated

The exit audit produced all mandatory handoff artifacts:
- `phase5-exit-subsystem-surface.json`
- `phase5-exit-subsystem-surface.md`
- `phase5-exit-first-touch.txt`
- `phase6-risk-map.json`
- `phase6-handoff.md`

Together with the Phase 5BV 3/3 frozen-pack hardware repeatability PASS, this
satisfies the Phase-5 completion criteria. Phase 5 is **100% complete**.

The next active development phase is **Phase 6 — Native Xbox 360 graphics
(Xenos)**. The first implementation target is an independently rendered native
Xenos test surface, followed by guest-rendered first pixels, the main menu, and
a reproducible 3D scene.


### Phase 6 — Native Xbox 360 graphics (Xenos) — ACTIVE

Phase 5 closed at 100% on 2026-10-21 after:
- Phase 5BV frozen-pack hardware repeatability: 3/3 identical boots;
- stable endpoint `0x0014CD30` classified as exact generated title code;
- mandatory exit reconnaissance: `READY / PASS`;
- all required subsystem-surface, first-touch, risk-map and handoff artifacts
  generated without fabricating backend functionality.

Active branch: `xbox360/phase6-native-graphics`.

Phase-6 graphics status:
- **DONE:** initial Mercenaries NV2A pushbuffer/format/swizzle/render-state/
  vertex-program/combiner/surface-alias inventory.
- **IN PROGRESS:** isolate D3D11/DXGI assumptions behind a backend-neutral
  presentation/texture/draw seam.
- **NEXT HARDWARE MILESTONE:** initialize the Xbox 360 graphics device and
  render an independent native Xenos test surface.
- Later Gate-6 milestones: minimal 2D/textured draw + flip, required
  shaders/vertex formats/state/synchronization, first guest-rendered frame,
  main-menu graphics, reproducible 3D scene, then frame-time/GPU-memory/error
  instrumentation.

Detailed plan:
`ports/mercenaries/xbox360/phase6_native_graphics/PHASE6_XENOS_PLAN.md`.


### Phase 6A — native Xenos surface proof

Source:
- `ports/mercenaries/xbox360/phase6_native_graphics/xenos_surface_xex/main.cpp`
- `ports/mercenaries/xbox360/phase6_native_graphics/xenos_surface_xex/BUILD_PHASE6A.md`

Build tag: `P6A-XENOS-SURFACE-20261021-A`.

The first Phase-6 hardware test is deliberately independent of Mercenaries
guest rendering. It uses the real Xbox 360 XDK D3D9 surface:
`Direct3D_CreateDevice` -> `D3DDevice_Clear` -> `D3DDevice_Present`.

Initial mode is conservative 640x480 A8R8G8B8, one back buffer, no MSAA,
no depth/stencil and presentation interval one. The test cycles dark green,
blue, red and white for up to 15 seconds, logs through xbWatson/debug output,
accepts controller A as an early exit, and never fakes graphics success.

Phase 6A remains **unpassed** until real Xbox 360 hardware visibly presents
the frames and the log reports device creation + Phase-6A PASS + clean XAPI
return. After that, Phase 6B isolates the proven Xenos presentation/resource
primitives behind the backend-neutral seam used by translated guest graphics.


### Phase 6A — first visible Xenos hardware output

Real Xbox 360 hardware visibly presented the intended Phase-6A color sequence:

- dark green
- blue
- red
- grey/white

This confirms that the native Xbox 360 D3D device/backbuffer/presentation path
is reaching the physical display. The first visible Xenos output milestone is
therefore achieved.

This is not yet marked as the complete Phase-6A gate until the corresponding
xbWatson/debug tail confirms the expected device-creation/PASS markers and a
clean XAPI return value 0. No Mercenaries guest rendering is connected yet;
this proof remains the isolated native Xenos surface baseline.


### Phase 6B — first Mercenaries graphics touch

Phase 6B is prepared as the first combined title-runtime + native-Xenos build.

Files:
- `ports/mercenaries/xbox360/phase6_native_graphics/Prepare-Phase6B.ps1`
- `ports/mercenaries/xbox360/phase6_native_graphics/emit_phase6b_first_graphics_touch.py`

Build tag: `P6B-FIRST-GRAPHICS-TOUCH-20261021-A`.

The build regenerates the proven Phase-5BV pack, adds exact generated title
root `0x0014CD30` plus a bounded depth-12/cap-512 direct closure, initializes
the Phase-6A native Xenos surface, and resumes translated Mercenaries execution.

Unknown graphics/platform semantics remain hard stops. A rejected guest access
records exact address/width/read-vs-write; NV2A MMIO and VRAM aperture accesses
also trigger a purple diagnostic screen. Purple is only evidence that the title
reached the GPU boundary, not that Mercenaries rendered the frame.

Hardware target: reach the first actual graphics semantic touch with Xenos
already alive so the next patch can translate that specific operation into the
first genuine guest-driven pixels.
