# Phase 4C-A — real translated startup closure preflight

**Status: Phase 4C-A PASS; Phase 4C-B package preparation ready.**

Phase 4B service migration is complete. The exact retail service surface is:

```text
host_surface=0
platform_bound=15
guest_native=2
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```

Phase 4C is the first phase that intentionally moves from bounded service
harnesses toward the real retail-derived translated title startup path.

## Why Phase 4C-A is analysis-first

The repository intentionally does not commit the generated retail game bodies.
The complete translated tree exists locally under the locked Phase-3N-A build
and is tied to its recorded SHA-256.

The desktop launcher identifies the supported retail XBE entry as:

```text
0x0022964A
```

Before emitting an XDK startup XEX, 4C-A resolves that exact entry in the
locked function inventory. If the XBE entry is not itself a translated function
start, the analyzer resolves the containing translated owner and requires the
exact interior label `loc_0022964A` to exist in its audited generated body.
It then builds the complete direct translated dependency closure from that
owner.

The report records:

- whether the retail entry body exists;
- total directly reachable translated functions;
- maximum direct-call depth;
- reachable original guest-code bytes and generated source bytes;
- any missing direct translated dependencies;
- functions containing indirect/tail/dynamic dispatch boundaries;
- a breadth-first member manifest for startup-harness generation.

This does **not** execute retail code. It prevents the first startup harness
from being built from an arbitrary or incomplete hand-selected set.

## Run

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Analyze-Phase4C-A.ps1"
```

The preflight requires:

1. the exact locked Phase-3N-A generated tree;
2. its unchanged recorded tree SHA;
3. the Phase-4B-C2 final audit at
   `0 direct / 15 platform-bound / 2 guest-native`.

Outputs:

```text
build\phase4c_native_startup\phase4c-startup-closure.txt
build\phase4c_native_startup\phase4c-startup-closure.json
```

A structural PASS means the direct translated startup closure is complete in
the locked audited tree. It does **not** mean startup executes yet.

The next step uses that manifest together with the Phase-2E real-XBE
loader/execution environment and the completed Phase-4B service layer to emit
the first bounded native startup XEX with deterministic xbWatson checkpoints.


## Entry-resolution corrections

The first 4C-A run assumed every generated function was named
`sub_XXXXXXXX`, so it could not recognize identified translated symbols.

The second run proved that the function inventory already contains:

```text
xbe_entry_point  0x0022964A:0x002296BC
```

The generated-code parser now uses the inventory's authoritative symbolic
name-to-VA mapping. That means named translated definitions such as
`xbe_entry_point` participate in the closure exactly like `sub_...`
definitions, and direct dependencies are resolved through all known translated
symbols rather than only `sub_XXXXXXXX` calls.

Interior-entry resolution remains supported for any future entry that actually
lands inside a translated owner, but `0x0022964A` is expected to resolve as
an exact translated function start once named symbols are indexed correctly.


## Phase 4C-A result — October 19, 2026

The corrected named-symbol analyzer passed:

```text
Retail entry: 0x0022964A
Entry resolution: exact_function
Entry owner: 0x0022964A:0x002296BC xbe_entry_point
Reachable direct translated bodies: 40
Maximum direct-call depth: 8
Reachable retail guest bytes: 5918
Reachable generated source bytes: 111376
Missing direct translated dependencies: 0
Dynamic/indirect boundary bodies: 14
STRUCTURAL RESULT: PASS
```

## Phase 4C-B — first bounded real startup XEX

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-B.ps1"
```

The preparation step emits two local XDK sources:

```text
build\phase4c_native_startup\xdk\main.cpp
build\phase4c_native_startup\xdk\phase4c_env.cpp
```

Add **both** files to the known-good XDK diagnostic project.

Build tag:

```text
P4C-STARTUP-20261019-A
```

The runtime loads and verifies the user's exact retail `game:\default.xbe`,
reconstructs the proven Phase-2E execution environment, enters the real
translated `xbe_entry_point`, and performs a non-local escape at the first
live indirect/tail dispatch boundary.

A successful bounded run is expected to report a line shaped like:

```text
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=........ target=........ esp=........ saved_esp=........ ticks=... trace=...
[Merc360:P4C] PHASE 4C-B BOUNDED REAL STARTUP RESULT: PASS
```

That PASS means real retail-derived startup executed from the actual XBE entry
to its first live dynamic dependency without a guest-memory fault or execution
budget exhaustion. It does not mean full startup or gameplay yet.


## 4C-B helper-surface correction

The first 4C-B package emission correctly refused to continue because the
40-body translated closure directly referenced support outside generated
translated bodies.

The identified support was not missing retail translation:

