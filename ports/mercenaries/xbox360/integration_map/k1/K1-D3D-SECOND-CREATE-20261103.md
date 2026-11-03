# K1 D3D second CreateDevice — 2026-11-03

## Hardware witness

The K1 TEXT run proved the original guest 0x0017A0A0 path by reaching
K1STATE MAIN CHECKPOINT: calls=1 state=59C00449 substate=039D462F.
The previous DIRECT_FRONTIER was crossed. The next exact boundary:

    Phase 6DQ CreateDevice PP width=640 height=480 format=00000006 buffers=2 ms=00001121 swap=1 auto_depth=1 depth_format=0000002A
    Phase 6DQ CreateDevice contract mismatch: refusing generalized device fabrication
    P6DQ ROCKET HARD STOP kind=19 target=80070057 ticks=58540130
    BOUNDARY: kind=RENDERER_FATAL ... fault=0

The FIRST request, successfully bridged earlier in the same hardware run,
was identical except buffers=1 and ms=0x0011. Both use output 0x007AD604.

## Source-authentic, narrowly bounded next stage

The first request is constrained to one buffer / Xbox MSAA-none (0x0011).
The second request is constrained to exactly TWO buffers and Xbox
2-sample quincunx (0x1121). This value is defined as
D3DMULTISAMPLE_2_SAMPLES_MULTISAMPLE_QUINCUNX in the original Xbox D3D8
enumeration. The native Xenos swapchain is reconfigured using a REAL
D3DDevice_Reset with two backbuffers and D3DMULTISAMPLE_2_SAMPLES.

NOTE: Native Xbox 360 2x MSAA and original Xbox quincunx have the same
sample count but NOT necessarily the same resolve filter. The implementation
logs this difference rather than claiming pixel-exact reproduction.
A more exact filter may be needed for graphical fidelity later.

The second request additionally requires:
* the previous CreateDevice bridge call succeeded exactly once;
* same retail guest device identity 0x00299380;
* the current output pointer readback matches that identity;
* the original guest-fault fence passes;
* the original native Xenos device is alive;
* the actual Xenos Reset HRESULT indicates success.

If native Reset fails, no success is returned to the game: the existing
RENDERER_FATAL hard fence is raised. No Xenos mode or device resource is
fabricated, and no new framebuffer/pixel count is invented. Unknown
presentation parameters remain rejected. Native XDK build and hardware
execution are NOT verified by source-only staging.

The script derives a new main.cpp plus a separate 64-TU source directory.
It patches only the file that actually owns the 0028CAA0 bridge (main.cpp
or exactly one original TrueTU). All original game source shards, generated
runtime header, and source-authentic K1 TEXT parent remain unchanged.
The existing incremental builder copies by content hash: at most one
changed TrueTU and the changed main.cpp should need recompilation.

## Source-only preflight

    cd "C:\Users\jorda\Mercenaries-Recompiled-Xbox360"
    git pull --ff-only
    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1D3DSecondCreateDevice.ps1"

This reruns inherited K1 TEXT source proofs, regression fixtures, parent
hash/safety checks, unique bridge ownership, 64-shard and runtime header
identity, then writes a new staged manifest.

## One incremental XDK build

    powershell.exe -NoProfile -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\integration_map\k1\Advance-K1D3DSecondCreateDevice.ps1" -Build

Expected XEX after successful compilation:

    build\phase6_integration_map\k1_d3d_second_create\xdk\Merc-K1D3D-SecondCreateDevice.xex

Xbox hardware must independently prove:
1. K1STATE checkpoint still fires;
2. K1D3D SECOND native Reset begins, returns a genuine successful HRESULT;
3. the original guest code continues past the second CreateDevice;
4. record the next exact boundary and any real Swap/PersistDisplay and
   display_calls (never assume pixels until seen).

If Xbox 360 XDK compilation reports an unavailable Reset entrypoint or an
API contract difference, fix that using the local XDK headers. Do NOT
replace Reset with S_OK, skip the second CreateDevice, or remove its fences.

## First hardware result and R2 follow-up

First hardware K1D3D run on November 3, 2026 (build tag includes
P6K1-D3D-SECOND-CREATE-20261103):
* K1STATE MAIN CHECKPOINT: calls=1, state=59C00449, substate=039D462F.
* Second PP 640x480 format 6, buffers=2, multisample=0x1121 accepted by
  the explicit presentation contract.
* The *new ownership check* stopped before Xenos Reset:
  K1D3D SECOND: first-device ownership/out-pointer contract drift.
* Final ticks=58,540,130, RENDERER_FATAL 0x80070057, display_calls=0.
* First CreateDevice bridge count=1 and identity=0x00299380 in summary;
  the old ownership guard did not report out-slot readback, so the
  actual second-call out-slot contents are UNKNOWN at this checkpoint.

R2 therefore reads the out slot ONCE and checks s_accessFault first; logs
the actual first-device call count, identity, out slot address and slot value;
then only accepts the two proven-compatible values 0 (caller cleared the
slot) or 0x00299380 (first guest device) at the observed 0x007AD604
address. Unknown nonzero pointers and all other identity/ownership
changes remain fatal. The native Reset is still obligatory before guest
success, not fabricated. Do not claim R2 hardware success without a log.

R2 output directory:
build\phase6_integration_map\k1_d3d_second_create_r2

R2 XEX:
build\phase6_integration_map\k1_d3d_second_create_r2\xdk\Merc-K1D3D-SecondCreateDevice-r2.xex

The R2 path is intentionally isolated from the previous completed stage:
the source stager refuses to overwrite earlier generated outputs when
they differ. Keeping the earlier XEX aids rollback and differential tests.
