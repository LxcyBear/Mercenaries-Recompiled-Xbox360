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
| 6 — Native Xenos graphics | **In progress** | Retail asset I/O is alive; 6BT completed the observed 200 ms `KeDelayExecutionThread`; current blocker is canonical ordinal-246 `ObReferenceObjectByHandle` at `0x800000F6`, `fault=0` |
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
- **Phase 6BK — hardware PASS / major frontier transition:** the later PFIFO `FD003220=0` clear completed; retail D3D root `00290895` PASS, internal D3D device PASS, D3D sync checkpoints=9, and the 640×480 D3D device summary populated.
- **Phase 6BL — hardware PASS:** the translated closure rooted at `0028B180` entered successfully and advanced execution to clean `DIRECT_FRONTIER 00290970` with `fault=0`.
- **Phase 6BM — hardware PASS / XGRPH transition:** translated root `00290970` entered; execution advanced to clean `DIRECT_FRONTIER 0029C8BE` with `fault=0`.
- **Phase 6BN — hardware PASS / return to title `.text`:** XGRPH root `0029C8BE` entered six times and execution advanced to clean `DIRECT_FRONTIER 00209810` with `fault=0`.
- **Phase 6BO — hardware root-entry PASS / kernel-frame frontier:** exact translated root `00209810` entered once, then ordinal-289 `RtlInitAnsiString` stopped on caller context `0023A3CE` with 16-byte saved-ESP delta vs canonical 12 and `fault=0`.
- **Phase 6BP — hardware PASS / PBL phase-1 progress:** the `0023A3CE` `RtlInitAnsiString` frame repair succeeded; `d:\\xesrb.tga` and `d:\\` opened successfully; PBL checkpoint phase 1 fired; next boundary is ordinal-218 `NtQueryVolumeInformationFile` with 28-byte delta vs canonical 24 and `fault=0`.
- **Phase 6BQ — hardware PASS / PBL phase-2 progress:** the `0023A3CE` ordinal-218 `NtQueryVolumeInformationFile` 28→24-byte repair passed after canonical class-3 validation. The native volume query completed; two class-34 `NtQueryInformationFile` queries on `game:\\xesrb.tga` succeeded; the maintained PBL checkpoint reached `calls=2 phase1=1 phase2=1`; and execution advanced to clean `DIRECT_FRONTIER 0x00209A70` with `fault=0`.
- **Phase 6BR — hardware PASS / post-PBL title progress:** exact generated root `00209A70` entered once and execution continued through `00209A7C/85/8C` into the `00229Fxx` title path. The PBL observer advanced to `calls=3`, retaining live file handle `0x48000001`. The next boundary is `ICALL_SAFE target=0x800000E2` (ordinal 226 `NtSetInformationFile`) with a canonical 24-byte frame and `fault=0`.
- **Phase 6BS — hardware PASS / complete `xesrb.tga` consumption:** ordinal-226 `NtSetInformationFile` class-14 seeks succeeded three times. The game then read 786,432 bytes and the final 44 bytes from `game:\\xesrb.tga`, exactly matching its 786,476-byte EOF, proving complete retail asset-file consumption. Execution re-entered XGRPH, PBL advanced to `calls=4`, and the next boundary is `ICALL_SAFE target=0x80000063` (ordinal 99 `KeDelayExecutionThread`) with canonical 16-byte frame and `fault=0`.
- **Phase 6BT — hardware PASS / relative wait continuation:** the live ordinal-99 `KeDelayExecutionThread` frame was canonical (`wait_mode=1`, `alertable=0`) with interval `FFFFFFFFFFE17B80`; the existing Phase-4B conversion executed it as a 200 ms relative wait successfully. The next clean boundary is `ICALL_SAFE target=0x800000F6` (ordinal 246 `ObReferenceObjectByHandle`) with canonical 16-byte frame and `fault=0`.

### Current next step — Phase 6BU

Phase 6BT is hardware-proven. The live ordinal-99 `KeDelayExecutionThread` call used a canonical 16-byte frame with `wait_mode=1`, `alertable=0` and relative interval `0xFFFFFFFFFFE17B80`; the Phase-4B-derived delay bridge converted that interval to 200 ms and returned successfully.

Execution then advanced to `ICALL_SAFE caller=0023A3CE target=800000F6 esp=008BF8EC saved_esp=008BF8FC`, `fault=0`. Ordinal 246 is `ObReferenceObjectByHandle(HANDLE, ObjectType*, Object**)`; the observed frame size is canonical, but the live three arguments and required guest object representation are not yet proven. Phase 6BU is intentionally probe-only: it logs Handle, ObjectType and ReturnedObject*, classifies the handle through the existing tagged native-handle table, and synthesizes no object pointer. All 6BT file, delay, ABI, GPU/MMIO, allocator and 8M-budget invariants remain unchanged.

## Next major graphics milestones

1. Probe ordinal 246 `ObReferenceObjectByHandle` live arguments without synthesizing an object pointer; use the hardware frame to decide whether a simple handle→guest-object mapping is sufficient.
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
