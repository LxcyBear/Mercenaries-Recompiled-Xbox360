# Phase 3J — First dependency-closed translated function cluster

**Status: COMPLETE — Build `P3J-CLOSURE-20261018-B` hardware PASS on modified Xbox 360 hardware.**

Phase 3I proved that several previously verified translated families can coexist
inside one persistent guest arena. Phase 3J removes the hand-picked composition:
the root and its translated dependencies are selected automatically from the
supported retail function graph.

## What "dependency closed" means here

For a candidate root, the selector recursively follows every statically named
translated C call of the form:

```text
sub_XXXXXXXX()
```

This catches ordinary direct CALL edges, translated tail jumps, and any other
statically named external translated transfer.

A candidate is accepted only when every reachable translated dependency is also
present in the selected cluster.

The first Phase 3J gate rejects:
- `RECOMP_ICALL` / `RECOMP_ITAIL`
- missing translated dependency boundaries
- recursive/cyclic dependency graphs
- named/non-anonymous external translated dependencies
- unsupported runtime helpers
- x87/SSE/MMX dependencies
- string/runtime-copy/RDTSC/debugbreak dependencies

Thus the first cluster has no unresolved translated call edge.

## Phase 3J-A bounds

The first hardware cluster is deliberately bounded:

- **4–8 real translated functions**
- dependency depth at least **2**
- at most 1,400 translated x86 bytes total
- at most 360 translated instructions total
- at most 320 bytes / 96 instructions per member
- all members are new to this gate: the hand-selected Phase 3E–3I function VAs
  are excluded
- the root has exactly one plain translated RET
- nested members may use bounded RET-N cleanup (<= 64 bytes)
- forward/acyclic conditional control flow is allowed
- backward guest branch edges, LOOP/LOOPE/LOOPNE and generated C while/for/switch surfaces are deferred to Phase 3K

The initial branchless requirement was removed after selector evidence showed
that real Mercenaries closures overwhelmingly contain ordinary conditional
control flow. The final gate allows forward/acyclic branch control while
continuing to reject backward guest edges/loops and dynamic dispatch surfaces.

## Candidate ranking

The selector considers real call-graph roots and recursively constructs their
full static translated closure.

Accepted clusters are ranked by:

1. largest member count
2. deepest dependency graph
3. smallest translated byte budget
4. smallest translated instruction budget
5. root VA

No cluster root or member is hard-coded.

## Hardware proof

The generated XEX receives:
- forward declarations for every selected function
- all mechanically translated cluster bodies
- the automatically selected root
- the exact selected member VA table

Twelve deterministic branch-driving register/stack/object profiles are used.

For each profile the full cluster runs twice from identical state.

The gate requires:

- no guest-memory faults
- translated trace starts at the selected root
- A/B member coverage is identical for each profile
- the **union of all 12 profile coverage masks executes every selected cluster member**
- unrelated high-RAM canaries remain intact
- the root returns with exact guest stack state
- A/B translated traces match exactly
- final integer architectural state matches
- complete **64 MiB guest-RAM hash** matches

This is a closure/coexistence proof, not a replacement for the semantic
instruction proofs in Phase 3A–3I.

## Safe deterministic seed

General-purpose guest registers point at separate mapped low-RAM object pools.

The pools are mostly zero-filled so a pointer loaded from an unknown field
remains a mapped guest value rather than a random host-invalid pointer. Several
fields contain deterministic nonzero guest pointers back into the safe pools.

The guest argument area contains a mixture of those safe pointer values, zeroes
and small deterministic integers.

A high-RAM canary region is checked after execution.