- `sub_0022B150` — maintained Xbox `GetLastError` wrapper;
- `sub_0022B178` — maintained Xbox `SetLastError` wrapper;
- `sub_0022DDA4` — maintained retail `RtlAllocateHeap` wrapper;
- `sub_0022E51F` — maintained retail `RtlFreeHeap` wrapper;
- `XBOX_REP_MOVS` — guest-aware REP MOVS ABI helper;
- `__debugbreak` — generated INT3/debug-break surface.

The 4C-B emitter now packages those four canonical manual entry points, the
guest-aware REP MOVS helper, and converts a live debug break into a bounded
`DEBUGBREAK` diagnostic escape. The bounded heap implementation uses the
same initial title-heap range as the maintained runtime:

```text
0x008C1000 .. 0x009C0000
```

If the first bounded startup run requires more than that initial arena, the
harness records `HEAP_EXHAUSTED` and fails rather than silently substituting
different allocator behavior.


### Transformed-helper audit fix

A follow-up 4C-B preparation still reported `__debugbreak` after the runtime
support had already converted it to the bounded `PHASE4C_DEBUGBREAK` escape.
The cause was the helper validator inspecting the original generated body while
the emitter compiled the transformed body.

The validator now checks the exact transformed source that is emitted into
`main.cpp`. This keeps helper-surface validation and compiled startup code in
lockstep.


## Phase 4C-B hardware result — PASS

Real Xbox 360 hardware reached the first live startup dispatch:

```text
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022B4D7 target=800000FF esp=008BFF98 saved_esp=008BFFC4 ticks=5 trace=2
[Merc360:P4C] BOUNDARY REGISTERS: eax=008BFFD0 ecx=00000000 edx=00000000 ebx=00000000 esi=00000000 edi=00000000 seh_ebp=00000000 fault=0
[Merc360:P4C] trace[0]=0022964A
[Merc360:P4C] trace[1]=0022B4D7
[Merc360:P4C] PHASE 4C-B BOUNDED REAL STARTUP RESULT: PASS
```

The target `0x800000FF` is Xbox kernel ordinal 255,
`PsCreateSystemThreadEx`. The observed `saved_esp - esp = 0x2C` exactly
matches ten 32-bit arguments plus the translated synthetic CALL return slot.

This is the first hardware proof that retail-derived Mercenaries startup code
has executed from the genuine XBE entry on Xenon. It is not full title startup
or gameplay proof.

Phase 4C-C follows this kernel handoff into the first translated startup thread.


## Phase 4C-C package preparation

The next package is emitted separately from the hardware-proven 4C-B artifact.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-C.ps1"
```

Output:

```text
build\phase4c_native_startup\thread_xdk\main.cpp
build\phase4c_native_startup\thread_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-THREAD-20261019-A
```

The package includes both maintained startup-related roots
`0x0022B43F` and `0x002295D6` plus their direct generated closures, but the
runtime does not assume either is the live thread target. It decodes the actual
`PsCreateSystemThreadEx` argument frame on hardware, logs the StartRoutine and
contexts, and only enters the target if that exact address exists in the packed
closure. Otherwise it stops with a `THREAD_TARGET` boundary.


## 4C-C scope correction — live target capture first

The first 4C-C preparation attempt intentionally failed its helper audit because
recursively packing both static startup candidates dragged large renderer,
audio, XACT, XInput, checkpoint, and runtime-support surfaces into the package.

That was too broad for the next evidence gate. The corrected 4C-C package now
reuses exactly the hardware-proven 40-body 4C-B entry closure and does **not**
pack either guessed thread routine.

Runtime behavior:

```text
xbe_entry_point
 -> 0x0022B4D7
 -> 0x800000FF / PsCreateSystemThreadEx
 -> verify saved_esp - esp == 0x2C
 -> decode all 10 arguments
 -> log StartRoutine / ctx1 / ctx2
 -> THREAD_TARGET
```

`THREAD_TARGET` is a successful 4C-C evidence boundary when the frame is
exact and no guest-memory fault occurred.

New build tag:

```text
P4C-THREAD-20261019-B
```

After hardware reports the actual StartRoutine, the next phase will package
only that routine's required execution slice.


## Phase 4C-C hardware result — PASS

Real Xbox 360 hardware captured the exact live `PsCreateSystemThreadEx` frame:

```text
handle_ptr=008BFFD0
extra=0
kstack=262144
tls=20
tid_ptr=00000000
ctx1=002295D6
ctx2=00000000
suspended=0
debug=0
routine=0022B43F
```

The frame delta remained exactly `0x2C` bytes and `fault=0`.

The resulting evidence boundary was:

```text
BOUNDARY: kind=THREAD_TARGET caller=0022B4D7 target=0022B43F esp=008BFF98 saved_esp=008BFFC4 ticks=5 trace=2
PHASE 4C-C LIVE THREAD-HANDOFF CAPTURE RESULT: PASS
```

This confirms the actual first title-thread StartRoutine is `0x0022B43F`.
The first context is `0x002295D6`; the second is zero.

## Phase 4C-D — first title-thread target preflight

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Analyze-Phase4C-D.ps1"
```

