# Phase 4B-B — Native Xenon file/handle gate

**Status: hardware gate A ready.**

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
