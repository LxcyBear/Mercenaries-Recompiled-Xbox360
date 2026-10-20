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


## Phase 5O hardware result

**PASS on real Xbox 360 hardware.**

The native class-34 `NtQueryInformationFile` path remained successful, then
the newly promoted translated root executed:

```text
trace[54] = 0x00239B78
```

It advanced immediately to the next clean direct frontier:

```text
caller    = 0x00239B78
target    = 0x0023DDDD
esp       = 0x008BFBE0
saved_esp = 0x008BFBE0
fault     = 0
trace     = 55
```

Harness result: `PHASE 5O DIRECT239B78 RESULT: PASS`.

## Phase 5P — direct root 0x0023DDDD

5P promotes only `0x0023DDDD` at depth zero while retaining all earlier
Phase-5 storage/runtime continuations and root `0x00239B78`. The package
requires an exact function start plus a generated Stage-3 body; split targets
and missing bodies fail preparation explicitly.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5P.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_23dddd_xdk\main.cpp
build\phase5_subsystem_bringup\direct_23dddd_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_23dddd_xdk\phase5p-manifest.json
```

Build: `P5P-DIRECT23DDDD-20261020-A`

Cookie: `P5P1 / 0x50355031`.

Link-time guard symbol: `phase5p_env_build_cookie`.


## Phase 5P hardware result

**PASS on real Xbox 360 hardware.**

The newly promoted translated root executed as:

```text
trace[55] = 0x0023DDDD
```

and immediately reached the next clean direct frontier:

```text
caller    = 0x0023DDDD
target    = 0x0023DD7B
esp       = 0x008BF76C
saved_esp = 0x008BF76C
fault     = 0
trace     = 56
```

Harness result: `PHASE 5P DIRECT23DDDD RESULT: PASS`.

## Phase 5Q — direct root 0x0023DD7B

5Q promotes only `0x0023DD7B` at depth zero while retaining the complete
Phase-5 storage/runtime stack plus roots `0x00239B78` and `0x0023DDDD`.
The gate requires an exact function start and generated Stage-3 body.
Split/mid-function targets and missing bodies fail preparation explicitly.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5Q.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_23dd7b_xdk\main.cpp
build\phase5_subsystem_bringup\direct_23dd7b_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_23dd7b_xdk\phase5q-manifest.json
```

Build: `P5Q-DIRECT23DD7B-20261020-A`

Cookie: `P5Q1 / 0x50355131`.

Link-time guard symbol: `phase5q_env_build_cookie`.


## Phase 5Q hardware result

**PASS on real Xbox 360 hardware.**

The newly promoted translated root executed as:

```text
trace[56] = 0x0023DD7B
```

and immediately reached the next clean direct frontier:

```text
caller    = 0x0023DD7B
target    = 0x0023DDA0
esp       = 0x008BF774
saved_esp = 0x008BF774
fault     = 0
trace     = 57
```

Harness result: `PHASE 5Q DIRECT23DD7B RESULT: PASS`.

## Phase 5R — direct root 0x0023DDA0

