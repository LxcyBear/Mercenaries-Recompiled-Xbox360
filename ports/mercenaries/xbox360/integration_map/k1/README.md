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

## K1A READ32: exact DSOUND table-index source audit

The latest hardware fault was traced to guest VA `002A6624`, in
`sub_002A6595`. An 8-byte table entry is addressed by
`ESI = ECX + EDX*8`; the fault read is `[ESI+4]`.
Post-call hardware registers `ECX=024A8000`, `EDX=FDB471D8`
arithmetically reproduce `ESI=EFEE0EC0`. However, the registers were
captured **after** a guest `MmGetPhysicalAddress` call, so matching values
are NOT proof they were unchanged at the previous ESI computation.

Use `Audit-K1A-DsoundTableIndex.py` and its synthetic test to extract
the complete R59 function, all `[EBP-4]`/`[EBP-12]` reads and writes,
and the translated caller before attempting a root-cause patch:

```powershell
git pull --ff-only
$k1 = ".\ports\mercenaries\xbox360\integration_map\k1"
python "$k1\Test-K1A-DsoundTableIndex.py"
if ($LASTEXITCODE -ne 0) { throw "K1A DSOUND index audit test failed" }
python "$k1\Audit-K1A-DsoundTableIndex.py" --source ".\build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp" --out ".\build\phase6_integration_map\K1A_DSOUND_TABLE_INDEX.txt"
if ($LASTEXITCODE -ne 0) { throw "K1A DSOUND source audit failed" }
Get-Content ".\build\phase6_integration_map\K1A_DSOUND_TABLE_INDEX.txt" -Raw -Encoding UTF8 | Set-Clipboard
```

Inspect the setup of the EBP-12 index and its relationship to the
024A8000 table base, rather than inventing a mapping for EFEE0EC4.
The R76 baseline, K1A XEX and 64 TrueTU shards remain unchanged.

## K1A: test the real source of suspicious EBX without another Xbox build

The complete `sub_002A6595` source shows:

- At entry `EBX=ECX`, where the caller loaded `ECX=[EDI+8]`.
- `[EBP-12]` stores `DWORD[EBX] - DWORD[EBX+4]`.
- `[EBP-4]` stores `DWORD[0x002BB240]` (the table base).
- The loop computes `ESI = [EBP-4] + [EBP-12]*8`, then reads `[ESI+4]`.
- Hardware fault-time `EBX=00041D70`, which lies **inside the retail
  XBE's .text section** (`00011000..0025561B`). This is suspicious but
  does not alone prove which guest call corrupted or supplied the pointer.

The new tool reads ONLY two dwords from the user's own, verified SHA-256
retail XBE image at fault-time EBX. If their difference matches
`FDB471D8`, it strongly supports that a code-section address fed the
DSOUND object reads. If not, inspect EBX restoration and EBP locals.

```powershell
git pull --ff-only
$k1 = '.\ports\mercenaries\xbox360\integration_map\k1'
python "$k1\Test-K1A-EbxTextBytes.py"
if ($LASTEXITCODE -ne 0) { throw 'K1A EBX synthetic test failed' }
python "$k1\Check-K1A-EbxTextBytes.py" --retail-xbe '.\game_files\mercenaries-retail\default.xbe'
if ($LASTEXITCODE -ne 0) { throw 'K1A retail XBE pointer proof failed' }
```

Do not commit/output the user's game bytes. The tool prints only the two
relevant 32-bit values and whether their difference matches the hardware
index. No source mutation or XDK compilation; keep EFEE0EC4 hard-fenced.
## DSINDEX: one modified TrueTU, four diagnostic checkpoints

The original-XBE comparison of the post-fault EBX address **did not**
reproduce the negative index. That's a negative hypothesis test, not
proof that the caller or MM173 clobbered EBX. We need live values
**before** the nested calls.

`Stage-K1A-DsoundIndexTrace.py` copies the frozen 64 TrueTU files into
a new directory and changes exactly one `.cpp` owner of
`sub_002A6595`. It adds four limited, read-only host trace messages:
`K1A DSINDEX ENTRY`, `LEA`, `PRE173`, and `POST173`. That
distinguishes bad object fields from register/stack mutation.

From the Mercenaries repo root, the new guarded build command is:

```powershell
git pull --ff-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  ".\ports\mercenaries\xbox360\integration_map\k1\Build-K1A-DsoundIndexTrace.ps1"
```

