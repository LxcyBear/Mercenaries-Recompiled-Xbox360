# Phase 3N-B — final XDK compiler/linker/runtime scale gate

Phase 3N-A has already audited the complete post-patch/post-lowering retail
generated tree. Stage B answers the final Phase-3 question: can the Xbox 360
XDK toolchain compile/link a substantially larger body of real translated code,
load that larger XEX on Xenon, and still execute a deterministic known-safe
translated proof path?

## Scale policy

Preparation consumes the exact generated-tree SHA256 recorded by the passing
3N-A report. It refuses to continue if any generated source changed afterward.

The emitted XDK source contains:

- the nine real translated functions from the hardware-proven Phase 3M closure,
  extracted from the passing 3N-A tree and executed under the same hard budget;
- 128 additional audited translated leaf bodies selected from that exact
  final tree when available;
- a minimum accepted pack of 64 scale bodies and 16 KiB of original guest code;
- a volatile function-pointer relocation table referencing every scale body so
  compiler/linker dead stripping cannot erase the proof;
- a runtime relocation checksum/non-null probe after XEX load.

The scale-only functions are intentionally not executed. Scale is not a reason
to call arbitrary retail functions without valid game state. Runtime execution
remains the deterministic A/B proof path already demonstrated in 3M.

## Hardware PASS contract

A real-console PASS requires the large source to compile/link into a loadable
XEX, every scale relocation to be non-null after load, and the deterministic
execution closure to preserve exact root-return ESP, integer/x87/XMM state,
full 64 MiB guest-RAM equality, coverage, budget safety and x87 execution.

Watson logging is deliberately low-noise: one compact line per profile rather
than the full trace/check dump used by earlier gates.

## Prepare

From the repository root run:

    powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3n_xdk_scale_xex\Prepare-Phase3NB.ps1"

The output XDK source is:

    build\phase3n_xdk_scale\main.cpp

Copy that file into the existing Mercenaries-PPC-Port XDK project as main.cpp,
build the Release XEX, run it on the modified Xbox 360, and capture xbWatson.

Target final marker:

    PHASE 3N-B XDK SCALE + RUNTIME PROOF RESULT: PASS

A clean hardware PASS closes Phase 3. Phase 4 then begins with native
platform/kernel services.