5R promotes only `0x0023DDA0` at depth zero while retaining the complete
Phase-5 storage/runtime stack plus roots `0x00239B78`, `0x0023DDDD`, and
`0x0023DD7B`. Because the new address is only 0x25 bytes above the preceding
root, the gate explicitly rejects split/mid-function targets. A missing
Stage-3 generated body also fails closed.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5R.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_23dda0_xdk\main.cpp
build\phase5_subsystem_bringup\direct_23dda0_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_23dda0_xdk\phase5r-manifest.json
```

Build: `P5R-DIRECT23DDA0-20261020-A`

Cookie: `P5R1 / 0x50355231`.

Link-time guard symbol: `phase5r_env_build_cookie`.


## Phase 5R hardware result

**PASS on real Xbox 360 hardware.**

The promoted root `0x0023DDA0` executed twice:

```text
trace[57] = 0x0023DDA0
trace[58] = 0x0023DDA0
```

and then reached the next clean direct frontier:

```text
caller    = 0x0023DDA0
target    = 0x0023DD56
esp       = 0x008BF764
saved_esp = 0x008BF764
fault     = 0
trace     = 59
```

Harness result: `PHASE 5R DIRECT23DDA0 RESULT: PASS`.

## Phase 5S — direct root 0x0023DD56

5S promotes only `0x0023DD56` at depth zero while retaining the complete
Phase-5 storage/runtime stack plus roots `0x00239B78`, `0x0023DDDD`,
`0x0023DD7B`, and `0x0023DDA0`. The proof requires the observed repeated
`0x0023DDA0` trace shape before `trace[59]=0x0023DD56`. The gate rejects
split/mid-function targets and missing generated bodies explicitly.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5S.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_23dd56_xdk\main.cpp
build\phase5_subsystem_bringup\direct_23dd56_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_23dd56_xdk\phase5s-manifest.json
```

Build: `P5S-DIRECT23DD56-20261020-A`

Cookie: `P5S1 / 0x50355331`.

Link-time guard symbol: `phase5s_env_build_cookie`.


## Phase 5S hardware result

**PASS on real Xbox 360 hardware.**

The promoted root `0x0023DD56` executed as:

```text
trace[59] = 0x0023DD56
```

and immediately reached the next clean direct frontier:

```text
caller    = 0x0023DD56
target    = 0x0023F8CB
esp       = 0x008BF758
saved_esp = 0x008BF758
fault     = 0
trace     = 60
```

Harness result: `PHASE 5S DIRECT23DD56 RESULT: PASS`.

## Phase 5T — direct root 0x0023F8CB

5T promotes only `0x0023F8CB` at depth zero while retaining the complete
Phase-5 storage/runtime stack plus roots `0x00239B78`, `0x0023DDDD`,
`0x0023DD7B`, `0x0023DDA0`, and `0x0023DD56`. The package requires an
exact function start and a frozen Stage-3 generated body. Split/mid-function
targets and missing bodies fail preparation explicitly.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5T.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_23f8cb_xdk\main.cpp
build\phase5_subsystem_bringup\direct_23f8cb_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_23f8cb_xdk\phase5t-manifest.json
```

Build: `P5T-DIRECT23F8CB-20261020-A`

Cookie: `P5T1 / 0x50355431`.

Link-time guard symbol: `phase5t_env_build_cookie`.


## Phase 5T hardware result

**PASS on real Xbox 360 hardware.**

The promoted root `0x0023F8CB` executed inside a repeated TitleMeta loop with
`0x0023DD56`. The trace advanced from the first `0x0023F8CB` entry at 60
to a new kernel boundary at trace 119:

```text
BOUNDARY kind = ICALL_SAFE
caller        = 0x0023F8CB
target        = 0x800000EC
esp           = 0x008BFC18
saved_esp     = 0x008BFC3C
fault         = 0
trace         = 119
```

Xbox kernel ordinal 236 is `NtWriteFile@32`; the 36-byte observed full frame
matches 32 argument bytes plus the synthetic return slot.

Harness result: `PHASE 5T DIRECT23F8CB RESULT: PASS`.

## Phase 5U — native NtWriteFile continuation

5U adds a synchronous native bridge for ordinal 236 while retaining every
previous Phase-5 continuation and translated root. The bridge decodes:

```text
handle
event
APC routine
APC context
IO_STATUS_BLOCK
buffer
length
byte offset
```

The synchronous form resolves the tagged guest handle to its native Xenon
HANDLE, applies supported byte-offset semantics, performs a real `WriteFile`,
writes guest `IO_STATUS_BLOCK.Status` and `Information`, restores the
stdcall stack, and resumes retail execution.

Supported offset forms:

```text
absolute offset
FILE_USE_FILE_POINTER_POSITION
FILE_WRITE_TO_END_OF_FILE
```

Async event/APC forms and other negative/special offsets remain fenced.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5U.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntwritefile_native_xdk\main.cpp
build\phase5_subsystem_bringup\ntwritefile_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntwritefile_native_xdk\phase5u-manifest.json
```

