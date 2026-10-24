# Mercenaries Recompiled — Xbox 360 Roadmap

> **Updated:** October 24, 2026  
> **Default branch:** `master`  
> **Active development branch:** `xbox360/phase6-native-graphics`  
> **Current focus:** Phase 6 — native Xbox 360 graphics / NV2A-to-Xenos bring-up

## Project goal

Run the supported retail original-Xbox release of *Mercenaries: Playground of Destruction* as a native Xbox 360 XEX by recompiling the translated x86 game code for Xenon PowerPC and replacing the surrounding Xbox/PC compatibility services with Xbox 360-native implementations.

No retail game data is distributed by this repository. Users must provide their own legally obtained game files/XBE.

## Phase status

| Phase | Status | Current result |
| --- | --- | --- |
| 0 — Foundation / audit | In progress | Portable-memory and source-audit work remains |
| 1 — Native XDK bootstrap | **Complete** | Real Xbox 360 XEX boots, logs, handles input, exits cleanly |
| 2 — Guest memory + retail XBE | **Complete** | Exact supported retail XBE, 64 MiB arena, sections/TLS/TIB/stack/kernel-data verified |
| 3 — PPC recompilation + guest ABI | **Complete** | Translated-code scale/ABI gates passed on hardware |
| 4 — Native platform/kernel layer | **Complete** | Retail startup executes through migrated Xenon service layer |
| 5 — Subsystem bring-up | **Complete** | Repeatability and Phase-6 handoff gates passed |
| 6 — Native Xenos graphics | **In progress** | Native Xenos presentation proven; first genuine guest NV2A MMIO touch proven; PFIFO/PGRAPH idle gates and PFB tile LIMIT/PITCH crossed; current frontier `DIRECT_FRONTIER 0x0028B180` (fault=0) |
| 7 — Audio/movies/input/streaming integration | Not started | Begins after stable graphics path |
| 8 — Gameplay/compatibility hardening | Not started | Playability, save/load, missions, stability |

## Phase 6 — current hardware truth

The graphics path has moved from speculative initialization debugging into the real Xbox GPU command path.

### Proven milestones

- Native Xbox 360 D3D/Xenos device, backbuffer and presentation work on real hardware.
- Retail title heap supports the large graphics-side allocation.
- Retail contiguous graphics claims are hardware-proven:
  - 23,592,960 bytes at guest `0x02880000`
  - 2,457,600 bytes at guest `0x02628000`, 16 KiB aligned
- Exact retail D3D frontier `0x00292586` executes.
- The long translated D3D spin was traced to `sub_00292271`.
- Retail D3D static-state relationship is proven:
  - base `0x00299380`
  - child object `+0x1C28 = 0x0029AFA8`
  - constructor helper `sub_00291F31` initializes child[0] to NV2A BAR0 `0xFD000000`
- **Phase 6BD — hardware PASS:** restoring only that proven BAR0 field immediately produced READ8 `0xFD003214`. The reserved diagnostic display turned **purple**, proving the first genuine guest NV2A MMIO boundary.
- **Phase 6BE — hardware PASS:** the PFIFO idle/quiescence loop was answered with the maintained backend semantics:
  - `FD003214 -> 0x10` — CACHE1 status LOW_MARK
  - `FD002400 -> 0x10` — runout status LOW_MARK
  - `FD003220 -> 0x00` — DMA pusher idle/state clear
  - zero clear of `FD003220` accepted
