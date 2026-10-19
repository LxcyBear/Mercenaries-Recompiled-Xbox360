# Phase 4B-C — Guest memory/protection hardware gate

**Status: hardware PASS; Phase 4B-C2 runtime verification PASS; Phase 4B complete.**

Phase 4B-A/A2 and Phase 4B-B/B2 are complete. The exact retail audit now
reports only two remaining direct semantic host-backed import paths:

- `NtFreeVirtualMemory`
- `MmSetAddressProtect`

Current locked baseline:

```text
imports=111
host_surface=2
platform_bound=15
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```

## Why this gate models guest state instead of VirtualFree/VirtualProtect

The translated guest bridge allocates `NtAllocateVirtualMemory` regions from
the tracked Xbox guest heap. The old free path incorrectly passed the
translated native pointer to `VirtualFree`, so allocation and release did not
use the same owner.

Likewise, translated guest RAM is one bounded arena. Applying host
`VirtualProtect` to a translated pointer is not the correct ownership model
for Xenon-native execution. Protection is guest metadata associated with guest
pages/ranges.

This gate therefore proves the intended native semantics directly on Xenon:

- page-aligned guest allocation in a bounded arena;
- logical protection changes per 4 KiB guest page;
- adjacent-page protection isolation;
- multi-page protection ranges;
- logical `MEM_DECOMMIT` and recommit state;
- whole-allocation `MEM_RELEASE`;
- clearing the released base/size outputs;
- released-range reuse;
- zero-initialized reused allocations;
- range/bounds rejection;
- double/untracked release rejection.

Build marker:

```text
P4B-MEMPROT-20261019-B
```

This XEX does **not** execute retail Mercenaries code.

## Prepare

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4b_native_memory_protection_xex\Prepare-Phase4B-C.ps1"
```

Compile:

```text
build\phase4b_native_memory_protection\main.cpp
```

in the same known-good XDK diagnostic project used by the previous gates.

A successful tail will contain:

```text
[Merc360:P4B-MEM] PASS: MEM_RELEASE frees tracked guest allocation
[Merc360:P4B-MEM] PASS: released guest range is reusable
[Merc360:P4B-MEM] PASS: logical MEM_DECOMMIT succeeds
[Merc360:P4B-MEM] PASS: recommit restores committed protection state
[Merc360:P4B-MEM] PHASE 4B-C GUEST MEMORY/PROTECTION RESULT: PASS
```

After hardware PASS, Phase 4B-C2 will wire the real guest bridge to tracked
guest-heap release and logical guest protection metadata, then rerun the exact
111-import surface audit.


## Build A rerun note

Build `P4B-MEMPROT-20261019-A` passed every guest allocation,
protection, decommit/recommit, release and reuse check except the final
"double release" assertion.

That assertion was invalid because Build A first released the original VA,
then immediately reused the same VA for a new live allocation, and only after
that attempted the supposed double release. Releasing that reused live
allocation was correct behavior.

Build B moves the stale-VA double-release check before reuse and additionally
verifies that the reused live allocation can later be released cleanly.


## Hardware result — October 19, 2026

Build `P4B-MEMPROT-20261019-B` passed on real Xbox 360 hardware.

Every bounded guest-owned memory check passed:

- bounded guest arena allocation;
- 4 KiB-aligned allocation and writable payload;
- per-page protection and adjacent-page isolation;
- multi-page protection coherence;
- logical decommit/no-access state;
- logical recommit;
- tracked whole-allocation release;
- clearing released base/size;
- stale/double-release rejection;
- released-range reuse;
- zero-initialized reuse;
- cross-arena protection rejection;
- clean release of the reused allocation.

Overall result:

```text
[Merc360:P4B-MEM] PHASE 4B-C GUEST MEMORY/PROTECTION RESULT: PASS
```

## Phase 4B-C2 verification

The production guest bridge now uses page-backed guest allocations, tracked
guest release and logical per-page guest protection state instead of
`VirtualFree` / `VirtualProtect` on translated pointers.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4b_native_memory_protection_xex\Verify-Phase4B-C2.ps1"
```

Expected final service accounting:

```text
host_surface=0
platform_bound=15
guest_native=2
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```


## Phase 4B-C2 final result

The complete verifier passed on October 19, 2026.

```text
host_surface=0
platform_bound=15
guest_native=2
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```

All regression layers passed: the 7,722-case timing/deadline suite, canonical
guest-kernel ABI metadata, time/sync platform boundary, file/handle platform
boundary, and all six guest-memory ownership tests.

Phase 4B service migration is complete. The next active phase is Phase 4C:
execute the first real retail-derived translated Mercenaries startup path with
the migrated Xenon service layer.
