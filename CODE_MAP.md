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

