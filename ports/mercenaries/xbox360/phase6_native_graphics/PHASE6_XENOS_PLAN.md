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


- **Phase 6Q hardware:** safe-text saturation passed on hardware and eliminated the
  recurring ordinary generated-.text frontier class. Native Xenos creation remained
  healthy. The run advanced to direct=1765 / ICALL=9065 and stopped cleanly at
  `ICALL_SAFE 0x0023A3CE -> 0x002D66A2`, `fault=0`, `ticks=430987`,
  `trace=131961`. The target lies in the retail XBE `XPP` section
  (`0x002D4300-0x002DBCC8`), not Mercenaries `.text`. No NV2A MMIO/VRAM touch
  and no DATAxbox access were observed; harness PASS and XAPI return 0.
- **Phase 6R:** exact XPP frontier resolver. Reuse the hardware-proven Phase-6Q
  saturation cache, require `0x002D66A2` to be an exact generated XPP function,
  and pack only a bounded depth-2/cap-64 generated closure. Interior XPP entries,
  missing translated bodies, unresolved support, NV2A/platform/ABI boundaries, and
  guest-memory faults remain hard stops. Existing native `cos()`/`sin()` support
  is retained.


- **Phase 6R hardware:** exact XPP frontier root `0x002D66A2` executed successfully.
  Native Xenos creation remained healthy. The run stopped only five budget ticks later at
  `ICALL_SAFE 0x0023A3CE -> 0x002A0159`, `fault=0`, `ticks=430992`,
  `trace=131962`. Summary: direct=1765, ICALL=9066, last packed ICALL
  `0x002D66A2`. The new target lies in retail XBE `DSOUND`
  (`0x0029CB80-0x002BB274`), proving the XPP frontier is behind us.
- **Phase 6S:** batched DSOUND frontier resolver. Reuse the hardware-proven Phase-6R
  cache, require `0x002A0159` to be an exact generated DSOUND function start,
  then pack a depth-4/cap-256 support-clean closure to batch safe DSOUND dependencies.
  Existing native `cos()`/`sin()` support remains active. Interior DSOUND entries,
  missing bodies, unresolved support, NV2A/platform/ABI boundaries, and guest-memory
  faults remain hard stops.


- **Phase 6S hardware:** the exact DSOUND root `0x002A0159` executed successfully,
  but the same table-walk caller stopped five ticks later at
  `ICALL_SAFE 0x0023A3CE -> 0x002A0164`, `fault=0`, `ticks=430997`,
  `trace=131963`. Summary: direct=1765, ICALL=9067, last packed ICALL
  `0x002A0159`. The +0xB sibling step shows a call-graph closure is the wrong
  batching shape for this DSOUND registration/table walk.
- **Phase 6T:** broad DSOUND sibling sweep. Reuse the hardware-proven Phase-6S
  cache, require `0x002A0164` to be an exact generated DSOUND function start,
  enumerate remaining exact generated starts across DSOUND itself, prioritize
  the frontier and all later starts, then fill any remaining capacity from
  pre-frontier starts. Candidate cap is 1024 and existing support-clean pruning
  remains authoritative; unresolved helpers, interior entries, missing bodies,
  NV2A/platform/ABI boundaries, and guest faults remain hard stops.


- **Phase 6T hardware:** broad DSOUND sibling sweep successfully broke the +0xB
  sibling frontier pattern. The run advanced to direct=1769 / ICALL=9073 and
  stopped at `HEAP_EXHAUSTED`, `fault=0`, request/target `0x012999A0`
  (~18.6 MiB), ticks=431056, trace=131985. This is not a code frontier: the
  Phase-4C synthetic ordinary title heap is still only 1 MiB. Hardware showed
  the only VM reservation before the stop was 1 MiB at `0x03F00000`, with
  page_next remaining `0x03F00000`.
- **Phase 6U:** reuse the exact hardware-proven Phase-6T translated pack and
  shards unchanged, widen only the synthetic ordinary title heap window from
  1 MiB to 32 MiB (heap end `0x028C0000`), and retain all existing hard-stop
  behavior. This leaves the heap below the proven `0x03F00000` top-down VM
  frontier while allowing the observed 18.6 MiB allocation to fit.


- **Phase 6U hardware:** the 32 MiB title-heap expansion worked. The previously
  fatal `0x012999A0` / 19,503,520-byte `RtlAllocateHeap` request succeeded
  at guest VA `0x008C2980`. Execution then reached the harness budget at
  `ticks=600001`, `trace=165774`, target `0x001F6BF8`, `fault=0`.
  Summary advanced to direct=1779 / ICALL=9073 and the phase returned PASS/XAPI 0.
