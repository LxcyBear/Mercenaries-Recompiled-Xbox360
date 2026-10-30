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
