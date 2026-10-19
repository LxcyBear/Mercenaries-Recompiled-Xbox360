# Phase 3L — Bounded backward-control-flow translated cluster

**Status: selector/harness prepared; local retail selection and hardware run pending.**

Phase 3K proved a seven-function dependency-closed retail cluster combining
real conditional control flow with x87/XMM state across 16 deterministic
hardware profiles. Phase 3L makes the next narrow control-flow relaxation:
ordinary **backward guest branches** may now participate in the selected
closure, but execution is guarded by a hard translated-block budget.

## Selection contract

Phase 3L keeps the Phase 3K closure bounds and requires:

- 5–10 entirely new real translated functions
- dependency depth >= 2
- exact static dependency closure
- at least one supported x87/XMM member
- at least one conditional/flag member
- at least one member containing an ordinary backward guest branch
- a plain-RET root and bounded nested RET-N cleanup <= 64 bytes
- no dynamic ICALL/ITAIL, MMX, broad runtime-copy surface, advanced x87
  transcendental/rounding helpers, recursive call graph, or LOOP/LOOPE/LOOPNE

All Phase 3E–3K hardware-proven VAs are excluded.

## Hang guard and proof requirement

Every generated guest basic-block label receives a budget tick. The complete
translated run gets a fixed execution budget of 4096 label entries. Exceeding
that budget sets a failure flag and forces translated functions to unwind rather
than allowing a retail loop to hang the console.

The selector also instruments each generated backward `goto loc_...` transfer.
A hardware PASS requires:

- no execution-budget exhaustion
- deterministic A/B backedge count
- at least one real backward edge actually taken by the 16-profile suite
- full selected-member union coverage
- no guest-memory faults
- exact root-return ESP
- identical translated traces
- identical integer/x87/XMM architectural state
- identical complete 64 MiB guest-RAM hashes

Build tag: `P3L-BOUNDEDLOOP-20261019-A`.

Run from repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3l_bounded_loop_xex\Prepare-Phase3L.ps1"
```

If no closure survives, use the selector rejection histogram for the next
narrow relaxation; do not weaken the gate blindly.
