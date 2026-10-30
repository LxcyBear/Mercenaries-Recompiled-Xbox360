# K1A — genuine native kernel clock/date implementation

**Status (2026-10-29): portable clock conversion and guest-memory bridge implemented;
native host GCC/Clang tests PASS; guest kernel ABI integration NOT YET APPLIED.**

- `KernelClockCore.h` is the independent pure-C++ 100ns clock/calendar core.
  No private Xbox game file, XDK header or generated game source is included.
- `KernelClockGuestBridge.h` implements guest pointer contracts for all three
  clock APIs (ordinals 128, 304, 305), independent of the actual dispatcher.
- `Test-KernelClockGuestBridge.cpp` tests bounded guest-memory read/write,
  64-bit results, DATE conversion and invalid-pointer/no-partial-write behavior.
- `Test-KernelClock.cpp` verifies FILETIME epoch, leap years, dates,
  known absolute timestamps, weekdays, invalid fields, 1601–9999 bounds
  and thousands of round trips. Tested using GCC and Clang C++11.
- `Audit-K1A-Dispatch.py` is the read-only exact-source guest ABI scanner.
- `Test-K1A-Audit.py` checks that the audit fails closed on wrong R76
  watermark/duplicate macros and extracts synthetic clock/ICALL paths.

## Read-only R76 K1A ABI audit (from Mercenaries repo root)

PowerShell (paste only these commands; no console prompts):

```powershell
git pull --ff-only
python ".\ports\mercenaries\xbox360\integration_map\k1\Test-K1A-Audit.py"
python ".\ports\mercenaries\xbox360\integration_map\k1\Audit-K1A-Dispatch.py" --main ".\build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp" --source ".\build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp" --out ".\build\phase6_integration_map\K1A_DISPATCH_AUDIT.txt"
Get-Content ".\build\phase6_integration_map\K1A_DISPATCH_AUDIT.txt" -Raw -Encoding UTF8 | Set-Clipboard
```

Output is copied to the clipboard. It contains focused dispatch and caller
code contexts (not the XBE/game files). Show it to the maintainer for the
guest ABI audit and central integration patch. No source mutation or Xbox
build occurs. `python` can be replaced with `.\.venv\Scripts\python.exe`
if the system Python is unavailable.

## K1A R76 packed-dispatch staging (three real compatibility handlers)

**Staging is implemented** in `Stage-K1A-ClockBatch.py`. The source-only
preflight `Test-K1A-Stage.py` checks insertion, source hash preservation,
all three exact import target routes, guest stack argument offsets, and
fail-closed behavior for **any extra dispatcher** (including altered signatures),
wrong R76 identity and in-place writes.

From the Mercenaries repo root, after `git pull --ff-only`:

```powershell
python ".\ports\mercenaries\xbox360\integration_map\k1\Test-K1A-Stage.py"
if ($LASTEXITCODE -ne 0) { throw "K1A stage regression gate FAILED; stop before staging" }
python ".\ports\mercenaries\xbox360\integration_map\k1\Stage-K1A-ClockBatch.py" --main ".\build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp" --out ".\build\phase6_integration_map\k1a_clock_staging\main.cpp"
if ($LASTEXITCODE -ne 0) { throw "K1A staged source generation FAILED" }
Get-Content ".\build\phase6_integration_map\k1a_clock_staging\k1a-stage-manifest.json" -Raw
```

This creates a completely new staged `main.cpp` and an SHA manifest under
`build/phase6_integration_map`. The R76 source, 64 TrueTU shards and
existing R76 XEX remain unchanged. Do **not** send the staged `main.cpp`
or any retail game file; only send the short manifest/output.

## First incremental VS2017 Xbox 360 build

The new `Build-K1A-ClockBatch.ps1` script runs both Python fixture gates,
checks the **exact proven R76 main SHA-256**, regenerates staged code,
verifies all three imported target ordinals and distinct K1A **boot marker**,
and checks the 64 TrueTU shard inputs. It then invokes the existing
VS2017 Xbox 360 shadow builder with `SkipClean` and publishes a **separate**
`build/phase6_integration_map/k1a_clock_build/Merc-K1A-ClockBatch.xex`.

From the Mercenaries repo root:

```powershell
git pull --ff-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Build-K1A-ClockBatch.ps1"
```

To only rerun the gates and regenerate staged source without compiling:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Build-K1A-ClockBatch.ps1" -PreflightOnly
```

The K1A runtime startup watermark is
`P6K1A-BOOT-CLOCK128-304-305-20261029`. It must appear in a **genuine
Xbox execution log** before any hardware success is attributed to K1A.
The existing R76 XEX is preserved in its original output directory.
A successful XDK compilation is not proof of guest ABI, timing, first frame,
audio or menu operation.

**Not an Xbox-build PASS yet.** Remaining verification: the stage itself
must pass on the user's exact R76 cached source, the host C++ tests must
run locally if a compiler is available, and the VS2017/XDK guest
runtime must compile and preserve its kernel ABI. Hardware test comes
only after those checks.

## Actual K1A Xbox result and next READ32 root-cause audit

The K1A XEX booted on a real Xbox 360 and executed kernel ordinal 128
once (output VA `008BF954`). Original R76 ordinal-128 hard stop **cleared**.
The next verified boundary is `GUEST_FAULT READ32 EFEE0EC4`, with
`ESI=EFEE0EC0`, tick `27,029,593`. No game pixels or guest display
handoff yet. The two date conversion APIs (304/305) were staged but **not
observed executing** in this hardware log.

Do **not** whitelist this address, guess GPU/MMIO semantics, or regenerate
the full game. Inspect the exact frozen translated source with:

```powershell
git pull --ff-only
$k1 = ".\ports\mercenaries\xbox360\integration_map\k1"
python "$k1\Test-K1A-NextRead32.py"
if ($LASTEXITCODE -ne 0) { throw "K1A READ32 probe regression failed" }
python "$k1\Investigate-K1A-NextRead32.py" --source ".\build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp" --out ".\build\phase6_integration_map\K1A_NEXT_READ32_PROVENANCE.txt"
if ($LASTEXITCODE -ne 0) { throw "K1A READ32 source investigation failed" }
Get-Content ".\build\phase6_integration_map\K1A_NEXT_READ32_PROVENANCE.txt" -Tail 160 | Set-Clipboard
Get-Content ".\build\phase6_integration_map\K1A_NEXT_READ32_PROVENANCE.txt" -Tail 160
```

The report highlights the final 32 guest VAs and the candidate instructions
that assign/use ESI. A source match is NOT proof of the exact offending
instruction; use it to choose a grounded provenance repair.

## Optional host compilation

With GCC/Clang installed and on PATH:

```powershell
g++ -std=c++11 -Wall -Wextra -Werror -O2 ".\ports\mercenaries\xbox360\integration_map\k1\Test-KernelClock.cpp" -o "$env:TEMP\merc360-k1-clock.exe"
& "$env:TEMP\merc360-k1-clock.exe"
g++ -std=c++11 -Wall -Wextra -Werror -O2 ".\ports\mercenaries\xbox360\integration_map\k1\Test-KernelClockGuestBridge.cpp" -o "$env:TEMP\merc360-k1-bridge.exe"
& "$env:TEMP\merc360-k1-bridge.exe"
```

Do not attempt an XDK build or deploy any XEX from these portable files.
Required next gate: real R76 ICALL/ITAIL and savedEsp ABI confirmation,
then one central compatible dispatcher bridge with its own guest-stack,
pointer safety and return-register tests.