Build: `P5U-NTWRITEFILE236-NATIVE-20261020-A`

Cookie: `P5U1 / 0x50355531`.

Link-time guard symbol: `phase5u_env_build_cookie`.


## Phase 5U hardware result

**PASS on real Xbox 360 hardware.**

The native ordinal-236 `NtWriteFile` bridge serviced the real
`TitleMeta.xbx` write:

```text
handle     = 0x48000002
buffer     = 0x008BFC48
length     = 48
offset_ptr = 0x00000000
status     = 0x00000000
bytes      = 48
requested  = 48
```

The write was followed by a successful `NtClose`, then retail execution
reached:

```text
caller = 0x0023F8CB
target = 0x0022BDA5
esp    = 0x008BFC28
trace  = 119
fault  = 0
```

Harness result: `PHASE 5U NTWRITEFILE236 NATIVE RESULT: PASS`.

## Phase 5V — direct root 0x0022BDA5

5V promotes only `0x0022BDA5` at depth zero while preserving the native
`NtWriteFile` continuation and all previously proven Phase-5 runtime/storage
work.

The Phase-5 path is now stateful because 5U wrote persistent
`TitleMeta.xbx` contents. Therefore 5V does not require a write on every run.
Instead, the promoted root is instrumented with an explicit execution flag so
hardware can prove `0x0022BDA5` ran even if the earlier TitleMeta loop changes
iteration count.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5V.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_22bda5_xdk\main.cpp
build\phase5_subsystem_bringup\direct_22bda5_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_22bda5_xdk\phase5v-manifest.json
```

Build: `P5V-DIRECT22BDA5-20261020-A`

Cookie: `P5V1 / 0x50355631`.

Link-time guard symbol: `phase5v_env_build_cookie`.


## Phase 5V hardware result

**Hardware PASS; emitted harness PASS expression was stale.**

The 5U write persisted `TitleMeta.xbx`, so on 5V the metadata query reports:

```text
EOF        = 48
allocation = 16384
status     = 0
```

Retail therefore takes a shorter path than the earlier zero-byte-file runs.
The promoted root still executes:

```text
trace[54] = 0x0022BDA5
```

It then advances into `TitleImage.xbx` handling and reaches:

```text
caller    = 0x00239C23
target    = 0x0022F08D
esp       = 0x008BFBBC
saved_esp = 0x008BFBBC
trace     = 58
fault     = 0
```

The logged `BOUNDED REAL STARTUP RESULT: FAIL` is a proof-harness
false-negative: the 5V pass expression still expected the old fixed
pre-persistence trace entries 54..60. The root execution and clean next
boundary provide the required hardware proof.

## Phase 5W — TitleImage-path root 0x0022F08D

5W promotes only `0x0022F08D` at depth zero while retaining every previously
proven Phase-5 continuation, including native `NtWriteFile`.

The gate is explicitly state-aware. It does not require historical fixed trace
positions or a write on every boot. Instead, the new translated root has an
entry flag that is required by the runtime PASS condition.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5W.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_22f08d_xdk\main.cpp
build\phase5_subsystem_bringup\direct_22f08d_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_22f08d_xdk\phase5w-manifest.json
```

Build: `P5W-DIRECT22F08D-20261020-A`

Cookie: `P5W1 / 0x50355731`.

Link-time guard symbol: `phase5w_env_build_cookie`.


## Phase 5W hardware result

**PASS on real Xbox 360 hardware.**

The state-aware path behaved as intended. Persistent `TitleMeta.xbx` was
recognized at EOF 48, `TitleImage.xbx` was opened and queried at EOF 0, and
the promoted translated root executed:

```text
trace[58] = 0x0022F08D
```

It then reached:

```text
kind      = ICALL_SAFE
caller    = 0x0022F08D
target    = 0x80000147
esp       = 0x008BFBB0
saved_esp = 0x008BFBB8
trace     = 59
fault     = 0
```

Ordinal 327 is `XeLoadSection@4`, matching the observed 8-byte full frame.

Harness result: `PHASE 5W DIRECT22F08D RESULT: PASS`.

## Phase 5X — native XeLoadSection continuation

5X services ordinal 327 without rereading section bytes. The Phase-2E
environment has already copied and zero-filled every retail XBE section into
guest RAM before execution, so the bridge performs the missing kernel
bookkeeping:

```text
validate exact XBE section-table pointer
read 0x38-byte XBE section header
increment SectionReferenceCount
on first load, increment distinct shared head/tail page reference counters
return STATUS_SUCCESS
restore stdcall ESP and resume retail execution
```

Unexpected pointers, malformed section metadata, invalid reference counts, and
guest-memory faults remain fenced.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5X.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\xeloadsection_native_xdk\main.cpp
build\phase5_subsystem_bringup\xeloadsection_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\xeloadsection_native_xdk\phase5x-manifest.json
```

Build: `P5X-XELOADSECTION327-NATIVE-20261020-A`

Cookie: `P5X1 / 0x50355831`.

Link-time guard symbol: `phase5x_env_build_cookie`.


## Phase 5X hardware result

**PASS on real Xbox 360 hardware.**

The native ordinal-327 bridge received an exact XBE section-table entry for
section 11, `$$XTIMAGE`:

```text
section    = 0x000105D8
index      = 11
name       = $$XTIMAGE
VA         = 0x00874D40
virtual    = 10240 bytes
file       = 0x0030E000
file size  = 10240 bytes
references = 0 -> 1
```

The continuation completed and retail reached:

```text
caller = 0x0022F08D
target = 0x0022F0CC
esp    = 0x008BFBB8
trace  = 59
fault  = 0
```

Harness result: `PHASE 5X XELOADSECTION327 NATIVE RESULT: PASS`.

## Phase 5Y — direct root 0x0022F0CC

5Y preserves the native `XeLoadSection` implementation and promotes only the
new hardware-observed direct target `0x0022F0CC` at depth zero. The emitter
requires the address to be an exact frozen function start with a generated
body; otherwise preparation stops instead of guessing a split/mid-function
continuation.

The runtime proof remains state-aware and uses explicit entry instrumentation
for `0x0022F0CC`.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5Y.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_22f0cc_xdk\main.cpp
build\phase5_subsystem_bringup\direct_22f0cc_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_22f0cc_xdk\phase5y-manifest.json
```

Build: `P5Y-DIRECT22F0CC-20261020-A`

Cookie: `P5Y1 / 0x50355931`.

Link-time guard symbol: `phase5y_env_build_cookie`.


## Phase 5Y hardware result

**Root execution proven; full harness result intentionally remains FAIL because
the next NtWriteFile ABI shape is not yet classified.**

The proven `XeLoadSection` bridge again services section 11
`$$XTIMAGE`, then the promoted root executes:

```text
trace[58] = 0x0022F08D
trace[59] = 0x0022F0CC
```

Root `0x0022F0CC` reaches ordinal 236 with:

```text
esp       = 0x008BFBA0
saved_esp = 0x008BFBC0
delta     = 32 bytes
fault     = 0
```

The prior native TitleMeta write established a 36-byte full frame for
`NtWriteFile`. The 5Y bridge therefore fences this new 32-byte form rather
than guessing its layout.

## Phase 5Z — compact NtWriteFile frame capture

5Z is an ABI-evidence phase. It keeps the proven 36-byte native
`NtWriteFile` continuation intact. When caller `0x0022F0CC` reaches the
observed 32-byte form, the bridge logs the raw guest stack at offsets
`+0x00` through `+0x28` and performs no native I/O.

