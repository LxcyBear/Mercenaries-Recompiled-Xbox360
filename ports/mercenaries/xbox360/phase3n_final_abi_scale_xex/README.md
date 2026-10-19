# Phase 3N — Final ABI + scale gate

Phase 3N is intended to be the **last Phase 3 milestone**. Phase 3M completed
the remaining instruction-semantic proof (real x87 rounding and exceptional
conversion paths). What remains for Gate 3 is consolidation:

1. prove the *complete patched generated retail tree* has no remaining
   PowerPC-unsafe guest-memory/x86-host assumptions, and
2. prove the Xbox 360 XDK compiler/linker/runtime can carry a substantially
   larger translated-code image than the earlier 5–9 function hardware
   clusters.

If both 3N stages pass, Phase 3 closes and work advances to Phase 4 native
Xbox/kernel/platform services.

## Stage A — full generated-tree audit

Run:

~~~powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3n_final_abi_scale_xex\Prepare-Phase3N.ps1"
~~~

Stage A:

- verifies/uses the same supported retail XBE revision as the normal recompile,
- runs the maintained full discovery/recompile policy in an isolated
  `build\phase3n_final_abi_scale` workspace,
- applies the normal Mercenaries post-generation patch inventory unchanged,
- lowers the finished patched C from legacy assignable `MEM*` syntax to
  `GUEST_READ*` / `GUEST_WRITE*`,
- inserts `RECOMP_EXPLICIT_GUEST_MEMORY_ABI` into generated code,
- rejects unsupported expression-valued/address-of legacy lvalues instead of
  guessing their semantics,
- runs the strict legacy-memory audit after lowering,
- scans for x86 inline asm/intrinsics/raw guest pointers,
- reports but does not reject expected Phase-4 graphics/audio/platform
  surfaces,
- rejects any failed translation or unresolved direct-call stub for this final
  Gate-3 audit,
- records a SHA-256 manifest of the disposable generated tree.

Generated retail-derived C remains local under `build/` and is not committed.

Required Stage-A finish:

~~~text
[Phase3N] PHASE 3N-A RESULT: PASS
[Phase3N] READY FOR 3N-B XDK SCALE-PACK SELECTION
~~~

Send `build\phase3n_final_abi_scale\phase3n-audit.json` (or the complete console
output) after Stage A. Its real function/source-size counts are used to choose
the 3N-B scale pack rather than inventing an arbitrary target.

## Stage B — XDK scale proof

Stage B will be emitted after Stage A establishes the audited tree. It will:

- link a substantially larger set of real translated retail functions,
- retain checked explicit guest-memory routing,
- avoid the thousands of per-call xbWatson lines used by 3M,
- execute a bounded known-safe retail proof path twice,
- require identical integer/x87/XMM/full-RAM results and exact return stack,
- prove the larger image compiles, links, loads, executes and exits cleanly on
  modified Xbox 360 hardware.

A Stage-B hardware PASS closes Phase 3 / Gate 3.
