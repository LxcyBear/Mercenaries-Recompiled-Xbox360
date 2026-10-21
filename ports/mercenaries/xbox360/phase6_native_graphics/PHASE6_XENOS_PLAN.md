# Phase 6 — Native Xbox 360 graphics (Xenos)

> **Status:** ACTIVE · Phase 6C hardware frontier PASS on 2026-10-21
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
- **Phase 6D:** promotes exact target `0x0014E2D0` with the same depth-12 /
  cap-512 bounded direct continuation and the live native Xenos surface.

Purple remains reserved for an actual rejected NV2A MMIO/VRAM access. No
purple GPU-boundary event has yet been confirmed by xbWatson.
