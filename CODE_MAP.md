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
`0x0023BE3C` mandatory, scans the inherited generated `main.cpp` for every
currently fenced `phase4c_direct_frontier(0x...)` target, filters those to
exact generated/unpacked function starts, adds bounded translated closures for
them, and packs the largest support-clean subset under a 256-new-function cap.
The mandatory hardware-observed root is never pruned or guessed. Unsupported
side branches, guest faults, ABI/frame anomalies, kernel/device unknowns, heap
exhaustion and the execution-budget watchdog remain hard stops.
