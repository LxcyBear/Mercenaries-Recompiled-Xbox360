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

## Hardware follow-up: DSOBJECT watch did not advance the tick frontier

The 2026-10-30 xbWatson log (3,402 lines) still stops at
`27,029,593` translated ticks on the same
`GUEST_FAULT READ32 EFEE0EC4`. The same four DSINDEX snapshots
reproduce the invalid index. **No** `K1A DSOBJECT WRITE` record
appeared, but that does not prove that no guest write occurred:
the hooks monitor only `phase6ch_apu_write*` helpers. There is
also no new **runtime-visible** DSOBJECT boot marker in this build.

Before another expensive Xbox build, run this read-only coverage audit
over the *actual staged source files*:

```powershell
$k1 = '.\ports\mercenaries\xbox360\integration_map\k1'
python "$k1\Test-K1A-DsoundWriterCoverage.py"
if ($LASTEXITCODE -ne 0) { throw 'K1A coverage fixture failed' }
$root = '.\build\phase6_integration_map\k1a_dsobject_writer_watch'
python "$k1\Audit-K1A-DsoundWriterCoverage.py" --main "$root\main.cpp" --shards "$root\translated_shards" --out "$root\k1a-writer-coverage.json"
if ($LASTEXITCODE -ne 0) { throw 'K1A source-coverage audit failed' }
```

It summarizes direct `GUEST_WRITE8/16/32`, APU helper writes,
native guest writes, and likely bulk copies across all 64 TUs.
The counts are **lexical**, not proof of executed writes.
Next runtime XEX must visibly report a distinct DSOBJECT boot
watermark and confirm the actual compiled writer coverage.

## Next source decision: 61,619 direct `GUEST_WRITE*` references

The latest lexical coverage report shows 61,619 direct `GUEST_WRITE*`
references (61,454 in 64 translated shards) versus 1,607
`phase6ch_apu_write*` references. **These are source call-site
counts, not runtime write events.** The prior DSOBJECT watch was
restricted to APU helpers and cannot rule out direct generic writes.

The report also named `translated_004.cpp:21670` and
`translated_026.cpp:1261` as two occurrences of the fault-time
object address `00041D70`. Before a central write watch, inspect
the actual instructions and the generic `GUEST_WRITE` implementation
to avoid instrumenting the wrong thing again.

Run from repository root:

```powershell
git pull --ff-only
$k1 = '.\ports\mercenaries\xbox360\integration_map\k1'
$root = '.\build\phase6_integration_map\k1a_dsobject_writer_watch'
python "$k1\Test-K1A-CentralGuestWriters.py"
if ($LASTEXITCODE -ne 0) { throw 'K1A central writer fixture failed' }
python "$k1\Inspect-K1A-CentralGuestWriters.py" --main "$root\main.cpp" --shards "$root\translated_shards" --out "$root\k1a-central-writer-context.txt"
if ($LASTEXITCODE -ne 0) { throw 'K1A central writer source inspection failed' }
Get-Content "$root\k1a-central-writer-context.txt" -Raw | Set-Clipboard
```

This inspector copies no files, does not write guest memory, does not
alter any of the 64 TrueTU sources and triggers **no XDK build**.
Send the report to determine the next minimal writer instrumentation.

## 2026-10-30 K1B: target the generic guest writes, not APU-only writes

The latest source report gives the exact original TrueTU writer roots:

- `main.cpp:942` `recomp_guest_write8`
- `main.cpp:956` `recomp_guest_write16`
- `main.cpp:1059` `recomp_guest_write32`
- `main.cpp:1101` `recomp_guest_write64`
- `main.cpp:1195` `recomp_guest_write128`

`translated_runtime.h` routes `GUEST_WRITE8/16/32/64` to the
corresponding central `recomp_guest_write*` functions.
The two lexical `0x41D70` references are **not direct writes**
to this address: `translated_004.cpp:21670` stores the POINTER
`0x41D70` at `[EAX+8]`, while `translated_026.cpp:1261` reads
a dispatch lookup byte from `[ECX+0x41D74]`, then branches through
a table rooted at `0x41D60`. This ties the address to code-side
jump-table data, not a demonstrated DSOUND object structure.

New stage: `Stage-K1A-CentralGuestWriteWatch.py` instruments the five
central store widths, checks overlap **only** for
`0x00041D70..0x00041D77`, and includes a unique runtime boot marker:

`P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030`

This mark should appear in the original `PHASE 6DQ REAL TRANSLATED
STARTUP BOUNDARY PROOF START` line of the new XEX, **even when no
write is observed**. The patch does not change the guest-write body
or the hard fence. The stage points the incremental VS17 builder at
the unchanged 64 TrueTU files from the previous K1A DSINDEX probe;
only the host `main.cpp` is patched.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File
  '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1B-CentralGuestWriteWatch.ps1'
