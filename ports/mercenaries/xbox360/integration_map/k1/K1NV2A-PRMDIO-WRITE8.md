# K1NV2A: exact 8-bit PRMDIO write fault — one-build witness

## Proven Xbox hardware boundary (2026-11-03)

The genuine Xbox 360 run of `Merc-K1NT207-RealDirectory.xex` with native
directory enumeration reached all four real class-1 directory results, native
XInputGetState and XInputSetState, then stopped with the ORIGINAL hard fence:

```text
FAULT ACCESS IMMEDIATE: WRITE width=1 guest=FD6813C8
P6DQ D3D FAULT PROBE: step=10 a=00000000 b=00299380 c=00000000
P6DQ ROCKET HARD STOP kind=6 caller=0023A3CE target=FD6813C8 esp=008BF3E8 ticks=56902779
P6DQ ROCKET HARD REGS eax=00000001 ecx=FD000000 edx=0029B484 ebx=0029B484 esi=FFFFFF00 edi=0029B784
P6DQ PIXEL CHASE ... display_calls=0 framebuffer=00000000
```

The `caller=0023A3CE` from the trace ring is **not** the exact translated
instruction PC. `EAX=00000001` is also **not** proof that the byte argument
to the write was 01.

## Verified real hardware witness after the first diagnostic XEX (2026-11-03)

The new first-fault instrumentation **executed on real Xbox 360 hardware**:

```text
K1NV2A EXACT WRITE8: addr=FD6813C8 value=00 last_guest_block_va=0028ED48 esp=008BF3E8 eax=00000001 ecx=FD000000 edx=0029B484 ebx=0029B484 esi=FFFFFF00 edi=0029B784
FAULT ACCESS IMMEDIATE: WRITE width=1 guest=FD6813C8
P6DQ ROCKET HARD STOP ... ticks=56902779
P6DQ PIXEL CHASE: ... display_calls=0 framebuffer=00000000
```

**PROVED:** the passed `recomp_guest_write8` byte is `00`.
The most recently tracked translated basic block is `0028ED48`,
within the retail `D3D` XBE section (VA `00288640`,
offset `+6708`; section raw starts `0027A000` giving raw file
offset `00280708`). `ECX=FD000000` corroborates the original
Xbox NV2A MMIO base. This is **not** proof of the individual x86
store instruction or of successful guest presentation.

The original XBE map is confirmed in the live log. The user again
observed purple, but hardware counters still show no guest
`Swap` or framebuffer.

### Targeted PC-only source/disassembly replay, no Xbox run

Pull the branch after the XDK build completes. From repo root:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "Git pull failed" }
$script = ".\ports\mercenaries\xbox360\integration_map\k1\Audit-K1NV2ASource.py"
$shards = ".\build\phase6_integration_map\k1_ntquerydirectory207_native\translated_shards"
$xbe = ".\game_files\mercenaries-retail\default.xbe"
$argsAudit = @("--shards", $shards, "--focus-va", "0x0028ED48",
               "--out", ".\build\phase6_integration_map\k1_nv2a_prmdio_write8\focused-0028ED48.txt",
               "--max", "8")
if (Test-Path -LiteralPath $xbe -PathType Leaf) { $argsAudit += @("--xbe", $xbe) }
python $script @argsAudit
if ($LASTEXITCODE -ne 0) { throw "Focused source audit failed" }
```

The updated auditor always prints the **actual translated block
around `PHASE4C_BUDGET_TICK(0x0028ED48u)`**, whether or not the
general call-site heuristic finds a corresponding WRITE8. When the
exact verified XBE is accessible, it also prints the 32-bit original
x86 instructions starting at `0028ED48` (Capstone required for
instruction decoding). If there is no matching marker, report that
honestly: the tracker might be stale or the source set different.
The output is local source excerpts and metadata, not game files.

## GPU register identification

This address is in the original Xbox NV2A MMIO BAR at
`FD000000 + 006813C8`. xqemu's NV2A block table maps
`00681000..00681FFF` to **PRMDIO**, making the block-local
offset `+03C8`. This matches the classic VGA DAC write-index port
`0x3C8`, but xqemu's `nv2a_stubs.c` currently treats PRMDIO as a
**stub**. Do not invent PRMDIO palette semantics or permit this
unknown MMIO write based solely on the port-number coincidence.
Whether the transient purple screen was guest-rendered remains
unproven. No real guest Swap/Present or framebuffer is yet observed.

Upstream code sources:
- https://github.com/xqemu/xqemu/blob/master/hw/xbox/nv2a/nv2a.c
- https://github.com/xqemu/xqemu/blob/master/hw/xbox/nv2a/nv2a_stubs.c
- https://github.com/sp00nznet/xboxrecomp/blob/main/docs/DECOMP.md

## Already staged: no XDK, only source/ABI audit

From the Mercenaries repo root:

```powershell
git pull --ff-only
if ($LASTEXITCODE -ne 0) { throw "git pull failed" }
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1NV2APrmdioWrite8.ps1"
```

This runs Python syntax + synthetic stage tests, checks the last native
K1NT207 main/header hashes and real XEX existence, stages a NEW copy
of only `main.cpp`, and ranks the original Xbox WRITE8 candidate
sites in all 64 xboxrecomp-generated TrueTUs. If a matching SHA-256
retail `game_files\mercenaries-retail\default.xbe` is available,
the optional Capstone path also disassembles the first eight candidate
guest blocks (requires Capstone in the selected Python environment).

Read the grounded source report:
`build\phase6_integration_map\k1_nv2a_prmdio_write8\k1nv2a-source-candidates.txt`.
A static `block=...` is a **candidate basic-block VA**, not a
guaranteed byte-store instruction address, especially when the
destination is computed dynamically.

For full original disassembly using xboxrecomp's maintained XBE
parser/disassembler, you can operate on your local legitimate XBE
with `python -m tools.xbe_parser <XBE> --json <analysis.json>` and
`python -m tools.disasm <XBE>` from the xboxrecomp project, or
use its `tools.recomp <XBE> --func <actual-function-VA>` once
the candidate function is identified. Do not rerun the whole-game
recompiler for this one fault; use the cached disassembly where
possible. Never commit the retail XBE or generated game code.

## One incremental, protected native Xbox 360 build

If the above preflight passes, add `-Build`:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1NV2APrmdioWrite8.ps1" -Build
```

