[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$stage3Root = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$generatedRoot = Join-Path $stage3Root "runtime\gen"
$functionsPath = Join-Path $stage3Root "analysis\disasm\functions.json"
$entryReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-startup-closure.json"
$threadReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-thread-routine.json"
$baseEmitter = Join-Path $phaseRoot "..\phase4c_native_startup\emit_phase4c_startup_slice.py"
$emitter = Join-Path $phaseRoot "emit_phase5v_direct_22bda5.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\direct_22bda5_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 5V input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5V] POST-WRITE DIRECT ROOT 0x0022BDA5"
Write-Host "[Phase5V] Phase 5U hardware PASS wrote 48/48 TitleMeta.xbx bytes, closed the handle, and reached 0x0022BDA5 with fault=0."
Write-Host "[Phase5V] Promoting exactly root 0x0022BDA5 at depth 0; deeper callees remain fenced."
Write-Host "[Phase5V] NtWriteFile remains native and armed, but a write is not required on every boot because TitleMeta.xbx is persistent state."
Write-Host "[Phase5V] Preparation fails if 0x0022BDA5 is a split/mid-function target or lacks a frozen generated body."
Write-Host "[Phase5V] Main/env link-time cookie symbol is phase5v_env_build_cookie / P5V1."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5v-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

# PowerShell 5 treats native stderr as an ErrorRecord when ErrorActionPreference
# is Stop. Let Python complete so we can inspect its exit code + emitted
# manifest, then restore strict wrapper behavior.
$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir 2>&1 | Tee-Object -FilePath $emitLog
    $emitExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($emitExit -ne 0) {
    $failedManifest = Join-Path $outDir "phase5v-manifest.json"
    if (Test-Path -LiteralPath $failedManifest) {
        try {
            $failedJson = Get-Content -LiteralPath $failedManifest -Raw | ConvertFrom-Json
            if ($failedJson.unknown_direct_helpers) {
                Write-Host ""
                Write-Host "[Phase5V] Remaining unresolved helper dependencies:"
                $failedJson.unknown_direct_helpers.PSObject.Properties | ForEach-Object {
                    Write-Host ("[Phase5V]   {0}: {1}" -f $_.Name, ($_.Value -join ", "))
                }
                Write-Host ""
            }
        } catch {
            Write-Host "[Phase5V] Could not decode failure manifest: $($_.Exception.Message)"
        }
    }
    throw "Phase 5V direct 0x0022BDA5 package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5v-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P5V-DIRECT22BDA5-20261020-A",
    "PASS: ordinal 149 KeSetTimer continuation armed",
    "PASS: bounded direct closure rooted at 0022D980 is packed for translated execution",
    "PASS: hardware-observed direct root 00238C00 is packed for translated execution",
    "PASS: maintained recomp_crt_memmove cdecl support armed",
    "PASS: ordinal 184 NtAllocateVirtualMemory reserved/commit page-state continuation armed",
    "PASS: ordinal 291 RtlInitializeCriticalSection continuation armed",
    "PASS: hardware-observed direct root 0022D431 is packed for translated execution",
    "PASS: hardware-observed direct root 0022CA2B is packed for translated execution",
    "PASS: hardware-observed direct root 0022C8EA is packed for translated execution",
    "PASS: hardware-observed direct root 0022CEEE is packed for translated execution",
    "PASS: Phase 5V ordinal 202 NtOpenFile native continuation armed",
    "NtOpenFile LIVE FRAME",
    "NtOpenFile OBJECT:",
    "NtOpenFile NATIVE:",
    "PASS: Phase 5V NtOpenFile native continuation",
    "PASS: Phase 5V ordinal 218 NtQueryVolumeInformationFile native continuation armed",
    "NtQueryVolumeInformationFile LIVE FRAME",
    "PASS: Phase 5V NtQueryVolumeInformationFile native continuation",
    "PASS: Phase 5V ordinal 187 NtClose native continuation armed",
    "NtClose LIVE FRAME",
    "PASS: Phase 5V NtClose native continuation",
    "PASS: Phase 5V ordinal 67 IoCreateSymbolicLink native continuation armed",
    "IoCreateSymbolicLink LIVE FRAME",
    "IoCreateSymbolicLink OBJECTS:",
    "PASS: Phase 5V IoCreateSymbolicLink native continuation",
    "PASS: Phase 5V ordinal 69 IoDeleteSymbolicLink native continuation armed",
    "IoDeleteSymbolicLink LIVE FRAME",
    "PASS: Phase 5V IoDeleteSymbolicLink native continuation",
    "PASS: hardware-observed post-mount direct root 0022C1C0 is packed for translated execution",
    "PASS: hardware-observed next retail direct root 002370B8 is packed for translated execution",
    "PASS: hardware-observed next retail direct root 0022BE8C is packed for translated execution",
    "PASS: Phase 5V ordinal 190 NtCreateFile native continuation armed",
    "NtCreateFile LIVE FRAME",
    "NtCreateFile OBJECT:",
    "NtCreateFile NATIVE:",
    "PASS: Phase 5V NtCreateFile native continuation",
    "PASS: Phase 5V ordinal 219 NtReadFile synchronous continuation armed",
    "NtReadFile LIVE FRAME",
    "PASS: Phase 5V NtReadFile native continuation",
    "PASS: Phase 5V ordinal 289 RtlInitAnsiString continuation armed",
    "RtlInitAnsiString LIVE FRAME",
    "PASS: Phase 5V RtlInitAnsiString continuation",
    "PASS: Phase 5V ordinal 279 RtlEqualString continuation armed",
    "RtlEqualString LIVE FRAME",
    "PASS: Phase 5V RtlEqualString continuation",
    "PASS: hardware-observed post-storage direct root 0022F026 is packed for translated execution",
    "PASS: hardware-observed root 0022B178 uses maintained manual SetLastError execution",
    "PASS: Phase 5V maintained SetLastError value=",
    "PASS: Phase 5V ordinal 211 NtQueryInformationFile class-34 native continuation armed",
    "PASS: hardware-observed post-TitleMeta direct root 00239B78 is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DDDD is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DD7B is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DDA0 is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023DD56 is packed for translated execution",
    "PASS: hardware-observed next post-TitleMeta direct root 0023F8CB is packed for translated execution",
    "PASS: hardware-observed post-write direct root 0022BDA5 is packed for translated execution",
    "s_phase5vRoot22BDA5Entered = 1;",
    "sub_00239B78",
    "sub_0023DDDD",
    "sub_0023DD7B",
    "sub_0023DDA0",
    "sub_0023DD56",
    "sub_0023F8CB",
    "NtWriteFile LIVE FRAME:",
    "PASS: Phase 5V NtWriteFile native continuation",
    "WriteFile(",
    "PASS: Phase 5V ordinal 236 NtWriteFile synchronous continuation armed",
    "NtQueryInformationFile LIVE FRAME:",
    "NtQueryInformationFile NATIVE:",
    "PASS: Phase 5V NtQueryInformationFile class 34 native continuation",
    "GetFileAttributesExA",
    "s_phase5bHandlePaths",
    "FILE_INFORMATION",
    "STORAGE_IO",
    "game:\\merc360-partition1",
    "RtlInitializeCriticalSection LIVE FRAME",
    "PASS: ordinal 291 RtlInitializeCriticalSection matched maintained serialized-guest semantics",
    "NtAllocateVirtualMemory LIVE FRAME",
    "PASS: ordinal 184 NtAllocateVirtualMemory matched reserved/commit guest-VM semantics",
    "CRT memmove LIVE FRAME",
    "PASS: recomp_crt_memmove matched maintained cdecl semantics",
    "PASS: Phase 5V main/env build cookie matches",
    "PHASE 5V DIRECT22BDA5 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 5V main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5V RETAIL ENVIRONMENT PREP START",
    "PHASE 5V EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5V EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5v_env_build_cookie",
    "50355631",
    "PHASE 5V RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 5V phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 5V manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.phase -ne "5V" -or $manifestJson.build_tag -ne "P5V-DIRECT22BDA5-20261020-A") {
    throw "Phase 5V manifest identity mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_7 -ne "0x00238C00") {
    throw "Phase 5V manifest 38C00 root mismatch"
}
if ($manifestJson.continued_kernel_call_184.target -ne "0x800000B8" -or
    [int]$manifestJson.continued_kernel_call_184.arg_bytes -ne 20 -or
    [int]$manifestJson.continued_kernel_call_184.frame_bytes -ne 24) {
    throw "Phase 5V manifest ordinal-184 ABI mismatch"
}
if ($manifestJson.continued_kernel_call_291.target -ne "0x80000123" -or
    [int]$manifestJson.continued_kernel_call_291.arg_bytes -ne 4 -or
    [int]$manifestJson.continued_kernel_call_291.frame_bytes -ne 8) {
    throw "Phase 5V manifest ordinal-291 ABI mismatch"
}
if ($manifestJson.phase5_storage_boundary.target -ne "0x800000CA" -or
    [int]$manifestJson.phase5_storage_boundary.ordinal -ne 202 -or
    [int]$manifestJson.phase5_storage_boundary.arg_bytes -ne 24 -or
    [int]$manifestJson.phase5_storage_boundary.frame_bytes -ne 28 -or
    $manifestJson.phase5_storage_boundary.mode -ne "native-continuation") {
    throw "Phase 5V NtOpenFile native contract mismatch"
}
if ($manifestJson.phase5_storage_boundary.native_mapping -notlike "*Harddisk0*partition1*merc360-partition1*") {
    throw "Phase 5V Partition1 native mapping mismatch"
}
if ($manifestJson.phase5_volume_query.target -ne "0x800000DA" -or
    [int]$manifestJson.phase5_volume_query.ordinal -ne 218 -or
    [int]$manifestJson.phase5_volume_query.arg_bytes -ne 20 -or
    [int]$manifestJson.phase5_volume_query.frame_bytes -ne 24 -or
    [int]$manifestJson.phase5_volume_query.supported_class -ne 3) {
    throw "Phase 5V volume-query contract mismatch"
}
if ($manifestJson.phase5_handle_close.target -ne "0x800000BB" -or
    [int]$manifestJson.phase5_handle_close.ordinal -ne 187 -or
    [int]$manifestJson.phase5_handle_close.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_handle_close.frame_bytes -ne 8) {
    throw "Phase 5V NtClose contract mismatch"
}
if ($manifestJson.phase5_symbolic_link.target -ne "0x80000043" -or
    [int]$manifestJson.phase5_symbolic_link.ordinal -ne 67 -or
    [int]$manifestJson.phase5_symbolic_link.arg_bytes -ne 8 -or
    [int]$manifestJson.phase5_symbolic_link.frame_bytes -ne 12) {
    throw "Phase 5V IoCreateSymbolicLink contract mismatch"
}
if ($manifestJson.phase5_symbolic_link_delete.target -ne "0x80000045" -or
    [int]$manifestJson.phase5_symbolic_link_delete.ordinal -ne 69 -or
    [int]$manifestJson.phase5_symbolic_link_delete.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_symbolic_link_delete.frame_bytes -ne 8) {
    throw "Phase 5V IoDeleteSymbolicLink contract mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_8 -ne "0x0022D431") {
    throw "Phase 5V retained D431 root mismatch"
}
if ($manifestJson.promoted_closure_8_members.Count -ne 1 -or
    $manifestJson.promoted_closure_8_members[0] -ne "0x0022D431") {
    throw "Phase 5V retained D431 member set must be exactly 0x0022D431"
}
if ($manifestJson.promoted_direct_frontier_target_9 -ne "0x0022CA2B") {
    throw "Phase 5V retained CA2B root mismatch"
}
if ($manifestJson.promoted_closure_9_members.Count -ne 1 -or
    $manifestJson.promoted_closure_9_members[0] -ne "0x0022CA2B") {
    throw "Phase 5V retained CA2B member set must be exactly 0x0022CA2B"
}
if ($manifestJson.promoted_direct_frontier_target_10 -ne "0x0022C8EA") {
    throw "Phase 5V retained C8EA root mismatch"
}
if ($manifestJson.promoted_closure_10_members.Count -ne 1 -or
    $manifestJson.promoted_closure_10_members[0] -ne "0x0022C8EA") {
    throw "Phase 5V retained C8EA member set must be exactly 0x0022C8EA"
}
if ($manifestJson.promoted_direct_frontier_target_11 -ne "0x0022CEEE") {
    throw "Phase 5V retained CEEE root mismatch"
}
if ($manifestJson.promoted_closure_11_members.Count -ne 1 -or
    $manifestJson.promoted_closure_11_members[0] -ne "0x0022CEEE") {
    throw "Phase 5V retained CEEE member set must be exactly 0x0022CEEE"
}
if ($manifestJson.promoted_direct_frontier_target_12 -ne "0x0022C1C0") {
    throw "Phase 5V retained C1C0 root mismatch"
}
if ($manifestJson.promoted_closure_12_members.Count -ne 1 -or
    $manifestJson.promoted_closure_12_members[0] -ne "0x0022C1C0") {
    throw "Phase 5V retained C1C0 member set must be exactly 0x0022C1C0"
}
if ($manifestJson.promoted_direct_frontier_target_13 -ne "0x002370B8") {
    throw "Phase 5V retained 370B8 root mismatch"
}
if ($manifestJson.promoted_closure_13_members.Count -ne 1 -or
    $manifestJson.promoted_closure_13_members[0] -ne "0x002370B8") {
    throw "Phase 5V retained 370B8 member set must be exactly 0x002370B8"
}
if ($manifestJson.promoted_direct_frontier_target_14 -ne "0x0022BE8C") {
    throw "Phase 5V retained BE8C root mismatch"
}
if ($manifestJson.promoted_closure_14_members.Count -ne 1 -or
    $manifestJson.promoted_closure_14_members[0] -ne "0x0022BE8C") {
    throw "Phase 5V retained BE8C member set must be exactly 0x0022BE8C"
}
if ($manifestJson.promoted_direct_frontier_target_15 -ne "0x0022F026") {
    throw "Phase 5V retained F026 root mismatch"
}
if ($manifestJson.promoted_closure_15_members.Count -ne 1 -or
    $manifestJson.promoted_closure_15_members[0] -ne "0x0022F026") {
    throw "Phase 5V retained F026 member set must be exactly 0x0022F026"
}
if ($manifestJson.promoted_direct_frontier_target_16 -ne "0x0022B178") {
    throw "Phase 5V manifest B178 root mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_16_mode -ne "manual-maintained") {
    throw "Phase 5V B178 mode must be manual-maintained"
}
if ($manifestJson.manual_maintained_root_16.address -ne "0x0022B178" -or
    $manifestJson.manual_maintained_root_16.name -ne "sub_0022B178" -or
    $manifestJson.manual_maintained_root_16.semantic_name -ne "SetLastError" -or
    $manifestJson.manual_maintained_root_16.production_source -ne "ports/mercenaries/src/recomp_manual.c") {
    throw "Phase 5V maintained B178 contract mismatch"
}
if ($manifestJson.promoted_closure_members.Count -ne 1 -or
    $manifestJson.promoted_closure_members[0] -ne "0x0022BDA5") {
    throw "Phase 5V promoted member set must be exactly 0x0022BDA5"
}
if ($manifestJson.promoted_direct_frontier_target_17 -ne "0x00239B78") {
    throw "Phase 5V retained target-17 address mismatch"
}
if ($manifestJson.promoted_closure_17_members.Count -ne 1 -or
    $manifestJson.promoted_closure_17_members[0] -ne "0x00239B78") {
    throw "Phase 5V retained target-17 member set must be exactly 0x00239B78"
}
if ($manifestJson.promoted_direct_frontier_target_18 -ne "0x0023DDDD") {
    throw "Phase 5V retained target-18 address mismatch"
}
if ($manifestJson.promoted_closure_18_members.Count -ne 1 -or
    $manifestJson.promoted_closure_18_members[0] -ne "0x0023DDDD") {
    throw "Phase 5V retained target-18 member set must be exactly 0x0023DDDD"
}
if ($manifestJson.promoted_direct_frontier_target_19 -ne "0x0023DD7B") {
    throw "Phase 5V retained target-19 address mismatch"
}
if ($manifestJson.promoted_closure_19_members.Count -ne 1 -or
    $manifestJson.promoted_closure_19_members[0] -ne "0x0023DD7B") {
    throw "Phase 5V retained target-19 member set must be exactly 0x0023DD7B"
}
if ($manifestJson.promoted_direct_frontier_target_20 -ne "0x0023DDA0") {
    throw "Phase 5V retained target-20 address mismatch"
}
if ($manifestJson.promoted_closure_20_members.Count -ne 1 -or
    $manifestJson.promoted_closure_20_members[0] -ne "0x0023DDA0") {
    throw "Phase 5V retained target-20 member set must be exactly 0x0023DDA0"
}
if ($manifestJson.promoted_direct_frontier_target_21 -ne "0x0023DD56") {
    throw "Phase 5V retained target-21 address mismatch"
}
if ($manifestJson.promoted_closure_21_members.Count -ne 1 -or
    $manifestJson.promoted_closure_21_members[0] -ne "0x0023DD56") {
    throw "Phase 5V retained target-21 member set must be exactly 0x0023DD56"
}
if ($manifestJson.promoted_direct_frontier_target_22 -ne "0x0023F8CB") {
    throw "Phase 5V retained target-22 address mismatch"
}
if ($manifestJson.promoted_closure_22_members.Count -ne 1 -or
    $manifestJson.promoted_closure_22_members[0] -ne "0x0023F8CB") {
    throw "Phase 5V retained target-22 member set must be exactly 0x0023F8CB"
}
if ($manifestJson.promoted_direct_frontier_target_23 -ne "0x0022BDA5") {
    throw "Phase 5V target-23 address mismatch"
}
if ($manifestJson.promoted_closure_23_members.Count -ne 1 -or
    $manifestJson.promoted_closure_23_members[0] -ne "0x0022BDA5") {
    throw "Phase 5V target-23 member set must be exactly 0x0022BDA5"
}
if ($manifestJson.phase5_nt_query_information_file.target -ne "0x800000D3" -or
    [int]$manifestJson.phase5_nt_query_information_file.ordinal -ne 211 -or
    [int]$manifestJson.phase5_nt_query_information_file.arg_bytes -ne 20 -or
    [int]$manifestJson.phase5_nt_query_information_file.frame_bytes -ne 24 -or
    $manifestJson.phase5_nt_query_information_file.mode -ne "native-class34-continuation" -or
    [int]$manifestJson.phase5_nt_query_information_file.supported_class -ne 34 -or
    [int]$manifestJson.phase5_nt_query_information_file.required_length -ne 56) {
    throw "Phase 5V NtQueryInformationFile class-34 native contract mismatch"
}
if ($manifestJson.phase5_nt_create_file.target -ne "0x800000BE" -or
    [int]$manifestJson.phase5_nt_create_file.ordinal -ne 190 -or
    [int]$manifestJson.phase5_nt_create_file.arg_bytes -ne 36 -or
    [int]$manifestJson.phase5_nt_create_file.frame_bytes -ne 40 -or
    $manifestJson.phase5_nt_create_file.mode -ne "native-continuation") {
    throw "Phase 5V NtCreateFile contract mismatch"
}
if ($manifestJson.phase5_nt_read_file.target -ne "0x800000DB" -or
    [int]$manifestJson.phase5_nt_read_file.ordinal -ne 219 -or
    [int]$manifestJson.phase5_nt_read_file.arg_bytes -ne 32 -or
    [int]$manifestJson.phase5_nt_read_file.frame_bytes -ne 36 -or
    $manifestJson.phase5_nt_read_file.mode -ne "synchronous-native-continuation") {
    throw "Phase 5V NtReadFile contract mismatch"
}
if ($manifestJson.phase5_nt_write_file.target -ne "0x800000EC" -or
    [int]$manifestJson.phase5_nt_write_file.ordinal -ne 236 -or
    [int]$manifestJson.phase5_nt_write_file.arg_bytes -ne 32 -or
    [int]$manifestJson.phase5_nt_write_file.frame_bytes -ne 36 -or
    $manifestJson.phase5_nt_write_file.mode -ne "synchronous-native-continuation") {
    throw "Phase 5V NtWriteFile contract mismatch"
}
if ($manifestJson.phase5_rtl_init_ansi_string.target -ne "0x80000121" -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.ordinal -ne 289 -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.arg_bytes -ne 8 -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.frame_bytes -ne 12 -or
    $manifestJson.phase5_rtl_init_ansi_string.mode -ne "maintained-native-continuation") {
    throw "Phase 5V RtlInitAnsiString contract mismatch"
}
if ($manifestJson.phase5_rtl_equal_string.target -ne "0x80000117" -or
    [int]$manifestJson.phase5_rtl_equal_string.ordinal -ne 279 -or
    [int]$manifestJson.phase5_rtl_equal_string.arg_bytes -ne 12 -or
    [int]$manifestJson.phase5_rtl_equal_string.frame_bytes -ne 16 -or
    $manifestJson.phase5_rtl_equal_string.mode -ne "maintained-native-continuation") {
    throw "Phase 5V RtlEqualString contract mismatch"
}
if ($manifestJson.continued_kernel_call_184.page_allocator -notlike "*top of 64 MiB guest RAM downward*") {
    throw "Phase 5V manifest page-backed allocator policy mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 0) {
    throw "Phase 5V manifest safe-root depth mismatch"
}
if ($manifestJson.continued_support_helper_memmove.name -ne "recomp_crt_memmove") {
    throw "Phase 5V manifest CRT memmove helper mismatch"
}
if ([int]$manifestJson.continued_support_helper_memmove.arg_bytes -ne 12 -or
    [int]$manifestJson.continued_support_helper_memmove.callee_cleanup_bytes -ne 4) {
    throw "Phase 5V manifest CRT memmove ABI mismatch"
}
Write-Host ""
Write-Host "[Phase5V] READY"
Write-Host "[Phase5V] Phase 5U evidence locked: NtWriteFile wrote 48/48 bytes, NtClose succeeded, and retail reached 0x0022BDA5 with fault=0."
Write-Host "[Phase5V] New translated root: 0x0022BDA5"
Write-Host "[Phase5V] Promotion depth: 0; member set must be exactly one generated function."
Write-Host "[Phase5V] Native ordinal-236 NtWriteFile remains armed, but the proof is state-aware and does not require rewriting existing TitleMeta.xbx."
Write-Host "[Phase5V] Explicit root-entry instrumentation proves 0x0022BDA5 executed even if persistent metadata changes the preceding loop count."
Write-Host "[Phase5V] Deeper direct callees remain DIRECT_FRONTIER boundaries for hardware discovery."
Write-Host "[Phase5V] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase5V]   $main"
Write-Host "[Phase5V]   $env"
Write-Host "[Phase5V] Link-time guard: main requires phase5v_env_build_cookie from the matching generated environment source."
Write-Host "[Phase5V] The 5V cookie must be 0x50355631 (P5V1)."
Write-Host "[Phase5V] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase5V] Expected build tag: P5V-DIRECT22BDA5-20261020-A"