```

Use `-PreflightOnly` to run the Python fixture and stage without XDK.
After a successful build, the independent diagnostic executable is:

`build\phase6_integration_map\k1b_central_write_watch\xdk\Merc-K1B-CentralWriter.xex`

On Xbox, obtain the boot line and `K1B CENTRAL WRITE` records, if any.
Zero writer records **with a verified K1B boot tag** directs the next
investigation to host bulk-copy, direct guest pointers, or the earlier
wrong-object/ABI source. It does **not** permit bypassing EFEE0EC4.

## K1B VS2017 C3861 source-order fix (2026-10-30)

The first K1B Xbox compile passed the 64 TrueTU source-hash gates,
synthetic staging regression, source sync, and reached incremental
`main.cpp` compilation only. It failed with exactly five
`C3861: 'phase4c_current_caller': identifier not found` errors
at the five newly instrumented central writer functions.

The first fix attempted a forward declaration for
`phase4c_current_caller(void)`, but **the real generated K1A main did
not contain the exact assumed function definition**. That produced a
fail-closed Python staging error before XDK.

The corrected K1B writer probes no longer call
`phase4c_current_caller()` or add a prototype. Instead, they capture
the latest trace-ring entry using `s_traceCount`, `s_trace[index]`
and `TRACE_CAPACITY`, mirroring the logic already present in the
existing `recomp_guest_write32` function in the actual K1A source.
This latest trace VA is a provenance clue, **not a guaranteed exact
call-site address**.

The new synthetic tests exercise the source-backed trace-ring path
for both LF and Windows CRLF input, and the PowerShell wrapper
verifies exactly five new ring reads and zero stale
`(unsigned)phase4c_current_caller()` calls **inside the five K1B
probe blocks** before starting VS2017. Other pre-existing APU helper
call sites remain unchanged.
No game-memory behavior or translated shards change.

The build script uses independent corrected output
`build\phase6_integration_map\k1b_central_write_watch_c3861fix`
to preserve the failed source for forensic comparison.
On a successful XDK build, launch only:

`build\phase6_integration_map\k1b_central_write_watch_c3861fix\xdk\Merc-K1B-CentralWriter-C3861Fix.xex`

No translated shard recompilation or clean is requested; no
hardware progress claim until the new XEX actually runs.

## 2026-10-30 K1B hardware PASS -> K1C write-site VA probe

The K1B Xbox 360 diagnostic executable **ran with the unique boot marker**
`P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030`.
At one actual 32-bit write to `00041D70`, it printed:

```text
K1B CENTRAL WRITE: width=4 hit=1 address=00041D70 value_lo=01B672D8 value_hi=00000000 before0=00041D59 before4=04020100 caller=0023A3CE budget=0 esp=008BF974
```

Immediately beforehand the native heap allocated 2,400 bytes at
`01B672B0`. The written guest value is `01B672B0 + 0x28`.
The writer is conclusively a guest `recomp_guest_write32` call, but
the observed `caller=0023A3CE` came from the broad trace ring and
is **not an exact translated instruction address**. The fault
still occurs later at `READ32 EFEE0EC4`,
`ticks=27029593 trace=1072569`. `display_calls=0` and
`framebuffer=00000000`; there is **no tick/pixel breakthrough yet**.

K1C extends the already-proven K1B central 8/16/32/64/128 write
messages with the existing `s_phase6cpCurrentVa` tracker, logged
as `guest_va=%08X`, while preserving the previous `trace_caller`.
This is a **candidate last executed guest VA**, not guaranteed to
be the precise guest store PC; interpret it alongside the tick/
trace context. It leaves original writes and memory hard fences
untouched. Only host `main.cpp` changes; the 64 TrueTUs and all
headers remain byte-for-byte identical.

```powershell
Set-Location 'C:\Users\jorda\Mercenaries-Recompiled-Xbox360'
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1C-ExactGuestWriteSite.ps1'
```

Pass `-PreflightOnly` for source verification and synthetic
regression without an XDK build. If VS2017 compiles and publishes,
launch **only this distinct new diagnostic XEX**:

`build\phase6_integration_map\k1c_guest_write_site_va\xdk\Merc-K1C-GuestWriteSiteVA.xex`

Search xbWatson for `P6K1C-EXACT-WRITE-SITE-VA-20261030` and
`K1C WRITE SITE:`. If `guest_va` is nonzero, inspect the specific
guest instruction against the retained translated source; if stale
or zero, do not guess or mutate the pointer. The existing
`EFEE0EC4` hard fence remains mandatory.

## K1C actual K1B source order correction (2026-10-30)

The first real K1C preflight verified R76, the built K1B XEX and all
64 TrueTU source/header identities. It also passed the synthetic
fixture. **Staging stopped before XDK** because the fixture placed
`static DWORD s_phase6cpCurrentVa = 0u;` *before* central writer
definitions whereas actual K1B generated `main.cpp` defines it
*after* them. A direct read in those earlier writer functions is
therefore not legal C++ at that point.

The K1C stage now preserves the original guest-VA tracker definition
in place. It inserts exactly one early
`static DWORD k1c_read_guest_va(void);` declaration and one helper
function body **immediately after** the original static tracker,
returning `s_phase6cpCurrentVa`. Five K1B logging expressions now
call that helper; original guest-store bodies, pointer values, hard
fences, 64 TrueTUs and runtime headers remain unchanged.

Synthetic tests now exercise both late (real) and early (legacy)
tracker source order under LF and CRLF. The PowerShell pre-XDK gate
requires exactly five helper calls, one helper declaration/body,
one unchanged tracker definition and one boot marker. Build and
hardware results remain **UNVERIFIED** until the corrected script
runs successfully on Windows.

## K1C REAL XBOX EVIDENCE -> K1D exact XACTENG source lookup

K1C boots on Xbox, and its unique marker appears in the hardware log:

```text
K1C WRITE SITE: width=4 hit=1 address=00041D70 value_lo=01B672D8 value_hi=00000000 before0=00041D59 before4=04020100 trace_caller=0023A3CE guest_va=0027DD0C budget=0 esp=008BF974
```

The guest VA is inside the retail XBE's XACTENG section
(0027D5C0..0028862F). It is the **last recorded translated tick
location**, not yet verified as the instruction that performed the
store. The destination 00041D70 is within retail .text
(00011000..0025561B), and the written pointer is the recently
allocated heap base 01B672B0 plus 0x28. **Do not mutate the store
or assume it is corrupt until the original instruction/ABI is
checked.** The run still stops at READ32 EFEE0EC4,
ticks=27029593 / trace=1072569; display_calls=0 and no framebuffer.

New offline script `Inspect-K1D-XactWriteSite.py` extracts the exact
`loc_0027DD0C` / `PHASE4C_BUDGET_TICK(0x0027DD0C)`
source window, plus any literal 00041D70 references across the
64 compiled TrueTUs. It writes only a report and rehashes all
source files to prove no edits.

```powershell
Set-Location 'C:\Users\jorda\Mercenaries-Recompiled-Xbox360'
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
$k1 = '.\ports\mercenaries\xbox360\integration_map\k1'
$stage = '.\build\phase6_integration_map'
python "$k1\Test-K1D-XactWriteSite.py"
if ($LASTEXITCODE -ne 0) { throw 'K1D synthetic regression failed' }
python "$k1\Inspect-K1D-XactWriteSite.py" --main "$stage\k1c_guest_write_site_va\main.cpp" --shards "$stage\k1a_dsobject_writer_watch\translated_shards" --out "$stage\k1d_xact_write_site\k1d-source-window.txt"
if ($LASTEXITCODE -ne 0) { throw 'K1D source inspection failed' }
notepad "$stage\k1d_xact_write_site\k1d-source-window.txt"
```

Upload the report for exact guest instruction/register interpretation.
No new XDK build or hardware test is requested for K1D.

## K1D XACTENG linked-list write proved -> K1E original tail-state witness

K1D hardware-source correlation found the guest VA `0027DD0C` in
`translated_029.cpp:15690`, function `sub_0027DC5B`. Original
translated code near that label does (abridged):

```cpp
edx = ebx + 0x74;                   // list head inside XACT context
eax = eax + 0x28;                   // new entry in recent allocation
GUEST_WRITE32(eax, edx);            // new Flink=head
ecx = GUEST_READ32(edx + 4);       // old head->Blink
GUEST_WRITE32(eax + 4, ecx);       // new Blink=old tail
GUEST_WRITE32(ecx, eax);           // old tail->Flink=new entry
ecx = GUEST_READ32(eax);
GUEST_WRITE32(ecx + 4, eax);       // head->Blink=new entry
```

K1C observed the `GUEST_WRITE32(ecx, eax)` consequence:
`address=00041D70`, `value=01B672D8`, `before=00041D59`.
There are TWO candidate stores within this same guest
tick that could have produced the K1C observation:
`GUEST_WRITE32(ecx,eax)` if the old tail is `00041D70`,
OR `GUEST_WRITE32(ecx+4,eax)` later if the list head
is `00041D6C`. K1C tracked the **block**, not the individual
store. Either result would place a list pointer into the XBE
`.text` range, so the root cause remains under investigation.
The later DSOUND `EFEE0EC4` read has NOT yet been proven to
be caused by this particular store.

Next, K1E instruments **only translated_029.cpp** at the existing
XACT list-link site. It logs `K1E XACT LIST PRE` immediately before
the original `GUEST_WRITE32(ecx, eax)`, showing `ebx`,
`edx=head`, `ecx=tail`, `eax=node`, `edi`,
`eventcount`, and guest ESP. Its two flags
`tail_hits_41D70` and `head_hits_41D70` explicitly
disambiguate the original link-tail and head-backlink
write targets without introducing another guest-memory read. It reuses the K1C main XEX
provenance, leaves 63 other TrueTU source files and all generated
headers unchanged, and preserves all guest register writes,
guest memory reads/writes, existing APU policy and hard fences.
Only one source unit is new to the incremental VS17 compile.
Do **not** replace the tail pointer or bypass the hard stop.

```powershell
Set-Location 'C:\Users\jorda\Mercenaries-Recompiled-Xbox360'
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1E-XactListTailWatch.ps1'
```

Use `-PreflightOnly` for synthetic test, SHA checks and staging only.
If incremental VS17 Xbox 360 Release succeeds, run **only**:

`build\phase6_integration_map\k1e_xact_list_tail\xdk\Merc-K1E-XactListTail.xex`

The K1C main boot marker will still appear:
`P6K1C-EXACT-WRITE-SITE-VA-20261030`. Look for the **new
one-shard marker** `K1E XACT LIST PRE:` near the prior
`K1C WRITE SITE:` message. K1E is diagnostic; current
27,029,593-tick frontier and zero pixels remain unbroken pending
hardware verification.

## K1E Windows synthetic-fixture line endings fix (2026-10-30)

The first K1E run passed K1C source/XEX/R76/K1D/64 TrueTU identity
checks but failed **before any XDK build** inside the synthetic
`stage()` test: `K1D linked-list instruction triple drift`.
Root cause was a test-only Windows file-writing mistake.
The fixture was already formatted with `\r\n`, but
`Path.write_text()` used Windows text translation a second time,
producing `\r\r\n` on disk; the exact K1D code anchor expects
normal CRLF. The actual frozen generated source was not responsible.

The fixture now uses `target.write_bytes(fixture("\r\n").encode("utf-8"))`
and asserts there is no `\r\r\n`. The K1E stager also rejects
bare CR / mixed LF / CRCRLF rather than falsely calling the
original XACT linked-list statements changed. No generated shard
source, XEX or hard fence was modified by this repair. Re-run the
same `Build-K1E-XactListTailWatch.ps1` command; it will run
the strengthened regression then stage the one-TU diagnostic
before an incremental XDK compile. Actual re-test still pending.

## K1E actual generated function-body lookup fix (2026-10-30)

After the CRLF regression fix, the K1E Python synthetic test
**PASSed** on Windows. Real 64-TU staging then stopped **before
XDK build** at `expected one XACTENG original function owner`.
That check counted every occurrence of
`void sub_0027DC5B(void)`, mistakenly treating a forward
declaration and the actual implementation as multiple owners.
K1D already identified the true function in
`translated_029.cpp` with `loc_0027DD0C`.

K1E now matches **exactly one definition with its opening
brace**, bounds the body at the top-level closing brace, and
requires the original tick marker and exact three-statement
guest list-link sequence inside that body. Forward declarations
are allowed; two definitions or zero definitions fail closed.
The synthetic test now mimics the real declaration+definition
shape under both LF and CRLF, and checks missing/duplicate
bodies. No source modification or hardware claim follows
from this change until the local build confirms it.

Re-run the unchanged `Build-K1E-XactListTailWatch.ps1`
command from above. The expected XEX path is unchanged.

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

## K1E hardware confirmation and K1F source-only next step (2026-10-30)

The K1E diagnostic **executed on Xbox 360**, observing eight original
XACT list-link insertions at guest VA 0027DD0C. The first pre-write
sample had EBX=00000018, list head=0000008C, head Blink address=00000090,
old tail=00041D70, inserted node=01B672D8, tail_hits_41D70=1,
head_hits_41D70=0. Immediately afterward K1C confirmed the original
XACT store wrote guest[00041D70]=01B672D8. The destination is inside
the original retail executable .text range. This is now an observed
damaging store, **not** a speculative guest address or CPU fault.

The same downstream DSOUND READ32 EFEE0EC4 hard stop remains at
27,029,593 ticks. display_calls=0 and framebuffer=00000000. The XACT
list-head origin and how EBX became 00000018 are still UNKNOWN.
Do not replace head/tail, map low-memory pointers, or remove hard fences.

Run this K1F read-only source/caller provenance audit before any more XDK builds:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1F-XactListHeadProvenance.py' `
    --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
    --k1e-manifest '.\build\phase6_integration_map\k1e_xact_list_tail\k1e-xact-tail-manifest.json' `
    --out '.\build\phase6_integration_map\k1f_xact_head_provenance.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1F source audit failed' }
Get-Content '.\build\phase6_integration_map\k1f_xact_head_provenance.txt' -Raw
```

