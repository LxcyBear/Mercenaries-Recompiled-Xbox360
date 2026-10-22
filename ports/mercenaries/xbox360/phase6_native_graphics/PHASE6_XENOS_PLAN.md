# Phase 6 — Native Xbox 360 graphics (Xenos)

> **Status:** ACTIVE · Phase 6G hardware PASS; Phase 6H cached caller harvester ready
>
> **Immediate target:** render an independent native Xenos test surface, then
> connect the translated Mercenaries graphics path far enough to capture the
> first guest-rendered frame.

## Purpose

Replace the Windows-hosted NV2A/PGRAPH-to-D3D11 presentation path with a
correct Xbox 360-native graphics backend while preserving the translated
original-Xbox game semantics proven during Phase 5.

Phase 5 is frozen as the runtime/ABI/storage/kernel baseline. Phase 6 must not
regress that baseline or fake graphics success merely to advance execution.

## Checklist

- [x] **Inventory actual Mercenaries NV2A pushbuffers, texture formats, swizzle,
  render states, vertex programs, combiners and surface aliases.**
  Phase-5 exit reconnaissance plus the maintained NV2A/PGRAPH/D3D8 semantic
  implementation provide the initial evidence-backed inventory. New cases
  discovered during Phase 6 are appended rather than reopening Phase 5.

- [ ] **Introduce backend-neutral presentation/texture/draw interfaces.**
  **IN PROGRESS.** The existing D3D8/NV2A semantic layers and resource/state
  ownership are already separated enough to provide a starting seam, but
  D3D11/DXGI-specific backend assumptions still need to be isolated before a
  Xenos implementation can be considered cleanly swappable.

- [ ] **Initialize an Xbox 360 graphics device and render an independent test
  surface.** **VISUAL HARDWARE PASS; xbWatson/XAPI tail still pending for full
  checkbox closure.** Real hardware visibly presented the intended Phase-6A
  green -> blue -> red -> grey/white sequence.

- [ ] **Implement compatible 2D, textured draw and flip operations.**
  Establish a minimal native path for resource creation/upload, simple
  textured geometry and repeatable presentation before broad state coverage.

- [ ] **Translate needed shaders and vertex formats; validate depth/stencil,
  blending, alpha testing, render targets and synchronization.**
  Reuse the decoded NV2A/D3D8 semantics as the reference, but implement a real
  Xenos-facing backend rather than transplanting desktop D3D11 code.

- [ ] **Capture the first guest-rendered frame; then the main menu; then a
  reproducible 3D scene, comparing to the working PC reference.**
  Each milestone should retain hardware logs and screenshots/captures where
  possible so regressions are attributable.

- [ ] **Measure frame time, GPU memory and renderer errors on hardware.**
  Add instrumentation only after the native path renders repeatably; do not
  optimize before correctness is established.

## Gate 6

**Repeatable native Xenos rendering with a guest-controlled first frame,
functional title/menu graphics, and a reproducible 3D scene.**

The recommended implementation order from the Phase-5 handoff is:

1. first pixels / independent Xenos surface;
2. resource and backend abstraction cleanup;
3. guest render target / texture / draw / present path;
4. title and main-menu graphics;
5. XMV presentation integration;
6. reproducible 3D scene;
7. profiling, memory accounting and renderer-error hardening.

## Phase-5 inheritance

Phase 6 starts from these frozen proofs:

- Phase 5BV repeatability: **3/3 identical real-hardware boots**;
- stable endpoint: `DIRECT_FRONTIER 0x0023A3CE -> 0x0014CD30`;
- endpoint classification: exact generated title function in
  `recomp_0006.c`, original range `0x0014CD30-0x0014CD9C`;
- `fault=0`, guest arena release, proof end and XAPI return 0;
- exact runtime counters: icall=1262, direct=1002, `_msize`=395,
  realloc=4, final allocation size=2048, ticks=73417, trace=7322;
- Phase-5 exit reconnaissance: **READY / PASS**;
- graphics/display, audio, movies/video, input and cross-cutting surfaces
  inventoried;
- Phase-6 risk map and ordered handoff generated.

No Phase-6 graphics milestone may be claimed merely because the PC/D3D11
reference implementation exists. The checkbox advances only when the
Xbox 360-native path itself is demonstrated.


## Phase 6B — first Mercenaries graphics touch

Phase 6B merges the frozen, hardware-proven Phase-5 runtime with the visually
proven Phase-6A Xenos device.

The generated build:
- resumes from exact title function `0x0014CD30`;
- adds a depth-12 / cap-512 direct closure rooted there;
- keeps a real 640x480 Xenos D3D surface alive during translated execution;
- preserves the Phase-5 hard-stop policy for unknown semantics;
- logs exact rejected guest access address, width and read/write direction;
- classifies `0xFDxxxxxx` as NV2A MMIO and `0xF0xxxxxx-0xF7xxxxxx` as
  the NV2A VRAM aperture.

