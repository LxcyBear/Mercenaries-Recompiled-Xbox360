# Phase 2A — 64 MiB guest-memory diagnostic

This is the first test after completing the Phase 1 XEX bootstrap.

It still **does not load or execute Mercenaries**. It tests the memory contract
we need before any translated original-Xbox code is allowed to run.

## What this XEX proves

On the actual Xbox 360 / Xenon CPU it will:

- identify the native host byte order from memory,
- allocate and clear a 64 MiB low guest-RAM arena,
- test byte, 16-bit, 32-bit, 64-bit and float guest accesses,
- prove guest bytes are stored in **original-Xbox little-endian order**,
- test intentionally unaligned reads/writes,
- test the original Xbox XBE base address \`0x00010000\`,
- test accesses at the top of the 64 MiB region,
- reject writes/reads that cross the upper bound,
- free the arena before waiting for exit.

No XBE, ISO, game asset, GPU, MMIO alias or generated game function is used.

## Build with your existing VS17 + XDK project

Use a **copy** of the working Phase 1 Xbox 360 project.

1. Replace the Phase 1 \`main.cpp\` with
   [phase2_memory_xex/main.cpp](main.cpp).
2. Add the include directories:
   - \`ports\mercenaries\xbox360\include\`
   - or otherwise make both \`guest_memory.h\` and \`guest_endian.h\`
     resolvable by the source.
3. Build with the exact same known-good Xbox 360 / PowerPC XDK configuration.
4. Send the **entire compiler output** if it still fails. Do not substitute desktop
   Win32 headers/libraries to make an error disappear.

## Expected real-console output

The exact host-endian line is intentionally measured on hardware.

A successful run should include:

~~~text
[Merc360:P2] PHASE 2 GUEST MEMORY DIAGNOSTIC START
[Merc360:P2] Allocating and clearing 64 MiB low guest RAM arena
[Merc360:P2] HOST BYTE ORDER: BIG-ENDIAN (expected Xenon)
[Merc360:P2] PASS: 64 MiB guest arena allocated
[Merc360:P2] PASS: low-address byte write
[Merc360:P2] PASS: low-address byte readback
[Merc360:P2] PASS: XBE-base 32-bit guest write
[Merc360:P2] PASS: XBE-base bytes are little-endian in RAM
[Merc360:P2] PASS: XBE-base 32-bit guest readback
[Merc360:P2] PASS: unaligned 32-bit guest write
[Merc360:P2] PASS: unaligned bytes remain little-endian
[Merc360:P2] PASS: unaligned 32-bit guest readback
[Merc360:P2] PASS: unaligned guest float write
[Merc360:P2] PASS: float bytes are IEEE-754 little-endian
[Merc360:P2] PASS: guest float readback
[Merc360:P2] PASS: last valid 64-bit guest write
[Merc360:P2] PASS: last valid 64-bit guest readback
[Merc360:P2] PASS: last valid 16-bit guest write
[Merc360:P2] PASS: last valid 16-bit guest readback
[Merc360:P2] PASS: crossing upper bound rejected
[Merc360:P2] PASS: first out-of-range address rejected
[Merc360:P2] PASS: wrapped/high address rejected
[Merc360:P2] PHASE 2 MEMORY TEST RESULT: PASS
[Merc360:P2] Guest arena released
~~~

After that, press **A** or allow the 10-second post-test timer to exit.

## Stop conditions

Do not move on to retail XBE loading if any of these happen:

- the 64 MiB allocation fails,
- host byte order is not reported as expected,
- the underlying byte-array checks are not little-endian,
- an unaligned access test fails,
- an out-of-range access is accepted,
- the XEX crashes while allocating, zeroing or freeing the arena.

Send the complete xbWatson/debug transcript for any failure.

## Why this comes before XBE loading

The upstream Windows runtime can treat guest addresses as directly dereferenced
native pointers because Windows x64 and the original Xbox are both
little-endian and the runtime builds a large virtual-address mapping.

That assumption is invalid for native Xbox 360 PowerPC. This test establishes
an explicit **guest-address -> bounded byte arena -> little-endian access**
contract before we add:

1. XBE header parsing and verified section copies;
2. original-Xbox RAM aliases / KSEG routes;
3. synthetic kernel data;
4. GPU/APU MMIO routing;
5. generated x86-to-C code.

Passing this test is Phase 2A, not the whole Phase 2 gate.


## First two compile attempts

The first attempts failed before code generation because an older diagnostic
referenced `../include/guest_memory.h` from a standalone VS project. That
single missing include caused the large cascade of `MercGuestMemory`,
`memory`, storage-class and declaration errors.

The hardware diagnostic is now **one self-contained `main.cpp`** to eliminate
that entire class of setup mistakes.