- **Phase 6V:** reuse the exact hardware-proven Phase-6U source, translated
  pack, shards, 32 MiB heap, and hard-stop policy unchanged; raise only
  `PHASE4C_EXEC_BUDGET` from 600,000 to 2,000,000 ticks. This is intended to
  let the long post-allocation translated initialization complete and expose
  the next genuine boundary without another small budget-only hardware cycle.


- **Phase 6V hardware:** the 2,000,000-tick deep-budget pass cleared the old
  600,001-tick harness stop and reached a genuine new translated-code frontier:
  `DIRECT_FRONTIER 0x0023A3CE -> 0x0017FE90`, ticks=670295,
  trace=179827, fault=0. Direct dispatches advanced to 1795 while ICALL stayed
  at 9073. The previously fatal 19,503,520-byte heap allocation still succeeds.
  No FIRST GRAPHICS TOUCH or DATAxbox event was observed before the frontier.
- **Phase 6W:** exact frontier resolver for `0x0017FE90`. Before packing, the
  emitter consults the inherited Phase-6Q support-clean prune table. If this
  target was previously pruned, prep hard-stops and prints the exact unresolved
  helper names; otherwise it validates an exact generated function start and
  packs a bounded depth-4/cap-256 generated closure. The 2M budget and 32 MiB
  title heap remain unchanged.


- **Phase 6W preflight finding:** live frontier `0x0017FE90` was confirmed to
  be one of Phase-6Q's previously support-pruned functions. The exact unresolved
  host-patch dependencies are `recomp_frame_ticks_with_remainder` and
  `recomp_freecam_game_ticks`.
- **Phase 6W support implementation:** reviewed against the canonical upstream
  Mercenaries-Recompiled host patch layer. The fractional frame-tick helper now
  carries sub-tick remainder across updates with invalid-input reset semantics.
  The freecam game-tick helper uses the canonical normal/off-mode identity
  behavior because the Xbox 360 port exposes no freecam enable/time-control
  path. These are support-owned compiled bodies, not names added to a whitelist.
  Any dependency drift beyond these exact two helpers remains a hard stop before
  packing `0x0017FE90`.


- **Phase 6W hardware:** crossed the previously support-pruned `0x0017FE90`
  root successfully. The reviewed frame-tick/freecam-tick support stayed stable,
  the 19,503,520-byte title-heap allocation still succeeded at `0x008C2980`,
  and execution reached a new `DIRECT_FRONTIER 0x0023A3CE -> 0x0020F9C0`
  at ticks=670776, trace=179920, fault=0. Summary advanced to direct=1812 /
  ICALL=9075; the phase returned PASS/XAPI 0. No FIRST GRAPHICS TOUCH or
  DATAxbox event occurred before the frontier.
- **Phase 6X:** `0x0020F9C0` is materially interesting: upstream
  Mercenaries-Recompiled's native graphics-memory tests call
  `sub_0020F9C0` as the retail graphics-pool initializer, and its optional
  extended-graphics-memory transformations target `0x0020F9C0` and
  `0x0020F9D3` with no host helper at those patch sites. 6X therefore packs
  the exact generated `0x0020F9C0` root plus a support-clean depth-4/cap-256
  closure while inheriting the proven Phase-6W timing support, 2M execution
  budget, 32 MiB title heap, native Xenos surface, and all NV2A/platform/ABI/
  guest-fault hard stops unchanged.


- **Phase 6X preflight finding:** the live graphics-pool root `0x0020F9C0`
  was previously support-pruned only because its generated body calls
  `xbox_GetExtendedGraphicsPool`.
- **Phase 6X graphics-memory support:** upstream defines
  `xbox_GetExtendedGraphicsPool()` as `0x04000000` only when the optional
  PC extended graphics bank is enabled and mapped; otherwise it returns zero.
  The Xbox 360 port intentionally keeps the original retail 64 MiB guest layout,
  so 6X installs the canonical disabled-state result (`0`). This selects the
  retail graphics-pool path (`0x02980000` start / `0x01680000` size in the
  upstream native graphics-memory test) rather than inventing a second guest
  graphics bank. The helper is a compiled support-owned body, not a whitelist
  entry, and any dependency drift still hard-stops before packing.


