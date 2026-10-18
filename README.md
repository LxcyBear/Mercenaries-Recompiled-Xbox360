# Mercenaries Recompiled — Xbox 360 Edition

> **Experimental native Xbox 360 port · Not playable yet**
>
> **Platform:** RGH/JTAG Xbox 360 · Xenon PowerPC · Xbox 360 XDK / VS17 · native `default.xex`
>
> **Last roadmap review:** October 18, 2026 · **Current focus:** Phase 0 audit + Phase 2 guest-address routing after completing Phase 2C exact-XBE verification.
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
| **2 — Guest memory + retail XBE loading** | **In progress — Phase 2A/2B/2C COMPLETE on Xenon; address routing next** | Correct Xbox guest bytes/addresses, section loading, aliases, MMIO fixture PASS |
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
- [x] Launch from a new isolated folder; real RGH/JTAG hardware execution confirmed October 18, 2026.
- [x] Confirm debug output: xbWatson captured `[Merc360]` startup, heartbeat, controller and shutdown messages.
- [x] Confirm 1-second heartbeats and controller 0 detection on real hardware.
- [x] Confirm A-button exit and clean XAPI return value 0.
- [x] Confirm the independent 15-second automatic timeout in a separate run; clean `[XAPI RETURN VALUE] 0` verified.
- [ ] Record console model, kernel, build flavor, XEX size, debugger/xbWatson
      transcript and any failed test cases.
- [ ] Add a small probe for CPU endian, available memory, file access,
      high-resolution timing and allocation failures.

**Gate 1:** real RGH/JTAG hardware produces consistent startup, log, input
and shutdown evidence. A black screen from this diagnostic is expected;
**it has no renderer**.

### Phase 2 — Original Xbox guest memory / XBE sections

**Purpose:** safely reproduce original Xbox 32-bit guest addresses in
Xbox 360 native memory.

- [x] Implement a bounded 64 MiB low guest-RAM arena and host contract test on
      the `xbox360/phase2-guest-memory` branch. GCC 14.2, Clang 17 and
      Clang ASan+UBSan all PASS; real Xenon allocation is still pending.
- [ ] Implement checked guest VA routing: RAM, mirrors, aliases, synthetic
      kernel area and GPU/APU MMIO regions.
- [x] Implement explicit endian-correct, alignment-safe guest 8/16/32/64-bit
      and float reads/writes for the bounded low-RAM arena; host tests PASS.
- [x] Verify those accessors on real Xenon hardware: **Phase 2A PASS**. Xenon reported big-endian host order; every low/high/unaligned/endian/bounds test passed and the XEX returned 0.
- [ ] Replace direct native pointer semantics with explicit checked access;
      reject unsupported regions instead of corrupting unrelated memory.
- [x] Load the exact supported retail XBE on Xenon: on-console SHA-256 matched
      the pinned digest, 14/14 sections loaded, initialized bytes matched the
      source, and every virtual/BSS tail remained zero. Stack/heap initialization
      remains a later Phase 2 item.
- [ ] Compare original-Xbox guest memory fixtures and address alias behavior.
- [ ] Stress-test fragmentation and low-memory paths.
- [x] Host-test upper-bound crossing, first-out-of-range and wrapped/high
      addresses; all are rejected without sanitizer findings.

**Gate 2:** exact guest byte/alias/section fixtures PASS on a real Xbox 360.

### Phase 3 — PowerPC-safe generated C and execution ABI

**Purpose:** preserve guest x86 instruction behavior even though host code
executes as Xbox 360 PowerPC.

- [ ] Audit translated instruction helpers for x86-only intrinsics,
      compiler extensions, native-endian casts, 32/64-bit assumptions and
      Windows/MSVC-specific code.
- [ ] Update **maintained translator / lifter / patch generator**, not
      disposable `ports/mercenaries/src/recomp/gen` files, for explicit
      endian-safe guest reads/writes/RMW.
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
                 RGH/JTAG console
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
| 2026-10-18 | First real-console bootstrap run: startup, repeated heartbeats, controller 0, A-button exit | **PASS** | RGH/JTAG Xbox 360; xbWatson; `[XAPI RETURN VALUE] 0` |
| 2026-10-18 | Independent 15-second safety-timeout run | **PASS** | RGH/JTAG Xbox 360; timeout log + `[XAPI RETURN VALUE] 0` |
| 2026-10-18 | Phase 2A bounded 64 MiB guest-RAM host contract | **PASS (GCC / Clang / ASan+UBSan)** | Linux x86-64; host preflight |
| 2026-10-18 | Phase 2A 64 MiB guest-RAM hardware diagnostic | **PASS** | Real Xbox 360 Xenon: big-endian host, LE guest bytes, unaligned access, high-bound rejection, clean timeout / XAPI 0 |
| 2026-10-18 | Phase 2B retail XBE parse + bounded section load | **PASS** | Real Xbox 360 Xenon: 3,223,552-byte XBE, Title ID 0x4C410015, entry 0x0022964A, 14/14 sections, 3,188,156 initialized bytes, XAPI 0 |
| 2026-10-18 | Phase 2C exact retail identity + post-load integrity | **PASS** | Real Xbox 360 Xenon: pinned SHA-256 exact match, exact build invariants, 14/14 section/source comparisons, zero-fill invariants, XAPI 0 |

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
