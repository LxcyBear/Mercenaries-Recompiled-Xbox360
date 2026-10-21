# Phase 5 Exit Gate — Phase 6 Subsystem Exposure & Reconnaissance

> **Status: COMPLETE — PASS (2026-10-21)**
>
> Phase 5BV repeatability passed 3/3 on real Xbox 360 hardware. The exit audit
> then classified the stable `0x0014CD30` endpoint as exact generated title
> code, inventoried all five required subsystem families, produced the risk map
> and ordered Phase-6 handoff, and reported `[Phase5Exit] READY / PASS`.


This is the mandatory final Phase 5 stage after the translated/runtime
saturation roadmap is complete. It does **not** implement the Phase 6
graphics/audio/movie/input backends. Its purpose is to expose, classify, and
measure the platform-facing work that Phase 6 will inherit.

## Purpose

Phase 5 must not end merely because the current translated boot path stops
discovering new function/frontier coverage. Before Phase 6 begins, the port
must have a concrete map of the title-facing subsystem surface and a real
hardware first-touch timeline showing which pieces are reached first.

The exit stage combines:

1. a whole-codebase static subsystem-surface audit; and
2. an observe-only real-Xbox-360 first-touch trace.

The result is a Phase 6 implementation/risk map rather than a speculative list.

## Non-goals

This stage must **not**:

- pretend a graphics device, audio engine, movie decoder, or controller backend
  is functional merely to advance execution;
- replace genuine subsystem operations with success-returning stubs;
- classify unknown behavior as safe without evidence;
- hide ABI, resource-lifecycle, threading, endian, or synchronization gaps;
- declare Phase 6 functionality complete.

Maintained no-op helpers are allowed only when review proves they are
observational/diagnostic-only and have no guest-visible semantics, following
the precedent established during Phase 5.

## Static exposure audit

Scan translated game code, maintained runtime code, manual hooks, patches,
resource helpers, and platform boundaries for Phase-6-facing operations.

At minimum classify:

### Graphics / display

- device/display creation and teardown;
- presentation/swap/display-mode paths;
- render-target and depth/stencil lifecycle;
- textures, surfaces and resource upload/lock/unlock paths;
- vertex/index buffers and vertex declarations;
- shader/shader-like translated paths and constants;
- render-state, sampler-state, transform and viewport/scissor usage;
- clear/draw/submit operations;
- resource formats/layout assumptions and Xbox/NV2A-specific behavior;
- synchronization, fences, command submission and frame pacing;
- graphics-related file/resource loading.

### Audio

- audio/XACT-style initialization and teardown;
- bank/wave/cue discovery and lifecycle;
- buffers, voices, streams and playback control;
- 3D audio/listener/emitter parameters;
- codecs/streaming and async refill behavior;
- volume/mix/routing state;
- synchronization and timing dependencies;
- existing maintained audio-side fixes and assumptions.

### Movies / video

- movie/player initialization and teardown;
- file/resource discovery;
- decode/output surfaces;
- audio/video clocking and synchronization;
- skip/input behavior;
- presentation/compositing handoff;
- format/codec assumptions.

### Input

- controller discovery/polling;
- button/axis mapping;
- deadzone and normalization behavior;
- vibration/feedback;
- device reconnect/disconnect semantics;
- input timing/frame integration.

### Cross-cutting dependencies

- async I/O and worker threads;
- events/critical sections and other synchronization;
- timers/frame clocks;
- guest/native allocation and resource ownership;
- endian-sensitive resource structures;
- filesystem/path/content dependencies;
- lifecycle ordering between graphics/audio/movie/input systems.

## Hardware first-touch trace

Run the final Phase 5 hardware image with observe-only subsystem probes.

For each first touch or newly distinct semantic operation, capture as much as is
safely available:

- monotonic sequence/timestamp;
- translated caller VA and target/boundary;
- subsystem and operation classification;
- stack/ABI shape;
- relevant argument/register values;
- guest pointers and bounded previews/metadata where safe;
- resource handle/id/type relationships;
- create/use/destroy lifecycle relationships;
- thread identity/context when available;
- call count;
- result/fault state;
- whether the operation is required before first frame, logo/movie, menu, or
  later gameplay.

A genuine unimplemented subsystem operation remains a hard boundary. The trace
may observe it, but must not fabricate successful device/backend behavior.

## Required outputs

The final implementation should generate machine-readable and human-readable
artifacts equivalent to:

- `phase5-exit-subsystem-surface.json`
- `phase5-exit-subsystem-surface.md`
- `phase5-exit-first-touch.txt`
- `phase6-risk-map.json`
- `phase6-handoff.md`

Exact filenames may change when implemented, but the information content below
is required.

Each classified boundary/operation should include, where known:

- subsystem;
- operation/family;
- source/callsite;
- translated/manual/platform-bound status;
- observed-on-hardware status;
- first-touch order;
- ABI/argument notes;
- resource/lifecycle notes;
- threading/synchronization notes;
- first-frame/menu criticality;
- implementation dependency;
- proposed Phase 6 strategy;
- risk/complexity rank;
- evidence/confidence.

## Phase 6 handoff

The handoff must produce an ordered implementation plan, not merely a catalog.

At minimum identify:

1. operations required for the first native visible frame;
2. operations required for startup logo/movie;
3. operations required for main-menu rendering and input;
4. audio operations needed before/at the menu;
5. operations that can safely wait for gameplay hardening;
6. unresolved or high-risk semantics needing dedicated research/prototyping.

## Exit criteria

Phase 5 is complete only when all of the following are true:

- the current translated/runtime saturation roadmap has reached its completion
  and repeatability gate;
- no unexplained translated/runtime frontier remains on the tested boot path;
- reachable Phase-6-facing boundaries have been observed/classified on hardware
  where possible;
- statically discoverable Phase-6-facing operations have been inventoried even
  when not yet dynamically reachable;
- graphics, audio, movie, input, and cross-cutting dependencies each have a
  documented surface map;
- a hardware first-touch timeline exists;
- first-frame/logo/movie/menu critical operations are explicitly identified;
- unknown/unclassified entries are called out rather than silently guessed;
- the Phase 6 risk map and ordered implementation plan are complete;
- the exit stage does not claim backend functionality that it did not actually
  implement or verify.

## Expected result

Phase 6 should begin with a bounded, evidence-backed implementation backlog:
what must exist for first pixels, what is needed next for movie/audio/menu,
what can wait until gameplay, and which semantics are likely to be the hardest.

This exit gate intentionally turns the Phase 5 -> Phase 6 transition from
open-ended subsystem discovery into a measured implementation handoff.


## Completion result — PASS

The implemented exit gate passed with:
- endpoint `0x0014CD30` classified as an exact generated title function in
  `recomp_0006.c`, original range `0x0014CD30-0x0014CD9C`;
- Phase 5BV frozen-pack hardware repeatability already proven 3/3;
- graphics/display, audio, movies/video, input and cross-cutting surfaces
  inventoried;
- all five required handoff artifacts emitted;
- six Phase-6 risks ranked;
- no fake backend-success behavior introduced.

**Phase 5 is complete. Phase 6 implementation may begin.**