- **Phase 6X local build automation:** `Prepare-Phase6X.ps1` now invokes the
  reusable `Invoke-VS2017Xbox360Build.ps1` helper by default. The helper targets
  the local `Mercenaries-PPC-Port` solution, discovers the project compiling
  `main.cpp`, replaces that source plus the compiled env CPP and entire
  `translated_shards` directory with the freshly generated Phase-6X output,
  verifies hashes/build-tag/env-cookie identity, refuses to compile
  `main_monolithic.cpp`, then runs VS2017 `devenv.com` command-line
  `/Clean` and `/Build` for `Release|Xbox 360`. This removes the manual
  Visual Studio copy/clean/build step while retaining stale-build guards.


- **Phase 6 parallel acceleration track (active):** startup/frontier work and
  renderer work are no longer serialized. The project now maintains three
  complementary tracks alongside the live hardware frontier:
  1. **PC semantic oracle:** normalize guest-visible dispatch/kernel/storage/
     NV2A/PFIFO/PGRAPH events from the working PC runtime and diff the Xbox 360
     trace at the first semantic divergence rather than discovering every next
     boundary blind.
  2. **Local GPU capture/replay:** capture a content-addressed local pushbuffer
     plus only the guest memory/state it depends on, validate every blob by
     SHA-256, and replay it in a narrow standalone XEX. Captures may contain
     retail-derived bytes and are developer-local only; they are never a repo
     or release artifact.
  3. **Typed hash-keyed Xenos shader table:** reuse upstream NV2A combiner/
     vertex semantic identities, compile Xenos bytecode offline, and look it up
     by shader kind + semantic key with source-hash provenance. Missing entries
     remain visible diagnostics/hard stops during development.
  Initial tooling lives under `tools/phase6/` and the complete contract is in
  `PHASE6_ORACLE_REPLAY_SHADER_PLAN.md`.


- **PC oracle implementation milestone:** the fork now contains an opt-in
  `phase6_oracle` JSONL writer compiled with the kernel runtime. Setting
  `MERCENARIES_PHASE6_ORACLE_PATH` enables it; normal runs remain unchanged
  when the variable is absent. The first live producer hooks are at
  `pfifo_process_pushbuffer()` and `pgraph_method()`, recording PFIFO
  submission geometry plus decoded/resolved PGRAPH method events. The
  `tools/phase6/phase6_oracle.py` normalizer/differ can consume this stream.
  Direct/ICALL/kernel/storage event producers are the next oracle expansion.


- **Phase 6X hardware:** PASS/XAPI 0 with the intended
  `P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A` image. The exact translated
  `0x0020F9C0` graphics-pool root executed successfully; summary advanced to
  direct=1813 with last_direct=`0x0020F9C0`, ICALL=9075, and the next
  boundary is `KERNEL_FRAME target=0x800000A6` (ordinal 166,
  `MmAllocateContiguousMemoryEx`) at ticks=670780 / trace=179922 / fault=0.
  The live frame is esp=`0x008BF9E0`, saved_esp=`0x008BF9FC` (28 bytes),
  while the canonical five-argument kernel frame is 24 bytes. ECX was
  `0x01680000`, exactly the retail graphics-pool size validated by upstream.
  No FIRST GRAPHICS TOUCH or DATAxbox event occurred before this boundary.
- **Phase 6Y:** resolve that ABI shape without globally weakening ordinal 166.
  Emission first inspects the local generated `sub_0022AEE9` physical
  allocation wrapper and structurally proves its exact call setup:
  `_icall_esp` is snapshotted, then saved `ESI`, the five ordinal-166
  arguments, and the dummy return are pushed. Therefore the hardware-observed
  +28 delta is **24 bytes owned by `MmAllocateContiguousMemoryEx` plus a
  4-byte wrapper-owned saved-ESI spill**. Runtime accepts that +28 shape only
  for the retail `0x01680000` graphics-pool request and only when the spill
  still equals live `ESI`; it resumes at `c+24 == savedEsp-4` so the
  wrapper can perform its later `POP32(esp, esi)`. Canonical +24 calls remain
  unchanged; every other shape still hard-stops.


- **Phase 6Y-B hardware:** the saved-ESI / ordinal-166 ABI repair is proven on
  real hardware. `MmAllocateContiguousMemoryEx` received exactly the retail
  graphics request `size=0x01680000` (22.5 MiB), `low=0`,
  `high=0xFFFFFFFF`, `align=0`, `protect=0x404`, with the expected
  +28 wrapper frame. The continuation preserved the wrapper spill and resumed
  at `savedEsp-4`; execution continued with `fault=0`. The allocation
  itself returned NULL (`base=0`, rounded=0) and the title immediately set
  last-error 8 before reaching `DIRECT_FRONTIER 0x0020FAE0` at ticks=670789
  / trace=179925. Therefore `0x0020FAE0` is treated as allocation-failure
  path evidence, not as the next safe frontier to pack.
