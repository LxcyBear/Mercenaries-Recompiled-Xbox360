# Phase 4A - Mercenaries guest-kernel surface audit

Phase 3 proved the translated guest ABI, generated-tree portability, XDK
compiler/linker scale, and real translated retail execution on Xbox 360
hardware. Phase 4 moves the runtime boundary from the Windows-oriented
original-Xbox compatibility layer toward native Xbox 360 platform services.

Phase 4A does not recompile the game and does not execute retail code. It reads
the verified retail XBE, inventories the exact 111 kernel imports used by
Mercenaries, and audits the path that translated code actually uses:

- `kernel_data_va_for_ordinal()` for guest-visible kernel data exports;
- `bridge_for_ordinal()` for explicit callable guest bridges;
- `kernel_thunk_dispatch()` for function dispatch and fallback behavior;
- `stdcall_args_for_ordinal()` for x86 callee stack cleanup.

The general `xbox_resolve_ordinal()` table is still reported as useful source
metadata, but it is not the translated game's dispatch path.

## Phase-4A ABI repair

The first Phase-4A inventory exposed stale ordinal assumptions in the legacy
guest stack-cleanup table. A missing bridge could therefore return zero and
also pop the wrong number of bytes from guest ESP. Phase 4A replaces that table
with cleanup metadata derived from the canonical ordinal resolver and the
actual calling conventions/prototypes in `kernel.h`, including `__fastcall`,
`__cdecl`, and by-value 64-bit arguments.

`tools/recomp/test_kernel_bridge_abi_metadata.py` locks this invariant. The
table currently matches all 172 canonical callable prototypes plus the two
bridge-only entries used by the runtime.

## Report

For every Mercenaries import, the report records:

- thunk slot, ordinal, name, and thunk VA;
- explicit guest bridge, guest data export, or return-zero fallback;
- guest x86 argument-cleanup bytes and the expected value;
- source implementation when found;
- obvious host API references that need portability review;
- conservative semantic-review hints for no-effect/constant-only functions;
- optional static reference counts from the preserved Phase-3N generated tree.

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4a_kernel_surface_audit\Prepare-Phase4A.ps1"
```

Outputs:

```text
build\phase4a_kernel_surface\phase4a-kernel-surface.txt
build\phase4a_kernel_surface\phase4a-kernel-surface.json
```

The supported retail XBE SHA-256, title ID, and 111-import count are hard
gates. If the preserved 3N generated tree exists, the runner also scans it for
thunk references so Phase 4B can prioritize fallbacks that translated
Mercenaries actually references.

Phase 4B begins from the corrected report by replacing/reviewing the
startup-critical fallback services and then proving the native service slice
under the Xbox 360 XDK.
