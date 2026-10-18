# Mercenaries Recompiled - experimental Xbox 360 target

## Status

**Research/bootstrap only. No playable Xbox 360 XEX is produced by this tree.**

This folder starts a *native Xbox 360* target for RGH/JTAG hardware. It is not
the original Xbox backward-compatibility emulator, not an Xbox 360 emulator,
and not a rebuild of the existing Windows runtime.

The source project translates a supported original-Xbox retail XBE (x86)
into C, compiles that translation for Windows x64, and uses host compatibility
libraries for the original Xbox hardware and services. See the repository-root
ARCHITECTURE.md, CODE_MAP.md, and COMPATIBILITY.md.

An Xbox 360 game executable instead targets a 32-bit, big-endian PowerPC
environment and Xbox 360 platform facilities. We **must not** treat Windows
CMake success as proof of a native Xbox 360 build.

## Important findings

1. **Guest byte order:** Original Xbox x86 guest memory is little-endian; the
   Xenon CPU is big-endian. The translated game's recomp_types.h implements
   MEM16, MEM32 and MEM64 as directly dereferenced, assignable native pointers.
   Merely byte-swapping at the edge of the renderer is not sufficient.
2. **Lvalue constraint:** Generated code uses expressions such as
   MEM32(address) = value, increment/masked assignments, and memory operands.
   An ordinary read function cannot transparently replace those macros.
   Before generating PPC-compatible code, audit read, write and read-modify-
   write forms and adapt the lifter/patch pipeline **without editing the
   disposable generated code**. Guest structure fields and runtime accesses
   also require auditing.
3. **Memory:** The current runtime maps guest RAM, mirrors, CPU aliases, and
   GPU/MMIO addresses using Windows virtual-memory facilities; in particular,
   the 64-bit address-space aperture and exception-driven alias handling
   cannot simply be reproduced in a 32-bit console process.
4. **Graphics:** The shipped GPU bridge is NV2A/PGRAPH to Windows D3D11.
   A native Xbox 360 target needs an Xbox 360 graphics backend, including
   compatible shader, surface/texture, pushbuffer and synchronization behavior.
5. **Host services:** Windows handles, file mapping, SEH, Win32 windows,
   threads, XInput/SDL, timers, D3D11, XAudio2, and movie playback paths are
   coupled into the runtime and title integration. Replace or isolate each
   dependency while maintaining guest callback ordering.
6. **Build/generated game code:** The translated C tree is generated locally
   from a verified, legally obtained original Xbox retail image. It is not
   checked into this public source repository; a standalone CMake invocation
   builds only the toolkit components, not the native Mercenaries product.
7. **XDK:** Use your locally installed, legitimately obtained Xbox 360 XDK to
   build a future target. Do not commit or distribute XDK SDK files, game data,
   original XBE, generated copyrighted game code, or copyrighted assets.

## Bootstrap deliverable: portable guest byte access

The reference helpers in include/guest_endian.h define explicit little-endian
16/32/64-bit and IEEE-754 32-bit float reads/writes, independent of host
byte order. The test exercises unaligned accesses and exact byte layouts.

From the repository root, with a C11 host compiler:

~~~sh
cc -std=c11 -Wall -Wextra -Werror -pedantic -O2 \
  -Iports/mercenaries/xbox360/include \
  ports/mercenaries/xbox360/tests/test_guest_endian.c \
  -o merc_guest_endian_test
./merc_guest_endian_test
~~~

**Host-side verification (October 18, 2026): PASS.** The exact committed
header and corrected test-source Git blobs (`289c8792`, `00149528`)
were compiled/run on Linux x86-64 with GCC 14.2.0, Clang 17.0.0 and
Clang UndefinedBehaviorSanitizer, all passing. The first run also spotted
and fixed a cosmetic failure-message newline escaping issue.

This is **not integrated** into generated game memory access yet; nor does
passing it on a development computer prove PowerPC compatibility.
It provides a simple canonical contract to test future PowerPC/XDK code
against, including under intentionally unaligned addresses.

## First Xbox 360 hardware test

Follow [bootstrap_xex/BUILD_FIRST_XEX.md](bootstrap_xex/BUILD_FIRST_XEX.md)
using the user's already-working VS17 + Xbox 360 XDK project configuration.
The diagnostic XDK `main.cpp` exists, but has **not** yet been built with
the user's working VS17 + XDK setup or tested on an Xbox 360; do not mistake host-side memory
tests for a successful XEX build.

## Milestones / required proof

| Phase | Concrete exit criterion |
| --- | --- |
| 0 - Reference foundation | Host-neutral byte-access tests pass. Identify all guest memory lvalue forms and runtime direct memory reads/writes. |
| 1 - Console toolchain | A separate minimal XDK-built diagnostics XEX launches on real RGH/JTAG hardware, logs to a usable channel, checks controller input and exits cleanly. |
| 2 - Guest memory | Allocate 64 MiB guest RAM where feasible; implement explicit guest virtual-address translation, alias/MMIO routes and correct little-endian reads/writes without assuming a 4 GiB host aperture. Validate section loading and pointer bounds. |
| 3 - Recompiler ABI | Regenerate translated code with correct read/write/RMW semantics. Validate stack, flags, x87/SSE/MMX, indirect calls and guest-to-host callbacks against known original-Xbox traces. Ensure build size and native stack usage fit Xenon limits. |
| 4 - Host kernel | Implement the subset of file, memory, synchronization, timer, thread, logging, handle and controller services actually used by Mercenaries. |
| 5 - Native graphics/audio | Replace the D3D11/NV2A presentation chain with a 360 renderer and reimplement audio and movie output as needed. |
| 6 - First game milestone | Load verified retail assets from console storage, reach first visible frame, then menu, then controllable gameplay. Profile memory/performance and fix determinism. |

Keep the Xbox 360 target separately selectable so upstream Windows behavior
remains testable. Phase 1 should not compile the entire game or take runtime
shortcuts that bypass the guest ABI tests.

## Licensing and distribution

Preserve upstream authorship and the per-component MIT/LGPL/other third-party
notices. This work requires your own supported retail Xbox game. Do not add
retail executables or assets to the Git history. Never treat an Xbox 360 SDK
installation as redistributable source material.
