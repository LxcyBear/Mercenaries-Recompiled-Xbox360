# Mercenaries Recompiled — Xbox 360 Edition

> **Experimental native Xbox 360 port · Not playable yet**
>
> **Platform:** modified Xbox 360 · Xenon PowerPC · Xbox 360 XDK / VS17 · native `default.xex`
>
> **Last roadmap review:** October 21, 2026 · **Current focus:** Phase 6 — Native Xbox 360 graphics (Xenos). Phase 5 is 100% COMPLETE: 5BV passed 3/3 frozen-pack hardware repeatability and the mandatory exit reconnaissance reported `READY / PASS`, classifying `0x0014CD30` as exact generated title code and producing the complete Phase-6 handoff.
>
> **Active development:** [Phase 6 — native Xenos graphics](https://github.com/LxcyBear/Mercenaries-Recompiled-Xbox360/tree/xbox360/phase6-native-graphics). Phase 5 is frozen on its completed hardware-proven branch; `master` keeps the public roadmap/status current until reviewed work is merged.

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
| **3 — PPC recompilation + x86 guest ABI** | **COMPLETE — Gate 3 / 3N-B PASS on modified Xbox 360 hardware** | 128-function audited translated-code scale pack, loaded-XEX anchors, x87 checks and six independent-reference retail-function runs PASS |
| **4 — Native platform + kernel services** | **COMPLETE — Gate 4 / Phase 4C-AF PASS on modified Xbox 360 hardware** | Real retail-derived translated startup executes through the migrated Xenon service layer with deterministic hardware checkpoints |
| **5 — Subsystem bring-up under native game execution** | **COMPLETE — repeatability 3/3 PASS + exit reconnaissance READY/PASS** | Stable translated/runtime path, classified endpoint, subsystem inventory, first-touch baseline, risk map and ordered Phase-6 handoff |
| **6 — Native Xbox 360 graphics (Xenos)** | **IN PROGRESS — inventory complete; backend abstraction cleanup / first Xenos surface next** | Repeatable native Xenos first frame, functional title/menu graphics and reproducible 3D scene |
| 7 — Audio, movies, input and streaming integration | Not started | Functional startup media/menu audio/input with stable timing and storage streaming |
| 8 — Gameplay and compatibility hardening | Not started | Repeated playable scenarios, save/load, mission progression and documented compatibility |

**Verified foundation:** the VS17/XDK bootstrap, 64 MiB guest RAM contract,
exact retail-XBE identity, bounded 14-section load, and the full Phase 3
PowerPC-safe recompiler ABI path have passed on real Xbox 360 hardware. Phase
3N-B closed Gate 3 with a 128-function audited translated-code scale pack,
loaded-XEX anchor checks, maintained x87 rounding/exception checks and six
independent-reference executions of retail function `0x00208F30`, all with
clean XAPI return. Phase 4A then locked the exact 111-import guest-kernel/ABI
surface. Phase 4B is now complete: timing/sync, file/handle and
memory/protection slices all passed real-Xenon hardware gates plus runtime
verification, closing the original 17-path semantic host surface at
**0 direct host-backed / 15 platform-bound / 2 guest-native**. Phase 4C then
executed the real retail startup path on hardware through 23 translated
entries, including live thread/TLS/kernel/VM continuations, and reached
ordinal 202 `NtOpenFile` with `fault=0`, closing Gate 4.

**Present blockers:** Phase 5 is complete. The same frozen
`P5BV-REPEATABILITY-20261021-A` XEX reproduced the exact
`DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30` endpoint and counters
on three consecutive real-hardware boots with `fault=0`, guest-arena release,
proof end and XAPI return 0. The mandatory exit reconnaissance then reported
`READY / PASS`, classified `0x0014CD30` as exact generated title code in
`recomp_0006.c` (original range `0x0014CD30-0x0014CD9C`), inventoried the
five required subsystem families, ranked six Phase-6 risks and generated all
five handoff artifacts. The active blocker is now Phase 6 implementation:
isolate the remaining D3D11/DXGI-specific backend assumptions and bring up the
first independent Xbox 360/Xenos render surface without regressing the frozen
Phase-5 runtime baseline.

### Immediate next tests

1. **Done:** native XEX bootstrap, input, heartbeat and clean timeout.
2. **Done:** guest RAM, exact retail XBE loading, aliases and execution-environment fixtures.
3. **Done:** explicit scalar, signed/x87, SSE/XMM/MMX and runtime/string memory ABI fixtures on Xenon.
4. **Done:** generate reviewed retail function `0x00208F30` locally with
   `--explicit-guest-memory`; reject unexpected calls/writes/legacy lvalues.
5. **Done:** compile the generated function into the bounded Phase 3E XDK
   harness and match all six controlled inputs against the independent
   `(byte & 1)` reference on modified Xbox 360 hardware.
6. **Done:** execute real translated direct CALL, tail-call and nonzero
   function-pointer ICALL paths on modified Xbox 360 hardware.
7. **Done:** run the Phase 3I five-stage composite translated slice in one persistent
   guest arena; repeated-run trace/state/full-RAM checkpoint equality passed.
8. **Done:** Phase 3N/3N-B full generated-tree audit and 128-function translated
   scale gate passed on real Xbox 360 hardware; Gate 3 is complete.
9. **Done:** Phase 4A locked the exact 111-import guest kernel surface and ABI
   metadata with 17 semantic host-backed callable paths at baseline.
10. **Done:** Phase 4B-A/A2 and 4B-B/B2 hardware + runtime verification migrated
    15 service paths to native-ready platform boundaries; current audit is
    `host_surface=2`, `platform_bound=15`.
11. **Hardware PASS:** Phase 4B-C build `P4B-MEMPROT-20261019-B` passed
    tracked release/reuse, per-page protection, decommit/recommit, zero-init,
    bounds and stale-release checks on real Xbox 360 hardware.
12. **Done:** Phase 4B-C2 passed at `host_surface=0`,
    `platform_bound=15`, `guest_native=2`, with ABI/fallback, timing,
    file/handle and all six guest-memory ownership regressions green. Phase 4B
    service migration is complete.
13. **Done:** Phase 4C-A resolved retail entry `0x0022964A` exactly to
    `xbe_entry_point` and proved a complete direct closure of 40 translated
    bodies, depth 8, 5,918 guest bytes and 111,376 generated-source bytes, with
    0 missing direct dependencies and 14 dynamic/indirect-boundary bodies.
14. **Done:** Phase 4C-B executed the genuine translated `xbe_entry_point`
    on real Xbox 360 hardware and reached the first live dynamic boundary with
    `fault=0`: caller `0x0022B4D7`, target `0x800000FF`.
    That target is kernel ordinal 255, `PsCreateSystemThreadEx`; the observed
    44-byte frame exactly matches ten arguments plus the synthetic return slot.
15. **Done:** Phase 4C-C captured the live ordinal-255 frame on real Xbox 360
    hardware: StartRoutine `0x0022B43F`, ctx1 `0x002295D6`, ctx2
    `0x00000000`, exact 44-byte frame, `fault=0`.
16. **Done:** Phase 4C-D proved the hardware-observed StartRoutine
    `0x0022B43F` is an exact translated function with a six-body direct
    closure, depth 2, 460 guest bytes, 8,556 generated-source bytes,
    0 missing direct translated dependencies and 5 dynamic-boundary bodies.
17. **Done:** Phase 4C-E executed the 43-body continuous startup slice on real
    Xbox 360 hardware and advanced into the title thread to caller
    `0x0022B363` -> target `0x80000115`, with `fault=0`.
    Target `0x80000115` is kernel ordinal 277,
    `RtlEnterCriticalSection`; the observed 8-byte frame exactly matches one
    argument plus the synthetic CALL return.
18. **Done:** Phase 4C-F continued through ordinal 277
    `RtlEnterCriticalSection` on real hardware with live guest critical
    section `0x00312FC0`, exact 8-byte frame, balanced stack and `fault=0`.
    The next target is `0x80000126` = ordinal 294,
    `RtlLeaveCriticalSection`.
19. **Done:** Phase 4C-G executed the full ordinal 277/294 enter/leave pair on
    real Xbox 360 hardware with balanced 8-byte frames and `fault=0`.
    The next live ICALL target is `0x002295D6`, exactly matching the ctx1
    value captured from `PsCreateSystemThreadEx`; hardware has therefore
    confirmed ctx1 as executable title-startup code.
20. **Phase 4C-H:** real Xbox 360 hardware entered callback `0x002295D6`
    and reached translated function `0x0022C4DF`, then stopped on a
    deterministic `GUEST_FAULT` observed at translated VA `0x0022C4FF`.
    The stack remained balanced; this gate is blocked, not passed.
21. **Done:** Phase 4C-I Build B captured the first rejected guest access on
    real Xbox 360 hardware: READ32 `0x80000142` from translated caller
    `0x0022C4DF`. Ordinal `0x142` = decimal 322 =
    `XboxHardwareInfo`, a guest-visible DATA export.
22. **Done:** Phase 4C-J relocated ordinal 322 `XboxHardwareInfo` at live
    thunk slot `0x002DBE0C`; real hardware advanced past the old fault.
    The next rejected access is READ16 `0x80000148` with
    `ECX=0x80000144`, identifying ordinal 324 `XboxKrnlVersion` plus
    offset 4 (the Build field).
23. **Done:** Phase 4C-K relocated initialized startup DATA imports 156/322/324
    on real hardware. The callback advanced with `fault=0` to
    `DIRECT_FRONTIER caller=0x0022C4DF target=0x0022C47B`.
24. **Done:** Phase 4C-L promoted `0x0022C47B`; real hardware executed it
    and exposed READ32 `0x8001003C` from that function with a balanced stack.
25. **Done:** Phase 4C-M modeled the fenced xboxkrnl PE-header page; hardware
    advanced through `0x0022C47B` into `0x0022C28B`, then stopped at
    `ICALL_SAFE 0x8000002F` with `fault=0` and a 12-byte frame.
26. **Done:** Phase 4C-N validated the live ordinal-47 frame
    (`registration=0x003134C0`, Register=1), matched production no-callback
    semantics, and resumed translated startup with `fault=0` to
    `DIRECT_FRONTIER 0x0022F128`.
27. **Done:** Phase 4C-O promoted `0x0022F128`; real hardware executed it
    and reached `ICALL_SAFE 0x8000006B` with `fault=0` and a 16-byte frame.
28. **Done:** Phase 4C-P validated and executed live ordinal 107
    `KeInitializeDpc` with DPC `0x00869580`, routine `0x0022F116`,
    context 0; startup advanced with `fault=0` to `ICALL_SAFE 0x80000071`.
29. **Done:** Phase 4C-Q validated and executed live ordinal 113
    `KeInitializeTimerEx`; the Q main/env cookie matched and startup advanced
    with `fault=0` to `DIRECT_FRONTIER 0x0022C5A4`.
30. **Done:** Phase 4C-R promoted and executed `0x0022C5A4`; the R main/env
    cookie matched and startup advanced with `fault=0` to
    `DIRECT_FRONTIER caller=0x0022C5A4 target=0x00230060`.
31. **Done:** Phase 4C-S promoted and executed `0x00230060`; the S main/env
    cookie matched and startup advanced with `fault=0` to
    `ITAIL caller=0x00230060 target=0x80000018`.
32. **Done:** Phase 4C-T validated and continued ordinal 24
    `ExQueryNonVolatileSetting`; the live frame was `XC_MISC` with a 4-byte
    value buffer, returned STATUS_SUCCESS, and startup advanced with `fault=0`
    to `ICALL_SAFE caller=0x00230060 target=0x8000012D`.
33. **Done:** Phase 4C-U validated and continued ordinal 301
    `RtlNtStatusToDosError`; STATUS_SUCCESS mapped to DOS error 0 with the
    expected 8-byte frame, and startup advanced with `fault=0` to
    `DIRECT_FRONTIER caller=0x00230060 target=0x0022F0FB`.
34. **Done:** Phase 4C-V executed the bounded direct closure rooted at
    `0x0022F0FB`; the live path advanced with `fault=0` to
    `ICALL_SAFE caller=0x0022F0FB target=0x80000095`.
35. **Done:** Phase 4C-W validated and continued ordinal 149 `KeSetTimer`;
    the expected 20-byte full frame armed KTIMER `0x008695A0` with DPC
    `0x00869580`, returned prior-active FALSE, and startup advanced with
    `fault=0` to `DIRECT_FRONTIER caller=0x0022F0FB target=0x0022D980`.
36. **Done:** Phase 4C-X executed translated root `0x0022D980`; startup
    re-entered `0x00239BE8` and advanced with `fault=0` to
    `DIRECT_FRONTIER caller=0x00239BE8 target=0x00238C00`.
37. **Done:** Phase 4C-Y executed translated root `0x00238C00` with the
    maintained CRT memmove helper; startup advanced with `fault=0` to
    `ICALL_SAFE target=0x800000B8`, ordinal 184 `NtAllocateVirtualMemory`.
38. **Done:** Phase 4C-Z validated ordinal 184 and captured the live 1 MiB
    `MEM_RESERVE` / `PAGE_READWRITE` request with `fault=0`.
39. **Done:** Phase 4C-AA reserved 1 MiB at `0x03F00000`, committed the
    first 4 KiB at the same VA, and advanced with `fault=0` to
    `ICALL_SAFE target=0x80000123`.
40. **Done:** Phase 4C-AB continued ordinal 291
    `RtlInitializeCriticalSection` and advanced with `fault=0` to
    `DIRECT_FRONTIER target=0x0022D431`.
41. **Done:** Phase 4C-AC executed translated root `0x0022D431` and
    advanced with `fault=0` to `DIRECT_FRONTIER target=0x0022CA2B`.
42. **Done:** Phase 4C-AD executed translated root `0x0022CA2B` and
    advanced with `fault=0` to `DIRECT_FRONTIER target=0x0022C8EA`.
43. **Done:** Phase 4C-AE executed translated root `0x0022C8EA` and
    advanced with `fault=0` to `DIRECT_FRONTIER target=0x0022CEEE`.
44. **Done:** Phase 4C-AF executed `0x0022CEEE`, then flowed through
    `0x00239C23`, `0x0022C27A`, and `0x0022BD2D` before reaching
    `ICALL_SAFE target=0x800000CA` with a 23-entry trace and `fault=0`.
    Target `0x800000CA` is ordinal 202 `NtOpenFile`; its observed
    28-byte full frame matches six stdcall arguments plus the synthetic return.
    **Phase 4 / Gate 4 is complete.**
45. **Done:** Phase 5A captured ordinal 202 `NtOpenFile` on hardware with
    `path=\\Device\\Harddisk0\\partition1\\`, access `0x00100001`, share
    `0x3`, options `0x00800021`, exact 28-byte frame and `fault=0`.
46. **Done:** Phase 5B mapped `\\Device\\Harddisk0\\partition1\\` to
    `game:\\merc360-partition1`, returned STATUS_SUCCESS and tagged guest
    handle `0x48000001`, then resumed to `ICALL_SAFE target=0x800000DA`
    (`NtQueryVolumeInformationFile`) with `fault=0`.
47. **Done:** Phase 5C serviced `NtQueryVolumeInformationFile` class 3 with
    native-backed free/total space, then successfully closed token `0x48000001`
    through ordinal 187 `NtClose`. The next live boundary is
    `0x80000043` = ordinal 67 `IoCreateSymbolicLink`, with `fault=0`.
48. **Done:** Phase 5D handled ordinal 67 `IoCreateSymbolicLink` on hardware,
    creating `\\??\\D: -> \\Device\\CdRom0` with STATUS_SUCCESS, then
    advanced with `fault=0` to `DIRECT_FRONTIER target=0x0022C1C0`.
49. **Done:** Phase 5E executed translated root `0x0022C1C0` with the full
    native storage + symbolic-link stack intact and advanced with `fault=0` to
    `DIRECT_FRONTIER target=0x002370B8`; the trace reached 24 translated entries.
50. **Done:** Phase 5F executed translated root `0x002370B8`, expanded the
    live translated trace from 24 to 45 entries through already-packed retail
    initialization helpers, and reached `DIRECT_FRONTIER target=0x0022BE8C`
    from caller `0x0023A3CE` with `fault=0`.
51. **Done:** Phase 5G executed translated root `0x0022BE8C` with the full
    native storage/mount stack intact and reached `ICALL_SAFE target=0x800000BE`
    (ordinal 190 `NtCreateFile`) with a 46-entry trace and `fault=0`.
52. **Done:** Phase 5H serviced ordinal 190 `NtCreateFile` for
    `\\Device\\Harddisk0\\partition1\\TDATA` using `FILE_OPEN_IF`,
    returned STATUS_SUCCESS, closed the tagged handle, and reached ordinal 289
    `RtlInitAnsiString` with `fault=0`.
53. **Done:** Phase 5I initialized the live title-id ANSI strings, created
    `TDATA\\4c410015` and `UDATA\\4c410015`, mounted
    `\\??\\T: -> \\Device\\Harddisk0\\partition1\\TDATA\\4c410015`,
    and advanced with `fault=0` to `DIRECT_FRONTIER target=0x0022F026`.
54. **Done:** Phase 5J executed translated root `0x0022F026`, initialized
    `$XTINFO` and `.text` ANSI strings, and reached ordinal 279
    `RtlEqualString` at `0x80000117` with a 48-entry trace and `fault=0`.
55. **Done:** Phase 5K compared `$XTINFO` against every loaded XBE section
    name using maintained ordinal 279 `RtlEqualString` semantics, correctly
    found no match, and reached `DIRECT_FRONTIER target=0x0022B178` with
    `fault=0`.
56. **Done:** Phase 5L and the subsequent hardware-driven Phase 5
    continuations advanced beyond maintained `SetLastError` through native
    TitleMeta/TitleImage/SaveImage information/write handling, persistent title
    state, and translated root `0x0022A3B9`.
57. **Done:** Phase 5AG opened exact
    `\\Device\\Harddisk0\\partition0` through the isolated
    `game:\\merc360-partition0` sandbox, then captured the first raw probe:
    512-byte `NtReadFile` at offset `0x800` returned
    `STATUS_UNSUCCESSFUL` and exposed a second ordinal-301 status conversion.
58. **Done:** Phase 5AH made ordinal 301 `RtlNtStatusToDosError` repeatable.
    Real hardware mapped `0xC0000001 -> 31`, executed maintained
    `SetLastError(31)`, and advanced to a new deterministic READ32 fault at
    `0x800000A4` from translated caller `0x002294AE`. Build:
    `P5AH-RTLSTATUS301-REPEATABLE-20261020-A`.
59. **Done:** Phase 5AI relocated ordinal 164 `LaunchDataPage` to guest
    kernel-data VA `0x0087E030`, initialized NULL. Hardware proved the exact
    thunk rewrite `0x800000A4 -> 0x0087E030`, preserved the complete prior
    startup/storage path, and advanced with `fault=0` to
    `ICALL_SAFE caller=0x002294AE target=0x800000A5`. Build:
    `P5AI-LAUNCHDATAPAGE-DATA-20261020-A`.
60. **Done:** Phase 5AJ proved batched memory-manager bring-up on real
    hardware. Ordinal 165 `MmAllocateContiguousMemory` serviced a 4096-byte
    request, returned guest VA `0x03EFF000`, and advanced immediately to
    ordinal 178 `MmPersistContiguousMemory` with `fault=0`. Build:
    `P5AJ-MM-CLUSTER-20261020-A`.
61. **Done:** Phase 5AK serviced the expanded memory-services path on real
    hardware. Ordinal 165 returned guest `0x03EFF000`; ordinal 178
    `MmPersistContiguousMemory` consumed that 4096-byte page with
    `Persist=TRUE`; execution then reached ordinal 49
    `HalReturnToFirmware` with `fault=0`. Build:
    `P5AK-MM-SERVICES-20261020-A`.
62. **Done:** Phase 5AL modeled Partition0 as a bounded 512 KiB
    fixed-structure config device. Real hardware opened the exact root, serviced
    the offset-`0x800` / 512-byte raw read with `STATUS_SUCCESS`,
    `bytes=512`, and eliminated the previous firmware-return fallback. The
    next deterministic boundary is READ32 `0x80000028` from caller
    `0x0022A3B9`. Build: `P5AL-PARTITION0-CONFIG-20261020-A`.
63. **Done:** Phase 5AM relocated the HAL disk-identity DATA cluster on real
    hardware. Ordinal 40 moved from `0x80000028` to `0x0087E4A0`,
    initialized cache count 3; ordinals 41/42 were absent from this import
    table. Partition0 raw read stayed successful. Retail then attempted a
    512-byte writeback at offset `0x800`, constructed Partition5 cache paths,
    and reached direct frontier `0x0022C5C6` with `fault=0`. Build:
    `P5AM-DISK-IDENTITY-DATA-20261020-A`.
64. **Done:** Phase 5AN-B completed the cache-partition/storage batch on
    real hardware. Partition0 read/write succeeded at offset `0x800`,
    length `512`; cache prep reported all three roots ready; exact
    `\\Device\\Harddisk0\\Partition5` mapped to
    `game:\\merc360-partition5` and opened successfully; translated root
    `0x0022C5C6` executed. The next boundary is fault-free
    `ICALL_SAFE target=0x800000C4` (ordinal 196
    `NtDeviceIoControlFile`). Build:
    `P5AN-CACHE-PARTITION-BATCH-20261020-B`.
65. **Done:** Phase 5AO-B passed on real hardware. The first ordinal-196
    `NtDeviceIoControlFile` call used the 52-byte padded caller frame with
    the canonical argument window at offset 0 and successfully handled
    `IOCTL_DISK_GET_DRIVE_GEOMETRY (0x00070000)`. The immediately following
    canonical 44-byte call successfully handled
    `IOCTL_DISK_GET_PARTITION_INFO (0x00074004)`. Retail then requested
    `HalReturnToFirmware(2)` with a persisted LaunchDataPage for the same
    title. Build: `P5AO-CACHE-DEVICE-IO-20261020-B`.
66. **Done:** Phase 5AP completed its two-launch persistence proof on real
    hardware. Pass 1 created/flushed the 512 KiB Partition0 backing with the
    sector-`0x800` write logged as `changed=1`. Pass 2, using the same XEX,
    reloaded all 524,288 bytes, rewrote that sector as `changed=0`, skipped
    the first-boot cache IOCTL/reboot path, opened/queryed Partition5, created
    `\\??\\Z:`, and advanced fault-free to direct frontier
    `0x0022F0D6` from caller `0x0022BD2D`. The old harness FAIL label was a
    stale first-boot-only gate and has been corrected. Build:
    `P5AP-PARTITION0-PERSIST-20261020-A`.
67. **Done:** Phase 5AQ through 5BB advanced the post-persistence startup
    path through successive translated closures and runtime-service proofs.
    Phase 5BB entered packed ICALL target `0x0023D550`, executed the
    support-owned Xbox CRT heap family, allocated 256 bytes at `0x008C1000`,
    and reached the next fault-free safe indirect frontier
    `0x0022C3FA -> 0x00237052`. Build:
    `P5BB-FRONTIER22DDA4-20261020-A`.
68. **Done:** Phase 5BC introduced the bounded support-clean broad-sweep
    strategy. Generic packed ICALL dispatch automatically entered
    `0x00237052` from caller `0x0022C3FA`, execution continued to
    `0x0023701A`, and hardware stopped cleanly at the next safe indirect
    target `0x00237801` with `fault=0`. This proved that exact translated
    targets can be consumed without a bespoke harness build for each address.
    Build: `P5BC-BROADSWEEP237052-20261020-C`.
69. **Done:** Phase 5BD widened the translated neighborhood and consumed both
    `0x00237052` and `0x00237801` automatically in one launch. A second
    maintained heap allocation returned 128 bytes at `0x008C1100`; execution
    continued through the `0x002385xx` path and reached fault-free
    `ICALL_SAFE target=0x00239055`. Build:
    `P5BD-REGIONALSWEEP237801-20261020-A`.
70. **Done:** Phase 5BE automatically consumed three packed safe-ICALL targets
    in one launch: `0x00237052`, `0x00237801`, and `0x00239055`. The
    maintained heap completed a third allocation (2048 bytes, flags `0x8`)
    at `0x008C1180`; translated execution continued through
    `0x0023D87C` and stopped at fault-free
    `ICALL_SAFE caller=0x0022DDA4 target=0x0023F22B`. Build:
    `P5BE-FORWARDSWEEP239055-20261020-A`.
71. **Done:** Phase 5BF automatically consumed four packed
    safe-ICALL targets in one launch: `0x00237052`, `0x00237801`,
    `0x00239055`, and `0x0023F22B`. The startup path remained fault-free
    through the inherited persistence/VM/heap infrastructure and advanced to
    `ICALL_SAFE caller=0x0022B3F1 target=0x002471C0` with `fault=0`.
    Build: `P5BF-FORWARDSWEEP23F22B-20261020-A`.
72. **Done:** Phase 5BG automatically consumed five packed safe-ICALL
    targets in one launch: `0x00237052`, `0x00237801`, `0x00239055`,
    `0x0023F22B`, and `0x002471C0`. The inherited persistence, VM,
    filesystem and maintained-heap proofs remained stable. Execution then
    reached fault-free direct frontier
    `0x0023776D -> 0x0023BE3C`. Build:
    `P5BG-TEXTTAIL2471C0-20261020-A`.
73. **Done:** Phase 5BH crossed the maintained CRT `_msize` root at
    `0x0023BE3C`, later exercised maintained `RtlReAllocateHeap`, and
    advanced through 53 safe-ICALL plus 94 direct automatic dispatches in one
    launch. The first new hard stop was fault-free
    `ICALL_SAFE caller=0x0023A3CE target=0x000B5E50`. Build:
    `P5BH-DIRECTMOP23BE3C-20261021-B`.
74. **Done:** Phase 5BI consumed the mandatory `0x000B5E50`
    safe-ICALL target and continued to 76 safe-ICALL plus 107 direct automatic
    dispatches, 18282 translated block ticks and 1424 trace entries. The
    maintained CRT/heap paths remained healthy. The first new hard stop was
    fault-free `ICALL_SAFE caller=0x0023A3CE target=0x00039B00`. Build:
    `P5BI-LOWTEXTB5E50-20261021-A`.
75. **Done:** Phase 5BJ consumed `0x00039B00` as safe-ICALL
    dispatch 77 and advanced to 18578 translated block ticks / 1445 trace
    entries before reaching fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x001F2A60`. The inherited
    persistence, VM, filesystem, heap and CRT-manual proofs remained healthy.
    Build: `P5BJ-DEEPLOW39B00-20261021-A`.
76. **Done:** Phase 5BK cleared the observational diagnostic fence at
    `0x001F2A60` and advanced to 316 safe-ICALL plus 555 direct automatic
    dispatches, 60852 translated block ticks, 4941 trace entries, and 229
    maintained CRT `_msize` calls. The first new hard stop was fault-free
    `ICALL_SAFE caller=0x0023A3CE target=0x0024BC50`. Build:
    `P5BK-DIAGMOP1F2A60-20261021-A`.
77. **Done:** Phase 5BL consumed `0x0024BC50` as safe-ICALL
    dispatch 317 and advanced to 358 safe-ICALL plus 597 direct automatic
    dispatches, 61750 translated block ticks, 5152 trace entries, 270
    maintained CRT `_msize` calls and four successful
    `RtlReAllocateHeap` calls. The first new hard stop was fault-free
    `ICALL_SAFE caller=0x0023A3CE target=0x000B20C0`. Build:
    `P5BL-HIGHTAIL24BC50-20261021-A`.
78. **Done:** Phase 5BM proved the reanalysis-promoted
    `0x000B20C0` path through generic packed dispatch and advanced to 807
    safe-ICALL plus 622 direct automatic dispatches, 64101 translated block
    ticks, 5743 trace entries, 295 maintained CRT `_msize` calls and four
    successful `RtlReAllocateHeap` calls. The first new hard stop was
    fault-free `ICALL_SAFE caller=0x0023A3CE target=0x00031080`. Build:
    `P5BM-LOWTEXTB20C0-20261021-A`.
79. **Done:** Phase 5BN consumed `0x00031080` repeatedly through
    generic packed safe-ICALL dispatch and advanced to 843 safe-ICALL plus 626
    direct automatic dispatches, 64803 translated block ticks, 5859 trace
    entries, 299 maintained CRT `_msize` calls and four successful
    `RtlReAllocateHeap` calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x00216BB0`. Build:
    `P5BN-DEEPLOW31080-20261021-A`.
80. **Done:** Phase 5BO consumed `0x00216BB0` through generic packed
    direct dispatch and advanced to 845 safe-ICALL plus 630 direct automatic
    dispatches, 64829 translated block ticks, 5869 trace entries, 301
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x000C8140`. Build:
    `P5BO-MIDTEXT216BB0-20261021-A`.
81. **Done:** Phase 5BP consumed `0x000C8140` through generic packed
    direct dispatch and advanced to 859 safe-ICALL plus 641 direct automatic
    dispatches, 66991 translated block ticks, 5992 trace entries, 307
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x0010B2B0`. Build:
    `P5BP-LOWTEXTC8140-20261021-A`.
82. **Done:** Phase 5BQ consumed `0x0010B2B0` through generic packed
    direct dispatch and advanced to 868 safe-ICALL plus 646 direct automatic
    dispatches, 67067 translated block ticks, 6018 trace entries, 309
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x000F8BB0`. Build:
    `P5BQ-LOWTEXT10B2B0-20261021-A`.
83. **Done:** Phase 5BR consumed `0x000F8BB0` through generic packed
    direct dispatch and advanced to 930 safe-ICALL plus 722 direct automatic
    dispatches, 67954 translated block ticks, 6284 trace entries, 346
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x00105020`. Build:
    `P5BR-LOWTEXTF8BB0-20261021-A`.
84. **Done:** Phase 5BS consumed `0x00105020` through generic packed
    direct dispatch and advanced to 1253 safe-ICALL plus 988 direct automatic
    dispatches, 73303 translated block ticks, 7280 trace entries, 386
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x00191680`. Build:
    `P5BS-LOWTEXT105020-20261021-A`.
85. **Done:** Phase 5BT consumed `0x00191680` through generic packed
    direct dispatch and advanced to 1261 safe-ICALL plus 1000 direct automatic
    dispatches, 73402 translated block ticks, 7316 trace entries, 394
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x001462E0`. Build:
    `P5BT-MIDTEXT191680-20261021-A`.
86. **Done:** Phase 5BU consumed `0x001462E0` through generic packed direct
    dispatch and advanced to 1262 safe-ICALL plus 1002 direct automatic
    dispatches, 73417 translated block ticks, 7322 trace entries, 395
    maintained CRT `_msize` calls and four successful `RtlReAllocateHeap`
    calls. The first new hard stop was fault-free
    `DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`. The delta versus
    5BT collapsed to +1 safe ICALL, +2 direct, +1 `_msize`, +15 ticks and
    +6 trace. Build: `P5BU-MIDTEXT1462E0-20261021-A`.
87. **Done:** Phase 5BV frozen-pack repeatability passed 3/3 on real
    hardware using one unchanged `P5BV-REPEATABILITY-20261021-A` XEX and
    persistent Partition0 state. Every run reproduced
    `DIRECT_FRONTIER 0023A3CE -> 0014CD30`, `fault=0`, icall=1262,
    direct=1002, `_msize`=395, realloc=4, final allocation size 2048,
    ticks=73417, trace=7322, guest-arena release, proof-end and XAPI return 0.
    The translated/runtime repeatability gate is closed.
88. **Done:** Phase-5 exit reconnaissance reported
    `[Phase5Exit] READY / PASS`. The stable `0x0014CD30` endpoint was
    classified as exact generated title code in `recomp_0006.c`, original
    range `0x0014CD30-0x0014CD9C`; graphics/display, audio, movies/video,
    input and cross-cutting surfaces were inventoried; six Phase-6 risks were
    ranked; and all five required handoff artifacts were generated. **Phase 5
    is 100% COMPLETE.**
89. **Phase 6 active — Native Xbox 360 graphics (Xenos):** the Mercenaries
    NV2A/pushbuffer/format/state/shader/surface inventory is complete. The
    backend-neutral interface seam is **in progress** because maintained
    D3D8/NV2A semantic layers exist but D3D11/DXGI backend assumptions still
    need isolation. Immediate target: initialize a native Xbox 360 graphics
    device and render an independent Xenos test surface. Plan:
    `ports/mercenaries/xbox360/phase6_native_graphics/PHASE6_XENOS_PLAN.md`.


### 2026-10-21 — PHASE 5 COMPLETE / Phase 6 begins

- Phase 5BV froze the translated pack and passed **3/3 identical real-hardware
  boots** with the same `0x0014CD30` endpoint and exact runtime counters.
- The mandatory Phase-5 exit reconnaissance reported **READY / PASS**.
- `0x0014CD30` was classified as exact generated title code in
  `recomp_0006.c`, original range `0x0014CD30-0x0014CD9C`.
- All five required exit artifacts were generated and five subsystem families
  plus six Phase-6 risks were recorded.
- **Phase 5 is 100% complete.**
- Active development moved to branch
  `xbox360/phase6-native-graphics`. The first graphics-inventory task is
  complete; backend abstraction cleanup is in progress; the immediate hardware
  milestone is an independent native Xenos test surface.

### 2026-10-21 — First visible Xenos hardware output

- Phase 6A visibly presented the intended native Xenos color sequence on real
  Xbox 360 hardware: dark green -> blue -> red -> grey/white.
- This proves the native Xbox 360 D3D device/backbuffer/present path reaches the
  physical display.
- Full Phase-6A gate closure remains pending the xbWatson/debug PASS tail and
  clean XAPI return 0.
- No Mercenaries guest renderer is connected yet; this is the standalone native
  graphics baseline that Phase 6B will wrap behind the backend seam.

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
complete. Subsequent Phase 3E testing has now also executed the first bounded
translated Mercenaries function successfully.

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
- [x] Generate and compile isolated memory/instruction fixtures under the actual
      Xbox 360 compiler before attempting translated game functions. Phase
      3A/3B/3C/3D all passed on modified Xbox 360 hardware.
- [x] Validate flags, sign extension, stack/calling convention, frame saving,
      `RECOMP_ICALL` dispatch, direct/tail calls and function returns on real
      modified Xbox 360 hardware across Phase 3E–3L fixtures.
- [x] Validate x87, MMX and SSE semantics against the original instruction
      results, including controlled rounding, NaN, Infinity and invalid-conversion
      paths; Phase 3M hardware suite passed with full selected-cluster coverage.
- [ ] Evaluate Xenon limitations: native stack depth, object/code size,
      memory budget and compiler/linker constraints.
- [x] Execute one bounded real translated Mercenaries function on hardware:
      `sub_00208F30` matched the independent reference for six inputs, preserved
      guest state, and returned with correct guest ESP cleanup.
- [x] Execute a small real translated tail-call chain on hardware: translated
      `0x001EF850` adjusted ECX by 0x28 and tail-called translated `0x0021AB90`,
      matching a direct translated-callee differential across registers, XMM0,
      ret-4 stack cleanup and the complete 64 MiB guest-RAM digest.
- [x] Execute a normal translated CALL chain with synthetic guest return-address
      push: translated `0x00050010 -> 0x0004CFF0` matched an independent explicit
      guest-stack reference across all three hardware cases, including callee
      entry ESP/[ESP], final registers and complete 64 MiB RAM digest.
- [x] Execute indirect translated call dispatch: real translated caller
      `0x0008DE60` computed its own guest function-pointer slot, read nonzero
      `0x0004CFF0`, and dispatched through `RECOMP_ICALL_SAFE` to translated
      `0x0004CFF0`; resolved, unresolved and range-reject paths all matched the
      independent reference on modified Xbox 360 hardware.
- [x] Execute a broader multi-function translated slice: one persistent 64 MiB
      guest arena ran direct CALL, tail-call/MOVSS, resolved ICALL, unresolved
      ICALL and a final direct CALL; all three cases repeated deterministically
      with matching full-RAM checkpoint hashes, intact canaries/markers and no
      guest-memory faults.
- [x] Execute the first dependency-closed translated function cluster selected
      automatically from a real Mercenaries call graph: root `0x000B2080`,
      6 members, dependency depth 2, deterministic 12-profile suite coverage
      `6/6`, exact root-return ESP, no guest-memory faults, matching A/B
      traces/full-RAM hashes, and clean XAPI return on modified Xbox 360 hardware.
- [x] Widen to a new seven-function translated cluster with broader control-flow/flags
      and mixed x87/XMM state; 16 deterministic hardware profiles passed with 7/7
      coverage, exact integer/x87/XMM A/B state, full 64 MiB RAM equality and XAPI 0.
- [x] Prove a bounded real translated closure containing backward guest control flow
      under an explicit execution budget; 16 hardware profiles passed with 9/9
      coverage, 17,344 real backward-edge executions, deterministic mixed state,
      full 64 MiB RAM equality and XAPI 0.
- [x] Prove real x87 rounding/exceptional-path translation under controlled control-word
      and NaN/Infinity/boundary inputs: Phase 3M hardware build D passed 9/9
      selected-cluster coverage, deterministic A/B state/full-RAM comparison,
      11 real x87 rounding/conversion calls and clean XAPI return.
- [x] **Phase 3N final Gate-3 consolidation:** full post-patch generated-tree
      audit completed; Phase 3N-B compiled/linked and executed a 128-function
      audited translated-code scale pack on real Xbox 360 hardware, verified
      loaded-XEX anchors, maintained x87 behavior, six independent-reference
      runs of retail `0x00208F30`, and clean XAPI return.

**Gate 3: PASS (October 19, 2026).** Reproducible real-hardware guest ABI,
translated-code scale and reference-comparison suite passed on modified Xbox
360 hardware.

### Phase 4 — Xbox 360 platform and original Xbox kernel bridge

**Purpose:** provide original Xbox guest services using native Xbox 360 APIs.

- [x] Inventory original Xbox kernel imports *actually used by Mercenaries*:
      exact verified-retail surface is 111 imports — 74 explicit bridges,
      11 guest data exports and 26 return-zero fallbacks.
- [x] Hardware-prove and runtime-platformize the six timing/synchronization
      imports; Phase 4B-A/A2 passes at the real-console and regression layers.
- [x] Hardware-prove and runtime-platformize the nine file/handle imports;
      Phase 4B-B/B2 passes at the real-console and regression layers.
- [x] Hardware-prove the final memory/protection semantics on real Xenon
      with `P4B-MEMPROT-20261019-B`.
- [x] Complete Phase 4B-C2 verification of the production guest-owned
      `NtFreeVirtualMemory` / `MmSetAddressProtect` integration:
      `host_surface=0`, `platform_bound=15`, `guest_native=2`, with all
      timing, ABI, file/handle and memory ownership regressions green.
- [ ] Execute the first real retail-derived translated Mercenaries startup path
      through the migrated Xenon service layer and record deterministic
      xbWatson checkpoints/failure boundaries.
- [ ] Complete title-owned path/storage validation with real Mercenaries asset
      and save traffic on the native startup path.
- [ ] Support Xbox 360 controller input and original-game button mapping.
- [ ] Preserve remaining guest callbacks, interrupts, DPC/ISR safe points and
      thread-scheduling expectations under real title startup.
- [ ] Validate guest kernel data exports and safe callback delivery under real
      translated execution.
- [ ] Exercise real asset reads and title shutdown/error cases.

**Gate 4:** startup service requests and title-critical imports have verified
native implementations, not unexplained stubs.

### Phase 5 — Subsystem bring-up under native game execution

**Status: COMPLETE — Gate 5 PASS (October 21, 2026).**

**Purpose:** drive genuine translated Mercenaries startup through the native
Xbox 360 runtime until the active title-code graph converges, then prove the
result is deterministic and produce an evidence-backed subsystem handoff for
native graphics/audio/movie/input work.

- [x] Bring the exact supported retail XBE through native Xbox 360 startup with
      persistent guest storage, VM, filesystem, kernel-data and ABI invariants.
- [x] Establish and hardware-prove the maintained guest heap/CRT path,
      including allocation, free, realloc and `_msize`.
- [x] Implement reviewed automatic continuation through exact packed
      `ICALL_SAFE` and direct-frontier targets while retaining hard stops for
      unknown semantics, unsafe indirects, faults and platform/subsystem
      boundaries.
- [x] Classify maintained diagnostic/checkpoint helpers without fabricating
      gameplay/platform success.
- [x] Saturate the translated startup graph across deep-low, low, mid, forward,
      high-tail and text-tail regions through Phase 5BU.
- [x] Freeze the final translated pack and prove repeatability with one
      unchanged `P5BV-REPEATABILITY-20261021-A` XEX over **3/3 consecutive
      real-hardware boots** with persistent Partition0 left intact.
- [x] Reproduce the exact stable endpoint on all three runs:
      `DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`,
      `esp=0x008BFF3C`, `saved_esp=0x008BFF3C`, icall=1262,
      direct=1002, `_msize`=395, realloc=4, final allocation size=2048,
      ticks=73417, trace=7322, `fault=0`, guest-arena release, proof end and
      XAPI return 0.
- [x] Run the mandatory Phase-5 exit reconnaissance. It reported
      **`READY / PASS`**, classified `0x0014CD30` as an exact generated
      title function in `recomp_0006.c` (original range
      `0x0014CD30-0x0014CD9C`), inventoried graphics/display, audio,
      movies/video, input and cross-cutting surfaces, and ranked six Phase-6
      risks.
- [x] Produce all required Phase-6 handoff artifacts:
      `phase5-exit-subsystem-surface.json`,
      `phase5-exit-subsystem-surface.md`,
      `phase5-exit-first-touch.txt`, `phase6-risk-map.json`, and
      `phase6-handoff.md`.

**Gate 5: PASS.** The translated/runtime startup path is converged,
repeatable and classified. Phase 5 is frozen; Phase 6 may implement real
Xbox 360-native subsystem backends without reopening Phase 5 unless new
hardware evidence invalidates a proven invariant.

### Phase 6 — Native Xbox 360 graphics (Xenos)

**Purpose:** replace NV2A/PGRAPH-to-D3D11 hosting with a correct native
Xbox 360/Xenos graphics backend.

- [x] Inventory actual Mercenaries NV2A pushbuffers, texture formats,
      swizzle, render states, vertex programs, combiners and surface aliases.
      Phase-5 exit reconnaissance plus the maintained NV2A/PGRAPH/D3D8
      semantic implementation provide the evidence-backed starting inventory.
- [ ] Introduce backend-neutral presentation/texture/draw interfaces.
      **IN PROGRESS:** the semantic/resource layers exist, but D3D11/DXGI
      backend assumptions still need to be isolated behind the Xenos seam.
- [ ] Initialize an Xbox 360 graphics device and render an independent test
      surface (not yet the game). **Immediate target.**
- [ ] Implement compatible 2D, textured draw and flip operations.
- [ ] Translate needed shaders and vertex formats; validate depth/stencil,
      blending, alpha testing, render targets and synchronization.
- [ ] Capture the first guest-rendered frame; then the main menu;
      then a reproducible 3D scene, comparing to the working PC reference.
- [ ] Measure frame time, GPU memory and renderer errors on hardware.

**Gate 6:** repeatable native Xenos first frame and functional
title/menu/scene graphics.

Detailed active plan:
`ports/mercenaries/xbox360/phase6_native_graphics/PHASE6_XENOS_PLAN.md`.

### Phase 7 — Audio, movies, input, asset streaming and timing

- [x] Inventory original Xbox APU/DirectSound/XACT, XMV/WMADEC, input and
      cross-cutting timing/lifecycle surfaces during the Phase-5 exit gate.
- [ ] Implement/bridge native Xbox 360 audio output, sound decoding and
      channel/mixing behavior.
- [ ] Bind native Xbox 360 controller polling to the preserved title mapping
      and context layer; validate vibration and reconnect semantics.
- [ ] Preserve sample progression, callbacks and cutscene timing.
- [ ] Connect required movie playback/output to the native graphics/audio
      backends without bundling proprietary media.
- [ ] Validate loading/streaming on console storage within available RAM.
- [ ] Test music, dialogue, SFX, movie transitions, input handoff and long
      idle playback.

**Gate 7:** stable startup media/menu audio/input with no critical timing drift
or cutscene softlock in documented hardware scenarios.

### Phase 8 — Gameplay, reliability and packaging

- [ ] Start game, use menus, load world and control a character.
- [ ] Test driving, combat, AI, mission triggers and asset loading.
- [ ] Test save/load, checkpoints and repeated cold starts.
- [ ] Run extended sessions and record memory/CPU/GPU use and crashes.
- [ ] Optimize only after profiling actual hardware; document FPS and
      resolution measurements rather than speculative targets.
- [ ] Produce repeatable builds, provenance, bug list and setup guide.
- [ ] Verify no proprietary Xbox 360 SDK or original game files are
      included in public release artifacts.

**Gate 8:** independently repeatable playable scenarios and a documented
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
| 2026-10-18 | Phase 3A explicit scalar guest-memory ABI hardware fixture | **PASS** | Modified Xbox 360 Xenon: big-endian host + LE guest bytes, 8/16/32/64 MOV/RMW, CMPXCHG-style paths, PUSH/POP order, aliases and MMIO/boundary rejection |
| 2026-10-18 | Phase 3B signed + x87 guest-memory ABI hardware fixture | **PASS** | Modified Xbox 360 Xenon: signed loads, float/double IEEE-754 bytes, FILD/FIADD/FLD/FADD/FSTP/FIST/FCOM-style memory paths |
| 2026-10-18 | Phase 3C SSE/XMM + MMX guest-memory ABI hardware fixture | **PASS** | Modified Xbox 360 Xenon: 128-bit lanes, MOVSS/MOVSD/MOVLPS/MOVHPS, packed arithmetic/bitwise, MMX, alias + boundary/MMIO rejection |
| 2026-10-18 | Phase 3D runtime/string guest-memory ABI hardware fixture | **PASS** | Modified Xbox 360 Xenon: shared PUSH/POP, XBOX_MEMCPY, REP MOVS overlap/order, MOVS/STOS/LODS, CMPS/SCAS, alias + MMIO/boundary semantics |
| 2026-10-18 | Phase 3E first bounded translated Mercenaries function | **PASS** | Modified Xbox 360 Xenon: real translated retail function `0x00208F30`, six reference-matched inputs, guest object preserved, translated RET restored ESP |
| 2026-10-18 | Phase 3F first translated Mercenaries tail-call chain | **PASS** | Modified Xbox 360 Xenon: translated `0x001EF850 -> 0x0021AB90`, scalar MOVSS stack load/store, ret-4 cleanup, XMM0 equality, full 64 MiB RAM-hash equality |
| 2026-10-18 | Phase 3G first translated Mercenaries normal-CALL chain | **PASS** | Modified Xbox 360 Xenon: translated `0x00050010 -> 0x0004CFF0`, synthetic zero return-slot push, callee RET/caller RET stack restoration, full 64 MiB RAM-hash equality, clean XAPI 0 |
| 2026-10-18 | Phase 3H first translated Mercenaries indirect-call dispatch | **PASS** | Modified Xbox 360 Xenon: caller `0x0008DE60` discovered real guest pointer slot `0x00000034`, consumed nonzero `0x0004CFF0`, resolved through `RECOMP_ICALL_SAFE`, matched unresolved/range-guard reference, clean XAPI 0 |
| 2026-10-18 | Phase 3I composite translated execution slice | **PASS** | Modified Xbox 360 Xenon: five-stage direct-CALL → tail/MOVSS → resolved ICALL → unresolved ICALL → direct-CALL sequence in one persistent 64 MiB arena; all 15 A/B full-RAM checkpoints matched with intact canaries/markers |

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

### 2026-10-18 — Phase 3E first bounded translated-function gate prepared

- Selected reviewed retail function `0x00208F30`: a tiny one-byte state
  accessor documented by the manual seed as returning bit zero of
  `[ECX + 0x14]`.
- Created `xbox360/phase3e-first-translated-function`.
- No new retail-derived generated C is committed. A local PowerShell prep
  script verifies the pinned retail XBE, runs one reviewed-seed disassembly,
  lifts only `0x00208F30` with `--explicit-guest-memory`, audits it, and
  injects it into a gitignored local XDK harness.
- The candidate is rejected if it no longer has exactly the expected 8-bit
  read-only shape, contains guest writes, ICALL/runtime dependencies, wider
  reads or another translated-function call.
- The hardware harness tests inputs `00 01 02 03 FE FF`, compares the
  translated low-byte result to `input & 1`, verifies function trace VA,
  object immutability, no guest access fault and exact four-byte RET cleanup.
- **Next:** run the local prep script, compile the generated
  `build\phase3e_first_translated\main.cpp`, and capture xbWatson.

### 2026-10-18 — Phase 3E local translated-function generation passes

- Local Python environment confirmed at Python 3.12.10 with required packages.
- User-supplied retail `default.xbe` matched the exact pinned SHA-256.
- Reviewed-seed disassembly completed in 35.49 seconds.
- Recompiler loaded 13,346 functions and 16,598 labels for the isolated lift.
- Missing optional identified-function / ABI databases were warned about but did
  not block this dependency-free accessor candidate.
- Function `0x00208F30` lifted successfully with
  `--explicit-guest-memory`.
- Post-generation audit reported:
  `PASS: no legacy guest-memory lvalues in generated C`.
- Prep script finished with `[Phase3E] READY` and produced local gitignored:
  `build\phase3e_first_translated\sub_00208F30.c` and
  `build\phase3e_first_translated\main.cpp`.
- **Phase 3E local-generation gate: PASS. Hardware execution remains pending.**
- **Next:** compile the generated local `main.cpp` in VS17/XDK and run the
  resulting XEX on modified Xbox 360 hardware.

### 2026-10-18 — Phase 3E first real translated Mercenaries function passes on Xenon

- Runtime build tag `P3E-FIRSTFUNC-20261018-A` confirmed the intended XEX.
- Real mechanically translated retail function `sub_00208F30` executed on
  modified Xbox 360 Xenon hardware.
- Controlled inputs and independent reference results:
  `00→0`, `01→1`, `02→0`, `03→1`, `FE→0`, `FF→1`.
- Every case matched `input & 1`.
- Full EAX retained its seeded upper 24 bits while the translated function
  updated the expected low byte.
- Guest object byte remained unchanged for every read-only accessor case.
- No guest-memory access fault was observed.
- Function trace VA matched `0x00208F30`.
- Translated `RET` consumed exactly one 4-byte guest return-address slot and
  restored ESP to `0x008BFFF0` on every case.
- `PHASE 3E FIRST TRANSLATED FUNCTION RESULT: PASS` observed on hardware.
- **Phase 3E: COMPLETE.**
- **Next:** Phase 3F — a small audited translated direct-call chain before
  indirect-call dispatch or broad startup execution.

### 2026-10-18 — Phase 3F translated tail-call chain prepared

- Created `xbox360/phase3f-translated-tail-call-chain` from completed Phase 3E.
- Selected reviewed retail wrapper `0x00034AD0` and translated callee
  `0x00034AE0`. The seed documents the wrapper as `ECX += 0x78` followed
  by a direct tail jump to the callee.
- The prep workflow verifies the exact retail XBE, reuses Phase 3E analysis when
  available, confirms both reviewed function boundaries, lifts both functions
  with `--explicit-guest-memory`, and rejects unexpected third-function calls,
  ICALL/ITAIL, runtime-copy/kernel dependencies, debug/RDTSC, or SIMD/x87 state.
- It also requires the generated wrapper tail-jump marker and rejects any
  synthetic `PUSH32` in that tail-call path.
- Hardware reference is differential rather than a guessed callee model:
  direct callee at `ECX=BASE+0x78` is compared with wrapper at `ECX=BASE`.
- Three deterministic cases compare final integer register state, SEH EBP,
  guest ESP cleanup, function-trace sequence, access-fault state and a hash of
  the complete 64 MiB guest arena.
- **Next:** run Phase 3F prep locally, compile the generated
  `build\phase3f_translated_tailcall\main.cpp`, and capture xbWatson.

### 2026-10-18 — Phase 3F first candidate rejected by dependency audit

- Local prep reused the Phase 3E reviewed-seed disassembly successfully.
- Wrapper `0x00034AD0`: 12 bytes / 3 instructions.
- Callee `0x00034AE0`: 108 bytes / 36 instructions.
- Both functions lifted successfully with the explicit guest-memory mode.
- Before XDK compilation, the strict Phase 3F dependency gate rejected the
  callee because generated output matched the guarded ICALL/kernel/runtime-copy
  dependency class.
- **No hardware run occurred and this is not a translated-execution failure.**
- Updated the prep script to print the exact generated dependency line(s) on
  the next run so the candidate can be re-audited precisely.
- A reviewed backup tail-call family around `0x001EF850 -> 0x0021AB90` is
  available if the current callee proves too broad for the first chain.

### 2026-10-18 — Phase 3F pivots to isolated setter tail-call candidate B

- Candidate A's exact dependency was identified:
  `RECOMP_ICALL_SAFE(GUEST_READ32(eax), _icall_esp)`.
- Candidate A is therefore deferred because it would test tail-call semantics
  and guest indirect-call dispatch simultaneously.
- Candidate B is `0x001EF850 -> 0x0021AB90`; the callee is the reviewed
  scalar transform setter documented as writing its float argument to
  `this + 0xDC` and returning with `ret 4`.
- The local prep workflow now derives a reference-prefix copy from the exact
  translated wrapper and stops it at its real generated tail boundary.
- Hardware will compare reference-prefix + direct translated callee against the
  unmodified translated wrapper + real tail-called callee from identical guest
  state.
- Build tag: `P3F-TAILCALL-20261018-B`.
- **Next:** update the local branch and rerun `Prepare-Phase3F.ps1`.

### 2026-10-18 — Phase 3F Candidate B scalar-XMM0 audit refined

- Candidate B local lift found wrapper `0x001EF850` at 8 bytes / 2
  instructions and callee `0x0021AB90` at 17 bytes / 3 instructions.
- The first Candidate B prep stopped because its deliberately conservative
  SIMD guard saw:
  `GUEST_WRITEF32(ecx + 0xDC, xmm0); /* movss */`.
- This is not a new unsupported execution class: scalar XMM0 + float guest
  memory was already hardware-proven in Phase 3C.
- The Phase 3F guard now permits only the exact scalar XMM0 path required by
  this candidate: wrapper `recomp_xmm_loadss(g_xmm0, esp + 4)` and callee
  `GUEST_WRITEF32(ecx + 0xDC, xmm0)`.
- Packed SSE, XMM1-XMM7, MMX, x87, 64-bit float paths, ICALL/ITAIL,
  kernel/runtime-copy helpers, RDTSC and debugbreak remain rejected.
- The Xenon harness now seeds and captures all four XMM0 lanes and includes
  them in the differential architectural-state comparison.
- **Next:** update the local branch and rerun Candidate B prep.

### 2026-10-18 — Phase 3F Candidate B wrapper shape confirmed

- Local generated wrapper `0x001EF850` was observed directly:
  `ecx = ecx + 0x28;` followed by the generated direct tail invocation of
  `sub_0021AB90()`.
- The wrapper is only 8 bytes / 2 x86 instructions and does not load or modify
  XMM0; the scalar value is already live on entry.
- The prior prep expectation that the wrapper loaded `[ESP+4]` into XMM0 was
  therefore incorrect and has been removed.
- Candidate B is now tested with a simpler differential:
  direct translated callee at `ECX=BASE+0x28` versus real translated wrapper
  at `ECX=BASE`, with identical live XMM0 and guest stack state.
- The harness explicitly requires the scalar XMM0 bits to be written at the
  common effective `this+0xDC` address, verifies `ret 4` cleanup, compares
  all integer registers and all four XMM0 lanes, and hashes all 64 MiB of guest
  RAM after both paths.
- **Next:** update the local branch and rerun `Prepare-Phase3F.ps1`.

### 2026-10-18 — Phase 3F Candidate B callee stack-MOVSS shape confirmed

- Candidate B's generated callee was confirmed to perform its own scalar
  XMM0 load from guest stack before the setter store.
- The earlier guard that rejected any callee-side `recomp_xmm_loadss` was
  therefore too strict and has been corrected.
- Phase 3F now requires the callee shape:
  `MOVSS [ESP+4] -> XMM0`, then
  `GUEST_WRITEF32(ECX+0xDC, XMM0)`, then translated `ret 4`.
- The Xenon harness poisons all four XMM0 lanes before entry, places the scalar
  argument only in guest `[ESP+4]`, and requires lane 0 to equal the exact
  guest argument while lanes 1-3 are zeroed according to the Phase 3C-proven
  memory-form MOVSS semantics.
- Direct-callee and real wrapper-tail-call paths still begin from otherwise
  identical state and are compared across registers, XMM0, ESP, store bits,
  trace order and complete 64 MiB guest-RAM digest.
- **Next:** update the local Phase 3F branch and rerun the prep workflow.

### 2026-10-18 — Phase 3F generated XMM alias corrected

- Local Candidate B output confirmed the full 3-instruction callee:
  `recomp_xmm_loadss(xmm0v, esp + 4)`,
  `GUEST_WRITEF32(ecx + 0xDC, xmm0)`,
  then translated `ret 4`.
- The prep gate incorrectly expected the vector form as `g_xmm0`; generated
  code correctly uses the runtime alias `xmm0v`.
- Updated the prep audit to require canonical `xmm0v`.
- Updated the XDK harness with `#define xmm0v g_xmm0` so the generated body
  matches the maintained runtime ABI.
- **Candidate B remains valid; no hardware execution occurred in this attempt.**

### 2026-10-18 — Phase 3F translated tail-call chain passes on Xenon

- Runtime build tag `P3F-TAILCALL-20261018-B` confirmed the intended XEX.
- Real mechanically translated wrapper `0x001EF850` executed on modified Xbox
  360 hardware and tail-called real translated callee `0x0021AB90`.
- Wrapper behavior `ECX += 0x28` matched the direct translated-callee
  differential in all three cases.
- Callee loaded the exact scalar argument from guest `[ESP+4]` into XMM0 lane
  0 for `1.0f`, `-2.5f`, and `~1/3`.
- Memory-form MOVSS zeroed XMM0 lanes 1-3 on both direct and real-chain paths.
- The scalar bits were stored exactly at effective `this + 0xDC`.
- Translated `ret 4` restored ESP to `0x008BFFF0` in every case.
- Direct trace was exactly `[0x0021AB90]`; real-chain trace was exactly
  `[0x001EF850, 0x0021AB90]`.
- No guest-memory access faults were observed.
- All integer architectural results and all four XMM0 lanes matched the
  differential reference.
- Complete 64 MiB guest-RAM digests matched for all three cases:
  `F47312746CCBB4D1`, `69F1610204AF5DE6`, and `4160C21D46EE4A6B`.
- `PHASE 3F TRANSLATED TAIL-CALL RESULT: PASS` observed on hardware.
- The supplied log excerpt ends during post-test heartbeats; no final timeout
  or XAPI exit-status line was supplied, so only the observed functional PASS
  is recorded.
- **Phase 3F: COMPLETE.**
- **Next:** Phase 3G — first bounded real translated normal-CALL chain, proving
  the synthetic guest return-address push + callee RET interaction before
  indirect-call dispatch.

### 2026-10-18 — Phase 3G translated normal-CALL gate prepared

- Created `xbox360/phase3g-translated-direct-call-chain` from completed Phase
  3F.
- Phase 3G selects its candidate from the actual reviewed disassembler
  `calls_to` graph, which records real x86 CALL targets.
- The selector searches compact anonymous caller/callee pairs and requires
  exactly one generated `PUSH32(esp, 0); callee();` normal-CALL lowering.
- The first gate rejects tail jumps, ICALL/ITAIL, kernel/runtime-copy helpers,
  RDTSC/debugbreak, SEH bridging, x87/SSE/MMX, third translated calls, RET N,
  and unrelated stack mutation.
- A local reference copy of the selected translated caller replaces only the
  generated PUSH32 CALL with an independent explicit
  `GUEST_WRITE32(ESP-4, 0)` + ESP update before entering the same translated
  callee.
- A non-semantic callee wrapper records entry ESP and guest `[ESP]`, proving
  the real generated CALL creates one zero-valued 4-byte synthetic return slot.
- Three deterministic hardware cases compare final integer architecture,
  guest ESP, trace order, probe data, access-fault state and complete 64 MiB
  guest-RAM digest.
- Build tag: `P3G-CALL-20261018-A`.
- **Next:** run `Prepare-Phase3G.ps1`, compile the generated local
  `build\phase3g_translated_direct_call\main.cpp`, and capture xbWatson.

### 2026-10-18 — Phase 3G selector standalone-import fix

- First local Phase 3G prep verified the exact retail XBE and reused the Phase
  3E reviewed-seed disassembly, but the standalone selector failed before
  candidate selection with `ModuleNotFoundError: No module named 'tools'`.
- Cause: launching the nested selector file directly placed only its own
  directory on Python `sys.path`, not the repository root.
- The selector now derives the repository root from `__file__` and inserts it
  before importing `tools.recomp`.
- While auditing the rerun path, the first normal-CALL selector was also
  tightened to prefer linear, flag-free caller/callee pairs so the 3G hardware
  fixture isolates CALL-stack behavior rather than mixing in branch/flag state.
- **No candidate selection or hardware execution occurred in this failed
  attempt.**

### 2026-10-18 — Phase 3G translated normal-CALL chain passes on Xenon

- Build tag `P3G-CALL-20261018-A` confirmed the intended XEX.
- Automatic selection chose real translated caller `0x00050010` and callee
  `0x0004CFF0`.
- All three deterministic cases matched the independent explicit-stack
  reference.
- The translated callee entered exactly once on both reference and generated
  paths.
- Callee entry ESP was `0x008BFDFC`, exactly one 4-byte slot below caller
  initial ESP `0x008BFE00`.
- Guest `[ESP]` at callee entry was exactly `0x00000000`, proving the
  generated `PUSH32(esp, 0)` synthetic translated return slot.
- Callee RET restored the caller stack and caller RET consumed its own return
  slot, finishing at ESP `0x008BFE04`.
- Trace order was exactly caller `0x00050010` then callee `0x0004CFF0`.
- Generated `PUSH32` CALL behavior matched the independent
  `GUEST_WRITE32(ESP-4, 0)` reference.
- No guest-memory faults were observed.
- Complete 64 MiB guest-RAM digests matched for all three cases:
  `BDABF3F60D2792E5`, `7BC023EB662792E5`, and `7D456C28BF2792E5`.
- `PHASE 3G TRANSLATED NORMAL-CALL RESULT: PASS` observed on hardware.
- Post-test timeout completed normally and `[XAPI RETURN VALUE] 0` was
  observed.
- **Phase 3G: COMPLETE.**
- **Next:** Phase 3H — bounded real translated indirect-call dispatch /
  `RECOMP_ICALL_SAFE`, with the earlier `0x00034AE0` virtual-call path as a
  strong candidate.

### 2026-10-18 — Phase 3H translated ICALL gate prepared

- Created `xbox360/phase3h-translated-icall-dispatch` from completed Phase 3G.
- Phase 3H scans real mechanically translated Mercenaries functions for one
  bounded `RECOMP_ICALL_SAFE` site; earlier candidate `0x00034AE0` is
  preferred but not forced.
- The first ICALL fixture is deliberately linear and stack-simple: no guest
  arguments before the dummy return slot, no unrelated PUSH/POP, no direct
  translated calls, no SEH/x87/SSE/MMX/flag dependency, and one plain RET.
- The resolved dispatch target is the already hardware-proven translated
  `0x0004CFF0`.
- Resolved mode verifies manual miss -> generated lookup hit, synthetic zero
  return slot, target entry, and runtime restoration of deliberately clobbered
  `EBX/ESI/EDI`.
- Unresolved mode keeps target `0x0004CFF0` but disables generated lookup,
  requiring manual/generated/kernel misses, saved-ESP restoration and
  `EAX=0`.
- Range-reject mode uses `0x00400000`, requiring rejection before any lookup,
  saved-ESP restoration and `EAX=0`.
- A transformed local reference caller replaces only the ICALL operation with
  an independent explicit-stack/direct-target helper.
- Three deterministic inputs run through all three modes and compare
  architectural results, target/trace observations, fault state and complete
  64 MiB guest-RAM digest.
- Build tag: `P3H-ICALL-20261018-A`.
- **Next:** run `Prepare-Phase3H.ps1`, compile the generated local
  `build\phase3h_translated_icall\main.cpp`, and capture xbWatson.

### 2026-10-18 — Phase 3H first selector pass finds real ICALL population

- First local Phase 3H prep verified the exact retail XBE and reused the Phase
  3E reviewed-seed disassembly.
- The first 1,600 compact candidates contained 11 real
  `RECOMP_ICALL_SAFE` functions.
- Initial strict-gate rejection histogram:
  - 7 contained one or more direct translated calls
  - 2 contained branching control flow
  - 2 contained a tail jump
- Therefore the first gate was too strict rather than lacking real ICALL sites.
- Phase 3H now permits exactly one additional tiny direct translated helper
  call, provided that helper is linear, plain-RET, dependency-free,
  stack-simple and does not modify EBX/ESI/EDI.
- The optional helper is lifted locally, injected ahead of the caller, and
  audited with the same explicit guest-memory scanner.
- Hardware trace checks now compare the complete reference/real trace instead
  of assuming exactly two entries, while still requiring the indirect target
  exactly once only in resolved mode.
- The ICALL harness now records saved ESP, post-dispatch ESP and post-dispatch
  EAX immediately at the dispatcher so safe-failure behavior is proven at the
  ICALL boundary rather than inferred after later caller instructions.
- If selection still fails, the selector now prints caller VA + exact rejection
  reason for the first real ICALL candidates.
- **No hardware run occurred in the first selector attempt.**

### 2026-10-18 — Phase 3H second selector pass identifies two near-clean real callers

- The diagnostic rerun again found 11 real ICALL callers.
- Exact rejection details showed `0x0008DE60` and `0x0008DE70` passed every
  existing first-gate rule except the selector's requirement that the ICALL
  base register not be modified before the call.
- That requirement was an analysis convenience, not a dispatcher requirement,
  and has been removed.
- Phase 3H now preserves the exact translated caller pointer-computation path.
  A deterministic unresolved discovery prepass records the guest VA the caller
  actually computes at its real ICALL site.
- Resolved mode resets identical state and maps that exact observed guest VA
  through generated lookup to the already-proven translated target
  `0x0004CFF0`.
- Unresolved mode resets the same state and requires manual/generated/kernel
  lookup to exhaust without entering the target; immediate ICALL probes require
  saved-ESP restoration and `EAX=0`.
- The generic `0x00400000` range-reject behavior is now tested separately
  against the same production `RECOMP_ICALL_SAFE` macro and independent
  explicit-stack reference instead of rewriting the real caller's operand.
- If the discovered real guest VA itself falls inside the production rejected
  range, the hardware fixture stops rather than weakening that guard.
- **No hardware execution occurred in this selector attempt.**

### 2026-10-18 — Phase 3H-A real ICALL dispatcher mechanics pass on Xenon

- Build tag `P3H-ICALL-20261018-A` executed real translated caller
  `0x0008DE60` through `RECOMP_ICALL_SAFE` on modified Xbox 360 hardware.
- The deterministic discovery seed produced guest ICALL target `0x00000000`
  in all three cases.
- Resolved mode deliberately mapped that observed guest key through generated
  lookup to translated target `0x0004CFF0`.
- All resolved cases verified:
  - no guest-memory fault
  - identical discovered ICALL target on reference and real paths
  - translated target entered exactly once
  - target entered with one zero-valued synthetic return slot
  - generated lookup hit after manual miss
  - target deliberately clobbered EBX/ESI/EDI and RECOMP_ICALL_SAFE restored all
    three
  - caller/target translated trace matched the independent reference
  - final guest ESP matched
  - complete 64 MiB RAM hashes matched
- All unresolved cases verified:
  - target was not entered
  - saved ESP restored immediately at ICALL boundary
  - EAX forced to zero immediately
  - manual/generated/kernel lookup chain exhausted
  - translated trace matched the reference
  - complete 64 MiB RAM hashes matched
- Separate production range-guard tests at `0x00400000` verified rejection
  before lookup, saved-ESP restoration, EAX=0 and full RAM-hash equality.
- Final observed marker:
  `PHASE 3H TRANSLATED INDIRECT-CALL RESULT: PASS`.
- Supplied excerpt ends during post-test heartbeats; no final XAPI line was
  supplied, so only the observed functional PASS is recorded.
- **Phase 3H-A dispatcher mechanics: PASS.**
- Because the real caller's seeded function-pointer value was NULL
  (`0x00000000`), full Phase 3H completion is intentionally deferred until a
  follow-up run seeds the caller's naturally computed guest pointer slot with a
  nonzero valid translated code VA and proves the same path without mapping
  NULL as the resolved key.

### 2026-10-18 — Phase 3H-B nonzero guest pointer-slot proof prepared

- Follow-up build tag: `P3H-ICALL-20261018-B`.
- The selector now requires a real `GUEST_READ32(...)` ICALL operand so the
  guest function-pointer **slot address** can be observed directly.
- A local discovery caller preserves every translated instruction that computes
  that slot and replaces only the ICALL operation with a probe.
- Hardware discovery records the real guest slot address, resets identical
  state, writes nonzero translated code VA `0x0004CFF0` into that exact slot,
  then runs the unchanged translated caller.
- The actual ICALL trace must then be exactly `0x0004CFF0`; resolved mode maps
  that real nonzero guest code VA to translated `sub_0004CFF0`.
- Unresolved mode uses the same seeded slot and same unchanged caller but
  disables generated lookup, preserving the 3H-A failure-contract checks.
- The separate production `0x00400000` range-guard proof remains unchanged.
- The new generated discovery caller is explicit-memory audited alongside the
  real caller, reference caller, optional direct helper, and translated target.
- **Next:** rerun Phase 3H prep, compile generated `main.cpp`, and capture the
  B-build xbWatson log.

### 2026-10-18 — Phase 3H translated ICALL dispatch passes fully on Xenon

- Follow-up build tag `P3H-ICALL-20261018-B` removed the Phase 3H-A NULL-key
  caveat.
- Real mechanically translated caller `0x0008DE60` computed guest
  function-pointer slot `0x00000034` under all three deterministic seeds.
- The fixture reset identical state and wrote nonzero translated code VA
  `0x0004CFF0` into that exact discovered guest slot.
- The **unchanged translated caller** then read `0x0004CFF0` through its real
  `GUEST_READ32(...)` ICALL operand.
- Real ICALL trace was exactly `0x0004CFF0` for resolved and unresolved runs.
- Resolved mode verified:
  - no guest-memory faults
  - target entered exactly once
  - zero synthetic guest return slot
  - manual lookup miss -> generated lookup hit
  - target deliberately clobbered EBX/ESI/EDI and `RECOMP_ICALL_SAFE`
    restored all three
  - translated trace matched the independent reference
  - final guest ESP matched
  - complete 64 MiB guest-RAM hash matched
- Unresolved mode verified:
  - same unchanged caller read the same nonzero `0x0004CFF0`
  - target was not entered
  - saved ESP restored immediately at the ICALL boundary
  - EAX forced to zero immediately
  - manual/generated/kernel lookup chain exhausted
  - translated trace and full 64 MiB RAM hash matched the reference
- Separate production range-guard tests at `0x00400000` again verified
  rejection before lookup, saved-ESP restoration, EAX=0 and full RAM equality.
- Case hashes:
  - case 0: `5FEC0A1C02F3BEE5`
  - case 1: `BB6103599BF3BEE5`
  - case 2: `64F113F868F3BEE5`
- Final markers observed:
  - `PHASE 3H TRANSLATED INDIRECT-CALL RESULT: PASS`
  - `[XAPI RETURN VALUE] 0`
- **Phase 3H: COMPLETE.**
- **Next:** Phase 3I — first broader multi-function translated execution slice
  combining proven scalar/memory, direct CALL, tail-call and ICALL behavior
  before guarded game-entry/startup execution.

### 2026-10-18 — Phase 3I composite translated slice prepared

- Created `xbox360/phase3i-composite-translated-slice` from completed Phase 3H.
- Phase 3I is a composition gate rather than another isolated semantics proof.
- One XEX now carries the hardware-proven real translated families:
  - direct CALL `0x00050010 -> 0x0004CFF0`
  - tail-call/MOVSS `0x001EF850 -> 0x0021AB90`
  - ICALL caller `0x0008DE60` using its real guest function-pointer slot and
    shared translated target `0x0004CFF0`
- Each case executes five stages without clearing the 64 MiB guest arena:
  direct CALL, tail/MOVSS, resolved ICALL, unresolved ICALL, then direct CALL
  again.
- The final direct call specifically checks that translated execution remains
  healthy after both successful and failed indirect dispatch.
- Persistent guest canaries and cumulative stage markers must survive every
  stage.
- Every stage records a complete 64 MiB guest-RAM checkpoint hash.
- The entire five-stage slice runs twice from identical state for each of three
  input cases; all five checkpoint hashes, final architecture/XMM state,
  translated trace, pointer slot, canaries and fault state must match.
- ICALL pointer-slot discovery itself runs twice and must produce the same
  nonzero mapped guest slot.
- The preparer revalidates all previously proven retail function shapes and
  explicit-memory audits every locally generated body before XDK compilation.
- Build tag: `P3I-SLICE-20261018-A`.
- **Next:** run `Prepare-Phase3I.ps1`, compile generated
  `build\phase3i_composite_slice\main.cpp`, and capture xbWatson.

### 2026-10-18 — Phase 3I first prep attempt hits template-token bookkeeping bug

- Local prep verified the exact supported retail XBE and successfully reused the
  Phase 3E reviewed-seed disassembly.
- The composite retail functions lifted far enough to reach template assembly.
- Preparation then stopped before XDK source generation because the preparer's
  replacement table contained unused token `__P3I_TAIL_CALLEE_NAME__`, while
  the template injects the tail-callee body directly and has no such placeholder.
- Removed the unused replacement token.
- Performed a bidirectional template audit afterward:
  - template tokens missing replacements: 0
  - replacement tokens absent from template: 0
- **No translated semantic failure, explicit-memory audit failure, compile, or
  hardware execution occurred in this attempt.**
- Fix commit on the Phase 3I branch: `c5f3dbb48a84a44e7c22b54ed84194132fc5ce85`.

### 2026-10-18 — Phase 3I composite translated slice passes on Xenon

- Build tag `P3I-SLICE-20261018-A` executed the first five-stage composite
  translated slice on modified Xbox 360 hardware.
- Real translated families in one persistent guest arena:
  - direct CALL `0x00050010 -> 0x0004CFF0`
  - tail-call/MOVSS `0x001EF850 -> 0x0021AB90`
  - resolved ICALL from `0x0008DE60` through real guest pointer slot
    `0x00000034` to nonzero `0x0004CFF0`
  - unresolved ICALL through the same real nonzero pointer
  - final direct CALL `0x00050010 -> 0x0004CFF0` after both ICALL outcomes
- All stages remained guest-memory-fault free.
- Persistent canaries survived every stage and cumulative stage markers remained
  intact.
- The real ICALL pointer slot was deterministic at `0x00000034`.
- Each of three deterministic cases ran the complete five-stage slice twice
  from identical initial state.
- All 15 complete 64 MiB checkpoint hashes matched A vs B:
  - case 0:
    `391D8EBE77156185`,
    `3716FA5917BCAF5C`,
    `6A725AEF6CDC6739`,
    `5BC63F5096702E66`,
    `601DC9E5E9060642`
  - case 1:
    `33E99C35E7354685`,
    `8F5E78AB7F167EA3`,
    `849845E9665D51DE`,
    `22C6E2C437FECB71`,
    `97A3970721A1D89D`
  - case 2:
    `DC774012C0D09585`,
    `F14EAABCAD54286E`,
    `EDCCAAF0A1CF1A23`,
    `82B2E33EA043C0F0`,
    `920E7A6F58C65544`
- Final observed functional marker:
  `PHASE 3I COMPOSITE TRANSLATED SLICE RESULT: PASS`.
- The supplied log excerpt ends during post-test heartbeats, so no unseen XAPI
  return value is claimed.
- **Phase 3I: COMPLETE.**
- **Next:** Phase 3J — select and execute the first dependency-closed translated
  function cluster from the real Mercenaries call graph, preserving explicit
  guest memory and bounded runtime dependencies before guarded entry/startup.

### 2026-10-18 — Phase 3J dependency-closed cluster gate prepared

- Created `xbox360/phase3j-dependency-closed-cluster` from completed Phase 3I.
- Unlike Phase 3I, no translated root/member VA is hand-picked.
- The selector starts from real retail function metadata and recursively follows
  every statically named translated `sub_XXXXXXXX()` dependency.
- Direct CALL, tail-jump and other statically named translated external
  transfers therefore participate in closure.
- The first accepted closure must contain 4–8 entirely new translated functions,
  reach dependency depth >= 2, and stay within bounded byte/instruction budgets.
- Previously hand-selected Phase 3E–3I VAs are excluded from the entire cluster.
- 3J-A requires a statically closed, branch/loop-free integer/memory surface;
  dynamic ICALL/ITAIL, x87/SSE/MMX and unsupported runtime helpers are rejected.
  Branch/flags widening remains Phase 3K.
- Every selected retail-derived body is emitted only beneath gitignored
  `build/phase3j_closed_cluster` and explicit-memory audited before compile.
- The XDK fixture runs the selected root twice for each of three deterministic
  safe-pointer seeds.
- Hardware PASS requires every selected closure member to appear in the trace,
  no guest-memory faults, exact root-return ESP, intact high-RAM canaries,
  identical A/B traces, matching final architecture and complete 64 MiB
  guest-RAM hashes.
- Build tag: `P3J-CLOSURE-20261018-A`.
- **Next:** run `Prepare-Phase3J.ps1`; if no cluster survives, use the printed
  rejection histogram to make the narrowest justified relaxation.

### 2026-10-18 — Phase 3J first selector pass exposes comment-scan false positives

- The first local Phase 3J prep verified the exact retail XBE and reused the
  reviewed Phase 3E disassembly.
- 2,200 real candidate roots were considered; none passed the initial
  branchless/statistically closed gate.
- Initial rejection histogram was dominated by:
  - 1,144 branch/loop-control candidates deferred by the initial 3J-A policy
  - 640 dynamic/SIMD/FPU/runtime-surface candidates
  - 246 apparent `self` helper dependencies
  - 86 RET-N members
- Investigation proved the `self` class was a selector bug: generated comments
  such as `/* sbb self (CF extend) */` were being parsed by the generic
  helper-call regex as if `self(...)` were executable C.
- The selector now strips generated C comments before dependency, helper, and
  control-flow surface classification.
- Real `movzx` helpers `ZX8` / `ZX16` are now explicitly supported by the
  selector and XDK harness instead of being reported as unknown helpers.
- The exact retail hash pin and all dependency-closure bounds remain unchanged.
- **No XDK compile or hardware run occurred in this first selector attempt.**
- **Next:** rerun the same Phase 3J selector before considering any branch/flags
  relaxation.

### 2026-10-18 — Phase 3J second selector pass proves branchless closure is too artificial

- After the comment-scanner and ZX8/ZX16 fixes, the selector again considered
  2,200 real candidate roots and still found no cluster under the branchless
  3J-A policy.
- The dominant blocker increased to **1,390 branch/loop-control rejections**,
  confirming that useful real Mercenaries closures overwhelmingly include
  ordinary control flow.
- The next relaxation is intentionally narrow:
  - forward/acyclic guest branches are allowed
  - SETcc/CMOV-style generated conditional statements are allowed
  - backward guest branch edges remain rejected
  - LOOP/LOOPE/LOOPNE remain rejected
  - generated C while/for/switch surfaces remain rejected
  - dynamic ICALL/ITAIL, SIMD/FPU/runtime surfaces, RET-N, cycles and all
    existing closure/member/size/depth bounds remain rejected
- Runtime condition helpers used by the maintained lifter are now provided by
  the XDK fixture: CMP_EQ/NE/B/AE/BE/A, signed CMP_L/GE/LE/G, TEST_Z/NZ/S and
  EVEN_PARITY8.
- `RECOMP_ICALL_SAFE` / `RECOMP_ITAIL_SAFE` are now classified explicitly
  as dynamic-dispatch surface instead of appearing as unknown helpers.
- **No compile or hardware run occurred in this selector attempt.**
- **Next:** rerun the same Phase 3J selector with bounded acyclic branch support.

### 2026-10-18 — Phase 3J third selector pass exposes C-keyword helper false positive

- With bounded acyclic branches enabled, the selector again considered 2,200
  real candidate roots and found no closure yet.
- New top rejection classes:
  - 799 unsupported dynamic/SIMD/FPU/runtime surface
  - 518 apparent unknown helper `if`
  - 442 backward/loop guest control flow
  - 341 RET-N members
- The `if` class is another selector-only false positive: the generic
  `name(...)` helper scanner was treating ordinary generated C
  `if (...)` syntax as a function call after conditional control flow became
  legal.
- C control/operator tokens `if`, `while`, `for`, `switch`, and
  `sizeof` are now ignored by helper-call classification.
- Unsupported-surface diagnostics now report the first actual matched token
  (for example a specific RECOMP_ICALL/SIMD/FPU/runtime symbol) rather than one
  799-entry aggregate reason.
- **No closure bound, SHA check, runtime rule, compile rule, or hardware pass
  criterion was weakened.**
- **No compile or hardware run occurred in this selector attempt.**
- **Next:** rerun the same Phase 3J selector; if no closure survives, the new
  token-specific unsupported-surface histogram will identify the next real
  blocker.

### 2026-10-18 — Phase 3J fourth selector pass isolates RET-N as next safe relaxation

- After scanner fixes, the selector's rejection profile now reflects real retail
  code shape rather than parser noise.
- Dominant classes:
  - 799 backward/loop guest control flow
  - 381 dynamic `RECOMP_ICALL_SAFE`
  - 380 RET-N members
  - 281 x87 `fp_push`
  - 80 scalar/SSE `recomp_xmm_loadss`
  - 50 `recomp_xmm_zero`
- The next relaxation is limited to **nested translated RET-N dependencies**.
- Phase 3F already hardware-proved translated callee-cleanup return behavior
  (`ret 4`), so rejecting every RET-N dependency is no longer justified.
- The selected **root still must have exactly one plain RET and no RET-N**, so
  the harness retains the exact final `ROOT_STACK + 4` expectation.
- Nested members may use RET-N only when the immediate cleanup is parseable and
  <= 64 bytes.
- Loops/back-edges, dynamic ICALL/ITAIL, x87/SSE/runtime expansion, closure
  budgets, exact retail hash pin, and all hardware pass criteria remain
  unchanged.
- **No compile or hardware run occurred in this selector attempt.**
- **Next:** rerun Phase 3J with bounded nested RET-N support.

### 2026-10-18 — Phase 3J RET-N relaxation correction

- The first rerun after documenting bounded nested RET-N support still printed
  `ret-N member deferred from first closed cluster` 380 times.
- Inspection showed the previous patch had updated the root-return rule but left
  the generic per-member surface filter's old unconditional RET-N rejection in
  place.
- That stale member filter is now removed.
- Nested members now genuinely accept parsed RET-N cleanup <= 64 bytes.
- The root still requires exactly one plain RET and no RET-N.
- Verified the stale rejection string no longer exists in the selector.
- Fix commit: `42be8dc0d0b6423104e2b140c6c1330d558c8430`.
- The preceding rerun therefore did **not** test the intended RET-N relaxation;
  no conclusion should be drawn from its unchanged 380-entry RET-N count.

### 2026-10-18 — Phase 3J RET marker comment-strip correction

- The first rerun with the stale RET-N filter removed produced 996
  `no translated RET` rejections.
- Inspection confirmed another selector-only bug: translated RET identity is
  emitted by the lifter in generated comments (`/* ret */`, `/* ret N */`),
  but the new return classifier was searching the comment-stripped executable
  copy.
- RET classification now reads the raw generated source while helper/runtime
  and control-flow scans continue using the comment-stripped copy.
- The root plain-RET check was corrected the same way.
- Added selector startup invariants proving the RET/RET-N regexes match raw
  lifter output and intentionally do not survive comment stripping.
- Fix commit: `fbc90cddf3a187dc9c0b176a646b8ec051c69ade`.
- The preceding 996-entry `no translated RET` histogram was therefore not a
  real retail-code limitation.

### 2026-10-18 — Phase 3J-A first hardware run reaches real 6-function closure

- Build `P3J-CLOSURE-20261018-A` selected and executed a real automatically
  chosen dependency-closed cluster on modified Xbox 360 hardware.
- Selected root: `0x000B2080`.
- Static closure: **6 translated functions**, dependency depth **2**.
- All three deterministic cases executed fault-free.
- High-RAM canaries survived every run.
- Root returned with exact expected guest ESP `0x008B4004`.
- A/B translated traces matched for all cases.
- A/B complete 64 MiB guest-RAM hashes matched for all cases:
  - case 0: `B1BB8502E837B4EF`
  - case 1: `27269D03DBB0B4EF`
  - case 2: `E83F01493C3DB4EF`
- The only failed gate was member execution coverage: each seed executed **2/6**
  selected members.
- This is therefore **not** a Phase 3J pass, but it is also not a translated
  runtime/ABI failure.
- The original coverage rule came from the earlier branchless design and was
  too strict once real forward conditional paths were admitted: mutually
  exclusive dependencies cannot all execute in one branch path.
- Build B keeps the strong requirement at suite level:
  - every deterministic profile runs twice and must match trace, architecture,
    exact root ESP, canaries, fault state and full 64 MiB RAM hash
  - the union of all deterministic profile coverage must execute **every**
    selected closure member on hardware
- Build B expands to 12 safe branch-driving profiles and logs:
  - exact selected member VA table
  - per-profile translated trace
  - per-profile coverage mask
  - final suite coverage mask
  - any still-missing member VAs
- Build B tag: `P3J-CLOSURE-20261018-B`.
- **Phase 3J remains in progress.**

### 2026-10-18 — Phase 3J COMPLETE — dependency-closed cluster hardware PASS

- Build `P3J-CLOSURE-20261018-B` passed on modified Xbox 360 hardware.
- Automatically selected root: `0x000B2080`.
- Static closure: **6 translated retail functions**, dependency depth **2**.
- Selected member VAs:
  - `0x000AE4E0`
  - `0x000AE510`
  - `0x000AE540`
  - `0x000B14D0`
  - `0x000B2080` (root)
  - `0x00209720`
- The 12-profile deterministic suite reached union coverage **6/6**
  (`mask=0x0000003F`).
- Multiple individual profiles (including profiles 2, 3, 5, 7, 8, 9, 10 and
  11) independently executed all six members.
- Every A/B profile pair matched translated trace, final architecture and the
  complete 64 MiB guest-RAM hash.
- Every profile remained free of guest-memory faults, preserved high-RAM
  canaries and returned with exact guest ESP `0x008B4004`.
- Final markers:
  - `SUITE COVERAGE: 6/6 mask=0000003F expected=0000003F`
  - `PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER RESULT: PASS`
  - `[XAPI RETURN VALUE] 0`
- **Phase 3J is complete.**
- **Next:** Phase 3K — widen to real branch/flags and mixed ABI/FP surfaces.

### 2026-10-18 — Phase 3K mixed control/flags + FP gate prepared

- Created `xbox360/phase3k-wider-control-fp-cluster` from the completed Phase
  3J hardware-pass head.
- 3K-A selects a **new** 5–10 function dependency-closed real retail cluster
  with dependency depth >= 2.
- All Phase 3E–3J hardware-proven function VAs are excluded from selection.
- A valid cluster must contain both:
  - real conditional/flag control flow
  - supported x87 or XMM/SSE architectural state
- The selector admits previously hardware-proven explicit float/double guest
  memory and XMM helper surfaces while still rejecting dynamic ICALL/ITAIL,
  backward loops, MMX, broad runtime copy paths and advanced x87 transcendental
  behavior.
- The XDK harness now seeds and compares integer registers, x87 stack/top,
  XMM0–XMM7, translated trace, coverage and complete 64 MiB guest RAM.
- The final Phase 3J branch-profile suite is expanded from 12 to **16**
  deterministic profiles; the added profiles use safe IEEE-754 patterns to
  drive real FP branches/state.
- Per-profile A/B must match exact x87/XMM bits in addition to the existing
  trace/architecture/full-RAM determinism rules.
- Union coverage across the 16 profiles must execute every selected cluster
  member.
- Exact retail SHA verification and per-body explicit guest-memory audit remain
  mandatory.
- Build tag: `P3K-MIXEDFP-20261018-A`.
- **Next:** run `Prepare-Phase3K.ps1`; if no mixed-state closure survives,
  use its concrete rejection histogram for the narrowest next relaxation.

### 2026-10-19 — Phase 3K mixed control/flags + FP hardware gate PASS

- Automatically selected real retail root `0x001F3400` with **7 members** and
  dependency depth **2**.
- Selected closure members:
  `0x001F3400`, `0x0020F910`, `0x0020F920`, `0x0022F31D`,
  `0x0022F3F3`, `0x0022F49E`, `0x0022F561`.
- The closure contains both real conditional/flag control flow and mixed
  x87/XMM/SSE architectural state.
- The standalone XDK harness was corrected to own and compare x87 control/status
  words in addition to x87 stack/top and XMM0–XMM7.
- A Xenon XDK compiler C1001 optimizer crash on the wider generated root was
  worked around by disabling optimization only around mechanically translated
  cluster bodies; the harness remains under project-default optimization.
- All **16/16** deterministic A/B profiles completed without guest-memory faults.
- Every profile executed **7/7** selected members with identical translated traces.
- Every repeated pair matched integer registers, x87 stack/top/control/status,
  all XMM lanes, and the complete **64 MiB guest-RAM hash**.
- Final markers:
  - `SUITE COVERAGE: 7/7 mask=0000007F expected=0000007F`
  - `PHASE 3K WIDER CONTROL + MIXED FP CLUSTER RESULT: PASS`
  - `[XAPI RETURN VALUE] 0`
- **Phase 3K is complete.**
- **Next:** Phase 3L — admit bounded real backward guest control flow / loops
  under a hard execution budget so no candidate can hang modified hardware.

### 2026-10-19 — Phase 3L bounded backward-control hardware gate PASS

- Automatically selected real retail root `0x000CE310` with **9 members** and
  dependency depth **2**.
- Selected closure members:
  `0x000C87B0`, `0x000C87D0`, `0x000C87F0`, `0x000C8E20`,
  `0x000C8F80`, `0x000C91C0`, `0x000CA6B0`, `0x000CDF90`,
  `0x000CE310`.
- Phase 3L admitted ordinary backward guest branches while retaining the Phase
  3K mixed integer/flags/x87/XMM closure requirements.
- Every generated guest basic-block label was guarded by a **4096-entry**
  execution budget so an unexpected retail loop could not hang the console.
- All **16/16** deterministic A/B hardware profiles completed without
  guest-memory faults or budget exhaustion.
- Every profile executed **9/9** selected members.
- Every profile executed **1,084 real backward edges** and consumed **1,117 /
  4,096** budget ticks.
- Suite total: **17,344 backward-edge executions**.
- Repeated runs matched translated trace, integer state, x87 state, XMM state,
  high-RAM canaries and complete **64 MiB guest-RAM hashes**.
- Final markers:
  - `SUITE COVERAGE: 9/9 mask=000001FF expected=000001FF`
  - `SUITE BACKEDGES: 17344`
  - `PASS: deterministic profile suite executes at least one real backward guest edge`
  - `[XAPI RETURN VALUE] 0`
- The first emitted 3L hardware build retained stale human-readable `PHASE 3K`
  START/RESULT/END text, but its prefix, build tag, budget/backedge instrumentation
  and all 3L-only proof fields were correct. The label-only bug was fixed after
  the hardware pass in commit `6ae0b2c6424cbdcd963ccc8ca283b328600622c8`.
- **Phase 3L is complete.**
- **Next:** Phase 3M — real x87 rounding and exceptional-path coverage.

### 2026-10-19 — Phase 3M x87 rounding + exceptional-path hardware gate PASS

- Final hardware build: `P3M-X87ROUND-20261019-D`.
- Automatically selected real retail root `0x000A5AF0` with **9 members** and
  dependency depth **3**.
- The independent helper preflight passed all four x87 rounding-control modes,
  finite inexact precision status, NaN integer-indefinite + IE without PE,
  Infinity invalid conversion and out-of-range invalid conversion.
- The retail closure executed real x87 rounding/conversion code; suite total:
  **11 x87 rounding/conversion calls**.
- Initial 3M-A/B coverage exposed retail member `0x0020BDC0` as dependent on
  outside queue-producer state. Build B injected only the producer flag and
  remained 8/9; build C modeled a non-empty queue but deliberately failed the
  4096-tick guard at 4098/4096 because its synthetic queue window was too large.
- Build D modeled exactly one **0x18-byte queue entry**. Profile 16 then executed
  `0x0020D450 -> 0x0020BDC0`, reached **9/9** coverage, stayed within budget at
  **4056/4096**, preserved exact root-return ESP, and matched A/B integer,
  x87/XMM and complete 64 MiB guest-RAM state.
- Final suite markers:
  - `SUITE COVERAGE: 9/9 mask=000001FF expected=000001FF`
  - `SUITE BACKEDGES (optional): 4609`
  - `SUITE X87 ROUNDING CALLS: 11`
  - `PHASE 3M X87 ROUNDING + EXCEPTION CLUSTER RESULT: PASS`
  - `[XAPI RETURN VALUE] 0`
- **Phase 3M is complete.**
- **Next:** Phase 3N — final Gate-3 consolidation: full generated-tree audit plus
  compiler/linker/runtime scale proof. If 3N passes, Phase 3 closes and work
  advances to Phase 4 native platform/kernel services.

### 2026-10-19 — Phase 3N-B closes Gate 3

- Final Phase 3 scale proof compiled/linked a **128-function audited translated-code pack**.
- All translated anchors were present in the loaded XEX.
- Maintained x87 rounding/exception checks passed.
- Retail function `0x00208F30` passed six independent-reference executions.
- Final result: **Phase 3 / Gate 3 PASS**, clean XAPI return value 0.

### 2026-10-19 — Phase 4A + 4B-A/A2 timing/sync migration PASS

- Exact verified-retail kernel surface: **111 imports**.
- Locked Phase 4A classification: **74 explicit bridges / 11 data exports / 26 fallbacks**.
- Baseline semantic host surface: **17** direct host-backed callable paths.
- Build `P4B-TIMESYNC-20261019-B` passed on real Xbox 360 hardware.
- Six timing/synchronization imports were routed through the shared
  `merc_platform_*` backend.
- A2 verifier passed at **11 direct host-backed / 6 platform-bound**, with
  zero ABI metadata errors and zero referenced fallbacks.

### 2026-10-19 — Phase 4B-B/B2 file-handle migration PASS

- Build `P4B-FILE-20261019-A` passed every bounded file/handle check on real
  Xbox 360 hardware: create/open, write/flush, size/query, seek/current offset,
  full and offset reads, truncate/reopen, attributes, directory enumeration,
  not-found behavior and cleanup.
- Nine retail file/handle imports were routed through
  `src/platform/kernel_file_io.*`.
- Full B2 verification passed: timing/deadline regression, canonical
  guest-kernel ABI regression, time/sync boundary regression and all four
  file/handle boundary tests.
- Current exact service split: **2 direct host-backed / 15 platform-bound**,
  with zero ABI metadata errors and zero referenced fallbacks.
- **Next:** Phase 4B-C — migrate `NtFreeVirtualMemory` and
  `MmSetAddressProtect`, then prepare the first real translated-game startup
  path.

### 2026-10-19 — Phase 4B-C memory/protection hardware PASS

- Build `P4B-MEMPROT-20261019-B` passed on real Xbox 360 hardware.
- Guest allocation, per-page protection, adjacent-page isolation,
  decommit/recommit, tracked release, stale/double-release rejection,
  released-range reuse, zero-initialized reuse and bounds rejection all passed.
- The production bridge now pairs virtual allocation/release through the
  page-backed guest allocator and models protection as guest page metadata.
- **Active:** Phase 4B-C2 final service verification, targeting
  **0 direct host-backed / 15 platform-bound / 2 guest-native**.

### 2026-10-19 — Phase 4B-C2 closes the service-migration surface

- Exact verified-retail audit remains **111 imports / 74 explicit bridges /
  11 data exports / 26 return-zero fallbacks**.
- Final service accounting: **0 direct host-backed / 15 platform-bound /
  2 guest-native**.
- ABI metadata remains **0 missing / 0 mismatched** and the preserved Phase-3N
  tree still has **0 referenced fallbacks**.
- The 7,722-case timing/deadline regression passed.
- Canonical guest-kernel ABI, time/sync boundary, file/handle boundary and all
  six guest-memory ownership regressions passed.
- **Phase 4B service migration is complete.**
- **Next:** Phase 4C — execute the first real retail-derived translated
  Mercenaries startup path on Xbox 360 hardware.

### 2026-10-19 — Phase 4C-A startup preflight ready

- Active branch: `xbox360/phase4c-native-startup`.
- The preflight roots at the verified retail entry `0x0022964A`.
- It consumes the exact locked Phase-3N-A generated tree and refuses to run
  unless the final Phase-4B service audit remains
  **0 direct / 15 platform-bound / 2 guest-native**.
- It emits an entry-rooted direct translated closure manifest, missing
  dependency report, and dynamic/indirect boundary list without executing
  retail code.
- **Next evidence:** use that manifest to build the first bounded native
  startup XEX.

### 2026-10-19 — Phase 4C-A entry-rooted startup closure PASS

- Retail XBE entry `0x0022964A` resolves exactly to translated
  `xbe_entry_point` (`0x0022964A:0x002296BC`).
- Direct startup closure: **40 translated bodies**, maximum depth **8**.
- Reachable retail guest code: **5,918 bytes**.
- Reachable generated source: **111,376 bytes**.
- Missing direct translated dependencies: **0**.
- Dynamic/indirect-boundary bodies: **14**.
- **Phase 4C-A structural result: PASS.**
- **Next:** Phase 4C-B emits a two-source XDK package combining the exact
  Phase-2E retail environment and the 40-body translated closure. Runtime
  enters the real XBE entry and escapes at the first live ICALL/ITAIL so the
  next startup dependency is captured deterministically.

### 2026-10-19 — Phase 4C-B startup helper surface classified

- The first 4C-B package emission intentionally stopped on nine unsupported
  direct helper references before producing an XEX.
- Four addresses are canonical maintained manual runtime functions:
  `0x0022B150` / `0x0022B178` (Xbox LastError) and
  `0x0022DDA4` / `0x0022E51F` (retail heap allocate/free).
- The remaining helper surfaces are guest-aware `XBOX_REP_MOVS` and generated
  `__debugbreak`.
- The 4C-B emitter now packages the manual entry points and REP MOVS semantics;
  a live debug break becomes a deterministic diagnostic escape instead of a
  raw XEX trap.
- The bounded title heap uses the maintained initial arena
  `0x008C1000..0x009C0000`; unexpected exhaustion is reported explicitly.
- **Phase 4C-B remains active:** regenerate the package, then build both emitted
  C++ sources into one XEX.

### 2026-10-19 — Phase 4C-B transformed-helper audit corrected

- The startup emitter already rewrote generated `__debugbreak()` calls to the
  bounded `PHASE4C_DEBUGBREAK()` diagnostic escape.
- The helper validator was still inspecting the pre-transform generated body,
  so it falsely rejected `__debugbreak` as unresolved.
- Validation now runs against the exact transformed source emitted into the XDK
  package. Phase 4C-B package preparation remains active.

### 2026-10-19 — Phase 4C-B first real translated startup execution PASS

- Exact retail XBE verification and Phase-2E guest environment both passed on
  real Xbox 360 hardware.
- The XEX entered real translated `xbe_entry_point` at `0x0022964A`.
- Execution reached the first live indirect boundary after five translated
  block ticks with `fault=0`.
- Boundary: caller `0x0022B4D7` -> target `0x800000FF`.
- `0x800000FF` is kernel ordinal **255**, `PsCreateSystemThreadEx`.
- Observed `saved_esp - esp = 0x2C`, exactly ten 32-bit arguments plus the
  four-byte synthetic CALL return slot.
- **Phase 4C-B hardware result: PASS.**
- **Next:** Phase 4C-C follows the first startup-thread handoff and captures
  the next live dependency.

### 2026-10-19 — Phase 4C-C thread-handoff package ready

- The hardware-proven 4C-B emitter remains unchanged/reproducible.
- A separate 4C-C emitter now packages the maintained startup roots
  `0x0022B43F` and `0x002295D6` plus their direct generated closures.
- Runtime decodes the actual `PsCreateSystemThreadEx` frame, validates its
  44-byte shape, logs StartRoutine/context values, and enters the live packed
  StartRoutine synchronously.
- Output is isolated under
  `build\phase4c_native_startup\thread_xdk`.
- Build tag: `P4C-THREAD-20261019-A`.

### 2026-10-19 — Phase 4C-C narrowed to live thread-target capture

- The first 4C-C emitter recursively packed both static startup candidates and
  correctly failed its helper-surface audit after pulling renderer/audio/XACT/
  XInput/runtime support into the package.
- 4C-C now reuses the exact hardware-proven 40-body 4C-B entry closure.
- It intercepts only kernel ordinal 255, requires the proven 44-byte frame,
  decodes all ten `PsCreateSystemThreadEx` arguments, and records the actual
  StartRoutine/context values.
- A valid `THREAD_TARGET` stop is the 4C-C PASS condition.
- New build tag: `P4C-THREAD-20261019-B`.
- The following phase will package only the hardware-observed StartRoutine.

### 2026-10-19 — Phase 4C-C live startup-thread handoff PASS

- Real Xenon captured the complete `PsCreateSystemThreadEx` argument frame.
- Live values: StartRoutine `0x0022B43F`, ctx1 `0x002295D6`,
  ctx2 `0x00000000`.
- Kernel stack request: **262,144 bytes**; TLS size: **20 bytes**.
- Frame delta remained exactly **0x2C** bytes and guest fault state remained 0.
- Evidence boundary:
  `THREAD_TARGET caller=0x0022B4D7 target=0x0022B43F`.
- **Phase 4C-C hardware result: PASS.**
- **Next:** Phase 4C-D analyzes only `0x0022B43F` before building the first
  translated title-thread execution slice.

### 2026-10-19 — Phase 4C-D first title-thread preflight PASS

- Hardware-observed StartRoutine `0x0022B43F` resolves as an exact translated
  function.
- Direct closure: **6 bodies**, maximum depth **2**.
- Reachable retail guest code: **460 bytes**.
- Generated source: **8,556 bytes**.
- Missing direct translated dependencies: **0**.
- Dynamic/indirect-boundary bodies: **5**.
- Three of the six bodies already belong to the hardware-proven entry closure,
  so the Phase 4C-E continuous package contains **43 unique translated bodies**.
- **Next:** execute from real `xbe_entry_point` through ordinal 255 into
  `0x0022B43F` with the hardware-captured contexts and stop at the next live
  dynamic/kernel boundary.
- Build tag: `P4C-THREADRUN-20261019-A`.

### 2026-10-19 — Phase 4C-E first title-thread execution PASS

- Real Xenon executed continuously through the genuine XBE entry,
  `PsCreateSystemThreadEx`, and hardware-observed title-thread routine
  `0x0022B43F`.
- Trace advanced through `0x00239BE8` to caller `0x0022B363`.
- Next live target: `0x80000115` = kernel ordinal **277**,
  `RtlEnterCriticalSection`.
- Observed `saved_esp - esp = 0x8`, exactly one 32-bit argument plus the
  four-byte translated CALL return slot.
- Guest fault state remained 0.
- **Phase 4C-E hardware result: PASS.**
- **Next:** Phase 4C-F applies the maintained serialized-guest no-op semantics
  for ordinal 277 and continues to the next live boundary.
- Build tag: `P4C-CRITCONT-20261019-A`.

### 2026-10-19 — Phase 4C-F critical-section enter PASS

- Real title-thread execution continued through kernel ordinal **277**,
  `RtlEnterCriticalSection`.
- Live guest critical-section VA: `0x00312FC0`.
- Observed frame: `esp=0x008BFF3C`,
  `saved_esp=0x008BFF44`, exact **8-byte** delta.
- Maintained serialized-guest no-op semantics completed and stack balance held.
- Next live target: `0x80000126` = ordinal **294**,
  `RtlLeaveCriticalSection`.
- Guest fault state remained 0.
- **Phase 4C-F hardware result: PASS.**
- **Next:** Phase 4C-G continues through the matching leave call.
- Build tag: `P4C-CRITPAIR-20261019-A`.

### 2026-10-19 — Phase 4C-G critical-section pair PASS

- Real Xenon executed both `RtlEnterCriticalSection` and
  `RtlLeaveCriticalSection` against guest CS `0x00312FC0`.
- Both calls used exact 8-byte translated frames and balanced the simulated
  stack correctly.
- Guest fault state remained 0.
- Next live ICALL: caller `0x0022B363` -> target `0x002295D6`.
- `0x002295D6` exactly matches the ctx1 value captured from the real
  `PsCreateSystemThreadEx` frame, proving it is subsequently invoked as
  executable startup code.
- **Phase 4C-G hardware result: PASS.**
- **Next:** Phase 4C-H enters that callback with a bounded direct-call frontier.
- Build tag: `P4C-CALLBACK-20261019-A`.

### 2026-10-19 — Phase 4C-H enters real startup callback, exposes guest fault

- Real Xenon entered the hardware-confirmed callback `0x002295D6`.
- Callback trace advanced to `0x0022C4DF`.
- Execution then stopped at a deterministic `GUEST_FAULT`, observed at
  translated VA `0x0022C4FF`.
- Fault boundary stack was balanced:
  `esp=0x008BFF48`, `saved_esp=0x008BFF48`.
- Guest fault flag was 1, so **Phase 4C-H is not a PASS**.
- The current harness did not preserve the rejected guest address itself.
- **Next:** Phase 4C-I records the first rejected guest address, access width,
  direction, and caller without changing guest-memory validity.
- Build tag: `P4C-FAULTPROBE-20261019-B`.

### 2026-10-19 — Phase 4C-I Build A superseded by hardened probe

- Probe A reached the hardware-confirmed callback `0x002295D6` and then hung
  before recording fault provenance.
- Review found the diagnostic transform used loose accessor-name matching and
  could anchor on earlier helper uses rather than the exact accessor definition.
- Build B now replaces exact accessor body fragments only.
- First rejected guest access is logged immediately inside the accessor as
  `FAULT ACCESS IMMEDIATE: READ|WRITE width=N guest=XXXXXXXX`.
- Guest mapping/validity semantics are unchanged.
- Active build tag: `P4C-FAULTPROBE-20261019-B`.

### 2026-10-19 — Phase 4C-I first-fault provenance PASS

- Hardened Build B captured the callback's first rejected guest access:
  **READ32 `0x80000142`**.
- Translated caller: `0x0022C4DF`.
- `0x142` is kernel ordinal **322**, `XboxHardwareInfo`, a DATA export.
- The production bridge already maps ordinal 322 to guest kernel-data storage.
- Phase-2E already initializes `XboxHardwareInfo` at guest VA
  `0x0087E000`; the missing step is data-import thunk relocation.
- **Phase 4C-I diagnostic result: PASS.**
- **Next:** Phase 4C-J relocates only ordinal 322, validates the exact
  111-import table/terminator and hardware-info readback, then resumes startup.
- Build tag: `P4C-HWINFO-20261019-A`.

### 2026-10-19 — Phase 4C-J XboxHardwareInfo relocation PASS

- Real hardware relocated ordinal **322** `XboxHardwareInfo` at thunk slot
  `0x002DBE0C`: `0x80000142 -> 0x0087E000`.
- The previous 4C-I fault disappeared.
- The next rejected access was **READ16 `0x80000148`** from
  `0x0022C4DF`, with `ECX=0x80000144`.
- `0x80000144` is raw ordinal **324**, `XboxKrnlVersion`; the +4 read is
  its 16-bit Build field.
- Phase-2E already initializes `XboxKrnlVersion` as 1.0.5849.0 at
  `0x0087E010`.
- **Phase 4C-J hardware result: PASS.**
- **Next:** Phase 4C-K relocates the three DATA imports explicitly initialized
  by Phase-2E: 156/322/324, while preserving immediate first-fault telemetry.
- Build tag: `P4C-KDATA3-20261019-A`.

### 2026-10-19 — Phase 4C-K startup DATA relocations PASS

- Real Xbox 360 hardware relocated exact startup DATA imports:
  - ordinal 156 `KeTickCount`: `0x8000009C -> 0x0087E020`;
  - ordinal 322 `XboxHardwareInfo`: `0x80000142 -> 0x0087E000`;
  - ordinal 324 `XboxKrnlVersion`: `0x80000144 -> 0x0087E010`.
- The callback advanced beyond both previous data-import failures.
- Next boundary:
  `DIRECT_FRONTIER caller=0x0022C4DF target=0x0022C47B`.
- Stack remained balanced and guest fault state was 0.
- **Phase 4C-K hardware result: PASS.**
- **Next:** Phase 4C-L promotes only `0x0022C47B` into the translated pack.
- Build tag: `P4C-DIRECTC47B-20261019-A`.

### 2026-10-19 — Phase 4C-L promoted direct target PASS

- Real Xbox 360 hardware executed promoted translated body `0x0022C47B`.
- First new dependency: **READ32 `0x8001003C`**.
- Boundary caller: `0x0022C47B`.
- Stack remained balanced at `0x008BFF40`.
- The address falls inside the intentionally fenced original-Xbox kernel image
  page at `0x80010000`, not the kernel ordinal-token range.
- **Phase 4C-L hardware result: PASS.**
- **Next:** Phase 4C-M supplies a separate minimal xboxkrnl PE-header page
  (MZ, `e_lfanew=0x80`, PE signature, i386, zero sections) while preserving
  all prior startup data relocations and fault telemetry.
- Build tag: `P4C-KHDR-20261019-A`.

### 2026-10-19 — Phase 4C-M kernel-header model PASS

- Synthetic xboxkrnl PE-header page at `0x80010000` passed readback.
- The previous READ32 `0x8001003C` blocker disappeared.
- Startup advanced through translated `0x0022C47B` into `0x0022C28B`.
- New boundary: `ICALL_SAFE caller=0x0022C28B target=0x8000002F`.
- Frame: `esp=0x008BFEFC`, `saved_esp=0x008BFF08`, delta 12 bytes.
- Guest fault state remained 0.
- Ordinal 47 is `HalRegisterShutdownNotification`; production ABI metadata
  requires 8 argument bytes, matching the live frame exactly.
- **Phase 4C-M hardware result: PASS.**
- **Next:** Phase 4C-N validates/logs the live registration frame, mirrors the
  production no-callback semantics, returns `eax=0`, and resumes startup.
- Build tag: `P4C-HAL47-20261019-A`.

### 2026-10-19 — Phase 4C-N ordinal-47 continuation PASS

- Live `HalRegisterShutdownNotification` frame:
  registration `0x003134C0`, Register=1.
- Frame delta 12 exactly matched the production 8-byte ABI plus synthetic return.
- Handler matched production no-callback semantics and returned `eax=0`.
- Startup resumed cleanly with guest fault state 0.
- Next boundary:
  `DIRECT_FRONTIER caller=0x0022C28B target=0x0022F128`.
- **Phase 4C-N hardware result: PASS.**
- **Next:** Phase 4C-O promotes only `0x0022F128`.
- Build tag: `P4C-DIRECTF128-20261019-A`.

### 2026-10-19 — Phase 4C-O promoted F128 PASS

- Real Xbox 360 hardware executed promoted translated body `0x0022F128`.
- New boundary:
  `ICALL_SAFE caller=0x0022F128 target=0x8000006B`.
- Frame: `esp=0x008BFEE4`, `saved_esp=0x008BFEF4`, delta 16 bytes.
- Guest fault state remained 0.
- Ordinal 107 is `KeInitializeDpc`; production ABI metadata requires
  12 argument bytes, exactly matching the live frame plus synthetic return.
- Production bridge initializes a 32-byte guest KDPC:
  Type `0x13`, DeferredRoutine at +12, DeferredContext at +16.
- **Phase 4C-O hardware result: PASS.**
- **Next:** Phase 4C-P reproduces that guest KDPC initialization and continues.
- Build tag: `P4C-DPC107-20261019-A`.

### 2026-10-19 — Phase 4C-P KeInitializeDpc PASS

- Live DPC frame:
  `dpc=0x00869580`, `routine=0x0022F116`, `context=0`.
- The production 32-byte KDPC initialization and readback passed on hardware.
- Startup resumed with guest fault state 0.
- New boundary:
  `ICALL_SAFE caller=0x0022F128 target=0x80000071`.
- Frame delta 12 bytes = 8 argument bytes + synthetic return.
- Ordinal 113 is `KeInitializeTimerEx(PKTIMER, TIMER_TYPE)`.
- **Phase 4C-P hardware result: PASS.**
- **Next:** Phase 4C-Q initializes the 40-byte guest KTIMER exactly as the
  production bridge does and introduces a main/env link-time build cookie.
- Build tag: `P4C-TIMER113-20261019-A`.

### 2026-10-19 — Phase 4C-Q KeInitializeTimerEx PASS

- Q main/env link-time build cookie matched on hardware.
- Live timer frame:
  `timer=0x008695A0`, `type_raw=0`, TimerType=0.
- Production 40-byte guest KTIMER initialization and readback passed.
- Startup resumed with guest fault state 0.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022F128 target=0x0022C5A4`.
- Stack remained balanced at `0x008BFEDC`.
- **Phase 4C-Q hardware result: PASS.**
- **Next:** Phase 4C-R promotes only `0x0022C5A4` and rotates the build cookie.
- Build tag: `P4C-DIRECTC5A4-20261019-A`.

### 2026-10-19 — Phase 4C-R promoted C5A4 PASS

- R main/env link-time build cookie matched on hardware.
- The entire proven startup chain remained intact through ordinal 113
  `KeInitializeTimerEx`.
- Promoted translated target `0x0022C5A4` executed on hardware.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022C5A4 target=0x00230060`.
- Boundary state remained clean: `fault=0`, ESP/saved ESP `0x008BFEC0`.
- Trace extended to 11 translated functions through `0x0022C5A4`.
- **Phase 4C-R hardware result: PASS.**
- **Next:** Phase 4C-S promotes only `0x00230060`.
- Build tag: `P4C-DIRECT30060-20261019-A`.

### 2026-10-19 — Phase 4C-S promoted 30060 PASS

- S main/env link-time build cookie matched on hardware.
- The proven startup chain remained intact through ordinal 113
  `KeInitializeTimerEx`.
- Promoted translated target `0x00230060` executed on hardware.
- New boundary:
  `ITAIL caller=0x00230060 target=0x80000018`.
- Target `0x80000018` is kernel ordinal 24,
  `ExQueryNonVolatileSetting`.
- Boundary state remained clean: `fault=0`, ESP/saved ESP `0x008BFEC0`.
- Trace extended to 12 translated functions through `0x00230060`.
- **Phase 4C-S hardware result: PASS.**
- **Next:** Phase 4C-T validates and continues ordinal 24 in-place.
- Build tag: `P4C-NV24-20261019-A`.

### 2026-10-19 — Phase 4C-T ExQueryNonVolatileSetting PASS

- T main/env link-time build cookie matched on hardware.
- The proven startup chain remained intact through ordinal 113 and the promoted
  `0x00230060` function.
- Live ordinal-24 tail frame:
  `ret=0`, `index=0x11 (XC_MISC)`, value length 4.
- The guest EEPROM continuation returned STATUS_SUCCESS and cleaned the
  24-byte tail frame to `ESP=0x008BFED8`.
- New boundary:
  `ICALL_SAFE caller=0x00230060 target=0x8000012D`.
- Target `0x8000012D` is kernel ordinal 301,
  `RtlNtStatusToDosError`.
- Boundary state remained clean: `fault=0`.
- **Phase 4C-T hardware result: PASS.**
- **Next:** Phase 4C-U validates and continues ordinal 301 in-place.
- Build tag: `P4C-RTL301-20261019-A`.

### 2026-10-19 — Phase 4C-U RtlNtStatusToDosError PASS

- U main/env link-time build cookie matched on hardware.
- The proven startup chain remained intact through ordinal 24
  `ExQueryNonVolatileSetting`.
- Live ordinal-301 frame:
  `ret=0`, `status=STATUS_SUCCESS`, expected 8-byte call frame.
- The runtime bridge mapping returned DOS error 0 and restored
  `ESP=0x008BFED8`.
- New boundary:
  `DIRECT_FRONTIER caller=0x00230060 target=0x0022F0FB`.
- Boundary state remained clean: `fault=0`.
- **Phase 4C-U hardware result: PASS.**
- **Next:** Phase 4C-V promotes a bounded depth-2 direct closure rooted at
  `0x0022F0FB` to reduce one-function-per-boot churn.
- Build tag: `P4C-F0FB-CLOSURE-20261019-A`.

### 2026-10-19 — Phase 4C-V direct closure PASS

- V main/env build cookie matched on hardware.
- The proven startup chain remained intact through ordinals 24 and 301.
- Promoted translated target `0x0022F0FB` executed, extending the trace to
  13 translated functions.
- New boundary:
  `ICALL_SAFE caller=0x0022F0FB target=0x80000095`.
- Target `0x80000095` is kernel ordinal 149, `KeSetTimer`.
- The live stack delta is 20 bytes, matching the locked ABI:
  dummy return + 16 bytes of stdcall arguments.
- Boundary state remained clean: `fault=0`.
- **Phase 4C-V hardware result: PASS.**
- **Next:** Phase 4C-W validates and continues ordinal 149 in-place.
- Build tag: `P4C-TIMER149-20261019-A`.

### 2026-10-19 — Phase 4C-W KeSetTimer PASS

- W main/env link-time build cookie matched on hardware.
- The proven startup chain remained intact through the translated
  `0x0022F0FB` function.
- Live ordinal-149 frame matched the locked ABI:
  dummy return + 16 argument bytes = 20 bytes.
- Guest KTIMER `0x008695A0` was armed with DPC `0x00869580`;
  the prior-active return was FALSE.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022F0FB target=0x0022D980`.
- Boundary state remained clean: `fault=0`.
- **Phase 4C-W hardware result: PASS.**
- **Next:** Phase 4C-X promotes a bounded depth-2 direct closure rooted at
  `0x0022D980`.
- Build tag: `P4C-D980-CLOSURE-20261019-A`.

### 2026-10-19 — Phase 4C-X D980 PASS

- X main/env build cookie matched on hardware.
- All proven startup continuations through ordinal 149 `KeSetTimer` remained
  intact.
- Translated root `0x0022D980` executed.
- Control re-entered translated function `0x00239BE8`.
- New boundary:
  `DIRECT_FRONTIER caller=0x00239BE8 target=0x00238C00`.
- The trace reached 15 translated entries with `fault=0`.
- **Phase 4C-X hardware result: PASS.**
- **Next:** Phase 4C-Y promotes only `0x00238C00`.
- Build tag: `P4C-DIRECT38C00-20261019-A`.

### 2026-10-19 — Phase 4C-Y CRT memmove PASS

- Y main/env cookie matched on hardware.
- All prior startup continuations remained intact through ordinal 149.
- Translated root `0x00238C00` executed.
- Maintained `recomp_crt_memmove` live frame:
  `dest=0x008BFE70 src=0x008BFF14 len=48`.
- The helper returned the destination and consumed only the cdecl synthetic
  return slot as intended.
- New boundary:
  `ICALL_SAFE caller=0x00238C00 target=0x800000B8`.
- `0x800000B8` is ordinal 184 `NtAllocateVirtualMemory`.
- The hardware trace reached 16 translated entries with `fault=0`.
- **Phase 4C-Y hardware result: PASS.**
- **Next:** Phase 4C-Z continues ordinal 184.
- Build tag: `P4C-NTALLOC184-20261019-A`.

### 2026-10-19 — Phase 4C-Z VM-reserve boundary PASS

- Z main/env cookie matched on hardware.
- All proven entry/thread/kernel/CRT continuations remained intact.
- Live ordinal-184 frame matched 24 bytes exactly.
- Request: `Base=NULL`, `RegionSize=0x00100000`,
  `AllocationType=MEM_RESERVE (0x2000)`, `Protect=PAGE_READWRITE (0x4)`.
- The harness stopped deliberately at `VM_UNSUPPORTED`; `fault=0`.
- **Phase 4C-Z hardware result: PASS.**
- **Next:** Phase 4C-AA adds explicit reserved/uncommitted guest-page state and
  continues this exact allocation path.

### 2026-10-19 — Phase 4C-AA package ready

- Z hardware PASS identified the exact blocker as a 1 MiB
  `MEM_RESERVE` / `PAGE_READWRITE` ordinal-184 request.
- AA now models reserved/uncommitted guest pages instead of stopping at
  `VM_UNSUPPORTED`.
- Page-backed virtual allocations grow downward from the top of 64 MiB guest
  RAM, matching the production runtime allocator strategy.
- Later `MEM_COMMIT` calls preserve the reserved VA, zero newly committed
  pages, and record protection metadata.
- Reserved/uncommitted pages remain inaccessible to translated guest accesses.
- Gate:
  `ports/mercenaries/xbox360/phase4c_native_startup/Prepare-Phase4C-AA.ps1`
- Build tag: `P4C-VMRESERVE-AA-20261019-A`.

### 2026-10-19 — Phase 4C-AA reserve/commit PASS

- AA main/env cookie matched on hardware.
- The title reserved a 1 MiB guest virtual range at `0x03F00000`.
- A second ordinal-184 call committed the first 4 KiB at the same VA.
- Both `NtAllocateVirtualMemory` calls returned STATUS_SUCCESS.
- Reservation identity was preserved across reserve -> commit.
- New boundary:
  `ICALL_SAFE caller=0x00238C00 target=0x80000123`.
- `0x80000123` is ordinal 291 `RtlInitializeCriticalSection`.
- The boundary remained `fault=0`.
- **Phase 4C-AA hardware result: PASS.**
- **Next:** Phase 4C-AB continues ordinal 291.
- Build tag: `P4C-RTL291-AB-20261019-A`.

### 2026-10-19 — Phase 4C-AB RTL291 PASS

- AB main/env cookie matched on hardware.
- The working ordinal-184 reserve/commit sequence remained intact.
- Ordinal 291 `RtlInitializeCriticalSection` received the exact 8-byte frame.
- Maintained serialized-guest semantics completed successfully.
- New boundary:
  `DIRECT_FRONTIER caller=0x00238C00 target=0x0022D431`.
- The boundary remained `fault=0`.
- **Phase 4C-AB hardware result: PASS.**
- **Next:** Phase 4C-AC promotes only `0x0022D431`.
- Build tag: `P4C-DIRECTD431-AC-20261019-A`.

### 2026-10-19 — Phase 4C-AC D431 PASS

- AC main/env cookie matched on hardware.
- All proven startup/kernel/VM continuations remained intact.
- Translated root `0x0022D431` executed.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022D431 target=0x0022CA2B`.
- The translated trace reached 17 entries with `fault=0`.
- **Phase 4C-AC hardware result: PASS.**
- **Next:** Phase 4C-AD promotes only `0x0022CA2B`.
- Build tag: `P4C-DIRECTCA2B-AD-20261019-A`.

### 2026-10-19 — Phase 4C-AD CA2B PASS

- AD main/env cookie matched on hardware.
- All proven startup/kernel/VM continuations remained intact.
- Translated root `0x0022CA2B` executed.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022CA2B target=0x0022C8EA`.
- The translated trace reached 18 entries with `fault=0`.
- **Phase 4C-AD hardware result: PASS.**
- **Next:** Phase 4C-AE promotes only `0x0022C8EA`.
- Build tag: `P4C-DIRECTC8EA-AE-20261019-A`.

### 2026-10-19 — Phase 4C-AE C8EA PASS

- AE main/env cookie matched on hardware.
- All proven startup/kernel/VM continuations remained intact.
- Translated root `0x0022C8EA` executed.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022C8EA target=0x0022CEEE`.
- The translated trace reached 19 entries with `fault=0`.
- **Phase 4C-AE hardware result: PASS.**
- **Next:** Phase 4C-AF promotes only `0x0022CEEE`.
- Build tag: `P4C-DIRECTCEEE-AF-20261019-A`.

### 2026-10-19 — Phase 4 complete / Phase 5A begins

- Phase 4C-AF build `P4C-DIRECTCEEE-AF-20261019-A` passed on real Xbox 360 hardware.
- The live translated trace reached 23 entries with `fault=0`.
- Startup flowed through `0x0022CEEE -> 0x00239C23 -> 0x0022C27A -> 0x0022BD2D`.
- New live dependency: `ICALL_SAFE target=0x800000CA` = ordinal 202 `NtOpenFile`.
- The observed stack delta is 28 bytes, exactly six stdcall arguments plus the translated synthetic return.
- **Gate 4 / Phase 4: COMPLETE.**
- New active branch: `xbox360/phase5-native-subsystems`.
- **Phase 5A:** capture the exact live storage/content path and open flags before implementing native I/O.
- Build tag: `P5A-NTOPEN202-CAPTURE-20261019-A`.

### 2026-10-19 — Phase 5A storage capture PASS

- Build `P5A-NTOPEN202-CAPTURE-20261019-A` passed on real Xbox 360 hardware.
- First live storage request: ordinal 202 `NtOpenFile`.
- Caller: `0x0022BD2D`.
- Path: `\\Device\\Harddisk0\\partition1\\`.
- Access/share/options: `0x00100001 / 0x00000003 / 0x00800021`.
- Exact 28-byte full frame; guest OBJECT_ATTRIBUTES / ANSI_STRING decoded cleanly.
- Explicit `STORAGE_OPEN` boundary reached with `fault=0`.
- **Phase 5A: PASS.**
- **Next:** Phase 5B native Xenon `NtOpenFile` continuation.
- Build tag: `P5B-NTOPEN202-NATIVE-20261019-A`.

### 2026-10-19 — Phase 5B native NtOpenFile PASS

- Build `P5B-NTOPEN202-NATIVE-20261019-A` passed on real Xbox 360 hardware.
- `\\Device\\Harddisk0\\partition1\\` mapped to `game:\\merc360-partition1`.
- Native `CreateFileA` returned STATUS_SUCCESS.
- Guest handle token: `0x48000001`.
- Translated execution resumed with `fault=0`.
- New live dependency: `0x800000DA` = ordinal 218 `NtQueryVolumeInformationFile`.
- Observed full frame: 24 bytes = five stdcall arguments + synthetic return.
- **Phase 5B: PASS.**
- **Next:** Phase 5C native volume-size query + tagged-handle close support.
- Build tag: `P5C-VOLUME218-NATIVE-20261019-A`.

### 2026-10-19 — Phase 5C volume query PASS

- Build `P5C-VOLUME218-NATIVE-20261019-A` passed on real Xbox 360 hardware.
- `NtOpenFile` again returned native-backed token `0x48000001`.
- `NtQueryVolumeInformationFile` class 3 returned:
  - total allocation units: `243868976`;
  - available allocation units: `55322560`;
  - sectors per allocation unit: `32`;
  - bytes per sector: `512`.
- Ordinal 187 `NtClose` released token `0x48000001` successfully.
- New live dependency: `0x80000043` = ordinal 67 `IoCreateSymbolicLink`.
- Observed full frame: 12 bytes = two stdcall arguments + synthetic return.
- Boundary remained `fault=0`.
- **Phase 5C: PASS.**
- **Next:** Phase 5D native guest symbolic-link mount continuation.
- Build tag: `P5D-SYMLINK67-NATIVE-20261019-A`.

### 2026-10-20 — Phase 5D symbolic-link mount PASS

- Build `P5D-SYMLINK67-NATIVE-20261019-A` passed on real Xbox 360 hardware.
- The full native Partition1 open/query/close lifecycle remained intact.
- Ordinal 67 `IoCreateSymbolicLink` decoded and created:
  - link: `\\??\\D:`;
  - target: `\\Device\\CdRom0`;
  - status: `0x00000000`.
- Translated execution advanced with `fault=0` to
  `DIRECT_FRONTIER caller=0x0022BD2D target=0x0022C1C0`.
- **Phase 5D: PASS.**
- **Next:** Phase 5E exact-root promotion of `0x0022C1C0`.
- Build tag: `P5E-DIRECTC1C0-20261020-A`.

### 2026-10-20 — Phase 5E direct C1C0 PASS

- Build `P5E-DIRECTC1C0-20261020-A` passed on real Xbox 360 hardware.
- The complete native Partition1 + `D:` mount stack remained intact.
- Translated root `0x0022C1C0` executed successfully.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022C1C0 target=0x002370B8`.
- The translated trace reached 24 entries with `fault=0`.
- **Phase 5E: PASS.**
- **Next:** Phase 5F exact-root promotion of `0x002370B8`.
- Build tag: `P5F-DIRECT370B8-20261020-A`.

### 2026-10-20 — Phase 5F direct 370B8 PASS

- Build `P5F-DIRECT370B8-20261020-A` passed on real Xbox 360 hardware.
- The complete native Partition1 + `D:` mount stack remained intact.
- Translated root `0x002370B8` executed successfully.
- The translated trace expanded from 24 to 45 entries through already-packed
  initialization helpers, including repeated execution through
  `0x0023F150` and `0x0023A3CE`.
- New boundary:
  `DIRECT_FRONTIER caller=0x0023A3CE target=0x0022BE8C`.
- Boundary remained `fault=0`.
- **Phase 5F: PASS.**
- **Next:** Phase 5G exact-root promotion of `0x0022BE8C`.
- Build tag: `P5G-DIRECTBE8C-20261020-A`.

### 2026-10-20 — Phase 5G direct BE8C PASS

- Build `P5G-DIRECTBE8C-20261020-A` passed on real Xbox 360 hardware.
- The complete native Partition1 + `D:` mount stack remained intact.
- Translated root `0x0022BE8C` executed successfully.
- New live dependency:
  `ICALL_SAFE caller=0x0022BE8C target=0x800000BE`.
- Target `0x800000BE` is ordinal 190 `NtCreateFile`.
- Observed full frame: 40 bytes = nine stdcall arguments + synthetic return.
- The translated trace reached 46 entries with `fault=0`.
- **Phase 5G: PASS.**
- **Next:** Phase 5H native `NtCreateFile` + synchronous `NtReadFile`.
- Build tag: `P5H-NTCREATE190-NATIVE-20261020-A`.

### 2026-10-20 — Phase 5H TDATA NtCreateFile PASS

- Build `P5H-NTCREATE190-NATIVE-20261020-A` passed on real Xbox 360 hardware.
- Ordinal 190 `NtCreateFile` opened/created
  `\\Device\\Harddisk0\\partition1\\TDATA`.
- Native backing path: `game:\\merc360-partition1\\TDATA`.
- Create disposition: `FILE_OPEN_IF`; status `0x00000000`.
- Tagged handle `0x48000001` was closed successfully.
- Ordinal 219 `NtReadFile` was armed but not reached in this run.
- New live dependency: `0x80000121` = ordinal 289 `RtlInitAnsiString`.
- Observed full frame: 12 bytes; boundary remained `fault=0`.
- **Phase 5H: PASS.**
- **Next:** Phase 5I maintained `RtlInitAnsiString` continuation.
- Build tag: `P5I-RTLINITANSI289-20261020-A`.

### 2026-10-20 — Phase 5I title-storage hierarchy PASS

- Build `P5I-RTLINITANSI289-20261020-A` passed on real Xbox 360 hardware.
- Ordinal 289 `RtlInitAnsiString` exposed the live title-data paths.
- Created/opened `TDATA\\4c410015` with STATUS_SUCCESS.
- Mounted `\\??\\T: -> \\Device\\Harddisk0\\partition1\\TDATA\\4c410015`.
- Created/opened `UDATA` and `UDATA\\4c410015` with STATUS_SUCCESS.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022BE8C target=0x0022F026`.
- The translated trace reached 47 entries with `fault=0`.
- **Phase 5I: PASS.**
- **Next:** Phase 5J exact-root promotion of `0x0022F026`.
- Build tag: `P5J-DIRECTF026-20261020-A`.

### 2026-10-20 — Phase 5J XBE section-name path PASS

- Build `P5J-DIRECTF026-20261020-A` passed on real Xbox 360 hardware.
- The unique 5J main/environment linker-cookie guard matched correctly.
- The complete native Partition1, `D:`/`T:`, TDATA/UDATA and RTL string
  stack remained intact.
- Translated root `0x0022F026` initialized `$XTINFO` and `.text`
  `ANSI_STRING` values.
- New live dependency:
  `ICALL_SAFE caller=0x0022F026 target=0x80000117`.
- Target `0x80000117` is ordinal 279 `RtlEqualString`.
- Observed full frame: 16 bytes; trace reached 48 entries; `fault=0`.
- **Phase 5J: PASS.**
- **Next:** Phase 5K maintained `RtlEqualString` continuation.
- Build tag: `P5K-RTLEQUAL279-20261020-A`.

### 2026-10-20 — Phase 5K XBE section scan PASS

- Build `P5K-RTLEQUAL279-20261020-A` passed on real Xbox 360 hardware.
- The complete native Partition1, D:/T:, TDATA/UDATA and RTL string stack
  remained intact.
- `0x0022F026` compared `$XTINFO` against all 14 loaded XBE section names.
- Every comparison correctly returned false; the retail XBE has no
  `$XTINFO` section.
- New boundary:
  `DIRECT_FRONTIER caller=0x0022F026 target=0x0022B178`.
- The translated trace remained 48 entries and `fault=0`.
- **Phase 5K: PASS.**
- **Next:** Phase 5L reviewed maintained `SetLastError` continuation at `0x0022B178`.
- Build tag: `P5L-DIRECTB178-20261020-A`.

### 2026-10-20 — Phase 5L through 5AG native title-state progression

- Phase 5L executed the reviewed maintained Xbox `SetLastError` root
  `0x0022B178` and preserved the complete native storage/title-data/RTL path.
- Hardware-driven continuations then carried the real translated startup path
  through TitleMeta/TitleImage/SaveImage information and write handling,
  XBE image-section bookkeeping, persistent title state and root
  `0x0022A3B9`.
- Phase 5AG build `P5AG-PARTITION0-NATIVE-20261020-A` successfully opened
  `\\Device\\Harddisk0\\partition0` as
  `game:\\merc360-partition0` and returned a valid tagged handle.
- Retail immediately issued a 512-byte `NtReadFile` at byte offset
  `0x800`; the directory-backed diagnostic sandbox returned
  `STATUS_UNSUCCESSFUL (0xC0000001)`.
- That failure exposed a legitimate second call to ordinal 301
  `RtlNtStatusToDosError`.
- **Phase 5AG proof: PASS; next dependency captured.**

### 2026-10-20 — Phase 5AH repeatable status conversion PASS

- Build `P5AH-RTLSTATUS301-REPEATABLE-20261020-A` passed on real Xbox 360
  hardware with XAPI return 0.
- The original startup conversion remained correct:
  `STATUS_SUCCESS -> ERROR_SUCCESS`, call 1.
- After the Partition0 offset-`0x800` probe failed, the same ordinal executed
  again and correctly mapped
  `STATUS_UNSUCCESSFUL (0xC0000001) -> ERROR_GEN_FAILURE (31)`, call 2.
- Maintained `SetLastError` then stored `0x1F`, proving the failure path
  continued through translated code instead of escaping at the kernel thunk.
- Execution advanced through translated roots
  `0x0022C215 -> 0x0022946C -> 0x0022BA47 -> 0x0022958F -> 0x002294AE`.
- New deterministic boundary:
  `GUEST_FAULT READ32 0x800000A4` from caller `0x002294AE`.
- `0x800000A4` is ordinal 164 `LaunchDataPage`, a kernel DATA export
  pointer rather than callable code.
- **Phase 5AH: PASS.**
- **Next:** Phase 5AI relocates ordinal 164 to guest VA `0x0087E030`,
  initialized NULL, and resumes to the next hardware boundary.
- Build tag: `P5AI-LAUNCHDATAPAGE-DATA-20261020-A`.

### 2026-10-20 — Phase 5AI LaunchDataPage relocation PASS

- Build `P5AI-LAUNCHDATAPAGE-DATA-20261020-A` passed on real Xbox 360
  hardware.
- Startup data-thunk relocation added ordinal 164:
  slot `0x002DBD48`, old token `0x800000A4`, new guest-data VA
  `0x0087E030`.
- Readback proved startup data imports 156/164/322/324 all point at initialized
  guest kernel data, with `LaunchDataPage=NULL`.
- The complete prior title-storage and Partition0/error-conversion path stayed
  intact.
- The old READ32 fault at `0x800000A4` disappeared.
- New boundary:
  `ICALL_SAFE caller=0x002294AE target=0x800000A5`, stack delta 8,
  `fault=0`.
- `0x800000A5` is ordinal 165 `MmAllocateContiguousMemory`.
- **Phase 5AI: PASS.**
- **Next:** Phase 5AJ batches the guest-safe Mm cluster instead of servicing
  one memory ordinal per hardware build.

### 2026-10-20 — Phase 5AJ batched memory-manager cluster PASS

- Build `P5AJ-MM-CLUSTER-20261020-A` passed on real Xbox 360 hardware.
- The full prior startup/storage/title-state path remained intact, including
  the Partition0 probe, repeatable ordinal-301 error mapping and maintained
  `SetLastError(31)`.
- The newly batched memory-manager dispatch serviced ordinal 165
  `MmAllocateContiguousMemory` directly:
  request `4096`, rounded `4096`, guest base `0x03EFF000`,
  allocation-success count `1`.
- Execution then advanced from the same translated caller `0x002294AE` to
  `ICALL_SAFE target=0x800000B2` with `fault=0`.
- `0x800000B2` is ordinal 178 `MmPersistContiguousMemory`, whose production
  backend semantics are an explicit no-op.
- **Phase 5AJ memory-manager cluster: PASS.**
- **Next:** Phase 5AK expands the batch across the remaining straightforward
  memory persistence/protection/map/unmap/free services instead of returning
  to one-address-per-build iteration.

### 2026-10-20 — Phase 5AK expanded memory-services batch PASS

- Build `P5AK-MM-SERVICES-20261020-A` passed on real Xbox 360 hardware.
- The exact retail-XBE identity, Phase-2E execution environment, startup data
  relocations, storage/title-state chain and repeatable status mapping all
  remained intact.
- Ordinal 165 `MmAllocateContiguousMemory` again serviced the 4096-byte
  request and returned guest VA `0x03EFF000`.
- Ordinal 178 `MmPersistContiguousMemory` then executed with
  base `0x03EFF000`, size `4096`, `Persist=1`, matching the production
  no-op semantics.
- Execution advanced with `fault=0` to
  `ICALL_SAFE caller=0x002294AE target=0x80000031`.
- `0x80000031` is ordinal 49 `HalReturnToFirmware`.
- Because this follows the exact Xbox launch-page allocation/persistence
  sequence, the firmware return is treated as the fallback outcome of the
  still-failing Partition0 raw read, not as a normal service to execute.
- **Phase 5AK memory-services batch: PASS.**
- **Next:** Phase 5AL models Partition0 as its actual fixed-structure config
  device so the offset-`0x800` raw read can succeed, and records any residual
  soft-launch request without actually rebooting the diagnostic XEX.

### 2026-10-20 — Phase 5AL Partition0 config-device PASS

- Build `P5AL-PARTITION0-CONFIG-20261020-A` passed on real Xbox 360 hardware.
- Exact retail verification, 77-body translated pack, startup data relocations,
  native title-storage state and prior kernel continuations remained intact.
- The exact Partition0 root open succeeded:
  `\\Device\\Harddisk0\\partition0 -> game:\\merc360-partition0`.
- The previously failing raw probe at byte offset `0x800`, length `512`,
  now returned `STATUS_SUCCESS`, `bytes=512`, `error=0`.
- Because that probe succeeded, the prior second ordinal-301 error mapping,
  launch-page allocation/persistence and firmware-return fallback were no
  longer reached.
- New deterministic boundary:
  `GUEST_FAULT READ32 0x80000028` from translated caller `0x0022A3B9`.
- Ordinal 40 is `HalDiskCachePartitionCount`, a kernel DATA export
  (`ULONG`), not a callable service. Adjacent ordinals 41/42 are the disk
  model/serial STRING exports.
- **Phase 5AL Partition0 config-device model: PASS.**
- **Next:** Phase 5AM relocates the 40/41/42 disk-identity data cluster in one
  build so startup does not fall back into one-data-export-per-test iteration.

### 2026-10-20 — Phase 5AM disk-identity data batch PASS

- Build `P5AM-DISK-IDENTITY-DATA-20261020-A` passed on real Xbox 360 hardware.
- Disk identity initialization succeeded with cache partition count 3 and
  deterministic guest-only model/serial data.
- Retail import relocation observed:
  ordinal 40 slot `0x002DBD98`, old token `0x80000028`, new guest-data VA
  `0x0087E4A0`. Ordinals 41/42 were not present in this XBE import table.
- The bounded Partition0 raw read remained successful at byte offset
  `0x800`, length `512`, `STATUS_SUCCESS`, `bytes=512`.
- Retail immediately copied/edited that sector and attempted a 512-byte
  `NtWriteFile` back to offset `0x800`; the old directory-backed write path
  returned `STATUS_UNSUCCESSFUL`.
- Startup continued rather than rebooting, initialized
  `\\Device\\Harddisk0\\Partition5\\` path strings, and reached
  `DIRECT_FRONTIER caller=0x0023A3CE target=0x0022C5C6` with `fault=0`.
- **Phase 5AM disk-identity data batch: PASS.**
- **Next:** Phase 5AN completes Partition0 writeback semantics, maps cache
  Partition3/4/5, and promotes a bounded depth-2 translated closure rooted at
  `0x0022C5C6`.

### 2026-10-20 — Phase 5AN partial hardware proof: Partition0 writeback PASS

- Build `P5AN-CACHE-PARTITION-BATCH-20261020-B` ran on real Xbox 360
  hardware with an 84-body translated pack.
- Exact retail XBE verification and execution-environment setup remained green.
- Partition0 raw read at offset `0x800`, length `512` returned
  `STATUS_SUCCESS`, and the matching 512-byte `NtWriteFile` writeback also
  returned `STATUS_SUCCESS`.
- The cache-prep support shim ran and reported `roots_ready=3`, then retail
  entered translated root `0x0022C5C6`.
- The next observed operation was
  `NtOpenFile("\\Device\\Harddisk0\\Partition5")` with no trailing slash.
  The mapper rejected that exact-root spelling and fenced at
  `BOUNDARY: kind=STORAGE_OPEN ... target=0x800000CA`, `fault=0`.
- P5AN therefore remains **active**, not passed.
- Active fix batches exact-root handling for Partition3/4/5 while preserving
  existing trailing-slash/child-path mappings; the hardware PASS gate now
  requires a successful cache-root native open.
- Corrected exact-root build identity is now `P5AN-CACHE-PARTITION-BATCH-20261020-B` so stale `-A` deployments are unambiguous in xbWatson.

### 2026-10-20 — Phase 5AN-B cache-partition batch PASS

- Build `P5AN-CACHE-PARTITION-BATCH-20261020-B` passed on real Xbox 360
  hardware with the 84-body translated pack.
- Corrected build identity and exact-root diagnostics were present, proving
  the deployed XEX contained the intended fix.
- Partition0 raw read and matching raw writeback both succeeded at offset
  `0x800`, length `512`, `STATUS_SUCCESS`.
- Cache prep reported `roots_ready=3`.
- Exact `\\Device\\Harddisk0\\Partition5` (no trailing slash) mapped to
  `game:\\merc360-partition5` and `NtOpenFile` succeeded.
- The run advanced to a new fault-free kernel boundary:
  `ICALL_SAFE caller=0x0022C5C6 target=0x800000C4`.
- Token `0x800000C4` is ordinal 196 `NtDeviceIoControlFile`.
- **Phase 5AN cache-partition batch: PASS.**
- **Next:** Phase 5AO handles the cache-mount disk geometry and partition-info
  device controls in one batch and fences any unknown control code.

### 2026-10-20 — Phase 5AO-A partial hardware proof: live frame is 52 bytes

- Build `P5AO-CACHE-DEVICE-IO-20261020-A` reached the newly armed ordinal 196
  `NtDeviceIoControlFile` continuation on real Xbox 360 hardware.
- The prior P5AN cache proof remained green: Partition0 read/write succeeded,
  exact Partition5 root mapping succeeded, and the cache handle opened.
- The ordinal-196 handler fenced before argument decode because hardware showed
  `esp=0x008BFD24`, `saved_esp=0x008BFD58`, delta `52`, while P5AO-A
  expected the canonical 44-byte translated frame.
- **P5AO-A: partial proof, not pass.**
- **P5AO-B:** accepts 44-byte calls and uniquely locates the canonical 44-byte
  argument window inside the observed 52-byte frame; raw 13-dword frame data
  is logged, and ambiguous layouts remain fenced.

### 2026-10-20 — Phase 5AO-B cache device-control PASS

- Build `P5AO-CACHE-DEVICE-IO-20261020-B` passed on real Xbox 360 hardware.
- Exact retail identity/environment and the full prior storage/cache proof
  remained green.
- The first ordinal-196 call exposed raw 52-byte frame data; the canonical
  44-byte argument window was uniquely identified at offset 0.
- `IOCTL_DISK_GET_DRIVE_GEOMETRY (0x00070000)` completed successfully.
- The next ordinal-196 call used the canonical 44-byte frame and
  `IOCTL_DISK_GET_PARTITION_INFO (0x00074004)` completed successfully.
- Retail then closed the cache handle, set last error `0x70`, allocated and
  persisted a LaunchDataPage, and requested `HalReturnToFirmware(2)`.
- The launch page identified the same Mercenaries title, consistent with a
  quick-reboot/relaunch handshake.
- **Phase 5AO cache device-control batch: PASS.**
- **Next:** Phase 5AP persists Partition0 across XEX launches and reruns the
  same build twice to test whether retail cache metadata survives the reboot
  boundary and allows startup to advance.

### 2026-10-20 — Phase 5AP pass 1: persistent Partition0 primed

- Build `P5AP-PARTITION0-PERSIST-20261020-A` ran on real Xbox 360 hardware.
- Persistent backing was absent at startup, so the phase created a fresh
  `game:\merc360-partition0\partition0-config.bin` model.
- The retail Partition0 sector at offset `0x800`, length `512`, was read,
  modified, and written successfully.
- The full 512 KiB backing flushed successfully before `NtWriteFile`
  reported success.
- The write was `changed=1`, proving the persisted image now differs from
  the original zero-initialized Partition0 state.
- Both cache-mount `NtDeviceIoControlFile` calls remained successful.
- Retail again requested `HalReturnToFirmware(2)` with LaunchDataPage for
  the same title.
- **P5AP pass 1: successful / persistence primed.**
- **Next:** launch the same P5AP XEX again with no regeneration or rebuild and
  verify `Partition0 backing LOADED` before evaluating the new frontier or
  any repeated `changed=0` write/reboot behavior.

### 2026-10-20 — Phase 5AP pass 2: persistence breaks cache reboot loop

- The exact same `P5AP-PARTITION0-PERSIST-20261020-A` XEX was launched a
  second time without regeneration/rebuild.
- Partition0 backing loaded successfully with all `524288` bytes and zero
  padding.
- The retail sector-`0x800` / 512-byte write repeated with `changed=0`,
  proving the first launch's metadata survived.
- Retail did **not** repeat the first-boot geometry/partition-info IOCTL branch
  and did **not** request the prior quick reboot.
- Instead it opened `\\Device\\Harddisk0\\Partition5\\`, queried volume
  information, and created `\\??\\Z:`.
- Execution reached new fault-free direct frontier `0x0022F0D6` from caller
  `0x0022BD2D`.
- The emitted P5AP result label said FAIL only because the gate still required
  first-boot `NtDeviceIoControlFile` success; source gate was corrected to
  accept the persisted second-boot branch.
- **Phase 5AP persistent Partition0 / reboot handshake: PASS.**
- **Next:** Phase 5AQ promotes `0x0022F0D6` with a depth-2/cap-16 translated
  closure and rejects that old frontier as acceptable progress.

### 2026-10-21 — Phase 5BU convergence PASS / Phase 5BV repeatability active

- Build `P5BU-MIDTEXT1462E0-20261021-A` passed on real Xbox 360 hardware.
- The previous frontier `0x001462E0` was consumed through generic packed
  direct dispatch.
- Execution advanced only one safe-ICALL, two direct dispatches, one
  maintained `_msize` call, 15 translated block ticks and six trace entries
  beyond Phase 5BT before reaching
  `DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`.
- Final 5BU state was icall=1262, direct=1002, `_msize`=395, realloc=4,
  ticks=73417, trace=7322, `fault=0`; the fourth realloc remained 2048 bytes.
- The harness reported PASS, released the guest arena, completed the post-test
  heartbeat interval, ended the proof cleanly and returned through XAPI with 0.
- This is the strongest convergence signal so far, so the translated pack is
  frozen rather than expanded again.
- **Phase 5BV active:** one `P5BV-REPEATABILITY-20261021-A` XEX must be
  launched three consecutive times with persistent Partition0 unchanged. All
  three complete xbWatson logs must reproduce the exact same endpoint and
  translated-runtime counters before Phase-5 exit reconnaissance begins.

### 2026-10-21 — Phase 5BV 3/3 repeatability PASS

- One unchanged `P5BV-REPEATABILITY-20261021-A` XEX completed three
  consecutive real-hardware boots with persistent Partition0 left intact.
- All three runs reproduced the exact same endpoint:
  `DIRECT_FRONTIER caller=0x0023A3CE target=0x0014CD30`.
- All three runs also reproduced icall=1262, direct=1002, `_msize`=395,
  realloc=4, final allocation size 2048, ticks=73417, trace=7322 and
  `fault=0`.
- Each run reported the repeatability result PASS, released the guest arena,
  reached proof end and returned through XAPI with 0.
- The translated/runtime repeatability requirement is complete. The project
  now proceeds to the mandatory final Phase-5 subsystem exposure &
  reconnaissance gate before Phase 6 implementation work begins.

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
