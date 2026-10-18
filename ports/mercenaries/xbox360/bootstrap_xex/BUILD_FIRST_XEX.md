# Phase 1 — Build the first Mercenaries Xbox 360 diagnostics XEX

**Status: VS17 + Xbox 360 XDK compile succeeded; real-hardware test not yet verified.**

This phase tests that an isolated Xbox 360 game/title can start, log,
read controller input, and quit. **This is NOT a Mercenaries build.** It
contains no guest game code, original Xbox XBE, assets or renderer.

## Requirements

- Working, locally installed Xbox 360 XDK accessible from the user's **VS17**
  environment (confirmed as an existing working setup; not bundled here).
- An RGH/JTAG Xbox 360 on which you can launch your own `.xex` titles.
- A debugger or Xbox 360 Neighborhood session, if available, to capture
  `OutputDebugStringA` output.
- Only the source file `main.cpp` in this directory is required for the
  diagnostic target. Do **not** add the PC `ports/mercenaries/CMakeLists.txt`
  game or the Windows `src/` compatibility libraries.

## Build in VS17 with the existing Xbox 360 XDK toolchain

1. Open **VS17**, using the user's known-working Xbox 360 XDK integration.
2. Prefer a **copy of an existing working Xbox 360 game/title project** from
   your VS17 + XDK setup. If a working Xbox 360 project template is available,
   that also works. Avoid a regular Windows x86/x64 desktop project.
3. Remove any template's example main/entry point to prevent duplicate
   definitions.
4. Add [main.cpp](main.cpp) from this directory to the project.
5. Configure the target as **Xbox 360 / PowerPC** and select your working
   game/title configuration. Verify that VS17 actually invokes the Xbox 360
   XDK compiler, linker and XEX packaging tools, rather than a normal PC
   toolchain. Keep the existing project's SDK include directories, Xbox 360
   libraries and entry-point settings. The source includes `<xtl.h>`;
   no SDK files are included in this repository.
6. Build. Record **the exact error text** if VS17 reports missing headers,
   unresolved `XInputGetState` / `OutputDebugStringA`, entry-point
   conflicts or an unsupported XEX tool setting. Don't add Windows desktop
   libraries as a workaround.
7. Confirm that the *Xbox 360 build output* contains an XEX (normally
   `default.xex` or another XDK-configured XEX filename). Do not rename
   an ordinary Windows `.exe` and call it an XEX.

**The XDK toolchain is not available to the development environment here.**
The user has now reported a successful VS17/XDK compile of this diagnostic.
Real-hardware execution is still pending and is tracked separately.


### VS17 compatibility checkpoint

The IDE version alone doesn't establish that an Xbox 360 binary is being
produced. Keep the previously working XDK toolchain and project settings:
confirm the build output uses the **Xbox 360 PowerPC compiler/linker** and
runs the **XEX packaging** step. If any configuration needs to be adapted for
VS17, record that change and the exact error/output in the root README. Do not
change toolchain versions just to match old VS2010 instructions.

## Safe hardware test

1. **Back up anything you plan to replace.** Do not replace `launch.xex`,
   the Aurora/DashLaunch executable, or any boot-path file.
2. Create a unique folder such as `Hdd1:\Homebrew\Merc360Bootstrap`.
3. Copy *only* the diagnostic XEX into that folder.
4. Launch this XEX from Aurora / XeXMenu as an ordinary, isolated app.
5. **A black screen is expected** because the diagnostic initializes no
   graphics device. It should log through debugger output instead.
6. Check for `[Merc360] MERCENARIES XBOX 360 BOOTSTRAP START` and
   subsequent `[Merc360] HEARTBEAT: title running` lines.
7. With controller 0 connected, press **A** and verify the diagnostic exits.
8. Launch it a second time without pressing A; verify the **15-second**
   safety timeout and exit. If the system hangs or crashes, record exact
   behavior and power off normally; **do not** swap dashboard files to
   diagnose this standalone test.

### Diagnostic output

Primary: the connected Xbox 360 debug channel, lines prefixed
`[Merc360]`.

Best-effort file: `game:\merc360-bootstrap.log`. The `game:` device
may be non-writable depending on deployment; if the open fails, the program
logs a warning over the debug channel and continues. A missing log file is
**not** itself a failed execution.

Example expected structure (illustrative, **not real console output**):

~~~text
[Merc360] MERCENARIES XBOX 360 BOOTSTRAP START
[Merc360] No game code, XBE, renderer or guest memory initialized
[Merc360] Press controller A to exit, or automatic timeout at 15 seconds
[Merc360] Controller 0 detected
[Merc360] HEARTBEAT: title running
[Merc360] Controller A detected - exiting
[Merc360] MERCENARIES XBOX 360 BOOTSTRAP END
~~~

Output may differ if there is no controller, the file path is not writable,
or the timeout is used.

## Completion / reporting checklist

- [x] VS17 invokes the Xbox 360 XDK toolchain and title compiles successfully. **Confirmed October 18, 2026.**
- [ ] Actual XEX binary is generated.
- [ ] XEX launches from an isolated folder on real RGH/JTAG hardware.
- [ ] Debug output or usable trace is captured.
- [ ] Startup and 1-second heartbeats seen.
- [ ] Controller 0 detection and button A exit confirmed.
- [ ] 15-second timeout exit confirmed in a separate test.
- [ ] Compiler/XDK build details, console/kernel, commit SHA and
      test logs added to the root README evidence and progress log.

Send the full **VS17 Output window build log** on failure, or the
**debug/xbWatson transcript** on success, preferably with the current
`xbox360/bootstrap-guest-memory` commit identifier. We can then fix multiple
diagnostic issues in one patch, without guessing what the SDK supports.

## After Phase 1

Only after that standalone XEX is verified will we initialize a bounded
original-Xbox guest memory arena. The original game expects little-endian
data and address aliases; running generated game code unchanged on the
big-endian Xenon processor is not safe.
