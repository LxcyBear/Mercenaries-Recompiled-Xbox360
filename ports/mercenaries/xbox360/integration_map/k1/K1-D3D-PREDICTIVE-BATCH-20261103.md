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

## Local 2026-11-03 source audit outcome and correction

The first hardware-informed source audit returned:

    ITAIL=0x0029655D classification=not_in_retail_function_inventory
    SEED 0x00296550 exact_source_entry recomp_0013.c
    SEED 0x002965F0 exact_source_entry recomp_0013.c
    GRAPH: source-authentic candidate=0
    RELATED ORIGINAL CALLSITES: owners=4 itail_macro_sites=2

This disproves the early hypothesis that 0x0029655D is necessarily a
valid interior label inside 0x00296550. The current retail function
inventory does not cover it. A short offset from a valid function start
is NOT an ABI, instruction boundary, or legal tail-call destination.

**Planner issue corrected:** prior breadth-first search stopped at already
compiled graphics functions. Consequently zero new candidates was not
a proof that the graph contained no uncompiled dependencies. The new
search traverses the *original C* of already compiled functions without
re-emitting them, then selects only genuine missing D3D/XGRPH function
starts within a bounded depth/candidate cap. A regression fixture
checks this through-compiled-root graph traversal.

**New evidence:** the report now includes the nearest previous and
following original function ranges, their exact exclusive ends,
gap width/offset, original C prologue and epilogue excerpts, target
string occurrences anywhere in D3D source, and nearby original ITAIL
macro callsite context. The console displays the gap summary and
through-compiled-root graph metrics.

Optional local raw-byte proof:

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Plan-K1D3DBatch.ps1" -XbePath "C:\your\existing\retail\default.xbe"

This is an optional input. The script verifies the exact supported
retail SHA-256 before interpreting the XBE section table, and reports
only a bounded byte window around 0x0029655D. Raw bytes are **not**
an x86 instruction-boundary proof; they help determine whether the
inventory gap contains actual code, padding or an unexpected thunk.
No retail XBE bytes or game assets are committed to GitHub.

There is still **no authorization to compile an ITAIL trampoline**
without original instruction-boundary and guest stack/register proof.
The latest known good native Reset/64 TrueTUs remain unchanged.


## Source-proven D3D 16-way jump table (latest 2026-11-03 audit)

The exact retail generated C function sub_00296550 spans
0x00296550–0x0029655D (13 bytes, 4 original x86 instructions)
and ends with:

    eax = edi;
    PUSH32(esp, esi);
    eax = eax & 0xF;
    g_seh_ebp = ebp;
    RECOMP_ITAIL(GUEST_READ32(eax * 4 + 0x2965D4));

This provides concrete *original C* evidence of a computed 16-way
indirect tail jump, with ESI pushed onto the guest stack before the jump.
The Xbox observed destination was 0x0029655D, exactly the previous
function's end-exclusive boundary. It is **not** a recognized function
start. The recognized next function starts at 0x002965A8, 75 bytes
later.

The indexed table reads 16 32-bit little-endian DWORD slots at
0x002965D4 through 0x00296613, end-exclusive 0x00296614.
This is significant: the function inventory claims sub_002965F0
starts at 0x002965F0, *inside that table*, at slot 7
(0x002965F0 - 0x002965D4 = 28 bytes = 7 DWORDs).

Consequently, **code-versus-data provenance is now suspect** for
this segment. The original function inventory and generated source
do not independently prove that the 16 slots are ordinary immutable
function addresses, nor that sub_002965F0 is truly safe compiled
code at that overlapping address. D3D guest memory may be modified
at runtime. Do not automatically prune or erase sub_002965F0 or
invent guest execution at 0x0029655D.

The K1 batch planner now validates the exact original 96550
source instruction pattern and reports this table/code overlap.
When a local exact-SHA retail default.xbe path is provided,
it also extracts all 16 actual original XBE DWORDs and classifies
each target relative to the retail inventory, flagging the
hardware-observed destination and any branch targets in the gap.
This is **static file** evidence, NOT a claim that those DWORDs
were unchanged at the time of execution on Xbox 360.

Run without a build:

    cd "C:\Users\jorda\Mercenaries-Recompiled-Xbox360"
    git pull --ff-only
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Plan-K1D3DBatch.ps1" -XbePath "C:\path\to\your\original\default.xbe"

Or omit -XbePath for the original-source-only static table/overlap
audit. Raw data stays entirely on the local PC; never commit
or upload the game file. No additional XDK build is justified until
we reconcile the 16-way table, its memory/code overlap, and the
guest stack/register/target ABI. The known-good second Xenos Reset
and original 64 TrueTUs remain untouched.
