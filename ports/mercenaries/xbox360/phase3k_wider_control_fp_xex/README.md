# Phase 3K — Wider control/flags + mixed FP translated cluster

**Status: selector/harness ready; local selection and modified Xbox 360 hardware run pending.**

Phase 3J proved an automatically selected six-function dependency-closed retail
cluster on modified Xbox 360 hardware. Phase 3K widens that proof into a real
cluster that composes integer control flow with x87 or XMM/SSE architectural
state.

## What Phase 3K-A must select

The root and member VAs are not hand-picked.

The selector recursively closes every statically named translated
`sub_XXXXXXXX()` dependency and requires:

- **5–10 entirely new real translated functions**
- dependency depth at least **2**
- at most 2,200 translated x86 bytes total
- at most 560 translated instructions total
- at most 480 bytes / 140 instructions per member
- no reuse of Phase 3E–3J hardware-proven function VAs
- at least one member with real conditional/flag control flow
- at least one member with supported x87 or XMM/SSE state
- exact static dependency closure
- a plain-RET root
- bounded nested RET-N cleanup <= 64 bytes

The selector prefers:
1. larger closures
2. deeper dependency graphs
3. more FP/XMM members
4. more conditional/flag members
5. smaller byte/instruction budgets

## Supported wider state

Phase 3K-A admits the maintained surfaces already established by earlier
hardware fixtures, including:

- x87 shared architectural stack/top
- float/double guest reads and writes
- basic x87 load/store/arithmetic/compare paths
- XMM0–XMM7 shared architectural state
- scalar SSE guest-memory loads/stores
- MOVAPS/MOVUPS/MOVSS/MOVSD/MOVLPS/MOVHPS/MOVQ helpers
- packed arithmetic helper paths
- bitwise/shuffle/unpack/min/max/compare helpers
- ordinary integer flag/condition helpers from Phase 3J

Advanced x87 transcendental/rounding paths remain outside this first 3K gate.

## Still rejected in 3K-A

The first mixed-state closure remains bounded and rejects:

- `RECOMP_ICALL` / `RECOMP_ICALL_SAFE`
- `RECOMP_ITAIL` / indirect tail dispatch
- backward guest branches
- LOOP / LOOPE / LOOPNE
- generated C while/for/switch surfaces
- MMX architectural state
- XBOX_MEMCPY / XBOX_REP_MOVS
- RDTSC/debugbreak/title-runtime surfaces
- advanced x87 sin/cos/atan2/log2/exp2/trunc/fmod/rounding paths
- missing or unresolved static translated dependencies
- recursive/cyclic translated dependency graphs

If the retail graph requires one of these, the selector prints an exact
rejection histogram rather than silently weakening the gate.

## Hardware architecture proof

The generated XEX owns and seeds:

- integer guest registers
- persistent 64 MiB guest RAM
- guest stack and deterministic object/argument pools
- x87 `g_fp_top` and all 8 x87 stack slots
- XMM0–XMM7, all 4 lanes each

The suite uses **16 deterministic profiles**.

Profiles 0–11 retain the branch-driving patterns from the final Phase 3J gate.
Profiles 12–15 add safe IEEE-754 patterns including:

- `+1.0f`
- `-1.0f`
- `2.0f`
- `0.5f`

The bit patterns are also valid under the existing guest-address router if a
branch unexpectedly consumes them as pointers.

Each profile runs A/B from identical state.

Every profile must match:

- guest-memory fault state
- high-RAM canaries
- translated trace
- member coverage mask
- final integer architecture
- exact x87 top/stack bits
- exact XMM0–XMM7 lane bits
- x87/XMM architectural-state hash
- complete **64 MiB guest-RAM hash**
- exact root-return guest ESP

Across all 16 profiles, union coverage must execute every selected cluster
member.

## Build marker

```text
P3K-MIXEDFP-20261018-A
```

Target success marker:

```text
[Merc360:P3K] SUITE COVERAGE: N/N ...
[Merc360:P3K] PASS: deterministic profile suite executes every statically closed cluster member
[Merc360:P3K] PHASE 3K WIDER CONTROL + MIXED FP CLUSTER RESULT: PASS
[XAPI RETURN VALUE] 0
```

## Preparation

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3k_wider_control_fp_xex\Prepare-Phase3K.ps1"
```

The workflow:

1. verifies the exact supported retail XBE SHA-256
2. reuses the reviewed Phase 3E disassembly when available
3. searches the real retail graph for the bounded mixed-state closure
4. writes retail-derived generated C only beneath
   `build/phase3k_wider_control_fp`
5. explicit-memory audits every selected translated body
6. emits `selection.json`
7. emits the compile-ready local XDK `main.cpp`

Successful preparation ends with:

```text
[Phase3K] SELECTED DEPENDENCY-CLOSED CLUSTER
[Phase3K] Wider surfaces: fp_members=..., flag_members=...
...
[Phase3K] READY
[Phase3K] XDK source: ...\build\phase3k_wider_control_fp\main.cpp
```

Compile the generated `main.cpp` in the existing VS17/XDK diagnostic project.
Do not compile `main_template.cpp` directly.

If no candidate survives, send the complete rejection histogram. The next
change should follow the real highest-value blocker instead of broadening the
runtime blindly.
