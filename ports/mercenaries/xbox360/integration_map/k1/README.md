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
