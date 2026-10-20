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


## Phase 5D hardware result

**PASS on real Xbox 360 hardware.**

The previously proven native storage lifecycle remained intact, then retail
code created the exact optical-disc symbolic link:

```text
link   = \??\D:
target = \Device\CdRom0
status = 0x00000000
```

The live path then advanced with `fault=0` to:

```text
DIRECT_FRONTIER
caller = 0x0022BD2D
target = 0x0022C1C0
```

This confirms the retail title establishes its normal original-Xbox `D:`
namespace before continuing startup.

## Phase 5E — post-mount translated helper

5E preserves the complete native storage + symbolic-link stack and promotes
only the exact hardware-observed translated root `0x0022C1C0`. Deeper direct
callees remain fenced.

Preparation fails explicitly if C1C0 is not an exact function start or has no
generated translated body.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5E.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_c1c0_xdk\main.cpp
build\phase5_subsystem_bringup\direct_c1c0_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_c1c0_xdk\phase5e-manifest.json
```

Build: `P5E-DIRECTC1C0-20261020-A`

Cookie: `P5E1 / 0x50354531`.


## Phase 5E hardware result

**PASS on real Xbox 360 hardware.**

The complete native storage and optical-disc mount path remained intact.
Translated root `0x0022C1C0` executed successfully and advanced with
`fault=0` to:

```text
DIRECT_FRONTIER
caller = 0x0022C1C0
target = 0x002370B8
trace  = 24 translated entries
```

## Phase 5F — next retail translated helper

5F preserves the complete native storage + symbolic-link stack and promotes
only the exact hardware-observed translated root `0x002370B8`. Deeper direct
callees remain fenced.

Preparation fails explicitly if `0x002370B8` is a split/mid-function target
or lacks a generated translated body.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5F.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_370b8_xdk\main.cpp
build\phase5_subsystem_bringup\direct_370b8_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_370b8_xdk\phase5f-manifest.json
```

Build: `P5F-DIRECT370B8-20261020-A`

Cookie: `P5F1 / 0x50354631`.


## Phase 5F hardware result

**PASS on real Xbox 360 hardware.**

The full native storage and optical-disc mount stack remained intact.
Translated root `0x002370B8` executed and opened a substantially larger
already-packed retail initialization path. The translated trace expanded from
24 to 45 entries before reaching:

```text
DIRECT_FRONTIER
caller = 0x0023A3CE
target = 0x0022BE8C
fault  = 0
trace  = 45
```

The observed path included repeated execution through `0x0023F150` and
`0x0023A3CE`, consistent with a real initialization loop/state-check path
rather than another single-function hop.

## Phase 5G — next retail translated helper

5G retains the complete native storage/mount stack and every previously proven
translated root, then promotes only the exact hardware-observed root
`0x0022BE8C`.

Preparation fails explicitly if `0x0022BE8C` is a split/mid-function target
or lacks a generated translated body.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5G.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_be8c_xdk\main.cpp
build\phase5_subsystem_bringup\direct_be8c_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_be8c_xdk\phase5g-manifest.json
```

Build: `P5G-DIRECTBE8C-20261020-A`

Cookie: `P5G1 / 0x50354731`.


## Phase 5G hardware result

**PASS on real Xbox 360 hardware.**

The full native storage and optical-disc mount stack remained intact.
Translated root `0x0022BE8C` executed successfully and reached the next live
kernel dependency with `fault=0`:

```text
ICALL_SAFE
caller = 0x0022BE8C
target = 0x800000BE
trace  = 46
```

`0x800000BE` is ordinal 190 `NtCreateFile`. The observed stack delta is
40 bytes, exactly nine stdcall arguments plus the translated synthetic return.

## Phase 5H — native NtCreateFile + synchronous NtReadFile

5H reuses the proven guest symbolic-link/path translator and tagged Xenon
handle table to service ordinal 190 `NtCreateFile` through native XDK
`CreateFileA` semantics. It decodes the live guest `OBJECT_ATTRIBUTES` /
`ANSI_STRING`, maps Xbox create dispositions, writes the guest handle and
`IO_STATUS_BLOCK`, and resumes translated execution.

Ordinal 219 `NtReadFile` is also armed for synchronous native-backed reads
from tagged handles. Event/APC asynchronous forms remain explicitly fenced.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5H.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntcreatefile_native_xdk\main.cpp
build\phase5_subsystem_bringup\ntcreatefile_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntcreatefile_native_xdk\phase5h-manifest.json
```