This distinguishes whether the second call is a compact argument layout,
tail/wrapper stack shape, or a saved-ESP translation issue before any
TitleImage payload is written.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5Z.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntwritefile_compact_capture_xdk\main.cpp
build\phase5_subsystem_bringup\ntwritefile_compact_capture_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntwritefile_compact_capture_xdk\phase5z-manifest.json
```

Build: `P5Z-NTWRITEFILE236-COMPACT-CAPTURE-20261020-A`

Cookie: `P5Z1 / 0x50355A31`.

Link-time guard symbol: `phase5z_env_build_cookie`.


## Phase 5Z hardware result

**PASS on real Xbox 360 hardware.**

The compact capture resolved the second `NtWriteFile` call shape. Caller
`0x0022F0CC` supplies the normal eight arguments; the captured raw stack is:

```text
+00 = 00000000   synthetic return
+04 = 48000002   file handle
+08 = 00000000   event
+0C = 00000000   APC routine
+10 = 00000000   APC context
+14 = 008BFC1C   IO_STATUS_BLOCK
+18 = 00874D40   buffer
+1C = 00002800   length
+20 = 00000000   ByteOffset
```

`0x00874D40 / 0x2800` is exactly the retail `$$XTIMAGE` section. The
kernel ABI is therefore not actually shortened; only this translated call
site's `savedEsp` is one dword short.

Harness result:
`PHASE 5Z NTWRITEFILE236 COMPACT CAPTURE RESULT: PASS`.

## Phase 5AA — native TitleImage NtWriteFile continuation

5AA keeps the already-proven standard `NtWriteFile` path intact and adds a
strict caller-specific correction for `0x0022F0CC`.

The correction is allowed only when the observed frame still matches the
5Z evidence:

```text
caller     = 0x0022F0CC
buffer     = 0x00874D40
length     = 0x2800
ByteOffset = NULL
event/APC/context = NULL
```

For that exact case, `resumeEsp = savedEsp + 4` restores the true 36-byte
stdcall frame end. The bridge then performs a real native `WriteFile`,
updates the guest `IO_STATUS_BLOCK`, and continues execution.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AA.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntwritefile_xtimage_native_xdk\main.cpp
build\phase5_subsystem_bringup\ntwritefile_xtimage_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntwritefile_xtimage_native_xdk\phase5aa-manifest.json
```

Build: `P5AA-NTWRITEFILE236-XTIMAGE-NATIVE-20261020-A`

Cookie: `P5AA / 0x50354141`.

Link-time guard symbol: `phase5aa_env_build_cookie`.


## Phase 5AA hardware result

**PASS on real Xbox 360 hardware.**

The Phase-5Z stack capture was classified correctly. Caller
`0x0022F0CC` still supplies the full standard NtWriteFile argument set; only
its translated continuation ESP is one dword short. 5AA validated the exact
captured frame, repaired `savedEsp` from `0x008BFBC0` to
`0x008BFBC4`, and performed the native write:

```text
buffer    = 0x00874D40   ($$XTIMAGE)
length    = 0x2800       (10,240 bytes)
status    = 0
bytes     = 10,240
requested = 10,240
```

Retail then reached:

```text
caller = 0x0022F0CC
target = 0x0022F0AE
esp    = 0x008BFBBC
trace  = 60
fault  = 0
```

Harness result: `PHASE 5AA NTWRITEFILE236 XTIMAGE NATIVE RESULT: PASS`.

## Phase 5AB — direct root 0x0022F0AE

5AB promotes only `0x0022F0AE` at depth zero and keeps every previously
proven native storage/runtime continuation armed.

