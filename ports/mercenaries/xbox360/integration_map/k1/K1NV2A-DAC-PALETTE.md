# K1NV2A — original retail D3D VGA DAC palette startup

## Exact retail-source proof

The Xbox hardware witness reported `WRITE8 FD6813C8`, value `00`, last translated block `0028ED48`, tick 56,902,779. The user-supplied verified original XBE disassembly now resolves the exact faulting x86 instruction:

```asm
0028ED54  mov byte ptr [ecx + 0x6813c8], 0
0028ED77  mov byte ptr [ecx + 0x6813c9], dl
0028ED7F  mov byte ptr [ecx + 0x6813c9], dl
0028ED8C  mov byte ptr [ecx + 0x6813c9], dl
```

At the fault ECX was `FD000000`. The generated TrueTU also matches: `translated_055.cpp:21659` calls `GUEST_WRITE8(ecx + 0x6813C8, 0);`. The code loops through a planar RGB palette sequence. xqemu maps NV2A `+0x681000` as `PRMDIO`, the VGA palette-register alias. Standard VGA port `0x3C8` selects the palette write index; `0x3C9` receives sequential red, green and blue bytes, incrementing the index every three.

References: https://github.com/xqemu/xqemu/blob/master/hw/xbox/nv2a/nv2a.c ; https://github.com/xqemu/xqemu/blob/master/hw/xbox/nv2a/nv2a_regs.h ; https://wiki.osdev.org/VGA_Hardware

## Exact guarded implementation

`Stage-K1NV2ADacPalette.py` creates a **new main.cpp** from the proven K1NV2A witness source. It intercepts only 8-bit writes to `FD6813C8` and, *after an index write*, `FD6813C9`. It stages actual RGB bytes and commits the complete triplet atomically into a 256x3-byte volatile shadow palette; after three bytes it advances/wraps the 8-bit write index. No fake palette values are supplied. Raw 8-bit guest values are preserved without guessing the Xbox DAC output depth.

All other NV2A reads/writes, including 16/32-bit versions of these addresses, retain the original hard fence. An unarmed `FD6813C9` write also retains the hard fence. The implementation does **not** translate a DAC palette into native Xenos colors or inject guest presentation.

Offline tests check the 256-entry/768-byte RGB sequence, 255-to-zero wrap, aborted partial triplets, unsupported-register rejection, source ancestry, and exact reversible main-only patch. Those tests are source-side until validated on the user's PC.

**Next likely frontier:** after the first DAC index write, the original x86 instruction at `0028ED6B` reads `[ecx + 0x3240]` when the loop offset is 8-byte aligned. With ECX=`FD000000`, this means `READ32 FD003240`, which xqemu identifies as PFIFO block `+0x1240` (`NV_PFIFO_CACHE1_DMA_PUT`). This is a *prediction*, not yet a hardware observation; its register value must not be faked or guessed. The original hard-read fence will identify the actual next boundary.

## Source preflight and one build

From the Mercenaries repository root on Windows:

```powershell
git pull --ff-only
powershell.exe -NoProfile -ExecutionPolicy Bypass -File './ports/mercenaries/xbox360/integration_map/k1/Advance-K1NV2ADacPalette.ps1'
```

Requires the previous K1NV2A witness `main.cpp` and its verified manifest, the existing 64 native K1NT207 TrueTUs, and the generated `focused-0028ED48.txt` report containing original source AND original XBE disassembly. Preflight does not build or deploy to Xbox.

After preflight passes:

```powershell
powershell.exe -NoProfile -ExecutionPolicy Bypass -File './ports/mercenaries/xbox360/integration_map/k1/Advance-K1NV2ADacPalette.ps1' -Build
```

The same runner now performs **K1DQ central logging quiet-mode staging**
after the DAC source preflight. It builds only ONE XEX from the
quiet-wrapper-derived main.cpp, not two separate builds. The derived
source lives in `build/phase6_integration_map/k1_nv2a_dac_palette_quiet`
and the 64 previous TrueTUs and runtime header are reused unchanged.

Output: `build/phase6_integration_map/k1_nv2a_dac_palette_quiet/xdk/Merc-K1NV2A-DAC-Palette-Quiet.xex`.

### Phase 6DQ quiet mode: narrowly scoped trace output

The prior 9,499-line xbWatson log contained 4,588 repeated
`KfLowerIrql`, `KfRaiseIrql`, `RtlEnterCriticalSection` and
`RtlLeaveCriticalSection` success+live-frame message pairs.
Those four **trace message families** are the only coalescing targets.

`Stage-K1DQQuietLogging.py` renames the existing `trace` sink to an
unfiltered emitter and installs a wrapper. It buffers an operation's
`LIVE FRAME` record until the next message: only a matching,
expected PASS causes coalescing. The first complete pair always
logs. Afterward pairs increment counters without printing;
an aggregate for that family logs every 256 successes. Unexpected
IRQL status, any nonmatching or failed next message, and all
unrelated messages flush the pending frame and log normally. On
D3D-init / rocket-hard-stop / shutdown milestones it also emits a
concise aggregate alongside the original milestone log.

**Protected by design:** underlying guest/kernel calls are never
skipped; register values, ABI, MMIO fences, framebuffers and all
translated TrueTUs are unchanged. The original trace output
mechanisms (`OutputDebugStringA`, file writes and flushes) are
preserved inside the unfiltered emitter. The wrapper does not
suppress actual NV2A witnesses, directory results, controller
messages, failures, or Swap/Present logging.

