# Phase 4C-A — real translated startup closure preflight

**Status: ready.**

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