- **Phase 6Z hardware — PASS:** the bounded dual-frontier repair worked on
  real Xbox 360 hardware. The retail graphics-pool claim succeeded at
  `0x02880000` for the full `0x01680000` bytes (22.5 MiB), moving
  `page_next` from `0x03F00000` to `0x02880000`. The live title-heap
  high-water was only `0x01B5C320`; exactly `0x00040000` (256 KiB) of the
  prior synthetic free tail was trimmed, with two VM reservations active.
  Ordinal 166 returned `base=0x02880000`, `graphics_claim=1`, and preserved
  the proven wrapper stack repair. No genuine NV2A/MMIO/VRAM first touch was
  observed before the next boundary.
- **Corrected 6Z inference:** `0x0020FAE0` is **not** OOM-only. Hardware
  reached `DIRECT_FRONTIER 0x0023A3CE -> 0x0020FAE0` after the successful
  graphics-pool allocation, at ticks=670788 / trace=179924 / fault=0 with
  EAX=1. The earlier failure-path assumption is retired.
- **Phase 6AA active — post-graphics-pool frontier:** require
  `0x0020FAE0` to be an exact locally generated function start/body, then
  pack only a depth-4/cap-256 support-clean closure rooted there. Preserve the
  hardware-proven Phase 6Z graphics pool and Mm166 repair unchanged. Genuine
  NV2A/MMIO/VRAM, platform, ABI, guest-fault, or unresolved-support boundaries
  remain hard stops.


- **Phase 6AA reviewed renderer recovery support:** local preflight proved the
  exact `0x0020FAE0` root depends on upstream helper
  `recomp_renderer_recovery_report(result, stage)`. Upstream defines stages
  1/2 as diagnostic-only with no guest-register/resource-ownership mutation;
  terminal/unknown stages must not return into null-device rendering. The Xbox
  360 harness maps that terminal case to explicit `RENDERER_FATAL` boundary
  evidence with the HRESULT preserved. The companion
  `recomp_renderer_test_oom(multisample)` is an opt-in PC regression
  injection upstream; Xbox 360 production/default semantics are the canonical
  disabled-state return 0. Phase 6AA-B installs both before support-clean audit.


- **Phase 6AA-B hardware — PASS:** exact generated renderer root
  `sub_0020FAE0` executed on Xbox 360 while the Phase 6Z retail graphics pool
  remained valid at `0x02880000` / `0x01680000`. The run advanced to
  direct=1814 with last_direct=`0x0020FAE0` and ended with the Phase 6AA
  post-graphics-pool result PASS. The next boundary is a 32-bit guest read from
  `0x80000164` at caller `0x0023A3CE`, ticks=670797, trace=179929,
  fault=1. This value is kernel ordinal 356, `HalBootSMCVideoMode`, a DATA
  export rather than a function.
- **Phase 6AB active — HalBootSMCVideoMode DATA relocation:** upstream uses the
  same kernel-data base `0x0087E000`, places `HalBootSMCVideoMode` at
  offset `0x98`, and initializes the 32-bit value to zero. 6AB therefore
  relocates the exact retail ordinal-356 thunk to `0x0087E098`, initializes
  and readbacks zero, requires exactly one ordinal-356 import, and otherwise
  preserves the hardware-proven 6AA renderer closure, recovery helpers,
  graphics pool, timing semantics, and all hard stops unchanged.


- **Phase 6AB hardware — PASS:** the HalBootSMCVideoMode DATA relocation at
  `0x0087E098` worked on real Xbox 360 hardware. Native Xenos device creation,
  the proven `0x02880000` / `0x01680000` graphics pool, storage setup, and
  the translated renderer path all remained healthy. The run advanced to
  direct=1816 / ICALL=9075 and stopped at
  `KERNEL_FRAME 0x0023A3CE -> 0x800000A6`, ticks=670830,
  trace=179938, fault=0. The live frame is esp=`0x008BF7C0`,
  saved_esp=`0x008BF7DC` (28 bytes). Boundary registers were
  EAX=`0xFFFFFFFF`, ECX=`0x00000060`, EDX=`0x00000000`,
  ESI=`0x00299380`. The last translated DIRECT target before the boundary was
  `0x0022AEE9`, the same physical-allocation wrapper structurally proven in
  Phase 6Y.