Share only the focused K1F report, not entire original retail game assets.
The audit verifies the frozen owner/K1E hashes and extracts original
function setup, EBX writes and direct lexical callers without compiling
or changing generated guest code.

## K1F source audit PASS -> K1G hardware register-lifetime test (2026-10-30)

K1F passed against the frozen original `translated_029.cpp` and the
K1E stage owner hash without a new XDK build. `sub_0027DC5B` copies
`ebx = ecx` at original source line 15570 and makes no other explicit
EBX assignments in that function. K1E nevertheless observed EBX=00000018
at the XACT list write. This does **not** yet prove incoming ECX was 18:
several nested translated calls execute before the damaging store, and
they might clobber shared guest register state. K1F found zero direct
lexical calls to `sub_0027DC5B` among the 64 original shards; indirect
dispatch or host-owned calls are not excluded.

The new K1G *instrumented* stage builds from the existing SHA-verified
K1E 64-TU staged set, adds host-only trace blocks to exactly
`translated_029.cpp`, and preserves the full K1E source witness.
Snapshots are taken at ENTRY before EBX=ECX, POST_COPY, and immediately
after the translated calls at guest labels DC69, DC8A, DCAC, DCBB, DCE5,
plus BEFORE_LIST at DD06. The K1E pre-write tail trace remains at DD0C.
Guest memory reads/stores, guest register assignments and hard fences are
unchanged. This instrumentation is NOT an EBX or list-pointer repair.

From the Mercenaries repository root:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1G-XactRegisterProvenance.ps1'
```

To run all synthetic/provenance checks and stage the K1G source without
XDK compilation, append `-PreflightOnly`.

On build success **deploy only**:

`build\phase6_integration_map\k1g_xact_register_provenance\xdk\Merc-K1G-XactRegisterProvenance.xex`

Capture `K1G XACT ABI ENTRY`, `POST_COPY`, `AFTER_D5C0`,
`AFTER_29FDF0`, `AFTER_29E435`, `AFTER_28345A`,
`AFTER_1787C0`, `BEFORE_LIST`, followed by `K1E XACT LIST PRE`.
Compare the first calls to detect the first transition to EBX=18.
Do not infer an entry-argument bug until that on-hardware comparison.
XDK compiler and Xbox K1G results remain unverified pending local run.

## K1G Xbox EBX corruption boundary -> K1H offline DSOUND source audit (2026-10-30)

K1G boot and all 8 checkpoint classes executed on Xbox 360.
`sub_0027DC5B` ENTERED with `ECX=01B5C320`; `POST_COPY` and
`AFTER_D5C0` confirmed `EBX=01B5C320` (valid XACT object pointer).
`AFTER_29FDF0` instead reports `EBX=00000018`, `ECX=0`, `EAX=0`,
`EDX=024908B8`, with `ESP=008BF974` unchanged across the outer
call boundary. Later checkpoints retain `EBX=18`, producing the
proven low list head `0x8C` and damaging `WRITE32[00041D70]`.
Therefore the change occurs somewhere inside the original translated
`sub_0029FDF0()` call tree, not at the original XACT function entry.
The exact nested function or epilogue responsible is **not** yet proven.

The subsequent `READ32 EFEE0EC4` memory fence is unchanged at
`27,029,593` ticks, `display_calls=0`, framebuffer zero. This is
diagnostic progress rather than any new display progress.

The new `Audit-K1H-DsoundCalleeSave.py` is source-only and requires
the K1E original TrueTU manifest/source SHA. It prints the complete
original body of `sub_0029FDF0` (bounded view), EBX assignments,
PUSH32/POP32 sites, returns, direct callsites and immediate callees.
It does not run XDK or replace EBX with a guessed value.

From repo root:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1H-DsoundCalleeSave.py' `
    --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
    --k1e-manifest '.\build\phase6_integration_map\k1e_xact_list_tail\k1e-xact-tail-manifest.json' `
    --out '.\build\phase6_integration_map\k1h_dsound_callee_save.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1H audit failed' }
Get-Content '.\build\phase6_integration_map\k1h_dsound_callee_save.txt' -TotalCount 100
```

Share the full K1H report file. Only once the original callee-save
path is understood should a corrective translation change be proposed.

## K1H full report -> K1I bounded recursive DSOUND EBX source proof (2026-10-30)

K1H full audit passed. The original `sub_0029FDF0` (68 lines,
`translated_041.cpp`) has zero lexical EBX writes, and calls
`sub_0029CDBE` plus `sub_0029FD83`. Both these direct callees also
have zero lexical EBX writes. **This does not exclude nested calls or
indirect dispatch:** `sub_0029CDBE` has a conditional ICALL and
`sub_0029FD83` makes four additional direct calls to
`sub_002A41EE`, `sub_0029CB9F`, `sub_0029CF0B`,
`sub_0029FC4A`, and has an indirect call near its end.

The K1G Xbox baseline remains: `EBX=01B5C320` before the call to
`sub_0029FDF0`, `EBX=00000018` on return. `K1E` then writes to
`guest .text[00041D70]`; DSOUND later hits the hard fence
`READ32 EFEE0EC4` at tick `27029593` with no display calls.

K1I is a SHA-checked **source-only** graph scan of up to four direct-call
edges from `sub_0029FDF0`. It ranks EBX assignment candidates,
includes source snippets, and prints the complete original
`sub_0029FD83` plus all 4 direct child function call/EBX sites.
This may reveal a likely missing callee-save path, but lexical
reachability cannot establish which branch executes on the Xbox.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1I-DsoundNestedEbx.py' `
  --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
  --k1e-manifest '.\build\phase6_integration_map\k1e_xact_list_tail\k1e-xact-tail-manifest.json' `
  --out '.\build\phase6_integration_map\k1i_dsound_nested_ebx.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1I audit failed' }
Get-Content '.\build\phase6_integration_map\k1i_dsound_nested_ebx.txt' -TotalCount 60
```

Upload the complete K1I text report. No XDK/Xbox needed for this run.
Do not blindly restore EBX at the XACT callsite, guess guest pointers,
or relax any unknown-address/VP/MMIO hard fence.

## K1I source graph PASS -> K1J DSOUND child-call EBX hardware witness (2026-10-30)

K1I passed on the actual 64 original TrueTUs: 13,510 function bodies,
29 bounded reachable DSOUND functions, 0 missing bodies, no cap clipping.
`sub_0029FC4A` (`translated_053.cpp`) contains 10 lexical EBX writes
including `ebx = esi + 0x18`, multiple `r59_saved_ebx` restores,
and an eventual `POP32(esp, ebx)`. Static reachability **does not**
prove that the `0x18` instruction executes along the live failing
path or that the original register is incorrectly preserved.

The new K1J stage starts from the hardware-tested K1G stage and
adds register-only traces to exactly **two** new TrueTUs:
`translated_041.cpp` (`sub_0029FDF0`: function entry, after
`sub_0029CDBE`, after `sub_0029FD83`, before return) and
`translated_017.cpp` (`sub_0029FD83`: entry, after
`sub_002A41EE`, `sub_0029CB9F`, `sub_0029CF0B`,
`sub_0029FC4A`, and before return). It retains the prior
`translated_029.cpp` K1G/E Xbox witness byte-for-byte. Compared with
K1G, the 62 non-target TUs and all headers are byte-identical.
Guest memory ops, guest register assignments and hard fences unchanged.