The preflight analyzes only `0x0022B43F` and reports:

- directly reachable translated bodies;
- maximum direct-call depth;
- reachable guest/source bytes;
- missing translated dependencies;
- dynamic/indirect boundary bodies;
- non-translated direct helper surface.

No additional retail code is executed by this preflight.


## Phase 4C-D result — PASS

The hardware-observed first title-thread routine is a small closure:

```text
StartRoutine: 0x0022B43F
Entry resolution: exact_function
Reachable direct translated bodies: 6
Maximum direct-call depth: 2
Reachable retail guest bytes: 460
Reachable generated source bytes: 8556
Missing direct translated dependencies: 0
Dynamic/indirect boundary bodies: 5
STRUCTURAL RESULT: PASS
```

Members:

```text
0x0022B43F
0x0022B363
0x0022B403
0x0022B4D7
0x00239BE8
0x0022B1A6
```

Three of those already exist in the hardware-proven 4C-B entry closure, so the
continuous entry+thread package contains only 43 unique translated bodies.

## Phase 4C-E — first title-thread execution

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-E.ps1"
```

Output:

```text
build\phase4c_native_startup\thread_run_xdk\main.cpp
build\phase4c_native_startup\thread_run_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-THREADRUN-20261019-A
```

This package executes continuously from the genuine retail XBE entry through
the live ordinal-255 thread handoff into translated `0x0022B43F`, using the
captured contexts `0x002295D6` and `0x00000000`. It then stops at the first
subsequent dynamic/kernel boundary. The ctx1 routine itself is deliberately not
pre-packed; if the title thread invokes it indirectly, that exact target becomes
the next hardware boundary.


## Phase 4C-E hardware result — PASS

The continuous entry-to-title-thread XEX advanced beyond the real
`PsCreateSystemThreadEx` handoff and reached:

```text
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022B363 target=80000115 esp=008BFF3C saved_esp=008BFF44 ticks=11 trace=5
[Merc360:P4C] BOUNDARY REGISTERS: eax=00000000 ecx=00000000 edx=00000008 ebx=00312FC0 esi=00000000 edi=0070000C seh_ebp=008BFF8C fault=0
[Merc360:P4C] trace[0]=0022964A
[Merc360:P4C] trace[1]=0022B4D7
[Merc360:P4C] trace[2]=0022B43F
[Merc360:P4C] trace[3]=00239BE8
[Merc360:P4C] trace[4]=0022B363
[Merc360:P4C] PHASE 4C-E FIRST TITLE-THREAD EXECUTION RESULT: PASS
```

Target `0x80000115` is Xbox kernel ordinal 277:
`RtlEnterCriticalSection`.

The observed stack delta is exactly `0x8` bytes, matching one dword argument
plus the synthetic CALL return slot.

## Phase 4C-F — critical-section continuation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-F.ps1"
```

Output:

```text
build\phase4c_native_startup\crit_continue_xdk\main.cpp
build\phase4c_native_startup\crit_continue_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-CRITCONT-20261019-A
```

The package preserves the 43-body hardware-proven continuous startup slice.
When ordinal 277 is reached, it validates the 8-byte frame, logs the live guest
critical-section address, applies the repository's maintained serialized-guest
no-op semantics, restores the simulated stack exactly to `saved_esp`, and
continues until the next live ICALL/ITAIL boundary.


## Phase 4C-F hardware result — PASS

The first critical-section enter completed on real Xbox 360 hardware:

```text
[Merc360:P4C] RtlEnterCriticalSection LIVE FRAME: cs=00312FC0 esp=008BFF3C saved_esp=008BFF44
[Merc360:P4C] PASS: ordinal 277 RtlEnterCriticalSection matched maintained serialized-guest semantics
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022B363 target=80000126 esp=008BFF3C saved_esp=008BFF44 ticks=14 trace=5
[Merc360:P4C] BOUNDARY REGISTERS: eax=00000000 ecx=00000000 edx=00000008 ebx=00312FC0 esi=00312FDC edi=00312FDC seh_ebp=008BFF8C fault=0
```

Target `0x80000126` is ordinal 294, `RtlLeaveCriticalSection`. Its observed
frame is also exactly 8 bytes.

The run used the correct `P4C-CRITCONT-20261019-A` build tag; some inherited
text banners still said `PHASE 4C-E`. That labeling bug did not affect the
executed logic and is corrected for 4C-G.

