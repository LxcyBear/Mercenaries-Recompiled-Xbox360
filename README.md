# Mercenaries Recompiled — Xbox 360 Edition

> **Experimental native Xbox 360 port · Not playable yet**
>
> **Platform:** modified Xbox 360 · Xenon PowerPC · Xbox 360 XDK / VS17 · native `default.xex`
>
> **Last roadmap review:** October 18, 2026 · **Current focus:** Phase 3A explicit scalar guest-memory ABI after completing Gate 2.
>
> **Active development:** [Xbox 360 foundation — Draft PR #1](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/pull/1). Prototype sources are on the PR branch, **not** on `master` until reviewed and merged.

## The mission

Build a **native Xbox 360** edition of *Mercenaries: Playground of Destruction* by
using the already-translated original Xbox **x86-to-C game code**, recompiling
that code for Xbox 360 **PowerPC**, and **porting/replacing the surrounding PC
compatibility runtime** with native Xbox 360 implementations.

Our starting point is [Mercenaries-Recompiled](https://github.com/KraftMacAndChee/Mercenaries-Recompiled)
by KraftMacAndChee, which uses [xboxrecomp](https://github.com/sp00nznet/xboxrecomp).
The upstream project statically recompiles a specific original Xbox retail
executable and runs it on Windows x64. Its gameplay and script logic comes from
the translated game. Its current rendering, audio, input, memory mapping and
kernel support are Windows-hosted compatibility layers.

**Chosen route: hybrid native port + static recompilation.** We do *not* plan to
reconstruct the entire game engine from scratch, retranslate its machine code
unnecessarily, or simply repackage the Windows executable. We do need to adapt
the translator output and build a real Xbox 360-native host.

This is not the original Xbox backward-compatibility emulator and not an
emulator running inside an XEX. `default.xex` is the intended native output.

### Scope and distribution rules

- Supported original Xbox game input must come from the user's own legal retail
  copy. The upstream project identifies the supported USA retail XBE with
  SHA-256 `AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7`.
- Do not commit or distribute a game ISO, extracted game files, the retail XBE,
  copyrighted generated game code, XDK headers/libraries, or Microsoft SDK assets.
- Preserve upstream attribution and the applicable **per-file licenses**; the
  root MIT license does not supersede LGPL and third-party components.
- A successful `default.xex` build is **not** evidence of gameplay. Real-hardware
  startup, graphics, input and asset loading must be verified separately.

---

## Live project status

Progress is based on **tested exit criteria**, not invented percentage values.
Each phase has independently checkable checkpoints below.

| Phase | State | Exit criterion |
| --- | --- | --- |
| **0 — Foundation and audit** | **In progress** | Portable memory tests PASS and guest memory access/lvalue audit documented |
| **1 — Native XDK bootstrap** | **COMPLETE** | Diagnostic XEX builds, runs on a real 360, logs heartbeats, detects input, and exits cleanly by input or timeout |
| **2 — Guest memory + retail XBE loading** | **COMPLETE — Gate 2 PASS on modified Xbox 360 hardware** | Correct Xbox guest bytes/addresses, section loading, aliases, MMIO fixture PASS |
| 3 — PPC recompilation + x86 guest ABI | Not started | Real-console instruction/call/stack/FP fixtures agree with reference |
| 4 — Native platform + kernel services | Not started | Required file, input, thread, timing, handle and guest callback fixtures PASS |
| 5 — Xenos graphics + first frame | Not started | Verified first frame, then main menu, then 3D rendering |
| 6 — Audio, movies and streaming | Not started | Audio/video/streaming timing and resource tests PASS |
| 7 — Gameplay, stability and release | Not started | Repeated playable scenarios, save/load, mission progression and documented release |

**Verified foundation:** the VS17/XDK bootstrap, 64 MiB guest RAM contract,
exact retail-XBE identity, and bounded 14-section load have all passed on real
Xbox 360 hardware. The pinned retail SHA-256 was computed on Xenon itself and
matched exactly. Translated Mercenaries game code has still **not** been
executed on Xbox 360.

**Present blockers:** generated `MEM16/32/64` expressions are assignable
native-pointer lvalues and still require a coordinated lifter/runtime refactor;
the Windows mapped-alias model cannot be carried directly to the 32-bit Xbox
360 process; guest RAM mirrors/KSEG/synthetic kernel/MMIO routing still need
native checked dispatch; D3D11, Win32, DXGI and host-audio dependencies still
need Xbox 360-native replacements.

### Immediate next tests

1. **Done:** native XEX bootstrap, input, heartbeat and clean timeout.
2. **Done:** 64 MiB guest RAM + little-endian access contract on Xenon.
3. **Done:** bounded retail XBE parse/load and exact on-console SHA-256.
4. Implement a checked guest-address router for low RAM mirrors, KSEG0/KSEG1
   aliases, synthetic kernel/fence pages, and explicit MMIO classification.
5. Validate alias coherence and low-memory/TIB fixtures on real hardware before
   any translated Mercenaries function is permitted to execute.

### Evidence policy

`[x]` = source/analysis task confirmed as **done**; it does **not** indicate
hardware validation unless the item explicitly says so. `[ ]` = outstanding.
Milestones move to **Done** only with test evidence. When a new change lands,
update the **status table, affected checklist, blockers, evidence table, and
progress log in the same commit/PR**, so the README stays synchronized with
actual progress. Failed experiments belong in the log, too.

---

## Detailed roadmap

### Phase 0 — Audit, test harness, and portable memory foundation

**Purpose:** retain the working upstream PC path and establish a testable
guest-memory contract before modifying generated code.

- [x] Confirm static original Xbox x86-to-C translation is reusable.
- [x] Identify the direct `MEM8/16/32/64` macros, shared register globals, and
      `g_xbox_mem_offset` guest-to-host address mapping.
- [x] Write explicit little-endian 16/32/64-bit and float access helpers in
      the development branch (not integrated with generated code yet).
- [x] Write unaligned byte-order tests in the development branch (not yet run).
- [x] Run the portable endian tests with GCC 14.2.0 and Clang 17.0.0 on Linux
      x86-64; also run Clang UBSan. All 3 passed. Confirm that the tested
      source Git blobs match the branch versions (guest endian header
      `289c8792` and test source `00149528`). This is **not** PowerPC proof.
- [ ] Audit read, write, compound assignment and read-modify-write forms in
      generated C, maintained lifter, patches, manual hooks, guest structures
      and hardware MMIO.
- [ ] Record baseline memory/instruction results from the current Windows port
      to compare against future PowerPC output.
- [ ] Inventory source/toolchain dependencies and choose a clean platform
      boundary so upstream Windows builds continue to work.

**Gate 0:** proven portable tests and an explicit plan for removing the
incorrect native-endian guest pointer dereferences without losing lvalue
semantics.

### Phase 1 — Xbox 360 toolchain and safe hardware bootstrap

**Purpose:** establish a reproducible XDK build/launch/logging loop *before*
trying to run original Xbox guest game code.

- [x] Add source for a **diagnostic-only** console entry point to Draft PR #1.
- [x] Open or reuse a VS17 Xbox 360 XDK **game** project using the user's working SDK; **build succeeded on October 18, 2026**.
      link only required system libraries and include the bootstrap source.
- [x] Produce and deploy an Xbox 360 XEX from VS17/XDK. Build and hardware execution both succeeded; exact local artifact path remains environment-specific.
- [x] Launch from a new isolated folder; real modified Xbox 360 hardware execution confirmed October 18, 2026.
- [x] Confirm debug output: xbWatson captured `[Merc360]` startup, heartbeat, controller and shutdown messages.
- [x] Confirm 1-second heartbeats and controller 0 detection on real hardware.
- [x] Confirm A-button exit and clean XAPI return value 0.
- [x] Confirm the independent 15-second automatic timeout in a separate run; clean `[XAPI RETURN VALUE] 0` verified.
- [ ] Record console model, kernel, build flavor, XEX size, debugger/xbWatson
      transcript and any failed test cases.
- [ ] Add a small probe for CPU endian, available memory, file access,
      high-resolution timing and allocation failures.

**Gate 1:** real modified Xbox 360 hardware produces consistent startup, log, input
and shutdown evidence. A black screen from this diagnostic is expected;
**it has no renderer**.

### Phase 2 — Original Xbox guest memory / XBE sections

**Purpose:** safely reproduce original Xbox 32-bit guest addresses in
Xbox 360 native memory.

- [x] Implement a bounded 64 MiB low guest-RAM arena and verify it on both host
      contract tests and real Xbox 360 Xenon hardware.
- [x] Implement and verify the Phase 2D checked guest-VA router for RAM,
      configured mirrors, KSEG aliases, synthetic fence/kernel pages, VRAM,
      kernel thunks and NV2A/APU/AC97 classification. Host tests and the real
      Xenon hardware fixture both PASS.
- [x] Implement explicit endian-correct, alignment-safe guest 8/16/32/64-bit
      and float reads/writes for the bounded low-RAM arena; host tests PASS.
- [x] Verify those accessors on real Xenon hardware: **Phase 2A PASS**. Xenon reported big-endian host order; every low/high/unaligned/endian/bounds test passed and the XEX returned 0.
- [x] Establish explicit checked-access semantics and a hardware-proven address
      router for the Phase 2 fixtures. **Generated assignable MEM lvalues are a
      Phase 3 translator/ABI task and are tracked there, not as a Gate 2 blocker.**
- [x] Load the exact supported retail XBE on Xenon: on-console SHA-256 matched
      the pinned digest, 14/14 sections loaded, initialized bytes matched the
      source, and every virtual/BSS tail remained zero.
- [x] Compare guest-memory fixtures and alias behavior on hardware: configured
      RAM mirrors, KSEG0/KSEG1 aliases, synthetic fence/kernel priority,
      unsupported gaps, TIB/TLS/KTHREAD/kernel-data coherence all PASS.
- [ ] Stress-test allocator fragmentation/low-memory behavior during later
      kernel-service and reliability phases; this is no longer a Gate 2 blocker.
- [x] Host-test upper-bound crossing, first-out-of-range and wrapped/high
      addresses; all are rejected without sanitizer findings.

**Gate 2: PASS (October 18, 2026).** Exact guest byte/alias/section and
execution-environment fixtures pass on modified Xbox 360 hardware. Phase 2 is
complete; no translated Mercenaries game function has executed yet.

### Phase 3 — PowerPC-safe generated C and execution ABI

**Purpose:** preserve guest x86 instruction behavior even though host code
executes as Xbox 360 PowerPC.

- [ ] Audit translated instruction helpers for x86-only intrinsics,
      compiler extensions, native-endian casts, 32/64-bit assumptions and
      Windows/MSVC-specific code.
- [x] Begin maintained-lifter migration with opt-in Phase 3A scalar integer
      `GUEST_READ8/16/32/64` + `GUEST_WRITE8/16/32/64` emission. Legacy PC
      output remains unchanged by default; float/SSE/MMX/string/manual paths
      remain later Phase 3 work.
- [ ] Generate and compile isolated instruction fixtures under the actual
      Xbox 360 compiler before attempting all translated functions.
- [ ] Validate flags, sign extension, stack/calling convention, frame saving,
      `RECOMP_ICALL` dispatch, direct/tail calls and function returns.
- [ ] Validate x87, MMX and SSE semantics against the original instruction
      results; test rounding, NaN and exceptional paths.
- [ ] Evaluate Xenon limitations: native stack depth, object/code size,
      memory budget and compiler/linker constraints.
- [ ] Execute a bounded translated function, then a small call chain, then
      the game's entry sequence with guardrails and logging.

**Gate 3:** reproducible real-hardware guest ABI fixture suite PASS with
reference comparisons.

### Phase 4 — Xbox 360 platform and original Xbox kernel bridge

**Purpose:** provide original Xbox guest services using native Xbox 360 APIs.

- [ ] Inventory original Xbox kernel imports *actually used by Mercenaries*
      and keep the subset explicit.
- [ ] Replace Win32 memory, file I/O, event/handle, thread and
      synchronization implementations without losing guest ordering.
- [ ] Implement title-owned path mapping for games, saves and logs.
- [ ] Support Xbox 360 controller input and original-game button mapping.
- [ ] Preserve guest timers, callbacks, interrupts, DPC/ISR safe points and
      thread scheduling expectations.
- [ ] Validate guest kernel data exports and safe callback delivery.
- [ ] Exercise real asset reads and title shutdown/error cases.

**Gate 4:** startup service requests and title-critical imports have verified
native implementations, not unexplained stubs.

### Phase 5 — Native Xbox 360 graphics (Xenos)

**Purpose:** replace NV2A/PGRAPH-to-D3D11 hosting with a correct native
360 graphics backend.

- [ ] Inventory actual Mercenaries NV2A pushbuffers, texture formats,
      swizzle, render states, vertex programs, combiners and surface aliases.
- [ ] Introduce backend-neutral presentation/texture/draw interfaces.
- [ ] Initialize an Xbox 360 graphics device and render an independent test
      surface (not yet the game).
- [ ] Implement compatible 2D, textured draw and flip operations.
- [ ] Translate needed shaders and vertex formats; validate depth/stencil,
      blending, alpha testing, render targets and synchronization.
- [ ] Capture the first guest-rendered frame; then the main menu;
      then a reproducible 3D scene, comparing to the working PC reference.
- [ ] Measure frame time, GPU memory and render errors on hardware.

**Gate 5:** repeatable first frame and functional title/menu/scene graphics.

### Phase 6 — Audio, movies, asset streaming and timing

- [ ] Identify needed original Xbox APU, DirectSound and XACT behavior.
- [ ] Implement/bridge native Xbox 360 audio output, sound decoding and
      channel/mixing behavior.
- [ ] Preserve sample progression, callbacks and cutscene timing.
- [ ] Implement required movie playback or a lawful user-side conversion
      approach without bundling proprietary video.
- [ ] Validate loading/streaming on console storage within available RAM.
- [ ] Test music, dialogue, SFX, movie transitions and long idle playback.

**Gate 6:** no critical missing sound, timing drift or cutscene softlock in
the documented test scenarios.

### Phase 7 — Gameplay, reliability and packaging

- [ ] Start game, use menus, load world and control a character.
- [ ] Test driving, combat, AI, mission triggers and asset loading.
- [ ] Test save/load, checkpoints and repeated cold starts.
- [ ] Run extended sessions and record memory/CPU/GPU use and crashes.
- [ ] Optimize only after profiling actual hardware; document FPS and
      resolution measurements rather than speculative targets.
- [ ] Produce repeatable builds, provenance, bug list and setup guide.
- [ ] Verify no proprietary Xbox 360 SDK or original game files are
      included in public release artifacts.

**Gate 7:** independently repeatable playable scenarios and a documented
build/install process.

---

## Architecture in one picture

```text
User-provided verified Xbox retail XBE + game files
                        |
              xboxrecomp x86 -> C
                        |
       guest ABI + endian-safe memory layer
                        |
         Native PowerPC code from Xbox 360 XDK
                        |
          Xbox 360 host compatibility layer
           /         |           |         \
        Kernel      Xenos       Audio     XInput
           \         |           |         /
                native default.xex
                        |
                 modified Xbox 360 console
```

The retained C **logic** is the starting point, not a guarantee that
Windows-hosted dependencies will work unmodified on Xenon.

## Developer navigation

- [Working upstream](https://github.com/KraftMacAndChee/Mercenaries-Recompiled)
  and upstream [architecture](ARCHITECTURE.md) / [code map](CODE_MAP.md).
- [Active Xbox 360 foundation PR](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/pull/1) —
  currently contains the experimental target; review before merging.
- [Xbox 360-specific working notes on the branch](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/blob/xbox360/bootstrap-guest-memory/ports/mercenaries/xbox360/README.md).
- [Hardware bootstrap on the branch](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/tree/xbox360/bootstrap-guest-memory/ports/mercenaries/xbox360/bootstrap_xex) and its [VS17/XDK build and safety checklist](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/blob/xbox360/bootstrap-guest-memory/ports/mercenaries/xbox360/bootstrap_xex/BUILD_FIRST_XEX.md).
- Upstream Windows build is **not** our Xbox 360 build:
  [`ports/mercenaries/scripts/Build-From-Iso.ps1`](ports/mercenaries/scripts/Build-From-Iso.ps1)
  compiles a Windows x64 game, not an XEX.

## Verified test evidence

| Date | Evidence | Status | Build / hardware |
| --- | --- | --- | --- |
| 2026-10-18 | Source inspection: Windows host and direct guest memory macros | Confirmed in source | No console run |
| 2026-10-18 | Little-endian memory and float tests: GCC 14.2.0, Clang 17.0.0, Clang UBSan | **PASS (3/3)** | Linux x86-64; branch blobs `289c8792`, `00149528`; no console run |
| 2026-10-18 | VS17 + Xbox 360 XDK diagnostic compile | **BUILD SUCCEEDED** | Xbox 360 toolchain |
| 2026-10-18 | First real-console bootstrap run: startup, repeated heartbeats, controller 0, A-button exit | **PASS** | modified Xbox 360; xbWatson; `[XAPI RETURN VALUE] 0` |
| 2026-10-18 | Independent 15-second safety-timeout run | **PASS** | modified Xbox 360; timeout log + `[XAPI RETURN VALUE] 0` |
| 2026-10-18 | Phase 2A bounded 64 MiB guest-RAM host contract | **PASS (GCC / Clang / ASan+UBSan)** | Linux x86-64; host preflight |
| 2026-10-18 | Phase 2A 64 MiB guest-RAM hardware diagnostic | **PASS** | Real Xbox 360 Xenon: big-endian host, LE guest bytes, unaligned access, high-bound rejection, clean timeout / XAPI 0 |
| 2026-10-18 | Phase 2B retail XBE parse + bounded section load | **PASS** | Real Xbox 360 Xenon: 3,223,552-byte XBE, Title ID 0x4C410015, entry 0x0022964A, 14/14 sections, 3,188,156 initialized bytes, XAPI 0 |
| 2026-10-18 | Phase 2C exact retail identity + post-load integrity | **PASS** | Real Xbox 360 Xenon: pinned SHA-256 exact match, exact build invariants, 14/14 section/source comparisons, zero-fill invariants, XAPI 0 |
| 2026-10-18 | Phase 2D checked guest-address router host contract | **PASS (GCC / Clang / ASan+UBSan)** | 64 MiB mirrors, KSEG alias coherence, synthetic-page priority, MMIO/thunk classification |
| 2026-10-18 | Phase 2D checked guest-address router hardware fixture | **PASS** | Real Xbox 360 Xenon: coherent RAM mirrors + KSEG0/KSEG1, synthetic-page priority, MMIO/thunk isolation, gap rejection, XAPI 0 |
| 2026-10-18 | Phase 2E guest execution-environment portable contract | **PASS (GCC / Clang / ASan+UBSan)** | TIB/KTHREAD/TLS negative-index math, 256 KiB guest stack, kernel-data mirror/KSEG coherence |
| 2026-10-18 | Phase 2E guest execution-environment hardware fixture | **PASS** | Modified Xbox 360: exact XBE reverify, TLS block 20 B, TIB→KTHREAD→TLS chain, negative TLS index, kernel-data aliases, guest stack PUSH/POP, XAPI 0 |

Add future evidence here: command, exact commit, hardware, compiler/toolchain,
log or artifact path, pass/fail and remaining questions. **Do not mark an
unexecuted test PASS.**

## Dated development log

### 2026-10-18 — Kickoff / route selected

- Chose **native PowerPC recompilation of existing C translation + an Xbox
  360-native platform runtime** rather than reimplementing gameplay or
  attempting a Windows executable conversion.
- Audited upstream architecture, CMake targets, native memory model,
  `recomp_types.h` and the translated-code interfaces.
- Opened [Draft PR #1](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/pull/1)
  to isolate portable guest endian helpers, tests, and Xbox 360 target notes.
- Added source for a minimal **non-game** XDK diagnostic with 15-second safety
  exit, heartbeat, A-button input and logging fallback.
- Ran the portable byte-order and unaligned-access test successfully under
  GCC 14.2, Clang 17, and Clang UBSan; confirmed exact Git blob identities.
- Corrected a test diagnostic newline and added
  [VS17/XDK XEX build instructions](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/blob/xbox360/bootstrap-guest-memory/ports/mercenaries/xbox360/bootstrap_xex/BUILD_FIRST_XEX.md).
- Replaced the nearly empty fork README with the **phase gates, checklists,
  blockers, test evidence and durable progression log**.
- **Phase 1 gate: COMPLETE. Next:** begin Phase 2 guest-memory integration and bounded retail-XBE section loading.
- **No playable XEX exists.** Phase 1 hardware success is not yet claimed.

- **Build environment decision:** use the user's existing **VS17 + Xbox 360 XDK**
  configuration instead of older Visual Studio setup. Updated the Phase 1
  build guide; no actual Xbox 360 compile or console test is claimed.

### 2026-10-18 — First Xbox 360 hardware execution succeeds

- The Phase 1 diagnostic **built successfully** in the user's working
  **VS17 + Xbox 360 XDK** environment and launched on the real console.
- xbWatson captured the complete diagnostic lifecycle: bootstrap start,
  repeated one-second heartbeats, controller 0 detection, A-button detection,
  clean diagnostic shutdown and **`[XAPI RETURN VALUE] 0`**.
- A second real-hardware run intentionally received no input. It logged the
  **15-second safety exit**, reported timeout as the exit reason, and returned
  **`[XAPI RETURN VALUE] 0`**.
- External codxe plugin-manager lines are intentionally ignored for this project;
  they come from a separately resident console plugin and are not part of the XEX.
- **Phase 1 is complete.**
- **Not yet proven:** guest memory, original-Xbox XBE loading, graphics/audio,
  or Mercenaries game code.
- **Next:** Phase 2 guest-memory arena, endian-correct access, address routing
  and bounded XBE-section loading.

### 2026-10-18 — Phase 2A guest-memory work starts

- Created branch `xbox360/phase2-guest-memory` from the completed Phase 1
  hardware branch.
- Added a bounded **64 MiB low guest-RAM arena** with explicit guest-address
  bounds checks and little-endian 8/16/32/64-bit + float accessors.
- Added a separate Phase 2 Xbox 360 diagnostic that measures native host byte
  order, allocates/clears the arena, tests XBE-base address `0x00010000`,
  unaligned operations, top-of-RAM accesses and out-of-range rejection.
- Host contract initially exposed warning-clean header linkage work; helpers
  were changed to inline and all access widths were added to the test.
- Final host result: **PASS** under GCC 14.2.0, Clang 17.0.0, and Clang
  AddressSanitizer + UndefinedBehaviorSanitizer.
- First VS17/XDK Phase 2A compile attempts: **FAIL (setup/include path)**. The
  actual compiler error was `C1083: Cannot open include file:
  '../include/guest_memory.h'`; all `MercGuestMemory`, `memory`, storage
  class and declaration errors were cascading parser errors.
- To remove this friction entirely, the Phase 2A hardware diagnostic is now a
  **single self-contained `main.cpp`** with the guest-memory/endian helpers
  embedded. No auxiliary headers or Additional Include Directories are needed.
- **Hardware result:** **PASS**. All Phase 2A memory checks succeeded on Xenon,
  followed by the 10-second timeout and clean XAPI return value 0.
- **Next:** Phase 2B — read a user-supplied supported retail `default.xbe`,
  validate its header/section table safely, and copy sections into the guest
  arena without executing them.

### 2026-10-18 — Phase 2A passes on real Xenon hardware

- Xbox 360 reports **BIG-ENDIAN**, exactly as required for the test.
- 64 MiB low guest arena allocation/zeroing passed.
- Original-Xbox little-endian byte representation passed at `0x00010000`.
- Aligned/unaligned 8/16/32/64-bit and float accesses passed.
- Last-valid-word/qword accesses passed.
- Crossing-bound, first-out-of-range and wrapped/high addresses were rejected.
- Guest arena freed successfully; post-test timeout completed and
  `[XAPI RETURN VALUE] 0` confirmed.
- **Phase 2A: COMPLETE.**
- **Next:** Phase 2B XBE header/section parsing and non-executing section load.

### 2026-10-18 — Phase 2B XBE loader prepared

- Created `xbox360/phase2b-xbe-loader` from the completed Phase 2A branch.
- Added a self-contained, non-executing Xbox 360 diagnostic that reads the
  user's own `game:\default.xbe`.
- Parser uses explicit little-endian reads on Xenon and mirrors the upstream
  XBE layout: base/header fields, certificate, 56-byte section headers,
  retail entry/thunk XOR decoding, and bounded section copies.
- The supported structural identifiers checked are Title ID `0x4C410015`,
  base `0x00010000`, decoded retail entry `0x0022964A`, and 14 sections.
- Entry-point execution is explicitly disabled.
- Pinned SHA-256 is documented but not yet calculated on-console; exact hash
  enforcement remains mandatory before guest game code is ever run.
- **Next:** compile Phase 2B in VS17/XDK, place the user's retail
  `default.xbe` beside the diagnostic `default.xex`, and capture all
  `[Merc360:P2B]` xbWatson output.

### 2026-10-18 — Phase 2B retail XBE load passes on hardware

- Read the user's own `game:\default.xbe` successfully on Xbox 360.
- XBE size: **3,223,552 bytes** (`0x00313000`).
- Parsed little-endian header correctly on big-endian Xenon:
  - base `0x00010000`
  - image size `0x00868AA0`
  - decoded retail entry `0x0022964A`
  - TLS VA `0x00302CB4`
  - decoded kernel thunk VA `0x002DBCE0`
  - **14 sections**
  - certificate Title ID `0x4C410015`
- Loaded **14/14** sections into the proven 64 MiB guest arena.
- Copied **3,188,156 initialized bytes** and zero-filled each virtual section.
- Decoded entry point landed inside a loaded section; kernel thunk VA remained
  inside guest RAM.
- Entry-point execution remained explicitly disabled.
- Guest arena was released, 10-second timeout completed, and
  `[XAPI RETURN VALUE] 0` confirmed.
- **Phase 2B: COMPLETE.**
- **Next:** Phase 2C exact SHA-256 enforcement and stronger post-load
  invariants before any translated guest code can execute.

### 2026-10-18 — Phase 2C exact-XBE verification prepared

- Created `xbox360/phase2c-verified-xbe` from the completed Phase 2B branch.
- Added a self-contained Xbox 360 diagnostic that computes SHA-256 over the
  user's complete retail XBE and requires the upstream pinned digest:
  `AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7`.
- Added exact supported-build invariants for file/header/image size, TLS VA,
  kernel thunk VA, title ID, entry point, section count and section order.
- Added post-load verification: full header byte comparison, per-section
  initialized-data `memcmp`, zero-fill-tail checks and virtual-overlap rejection.
- Entry-point execution remains disabled.
- SHA-256 implementation passed standard empty-string, `abc`, and quick-brown-
  fox vectors under GCC, Clang, and Clang ASan+UBSan.
- **Next:** build/run the Phase 2C XEX on the same Xbox 360 and capture the
  complete `[Merc360:P2C]` xbWatson trace.

### 2026-10-18 — First Phase 2C hardware run finds test-harness bug

- Exact on-console SHA-256 **PASS**:
  `AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7`.
- All exact file/header/image/entry/TLS/thunk/title checks passed.
- Header byte-for-byte guest copy passed.
- Section loads passed through section 10.
- Test stopped at real section 11 `$XTIMAGE` because the committed expected
  table accidentally contained `$XTIMAGE` / `$XSIMAGE` with one dollar.
- This was a **diagnostic bug, not an XBE mismatch**; the cryptographic hash had
  already proven the exact supported retail executable.
- Fixed expected names using explicit `\x24\x24` literals, corrected stale
  Phase 2B log labels, and added actual-vs-expected mismatch logging.
- **Phase 2C remains in progress.** Rebuild/run the corrected diagnostic.

### 2026-10-18 — Phase 2C rerun identified as stale binary

- The rerun still emitted the old Phase 2B start/end labels and the old generic
  section-name mismatch message, proving the console was still running an older
  Phase 2C XEX/source rather than the corrected section-name build.
- The XBE itself remains proven correct: exact pinned SHA-256 still PASS.
- Added runtime build tag `P2C-NAMEFIX-20261018-B` to the corrected source so
  future xbWatson output proves exactly which binary is executing.
- **Next:** clean/rebuild the VS17 project from the latest branch source and
  verify the build tag appears before evaluating section-name results.

### 2026-10-18 — Phase 2C exact-XBE + load-integrity gate passes

- Corrected build tag `P2C-NAMEFIX-20261018-B` appeared, proving the intended
  fixed XEX was running.
- Xbox 360 computed the complete retail XBE SHA-256 and matched the upstream
  pinned digest exactly:
  `AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7`.
- Exact file size, header size, image size, base, entry point, TLS VA, kernel
  thunk VA, Title ID, section count, names and order all passed.
- Complete XBE header copy compared byte-for-byte successfully.
- All **14/14 sections** loaded; **3,188,156 initialized bytes** copied.
- Every loaded initialized range matched its XBE source bytes and every
  virtual/BSS tail remained zero.
- Entry-point execution stayed disabled by design.
- Guest arena cleanup, post-test timeout and `[XAPI RETURN VALUE] 0` passed.
- **Phase 2C: COMPLETE.**
- **Next:** Phase 2D checked address routing, RAM mirrors/KSEG aliases and
  synthetic low/kernel-memory fixtures. No broad translated game execution yet.

### 2026-10-18 — Phase 2D checked address router prepared

- Created `xbox360/phase2d-address-router` from completed Phase 2C.
- Added a self-contained XDK diagnostic with build tag
  `P2D-ROUTER-20261018-A`.
- Router explicitly classifies primary/mirrored 64 MiB RAM, KSEG0/KSEG1,
  synthetic D3D fence/kernel pages, VRAM, synthetic kernel-thunk VAs,
  NV2A MMIO, MCPX APU MMIO, MCPX AC97 MMIO and unsupported gaps.
- RAM mirror/KSEG aliases resolve to the same 64 MiB backing store; synthetic
  kernel/fence pages intentionally override generic KSEG aliasing.
- MMIO and kernel-thunk routes deliberately expose **no ordinary RAM pointer**.
- Portable router contract: **PASS** under GCC, Clang, and Clang
  ASan+UBSan.
- **Next:** compile/run Phase 2D on real Xbox 360 and capture the complete
  `[Merc360:P2D]` trace. Game execution remains disabled.

### 2026-10-18 — Phase 2D checked address router passes on Xenon

- Runtime build tag `P2D-ROUTER-20261018-A` confirmed the intended XEX.
- Primary RAM, first/deep/final configured mirror windows all classified
  correctly.
- Mirror coherence passed in both directions, including the upstream fixture
  `0x20000448 == 0x00000448`.
- KSEG0 `0x81230000` and KSEG1 `0xA1230000` both coherently aliased
  low RAM `0x01230000`.
- Synthetic D3D fence `0x80000000` and fake kernel page `0x80010000`
  correctly overrode generic KSEG translation and remained distinct from low RAM.
- Last valid RAM dword was accepted; a crossing dword was rejected.
- VRAM, NV2A, synthetic kernel thunk, MCPX APU and AC97 regions classified
  separately; NV2A/APU/thunk routes exposed no ordinary RAM/data pointer.
- Unsupported pre/post-KSEG gaps and `0xFFFFFFFF` were rejected.
- Address backing released; timeout completed; `[XAPI RETURN VALUE] 0`.
- **Phase 2D: COMPLETE.**
- **Next:** Phase 2E guest stack + low TIB/KTHREAD/TLS + initial kernel-data
  fixtures through the checked router. Translated game execution stays disabled.

### 2026-10-18 — Phase 2E execution-environment fixture prepared

- Created `xbox360/phase2e-execution-environment` from completed Phase 2D.
- Reuses exact-XBE verification and the proven 14-section loader.
- Adds the current title-specific low-memory contract: synthetic TLS at
  `0x00700000`, synthetic KTHREAD at `0x00760000`, kernel data at
  `0x0087E000`, 256 KiB guest stack at `0x00880000-0x008BFFFF`,
  initial guest ESP `0x008BFFF0`, and heap base `0x008C0000`.
- Derives the retail TLS payload from the loaded XBE and validates the negative
  TLS-index equation through `fs:[4]`.
- Initializes TIB/KTHREAD/TLS plus initial XboxHardwareInfo,
  XboxKrnlVersion 1.0.5849.0 and KeTickCount fixtures.
- Tests kernel-data coherence through a RAM mirror and KSEG0.
- Tests one guest PUSH32/POP32 round-trip using Xbox-visible stack RAM only.
- Portable contract: **PASS** under GCC 14.2, Clang 17 and Clang ASan+UBSan.
- Runtime build tag: `P2E-ENV-20261018-A`.
- **Next:** build/run Phase 2E on modified Xbox 360 hardware. Translated
  Mercenaries game execution remains disabled.

### 2026-10-18 — Phase 2E passes; Gate 2 complete

- Runtime build tag `P2E-ENV-20261018-A` confirmed the intended binary.
- Exact supported XBE SHA-256 and all 14-section load invariants re-passed.
- Loaded-image high-water VA: `0x00878A88`; kernel-data page and 256 KiB
  guest stack were verified non-overlapping.
- Retail TLS directory on hardware resolved to:
  - raw start/end `0x00000000`
  - TLS index `0x00869118`
  - callbacks `0`
  - zero-fill `8` bytes
  - characteristics `0`
- Synthetic TLS block size was **20 bytes** at `0x00700000`.
- TIB → KTHREAD → TLS chain passed, including
  `fs:[4] + signed_tls_index*4 == 0x00700000`.
- XboxHardwareInfo, XboxKrnlVersion 1.0.5849.0 and KeTickCount fixtures passed.
- Kernel-data coherence passed through a RAM mirror and KSEG0.
- Guest PUSH32/POP32 round-trip at initial ESP `0x008BFFF0` passed.
- Cleanup/timeout completed with `[XAPI RETURN VALUE] 0`.
- **Phase 2E: COMPLETE. Gate 2: PASS. Phase 2 is complete.**
- Generated assignable `MEM16/32/64` lvalues now move to Phase 3 where they
  belong: maintained translator/lifter changes plus real XDK instruction
  fixtures before any bounded translated Mercenaries function executes.

### 2026-10-18 — Phase 3A scalar generated-memory ABI prepared

- Created `xbox360/phase3a-scalar-memory-abi` from completed Phase 2E.
- Audited the maintained lifter rather than editing disposable generated C.
- Scalar integer memory operands are centralized through
  `_fmt_mem_read()` / `_fmt_mem_write()`; Phase 3A adds an opt-in explicit
  mode while preserving legacy PC output by default.
- Explicit output shape:
  `GUEST_WRITE32(addr, GUEST_READ32(addr) + value)` instead of assignable
  native-pointer `MEM32(addr)` lvalues.
- Added runtime ABI declarations for
  `recomp_guest_read/write8/16/32/64`.
- Added generator regression coverage for legacy and explicit modes plus a
  scalar RMW emission.
- Added self-contained XDK fixture tagged `P3A-SCALAR-20261018-A` covering
  generated-style MOV/RMW, unaligned 8/16/64-bit access, CMPXCHG-style paths,
  mirror/KSEG coherence, PUSH source evaluation order, POP restoration and
  rejection of MMIO/cross-window accesses.
- **Next:** compile/run Phase 3A on modified Xbox 360 hardware. No translated
  Mercenaries function executes yet.

### 2026-10-18 — Phase 3A explicit scalar memory ABI passes on Xenon

- Runtime build tag `P3A-SCALAR-20261018-A` confirmed the intended XEX.
- Xenon big-endian host-order probe passed.
- Explicit generated-style 32-bit MOV round-trip passed with little-endian
  guest byte layout.
- Explicit 32-bit ADD RMW, unaligned 16-bit RMW, 8-bit XOR RMW and unaligned
  64-bit access all passed.
- 64-bit guest byte layout was verified little-endian.
- Explicit helpers remained coherent through RAM mirrors, KSEG0 and KSEG1.
- CMPXCHG-style equal and mismatch paths both passed.
- PUSH source evaluation happened before ESP decrement; POP restored value/ESP.
- NV2A MMIO and a cross-64MiB dword access were correctly rejected as RAM.
- Guest RAM released, timeout completed, and `[XAPI RETURN VALUE] 0`.
- **Phase 3A: COMPLETE.**
- **Next:** migrate the remaining non-scalar memory paths, beginning with
  x87/float/double and signed-memory helpers before SSE/MMX/string helpers.

### 2026-10-18 — Phase 3B signed/x87 memory ABI prepared

- Created `xbox360/phase3b-x87-memory-abi` from completed Phase 3A.
- Explicit ABI now includes signed scalar reads and IEEE-754 float/double
  guest reads/writes.
- Maintained lifter migration now covers MOVSX and x87 memory paths including
  FILD/FIST, integer-memory x87 arithmetic, FLD/FST, float/double arithmetic
  memory operands and x87 memory comparisons.
- Legacy PC output remains the default unless explicit guest-memory mode is
  enabled.
- Added generator regression coverage for legacy vs explicit signed/x87 output.
- Added self-contained XDK fixture tagged `P3B-X87MEM-20261018-A`.
- **Next:** build/run Phase 3B on modified Xbox 360 hardware. SSE/XMM, MMX and
  REP/string/manual legacy-memory paths remain later Phase 3 slices.

### 2026-10-18 — Phase 3B signed/x87 memory ABI passes on Xenon

- Runtime build tag `P3B-X87MEM-20261018-A` confirmed the intended XEX.
- Signed 8/16/32/64-bit guest reads and sign extension passed, including
  unaligned 16/32/64-bit accesses.
- Float32/float64 round-trips passed with exact little-endian IEEE-754 bytes.
- FILD-style signed integer load and FIADD-style signed memory arithmetic passed.
- FLD/FADD/FSTP-style explicit floating memory path passed.
- FIST-style explicit integer destination write passed.
- FCOM-style memory operand comparison passed.
- Float32 RAM-mirror and float64 KSEG0 coherence passed.
- Float32 MMIO rejection and float64 cross-64MiB rejection passed.
- Guest RAM released, timeout completed, and `[XAPI RETURN VALUE] 0`.
- **Phase 3B: COMPLETE.**
- **Next:** Phase 3C SSE/XMM + MMX guest-memory helpers, still without
  translated Mercenaries function execution.

### 2026-10-18 — Phase 3C SSE/XMM + MMX memory ABI prepared

- Created `xbox360/phase3c-sse-mmx-memory-abi` from completed Phase 3B.
- MMX memory operands now use explicit 64-bit guest reads/writes in explicit mode.
- Scalar SSE memory operands route through explicit float/double helpers.
- Packed XMM runtime helpers gain an explicit-memory branch selected by
  `RECOMP_EXPLICIT_GUEST_MEMORY_ABI`.
- Full XMM transfers use a checked 128-bit guest operation; low/high 64-bit
  moves use one checked 64-bit guest operation. This prevents SIMD accesses at
  a 64 MiB boundary from wrapping lane-by-lane into a mirror window.
- Added generator regression coverage for MOVQ/MMX, MOVSS/ADDSS/ADDSD and
  packed XMM helper emission.
- Added self-contained XDK fixture tagged `P3C-SIMD-20261018-A` covering
  packed lane reconstruction, raw-bit moves, MMX payloads, arithmetic/bitwise
  memory operands, alias coherence and boundary/MMIO rejection.
- Shared PUSH/POP macros, REP/string helpers and remaining manual legacy
  memory sites are explicitly deferred to the next cleanup slice.
- **Next:** build/run Phase 3C on modified Xbox 360 hardware.

### 2026-10-18 — Phase 3C SSE/XMM + MMX memory ABI passes on Xenon

- Runtime build tag `P3C-SIMD-20261018-A` confirmed the intended XEX.
- Unaligned 128-bit XMM load reconstructed all four float lanes correctly.
- 128-bit XMM store preserved raw lane bits and lane order.
- MOVSS low-lane load + upper-lane zeroing passed.
- MOVSD raw low-64 load/store preservation passed.
- MOVLPS/MOVHPS low/high lane replacement and raw stores passed.
- ADDPS-style packed memory arithmetic and XORPS-style raw lane-bit behavior passed.
- MMX MOVQ/PAND-style 64-bit memory paths passed.
- 128-bit XMM mirror coherence and MMX-width KSEG0 coherence passed.
- Checked 128-bit and 64-bit transfers rejected cross-64MiB accesses.
- 128-bit XMM helper rejected NV2A MMIO as ordinary RAM.
- `PHASE 3C SIMD MEMORY ABI RESULT: PASS` was observed on hardware.
- The pasted trace ended during the post-test heartbeat tail, so no unshown
  final XAPI return value is recorded here.
- **Phase 3C: COMPLETE.**
- **Next:** Phase 3D shared PUSH/POP, REP/string helpers, XBOX_MEMCPY and
  remaining maintained/manual legacy `MEM*` sites before first bounded
  translated-function execution.

### 2026-10-18 — Phase 3D explicit runtime/string cleanup prepared

- Created `xbox360/phase3d-explicit-runtime-cleanup` from completed Phase 3C.
- Added real recompiler CLI switch `--explicit-guest-memory`.
- Generated C now defines `RECOMP_EXPLICIT_GUEST_MEMORY_ABI` automatically
  when that mode is selected, keeping lifter/runtime ABI selection in sync.
- Shared `PUSH32/POP32`, `XBOX_MEMCPY`, `XBOX_REP_MOVS` and runtime
  checkpoint reads route through the explicit guest-memory bridge.
- String lifting now covers MOVS/STOS/LODS plus REP MOVS/STOS/CMPS/SCAS without
  native guest-pointer dereferences in explicit mode.
- Normal PC generation preserves the historical default path, including the
  forward REP STOSB memset fast path.
- Per-function explicit translation now hard-fails on executable legacy
  `MEM*`, `SMEM*`, `MEMF/MEMD` or `XBOX_PTR` accesses.
- Added post-patch scanner
  `tools.recomp.audit_explicit_guest_memory` so generated patch scripts cannot
  silently reintroduce unsafe host-lvalue memory after translation.
- Corrected SIMD/string boundary semantics: one scalar/SIMD access is checked
  as a whole width; string/copy instructions remain sequences of individual
  x86 accesses and may advance into a mapped mirror.
- Added self-contained XDK fixture tagged `P3D-RUNTIME-20261018-A`.
- **Next:** build/run Phase 3D on modified Xbox 360 hardware. A PASS makes the
  next gate the first small audited translated Mercenaries function.

### 2026-10-18 — Phase 3D explicit runtime/string memory ABI passes on Xenon

- The earlier lack of visible output was an xbWatson connectivity/visibility
  issue, not a Phase 3D software failure.
- Tested runtime build tag: `P3D-RUNTIME-20261018-A`.
- Shared PUSH32 old-ESP evaluation and POP32 restoration passed.
- XBOX_MEMCPY passed aligned dword+tail and unaligned raw-byte copies.
- REP MOVSB forward and overlapping x86-order behavior passed.
- REP MOVSW/MOVSD preserved unaligned element semantics.
- Generated-style MOVSD, STOSW, LODSB, REP STOSD and backwards REP MOVSD passed.
- CMPSW/SCASB explicit memory comparison paths passed.
- Runtime bridge remained coherent through RAM mirrors and KSEG0.
- One scalar dword crossing a 64 MiB window was rejected.
- XBOX_MEMCPY correctly advanced element-wise into the next mapped RAM mirror.
- XBOX_REP_MOVS rejected NV2A MMIO as ordinary RAM.
- `PHASE 3D RUNTIME MEMORY ABI RESULT: PASS` observed on modified Xbox 360.
- **Phase 3D: COMPLETE.**
- **Next:** first small audited mechanically translated Mercenaries function,
  generated with `--explicit-guest-memory`, compiled into a bounded XDK harness
  and compared against a reference result before broader translated execution.

### How future updates are recorded

Every substantive development change should update this README's **live table,
checklist, evidence and dated log** in the same pull request/commit. A brief
chat recap should match what is committed. If a test fails, log the failure,
do not silently reset a checklist. Preserve reproducible logs and keep branch
work isolated until the milestone is reviewable.

## Credits and licensing

Original Mercenaries recompilation: **Trenton Turner (KraftMacAndChee)**,
building upon sp00nz's xboxrecomp and the work of Xbox reverse engineering,
emulation and modding communities. See [upstream LICENSE](LICENSE),
[dependency notices](docs/dependencies.md) and component source headers.
*Mercenaries: Playground of Destruction* and its assets remain the property of
their respective owners. This is an unofficial fan project.