Because 5AA persisted the complete `TitleImage.xbx` payload, subsequent boots
may take a shorter path. The 5AB PASS condition therefore does not require
`XeLoadSection` or the TitleImage write to repeat. The new root has explicit
entry instrumentation and remains the authoritative proof target.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AB.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_22f0ae_xdk\main.cpp
build\phase5_subsystem_bringup\direct_22f0ae_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_22f0ae_xdk\phase5ab-manifest.json
```

Build: `P5AB-DIRECT22F0AE-20261020-A`

Cookie: `P5AB / 0x50354142`.

Link-time guard symbol: `phase5ab_env_build_cookie`.


## Phase 5AB hardware result

5AB confirmed that persistent title-image state changes the retail branch.
`TitleImage.xbx` is now 10,240 bytes, so retail proceeds to
`SaveImage.xbx`, finds it empty, loads XBE section 12 `$$XSIMAGE`, and
prepares a 4,096-byte write from guest VA `0x00877540`.

The call comes from the same translated caller `0x0022F0CC` and has the
same one-dword-short saved-ESP behavior previously proven for `$$XTIMAGE`.
5AB intentionally fences it because its repair allowlist still contained only
the first image payload. No native write is issued and `fault=0`.

## Phase 5AC — TitleImage + SaveImage write allowlist

5AC replaces the single-payload repair guard with a narrow two-entry
hardware-proven allowlist:

```text
section 11 $$XTIMAGE
  file   = TitleImage.xbx
  VA     = 0x00874D40
  length = 0x2800

section 12 $$XSIMAGE
  file   = SaveImage.xbx
  VA     = 0x00877540
  length = 0x1000
```

The repair is accepted only after the corresponding successful
`XeLoadSection` and only when the tagged handle path ends in the expected
filename, all synchronous fields are null, and `ByteOffset=NULL`.
The continuation still uses `resumeEsp=savedEsp+4`. Root
`0x0022F0AE` remains packed as the next execution proof target.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AC.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\ntwritefile_image_sections_xdk\main.cpp
build\phase5_subsystem_bringup\ntwritefile_image_sections_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\ntwritefile_image_sections_xdk\phase5ac-manifest.json
```

Build:
`P5AC-NTWRITEFILE236-IMAGESECTIONS-NATIVE-20261020-A`

Cookie: `P5AC / 0x50354143`.

Link-time guard symbol: `phase5ac_env_build_cookie`.


## Phase 5AC hardware result

**PASS on real Xbox 360 hardware.**

The SaveImage branch matched the new two-entry image-section write guard.
Retail loaded section 12 `$$XSIMAGE` and wrote the complete 4,096-byte
payload to `SaveImage.xbx`:

```text
section = 0x00010610
index   = 12
VA      = 0x00877540
length  = 0x1000
file    = SaveImage.xbx
status  = 0
bytes   = 4096 / 4096
```

The repaired continuation restored `ESP` from `0x008BFBC0` to
`0x008BFBC4`. Retail then entered translated root `0x0022F0AE` and reached
kernel target `0x80000148` with `fault=0`.

Ordinal 328 is `XeUnloadSection`.

Harness result:
`PHASE 5AC XSIMAGE SAVEIMAGE NATIVE RESULT: PASS`.

## Phase 5AD — XeUnloadSection continuation

5AD services ordinal 328 with the hardware-observed one-argument / 8-byte
frame. The bridge validates the section pointer against the XBE section table,
decrements `SectionReferenceCount`, and on a 1->0 transition decrements the
distinct shared head/tail page reference counters.

The guest section payload is intentionally left resident. Phase-2E already
loads every XBE section into guest RAM and the maintained `XeLoadSection`
bridge models reference bookkeeping rather than physical page loading, so the
inverse bridge follows the same resident-byte policy.