From the Mercenaries repository root:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1J-DsoundReturnEbxWatch.ps1'
```

Use `-PreflightOnly` for source/synthetic/SHA gates without invoking
VS2017 XDK. On success, deploy **only**:

`build\phase6_integration_map\k1j_dsound_register_edges\xdk\Merc-K1J-DsoundRegisterEdges.xex`

On Xbox capture the `K1J DSOUND ABI` checkpoints plus the original
`K1G XACT ABI` and `K1E XACT LIST PRE` witnesses. The first
checkpoint where EBX differs from XACT object's `01B5C320`
will determine the next localized source audit or translation repair.
The K1J test is **not** a speculative register restoration. No
compiler or Xbox result claimed before the local build and boot.

## K1J Xbox hardware PASS -> K1K exact FC4A EBX/stack audit (2026-10-30)

K1J captured DSOUND register boundaries on Xbox. Original XACT
`EBX=01B5C320` survives `sub_0029CDBE`, `sub_0029CB9F` and
`sub_0029CF0B`; directly after `sub_0029FC4A`, EBX is
`00000018` (first bad observed return boundary). K1E again
confirms `WRITE32[00041D70]=01B672D8` via wrong XACT head `0x8C`.
Hard-fenced `READ32 EFEE0EC4` at tick `27029593` remains unchanged.
No actual guest display calls (`display_calls=0`, framebuffer 0).

K1I's exact original `sub_0029FC4A` owner is
`translated_053.cpp:17686..18123` (438 source lines). It contains
`ebx = esi + 0x18` at line 17996, `PUSH32(esp, ebx)` at 17743
and 18025, `POP32(esp, ebx)` at 18118, and three explicit
`ebx = r59_saved_ebx` assignments. The working EBX values and
nested call structure make a blind XACT-level EBX restoration
unsound: actual saved stack contents and return path are unverified.

K1K is a further **read-only source audit**, not another XDK rebuild.
It SHA-verifies K1E/K1I provenance, exact source line anchors, and
writes the entire original FC4A body plus numbered EBX, PUSH/POP,
branch/return, and call-site excerpts to an independent report.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1K-FC4A-EbxRestorePath.py' `
  --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
  --k1e-manifest '.\build\phase6_integration_map\k1e_xact_list_tail\k1e-xact-tail-manifest.json' `
  --k1i-report '.\build\phase6_integration_map\k1i_dsound_nested_ebx.txt' `
  --out '.\build\phase6_integration_map\k1k_fc4a_ebx_restore.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1K audit failed' }
Get-Content '.\build\phase6_integration_map\k1k_fc4a_ebx_restore.txt' -TotalCount 65
```

Upload the COMPLETE K1K report; do not infer final EBX ABI fix
from one local x86 register mutation. No guest code or hard fence changes.

## K1L withdrawn; K1M source investigation at A19FC -> A739F (2026-10-30)

After the actual Xbox K1J trace and K1K original source, a more
upstream +4 ESP displacement was found:

- `sub_002A19FC` at its `sub_002A739F` direct call: R72
  `esp_before=008BF8B4 esp_after=008BF8B8` (+4). Its callsite
  only pushes the synthetic return address, not a guest parameter.
- The next `sub_002A2A16` call has the **same +4** across the
  R72 witness but deliberately pushes guest argument `0x7FF`
  first, so that one's +4 is an expected callee argument cleanup.
- `sub_002A19FC` prologue saves ECX, EBX, EBP, ESI, EDI;
  its epilogue pops EDI, ESI, EBP, EBX, ECX. The first shift
  is consistent with K1J R71 raw output
  `EBX=01B5C554` (saved ECX), `ESI=008BFF8C` (saved EBP),
  `EDI=008C1104` (saved ESI), all one slot off.
- It then produces `esp=008BF8D0` instead of `008BF8CC`
  at its FC4A call edge, leading FC4A's own epilogue to restore
  `EDI=0`, `ESI=01B5C320`, `EBX=0x18`, and corrupt XACT list head.

**Do not build or deploy the former experimental K1L patch.**
It would adjust ESP only *after* A19FC had already popped
the wrong registers and thus would not fix the upstream cause.
The unverified `Stage-K1L-A19FCStackBalance.py` was deleted from
the branch to prevent an unsafe build. K1J remains the last
hardware-tested diagnostic XEX.

Next source-only investigation: extract original
`sub_002A739F` from `translated_009.cpp` and optionally
`sub_002A2A16` from `translated_042.cpp` as a convention control.
Audit exact epilogue ret width and any nested calls before
proposing a location-specific repair. No broad EBX/ESP patch
or hard-fence relaxation.

## K1M original callee extraction -> K1N no-build nested return-width audit (2026-10-30)

The K1M exact-source extraction PASSED, demonstrating that
`sub_002A739F` (`translated_009.cpp`) saves ESI/EDI and finishes
with `POP32(edi); POP32(esi); esp+=4; return; /* ret */`.
`sub_002A19FC` passes no stack argument at this callsite, so
R72's `A739F esp_before=008BF8B4 esp_after=008BF8B8` is
an abnormal **+4** despite A739F's source-level plain ret.
A739F also calls 8 unique direct helpers (9 callsites):
`002A7322`, `002A70AA`, `002A6FDD`, `002A67E2`,
`002A6B98`, `002A6EE9` (zero explicit stack args),
`002A6D1A` (one explicit stack arg), and `002A77BE`
(one explicit stack arg on each of two callsites).

The `002A2A16` control has a real one-word argument and
`esp+=8; return; /* ret 4 */`, correctly explaining the
separate R72 `+4` observation at that particular call.

K1N is a read-only indexed TrueTU analysis of A739F's direct
helper bodies and ret widths, with provenance, exact K1M source
matching and full numbered helper source to spot nested drift.
It does NOT infer live execution paths from lexical return widths.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1N-A739FReturnContracts.py' `
  --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
  --k1e-manifest '.\build\phase6_integration_map\k1e_xact_list_tail\k1e-xact-tail-manifest.json' `
  --k1m-report '.\build\phase6_integration_map\k1m_a739f_call_contract.txt' `
  --out '.\build\phase6_integration_map\k1n_a739f_return_contracts.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1N audit failed' }
Get-Content '.\build\phase6_integration_map\k1n_a739f_return_contracts.txt' -TotalCount 95
```

No XDK build or deployment. Upload the entire report.
Do not reintroduce the withdrawn late K1L ESP repair.

## K1N PASS (7 matched return widths, 1 tail transfer) -> K1O (2026-10-30)

User's K1N audit passed on original 64-TU sources, 13,510 bodies,
and found zero ordinary child callsite/ret-width mismatches.
Seven of eight direct A739F helpers have standard lexical
argument cleanup matching their callers. The remaining first
helper `sub_002A7322` (`translated_057.cpp`) has no inline
`return; /* ret */`: after popping saved ESI it executes
`g_seh_ebp = ebp; sub_002A7AE8(); return; /* tail jmp */`.
This is **not yet proof** of which callee shifted ESP on Xbox.

`Audit-K1O-A7322TailReturn.py` follows this exact translated
tail-transfer chain through `sub_002A7AE8`, reporting its terminal
return widths and full original source. It refuses different
frozen SHA, missing K1N/K1M source evidence, missing A7AE8 body,
or attempts to overwrite frozen inputs. No XDK build or changes.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1O-A7322TailReturn.py' `
  --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
  --k1n-report '.\build\phase6_integration_map\k1n_a739f_return_contracts.txt' `
  --k1m-report '.\build\phase6_integration_map\k1m_a739f_call_contract.txt' `
  --out '.\build\phase6_integration_map\k1o_a7322_tail_return.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1O audit failed' }
Get-Content '.\build\phase6_integration_map\k1o_a7322_tail_return.txt' -TotalCount 75
```

Upload full K1O source-only report before considering another
on-hardware binary. The withdrawn K1L correction remains unsafe.

## K1O PASS -> K1P two-TrueTU stack-edge Xbox witness (2026-10-30)

K1O PASS resolved `sub_002A7322` (`translated_057.cpp`)
tail jump to `sub_002A7AE8` (`translated_050.cpp`),
whose terminal epilogue is `esp += 4; return; /* ret */`
(zero stack arguments). Therefore the tail-jump's lexical
return width is **correct**, and should not be blindly changed.
The child A7AE8 has direct and indirect nested calls; an ESP
shift within these or other A739F children is still possible.

Latest K1J hardware still shows A19FC -> A739F ESP
`008BF8B4 -> 008BF8B8` (+4 with no stack arguments), and
later A19FC / FC4A save/restore stack-slot displacement
corrupts XACT `EBX` to `00000018`, causing the erroneous
guest text list write and READ32 `EFEE0EC4` hard stop.

K1P is **diagnostic only**. It stages 15 source-bounded
call-edge ESP delta logs across two TrueTUs:
`translated_009.cpp` (9 direct A739F callsites)
and `translated_057.cpp` (5 A7322 children plus A7AE8 tail).
Expected deltas for ordinary callsites are argument-cleanup
bytes from immediately before the synthetic return push;
for tail transfer the expected +4 is return-address consumption.
Two separate A77BE callsites receive independent labels.

All original guest calls, registers, memory operations, 64
translated shards, and safety fences remain unchanged except
for host-side log snippets in those 2 files. K1J/G/E original
Xbox witnesses are retained byte-for-byte.

Run from repo root, assuming local K1J and K1O source reports:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
  '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1P-A739F-A7322-StackEdges.ps1'
```