Build: `P5H-NTCREATE190-NATIVE-20261020-A`

Cookie: `P5H1 / 0x50354831`.


## Phase 5H hardware result

**PASS on real Xbox 360 hardware.**

The full native storage/mount stack remained intact. Ordinal 190
`NtCreateFile` then opened/created the first live title-storage directory:

```text
xbox        = \Device\Harddisk0\partition1\TDATA
native      = game:\merc360-partition1\TDATA
disposition = 3  (FILE_OPEN_IF)
status      = 0x00000000
token       = 0x48000001
```

The tagged handle was closed successfully. No `NtReadFile` call was reached
in this run.

Translated execution then advanced with `fault=0` to
`ICALL_SAFE target=0x80000121`, ordinal 289 `RtlInitAnsiString`. The
observed full frame is 12 bytes.

## Phase 5I — RtlInitAnsiString continuation

5I matches the maintained Xbox `ANSI_STRING` initialization semantics:

```text
USHORT Length
USHORT MaximumLength
ULONG  Buffer   (guest VA)
```

The source C string is scanned through bounded guest reads with the maintained
`0xFFFE` clamp, and a bounded printable preview is logged before execution
continues.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5I.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\rtl_init_ansi_xdk\main.cpp
build\phase5_subsystem_bringup\rtl_init_ansi_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\rtl_init_ansi_xdk\phase5i-manifest.json
```

Build: `P5I-RTLINITANSI289-20261020-A`

Cookie: `P5I1 / 0x50354931`.


## Phase 5I hardware result

**PASS on real Xbox 360 hardware.**

The complete native storage and mount stack remained intact. The maintained
ordinal 289 `RtlInitAnsiString` continuation exposed the exact title-id path:

```text
\Device\Harddisk0\partition1\TDATA\4c410015
```

The live title then successfully:

```text
created/opened TDATA\4c410015
mounted \??\T: -> \Device\Harddisk0\partition1\TDATA\4c410015
created/opened UDATA
created/opened UDATA\4c410015
```

All observed `NtCreateFile` calls returned STATUS_SUCCESS. The translated
trace reached 47 entries and advanced with `fault=0` to:

```text
DIRECT_FRONTIER
caller = 0x0022BE8C
target = 0x0022F026
```

## Phase 5J — post-title-storage translated helper

5J preserves the full native Partition1, `D:`, `T:`, TDATA/UDATA,
`NtCreateFile`, handle-lifecycle and RTL-string stack, then promotes only the
exact hardware-observed translated root `0x0022F026`.

Preparation fails explicitly if F026 is a split/mid-function target or lacks a
generated translated body.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5J.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_f026_xdk\main.cpp
build\phase5_subsystem_bringup\direct_f026_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_f026_xdk\phase5j-manifest.json
```

Build: `P5J-DIRECTF026-20261020-A`

Cookie: `P5J1 / 0x50354A31`.


## Phase 5J hardware result

**PASS on real Xbox 360 hardware.**

The phase-specific main/environment link guard passed, proving the generated
5J sources were matched correctly. The complete native storage, D:/T: mount,
TDATA/UDATA title-id hierarchy, NtCreateFile/NtClose, and RTL ANSI-string
stack remained intact.

Translated root `0x0022F026` executed and initialized:

```text
$$XTINFO
.text
```

as live Xbox `ANSI_STRING` values. Execution then reached:

```text
ICALL_SAFE
caller = 0x0022F026
target = 0x80000117
fault  = 0
trace  = 48
```

`0x80000117` is ordinal 279 `RtlEqualString`. The observed full frame is
16 bytes, exactly three stdcall arguments plus the synthetic return.

## Phase 5K — maintained RtlEqualString continuation

5K matches the maintained Xbox `RtlEqualString` semantics: both guest
`ANSI_STRING` lengths must match, bytes are compared directly or with ASCII
case folding when `CaseInsensitive` is nonzero, and the BOOLEAN result is
returned in EAX.

The first 128 printable bytes of both live operands are logged so the hardware
trace shows exactly which XBE/image section names retail code is comparing.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5K.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\rtl_equal_string_xdk\main.cpp
build\phase5_subsystem_bringup\rtl_equal_string_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\rtl_equal_string_xdk\phase5k-manifest.json
```

Build: `P5K-RTLEQUAL279-20261020-A`

Cookie: `P5K1 / 0x50354B31`.

Link-time guard symbol: `phase5k_env_build_cookie`.


## Phase 5K hardware result

**PASS on real Xbox 360 hardware.**

The complete native title-storage and mount stack remained intact. Retail
helper `0x0022F026` used `RtlInitAnsiString` + `RtlEqualString` to scan
all 14 loaded XBE section names for the search key `$$XTINFO`.

Observed section names:

```text
.text
XMV
XACTENG
D3D
XGRPH
DSOUND
WMADEC
XPP
.rdata
.data
DOLBY
$$XTIMAGE
$$XSIMAGE
.XTLID
```

All comparisons correctly returned false because this supported retail XBE has
no `$$XTINFO` section. Execution then advanced with `fault=0` to:

```text
DIRECT_FRONTIER
caller = 0x0022F026
target = 0x0022B178
trace  = 48
```

## Phase 5L — maintained SetLastError continuation

5L preserves the complete native Partition1, D:/T: mounts, title-data
hierarchy and RTL string-comparison path, then executes the exact
hardware-observed root `0x0022B178` through its reviewed maintained manual
implementation. `Recompile.ps1` intentionally marks this function manual;
production `recomp_manual.c` implements it as the Xbox `SetLastError` wrapper
using stable runtime last-error state instead of the flattened FS-backed TIB.

Every other missing generated body remains fail-closed.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5L.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_b178_xdk\main.cpp
build\phase5_subsystem_bringup\direct_b178_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_b178_xdk\phase5l-manifest.json
```

Build: `P5L-DIRECTB178-20261020-A`

Cookie: `P5L1 / 0x50354C31`.

Link-time guard symbol: `phase5l_env_build_cookie`.


## Phase 5L hardware result

**PASS on real Xbox 360 hardware.**

The complete native Partition1, D:/T:, TDATA/UDATA, file-handle and RTL
section-scan path remained intact. The maintained support-owned
`sub_0022B178` / Xbox `SetLastError` implementation executed with:

```text
value   = 0x00000490
calls   = 1
new_esp = 0x008BFC14
```

Startup continued substantially farther after B178. The image-section scan
found the real `$$XTIMAGE` and `$$XSIMAGE` sections, then title-storage code
successfully created/opened:

```text
\Device\Harddisk0\partition1\UDATA\4c410015\TitleMeta.xbx
    -> game:\merc360-partition1\UDATA\4c410015\TitleMeta.xbx
token = 0x48000002
status = 0x00000000
```

The translated trace reached 54 entries and stopped cleanly with `fault=0`
at:

```text
ICALL_SAFE
caller    = 0x00239C23
target    = 0x800000D3
esp       = 0x008BFC24
saved_esp = 0x008BFC3C
```

Target `0x800000D3` is original-Xbox ordinal 211
`NtQueryInformationFile`. The 24-byte live frame is exactly five stdcall
arguments plus the translated synthetic return.

## Phase 5M — NtQueryInformationFile capture