The gate is persistent-state aware: now that both image files have been
written, future retail boots may skip the load/write/unload sequence entirely.
The service stays armed if encountered, while PASS is based on reaching the
next previously-unhandled runtime boundary.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AD.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\xeunloadsection_native_xdk\main.cpp
build\phase5_subsystem_bringup\xeunloadsection_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\xeunloadsection_native_xdk\phase5ad-manifest.json
```

Build: `P5AD-XEUNLOADSECTION328-NATIVE-20261020-A`

Cookie: `P5AD / 0x50354144`.

Link-time guard symbol: `phase5ad_env_build_cookie`.


## Phase 5AD hardware result

**PASS on real Xbox 360 hardware.**

The persistent title-state branch is now confirmed. Retail sees:

```text
TitleMeta.xbx  = 48 bytes
TitleImage.xbx = 10240 bytes
SaveImage.xbx  = 4096 bytes
```

That causes the image load/write path to be skipped. The 5AD
`XeUnloadSection` bridge was therefore not called in this run, so it remains
implemented and armed but not yet hardware-proven.

After closing the title handles and creating `U:`, retail reaches:

```text
caller = 0x00239C23
target = 0x0022A604
esp    = 0x008BFF00
trace  = 62
fault  = 0
```

Harness result:
`PHASE 5AD XEUNLOADSECTION328 NATIVE RESULT: PASS`.

## Phase 5AE — direct root 0x0022A604

5AE promotes only `0x0022A604` at depth zero. It retains every prior native
storage/image-section continuation, including the ordinal-328
`XeUnloadSection` bridge, but does not require skipped persistent-state work
to repeat.

The gate validates that `0x0022A604` is an exact generated function start,
adds explicit root-entry instrumentation, and accepts only a later
nonfaulting runtime boundary as proof.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AE.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_22a604_xdk\main.cpp
build\phase5_subsystem_bringup\direct_22a604_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_22a604_xdk\phase5ae-manifest.json
```

Build: `P5AE-DIRECT22A604-20261020-A`

Cookie: `P5AE / 0x50354145`.

Link-time guard symbol: `phase5ae_env_build_cookie`.


## Phase 5AE hardware result

**PASS on real Xbox 360 hardware.**

The persistent title-state branch remains stable and exact translated root
`0x0022A604` executed. It immediately reached:

```text
caller    = 0x0022A604
target    = 0x0022A3B9
esp       = 0x008BFDCC
saved_esp = 0x008BFDCC
trace     = 63
fault     = 0
```

Harness result:
`PHASE 5AE DIRECT22A604 RESULT: PASS`.

## Phase 5AF — direct root 0x0022A3B9

5AF promotes only the newly observed frontier `0x0022A3B9` at depth zero and
retains `0x0022A604` plus every previously proven native continuation.

The preparation gate validates `0x0022A3B9` against the frozen function
inventory. If it is an exact generated function start, it is packed and given
explicit root-entry instrumentation. If it falls inside another function, the
gate fails with the containing range instead of silently promoting a
mid-function address.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AF.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\direct_22a3b9_xdk\main.cpp
build\phase5_subsystem_bringup\direct_22a3b9_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\direct_22a3b9_xdk\phase5af-manifest.json
```

Build: `P5AF-DIRECT22A3B9-20261020-A`

Cookie: `P5AF / 0x50354146`.

Link-time guard symbol: `phase5af_env_build_cookie`.


## Phase 5AF hardware result

Root `0x0022A3B9` executed on real Xbox 360 hardware, but the overall phase
stopped at a newly discovered storage request:

```text
NtOpenFile
  caller  = 0x0022A3B9
  path    = \Device\Harddisk0\partition0
  access  = 0xC0100000
  share   = 3
  options = 0x10
  fault   = 0
```

The maintained storage bridge had no Partition0 mapping and correctly fenced
the request before native I/O. Therefore the root itself is hardware-proven,
while the final Phase-5AF harness result is FAIL.

## Phase 5AG — Partition0 root mapping

5AG adds only the hardware-observed exact root mapping:

```text
\Device\Harddisk0\partition0 -> game:\merc360-partition0
```

The native target is an isolated sandbox directory created on demand. Because
the request is a root-directory open, virtual-root opens force
`FILE_FLAG_BACKUP_SEMANTICS`. Child paths below Partition0 are still fenced
until retail actually requests one.

The PASS gate requires `s_phase5agPartition0OpenSuccessCount > 0` before a
later boundary can count, so prior Partition1 activity cannot mask a broken
Partition0 continuation.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AG.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\partition0_native_xdk\main.cpp
build\phase5_subsystem_bringup\partition0_native_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\partition0_native_xdk\phase5ag-manifest.json
```