Use `-PreflightOnly` to check SHA, synthetic probes and all
source gating without compiling. If build succeeds, the new
diagnostic XEX is:

`build\phase6_integration_map\k1p_a739f_a7322_stack_edges\xdk\Merc-K1P-StackEdges.xex`

On Xbox, collect *all* `K1P STACK EDGE` lines plus the original
`K1J DSOUND ABI`, `P6DQ R72 DSOUND NESTED ABI`, `K1E XACT LIST PRE`,
and hard-stop context. Look for the **first** `delta != expected`.
That edge determines the next local source contract investigation.
Do not build/deploy the withdrawn K1L late-FC4A repair.

## K1P HARDWARE: exactly one bad stack edge -> K1Q no-build audit (2026-10-30)

The K1P Xbox run reached all **15/15** inserted call-edge
checkpoints and **only one** differed from expected cleanup.
At `sub_002A739F -> sub_002A6B98`: `esp_before=008BF8A8`,
`esp_after=008BF8AC`, `delta=+4`, `expected=0`.
Prior A739F edges A7322/A70AA/A6FDD/A67E2 were all
zero; A6EE9 was zero, A6D1A and both A77BE calls all had
the expected +4 (one argument); all A7322 subcalls and tail
also matched their expected deltas. Thus A6B98 is the first
observed faulty **immediate** A739F child return.

A6B98 (`translated_005.cpp:16208..16347`) already contains
R49's `ESI REPAIR` check immediately after calling A7B73.
On hardware at `002A6BB0`, raw `ESI=00000000`, expected
`008BFFA0` and EBX `008BFF8C`: strong indication of an
even earlier child register/stack issue, but not yet a proved
culprit inside A7B73. A6B98 saves EBX/EBP/ESI/EDI and
restores all four with POP32 before its plain `ret`.

Do not patch A739F, A19FC, or FC4A return ESP: that
would mask corrupted register restores already performed
inside the deeper callee. Next investigate only A6B98's
five nested direct callee types (nine callsites) using K1Q.

`Audit-K1Q-A6B98NestedStack.py` is READ ONLY; it verifies
64 TrueTUs/K1E and K1N provenance, prints exact source
and caller/callee ret-width contracts, and checks the
especially suspicious A6B98->A7B73 edge. There is no XDK.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
python '.\ports\mercenaries\xbox360\integration_map\k1\Audit-K1Q-A6B98NestedStack.py' `
  --original-shards '.\build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards' `
  --k1e-manifest '.\build\phase6_integration_map\k1e_xact_list_tail\k1e-xact-tail-manifest.json' `
  --k1n-report '.\build\phase6_integration_map\k1n_a739f_return_contracts.txt' `
  --out '.\build\phase6_integration_map\k1q_a6b98_nested_stack.txt'
if ($LASTEXITCODE -ne 0) { throw 'K1Q source audit failed' }
Get-Content '.\build\phase6_integration_map\k1q_a6b98_nested_stack.txt' -TotalCount 65
```

If all nested return widths match, prepare **one** K1R
ESP/EBX/ESI edge witness inside A6B98, particularly
the A7B73 return site. If a width mismatch is proven,
inspect it against actual runtime branch before correction.
The old crash remained tick 27,029,593, `READ32 EFEE0EC4`,
`display_calls=0` in K1P. No production correction proven.

## K1Q PASS -> K1R first bad A6B98 child + conditional A7B73 epilogue (2026-10-30)

K1Q source-only audit passed against the original 64 TrueTUs.
All 5 A6B98 nested callee return contracts match the caller's
declared stack arguments: A7B73 `ret 4`, A7605 `ret 8`,
A7818 `ret 12`, A766D `ret 8`, A7598 `ret 4`.
However K1P hardware still measured the FIRST bad A739F direct edge:
`A6B98 esp=008BF8A8 -> 008BF8AC` (+4, expected 0).
The R49 hardware witness records unexpected raw `ESI=0` immediately
after the A6B98->A7B73 call. Standard return width matching
does **not** prove that A7B73's internal indirect calls preserved
the emulated guest stack or correct saved register slots.

K1Q's `translated_044.cpp:21121..21290` A7B73 source has five
`PHASE6DJ_ICALL_SAFE` sites, four direct calls, and a branch where
`loc_002A7C49` executes `POP32(esp, esi)` before merging into
`loc_002A7C4A` (which restores EDI/EBX/EBP and `ret 4`).
An alternate path jumps directly to `loc_002A7C4A`.
Only Xbox execution can tell which path was taken.

K1R preserves the full previously hardware-proven K1P 64-TU set.
Only `translated_005.cpp` (A6B98) and `translated_044.cpp`
(A7B73) receive host-side diagnostic C++ blocks. It records:

- 9 exact A6B98 child callsite ESP / EBX / ESI before/after edges,
  with K1Q-proven argument cleanup expectations.
- 4 exact A7B73 direct callsite ESP / EBX / ESI edges
  (expected return cleanup explicitly UNKNOWN, not guessed).
- 5 A7B73 indirect dispatch blocks, with before/after ESP, EBX, ESI.
- 3 A7B73 epilogue path checkpoints before POP ESI, POP EDI,
  and final `ret 4`, identifying the live branch/stack position.

**Zero new guest reads/writes/register assignments**, no patched
return widths and no changes to XACT or hard MMIO fences.
All prior K1P/J/G/E telemetry persists byte-for-byte.
`Test-K1R-A6B98A7B73StackPath.py` reconstructs the **real K1Q
original C++ function bodies**, tests both LF and CRLF and
rejects altered source anchors or duplicate probe insertion.
Do not use withdrawn K1L ESP/EBX compensation.

From the repo root, with K1P staged and K1Q report present:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1R-A6B98A7B73StackPath.ps1'
```

Diagnostic output XEX (after verified successful Release Xbox 360
incremental build):

`build\phase6_integration_map\k1r_a6b98_a7b73_stack_path\xdk\Merc-K1R-A6B98-A7B73-StackPath.xex`

The next Xbox capture must include `K1R CALL`, `K1R ICALL`,
`K1R PATH`, `K1P STACK EDGE`, `P6DQ R49 ESI REPAIR`,
and `K1J DSOUND ABI`, and the first hard stop.
Resolve the earliest nonzero A6B98 child delta and/or the A7B73
indirect/epilogue path before changing guest ESP.

## K1R HARDWARE: earliest actual +4 due to ordinal 44 consuming A7B73's saved ESI (K1S)

K1R Xbox log (2026-10-30) now establishes the complete fault:

- In `sub_002A7B73`, `EBP=008BF888`. At `loc_002A7BD1`
  the original translation executes `PUSH32(esp, esi)` at
  `EBP-12=008BF87C`; this is the saved ESI that the later
  `loc_002A7C49` `POP32(esp, esi)` must restore.
- Kernel ordinal 44 (`HALGETVECTOR44`, from thunk `002DBE20`)
  returns `ESP=008BF880=EBP-8` instead of preserving
  the saved ESI slot at `008BF87C=EBP-12`.
- `K1R ICALL A7B73_ICALL_2 before=008BF880 after=008BF880`,
  showing that the native continuation restored the pre-save
  stack height. Original call passes `6` and `ebp+8`
  as explicit parameters; the preceding `PUSH ESI` is a
  long-lived register save, **not** a third kernel parameter.
- The matching `POP ESI` at `loc_002A7C49` then reads
  `ESI=00000000`. The later POP EDI/EBX/EBP become
  one stack slot displaced (`EBX=008BFF8C`).
- `K1R CALL A6B98_002A7B73_1` observes +8 ESP
  instead of the expected +4, while all remaining A6B98
  child calls match their `ret` stack-argument widths.
- Later `K1P A739F_002A6B98_1` therefore returns +4
  rather than zero, and `K1J FD83_AFTER_FC4A EBX=00000018`.
  The final stop still occurs at `READ32 EFEE0EC4`,
  tick 27,029,593, with no display calls.

