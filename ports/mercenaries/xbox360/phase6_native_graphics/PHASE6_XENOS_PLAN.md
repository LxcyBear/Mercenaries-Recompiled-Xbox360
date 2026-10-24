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


- **Phase 6AE-A hardware - INVALID / host logging overflow:** hardware never
  reached the AV bridge. The run began with the 6AE-A build tag, then faulted
  while emitting the startup Policy trace with repeated 0xC0000005 reads at
  0x910D0A00. No Xenos startup, ordinal-2 PASS, translated boundary or phase
  result was reached. Root cause: the 6AE-A Policy literal was 518 characters,
  crossing the logging helper's practical 512-byte boundary once prefix/NUL
  overhead is included. Treat this as a host-side observability regression,
  not evidence against the combined AV-family strategy.
- **Phase 6AE-B active:** shorten the startup Policy trace to a bounded string,
  add emitter/prep guards rejecting an oversized policy trace, retain the same
  AV-family runtime semantics, and publish a distinctly named P6AE-B XEX.


- **Phase 6AE-B hardware - PASS:** the bounded AV-family retry crossed the
  hardware-observed ordinal 2 \`AvSendTVEncoderOption@16\` frontier with the
  exact +20 frame. The observed call was registerBase=0, option=9, param=1,
  Result=NULL; it was treated as a non-query logical encoder write/no-op and
  returned success. Ordinal 3 \`AvSetDisplayMode@24\` was not reached.
  Native Xenos device creation remained PASS. Immediately afterward the retail
  renderer recovery hook reported terminal stage 3 with HRESULT \`0x8007000E\`
  (E_OUTOFMEMORY) at esp \`0x008BF99C\`, producing a clean
  \`RENDERER_FATAL\` boundary with fault=0. Phase harness result PASS, XAPI
  return 0. The next frontier is therefore the retail CreateDevice/recovery
  path rather than the AV bridge.


- **Phase 6AF active - native D3D CreateDevice handoff:** use the 6AE-B
  hardware proof plus upstream Mercenaries-Recompiled's own renderer recovery
  regression contract to replace only retail \`sub_0028CAA0\` with a bounded
  native-Xenos handoff. The bridge validates the exact six-argument / 28-byte
  retail frame and 640x480 presentation contract, allows the retail AA/non-AA
  multisample field to vary, writes the upstream-proven successful guest device
  identity \`0x00299380\` through the title's device-out pointer, returns S_OK,
  and resumes the already-packed translated D3D path. The real physical device
  remains the live Xbox 360 Xenos \`D3DDevice\`; no original-Xbox NV2A register
  writes are fabricated. Genuine NV2A MMIO/VRAM, platform, ABI and guest faults
  remain hard stops. This stage is intended to cross the terminal
  \`0x8007000E\` renderer-creation frontier and expose multiple subsequent D3D
  boundaries in one hardware run when safely possible.


- **Phase 6AF-A build - INVALID / not hardware-tested:** emission and source
  sync passed, but VS2017 rejected the translated CreateDevice shard because it
  directly referenced \`s_phase6bXenosReady\` and \`s_phase6bXenosDevice\`
  before those native-Xenos statics were declared later in the monolithic
  translation unit. No XEX was produced and this is not runtime evidence.
- **Phase 6AF-B active:** the translated shard now calls a forward-declared
  \`phase6af_native_xenos_ready()\` helper. Its implementation is emitted beside
  the actual Xenos statics, removing the source-order dependency while
  preserving the exact same native CreateDevice handoff semantics. Prep also
  verifies exactly one helper definition before invoking VS2017.


- **Phase 6AF-B hardware - PASS / major renderer milestone:** native Xenos
  CreateDevice remained healthy, the retail CreateDevice bridge received the
  exact live Mercenaries contract (adapter 0, type 1, behavior 0x40, 640x480,
  format 6, one backbuffer, multisample 0x11, swap 1, auto-depth 1,
  depth-format 0x2A), published guest device 0x00299380 through 0x007AD604,
  returned S_OK, and eliminated the prior terminal 0x8007000E recovery failure.
  Execution immediately advanced into retail D3D and stopped cleanly at
  DIRECT_FRONTIER 0x0023A3CE -> 0x00290895 with
  esp=saved_esp=0x008BF92C and fault=0. The old final harness printed FAIL only
  because it still required optional AV ordinal-1/2 calls that this successful
  path no longer executes; that gate is stale, not a runtime failure.
- **Phase 6AG active - D3D neighborhood expansion:** promote hardware-proven
  retail D3D target 0x00290895 as a reviewed manual seed and pack a
  depth-6/cap-384 support-clean closure around it. Opportunistically include
  the existing reviewed local D3D format-dispatch entries 0x00290881,
  0x00290884 and 0x00290887 with small bounded closures when generated. Remove
  the stale optional AV-call PASS requirements, preserve the 6AF native
  CreateDevice handoff unchanged, and continue until the next genuine
  D3D/NV2A/platform boundary. Purple remains reserved for the first actual
  NV2A MMIO/VRAM touch.


- **Phase 6AG-A prep - INVALID / no build:** preflight correctly refused
  hardware target 0x00290895 because the cached Phase-3 inventory still owned
  it as an interior entry of sub_00290887 (0x00290887-0x0029089B). No VS build
  or XEX was produced.
- **Phase 6AG-B active:** 0x00290895 is now a protected reviewed manual seed.
  Prep detects a stale Phase-3 inventory and automatically reruns the isolated
  Phase-3 analysis/generated-tree gate before 6AG emission. It then requires
  0x00290895 to exist as an exact generated sub_00290895 body before the D3D
  neighborhood closure or VS2017 build can proceed.


- **Phase 6AG-B prep - PARTIAL PASS / no build:** the protected hardware seed
  successfully regenerated Phase-3 so 0x00290895 is now an exact generated
  sub_00290895 (range 0x00290895-0x0029089B). The D3D neighborhood resolved to
  one new root member plus three already-inherited local seeds. Emission then
  stopped because the 6AG result-gate patch matched the 6AF CreateDevice
  condition with fixed whitespace even though the generated multiline gate had
  different indentation. No VS build or XEX was produced.
- **Phase 6AG-C active:** result-gate edits are now token/regex based and
  indentation-tolerant. Optional AV gates may already be absent; the mandatory
  6AF CreateDevice token is located regardless of leading whitespace, and the
  6AG root requirement is inserted with the same indentation. The successful
  0x00290895 Phase-3 split is retained, so regeneration should be skipped on
  the next prep run.


- **Phase 6AG-C prep - PARTIAL PASS / no build:** exact-root and D3D-neighborhood
  analysis remained healthy, but emission still stopped because the inherited
  6AF CreateDevice PASS condition was not present in the cached source under
  the exact text expected by the gate editor. No VS build or XEX was produced.
- **Phase 6AG-D active:** stop mutating the inherited AV-era/6AF boolean result
  expression entirely. Emit a separate authoritative
  \`PHASE 6AG D3D NEIGHBORHOOD RESULT: PASS/FAIL\` beside the durable D3D-device
  summary. It depends only on \`s_phase6agRootEntered\` and
  \`s_phase6afCreateDeviceBridgeCount != 0\`, leaving all inherited legacy result
  gates untouched. The successful exact \`sub_00290895\` split is retained.


- **Phase 6AG-D hardware - PASS / best Phase-6 renderer run yet:** native Xenos
  CreateDevice remained PASS. The exact live retail CreateDevice contract again
  matched and published guest device 0x00299380 through 0x007AD604. The newly
  regenerated exact retail D3D entry sub_00290895 executed successfully, proving
  the hidden interior-entry split on hardware. Execution then continued farther
  through retail D3D and stopped cleanly at DIRECT_FRONTIER
  0x0023A3CE -> 0x0028E700 with esp=saved_esp=0x008BF918 and fault=0.
  Last direct progress reached 0x0028EB90 inside the retail D3D section.
  The independent \`PHASE 6AG D3D NEIGHBORHOOD RESULT\` reported PASS.
  The inherited old cosine-harvest line still prints FAIL and is now explicitly
  non-authoritative for Phase 6AG. No NV2A MMIO/VRAM touch has occurred yet.


- **Phase 6AH active - D3D saturation from 0x0028E700:** consume the
  Phase 6AG-D hardware PASS and promote fault-free retail D3D frontier
  0x0028E700 as a protected manual seed. Prep auto-regenerates the isolated
  Phase-3 function inventory/generated tree if that target is not yet an exact
  generated entry. The emitter packs a depth-8/cap-512 support-clean closure
  rooted at 0x0028E700, then performs one additional D3D-only saturation round:
  up to six newly exposed direct frontiers may be pre-armed in the same build
  only when they are exact generated entries inside the retail D3D section
  (0x00288640-0x0029B874). Each gets a shallow depth-2/cap-64 closure with a
  total second-round cap of 192 new members. Ambiguous/interior entries,
  non-D3D targets, unresolved-support members, NV2A MMIO/VRAM, platform, ABI
  and guest faults remain fenced. 6AH emits its own authoritative result
  requiring the 0x0028E700 root, prior 0x00290895 root, and native CreateDevice
  handoff; the inherited cosine-harvest result is relabeled non-authoritative.


- **Phase 6AH-A prep - INVALID / no build:** emission stopped before VS2017.
  The final PowerShell wrapper line alone did not preserve the underlying emitter
  reason in the user's pasted excerpt, so no runtime conclusion is attached.
- **Phase 6AH-B active:** the mandatory 0x0028E700 support-clean root remains
  authoritative. The extra D3D saturation round is now explicitly
  opportunistic: if every optional saturation candidate is support-unsafe,
  6AH falls back to the already-clean root-only pack rather than aborting the
  stage. Prep also embeds the best available emitter failure text directly in
  the final thrown error so any remaining mandatory-root failure is visible
  even from a short console excerpt.


- **Phase 6AH-B prep - SUPPORT BLOCKER IDENTIFIED / no build:** exact root
  0x0028E700 is valid, but support-clean emission correctly rejected it because
  the generated root calls \`recomp_d3d_sync_checkpoint\`. Upstream inspection
  proved that helper is diagnostic-only: when
  \`MERCENARIES_TRACE_D3D_SYNC\` is unset it returns immediately and does not
  mutate guest registers, guest memory, D3D device state, or control flow.
  Patch inventory entry 271 injects this diagnostic checkpoint at
  0x0028A060, 0x0028E740, 0x0028E74C, 0x0028E764, 0x0028E769 and 0x0028E7AE.
- **Phase 6AH-C active - maintained D3D sync diagnostic:** provide an exact
  support-owned \`recomp_d3d_sync_checkpoint(uint32_t)\` implementation before
  support-clean analysis. Xbox 360 preserves the upstream default semantics as
  a guest/device no-op and records only host-side call count/last phase for
  proof. 6AH's authoritative PASS now additionally requires that checkpoint
  to execute at least once. Unknown helpers remain fenced; no global support
  whitelist was added.


- **Phase 6AH-C prep - PARSER INVALID / no build:** the PowerShell prep file
  was corrupted by a truncated failure-reporting filter plus a duplicated tail.
  The parser failed before Phase-6AH emission/build; no XEX or hardware evidence
  exists for 6AH-C.
- **Phase 6AH-D active:** rebuild the prep script from the intact prefix, one
  clean failure-reporting block, and one clean post-emission/build tail. The
  repaired script has one build tail, balanced structural delimiters/quotes,
  retains the maintained diagnostic-only \`recomp_d3d_sync_checkpoint\` support,
  requires its hardware call counter in the authoritative 6AH result, and
  publishes \`Mercenaries-PPC-Port-P6AH-D.xex\`.


- **Phase 6AH-D hardware - PASS / orange next boundary:** native Xenos
  CreateDevice PASSed again; exact prior root 0x00290895 entered; new retail
  D3D root 0x0028E700 entered twice; maintained D3D-sync checkpoint executed
  six times with last phase=3; authoritative \`PHASE 6AH D3D SATURATION RESULT\`
  reported PASS. Execution then stopped at a new guest-memory boundary:
  READ32 0x80000004 with EAX=0x80000000, ESP=saved_ESP=0x008BF974,
  caller=0x0023A3CE. This is an orange guest fault, not an NV2A purple hit.
  The first KSEG page 0x80000000-0x80000FFF is deliberately fenced, so do not
  globally map 0x80000004 to physical RAM.
- **Phase 6AI-A active - E7AE forensic preflight:** inspect the exact cached
  6AH-D translated \`sub_0028E700\` body on the user's machine and extract the
  \`loc_0028E7AE\` block plus memory expressions. Hardware checkpoint evidence
  places the fault after sync phase 3 and before phase 4, so this local source
  block is the narrow target. 6AI-A intentionally does not invoke VS2017 or
  build an XEX; it refuses to change KSEG/memory semantics until the exact
  faulting expression and register provenance are visible.


- **Phase 6AI-B prep - REGEX INVALID / no build:** the predecessor-window
  forensic script reached the correct local source inspection path but used
  over-escaped Python raw regexes. The generic +4 matcher raised
  \`re.error: unbalanced parenthesis\` before report generation. No XEX or
  hardware run occurred.
- **Phase 6AI-C active:** fix both the exact EAX+4 and generic +4 source
  matchers, compile them explicitly before scanning, and retain the pre-E7AE
  predecessor-window inspection. This remains a source-only forensic pass.


- **Phase 6AI-C forensic - PASS:** the exact cached \`sub_0028E700\`
  predecessor window contains no literal EAX+4 access. The first relevant
  internal-device read is \`GUEST_READ32(esi + 0x1C20)\`; fixed
  \`GUEST_READ32(0x00298ED0)\` is the only other read before the phase-3
  checkpoint/branch. The E7AE target itself is only the POP/RET path.
- **Phase 6AI-D active - restore internal D3D device global:** upstream
  Mercenaries host code treats \`0x00299378\` as the current guest D3D device
  pointer and dereferences fields from it. Phase 6AF published successful guest
  identity \`0x00299380\` only through the game-facing CreateDevice output
  \`0x007AD604\`. 6AI-D restores the missing internal-XDK side effect by
  publishing and immediately reading back \`0x00299378 = 0x00299380\` during
  the proven CreateDevice bridge. The root is instrumented to report its local
  \`this\`, internal-global value, and \`this + 0x1C20\`; for the intended
  device identity that field address is \`0x0029AFA0\`. The KSEG first-page
  fence remains unchanged and no D3D object fields, NV2A MMIO or VRAM state are
  fabricated.


- **Phase 6AI-D hardware - PASS / orange persists:** native CreateDevice still
  PASSes; the internal current-device publication is now proven correct on
  hardware. \`sub_0028E700\` sees \`this=0x00299380\`,
  \`0x00299378=0x00299380\`, and \`this+0x1C20=0x0029AFA0\` on both root
  entries. The authoritative 6AI internal-device result is PASS. The next
  boundary nevertheless remains READ32 \`0x80000004\`, proving that the missing
  internal-device global was real but not the source of the orange fault.
- **Phase 6AJ-A active - source-step probe:** preserve every 6AI-D semantic
  unchanged and latch the exact source step immediately before each memory
  access/branch/call in \`sub_0028E700\`. The existing guest-fault handler
  reports the active step and three probe values. This is diagnostic-only and
  leaves guest memory, KSEG, D3D, NV2A/MMIO/VRAM, ABI, and sync semantics
  unchanged.


- **Phase 6AJ-A hardware - diagnostic PASS / orange persists:** the source-step
  probe ran on hardware without changing guest semantics. Both 0x0028E700
  entries still saw this=0x00299380, internal global 0x00299380, and
  this+0x1C20=0x0029AFA0. The orange boundary remains READ32
  0x80000004, but the active source latch was step 10, the
  loc_0028E7AE return path. The boundary still reports caller
  0x0023A3CE with the caller ESP restored. Because the probe latch persists
  after the callee returns, step 10 is evidence that the D3D root reached its
  return path before the later boundary, not proof that the POP/RET itself
  generated the fault.
- **Phase 6AK-A active - caller 0x0023A3CE forensic:** inspect the exact cached
  6AJ-A translated sub_0023A3CE body and print the neighborhood around every
  sub_0028E700 mention/direct call. Flag all guest-memory operations plus
  explicit EAX+4 reads or EAX=0x80000000 assignments. This is PC-only and
  intentionally builds no XEX until the post-D3D caller instruction producing
  the orange read is identified.

- **Phase 6AK-A forensic - PASS / deferred caller disproven:** exact cached
  `sub_0023A3CE` contains zero mentions/direct calls to `sub_0028E700`,
  zero explicit EAX+4 reads, and zero EAX=`0x80000000` assignments. Its body
  does contain ECX-relative accesses including `GUEST_READ32(ecx + 4)`, proving
  the old deferred boundary caller is only the last traced function and is not
  precise enough to identify the orange faulting instruction.
- **Phase 6AL-A active - exact READ32 site probe:** wrap every translated
  `GUEST_READ32` call site with a diagnostic shim that records translated
  function VA, generated site id, address, and live registers. If the checked
  guest-memory helper latches a fault, escape immediately from that exact site
  instead of waiting for a later Phase4C budget tick. Guest memory routing,
  KSEG fencing, D3D state, NV2A/MMIO/VRAM behavior, and read semantics remain
  unchanged.

- **Phase 6AL-A hardware - diagnostic PASS / exact faulting function captured:** native
  CreateDevice and both `0x0028E700` entries still PASS with the repaired internal
  device state. The orange boundary remains READ32 `0x80000004`. The READ32
  instrumentation summary latched `last_func=0x0028BC60`,
  `last_line=1957`, and `last_address=0x80000004` after 442,625 wrapped
  reads, disproving the stale deferred `0x0023A3CE` caller as the precise
  fault source.
- **Phase 6AM-A active - exact 0x0028BC60 source forensic:** inspect the cached
  6AL translated shard containing `sub_0028BC60`, verify hardware line 1957
  lies inside that function, and print the exact source neighborhood plus the
  full function. This is PC-only and intentionally builds no XEX; the next
  semantic repair must be based on that exact expression.

- **Phase 6AM-A forensic - PASS / exact instruction identified:** cached 6AL
  source proves hardware line 1957 is inside `sub_0028BC60` and is exactly
  `ebp = GUEST_READ32(eax + 4);`. The immediately preceding instruction is
  `eax = GUEST_READ32(edi);`, so the orange READ32 `0x80000004` occurs
  because a device-context state-stack entry itself contains
  `0x80000000`. This retires generic KSEG/arithmetic hypotheses.
- **Phase 6AN-A active - D3D +0x1A10 state-stack probe:** inherit the proven
  6AJ semantics and instrument only `sub_0028BC60`. Capture device fields
  +0x1A04/+0x1A08/+0x1A0C, count +0x1A10, stack entries
  +0x1A14/+0x1A18/+0x1A1C, selected top-object +4/+8 values, and the exact
  loop index/EDX/EDI/ECX when an entry equals `0x80000000`. Do not skip the
  retail dereference and do not map the KSEG first-page fence; the purpose is
  to distinguish missing CreateDevice/device-context initialization from a
  legitimate sentinel before applying semantics.

- **Phase 6AN-A build - INVALID / no hardware test:** emission and shard sync
  passed, but VS2017 rejected the probe because the diagnostic helper functions
  were emitted before `GUEST_READ32` and `trace` were declared. Errors were
  C3861 at main.cpp lines 130-155/197. No XEX was produced; this is source-order
  evidence only, not runtime evidence.
- **Phase 6AN-B active - source-order-safe state-stack probe:** retain only the
  probe globals at the early 6AJ state location and inject all guest reads and
  sentinel capture inline inside `sub_0028BC60`, where the guest-access
  macros are already valid. Preserve the same probe fields and hard fences.
  Publish a distinct P6AN-B XEX and use the end-of-run
  `P6AN D3D STACK SUMMARY` as the authoritative hardware evidence.

- **Phase 6AN-B hardware - diagnostic PASS / zero-depth underflow proven:**
  native Xenos CreateDevice, retail roots 0x00290895/0x0028E700, and prior D3D
  proofs remain healthy. The orange boundary is still READ32 0x80000004. The
  focused stack summary captured +0x1A10 count=0, zero +0x1A14/+0x1A18/+0x1A1C
  entries, one sentinel hit, loop count 1645, and sentinel EDX=0xFFFFF993.
  Because sub_0028BC60 decrements the count before its backward-copy loop,
  count=0 underflows and walks backward through the device object until it
  encounters 0x80000000 at device+0x5C; the KSEG address is therefore an
  accidental dereference caused by missing/invalid D3D stack initialization.
- **Phase 6AO-A active - exact D3D stack writer audit:** PC-only scan of the
  cached exact-XBE translated source for every +0x1A04..+0x1A1C reference,
  every write to +0x1A10/+0x1A14/+0x1A18/+0x1A1C (including absolute device
  addresses), every direct caller of sub_0028BC60, and focused source windows.
  Do not synthesize a stack depth yet; identify the exact initialization path
  bypassed by the CreateDevice handoff first.

- **Phase 6AO-A forensic - PASS / exact count writer isolated:** the exact-XBE
  scan found 90 +0x1Axx references but only five stack-field writes. Four are
  unrelated +0x1A14 array operations controlled by +0x1B14 in sub_000DBE00/
  000DBE40/000DBE90/000DBEE0. The sole D3D +0x1A10 count writer is
  sub_0028F9E0: it loads a stack/local value, increments it, and stores the
  result to device+0x1A10, then builds/iterates entries beginning at +0x1A14.
  No ordinary translated direct caller of sub_0028BC60 exists in the current
  packed source, reinforcing an indirect D3D dispatch path.
- **Phase 6AP-A active - recover retail D3D initializer provenance:** PC-only
  audit of the full sub_0028F9E0 body/call surface, every current textual or
  literal reference to 0x0028F9E0, and every cached Phase-6 sub_0028CAA0 body.
  Group distinct CreateDevice bodies and identify pre-6AF retail-like versions
  versus the later native bridge, highlighting any original path that reaches
  0028F9E0. Do not synthesize +0x1A10/+0x1A14 state until this provenance is
  recovered.

- **Phase 6AP-A forensic - PASS / retail CreateDevice handoff recovered:** cached
  pre-6AF sub_0028CAA0 has one retail-like body. It publishes internal device
  0x00299380 to global 0x00299378, sets related globals, then calls the retail
  initializer through phase4c_direct_frontier(0x0028FF80). On failure it calls
  0x00290450 cleanup, clears the device object, clears 0x00299378, and returns
  the failing HRESULT. On success it returns the guest device pointer. The
  later 6AF native bridge replaced this whole body, so 0x0028FF80 is the prime
  missing initialization path.
- **Phase 6AQ-A active - trace 0x0028FF80 to the sole +0x1A10 writer:** PC-only
  bounded direct/frontier call-graph audit rooted at sub_0028FF80, targeting
  sub_0028F9E0. Dump the shortest path and flag hardware/MMIO-looking accesses
  on every path function. The goal is to separate required guest D3D object
  initialization from original Xbox/NV2A hardware work before restoring any
  post-CreateDevice semantics.

- **Phase 6AQ-A forensic - PASS / direct initializer edge proven:** bounded call
  graph reaches the sole +0x1A10 writer in one edge:
  sub_0028FF80 -> sub_0028F9E0. Immediately before the call, 0028FF80 loads
  its first argument (the original CreateDevice presentation-parameters
  pointer), pushes it, sets ECX to the guest device, and directly invokes
  sub_0028F9E0. The parent 0028FF80 also contains original-Xbox absolute
  writes to 0x80000000, including a DEADBEEF marker, so restoring it wholesale
  is rejected.
- **Phase 6AR-A active - selective retail post-Create state repair:** keep the
  proven native-Xenos CreateDevice and 0x00299378 internal-device publication,
  then invoke only sub_0028F9E0 with the exact retail ABI
  (ECX=0x00299380, arg1=live CreateDevice pp). Validate guest stack balance,
  nonnegative HRESULT, nonzero +0x1A10 count and nonzero +0x1A14 first entry
  before allowing translated D3D to continue. Emitter preflights all nine
  immediate helper callees and refuses the build if any contains a literal
  absolute guest write at >=0x80000000. Parent 0028FF80 remains bypassed and
  all KSEG/NV2A/MMIO/VRAM fences remain hard.