A purple screen is a **diagnostic-only** indication that Mercenaries reached a
GPU boundary. It does not count as a guest-rendered frame. The next patch must
implement the specific observed graphics operation before claiming the first
Mercenaries pixel.

Preparation:
`ports/mercenaries/xbox360/phase6_native_graphics/Prepare-Phase6B.ps1`.


## Hardware frontier chain

The live-Xenos translated continuation is advancing deterministically without
guest faults:

- **Phase 6B:** promoted `0x0014CD30`; hardware stopped at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x0014D820`, `fault=0`; dark-blue
  diagnostic path; harness PASS and XAPI return 0.
- **Phase 6C:** promoted `0x0014D820`; hardware stopped at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x0014E2D0`, `fault=0`,
  `ticks=74380`, `trace=7402`; harness PASS and XAPI return 0.
- **Phase 6D:** promoted `0x0014E2D0`; hardware stopped at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x0014E770`, `fault=0`, `ticks=74854`,
  `trace=7439`; harness PASS and XAPI return 0.
- **Phase 6E:** promoted `0x0014E770`; hardware stopped at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x00150E40`, `fault=0`, `ticks=75040`,
  `trace=7446`; harness PASS and XAPI return 0.
- **Phase 6F:** replaces the one-address cadence with a batched harvester:
  mandatory root `0x00150E40`, depth-12 direct closure, then a forward-biased
  support-clean fill from `0x0014C000..0x0017FFFF` under a 256-new-member cap.
  Exact packed DIRECT/ICALL_SAFE targets auto-continue; genuine NV2A/platform/
  ABI/guest-fault/missing-body boundaries remain hard stops.

Purple remains reserved for an actual rejected NV2A MMIO/VRAM access. No
purple GPU-boundary event has yet been confirmed by xbWatson.

- **Phase 6F hardware:** consumed packed root `0x00150E40` and one subsequent
  ICALL, then stopped fault-free at adjacent backward sibling `0x00150E20`;
  `ticks=75046`, `trace=7448`, direct dispatches 1012, ICALL dispatches 1272,
  harness PASS, XAPI return 0. This proved the harvester dispatcher and exposed
  the forward-biased candidate-selection blind spot.
- **Phase 6G:** mandatory root `0x00150E20`; reserve 128 nearest generated
  siblings symmetrically, then add depth-12 direct closure, then symmetric fill
  from `0x00120000..0x0018FFFF` under a 512-new-member cap. Unknown support is
  pruned; true NV2A/platform/ABI/guest-fault/missing-body boundaries remain fenced.

- **Phase 6G hardware:** consumed `0x00150E20`, continued through
  `0x00153080`, then stopped at `DIRECT_FRONTIER 0x0023A3CE -> 0x00015B30`;
  `fault=0`, `ticks=75063`, `trace=7455`; harness PASS and XAPI return 0.
  This is the first hardware proof that one harvester XEX can clear multiple
  previously unknown direct holes before reaching the next frontier.
- **Phase 6H:** switches to a frozen local Phase-6G baseline instead of replaying
  the full emitter ancestry, prioritizes exact generated direct-call targets encoded
  by caller `0x0023A3CE`, then adds caller/root closures and a local reserve under
  a 1024-new-member cap. Proven DIRECT/ICALL logging is throttled with a dense window
  around the old frontier plus a final dispatch summary.


- **Phase 6I hardware:** cached caller harvest consumed `0x00202680` and stopped
  cleanly at `DIRECT_FRONTIER 0x0023A3CE -> 0x00063F80`; `fault=0`,
  `ticks=93858`, `trace=8084`, direct dispatches 1152, ICALL dispatches 1556,
  harness PASS, XAPI return 0.
- **Phase 6J:** cached Phase-6I baseline, mandatory root `0x00063F80`, same
  caller/root harvest policy and 1024-new-member cap. Generated `main.cpp`
  suppresses only MSVC C4102 because translated basic-block labels can remain
  intentionally unreferenced after pruning/lowering; runtime semantics are unchanged.


- **Phase 6J hardware:** consumed `0x00063F80` and stopped cleanly at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x000D4A30`; `fault=0`, `ticks=93860`,
  `trace=8085`, direct dispatches 1153, ICALL dispatches 1556, harness PASS,
  XAPI return 0. No NV2A MMIO/VRAM touch was observed.
- **Phase 6K:** cached Phase-6J baseline, mandatory root `0x000D4A30`, caller/root
  closures plus a 768-entry stratified global generated-text reserve and 192-entry
  local reserve under a 1536-new-member cap. This targets the now non-local dynamic
  frontier pattern while keeping true NV2A/platform/ABI/guest-fault/missing-body
  boundaries fenced.


- **Phase 6K hardware:** the global-gap harvester consumed multiple additional
  dynamic targets before stopping cleanly at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x0016B7F0`; `fault=0`,
  `ticks=97909`, `trace=9423`, direct dispatches 1162, ICALL dispatches
  2156, harness PASS, XAPI return 0. No NV2A MMIO/VRAM touch was observed.
