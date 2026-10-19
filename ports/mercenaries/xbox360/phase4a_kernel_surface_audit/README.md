# Phase 4A - Mercenaries kernel surface audit

Phase 3 proved the translated guest ABI, generated-tree portability, XDK
compiler/linker scale, and a real translated retail function on Xbox 360
hardware. Phase 4 now moves the runtime boundary from the Windows-oriented
original-Xbox compatibility layer to native Xbox 360 platform services.

Phase 4A does not recompile the game and does not execute retail code. It reads
the verified retail XBE and inventories the exact kernel imports used by
Mercenaries, then cross-checks those ordinals against the current kernel
resolver and implementation sources.

The report records, per import:

- thunk slot, ordinal, name, and thunk VA;
- the current `xbox_resolve_ordinal()` target;
- callable function vs data-export classification;
- implementation source file when found;
- obvious host API references that require portability review;
- conservative stub-like implementation hints.

Run from the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4a_kernel_surface_audit\Prepare-Phase4A.ps1"
```

Outputs:

```text
build\phase4a_kernel_surface\phase4a-kernel-surface.txt
build\phase4a_kernel_surface\phase4a-kernel-surface.json
```

The supported retail XBE SHA-256, title ID, and expected 111-import count are
hard gates. The audit intentionally distinguishes source evidence from a claim
that a Win32-looking API does or does not have an Xbox 360 XDK equivalent.
Phase 4B begins from the report by selecting the first startup-critical native
service batch.
