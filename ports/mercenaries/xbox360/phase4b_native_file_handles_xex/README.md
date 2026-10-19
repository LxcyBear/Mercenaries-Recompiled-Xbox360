# Phase 4B-B — Native Xenon file/handle gate

**Status: hardware PASS; Phase 4B-B2 runtime verification active.**

Phase 4B-A/A2 is complete. The exact retail audit now reports 11 remaining
direct semantic host-backed import paths and 6 Phase-4B platform-bound paths.

This gate targets the nine-file/handle block before production runtime wiring:

- `NtCreateFile`
- `NtOpenFile`
- `NtReadFile`
- `NtWriteFile`
- `NtSetInformationFile`
- `NtQueryInformationFile`
- `NtQueryDirectoryFile`
- `NtQueryFullAttributesFile`
- `NtClose`

The other two remaining direct host-backed paths are expected to be the later
memory/protection slice.

## Hardware scope

Build marker:

```text
P4B-FILE-20261019-A
```

The XEX proves the Xenon/XDK primitives needed for the guest file semantics:

- create/overwrite a file under `game:\`;
- write and flush an exact payload;
- query file size and handle information;
- seek to absolute offsets;
- read back full and offset payloads;
- observe the current file position;
- truncate with `SetEndOfFile`;
- close and reopen an existing file;
- query path attributes;
- enumerate a directory with `FindFirstFileA` / `FindNextFileA`;
- verify missing-file failure/error semantics;
- close enumeration/file handles and clean up the temporary test objects.

This is a bounded platform proof. It does not execute retail translated code.

## Prepare

From the repository root:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4b_native_file_handles_xex\Prepare-Phase4B-B.ps1"
```

The preparation script requires the completed A2 baseline:

```text
imports=111
host_surface=11
platform_bound=6
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```

It writes the compile-ready XDK source to:

```text
build\phase4b_native_file_handles\main.cpp
```

Compile that source in the same known-good XDK diagnostic project used by the
previous hardware gates.

## Expected successful xbWatson tail

```text
[Merc360:P4B-FILE] PASS: CreateFileA CREATE_ALWAYS
[Merc360:P4B-FILE] PASS: WriteFile writes full payload
[Merc360:P4B-FILE] PASS: ReadFile round-trip payload
[Merc360:P4B-FILE] PASS: SetEndOfFile truncates file
[Merc360:P4B-FILE] PASS: CreateFileA OPEN_EXISTING
[Merc360:P4B-FILE] PASS: directory enumeration finds sample.bin
[Merc360:P4B-FILE] PASS: missing OPEN_EXISTING fails
[Merc360:P4B-FILE] PHASE 4B-B NATIVE FILE/HANDLE RESULT: PASS
```

After a hardware PASS, Phase 4B-B2 will place the proven file primitives
behind a shared platform boundary while preserving the existing Xbox guest
path translation, IO status, read-cache, directory-context, and bridge logic.


## Hardware result — October 19, 2026

Build `P4B-FILE-20261019-A` passed on real Xbox 360 hardware.

The xbWatson run passed every bounded storage check:

- test directory create/existing;
- `CreateFileA(CREATE_ALWAYS)`;
- full payload `WriteFile` + `FlushFileBuffers`;
- `GetFileSize` and `GetFileInformationByHandle`;
- begin/explicit seek and `FILE_CURRENT` position;
- full and explicit-offset `ReadFile`;
- `SetEndOfFile` truncate to 24 bytes;
- close/reopen with truncated size preserved;
- `GetFileAttributesA` regular-file identification;
- `FindFirstFileA` / directory enumeration / `FindClose`;
- missing `OPEN_EXISTING` returns a not-found error;
- file and directory cleanup.

Overall result:

```text
[Merc360:P4B-FILE] PHASE 4B-B NATIVE FILE/HANDLE RESULT: PASS
```

This proves the bounded XDK primitive set. It does not by itself prove the
full translated game's storage path.

## Phase 4B-B2 verification

The production file HLE now routes the nine retail file/handle import paths
through `src/platform/kernel_file_io.*` while preserving guest path
translation, handle-token ownership, IO status layout, read caching and
directory contexts.

Run:

```powershell
powershell -ExecutionPolicy Bypass -File ".\ports\mercenaries\xbox360\phase4b_native_file_handles_xex\Verify-Phase4B-B2.ps1"
```

The expected migration split is:

```text
host_surface=2
platform_bound=15
arg_missing=0
arg_mismatch=0
fallback_referenced=0
fallback_refs=0
```
