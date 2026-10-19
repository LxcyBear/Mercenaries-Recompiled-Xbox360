# Phase 3M — x87 rounding + exceptional-path translated cluster

**Status: selector/harness ready; local retail selection and modified Xbox 360 hardware run pending.**

Phase 3L proved ordinary backward guest control flow on hardware with a hard
execution budget. Phase 3M now targets the next unproven semantic surface:
**x87 rounding/conversion and exceptional status behavior** in real translated
Mercenaries code.

## What Phase 3M must select

The selector still chooses real retail functions automatically and requires:

- 5–10 entirely new translated functions
- dependency depth at least 2
- exact static dependency closure
- at least one conditional/flag member
- at least one x87/XMM member
- at least one member that executes translated x87 rounding/conversion
  (`FIST/FISTP` via `X87_FIST16/32/64`, or `FRNDINT` via
  `x87_round_integral`)
- at least one member that uses x87 control/status state
- a plain-RET root and bounded nested RET-N cleanup <= 64 bytes
- the existing Phase 3L translated-block execution budget

All Phase 3E–3L hardware-proven VAs are excluded.

Ordinary backward edges remain allowed and budget-guarded, but they are no
longer required for selection. `LOOP/LOOPE/LOOPNE`, dynamic ICALL/ITAIL, MMX,
broad runtime-copy paths, and advanced transcendental x87 helpers remain outside
this gate.

## Runtime semantic correction

Phase 3M corrects `X87_FIST16/32/64` so NaN, infinity and out-of-range
conversions set x87 Invalid Operation status bit **IE (bit 0)** while returning
the x87 integer-indefinite result. NaN no longer spuriously sets Precision
Exception merely because NaN compares unequal to itself.

The maintained runtime copy and runtime template both receive this fix.

## Independent helper preflight

Before any retail function executes, the XEX checks:

- all four x87 RC modes using `+1.5` and `-1.5`
  - nearest-even
  - round down
  - round up
  - truncate
- Precision Exception (PE) on inexact finite conversion
- NaN FIST32 -> integer-indefinite + IE, without PE
- +Infinity FIST32 -> integer-indefinite + IE
- out-of-range FIST32 -> integer-indefinite + IE

These checks are independent expected-value assertions, not merely A/B
determinism.

## Retail-cluster proof

The 16 deterministic profiles continue to compare:

- integer guest registers
- exact x87 top/stack/control/status state
- all XMM0–XMM7 lanes
- translated trace and member coverage
- guest-memory fault state
- high-RAM canaries
- exact root-return ESP
- complete 64 MiB guest-RAM hash
- execution-budget state
- x87 rounding-helper call count and invalid-conversion count

The initial x87 control word cycles through all four RC modes across the profile
suite. Exceptional NaN/Infinity/overflow seeds are placed only in x87
architectural state, never generic pointer-shaped guest memory.

Hardware PASS requires at least one real selected retail rounding/conversion
helper execution across the suite.

## Build marker

```text
P3M-X87ROUND-20261019-A
```

Target success markers include:

```text
[Merc360:P3M] PASS: x87 rounding-control conversion matches expected result
[Merc360:P3M] PASS: NaN FIST32 returns integer-indefinite and sets IE without PE
[Merc360:P3M] SUITE X87 ROUNDING CALLS: N
[Merc360:P3M] PASS: deterministic profile suite executes real x87 rounding/conversion
[Merc360:P3M] PHASE 3M X87 ROUNDING + EXCEPTION CLUSTER RESULT: PASS
[XAPI RETURN VALUE] 0
```

## Preparation

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3m_x87_rounding_exception_xex\Prepare-Phase3M.ps1"
```

The preparation script verifies the exact retail XBE hash, reuses the reviewed
disassembly when available, selects the bounded closure, explicit-memory audits
every generated body, and emits:

- `build/phase3m_x87_rounding_exception/selection.json`
- `build/phase3m_x87_rounding_exception/main.cpp`

If no closure survives, use the complete rejection histogram for the next
narrow adjustment instead of weakening the gate blindly.