## Preparation

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3j_closed_cluster_xex\Prepare-Phase3J.ps1"
```

The exact supported retail XBE SHA-256 is verified first.

The workflow reuses the reviewed Phase 3E disassembly when available, then:

1. selects the bounded closure
2. emits each retail-derived translated function locally beneath
   `build/phase3j_closed_cluster`
3. emits `selection.json`
4. explicit-memory audits every selected generated body
5. emits the XDK `main.cpp`

If no candidate survives, the selector prints a rejection histogram plus the
first root/reason pairs. Do not weaken the exact retail hash check.

Successful preparation ends with:

```text
[Phase3J] SELECTED DEPENDENCY-CLOSED CLUSTER
[Phase3J] Root: sub_XXXXXXXX @ 0xXXXXXXXX
[Phase3J] Members: ...
[Phase3J] Static edges:
...
[Phase3J] READY
[Phase3J] XDK source: ...\build\phase3j_closed_cluster\main.cpp
```

Compile the generated local `main.cpp` in the same VS17/XDK diagnostic
project. Do not compile `main_template.cpp` directly.

## Hardware marker

Build tag:

```text
P3J-CLOSURE-20261018-A
```

Target functional marker:

```text
[Merc360:P3J] PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER RESULT: PASS
```

A complete clean run should also reach the normal timeout and
`[XAPI RETURN VALUE] 0`.

If 3J-A passes, Phase 3K widens the selected translated surface to real
branch/flags control flow and the remaining mixed ABI/FP paths before the larger
Phase 3 scale gate.


## First local selector pass — scanner fixes

The first local selection considered 2,200 candidate roots but found no cluster
under the original 3J-A gate.

Top rejection classes:
- 1,144 branch/loop control flow
- 640 dynamic/SIMD/FPU/runtime surface
- 246 apparent `self` helper calls
- 86 RET-N members

The `self` class was a false positive. The helper scanner was analyzing
generated C comments such as `/* sbb self (CF extend) */` and treating the
word before the comment's parenthesis as a function call.

The selector now removes generated `/* ... */` comments before:
- static dependency scanning
- helper-call classification
- control-flow surface classification

The real zero-extension helpers emitted by `movzx`, `ZX8` and `ZX16`,
are also now accepted and implemented by the Phase 3J XDK harness.

No closure bounds, retail hash checks, or hardware pass criteria were weakened.

## Second local selector pass — acyclic branch relaxation

After removing the comment-scanner false positives, the selector again
considered 2,200 real roots. The dominant rejection class became:

```text
1390: branch/loop control flow deferred to Phase 3K
```

That is strong evidence that a completely branchless 4–8 function retail
closure is not representative of Mercenaries.

Phase 3J has therefore been relaxed in one bounded direction:

- forward guest conditional branches are allowed
- generated SETcc/CMOV-style `if (...)` is allowed
- statically named external conditional transfers still participate in closure
- backward guest branch edges are rejected
- LOOP/LOOPE/LOOPNE are rejected
- generated C while/for/switch surfaces are rejected

The XDK fixture now carries the maintained integer branch-condition helpers:
`CMP_EQ`, `CMP_NE`, `CMP_B`, `CMP_AE`, `CMP_BE`, `CMP_A`,
`CMP_L`, `CMP_GE`, `CMP_LE`, `CMP_G`, `TEST_Z`, `TEST_NZ`,
`TEST_S`, and `EVEN_PARITY8`.

All dependency closure bounds and the exact retail SHA remain unchanged.

## Third local selector pass — C keyword scanner fix

With forward acyclic branches enabled, the next local selector pass produced:

```text
799 unsupported dynamic/SIMD/FPU/runtime surface
518 unknown helper(s): if
442 backward/loop guest control flow
341 ret-N member
```

The 518 `if` rejections were not real helper dependencies. The generic helper
scanner was interpreting normal generated C `if (...)` syntax as a function
call.

Helper classification now ignores C control/operator tokens including
`if`, `while`, `for`, `switch`, and `sizeof`.

The unsupported-surface rejection now includes the first actual matched symbol,
so a subsequent failure will separate dynamic dispatch, SIMD, FPU, runtime-copy,
RDTSC, and other real surfaces instead of aggregating all of them.

No Phase 3J closure bound or hardware criterion was relaxed.

## Fourth local selector pass — bounded nested RET-N enabled

The latest rejection profile is now dominated by real code-shape constraints:

- 799 backward/loop guest control flow
- 381 `RECOMP_ICALL_SAFE`
- 380 RET-N members
- 281 x87 `fp_push`
- 80 `recomp_xmm_loadss`
- 50 `recomp_xmm_zero`

The next relaxation is deliberately narrow: **nested translated dependencies
may use bounded RET-N**.

Phase 3F already proved translated `ret 4` cleanup on hardware. The Phase 3J
root still must have exactly one plain RET and no RET-N, preserving the harness
expectation that the complete cluster returns to `ROOT_STACK + 4`.

Nested RET-N immediates must be parseable and no larger than 64 bytes.

No loop, dynamic-dispatch, x87/SSE, closure-budget, hash-verification, or
hardware-pass rule was loosened.

## RET-N relaxation correction

The first rerun after enabling nested RET-N still reported the old rejection
message. Source inspection showed the previous patch changed the root rule but
did not replace the generic member-level RET-N rejection.

That stale filter is now removed.

Current behavior:
- nested members may use parseable RET-N cleanup <= 64 bytes
- the root still requires exactly one plain RET and no RET-N
- the legacy `ret-N member deferred from first closed cluster` rejection no
  longer exists in the selector

Fix commit: `42be8dc0d0b6423104e2b140c6c1330d558c8430`.

## RET marker comment-strip correction

The first rerun after actually removing the stale RET-N rejection produced
996 `no translated RET` results.

That was another selector-only issue. The lifter intentionally emits translated
return identity in comments:

```c
esp += 4; return;     /* ret */
esp += 8; return;     /* ret 4 */
```

Helper/runtime/control-flow classification must use comment-stripped source, but
RET/RET-N classification must use the raw generated source.

Both the member return classifier and root plain-RET check now use raw source.
Startup assertions verify this invariant before candidate scanning begins.

Fix commit: `fbc90cddf3a187dc9c0b176a646b8ec051c69ade`.

## First hardware result — functional PASS, closure coverage 2/6

Build `P3J-CLOSURE-20261018-A` selected:

- root `0x000B2080`
- 6 real translated members
- dependency depth 2

On modified Xbox 360 hardware all three seed cases:
- completed without guest-memory faults
- preserved unrelated high-RAM canaries
- began at the selected real root
- returned with exact guest ESP `0x008B4004`
- produced deterministic A/B translated traces
- produced matching complete 64 MiB A/B RAM hashes

Hashes:
- case 0: `B1BB8502E837B4EF`
- case 1: `27269D03DBB0B4EF`
- case 2: `E83F01493C3DB4EF`

The only failed condition was execution coverage: each case reached 2 of the 6
selected static members.

This does **not** complete Phase 3J.

### Build B coverage model

Once forward conditional paths were admitted, requiring every static dependency
to execute in one run became inappropriate for mutually exclusive branches.

Build B keeps the full execution requirement at suite level:
- 12 deterministic safe profiles
- each profile executes A and B from identical state
- A/B must match coverage, trace, final architecture and full 64 MiB RAM hash
- each run must remain fault-free, preserve canaries and return with exact ESP
- the **union** of profile coverage must equal every selected cluster member

Build B also logs the selected member table, profile traces, coverage masks and
specific missing member VAs.

Build tag: `P3J-CLOSURE-20261018-B`.

## Final hardware PASS — Phase 3J complete

Build `P3J-CLOSURE-20261018-B` passed on modified Xbox 360 hardware.

Selected cluster:
- root `0x000B2080`
- 6 members
- dependency depth 2

Member VAs:
- `0x000AE4E0`
- `0x000AE510`
- `0x000AE540`
- `0x000B14D0`
- `0x000B2080` (root)
- `0x00209720`

The deterministic 12-profile suite achieved:

```text
SUITE COVERAGE: 6/6 mask=0000003F expected=0000003F
PASS: deterministic profile suite executes every statically closed cluster member
PHASE 3J DEPENDENCY-CLOSED TRANSLATED CLUSTER RESULT: PASS
[XAPI RETURN VALUE] 0
```

Profiles 2, 3, 5, 7, 8, 9, 10 and 11 each independently executed all six
members. Every profile's A/B pair matched translated trace, final architectural
state and complete 64 MiB guest-RAM hash.

Every profile also:
- completed without guest-memory faults
- preserved unrelated high-RAM canaries
- began at the automatically selected real root
- returned with exact guest ESP `0x008B4004`

This closes Phase 3J. Phase 3K widens the real translated surface to broader
control-flow/flags and mixed ABI/FP behavior.