**K1S** is a guarded, one-TU **diagnostic correction**.
It changes only `translated_044.cpp` at the exact
`A7BD1 -> A7BDE` executed edge, after K1R's *raw*
`ICALL_2` witness. It applies
`if (esp == ebp - 8u) esp = ebp - 12u;`,
and logs the raw/current/expected ESP. The guard prevents
an adjustment on a different stack shape. It is not
a generic ordinal 44 handler change or an XACT EBX mask.

Unchanged: all existing K1R/P/J/G/E traces, other 63 TrueTUs,
all headers, guest reads/writes, indirect call targets and original
guest PUSH/POP operations and `ret 4`, as well as MMIO/VP fences.
The script refuses stale output and changed provenance; the
synthetic test reconstructs A7B73 from the real K1Q source.

Run from repo root:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Build-K1S-HalGetVectorSavedEsi.ps1'
```

Pass `-PreflightOnly` to perform all SHA and original-source tests
without the VS2017 Xbox 360 incremental build.
After successful build, the diagnostic XEX is:

`build\phase6_integration_map\k1s_halgetvector44_saved_esi\xdk\Merc-K1S-HalGetVectorSavedEsi.xex`

**Hardware PASS criteria** for the specific stack repair:

- `K1S HALGETVECTOR44 ESI SLOT: raw_esp=008BF880`
  `expected_esp=008BF87C repaired=1 final_esp=008BF87C`.
- `K1R PATH A7B73_BEFORE_POP_ESI esp=008BF87C`;
  `BEFORE_RET4 esp=008BF88C`.
- `K1R CALL 002A6B98_002A7B73_1 delta=00000004`
  `expected=00000004`, with original EBX and ESI restored.
- `K1P STACK EDGE 002A739F_002A6B98_1 delta=0`
  and `K1J FD83_AFTER_FC4A ebx=01B5C320`.

The historical fault should move or disappear if this was the
only initiating defect. **Do not claim display/audio PASS**
without new Xbox evidence. Preserve the hard stop on unknown
MMIO and guest reads. If the exact guard does not fire,
do not widen it; inspect the K1S trace and return untouched.

## FIRST PIXELS: verified K1S -> multi-root offline closure plan (2026-10-30)

Hardware goal: **a real guest `display_calls >= 1`**, generated
by the original guest's AvSetDisplayMode/presentation work, never
by synthesizing or incrementing the diagnostic counter.

The K1S Xbox run proves the precise saved-ESI repair and all downstream
register checks: `K1S repaired=1`, `A6B98->A7B73 delta=+4`,
`A739F->A6B98 delta=0`, `FC4A EBX=01B5C320`.
The old `READ32 EFEE0EC4` fault is NOT present in that run.
The next genuine hard stop is `DIRECT_FRONTIER 002A3A5A` at
`27,031,807` translated ticks (`fault=0`). A native Xenos device
and D3D guest device are initialized but guest `display_calls=0`
and framebuffer `00000000`.

The historical static Rocket packer sorts DSOUND candidates by
numeric distance from `002A6713`, not by *actual live
reachability* from the latest frontier. To stop incremental
one-function-at-a-time probes, `Audit-PixelBatchClosure.py`
performs a **single local-source-only** multi-root inventory:

- exact observed DSOUND call target `002A3A5A` and up to
  112 directly reachable nodes;
- guest present root `0023A3CE` and up to 80 nodes;
- observed D3D/XGRPH roots `0028E700`, `00290895`, `0029C8BE`
  and up to 64 reachable nodes each;
- cross-check original 64 K1S TrueTU bodies against the complete
  local generated C corpus and `functions.json`; flag exact
  functions, **mid-function targets** and unsupported bodies;
- run the existing Phase4C/5BB direct-call rewriting in memory
  for lexical dependency screening; write a ranked set of up
  to 192 source candidates and explanatory summary.

Read-only code; no game payload copied, no XDK build, no guest
memory or register changes, and unknown MMIO/NV2A/VP fences
remain hard. Lexical source-clean is not a proven compile.

From the repo root, **one command**:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Plan-PixelBatch.ps1'
```

Produces:

- `build\phase6_integration_map\pixel_batch\pixel_batch_summary.txt`
- `build\phase6_integration_map\pixel_batch\pixel_batch_closure.json`

Only after this identifies **verified exact generated sources**
should the batch be added to the incremental K1S TrueTU/lookup
set and tested together on Xbox. If the live target is mid-function
or source-missing, do not invent a return or add a lookup stub.
Do not run another Xbox build on guesswork, and never force
`display_calls` to increase without a real display operation.

## PIXEL OFFLINE PLAN PASS — A3A5A exact body; APU helper source proof next (2026-10-30)

User's `Plan-PixelBatch.ps1` executed **PASS** on K1S TrueTUs:

- `0x002A3A5A`: exact original generated function, not a mid-function
  target. `label_present=True` is normal for a function start.
- Its only two unresolved lexical symbols are
  `recomp_apu_read32` and `recomp_apu_write32`.
- Four total new source candidates across live DSOUND/presentation
  closure: **one exact original body**, three source/support gaps.
  The 17/20 already-packed presentation-root nodes do NOT imply
  three simple functions away from visible pixels.
- K1S hard fence policy unchanged; no new XDK build yet.

**Do not** guess that `recomp_apu_*` and `phase6ch_apu_*`
are semantically interchangeable merely because names suggest
APU. The maintained Rocket `route_all_dsound_accesses`
rewrites `GUEST_READ/WRITE*` macros, not necessarily the
`recomp_apu_*` helpers in this source. A blind name-only
rename could corrupt guest reads or bypass hardware policy.

To make one batched compile decision, run the fast no-XDK
`Prove-PixelApu.ps1` on the existing planner JSON. It
extracts the exact original 002A3A5A C body, the declared
APU helper signatures/definitions from current runtime
sources, and summarizes all 4 candidate types. It does
NOT patch or publish original game assets.

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Prove-PixelApu.ps1'
```

Output: `build\phase6_integration_map\pixel_batch\pixel_apu_contracts.txt`.

After checking its actual helper contracts, batch source-correct
translation/dispatch coverage into K1S's 64 TrueTU build once,
alongside any support-clean present-root additions. Keep unknown
VP/MMIO hard fences and only count true guest AvSetDisplayMode
or presentation requests. No one-function-per-build loop.

## PIXEL BATCH — original A3A5A integrated into K1S TrueTUs (2026-10-30)

User uploaded `pixel_apu_contracts.txt`, generated by the preceding
offline proof. It confirms original `recomp_0013.c`
SHA256 `c0808e2f58c27c82e837e29d8e1b448a4745ebb47ec1b549b9b31cb56eecd473`,
function `sub_002A3A5A` at line 42763 (231 lines).

**Important helper evidence:** 2 lexical `recomp_apu_read32` occurrences
include one `extern` declaration and **one** actual VP FREE poll at
`FE820010`. Six lexical `recomp_apu_write32` occurrences include
one `extern` and **five** actual VP writes (`FE820160`,
`FE820400..FE82043C` loop, `FE82043C`, `FE8202F8`, `FE82031C`).
The existing maintained Phase6DQ host main implements
`phase6ch_apu_read32` for the exact FE820010 readiness value 0x80
and hard-fences other unknown VP reads; its
`phase6ch_apu_write32` records aligned VP command writes.
Outside those ranges it retains the existing guest/MMIO route.

`Stage-PixelA3A5ABatch.py` builds a source-derived increment:

- Read the original C **only** from the user's local generated
  `recomp_0013.c`; verify exact SHA and the 231-line function
  proof. Never commit/distribute this generated guest code.
- Keep all existing 64 K1S TrueTUs/headers, the ordinal-44
  saved-ESI fix, and the original translated return (`ret 8`).
- Restore exactly matching `phase4c_direct_frontier(002A3A5A)`
  callsite(s) to the original direct subcall, preserve their
  existing guest argument pushes, and insert a real exact pack
  lookup case for `002A3A5A` in the staged host `main.cpp`.
- Install the 231-line genuine generated body in one original
  caller TrueTU, preferring the caller to minimize recompiles;
  three original direct child callees must already compile
  exactly once from the K1S translation set.
- Route `recomp_apu_read/write32` and original DSOUND 8/16/32
  guest memory macros via the **existing** Phase6DQ APU routing.
  Reject altered readiness/VP addresses and unchanged-ABI
  violations. Never lower unknown VP/MMIO fences.
- Emit bounded `PIXEL A3A5A ENTRY` logging (only first 4),
  leaving the real guest display call count untouched.
- SHA-verify all non-target TrueTUs and headers and produce
  an explicit stage manifest and separate XEX output.

Only **one** incremental VS2017 Xbox 360 build (SkipClean) after
all original-source synthetic regression and SHA gates pass:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File '.\ports\mercenaries\xbox360\integration_map\k1\Build-PixelA3A5ABatch.ps1'
```