## Phase 4C-G — critical-section pair continuation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-G.ps1"
```

Output:

```text
build\phase4c_native_startup\crit_pair_xdk\main.cpp
build\phase4c_native_startup\crit_pair_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-CRITPAIR-20261019-A
```

4C-G executes continuously through both the enter and leave calls using the
maintained serialized-guest no-op behavior and stops at the first live boundary
after the critical-section pair.


## Phase 4C-G hardware result — PASS

The first real critical-section pair completed on Xbox 360 hardware:

```text
[Merc360:P4C] RtlEnterCriticalSection LIVE FRAME: cs=00312FC0 esp=008BFF3C saved_esp=008BFF44
[Merc360:P4C] PASS: ordinal 277 RtlEnterCriticalSection matched maintained serialized-guest semantics
[Merc360:P4C] RtlLeaveCriticalSection LIVE FRAME: cs=00312FC0 esp=008BFF3C saved_esp=008BFF44
[Merc360:P4C] PASS: ordinal 294 RtlLeaveCriticalSection matched maintained serialized-guest semantics
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022B363 target=002295D6 esp=008BFF50 saved_esp=008BFF58 ticks=16 trace=5
[Merc360:P4C] ... fault=0
```

This is the first hardware proof that `ctx1=0x002295D6` from the actual
`PsCreateSystemThreadEx` call is later invoked as executable startup code.

The callback call itself has an exact 8-byte translated frame.

## Phase 4C-H strategy

The callback's complete static closure is too broad for a useful incremental
hardware gate. 4C-H therefore uses a bounded direct-call frontier:

- include `0x002295D6` and a small immediate translated slice;
- preserve all already-proven entry/thread/kernel continuation code;
- rewrite translated direct calls leaving that slice to a deterministic
  `DIRECT_FRONTIER` escape;
- continue to stop normally on unresolved ICALL/ITAIL targets;
- require callback entry and `fault=0` for a PASS.

This lets hardware reveal the actually executed callback path without
speculatively importing unrelated late-startup subsystems.


## Phase 4C-H — bounded startup callback frontier

Preparation:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-H.ps1"
```

Output:

```text
build\phase4c_native_startup\callback_frontier_xdk\main.cpp
build\phase4c_native_startup\callback_frontier_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-CALLBACK-20261019-A
```

The callback `0x002295D6` is now hardware-confirmed executable startup code.
The H package keeps the proven 43-body path, enters that callback using the
observed 8-byte indirect-call frame, and adds only its direct depth-1 translated
slice. Any translated direct call outside the slice becomes a
`DIRECT_FRONTIER` boundary while preserving the real call-site stack state.


## Phase 4C-H hardware result — callback entered, guest fault exposed

The bounded callback package reached genuine callback execution:

```text
[Merc360:P4C] STARTUP CALLBACK LIVE FRAME: target=002295D6 arg0=00000000 esp=008BFF50 saved_esp=008BFF58
[Merc360:P4C] PASS: entering hardware-confirmed translated startup callback 002295D6
[Merc360:P4C] BOUNDARY: kind=GUEST_FAULT caller=0022C4DF target=0022C4FF esp=008BFF48 saved_esp=008BFF48 ticks=19 trace=7
[Merc360:P4C] ... fault=1
[Merc360:P4C] trace[5]=002295D6
[Merc360:P4C] trace[6]=0022C4DF
[Merc360:P4C] PHASE 4C-H BOUNDED REAL STARTUP RESULT: FAIL
```

This is not a 4C-H PASS, but it proves the real startup callback executes on
Xenon. The next blocker is guest-memory state/mapping rather than the earlier
thread handoff or critical-section ABI.

