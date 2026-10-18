# Phase 3E — First bounded translated Mercenaries function

**Status: local generation workflow ready; hardware run pending.**

Phase 3A–3D proved the PowerPC-safe guest-memory ABI slices. Phase 3E is the
first test that executes a real mechanically translated Mercenaries function
on modified Xbox 360 hardware.

## Candidate

Reviewed retail function:

~~~text
0x00208F30
~~~

The project manual seed identifies it as a one-byte state accessor whose
guest-visible contract is:

~~~text
return low bit of byte at ECX + 0x14
~~~

It is intentionally tiny and dependency-free: no kernel call, no graphics, no
audio, no MMIO, no indirect call, and no guest-memory write is permitted by
the Phase 3E prep audit.

## No generated retail code is committed

The repository contains only:

- `Prepare-Phase3E.ps1`
- `main_template.cpp`

The actual translated function is generated locally from the user's own
verified retail XBE into the gitignored `build/` directory.

## Prepare the XDK source

From the repository root:

~~~powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3e_first_translated_xex\Prepare-Phase3E.ps1"
~~~

By default the script expects:

~~~text
game_files\mercenaries-retail\default.xbe
~~~

To use another extracted game directory:

~~~powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase3e_first_translated_xex\Prepare-Phase3E.ps1" -GameDirectory "D:\path\to\mercenaries"
~~~

The script:

1. verifies the exact supported retail SHA-256,
2. runs one reviewed-seed disassembly pass,
3. confirms `0x00208F30` exists exactly once,
4. lifts only that function with `--explicit-guest-memory`,
5. requires an 8-bit guest read and rejects wider reads, guest writes, ICALLs,
   runtime-copy helpers, or additional translated-function calls,
6. runs the explicit-memory legacy-lvalue scanner, and
7. injects the locally generated function into the XDK harness template.

Successful preparation ends with:

~~~text
[Phase3E] READY
[Phase3E] XDK source: ...\build\phase3e_first_translated\main.cpp
~~~

## Build

Compile this generated local file in the same VS17/XDK diagnostic project:

~~~text
build\phase3e_first_translated\main.cpp
~~~

Do **not** compile `main_template.cpp` directly; it intentionally contains an
uninjected marker.

No `default.xbe` is needed beside the XEX on the console for this test. The
single translated function has already been generated locally into the test
source from the verified user-supplied XBE.

## Hardware fixture

The harness creates a controlled guest object at `0x00030000`, sets ECX to
that object, supplies a dummy guest return-address slot, and calls the actual
generated `sub_00208F30()`.

It tests these object-byte values:

~~~text
00 01 02 03 FE FF
~~~

For each case it independently computes:

~~~text
expected = input & 1
~~~

and verifies:

- the translated trace VA is exactly `0x00208F30`,
- the returned low byte matches the independent reference,
- no guest-memory access fault occurs,
- the guest object byte is unchanged,
- translated `RET` consumes exactly four guest-stack bytes.

## Expected xbWatson start

~~~text
[Merc360:P3E] PHASE 3E FIRST BOUNDED TRANSLATED FUNCTION START
[Merc360:P3E] BUILD TAG: P3E-FIRSTFUNC-20261018-A
[Merc360:P3E] Translated retail function VA: 0x00208F30
~~~

Each case logs its input, expected result, actual result, full EAX and ESP.

Expected finish:

~~~text
[Merc360:P3E] PHASE 3E FIRST TRANSLATED FUNCTION RESULT: PASS
~~~

Send the complete prep-script output first if generation fails. If generation
succeeds, send the complete xbWatson trace from the XEX.

A PASS is the first hardware proof that mechanically translated Mercenaries
x86 game logic itself can execute through the explicit guest-memory ABI on
Xenon. It still does not authorize broad entry-point execution.

## Local generation result — PASS

The Phase 3E prep workflow completed successfully against the exact supported
retail XBE.

Observed:
- Python 3.12.10 environment ready
- exact SHA-256 verified
- reviewed-seed disassembly completed
- 13,346 functions / 16,598 labels loaded for the isolated lift
- `0x00208F30` lifted with explicit guest memory
- post-generation legacy-memory audit: PASS
- `[Phase3E] READY`

Generated local files:
- `build\phase3e_first_translated\sub_00208F30.c`
- `build\phase3e_first_translated\main.cpp`

The warnings for missing optional identified-function and ABI databases are not
blocking for this isolated, dependency-free accessor candidate.

**Local generation is complete; modified Xbox 360 hardware execution is next.**