5M keeps the complete 5L-proven runtime stack live and captures the exact
ordinal-211 request before implementing any `FILE_INFORMATION_CLASS`
semantics. It records:

```text
FileHandle
IoStatusBlock
FileInformation
Length
FileInformationClass
```

The capture then exits through a dedicated `FILE_INFORMATION` boundary.
This intentionally avoids guessing which Xbox information structure
Mercenaries expects.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5M.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntqueryinfo_capture_xdk\main.cpp
build\phase5_subsystem_bringup\ntqueryinfo_capture_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntqueryinfo_capture_xdk\phase5m-manifest.json
```

Build: `P5M-NTQUERYINFO211-CAPTURE-20261020-A`

Cookie: `P5M1 / 0x50354D31`.

Link-time guard symbol: `phase5m_env_build_cookie`.


## Phase 5M hardware result

**PASS on real Xbox 360 hardware.**

The capture-only ordinal-211 gate preserved the complete Phase-5L path and
observed the live request immediately after `TitleMeta.xbx` was opened:

```text
handle = 0x48000002
iosb   = 0x008BFEB4
info   = 0x008BFE68
len    = 56
class  = 34
fault  = 0
trace  = 54
```

Class 34 is `FileNetworkOpenInformation`, and the 56-byte request matches
the exact `FILE_NETWORK_OPEN_INFORMATION` footprint.

## Phase 5N — native FileNetworkOpenInformation continuation

5N retains the tagged native handle and records the Xenon path associated with
each guest handle token. The observed class-34 request is returned as:

```text
+0x00 CreationTime      u64
+0x08 LastAccessTime    u64
+0x10 LastWriteTime     u64
+0x18 ChangeTime        u64
+0x20 AllocationSize    u64
+0x28 EndOfFile         u64
+0x30 FileAttributes    u32
+0x34 Reserved          u32
total                   56 bytes
```

Native metadata comes from `GetFileAttributesExA`. ChangeTime mirrors
LastWriteTime because that XAM-visible metadata surface has no distinct
change-time field. AllocationSize rounds EOF to the 16 KiB FATX-style unit
already used by the proven volume bridge. Unobserved information classes stay
fenced at `FILE_INFORMATION`.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5N.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntqueryinfo_native_xdk\main.cpp
build\phase5_subsystem_bringup\ntqueryinfo_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntqueryinfo_native_xdk\phase5n-manifest.json
```

Build: `P5N-NTQUERYINFO211-NATIVE-20261020-A`

Cookie: `P5N1 / 0x50354E31`.

Link-time guard symbol: `phase5n_env_build_cookie`.


## Phase 5N hardware result

**PASS on real Xbox 360 hardware.**

The native class-34 `NtQueryInformationFile` continuation returned real
metadata for the tagged `TitleMeta.xbx` handle:

```text
handle     = 0x48000002
class      = 34
length     = 56
status     = 0x00000000
eof        = 0
allocation = 0
attributes = 0x00000080
```

After the successful query, translated retail execution continued and reached
a new direct frontier with no guest fault:

```text
caller    = 0x00239C23
target    = 0x00239B78
esp       = 0x008BFC18
saved_esp = 0x008BFC18
fault     = 0
trace     = 54
```

## Phase 5O — direct root 0x00239B78

5O promotes only the newly observed direct target at depth zero. The package
requires `0x00239B78` to be an exact function start with a frozen Stage-3
generated body. Split/mid-function targets and missing bodies fail preparation
explicitly. Calls beyond the one promoted root remain `DIRECT_FRONTIER`
boundaries.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5O.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_239b78_xdk\main.cpp
build\phase5_subsystem_bringup\direct_239b78_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_239b78_xdk\phase5o-manifest.json
```

Build: `P5O-DIRECT239B78-20261020-A`

Cookie: `P5O1 / 0x50354F31`.

Link-time guard symbol: `phase5o_env_build_cookie`.