## Phase 4C-I — first-fault provenance

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-I.ps1"
```

Output:

```text
build\phase4c_native_startup\fault_probe_xdk\main.cpp
build\phase4c_native_startup\fault_probe_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-FAULTPROBE-20261019-B
```

Expected additional xbWatson evidence:

```text
FAULT ACCESS: READ|WRITE width=N guest=XXXXXXXX translated_caller=0022C4DF
```

The probe records only the first rejected access and otherwise preserves the
existing guest validity rules.


### 4C-I Build A superseded

The first 4C-I probe hung immediately after entering `0x002295D6`. The issue
was in the diagnostic transform, not evidence of a new title behavior: accessor
names were located by loose textual search and could match earlier helper uses.

4C-I Build B uses exact accessor-body matching and writes first-fault telemetry
immediately from the rejecting accessor:
`FAULT ACCESS IMMEDIATE: READ|WRITE width=N guest=XXXXXXXX`.

No guest-memory mapping rule is relaxed by this change.


### Phase 4C-I probe revision B

The first 4C-I hardware attempt reached the confirmed startup callback and then
stalled instead of reproducing H's later bounded fault. That run is treated as
a diagnostic-harness failure, not new title behavior.

Revision B fixes two probe issues:

- guest-access instrumentation is anchored to exact accessor function bodies;
- after the driver's `setjmp` escape point is armed, the first rejected guest
  access records address/width/direction and immediately escapes as
  `GUEST_FAULT` instead of allowing translated execution to continue.

Guest address validity is unchanged. No additional region is mapped.

Build tag:

```text
P4C-FAULTPROBE-20261019-B
```


## Phase 4C-I Build B hardware result — PASS

The hardened first-fault probe captured the exact rejected access:

```text
[Merc360:P4C] FAULT ACCESS IMMEDIATE: READ width=4 guest=80000142
[Merc360:P4C] BOUNDARY: kind=GUEST_FAULT caller=0022C4DF target=80000142 esp=008BFF4C saved_esp=008BFF4C ticks=18 trace=7
[Merc360:P4C] FAULT ACCESS: READ width=4 guest=80000142 translated_caller=0022C4DF
```

`0x142` is kernel ordinal 322, `XboxHardwareInfo`, which is a DATA export.
The original Xbox loader would replace that thunk token with the exported
object's address. The stripped Phase-2E startup environment loads the raw XBE
and initializes the hardware-info object, but had not yet performed this data
thunk relocation.

## Phase 4C-J — XboxHardwareInfo thunk relocation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-J.ps1"
```

Output:

```text
build\phase4c_native_startup\hardware_info_xdk\main.cpp
build\phase4c_native_startup\hardware_info_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-HWINFO-20261019-A
```

Expected pre-execution evidence:

```text
DATA THUNK FIXUP: ordinal=322 XboxHardwareInfo slot=XXXXXXXX old=80000142 new=0087E000
PASS: XboxHardwareInfo thunk points at initialized guest kernel data
PHASE 4C-J DATA-THUNK PREP RESULT: PASS
```

Only ordinal 322 is relocated in this gate. First-fault provenance remains
active so any subsequent unresolved data-import token is reported immediately.


## Phase 4C-J hardware result — PASS

```text
[Merc360:P4C] DATA THUNK FIXUP: ordinal=322 XboxHardwareInfo slot=002DBE0C old=80000142 new=0087E000
[Merc360:P4C] PASS: XboxHardwareInfo thunk points at initialized guest kernel data
[Merc360:P4C] PHASE 4C-J DATA-THUNK PREP RESULT: PASS
[Merc360:P4C] FAULT ACCESS IMMEDIATE: READ width=2 guest=80000148
[Merc360:P4C] BOUNDARY REGISTERS: ... ecx=80000144 ... fault=1
[Merc360:P4C] PHASE 4C-J XBOXHARDWAREINFO DATA-THUNK RESULT: PASS
```

ECX=`0x80000144` identifies raw ordinal 324, `XboxKrnlVersion`.
The rejected READ16 at `0x80000148` is a +4 access into that structure,
matching its 16-bit Build field.

## Phase 4C-K — initialized startup data-thunk set

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-K.ps1"
```

Output:

```text
build\phase4c_native_startup\startup_data_xdk\main.cpp
build\phase4c_native_startup\startup_data_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-KDATA3-20261019-A
```

4C-K relocates exactly ordinals 156, 322, and 324 because those are the
guest-visible DATA exports explicitly initialized by the current Phase-2E
environment. It does not preemptively relocate uninitialized data exports.


## Phase 4C-K hardware result — PASS

```text
[Merc360:P4C] DATA THUNK FIXUP: ordinal=156 slot=002DBD58 old=8000009C new=0087E020
[Merc360:P4C] DATA THUNK FIXUP: ordinal=322 slot=002DBE0C old=80000142 new=0087E000
[Merc360:P4C] DATA THUNK FIXUP: ordinal=324 slot=002DBE14 old=80000144 new=0087E010
[Merc360:P4C] PASS: startup data imports 156/322/324 point at initialized guest kernel data
[Merc360:P4C] DIRECT FRONTIER: caller=0022C4DF target=0022C47B esp=008BFF4C
[Merc360:P4C] BOUNDARY: kind=DIRECT_FRONTIER caller=0022C4DF target=0022C47B esp=008BFF4C saved_esp=008BFF4C ticks=24 trace=7
[Merc360:P4C] ... fault=0
[Merc360:P4C] PHASE 4C-K STARTUP DATA-THUNK RESULT: PASS
```

The callback is now past the startup kernel-data relocation blockers and stops
only because the bounded translated slice intentionally excluded the next live
direct target.

## Phase 4C-L — promote live direct target 0x0022C47B

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-L.ps1"
```

