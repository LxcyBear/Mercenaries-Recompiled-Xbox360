# Mercenaries 360 K1 TEXT direct frontier — authentic source batch

## Hardware witness (2026-11-03)

The real three-lane XEX crossed the hardware-proven DAC-index/PFIFO
frontier and processed all 256 original grayscale palette entries (768
guest DAC byte writes). PFIFO CACHE1_DMA_PUT readback at original
0028ED6B succeeded. The next exact boundary was:

    DIRECT FRONTIER: caller=0023A3CE target=0017A0A0 esp=008BFA0C
    P6DQ ROCKET HARD STOP kind=13 target=0017A0A0 ticks=58539999
    BOUNDARY: kind=DIRECT_FRONTIER ... fault=0

Prior hardware was stopped at 56,902,781 ticks; this is +1,637,218.
No guest Swap or PersistDisplay executed, display_calls=0, framebuffer=0.
The native blue output is NOT game pixels.

## Next change: original translated TEXT, no dummy success

This stage does NOT synthesize a return for 0017A0A0 and does not
skip file parsing. It uses the original user-local xboxrecomp source
corpus and the original XBE-hashed functions inventory to require
0017A0A0 be a bounded exact function start. An absent original body,
mid-function address, duplicate compiled implementation, or unsupported
function dependency stops the source-only preflight.

A bounded breadth-first source closure (max 32 new members, depth 2)
is rendered with the repo's real Phase5BC support-clean pack machinery.
Any unsafe side members are pruned; unknown direct dependencies become
the inherited normal DIRECT_FRONTIER hard stop. The exact original
root is mandatory. A source-authentic root and an exact lookup
case must both survive; no dummy x86 calls or fabricated return values.

Phase 6DQ R51's genuine 64 TrueTUs are reused unchanged. The new
translated bodies are placed in a dedicated optimize-off region inside
a derived main.cpp, and the lookup for 0017A0A0 is installed there.
The original three-lane parent is not overwritten. Parent DAC palette,
PFIFO, K1PERF, Swap-route watch and unknown MMIO fences remain intact.

The real retail XBE/original generated C source remains LOCAL;
no original source body or game assets are committed.

## Run (source-only default)

From the existing Mercenaries repository:

    git pull --ff-only

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1TextDirectBatch.ps1"

This invokes the old three-lane source preflight and runs the new
original-XBE provenance, Python regression, 64-shard inventory,
bounded source promotion, hash/manifests and safety gates.
It does not rebuild or invoke XDK unless -Build is passed.

## One incremental Xbox 360 build (after preflight passes)

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1TextDirectBatch.ps1" -Build

Build output only on successful XDK compilation:

    build\phase6_integration_map\k1_text_direct_batch\xdk\Merc-K1Text-Direct0017A0A0.xex

Next hardware run must prove the original direct path actually
executes, then record the next exact fault and any real guest
display_calls. Source-stage PASS is NOT hardware PASS.

## Readable xbWatson view

Do NOT hide hardware faults, errors, nonzero status codes or
GPU/presentation instrumentation in the runtime. To produce a
shorter separate view of an existing log while retaining the original:

    python ".\ports\mercenaries\xbox360\integration_map\k1\Compact-K1Watson.py" "C:\path\to\watson.log" --brief

That tool groups routine PASS and R-series revision probes into
counts and keeps exact GPU, timing, fatal and guest presentation
markers. The raw Watson file remains the authoritative debug record.
A compacted log has NOT sped up original guest translated ticks.

Hardware measured a large 160,170-ms interval for ticks
24,000,000–28,000,000, alongside much faster periods. That suggests
a separate startup performance hotspot (possibly initialization
work or waiting); it is not evidence that a source-only log
formatter accelerates the Xbox.

## Exact PC checkpoint dependency resolved (2026-11-03)

The real source preflight identified a single missing helper at original
0017A0A0 in recomp_0007.c: recomp_main_state_checkpoint takes the
two guest stack arguments, followed by the genuine GUEST_WRITE32
to address 0x413F6C. The original translated call and guest write
remain intact in the new stage.

The maintained PC implementation is in
ports/mercenaries/src/recomp_manual.c, with its ABI declaration in
ports/mercenaries/src/recomp/recomp_types.h. It performs
environment-driven PC gameplay/shell-play capture, optional host
frontend test automation, and state-transition tracing. It does not
write guest registers or guest RAM. These PC capture modes do not
run on the Xbox 360 port.

The derived Xbox main.cpp now supplies the same two-argument void
helper as bounded K1STATE MAIN CHECKPOINT telemetry. It logs first
entry, state changes and every 1,024th repetition; it never alters
guest RAM, registers, return values, framebuffer or control flow.
Both the maintained PC helper body and the exact original retail
callsite/guest-write sequence are checked before source promotion.
The mandatory root remains fail-closed for any OTHER unresolved helper.

Phase5BC's obsolete synthetic sweep-entry global assignment is
not injected into the original root. Original 64 TrueTUs and prior
graphics/PFIFO/DAC/presentation hard fences remain unchanged.

Automated GitHub source-regression validation passed for commit
0bdd7c1050655eb7738610d52b206cdcf5cb94ec. The real source
stage, XDK compilation and Xbox hardware still require verification
on the user's Windows machine.