Or perform only the Python synthetic tests and **stage** the 64 copied
shards (no Xbox compilation):

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  ".\ports\mercenaries\xbox360\integration_map\k1\Build-K1A-DsoundIndexTrace.ps1" -PreflightOnly
```

On build success, a **separate** diagnostic XEX will be published at:

`build\phase6_integration_map\k1a_dsindex_probe\xdk\Merc-K1A-DSIndex-Probe.xex`

**2026-10-29 compiler-gate fix:** The first instrumented build stopped
at `translated_060.cpp(1): C1083 translated_runtime.h not found`. The
instrumentation staging script had copied only `translated_*.cpp`, not
the `*.h` files expected by the unmodified VS2017 builder. It now copies
and SHA-verifies **all source headers**, explicitly requires
`translated_runtime.h`, and can repair the previous 64-CPP-only stage
without regenerating or modifying any original TrueTU files. The synthetic
regression now covers that exact failed-build layout and rejects corrupted
headers. The XDK compilation remains unverified until rerun on Windows.
The user must test **that** new XEX, not an older K1A executable,
then upload its xbWatson log. Real success requires seeing the
ENTRY/LEA/PRE173/POST173 markers and verifying the original R76
and K1A behavior. If the trace fails to compile, keep the known-good
K1A XEX. Never whitelist `EFEE0EC4` or remove any hard fences.

## Actual K1A DSINDEX Xbox hardware proof (2026-10-30)

**The four checkpoints executed on the real Xbox**, not just in synthetic tests:

- `ENTRY`: object=`00041D70`, first=`01B672D8`, second=`04020100`,
  difference=`FDB471D8`, table=`024A8000`.
- `LEA`: computed ESI=`EFEE0EC0`, `local_delta=FDB471D8`,
  `loop_count=96` (exactly 393216 bytes / 4096).
- `PRE173` and `POST173`: EBX=`00041D70`, ESI=`EFEE0EC0`,
  ESP=`008BF8B4` unchanged across ordinal-173 MmGetPhysicalAddress.
- The actual hard-fenced `READ32 EFEE0EC4` remains at tick 27,029,593;
  `display_calls=0`, framebuffer=`00000000`.
- Retail initial XBE dwords at `00041D70` were `00041D59` and
  `04020100`. In live guest RAM, the first dword has become
  `01B672D8`; the second remains `04020100`. The altered first dword
  is sufficient to reproduce the invalid index before any ordinal-173
  call, but it is **not yet proven** whether the write is intentional,
  guest-translated, or native host memory copying.

**Next experiment: watch WHO writes that exact first dword.**

`Stage-K1A-DsoundWriterWatch.py` inserts strictly observational
overlap checks into translated guest write8/write16/write32 wrappers.
`Test-K1A-DsoundWriterWatch.py` validates the stage. The guarded
`Build-K1A-DsoundWriterWatch.ps1` reuses the 64 existing TrueTU files
(only the already-instrumented DSINDEX shard differs), all generated
headers, and the three clock handlers in a separate `main.cpp`.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1A-DsoundWriterWatch.ps1'
```

Output on successful XDK build:

`build\phase6_integration_map\k1a_dsobject_writer_watch\xdk\Merc-K1A-DSObjectWriter.xex`

**2026-10-29 staging fix:** The first DSOBJECT preflight rejected
`phase6ch_apu_write8` with definition count `0` because it only
searched the reduced K1A `main.cpp`. The 64-TrueTU layout uses
`translated_runtime.h` for common runtime helpers. Staging now
identifies the single owner (`main.cpp` or `translated_runtime.h`)
and instruments *only that owner*, staging all 64 `.cpp` inputs and
all original runtime headers together. This avoids changing any
translated gameplay functions. The preflight explicitly refuses
ambiguous signatures and reports the discovered names. Logging no
longer references per-function guest registers from shared helpers.

The Xbox builder receives the new staged shard folder, which
contains the original DSINDEX function probe and the monitored
runtime header. If that header changes, its dependent TrueTUs may
need recompilation even with `SkipClean` enabled. Stage tests are
synthetic until your local build confirms this exact generated layout.
On Xbox, filter for `K1A DSOBJECT WRITE` alongside `K1A DSINDEX`.
An absent write record doesn't prove the bytes never changed: host/native
bulk copies and unwatched guest-write paths remain possible.
Nothing in this stage bypasses the `EFEE0EC4` hard fence.

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