Output:

```text
build\phase4c_native_startup\promoted_direct_xdk\main.cpp
build\phase4c_native_startup\promoted_direct_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-DIRECTC47B-20261019-A
```

Only `0x0022C47B` is added beyond the K pack. Deeper direct dependencies
remain evidence boundaries.


## Phase 4C-L hardware result — PASS

```text
[Merc360:P4C] PASS: hardware-observed direct target 0022C47B is packed for translated execution
[Merc360:P4C] FAULT ACCESS IMMEDIATE: READ width=4 guest=8001003C
[Merc360:P4C] BOUNDARY: kind=GUEST_FAULT caller=0022C47B target=8001003C esp=008BFF40 saved_esp=008BFF40 ticks=25 trace=8
[Merc360:P4C] ... fault=1
[Merc360:P4C] trace[7]=0022C47B
[Merc360:P4C] PHASE 4C-L PROMOTED DIRECT-FRONTIER RESULT: PASS
```

The promoted translated body executed. The next dependency is the original-Xbox
kernel image page at `0x80010000`, specifically DWORD `0x8001003C`.

## Phase 4C-M — synthetic xboxkrnl PE header

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-M.ps1"
```

Output:

```text
build\phase4c_native_startup\kernel_header_xdk\main.cpp
build\phase4c_native_startup\kernel_header_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-KHDR-20261019-A
```

The kernel page remains separate from title RAM. The synthetic header readback
must prove MZ, `e_lfanew=0x80`, PE signature, i386 machine, and zero sections
before translated startup executes.


## Phase 4C-M hardware result — PASS

```text
[Merc360:P4C] KERNEL HEADER MODEL: base=80010000 e_lfanew=00000080 sections=0 size=4096
[Merc360:P4C] PASS: synthetic xboxkrnl PE header is readable through the fenced kernel-image page
[Merc360:P4C] PHASE 4C-M KERNEL HEADER PREP RESULT: PASS
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022C28B target=8000002F esp=008BFEFC saved_esp=008BFF08 ticks=28 trace=9
[Merc360:P4C] ... fault=0
[Merc360:P4C] trace[7]=0022C47B
[Merc360:P4C] trace[8]=0022C28B
[Merc360:P4C] PHASE 4C-M KERNEL HEADER RESULT: PASS
```

Kernel target `0x8000002F` is ordinal 47,
`HalRegisterShutdownNotification`. The observed 12-byte frame matches the
production ABI exactly: 8 argument bytes plus one translated synthetic return.

## Phase 4C-N — HalRegisterShutdownNotification continuation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-N.ps1"
```

Output:

```text
build\phase4c_native_startup\hal47_xdk\main.cpp
build\phase4c_native_startup\hal47_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-HAL47-20261019-A
```

Expected live evidence includes:

```text
HalRegisterShutdownNotification LIVE FRAME: registration=XXXXXXXX register_raw=XXXXXXXX register=N esp=XXXXXXXX saved_esp=XXXXXXXX
PASS: ordinal 47 HalRegisterShutdownNotification matched production no-callback semantics
```


## Phase 4C-N hardware result — PASS

```text
[Merc360:P4C] HalRegisterShutdownNotification LIVE FRAME: registration=003134C0 register_raw=00000001 register=1 esp=008BFEFC saved_esp=008BFF08
[Merc360:P4C] PASS: ordinal 47 HalRegisterShutdownNotification matched production no-callback semantics
[Merc360:P4C] DIRECT FRONTIER: caller=0022C28B target=0022F128 esp=008BFF04
[Merc360:P4C] BOUNDARY: kind=DIRECT_FRONTIER caller=0022C28B target=0022F128 esp=008BFF04 saved_esp=008BFF04 ticks=29 trace=9
[Merc360:P4C] ... fault=0
[Merc360:P4C] PHASE 4C-N HAL SHUTDOWN-REGISTRATION RESULT: PASS
```

## Phase 4C-O — promote live direct target 0x0022F128

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-O.ps1"
```

Output:

```text
build\phase4c_native_startup\promoted_f128_xdk\main.cpp
build\phase4c_native_startup\promoted_f128_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-DIRECTF128-20261019-A
```

Only `0x0022F128` is newly added beyond the N pack.


## Phase 4C-O hardware result — PASS

```text
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022F128 target=8000006B esp=008BFEE4 saved_esp=008BFEF4 ticks=30 trace=10
[Merc360:P4C] ... fault=0
[Merc360:P4C] trace[9]=0022F128
[Merc360:P4C] PHASE 4C-O PROMOTED F128 RESULT: PASS
```

Target `0x8000006B` is ordinal 107, `KeInitializeDpc`. The 16-byte live
frame matches its 12-byte production ABI plus the synthetic translated return.

## Phase 4C-P — KeInitializeDpc continuation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-P.ps1"
```

