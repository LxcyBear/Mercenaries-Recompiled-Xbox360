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


## Phase 5B hardware result

**PASS on real Xbox 360 hardware.**

The captured Partition1 request was serviced natively:

```text
xbox   = \Device\Harddisk0\partition1\
native = game:\merc360-partition1
status = 0x00000000
token  = 0x48000001
```

The translated path resumed with `fault=0` and immediately reached
`ICALL_SAFE target=0x800000DA` from caller `0x0022BD2D`.

`0x800000DA` is ordinal 218 `NtQueryVolumeInformationFile`. The observed
stack delta is 24 bytes, exactly five stdcall arguments plus the translated
synthetic return.

## Phase 5C — native volume query + handle lifecycle

5C resolves the tagged guest handle back to its native Xenon handle and
services `XboxFileFsSizeInformation` from the native `game:` volume using
`GetDiskFreeSpaceExA`. Guest-visible geometry remains FATX-style:

```text
BytesPerSector            = 512
SectorsPerAllocationUnit  = 32
AllocationUnitSize        = 16 KiB
```

Ordinal 187 `NtClose` is also armed so the same tagged handle can be released
natively if the live path closes it.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5C.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\volume_native_xdk\main.cpp
build\phase5_subsystem_bringup\volume_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\volume_native_xdk\phase5c-manifest.json
```

Build: `P5C-VOLUME218-NATIVE-20261019-A`

Cookie: `P5C1 / 0x50354331`.


## Phase 5C hardware result

**PASS on real Xbox 360 hardware.**

The complete native-backed storage lifecycle executed successfully:

```text
NtOpenFile                      -> STATUS_SUCCESS / token 0x48000001
NtQueryVolumeInformationFile    -> STATUS_SUCCESS
NtClose                         -> STATUS_SUCCESS
```

The live volume query used class 3 (`XboxFileFsSizeInformation`) and returned:

```text
TotalAllocationUnits      = 243868976
AvailableAllocationUnits  = 55322560
SectorsPerAllocationUnit  = 32
BytesPerSector             = 512
```

Translated execution then advanced with `fault=0` to
`ICALL_SAFE target=0x80000043`, ordinal 67 `IoCreateSymbolicLink`.

## Phase 5D — native symbolic-link mount continuation

5D decodes the exact guest `ANSI_STRING` link/target pair requested by retail
code and mirrors the maintained Xbox symbolic-link semantics. No drive letter
is guessed in advance.

Guest-created aliases such as `\??\T:` or `\??\U:` are stored and
consulted by the live storage path translator, so later drive-letter file opens
resolve through the exact device target created by the game.

Ordinal 69 `IoDeleteSymbolicLink` is also armed as the matching lifecycle
operation.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5D.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\symlink_native_xdk\main.cpp
build\phase5_subsystem_bringup\symlink_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\symlink_native_xdk\phase5d-manifest.json
```

Build: `P5D-SYMLINK67-NATIVE-20261019-A`

Cookie: `P5D1 / 0x50354431`.