- **Phase 6AC active — Mm166 wrapper reuse:** retire the temporary 6Y
  one-size-only +28 gate. Emission re-proves the generated `sub_0022AEE9`
  shape (saved ESI + five MmAllocateContiguousMemoryEx arguments + dummy
  return), instruments only its single `RECOMP_ICALL_SAFE` with a transient
  wrapper-active marker, and permits the +28 ordinal-166 frame only while that
  exact wrapper call is active and the c+24 spill still equals live ESI.
  Canonical +24 Mm166 calls remain unchanged, and the existing 22.5 MiB retail
  graphics-pool special allocation path remains restricted to its exact
  size/range/protection signature. Using the proven push mapping, the 6AB
  boundary registers decode the new request as size=`0x60`, low=0,
  high=`0xFFFFFFFF`; 6AC deliberately fixes the wrapper class rather than
  special-casing that single size.


- **Phase 6AC hardware - PASS:** the generalized sub_0022AEE9 ordinal-166
  wrapper repair is now proven for both the 22.5 MiB retail graphics-pool
  request and the later 96-byte aligned request. The latter reached the
  intended audio-allocation fallback with fault=0. Execution advanced to
  ICALL_SAFE target \`0x80000001\` at ticks=670846 / trace=179942 with
  esp=\`0x008BF958\`, saved_esp=\`0x008BF95C\` (4 bytes), and the run ended
  PASS/XAPI 0. Summary advanced to direct=1817 with
  last_direct=\`0x00290450\`, inside the retail D3D section.
- **Phase 6AD active - AV saved-data + safe cleanup pass #1:** ordinal 1 is
  \`AvGetSavedDataAddress(void)\`; implement only its exact observed +4 frame
  and maintained saved-address return, initially NULL. Pre-arm its natural
  ordinal-4 partner \`AvSetSavedDataAddress(PVOID)\` with a strict +8 frame so
  get/set semantics remain coherent if the title reaches it. Hardware-facing
  AV ordinals 2/3 remain hard stops. In the same build, throttle repetitive
  maintained \`_msize\` PASS logging without changing any helper result,
  allocation lookup, register, stack or counter semantics, and rename emitted
  translated shards to a phase-correct \`phase6ad_*\` prefix with byte-identical
  reconstruction required.
- **Cleanup policy from 6AD onward:** avoid serial cleanup phases. Safe cleanup
  may ride along with frontier builds only when it is semantics-free
  (diagnostic throttling, source/shard naming, deterministic preflight,
  comments/docs, or build-artifact hygiene). Do not refactor proven allocator,
  stack, VM, storage, timing, Xenos, graphics-pool or renderer semantics merely
  for neatness while the frontier is moving. Plan at most two dedicated cleanup
  passes: (1) structural consolidation after first real Mercenaries pixels are
  reached, and (2) release/hardening cleanup after stable rendering.


- **Phase 6AD hardware - PASS:** the combined AV saved-data + safe cleanup
  stage worked as intended. Ordinal 1 \`AvGetSavedDataAddress\` crossed with
  address NULL and exact +4 ABI. The next hard stop is ordinal 2
  \`AvSendTVEncoderOption@16\` with esp=\`0x008BF948\`,
  saved_esp=\`0x008BF95C\` (exact +20 frame), ticks=670848,
  trace=179942, fault=0. The inherited graphics-pool and 96-byte Mm166 paths
  both still pass. Safe cleanup was semantics-neutral: maintained CRT
  \`_msize\` executed 601 calls while 590 repetitive trace lines were
  suppressed. Phase result PASS, XAPI return 0.
- **Phase 6AE active - compact AV-family display handoff:** handle ordinals
  1-4 as one bounded compatibility unit. Ordinal 2 uses its hardware-proven
  +20 frame and models TV-encoder controls as logical port state; bounded
  query options receive stable compatibility values. Ordinal 3
  \`AvSetDisplayMode@24\` is pre-armed with a strict +28 frame and records
  register-base, step, mode, format, pitch and framebuffer while returning
  success without writing original-Xbox NV2A/encoder registers. The native
  Xbox 360 Xenos device remains the physical display owner. Ordinal 4 keeps
  the maintained saved-data setter. Genuine NV2A MMIO/VRAM and unrelated
  platform/ABI/guest-fault boundaries remain hard stops.