- After the PFIFO wait completed, translated execution advanced through `002922BE -> 002922D9 -> 0029259D -> 00292610 -> 0029528C`.
- **Phase 6BF — hardware PASS:** `FD400700` was bridged twice with backend-equivalent zero. Retail D3D then allocated 1,228,800 bytes at `0x024FC000` and advanced to WRITE32 `0xFD100254`.\n- **Phase 6BG — hardware PASS:** `FD100254` (PFB tile #1 LIMIT) accepted `0x02627FFF`, and `FD100258` (tile #1 PITCH) accepted `0x00000A00`.
- **Phase 6BH — hardware PASS:** PGRAPH writes `FD400914=02627FFF`, `FD400918=00000A00`, and `FD400910=024FC003` all crossed; execution advanced to PFB tile #1 BASE at `FD100250`.
- **Phase 6BI — hardware PASS:** PFB tile #1 BASE `FD100250=024FC003` crossed and read back correctly; PGRAPH `0910/0918/0914` readbacks matched their shadowed values.
- **Phase 6BJ — hardware PASS:** PFB ZCOMP tile #1 `FD100304=84000000` crossed, mirrored through PGRAPH `FD400984`, and both readbacks returned `84000000`.
- **Phase 6BK — hardware PASS / major frontier transition:** the later PFIFO `FD003220=0` clear completed; retail D3D root `00290895` PASS, internal D3D device PASS, D3D sync checkpoints=9, and the 640×480 D3D device summary populated. Execution then reached clean `DIRECT_FRONTIER 0028B180` with `fault=0`.

### Current next step — Phase 6BL

Phase 6BK is hardware-proven and marks the end of the previous MMIO-driven choke point. The later PFIFO `FD003220=0` clear completed, then the retail D3D root `0x00290895`, internal D3D device result, sync checkpoint summary and 640×480 device summary all reported PASS. The next boundary is no longer NV2A MMIO: it is a clean `DIRECT_FRONTIER 0x0028B180` with `fault=0`.

Phase 6BL is prepared to add the exact generated `sub_0028B180` retail D3D function plus a bounded depth-4/cap-256 support-clean dependency closure. All Phase 6BK PFIFO/PFB/ZCOMP/PGRAPH semantics, allocator geometry, 8,000,000-tick watchdog and unrelated NV2A/MMIO/VRAM hard fences remain unchanged.

## Next major graphics milestones

1. Cross the clean translated-code frontier at `0x0028B180` with its bounded dependency closure.
2. Capture and classify the next NV2A register or command-stream access.
3. Route proven PFIFO/PFB/PGRAPH behavior into the maintained NV2A/Xenos translation layer.
4. Reach pushbuffer/resource/surface setup.
5. Produce the first **Mercenaries-generated pixels**.
6. Produce a recognizable title/loading/menu frame.
7. Correct textures, shaders, depth, blending, synchronization and presentation.
8. Reach a repeatable rendered 3D scene.

The first pixels may be incomplete or visually corrupted; they still count as a major milestone if they are generated by the retail game path rather than the native diagnostic surface.

## Visual diagnostics

- Native color-cycle output proves the Xbox 360 presentation path only.
- **Purple is now hardware-proven to mean the translated retail path reached a genuine NV2A MMIO boundary.**
- Purple is **not** itself a game-rendered frame.

## Longer-term graphics strategy

Once individual MMIO bridges stop being the efficient path, use the accepted oracle workflow:

1. Trace the corresponding retail path on PC/xemu beyond the current frontier.
2. Capture relevant guest RAM + NV2A/pushbuffer state.
3. Replay/classify that traffic on Xbox 360.
4. Translate supported render state/methods to Xenos.
5. Maintain a typed, hash-keyed shader translation table where required.

## Exit criteria for Phase 6

Phase 6 is complete only when all of the following are true:

- A repeatable game-generated frame appears on real Xbox 360 hardware.
- Title/menu graphics are functional.
- At least one reproducible 3D scene renders through the native Xenos path.
- GPU synchronization no longer depends on diagnostic one-off shims.
- Required NV2A/PFIFO/PGRAPH behavior is represented by maintained translation/backend code.
- The result is reproducible from a clean documented build using user-supplied retail assets.

## Distribution rule

This repository must not contain the retail XBE, game assets, extracted copyrighted game files, XDK redistributables, or other proprietary Microsoft/game content. The port code and tooling are intended to operate on files supplied separately by the user.