Output:

```text
build\phase4c_native_startup\dpc107_xdk\main.cpp
build\phase4c_native_startup\dpc107_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-DPC107-20261019-A
```

Expected live evidence includes:

```text
KeInitializeDpc LIVE FRAME: dpc=XXXXXXXX routine=XXXXXXXX context=XXXXXXXX esp=XXXXXXXX saved_esp=XXXXXXXX
PASS: ordinal 107 KeInitializeDpc matched production guest-KDPC initialization semantics
```

The P prep gate also requires Phase-4C-P labels in both generated source files.


## Phase 4C-P hardware result — PASS

```text
[Merc360:P4C] KeInitializeDpc LIVE FRAME: dpc=00869580 routine=0022F116 context=00000000 esp=008BFEE4 saved_esp=008BFEF4
[Merc360:P4C] PASS: ordinal 107 KeInitializeDpc matched production guest-KDPC initialization semantics
[Merc360:P4C] BOUNDARY: kind=ICALL_SAFE caller=0022F128 target=80000071 esp=008BFEE8 saved_esp=008BFEF4 ticks=31 trace=10
[Merc360:P4C] ... fault=0
[Merc360:P4C] PHASE 4C-P KEINITIALIZEDPC RESULT: PASS
```

## Phase 4C-Q — KeInitializeTimerEx continuation

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-Q.ps1"
```

Output:

```text
build\phase4c_native_startup\timer113_xdk\main.cpp
build\phase4c_native_startup\timer113_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-TIMER113-20261019-A
```

Expected live evidence:

```text
PASS: Phase 4C-Q main/env build cookie matches
KeInitializeTimerEx LIVE FRAME: timer=XXXXXXXX type_raw=XXXXXXXX type=N esp=XXXXXXXX saved_esp=XXXXXXXX
PASS: ordinal 113 KeInitializeTimerEx matched production guest-KTIMER initialization semantics
```

The Q build cookie makes a stale environment project item a link-time failure
instead of merely a cosmetic log-label mismatch.


## Phase 4C-Q hardware result — PASS

```text
[Merc360:P4C] PASS: Phase 4C-Q main/env build cookie matches
[Merc360:P4C] KeInitializeTimerEx LIVE FRAME: timer=008695A0 type_raw=00000000 type=0 esp=008BFEE8 saved_esp=008BFEF4
[Merc360:P4C] PASS: ordinal 113 KeInitializeTimerEx matched production guest-KTIMER initialization semantics
[Merc360:P4C] DIRECT FRONTIER: caller=0022F128 target=0022C5A4 esp=008BFEDC
[Merc360:P4C] BOUNDARY: kind=DIRECT_FRONTIER caller=0022F128 target=0022C5A4 esp=008BFEDC saved_esp=008BFEDC ticks=33 trace=10
[Merc360:P4C] ... fault=0
[Merc360:P4C] PHASE 4C-Q KEINITIALIZETIMEREX RESULT: PASS
```

## Phase 4C-R — promote live direct target 0x0022C5A4

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-R.ps1"
```

Output:

```text
build\phase4c_native_startup\promoted_c5a4_xdk\main.cpp
build\phase4c_native_startup\promoted_c5a4_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-DIRECTC5A4-20261019-A
```

R rotates the main/env build cookie and adds only `0x0022C5A4` beyond Q.


## Phase 4C-S — promote live direct target 0x00230060

Phase 4C-R passed on hardware and executed 0x0022C5A4, reaching the next clean direct frontier at 0x00230060 with fault=0.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\\ports\\mercenaries\\xbox360\\phase4c_native_startup\\Prepare-Phase4C-S.ps1"
```

Output:

```text
build\\phase4c_native_startup\\promoted_30060_xdk\\main.cpp
build\\phase4c_native_startup\\promoted_30060_xdk\\phase4c_env.cpp
```

Build tag:

```text
P4C-DIRECT30060-20261019-A
```

S rotates the main/env build cookie and adds only `0x00230060` beyond R.


## Phase 4C-T — continue ordinal 24 ExQueryNonVolatileSetting

Phase 4C-S passed on hardware: translated target `0x00230060` executed and reached
`ITAIL target=0x80000018` with `fault=0`. Ordinal 24 is
`ExQueryNonVolatileSetting`.

T preserves every previously proven startup member, validates the live
5-argument stdcall tail frame, applies the existing guest EEPROM/XConfig
semantics, consumes the 24-byte tail-call frame (dummy return + 20 argument
bytes), and continues translated startup to the next real boundary.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-T.ps1"
```