- **Phase 6L:** cached Phase-6K baseline, mandatory root `0x0016B7F0`, same
  caller/root + stratified-global harvest policy and 1536-new-member cap to
  confirm the multi-frontier acceleration remains repeatable.


- **Phase 6L hardware:** the sharded-source/global harvester preserved native Xenos
  device creation and exact-retail startup behavior, then advanced to
  `DIRECT_FRONTIER 0x0023A3CE -> 0x00179850`; `fault=0`,
  `ticks=129724`, `trace=19928`, direct dispatches 1196, ICALL dispatches
  6832, harness PASS, XAPI return 0. No NV2A MMIO/VRAM touch was observed.
- **Phase 6M:** cached Phase-6L `main_monolithic.cpp` baseline, mandatory root
  `0x00179850`, same caller/root + stratified-global 1536-member harvest policy.
  Build output remains editor-friendly via wrapper `main.cpp` + function-boundary
  translated shards, while the monolithic file is retained only as emitter cache.


- **Phase 6M hardware (first launch after retail-data copy):** persistent Partition0 backing
  was recreated, Mercenaries changed the cache config and intentionally requested
  kernel ordinal 49 / firmware return routine 2. The diagnostic harness trapped that
  non-returning action safely; this was a one-time storage initialization path, not a
  translated frontier regression.
- **Phase 6M hardware (second launch):** Partition0 backing loaded successfully and the
  normal translated harvest resumed. It stopped cleanly at
  `DIRECT_FRONTIER 0x0023A3CE -> 0x00222B20`, `fault=0`,
  `ticks=129800`, `trace=19957`, direct dispatches 1207, ICALL dispatches 6838,
  harness PASS, XAPI return 0. No NV2A MMIO/VRAM touch was observed.
- **Phase 6N:** cached Phase-6M monolithic baseline, mandatory root `0x00222B20`,
  same caller/root + stratified-global 1536-member harvest policy and sharded
  Visual Studio build layout.


- **Phase 6N hardware:** full retail game-data tree present in the development folder;
  no `DATAxbox`/asset file was requested yet. The translated harvester advanced to
  `ICALL_SAFE 0x0023A3CE -> 0x00251CD0`, `fault=0`, `ticks=147981`,
  `trace=22791`, direct dispatches 1305, ICALL dispatches 8132, harness PASS,
  XAPI return 0. The 6N preparation audit had already fenced `0x00251CD0`
  because its translated body depends on CRT `cos()`.
- **Phase 6O:** cached Phase-6N monolithic baseline, mandatory root `0x00251CD0`.
  Phase-owned support explicitly certifies only `cos()` (with `<math.h>`);
  all other unresolved helpers remain support-clean fenced. Existing 1536-member
  caller/root + stratified-global harvesting and VS-friendly sharding remain active.


- **Phase 6O hardware:** the explicit `cos()` support fence at `0x00251CD0`
  was crossed successfully. Native Xenos device creation remained healthy and the
  translated run advanced to direct=1354 / ICALL=8185 before stopping only on the
  finite 200000-block watchdog: `BUDGET 0x0023A3CE -> 0x002527B5`,
  `fault=0`, `ticks=200001`, `trace=43586`. Harness PASS; no new support
  exception or guest fault was observed.
- **Phase 6P:** exact cached Phase-6O translated pack, no new members and no new
  support exceptions. Increase only `PHASE4C_EXEC_BUDGET` from 200000 to 600000
  blocks, retain all NV2A/platform/ABI/guest-fault/missing-support hard stops, and
  keep the VS-friendly sharded build layout.


- **Phase 6P hardware:** raising the finite execution watchdog to 600000 proved
  Phase 6O had not entered an infinite loop. The run advanced to
  `DIRECT_FRONTIER 0x0023A3CE -> 0x001F9FD0`, `fault=0`,
  `ticks=415202`, `trace=129649`, direct dispatches 1357, ICALL dispatches
  8204, last packed ICALL `0x00252A20`, and harness PASS/XAPI 0. No budget
  boundary was reached.
- **Phase 6Q:** safe-text saturation. Start from the hardware-proven Phase-6P
  600k-budget monolithic cache, seed mandatory root `0x001F9FD0`, retain only
  the already-proven `cos()` CRT support plus the live-root x87 `sin()` dependency, and attempt every remaining
  generated `.text` function (4096 safety cap) under the existing support-clean
  pruning rules. This is intended to remove ordinary generated-body coverage as
  a recurring source of blue boundaries; unresolved support, NV2A, ABI/platform,
  and guest-memory faults remain hard stops.