Optional `-PreflightOnly` runs tests/staging without XDK.

Build output after successful XDK link:

`build\phase6_integration_map\pixel_a3a5a_batch\xdk\Merc-Pixel-A3A5A-Batch.xex`

**What we can prove now:** original A3A5A source/ABI and
existing APU bridge code, not an Xbox execution result.
The four total planner candidates contained only **one**
new exact generated body. The remaining three presentation
lookups (`0022B150`, `0022B178`, `0022DDA4`) do not have
independent original generated C bodies; they may also be
covered by maintained startup/kernel helper code in host main.
Do not generate fake bodies or force a jump to graphics.

On Xbox watch `PIXEL A3A5A ENTRY`, the first next frontier
or genuine MMIO fence, `P6DQ PRESENT PROXIMITY`, and
`display_calls`/framebuffer. Success requires an actual
guest AvSetDisplayMode/presentation request; no fake counters.

### PIXEL K1C lookup-layout correction (2026-10-30, before XDK)

The user's real K1S `main.cpp` is the accumulated K1C host bootstrap,
not necessarily the older unsplit Rocket main. The first real
`Build-PixelA3A5ABatch.ps1` staging run failed:

`Missing or duplicate existing packed lookup function`.

All original-source A3A5A regression tests had passed, and no XDK
build started. **This was an unsupported host-layout assumption**
in our staging script, not a missing retail function. The Xbox
stop `DIRECT_FRONTIER 002A3A5A` comes from an exact *direct* guest
call; a new packed indirect lookup entry is not necessary for this
one restoration.

The corrected stager therefore leaves the entire K1C lookup and
indirect dispatch untouched. It restores only literal
`phase4c_direct_frontier(0x002A3A5Au);` callsite(s),
which must exist in the K1S host and/or TrueTU inputs. It adds
an external declaration only where a direct caller needs it,
places the real local generated body into a TrueTU, and requires
the entire existing APU/ret8/source-identity contract as before.
If there are no exact direct sites, it hard fails rather than
creating a fake lookup or bypass.

The regression tests now cover host source **with or without**
the legacy packed lookup function and an entirely unchanged
main.cpp when direct callers live only in TrueTUs. The PowerShell
preflight checks explicit manifest direct-only policy and asserts
there is no new lookup case. Compile still needs to pass on the
user's cached source.

## XBE-WIDE PREDICTIVE FRONTIER RECON (xboxrecomp, analysis-only)

Use `Run-XboxrecompRecon.ps1` to analyze the user's locally extracted,
SHA-verified Mercenaries `default.xbe` with `sp00nznet/xboxrecomp`,
without changing the native Xbox 360 recompilation build. The verified
XBE SHA256 is `AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7`.

The original 2026-10-30 run successfully completed whole-XBE function
discovery in **663.28 seconds**, then stopped because ABI analysis requires
`tools/func_id/output/identified_functions.json` (not previously run).
The current runner fixes the missing pipeline step and skips the
splitter's **forced full rescan**. It generates a semantically equivalent
predictive function/ABI/call-graph manifest from **saved** disassembler JSON.
The original binary and annotated full-assembly listings are not in the ZIP.

From the Merc360 repo root:

~~~powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw 'Git pull failed' }
$xbe = 'C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\default.xbe'
powershell.exe -NoProfile -ExecutionPolicy Bypass -File `
    '.\ports\mercenaries\xbox360\integration_map\k1\Run-XboxrecompRecon.ps1' `
    -Xbe $xbe -ResumeOnly
~~~

`-ResumeOnly` verifies existing `.disasm_cache.json` and related output
files. If not present or inconsistent with the exact retail XBE, it fails
instead of repeating the long scan. Omit the switch for a first run.

The pipeline runs XBE parsing, uses cached full executable-section
disassembly (including XPP), runs `tools.func_id`, then `tools.abi_analysis`
with explicit paths, and calls `Pack-XboxrecompRecon.py` to produce
`%LOCALAPPDATA%\Merc360-Xboxrecomp-Recon\Merc360_xboxrecomp_static_recon.zip`.
This contains full function metadata, original address ranges and static
call graph, ABI estimates, a priority XPP `002D5574` focus, and comparison
with original PIXEL batch TrueTUs. No game file bytes or source are packaged.

The analyzer's boundaries, indirect graph and ABI information are
heuristic. The report is a **prediction tool**, not evidence the guest
can display pixels or complete hardware initialization. Never bypass
hard MMIO fences or fabricate a display counter.


## K1 post-XPP next frontier + dual-track display audit (2026-10-30)

**Xbox hardware:** XPP 0x002D5574 executed; native XInput scan returned
connected mask 00000001. Next hardware DIRECT_FRONTIER: 0x002D559B
from 0x0023A3CE at **27,107,590 ticks** (previous 27,107,567;
gain +23; fault=0). Guest display_calls=0, framebuffer=00000000,
AvSetDisplayMode calls=0. This is a proven milestone, not a frame.

Run the source-only twin-track audit (no XDK or new disassembly):
Run-K1DisplayParallel.ps1 from the integration_map/k1 directory.

The runner reads the saved xboxrecomp metadata-only ZIP and xrefs.json
from the user-local Merc360-Xboxrecomp-Recon workspace, original locally
translated recomp_*.c, and the successful XPP-D5574 64-TrueTU stage.
It checks the D5574 manifest and original MMIO/hard-fence policy.

Audit A: XPP 0x002D559B with neighbors 0x002D5579 and 0x002D5574.
The original Mercenaries-Recompiled patch inventory associates D559B
with XGetDeviceChanges, but its exact guest ABI/device-change semantics
must be reviewed before another bridge.

Audit B: D3D/XGRPH missing candidates 0x002888A0, 0x00288F80,
0x00288B30, 0x00289E20, 0x0028A090, 0x00288960, 0x0029C13E;
read original translator sources, compiled TrueTU coverage, callees
and xref callsite owners.

Audit C: exact-name AvSetDisplayMode kernel ordinal 3 cross-references
from saved xrefs.json. No named refs does not prove the import
is unreachable, since indirect/thunk call edges may be missed.

Output directory: build/phase6_integration_map/post_xpp_display_recon
display_parallel_audit.txt is metadata-only.
xpp_original_source_LOCAL_ONLY.txt has private original XPP source for
local ABI review. Do not commit that code or retail game data to GitHub.
No function is automatically staged and no guest display call is faked.


## TGP482 XboxXBERecomp independent sidecar (2026-10-30)

Upstream: https://github.com/TGP482/XboxXBERecomp (MIT).
This is a SEPARATE original-Xbox XBE static recompilation engine.
Its generated runtime is for Windows x64/Direct3D12, not Xbox 360.
Use its function discovery, XDK 5849 signature database, and ABI results
as an independent source of evidence; never swap its outputs into our XEX.

Run from the Mercenaries git root with Windows PowerShell:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Run-TGP482SecondOpinion.ps1"

The default run clones the upstream SDK outside Mercenaries git and compares
its XDK5849 signature lengths/layout against the existing cached metadata-only
16,662-function xboxrecomp ZIP. It does not compile, read retail XBE bytes,
run Xbox, or write any game code.

Optional exact increasing analysis tiers (same command, add one option):
- -BuildTools: tools-only upstream xbe_symbols/xbe_recomp CMake build.
- -ScanXbe: above, plus exact XDK signature scan against locally verified retail XBE.
- -RunRecompiler: above, plus full independent code discovery and source generation.
- -UpdateSdk: explicitly fast-forward the cloned upstream SDK.
- -Generator "Visual Studio 18 2026": override CMake generator if needed.
- -Xbe "C:\path\default.xbe": override cached private original retail source.

All user-private output:
%LOCALAPPDATA%\Merc360-TGP482-XBERecomp\reports\tgp482_second_opinion.txt
(and .json). Upload those METADATA REPORTS only. Keep XBE, emitted C++,
generated mapping and signature config local and out of GitHub. The known
original retail SHA256 is strictly checked before any real XBE scan.

New hardware (xbWatson 2026-10-31): 27,107,602 translated ticks;
XPP D5272 and real XInputOpen port=0 handle=1 PASS. New genuine
DIRECT_FRONTIER 0023A3CE -> 002D52D4, XPP length 472, original recorded
direct children 002D6B3E, 002D7620, 002D79B6. Equal/near XDK
signature lengths are NOT sufficient proof of matching identities.
Also trace genuine D3DDevice_Swap/presentation, not just kernel ordinal 3.

## K1: TGP482 real Swap identification -> XPP D52D4 original-source audit (2026-10-31)

