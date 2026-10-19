# Phase 4B-C — Guest memory/protection hardware gate

**Status: hardware gate A ready.**

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
P4B-MEMPROT-20261019-A
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