Output:

```text
build\phase4c_native_startup\nv24_xdk\main.cpp
build\phase4c_native_startup\nv24_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-NV24-20261019-A
```

The T main/env cookie is `0x50435431` (`PCT1`).


## Phase 4C-U — continue ordinal 301 RtlNtStatusToDosError

Phase 4C-T passed on hardware. Ordinal 24 `ExQueryNonVolatileSetting`
received the live frame `index=0x11 (XC_MISC)`, returned success using the
guest EEPROM semantics, and startup advanced with `fault=0` to
`ICALL_SAFE target=0x8000012D`.

`0x8000012D` is kernel ordinal 301, `RtlNtStatusToDosError`. The locked
bridge ABI is one stdcall argument (4 bytes), giving an 8-byte live call frame
including the recompiler's dummy return slot.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-U.ps1"
```

Output:

```text
build\phase4c_native_startup\rtl301_xdk\main.cpp
build\phase4c_native_startup\rtl301_xdk\phase4c_env.cpp
```

Build tag:

```text
P4C-RTL301-20261019-A
```

The U main/env cookie is `0x50435531` (`PCU1`).


## Phase 4C-V — bounded direct closure rooted at 0x0022F0FB

Phase 4C-U passed on hardware. Ordinal 301 `RtlNtStatusToDosError`
received STATUS_SUCCESS, returned DOS error 0 with the expected 8-byte frame,
and startup advanced with `fault=0` to
`DIRECT_FRONTIER caller=0x00230060 target=0x0022F0FB`.

V accelerates the direct path: instead of promoting only the root, preparation
computes a bounded depth-2 translated direct closure rooted at `0x0022F0FB`,
capped at 16 members. Calls outside that proven slice remain explicit
`DIRECT_FRONTIER` boundaries, while all dynamic/kernel boundaries stay fenced.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-V.ps1"
```

Output:

```text
build\phase4c_native_startup\f0fb_closure_xdk\main.cpp
build\phase4c_native_startup\f0fb_closure_xdk\phase4c_env.cpp
build\phase4c_native_startup\f0fb_closure_xdk\phase4c-v-manifest.json
```

Build tag:

```text
P4C-F0FB-CLOSURE-20261019-A
```

The V main/env cookie is `0x50435631` (`PCV1`).


## Phase 4C-W — continue ordinal 149 KeSetTimer

Phase 4C-V passed on hardware. The bounded direct closure executed
`0x0022F0FB`, extending the translated trace to 13 functions, and reached
`ICALL_SAFE target=0x80000095` with `fault=0`.

`0x80000095` is kernel ordinal 149, `KeSetTimer`. The locked ABI is
16 bytes of stdcall arguments plus the 4-byte recompiler dummy return slot,
matching the 20-byte live frame observed on hardware.

W validates that frame, uses the Phase-4B-proven Xbox 360
`GetSystemTimeAsFileTime` path, applies the production guest-KTIMER fields
(Inserted, SignalState, absolute DueTime, DPC, Period), returns the prior active
state, and continues to the next real boundary. An already-due DPC is surfaced
as an explicit TIMER_DUE boundary rather than silently skipped.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-W.ps1"
```

Output:

```text
build\phase4c_native_startup\timer149_xdk\main.cpp
build\phase4c_native_startup\timer149_xdk\phase4c_env.cpp
build\phase4c_native_startup\timer149_xdk\phase4c-w-manifest.json
```

Build tag:

```text
P4C-TIMER149-20261019-A
```

The W main/env cookie is `0x50435731` (`PCW1`).


## Phase 4C-X — bounded direct closure rooted at 0x0022D980

Phase 4C-W passed on hardware. Ordinal 149 `KeSetTimer` received the expected
20-byte full frame, armed guest KTIMER `0x008695A0` with DPC
`0x00869580`, returned FALSE for the prior-active state, and startup advanced
with `fault=0` to `DIRECT_FRONTIER caller=0x0022F0FB target=0x0022D980`.

X retains the proven `0x0022F0FB` closure and computes a second bounded
depth-2 translated direct closure rooted at `0x0022D980`, capped at 16
members. Calls beyond that slice remain explicit boundaries.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4c_native_startup\Prepare-Phase4C-X.ps1"
```

Output:

```text
build\phase4c_native_startup\d980_closure_xdk\main.cpp
build\phase4c_native_startup\d980_closure_xdk\phase4c_env.cpp
build\phase4c_native_startup\d980_closure_xdk\phase4c-x-manifest.json
```

Build tag:

```text
P4C-D980-CLOSURE-20261019-A
```

The X main/env cookie is `0x50435831` (`PCX1`).
