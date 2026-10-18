# Phase 3I — Composite translated execution slice

**Status: source ready; local preparation + modified Xbox 360 hardware run pending.**

Phase 3A–3H proved the individual guest-memory and call/runtime mechanisms.
Phase 3I is the first **composition gate**: multiple real mechanically
translated Mercenaries function families execute inside one XEX and one
persistent 64 MiB guest arena without clearing guest RAM between stages.

This is intentionally not another isolated semantic proof. Earlier phases
remain authoritative for the individual instruction/call contracts. Phase 3I
tests coexistence, state continuity and deterministic repeated execution.

## Real translated slice

The local preparer lifts these exact supported-retail functions:

```text
0x00050010 -> direct CALL -> 0x0004CFF0

0x001EF850 -> tail JMP    -> 0x0021AB90
                                |
                                +-- MOVSS guest [ESP+4] -> XMM0
                                    store -> [ECX+0xDC]

0x0008DE60 -> GUEST_READ32(real guest function-pointer slot)
           -> RECOMP_ICALL_SAFE
           -> 0x0004CFF0 when resolved
```

If `0x0008DE60` still carries the one bounded ordinary direct helper accepted
by Phase 3H, that helper is lifted and compiled into the same slice as well.

No retail-derived generated C is committed. All translated bodies are emitted
locally beneath `build/phase3i_composite_slice`.

## Five-stage persistent-arena run

Each deterministic case executes all five stages without clearing guest RAM
between them:

1. **Direct CALL**
   - real translated `0x00050010`
   - real synthetic zero return slot
   - shared translated target `0x0004CFF0`

2. **Tail-call + MOVSS**
   - real translated `0x001EF850`
   - tail jump to translated `0x0021AB90`
   - scalar guest-stack load
   - XMM0 upper-lane zeroing
   - scalar guest store
   - `ret 4` cleanup

3. **Resolved ICALL**
   - unchanged translated `0x0008DE60`
   - real discovered guest function-pointer slot
   - slot contains nonzero `0x0004CFF0`
   - manual lookup miss -> generated lookup hit
   - same shared translated target `0x0004CFF0`

4. **Unresolved ICALL**
   - same unchanged translated caller
   - same real slot and same nonzero `0x0004CFF0`
   - manual/generated/kernel lookup all miss
   - saved ESP restored immediately
   - EAX forced to zero
   - caller continues and returns

5. **Direct CALL again**
   - `0x00050010 -> 0x0004CFF0` executes again after both ICALL paths
   - proves translated execution can continue after successful and failed
     indirect dispatch

## Persistent-state checks

The arena is initialized once per composite run.

Across all five stages the harness preserves and checks:
- four guest canaries in an unrelated RAM region
- cumulative stage markers
- prior guest-memory writes
- XMM0 state from the tail/MOVSS stage unless later real translated code changes it
- complete translated trace
- guest access-fault state

Each stage records a **complete 64 MiB guest-RAM hash**.

## Repeated-run determinism

For each of three input cases:

1. the real ICALL guest pointer slot is discovered twice from identical state
2. both discovery runs must return the same nonzero mapped guest slot
3. the full five-stage slice runs as **A**
4. the full five-stage slice runs again as **B**
5. A and B must match at every one of the five full-RAM checkpoints
6. final integer architecture, XMM0, pointer slot, translated trace, canaries
   and fault state must also match

The three tail-stage scalar inputs remain the hardware-proven values:

```text
0x3F800000  1.0f
0xC0200000 -2.5f
0x3EAAAAAB ~1/3
```

## Preparation guards

The preparer refuses to continue if the previously proven retail shapes drift.

It requires:
- exact supported retail XBE SHA-256
- `0x00050010` still has its direct CALL to `0x0004CFF0`
- `0x001EF850` still tail-jumps to `0x0021AB90`
- `0x0021AB90` still uses the proven MOVSS stack-load/store + `ret 4` shape
- `0x0008DE60` still has exactly one `RECOMP_ICALL_SAFE`
- its ICALL operand remains a real `GUEST_READ32(...)` guest pointer slot
- the shared target remains a bounded plain-RET translated function
- any optional ICALL direct helper remains bounded and call-free

Every generated local translated body is then passed through
`tools.recomp.audit_explicit_guest_memory`.

## Local preparation

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3i_composite_slice_xex\Prepare-Phase3I.ps1"
```

Successful output ends with:

```text
[Phase3I] READY
[Phase3I] Direct chain:     0x00050010 -> 0x0004CFF0
[Phase3I] Tail chain:       0x001EF850 -> 0x0021AB90
[Phase3I] ICALL caller:     0x0008DE60
...
[Phase3I] XDK source:       ...\build\phase3i_composite_slice\main.cpp
```

Compile the generated `main.cpp` in the same VS17/XDK diagnostic project.
Do not compile `main_template.cpp` directly.

## Hardware marker

Build tag:

```text
P3I-SLICE-20261018-A
```

Target final marker:

```text
[Merc360:P3I] PHASE 3I COMPOSITE TRANSLATED SLICE RESULT: PASS
```

A complete clean run should also reach the normal timeout path and:

```text
[XAPI RETURN VALUE] 0
```

After Phase 3I passes, the next Phase 3 escalation is a wider translated closure
and guarded startup/entry work rather than returning to isolated call fixtures.


## First local prep attempt — template-token fix

The first local Phase 3I prep verified the exact retail XBE and reused the
reviewed Phase 3E disassembly, then stopped during template assembly:

```text
[Phase3I] template token missing: __P3I_TAIL_CALLEE_NAME__
```

This was a preparer bookkeeping error, not a translated-code failure. The tail
callee body is injected directly before its wrapper, so the template does not
need a separate tail-callee-name placeholder.

The unused replacement was removed. A bidirectional audit now confirms:
- every template token has a replacement
- every replacement token exists in the template

No XDK source was produced by the failed attempt and no hardware run occurred.