The native builder uses the verified **same 64 TrueTUs** and
`translated_runtime.h`, `SkipClean`, and persistent shadow
intermediates. It publishes a **different XEX**:

`build\phase6_integration_map\k1_nv2a_prmdio_write8\xdk\Merc-K1NV2A-PRMDIO-Write8-Witness.xex`

This avoids a 64-shard recompile for a header-only trace. It does
NOT auto-deploy.

When testing that exact executable on the real Xbox, collect the
following two messages together:

```text
P6K1NV2A-PRMDIO-WRITE8-20261103
K1NV2A EXACT WRITE8: addr=FD6813C8 value=?? last_guest_block_va=???????? ...
FAULT ACCESS IMMEDIATE: WRITE width=1 guest=FD6813C8
```

After the hardware log gives a concrete last guest block, rerun the
existing read-only auditor without building or changing a shard:

```powershell
$k1 = ".\ports\mercenaries\xbox360\integration_map\k1"
$shards = ".\build\phase6_integration_map\k1_ntquerydirectory207_native\translated_shards"
$xbe = ".\game_files\mercenaries-retail\default.xbe"
python "$k1\Audit-K1NV2ASource.py" --shards $shards --xbe $xbe --focus-va 0xYOUR_GUEST_BLOCK_VA --max 8
```

Replace `0xYOUR_GUEST_BLOCK_VA` with the observed 8-digit hex.
The auditor ranks exact generated-block matches first and decodes the
user's original XBE bytes locally if the verified XBE is available.
Those matches still require source-level proof of the individual
byte-store instruction.

The added conditional executes at the **entry** of the central
`recomp_guest_write8` and logs the **actual uint8_t argument**
plus register/ESP context *before* the original fault path executes.
It never acknowledges, retries, redirects, clears, or performs the
forbidden NV2A write. The provenance helper is the existing K1C
last-guest-block tracker; use the static audit to find the exact
translated instruction inside that block. If the block has more than
one possible byte store, a future callsite-specific witness is required.

**Success criteria:** the unique boot tag, one actual-value record,
followed by the **unchanged** hard stop, and a source-disassembly
correlation to a plausible original Xbox byte-store instruction.
Only then decide whether the PRMDIO operation can be safely
implemented. Do not claim actual pixels from a purple screen alone.

## PC-only, read-only log triage and future logging-speed work

A read-only audit of the 2026-11-03 9,509-line xbWatson capture found
**4,588 repeated successful IRQL/critical-section trace lines**
(~48.2% of that capture). These are only text-output counts, not a
wall-clock profiler or proof that suppressed logging would speed the
translated CPU by the same percentage. Any future quiet-mode patch
must retain first occurrences, real failures, unique startup markers,
K1NT207 results, exact NV2A write values, and Swap/framebuffer counters.
Do not reduce the IRQ/critical-section *operations*, only redundant
success messages after hardware-validating a rate limit.

After the current XDK build finishes, pull the branch and run this
standalone diagnostic on a saved xbWatson text log:

```powershell
$k1 = ".\\ports\\mercenaries\\xbox360\\integration_map\\k1"
python "$k1\\Summarize-K1NV2AWatson.py" --self-test
$log = Read-Host "Full path to saved xbWatson .txt log"
python "$k1\\Summarize-K1NV2AWatson.py" --log $log --out ".\\build\\phase6_integration_map\\k1_nv2a_prmdio_write8\\offline-watson-summary.txt"
```

This does no Xbox work, no game-file reads, and no source mutation.
For a broader source study, run the existing
`Audit-K1NV2ASource.py` with the 64 generated TrueTUs and optional
verified retail XBE. Avoid running the larger source scan in parallel
with an XDK build on memory-limited PCs: it may compete with the C++
compiler and slow the current build.
