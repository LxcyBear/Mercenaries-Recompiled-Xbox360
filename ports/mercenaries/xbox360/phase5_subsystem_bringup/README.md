# Phase 5 — Native subsystem bring-up

Phase 4 is complete on real Xbox 360 hardware.

The final Phase-4 gate reached `ICALL_SAFE target=0x800000CA` from translated
caller `0x0022BD2D` with `fault=0` and a 23-entry translated trace.

`0x800000CA` is xboxkrnl ordinal 202, `NtOpenFile`. Its observed stack
delta is 28 bytes, exactly matching six stdcall arguments plus the translated
synthetic return.

## Phase 5A — storage/content request capture

5A preserves the complete hardware-proven startup path, validates the live
`NtOpenFile` frame, decodes the guest `OBJECT_ATTRIBUTES` /
`ANSI_STRING` path plus access/share/options, and stops deliberately at an
explicit `STORAGE_OPEN` boundary without fabricating file I/O.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5A.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntopenfile_capture_xdk\main.cpp
build\phase5_subsystem_bringup\ntopenfile_capture_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntopenfile_capture_xdk\phase5a-manifest.json
```

Build: `P5A-NTOPEN202-CAPTURE-20261019-A`

Cookie: `P5A1 / 0x50354131`

Expected hardware evidence:

```text
NtOpenFile LIVE FRAME: ...
NtOpenFile OBJECT: ... path=...
PASS: Phase 5A captured ordinal 202 NtOpenFile request ...
BOUNDARY: kind=STORAGE_OPEN ... target=800000CA ...
PHASE 5A NTOPEN202 CAPTURE RESULT: PASS
```

The captured live path and flags define the next native Xbox 360 storage
implementation gate.


## Phase 5A hardware result

**PASS on real Xbox 360 hardware.**

The first live storage request is:

```text
NtOpenFile
path    = \Device\Harddisk0\partition1\
access  = 0x00100001
share   = 0x00000003
options = 0x00800021
caller  = 0x0022BD2D
```

The frame is exactly 28 bytes, the guest OBJECT_ATTRIBUTES / ANSI_STRING path
decoded cleanly, and the explicit `STORAGE_OPEN` boundary was reached with
`fault=0`.

## Phase 5B — native NtOpenFile continuation

5B maps the observed original-Xbox Partition1 tree to a deterministic writable
Xenon backing directory:

```text
\Device\Harddisk0\partition1\
    -> game:\merc360-partition1
```

It uses native XDK `CreateDirectoryA` / `CreateFileA`, returns a stable
tagged 32-bit guest handle token, writes the guest IO_STATUS_BLOCK, restores the
stdcall stack, and resumes translated execution.

Unknown storage roots remain fenced rather than guessed.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5B.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntopenfile_native_xdk\main.cpp
build\phase5_subsystem_bringup\ntopenfile_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntopenfile_native_xdk\phase5b-manifest.json
```

Build: `P5B-NTOPEN202-NATIVE-20261019-A`

Cookie: `P5B1 / 0x50354231`.
