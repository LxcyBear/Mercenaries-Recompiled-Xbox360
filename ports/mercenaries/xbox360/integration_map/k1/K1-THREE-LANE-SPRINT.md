# Merc360 K1: Three-Lane Graphics and Speed Sprint (2026-11-03)

## Confirmed hardware basis

The DAC + quiet logger XEX successfully handled the old 8-bit DAC index
write FD6813C8 at original XBE instruction 0028ED54, and then reached
READ32 FD003240 at instruction 0028ED6B, tick 56,902,781. The previous
hardware stop was tick 56,902,779. Guest display_calls and framebuffer
remain zero. The quiet logger suppressed 4,286 duplicate successful
log lines. Phase 6DQ HOT PROFILE shows 24,862,470 / 56,902,781 ticks
(43.7%) attributed to the 001E hot region.

## Lane A: exact NV2A PFIFO state

FD003240 is NV_PFIFO_CACHE1_DMA_PUT (PFIFO offset 0x1240), documented
in xqemu's hw/xbox/nv2a/nv2a_regs.h. The experimental new main owns a
PUT register shadow initialized to zero, consistent with xqemu's
zero-initialized PFIFO state but NOT directly measured original-Xbox
hardware reset behavior. The first read is accepted only at known
retail block 0028ED6B. Subsequent reads require observed guest writes
to that register; writes are bounded to real D3D guest callers, valid
DMA_PUT offsets and aligned dwords.

Nothing is sent to Xenos; no colors or pixels are fabricated.
All other MMIO accesses retain their inherited hard-stop behavior.
The next Xbox run must verify what the game actually does with this
modeled value, not simply claim that passing the fault proves fidelity.

## Lane B: get actual time measurements

The new main adds GetTickCount timing ONLY when the existing
rare P6DQ SPIN SAMPLE or ROCKET HARD STOP messages pass through
the quiet trace writer. K1PERF WINDOW and K1PERF LAST_TO_FAULT report
millisecond intervals and translated ticks/second. They do not
skip, coalesce, speed up or alter any translated guest instruction.

The independent offline auditor locates source blocks 001EF4CD,
001EF64E, 001EEFF1 and 001EEFE0 to prepare safe hot-path analysis.
Performance optimization is not implemented or proven yet.

## Lane C: display-path inventory + targeted probes

The offline auditor lists actual translated source definitions and
direct C++ callsites for D3DDevice_Swap (0028BDB0),
D3DDevice_PersistDisplay (0028A530), and
Direct3D_CreateDevice (0028CAA0). Runtime K1PRESENT FRONTIER ROUTE
captures only a selected target in the existing packed dispatch
frontier. Compiled direct calls are not caught there; a route is
not a Swap, not a frame, and not a real display_calls increment.

## Commands (PowerShell 5.1)

From C:\Users\jorda\Mercenaries-Recompiled-Xbox360:

    git pull --ff-only

Standalone three-lane source audit, no Xbox/XDK:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Run-K1ThreeLanePreflight.ps1"

You may supply -HardwareLog "C:\path\to\completed-watson-log.txt".
The read-only JSON report is written to
build\phase6_integration_map\k1_three_lane_report\three_lane.json.

Stage a separate three-lane main from the hardware-tested DAC/quiet
parent with guarded checks; by default no XDK:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1ThreeLaneGraphics.ps1"

Add -Build to the same command for ONE incremental VS2017 Xbox 360
Release XEX from the derived main. Final target:

    build\phase6_integration_map\k1_three_lane\xdk\Merc-K1-ThreeLane-PFIFO-PERF-PRESENT.xex

The verified quiet parent and 64 translated TrueTUs are NOT modified.
Any missing XBE source proof, duplicate patch, missing global C++ trace
symbol, or source hash drift stops before the build.

## Success conditions

1. A real K1PFIFO DMA_PUT READ32 event with original caller VA.
2. Actual native K1PERF wallclock windows, not claims of speedups.
3. Source-grounded Swap/Persist definitions and eventual real guest
   Swap execution (NOT just an inferred dispatch route).
4. Original hard-stop and full fault evidence remains visible.

No synthetic framebuffer, forced Swap, skipped startup loops, or
unknown MMIO blanket exemptions.


## Source-audit false-positive fixed (2026-11-03)

The initial three-lane preflight halted before XDK with a duplicate translated display function definition error. The old scanner counted forward declarations together with genuine function bodies; multiple TrueTUs can legitimately reference the same function. The error is from audit classification, NOT an Xbox GPU fault.

The revised audit counts declarations separately from real function definitions (signatures followed by a brace). Its 64-shard synthetic regression covers repeated forward declarations and a deliberate duplicate real body. Multiple real implementation or PFIFO block witnesses are reported with their file/line locations in JSON diagnostics; the audit no longer erases these facts or treats them as evidence of execution. The stage now checks the real DAC guest-VA function call instead of a fragile prototype spelling.

No guest code, MMIO fences or original-XBE proof gates changed. Re-run source preflight before the optional -Build XDK operation. Actual 64 TrueTU/XDK success remains to be verified on the user's Windows PC.