The reduction in log traffic may improve run time because the old
logger writes and flushes each message, but hardware wall-time
speedup is **not yet measured**. Compare two comparable console
runs before making performance claims. The quiet source is still
unverified on hardware until the user builds and deploys the new
XEX.

Live Xbox criteria: startup tag `P6K1NV2A-DAC-PALETTE-20261103`, DAC write-index event, RGB commit summaries if reached, and the actual next memory boundary. `display_calls=0` and `framebuffer=00000000` remain the latest measured values: purple by itself is not proof of guest rendering.

## 2026-11-03 one-symbol Xbox link failure and guarded repair

The first DAC + quiet XDK build reached the **linker**, then failed with
63 `LNK2001` lines plus one `LNK2019` for precisely one C++ import,
`?trace@@YAXPBD@Z` (`void __cdecl trace(char const*)`). All 64
existing translated TrueTUs expected global external C++ linkage, but
the quiet output wrapper was declared `static void trace(...)`. The
compiler accepted `main.cpp` but could not export that symbol to
the other translation units. This is *not* an NV2A/ABI game fault,
and it is not evidence of 64 different bugs.

The corrected stage emits **`void trace(const char* line)`** (global
C++ symbol) while preserving the underlying output sink unchanged.
An updated preflight checks exactly one global `trace` definition
and zero static ones **before launching the XDK**. This prevents
the same 64-object linker failure from recurring silently.

Because the old source and manifest were already staged, the new
Python stager includes a **narrow guarded restage**: it will replace
the previous quiet `main.cpp` ONLY when the previous bytes match
the exact static-wrapper variant of the new source AND the previous
manifest's SHA-256/source/safety fields agree. The source remains
isolated from the DAC parent and all 64 TrueTUs. Arbitrary drift,
unknown output, and unsafe modifications still fail closed.
This cannot certify the XDK itself until the user builds again.

A host compiler two-translation-unit test confirmed an external
`trace(char const*)` resolves with the global definition. The
`--self-test` now also exercises guarded conversion of the old
static-wrapper source to the new global wrapper, idempotence, and
rejection of tampered generated files.

## Real Xbox 360 hardware witness — 2026-11-03: DAC index crossed

The first combined K1NV2A DAC + K1DQ quiet-mode XEX ran to its inherited
hard-stop reporting and clean process shutdown. The boot banner confirmed
`P6K1NV2A-DAC-PALETTE-20261103` and
`P6K1DQ-QUIET-LOG-20261103`.

The **previous** first hard-stop `WRITE8 FD6813C8 value=00` at
56,902,779 ticks was eliminated. Hardware recorded:

```text
K1NV2A EXACT WRITE8: addr=FD6813C8 value=00 last_guest_block_va=0028ED48 ...
K1NV2A DAC WRITE INDEX: index=0 count=1 guest_block=0028ED48
FAULT ACCESS IMMEDIATE: READ width=4 guest=FD003240
P6DQ ROCKET HARD STOP kind=6 caller=0023A3CE target=FD003240 ... ticks=56902781
P6DQ VA[29]=0028ED48
P6DQ VA[30]=0028ED63
P6DQ VA[31]=0028ED6B
```

This exactly follows the **original retail XBE** sequence:
`0028ED54` writes VGA DAC index, then `0028ED6B` reads
`[ecx+0x3240]` with `ecx=FD000000`. The new fault is
**NV_PFIFO_CACHE1_DMA_PUT**, NVIDIA PFIFO register offset 0x1240
from PFIFO base `FD002000`, confirmed by
[xqemu's NV2A register definitions](https://github.com/xqemu/xqemu/blob/master/hw/xbox/nv2a/nv2a_regs.h).

Crucially, **no 0xFD6813C9 DAC RGB-component writes were reached**:
the earlier expected PFIFO access occurs first. Do not invent
completed palette entries or claim pixels. The final telemetry
remains `display_calls=0`, `framebuffer=00000000`, and no verified
guest Swap or PersistDisplay. This is a +2 tick step with an exact
retail-source proof, NOT a meaningful execution-time speedup.

The quiet logger emitted normal first-success pairs, 256-pair summaries,
and hard-stop summaries while removing **4,286 repetitive success log
lines** (about 45% of the estimated unfiltered 9,509 lines). A final
summary showed `lower=493 raise=628 enter=513 leave=513`,
with `muted_lines=4286`. The quiet logger preserves unusual IRQL
transitions and errors, so some KfLowerIrql calls remain visible.

Separately, `P6DQ HOT PROFILE: total=56902781 hot_001E=24862470`
means 43.69% of translated ticks were attributed to the 001E hot
region. Suppressing Watson log lines cannot accelerate that much
translated execution on its own. Do not claim a speedup without
comparable hardware wall-clock measurements.

**Next graphics gate:** implement and test the documented PFIFO
`CACHE1_DMA_PUT` register in the existing **stateful PFIFO model**
with a proven initialization/reset basis and guest-write tracking.
The original source `0028ED6B` and real Xbox `READ32 FD003240`
must anchor the patch. Only this exact register/read width should be
newly handled; preserve every unknown NV2A hard fence, retain the
64 TrueTUs, and do not unconditionally fabricate a read value.
