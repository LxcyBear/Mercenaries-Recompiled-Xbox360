# Phase 6A — First native Xenos surface

This is the first Phase-6 hardware proof. It does **not** run Mercenaries guest
rendering yet. It proves only that the native Xbox 360 target can own the
display, clear the real Xbox 360 back buffer and present repeatable frames.

## Build

Use the same known-good VS17 + Xbox 360 XDK **game/title** project configuration
that built the Phase-1/Phase-5 XEXs.

1. Switch to branch `xbox360/phase6-native-graphics`.
2. Remove/disable the previous test `main.cpp` from the VS project so there is
   only one entry point.
3. Add:
   `ports/mercenaries/xbox360/phase6_native_graphics/xenos_surface_xex/main.cpp`
4. Keep the existing Xbox 360/XDK system libraries from the working project.
5. Add **`d3d9.lib`** to the Xbox 360 linker inputs if the project does not
   already link it.
6. Build the XEX with the same Xbox 360 PowerPC/XEX packaging settings already
   proven in earlier phases.

Do not add Windows desktop DirectX libraries and do not copy XDK headers/libs
into this repository.

## Expected hardware behavior

Launch the XEX from an isolated folder.

Expected screen sequence over roughly 15 seconds:

- dark green
- blue
- red
- white

The loop is vsynced and may be exited early with controller A.

Expected xbWatson/debug markers:

```text
[Merc360:P6A] PHASE 6A NATIVE XENOS SURFACE PROOF START
[Merc360:P6A] BUILD TAG: P6A-XENOS-SURFACE-20261021-A
[Merc360:P6A] CreateDevice: 640x480 A8R8G8B8, vsync, no depth
[Merc360:P6A] PASS: Direct3D_CreateDevice
[Merc360:P6A] Present stage 0: dark green
...
[Merc360:P6A] PASS: native Xenos clear/present loop completed
[Merc360:P6A] PHASE 6A RESULT: PASS
[Merc360:P6A] PHASE 6A NATIVE XENOS SURFACE PROOF END
[XAPI RETURN VALUE] 0
```

Best-effort file log:
`game:\merc360-phase6a.log`.

## PASS criteria

Phase 6A passes only when all of these are true:

- Xbox 360 XDK build succeeds with the native `d3d9.lib`;
- real hardware creates the D3D device;
- at least one clear/present visibly reaches the display;
- the color stages remain stable rather than corrupt/flickering;
- xbWatson shows the device-creation PASS and Phase-6A PASS markers;
- title exits cleanly with XAPI return 0.

A compile error, device-creation failure, black/no-sync display, GPU hang, or
crash is evidence to fix. Do not bypass it with fake graphics-success stubs.

## After PASS

The next step is **Phase 6B: backend seam** — wrap the proven native device,
surface/texture upload and presentation primitives behind a small backend-neutral
interface. Then the translated NV2A/D3D8 path can begin feeding real guest
rendering into the same native Xenos device.
