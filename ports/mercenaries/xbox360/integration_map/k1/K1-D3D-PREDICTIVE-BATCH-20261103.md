# K1D3D predictive graphics frontier batch — one source audit, not one build per VA

## New hardware proof, 2026-11-03

On Xbox 360, the K1D3D Direct289E20-r2 XEX:
- retained native Xenos CreateDevice + second-device Reset with native
  Reset HRESULT=00000000;
- finished the second guest CreateDevice handoff, guest_device=00299380,
  out=007AD604, calls=2;
- passed the earlier direct frontier 0x00289E20 without another hard stop;
- stopped on P6DQ ROCKET HARD STOP kind=3 caller=0023A3CE
  target=0029655D esp=008BF544 ticks=58540888, summarized as
  BOUNDARY kind=ITAIL fault=0;
- did not present game pixels: display_calls=0, framebuffer=00000000.

This is an INDIRECT TAIL control-flow boundary, not an ordinary direct
function call. The log's nearby D3D VA history includes 0x00296550 and
0x002965F0. Those may be execution labels inside a containing
function, not independent function starts. Simply promoting 0x0029655D
as a new C function or routing the ITAIL to the containing function's
ordinary entry would execute the wrong guest instructions.

## Replace one-XEX-per-frontier with a source-authentic batch

Use the already-available local original retail XBE disassembly and
xboxrecomp-generated C, not the Xbox hardware as a hot-loop profiler.

1. Classify observed ITAIL target against the local
   build/phase3n_final_abi_scale/analysis/disasm/functions.json.
   Identify containing function or exact entry, original source file,
   and matching loc_0029655D label (if present).
2. Gather source/label context around the target, inspect original
   translated tail-call macros near the logged caller and D3D
   neighborhood, and inventory already packed functions in the
   parent main plus the 64 TrueTUs.
3. Use verified graphics-function starts and original direct-call edges
   to build a bounded, de-duplicated batch candidate graph (cap 96,
   depth 4), seeded by actual hardware D3D context, the known original
   D3DDevice_Swap target and D3DDevice_PersistDisplay target.
4. Preserve one source report with all function/source hashes. The
   candidate set is NOT an assertion that all functions are
   support-clean; the next integration stage must run the real Phase5BC
   dependency-pruning analysis before any XDK build.
5. Add a real ABI-proven ITAIL dispatcher only after confirming
   whether the observed target is an exact original entry or an
   interior label. Interior labels demand exact entrypoint selection
   and guest stack/register control flow, not a fabricated return.
6. Compile and test one cohesive graphics batch, not a succession
   of one-function XEXs. Repeat only when new hardware evidence
   changes the class of boundary.

No guessed code, fake frame, synthetic S_OK, blanket support whitelist,
unknown MMIO continuation, or weakening of existing guest fault fences.

## One quick source audit (NO XDK, NO Xbox)

    cd "C:\Users\jorda\Mercenaries-Recompiled-Xbox360"
    git pull --ff-only
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Plan-K1D3DBatch.ps1"

Report:

    build\phase6_integration_map\k1_d3d_predictive_batch\k1-d3d-itail-predictive-source-plan.json

The audit captures the observed target's exact/interior classification,
containing original C function, up to 42 lines of entry prologue,
the exact label neighborhood, relevant original RECOMP_ITAIL callsites,
hardware seed classifications, and graph source hashes.

This script deliberately has no XDK builder invocation and does not
stage or rewrite any compiled function. Only once the ITAIL entry/ABI
is proven should a source batch be packaged and built. Do not spend an
Xbox build just to discover whether 0x0029655D is a function start.

## Separate timestamp issue

The xbWatson upload has host-added wallclock timestamps and occasionally
duplicate timestamps inserted within a single line; those are formatting,
not evidence of repeated guest execution. The observed hardware
boundary and tick values above are unchanged.