Independent TGP482 XboxXBERecomp scanner (XDK library build 5849)
assigned `D3DDevice_Swap=0x0028BDB0` by constant analysis, and
`XInputOpen=0x002D5272` via .XTLID. The original xboxrecomp inventory
agrees on exact starts. In the previous 64-shard pixel batch, Swap and
its six known direct callers were present. Upstream graph layers:
6 / 13 / 7; no known direct-only path from current
`0x0023A3CE -> 0x002D52D4` frontier to Swap within eight edges.
Indirect dispatch remains unproven; do not call it unreachable.

LAST HARDWARE: 27,107,602 translated ticks, XInputOpen native port=0
handle=1 PASS, next real XPP direct frontier 0x002D52D4, guest
display_calls=0. Saved static metadata has D52D4 size 472,
`old_pixel_batch=False`, and children 002D6B3E/002D7620/002D79B6.
This is not evidence that those children execute or that an independent
codegen succeeded.

For a NEW, NO-XDK diagnostic proving original generated-source bodies
and stack/ABI metadata at D52D4 and three callees (plus known Swap roots):

```powershell
cd "C:\Users\jorda\Mercenaries-Recompiled-Xbox360"
git pull --ff-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Run-K1TgpXppFrontierAudit.ps1"
```

This reuses the private original generated source corpus plus the cached
16,662-function metadata manifest; no fresh XBE scan, Xbox compile, or
deployment. It checks local source and optional staged Pixel A3A5A TrueTU
coverage without claiming the staged source is what is deployed.

Share only the metadata report:
`build\phase6_integration_map\tgp482_d52d4_source_audit\d52d4_source_abi_metadata.txt`.

A separate local source excerpt
`d52d4_original_source_LOCAL_ONLY.txt`
contains original guest-generated code for private ABI inspection;
NEVER commit it. Preserve all real MMIO/VP hard fences, no fake guest
display calls, no made-up function bodies or return widths.


## K1 D52D4: source-proven Xbox controller capabilities (2026-10-31)

Read-only source audit PASS: the latest hardware target 0x002D52D4
is retail XInputGetCapabilities, not a mystery graphics routine.
Exact source in the user-local recomp_0013.c has SHA256:
80aa0150e3d680d11925e2b2c3465509930b557fc511f625bafbbdea39e09ed5.
Its original guest wrapper reads two stack args (handle and output pointer),
sets EAX to the helper status, then executes esp += 12u; return
(i.e. two arguments and 8 bytes of guest argument cleanup).

The previous pixel TrueTU set did not include D52D4, though
its three disassembler-reported children were present. The actual
translated helper wrapper does not call those three static callees.
Existing original public host code in ports/mercenaries/src/recomp_manual.c
shows XInputGetCapabilities must use handle=port+1 and clear a 28-byte
original-Xbox capabilities buffer, writing Type/SubType/Flags only.
Xbox 360's native XINPUT_CAPABILITIES has a different layout and must
not be copied directly to guest memory.

Stage-XppD52D4.py is a guarded incremental source stage preserving
the prior D5272/D559B/D5579/K1S inputs and unknown VP/MMIO hard fences.
It queries real native XInputGetCapabilities and serializes 28 original-
Xbox guest bytes through existing GUEST_WRITE32, preserving EAX and ret8.
It rejects unrecognized retail source SHA, changed parent input hashes,
missing exact direct callsites, duplicate guest body, or changed ABI.

FIRST: no XDK, no deployment; from Merc360 repo root:

    git pull --ff-only
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-XppD52D4.ps1" -PreflightOnly

After clean preflight PASS, run the same command without -PreflightOnly
for an incremental VS2017 Xbox 360 build (SkipClean=true).
Published diagnostic XEX only after successful build:
build\phase6_integration_map\xpp_d52d4_batch\xdk\Merc-XPP-D52D4.xex

Xbox proof: XPP D52D4 ENTRY, XPP XINPUT capabilities return/status,
and next original guest frontier; real display_calls and framebuffer
must still be measured, never faked. No D52D4 Xbox PASS yet.
Original guest files and local-only excerpts stay private.


## D54AC: real Xbox 360 controller state, original 22-byte layout (2026-10-31)

Hardware XEX D52D4 successfully executed retail XInputGetCapabilities with
handle=1 port=0 status=00000000 and returned to a new clean direct
frontier at 002D54AC, tick=27,107,620, fault=0. display_calls=0.

Read-only original-source audit identifies 0x002D54AC (XPP, 115
XBE bytes, generated in private recomp_0013.c, SHA256
48e4ccc7ccc0ae3bfa852d584996f6f1ed034d0491f05433722054038f42a0e2)
and the sole observed host helper name recomp_xinput_get_state.
The original generated ABI must pass exact local SHA, two stack argument
reads, EAX return and original ret8 before the stage can build.

The public original Mercenaries recomp_manual.c documents 22-byte
XBOX_INPUT_STATE guest writes, NOT 24-byte sizeof(native struct).
The public Xbox compat input backend maps DPad/Start/Back/sticks as
digital low byte and Xbox360 A/B/X/Y/RB/LB/left/right triggers into
8 original Xbox analog button bytes; four signed stick axes follow.
Stage-XppD54AC.py uses real Xbox360 XInputGetState, returning native
status, and serializes exactly five DWORDs and one WORD to the guest
buffer (22 bytes; no 2-byte padding corruption), preserving original
packet number. Do not memcpy native XINPUT_STATE into original Xbox
guest buffer. It never fabricates controller buttons or display calls.

New preflight-first runner:

    cd "C:\Users\jorda\Mercenaries-Recompiled-Xbox360"
    git pull --ff-only
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-XppD54AC.ps1" -PreflightOnly

Preflight stages from the proven xpp_d52d4_batch in an independent
xpp_d54ac_batch directory. It checks parent hashes, inherited 64-TU
stage, original retail generated SHA and EAX/stack contract, exact
direct-fence patch, unique native helper, 22-byte guest write and all
existing unknown MMIO/VP hard fences. No XDK build/deploy until local
preflight PASS. Local-only original source excerpts must stay private.

Once preflight PASSES, the same command WITHOUT -PreflightOnly performs
one incremental Xbox360 VS2017 build with SkipClean true:
build\phase6_integration_map\xpp_d54ac_batch\xdk\Merc-XPP-D54AC.xex
Xbox hardware proof will require XPP D54AC ENTRY, genuine
XPP XINPUT state status, next direct frontier and real display_calls
/ framebuffer fields; no fake presentation.


## Predictive multi-recompiler XPP batch, not one Xbox build per API (2026-10-31)

After the successful D52D4 hardware test (XInputGetCapabilities status=0,
next XPP DIRECT 002D54AC at 27,107,620 translated ticks; fault=0),
the original C/source audit proved D54AC is retail XInputGetState (115
original bytes), exact SHA256
48e4ccc7ccc0ae3bfa852d584996f6f1ed034d0491f05433722054038f42a0e2.
Native D54AC exact 22-byte controller state bridge preflight now PASS:
all 64 inherited TrueTUs, changed TUs translated_027.cpp and
translated_033.cpp; NO XDK build or Xbox test yet for D54AC.

**Do not continue blindly one XDK build for each XPP wrapper.**
The existing upstream public Mercenaries compatibility layer lists
eight original XPP native input helpers. Six are already supported by
the staged native controller chain; remaining Close and SetState require
the user's exact original guest source and guest feedback memory ABI
before attempting native packaging. The xboxrecomp static inventory
(16,662 original functions) supplies original direct caller evidence.
TGP482/XboxXBERecomp symbols provide independent names where assigned.
Neither static source provides execution proof.

New source-only predictive scan (NO VS2017, NO XDK, NO Xbox):

    cd "C:\Users\jorda\Mercenaries-Recompiled-Xbox360"
    git pull --ff-only
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Run-K1XppPredictiveBatch.ps1"

The runner reruns known-good D54AC preflight for hashes, then maps
original-generated XPP function bodies to the known input-helper family
and original xboxrecomp caller graph, plus optional TGP482 symbol
assignments. It reports source SHA, helper identity, exact guest stack
cleanup hints, static caller count, already-compiled callers and
live direct-frontier replacement opportunities. Unknown helper, ABI
or VP/MMIO semantics remain HARD FENCED.

Share metadata-only:
build\phase6_integration_map\xpp_predictive_batch\xpp_input_candidate_report.txt
and optionally the JSON manifest in the same folder.

Next batch strategy: source/ABI-validate every reachable safe candidate,
then stage several in one incremental TrueTU XEX, retaining
previous hardware witness and renderer/presentation counters.
Do not use static callgraph position as a replacement for real runtime
execution. No private XBE, original C translations or guest bytes should
enter GitHub.