Build: `P5AG-PARTITION0-NATIVE-20261020-A`

Cookie: `P5AG / 0x50354147`.

Link-time guard symbol: `phase5ag_env_build_cookie`.


## Phase 5AG hardware result

The exact Partition0 root continuation itself **passed on real Xbox 360
hardware**:

```text
xbox   = \Device\Harddisk0\partition0
native = game:\merc360-partition0
status = 0
token  = 0x48000001
```

Retail next requested a 512-byte read at offset `0x800`. Because the current
Partition0 model is intentionally an isolated directory rather than a guessed
raw-disk image, the native read returned `STATUS_UNSUCCESSFUL`. Retail then
closed the handle and called ordinal 301 from translated function
`0x0022B1A6`.

That exposed an old harness limitation: `RtlNtStatusToDosError` was guarded
as a one-shot service, even though it is naturally repeatable. The first
startup `STATUS_SUCCESS` conversion had already consumed the gate. Thus
Phase 5AG's final harness label is FAIL even though the new Partition0 open is
hardware-proven.

## Phase 5AH — repeatable ordinal 301

5AH removes the `!s_phase4cNtStatusMapped` one-shot condition and services
every observed `RtlNtStatusToDosError` call using the production
`src/kernel/kernel_rtl.c` mapping table.

The key newly observed mapping is:

```text
0xC0000001 STATUS_UNSUCCESSFUL -> 31 ERROR_GEN_FAILURE
```

The hardware gate requires at least two ordinal-301 calls and requires the
latest input/output to match that pair before accepting the next boundary.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AH.ps1"
```

Generated sources:

```text
build\phase5_subsystem_bringup\rtlstatus301_repeatable_xdk\main.cpp
build\phase5_subsystem_bringup\rtlstatus301_repeatable_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\rtlstatus301_repeatable_xdk\phase5ah-manifest.json
```

Build: `P5AH-RTLSTATUS301-REPEATABLE-20261020-A`

Cookie: `P5AH / 0x50354148`.

Link-time guard symbol: `phase5ah_env_build_cookie`.

## Phase 5AS hardware result / Phase 5AT capture gate

**5AS PASS on real Xbox 360 hardware.**

The persistent cache path remained stable: Partition0 backing reloaded, the
0x800 sector rewrite remained unchanged, Partition5 mounted as `Z:`, and the
second ordinal-24 EEPROM query succeeded. The promoted `0x0022BBC8` closure
then advanced through:

```text
0022BBC8 -> 00237830 -> 0022B74E -> 0022B7B2
```

The next clean boundary is:

```text
ICALL_SAFE caller=0022B7B2 target=800000CB fault=0
```

`0x800000CB` is original-Xbox kernel ordinal 203,
`NtOpenSymbolicLinkObject`.

### Phase 5AT — NtOpenSymbolicLinkObject capture

5AT captures the exact live 12-byte translated call frame (synthetic return +
two stdcall arguments), decodes the guest `OBJECT_ATTRIBUTES` and
`ANSI_STRING` path, and stops without inventing native symbolic-link-object
semantics.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase5_subsystem_bringup\Prepare-Phase5AT.ps1"
```

Generated sources remain in the active shared Phase-5 XDK package directory:

```text
build\phase5_subsystem_bringup\post_persist_closure_xdk\main.cpp
build\phase5_subsystem_bringup\post_persist_closure_xdk\phase5_env.cpp
build\phase5_subsystem_bringup\post_persist_closure_xdk\phase5at-manifest.json
```

Build: `P5AT-NTOPENSYMLINK203-CAPTURE-20261020-A`

Cookie: `P5AT / 0x50354154`.

