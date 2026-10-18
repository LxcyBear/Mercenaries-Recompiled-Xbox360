# Phase 3J — First dependency-closed translated function cluster

**Status: selector/harness ready; local selection + modified Xbox 360 hardware run pending.**

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
- each member has a plain translated RET
- RET-N members are deferred
- forward/acyclic conditional control flow is allowed
- backward guest branch edges, LOOP/LOOPE/LOOPNE and generated C while/for/switch surfaces are deferred to Phase 3K

The branchless requirement is intentional for 3J-A. It makes the first closure
test about automatic dependency selection and execution rather than branch-path
seeding, and lets the hardware gate require every selected member to execute.

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

Three deterministic register/stack/object seeds are used.

For each case the full cluster runs twice from identical state.

The gate requires:

- no guest-memory faults
- translated trace starts at the selected root
- **every selected cluster member appears in the translated trace**
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