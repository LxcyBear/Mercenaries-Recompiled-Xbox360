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
$emitter = Join-Path $phaseRoot "emit_phase5j_direct_f026.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\direct_f026_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 5J input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5J] POST-TITLE-STORAGE RETAIL HELPER CONTINUATION"
Write-Host "[Phase5J] Phase 5I hardware PASS built TDATA/UDATA title-id trees, mounted \\??\\T:, and reached DIRECT_FRONTIER 0x0022F026 with fault=0."
Write-Host "[Phase5J] Promoting only exact hardware-observed translated root 0x0022F026; deeper direct callees remain fenced."
Write-Host "[Phase5J] Preparation fails explicitly if F026 is a split/mid-function target or lacks a generated body."
Write-Host "[Phase5J] Complete native storage, D:/T: mount, NtCreateFile, and RTL string state remains active."
Write-Host "[Phase5J] Main/env build cookie is P5J1."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5j-emitter.log"
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
    $failedManifest = Join-Path $outDir "phase5j-manifest.json"
    if (Test-Path -LiteralPath $failedManifest) {
        try {
            $failedJson = Get-Content -LiteralPath $failedManifest -Raw | ConvertFrom-Json
            if ($failedJson.unknown_direct_helpers) {
                Write-Host ""
                Write-Host "[Phase5J] Remaining unresolved helper dependencies:"
                $failedJson.unknown_direct_helpers.PSObject.Properties | ForEach-Object {
                    Write-Host ("[Phase5J]   {0}: {1}" -f $_.Name, ($_.Value -join ", "))
                }
                Write-Host ""
            }
        } catch {
            Write-Host "[Phase5J] Could not decode failure manifest: $($_.Exception.Message)"
        }
    }
    throw "Phase 5J post-storage F026 package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5j-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P5J-DIRECTF026-20261020-A",
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
    "PASS: Phase 5J ordinal 202 NtOpenFile native continuation armed",
    "NtOpenFile LIVE FRAME",
    "NtOpenFile OBJECT:",
    "NtOpenFile NATIVE:",
    "PASS: Phase 5J NtOpenFile native continuation",
    "PASS: Phase 5J ordinal 218 NtQueryVolumeInformationFile native continuation armed",
    "NtQueryVolumeInformationFile LIVE FRAME",
    "PASS: Phase 5J NtQueryVolumeInformationFile native continuation",
    "PASS: Phase 5J ordinal 187 NtClose native continuation armed",
    "NtClose LIVE FRAME",
    "PASS: Phase 5J NtClose native continuation",
    "PASS: Phase 5J ordinal 67 IoCreateSymbolicLink native continuation armed",
    "IoCreateSymbolicLink LIVE FRAME",
    "IoCreateSymbolicLink OBJECTS:",
    "PASS: Phase 5J IoCreateSymbolicLink native continuation",
    "PASS: Phase 5J ordinal 69 IoDeleteSymbolicLink native continuation armed",
    "IoDeleteSymbolicLink LIVE FRAME",
    "PASS: Phase 5J IoDeleteSymbolicLink native continuation",
    "PASS: hardware-observed post-mount direct root 0022C1C0 is packed for translated execution",
    "PASS: hardware-observed next retail direct root 002370B8 is packed for translated execution",
    "PASS: hardware-observed next retail direct root 0022BE8C is packed for translated execution",
    "PASS: Phase 5J ordinal 190 NtCreateFile native continuation armed",
    "NtCreateFile LIVE FRAME",
    "NtCreateFile OBJECT:",
    "NtCreateFile NATIVE:",
    "PASS: Phase 5J NtCreateFile native continuation",
    "PASS: Phase 5J ordinal 219 NtReadFile synchronous continuation armed",
    "NtReadFile LIVE FRAME",
    "PASS: Phase 5J NtReadFile native continuation",
    "PASS: Phase 5J ordinal 289 RtlInitAnsiString continuation armed",
    "RtlInitAnsiString LIVE FRAME",
    "PASS: Phase 5J RtlInitAnsiString continuation",
    "PASS: hardware-observed post-storage direct root 0022F026 is packed for translated execution",
    "STORAGE_IO",
    "game:\\merc360-partition1",
    "RtlInitializeCriticalSection LIVE FRAME",
    "PASS: ordinal 291 RtlInitializeCriticalSection matched maintained serialized-guest semantics",
    "NtAllocateVirtualMemory LIVE FRAME",
    "PASS: ordinal 184 NtAllocateVirtualMemory matched reserved/commit guest-VM semantics",
    "CRT memmove LIVE FRAME",
    "PASS: recomp_crt_memmove matched maintained cdecl semantics",
    "PASS: Phase 5J main/env build cookie matches",
    "PHASE 5J DIRECTF026 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 5J main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5J RETAIL ENVIRONMENT PREP START",
    "PHASE 5J EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5J EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5j_env_build_cookie",
    "50354A31",
    "PHASE 5J RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 5J phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 5J manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.promoted_direct_frontier_target_7 -ne "0x00238C00") {
    throw "Phase 5J manifest 38C00 root mismatch"
}
if ($manifestJson.continued_kernel_call_184.target -ne "0x800000B8" -or
    [int]$manifestJson.continued_kernel_call_184.arg_bytes -ne 20 -or
    [int]$manifestJson.continued_kernel_call_184.frame_bytes -ne 24) {
    throw "Phase 5J manifest ordinal-184 ABI mismatch"
}
if ($manifestJson.continued_kernel_call_291.target -ne "0x80000123" -or
    [int]$manifestJson.continued_kernel_call_291.arg_bytes -ne 4 -or
    [int]$manifestJson.continued_kernel_call_291.frame_bytes -ne 8) {
    throw "Phase 5J manifest ordinal-291 ABI mismatch"
}
if ($manifestJson.phase5_storage_boundary.target -ne "0x800000CA" -or
    [int]$manifestJson.phase5_storage_boundary.ordinal -ne 202 -or
    [int]$manifestJson.phase5_storage_boundary.arg_bytes -ne 24 -or
    [int]$manifestJson.phase5_storage_boundary.frame_bytes -ne 28 -or
    $manifestJson.phase5_storage_boundary.mode -ne "native-continuation") {
    throw "Phase 5J NtOpenFile native contract mismatch"
}
if ($manifestJson.phase5_storage_boundary.native_mapping -notlike "*Harddisk0*partition1*merc360-partition1*") {
    throw "Phase 5J Partition1 native mapping mismatch"
}
if ($manifestJson.phase5_volume_query.target -ne "0x800000DA" -or
    [int]$manifestJson.phase5_volume_query.ordinal -ne 218 -or
    [int]$manifestJson.phase5_volume_query.arg_bytes -ne 20 -or
    [int]$manifestJson.phase5_volume_query.frame_bytes -ne 24 -or
    [int]$manifestJson.phase5_volume_query.supported_class -ne 3) {
    throw "Phase 5J volume-query contract mismatch"
}
if ($manifestJson.phase5_handle_close.target -ne "0x800000BB" -or
    [int]$manifestJson.phase5_handle_close.ordinal -ne 187 -or
    [int]$manifestJson.phase5_handle_close.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_handle_close.frame_bytes -ne 8) {
    throw "Phase 5J NtClose contract mismatch"
}
if ($manifestJson.phase5_symbolic_link.target -ne "0x80000043" -or
    [int]$manifestJson.phase5_symbolic_link.ordinal -ne 67 -or
    [int]$manifestJson.phase5_symbolic_link.arg_bytes -ne 8 -or
    [int]$manifestJson.phase5_symbolic_link.frame_bytes -ne 12) {
    throw "Phase 5J IoCreateSymbolicLink contract mismatch"
}
if ($manifestJson.phase5_symbolic_link_delete.target -ne "0x80000045" -or
    [int]$manifestJson.phase5_symbolic_link_delete.ordinal -ne 69 -or
    [int]$manifestJson.phase5_symbolic_link_delete.arg_bytes -ne 4 -or
    [int]$manifestJson.phase5_symbolic_link_delete.frame_bytes -ne 8) {
    throw "Phase 5J IoDeleteSymbolicLink contract mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_8 -ne "0x0022D431") {
    throw "Phase 5J retained D431 root mismatch"
}
if ($manifestJson.promoted_closure_8_members.Count -ne 1 -or
    $manifestJson.promoted_closure_8_members[0] -ne "0x0022D431") {
    throw "Phase 5J retained D431 member set must be exactly 0x0022D431"
}
if ($manifestJson.promoted_direct_frontier_target_9 -ne "0x0022CA2B") {
    throw "Phase 5J retained CA2B root mismatch"
}
if ($manifestJson.promoted_closure_9_members.Count -ne 1 -or
    $manifestJson.promoted_closure_9_members[0] -ne "0x0022CA2B") {
    throw "Phase 5J retained CA2B member set must be exactly 0x0022CA2B"
}
if ($manifestJson.promoted_direct_frontier_target_10 -ne "0x0022C8EA") {
    throw "Phase 5J retained C8EA root mismatch"
}
if ($manifestJson.promoted_closure_10_members.Count -ne 1 -or
    $manifestJson.promoted_closure_10_members[0] -ne "0x0022C8EA") {
    throw "Phase 5J retained C8EA member set must be exactly 0x0022C8EA"
}
if ($manifestJson.promoted_direct_frontier_target_11 -ne "0x0022CEEE") {
    throw "Phase 5J retained CEEE root mismatch"
}
if ($manifestJson.promoted_closure_11_members.Count -ne 1 -or
    $manifestJson.promoted_closure_11_members[0] -ne "0x0022CEEE") {
    throw "Phase 5J retained CEEE member set must be exactly 0x0022CEEE"
}
if ($manifestJson.promoted_direct_frontier_target_12 -ne "0x0022C1C0") {
    throw "Phase 5J retained C1C0 root mismatch"
}
if ($manifestJson.promoted_closure_12_members.Count -ne 1 -or
    $manifestJson.promoted_closure_12_members[0] -ne "0x0022C1C0") {
    throw "Phase 5J retained C1C0 member set must be exactly 0x0022C1C0"
}
if ($manifestJson.promoted_direct_frontier_target_13 -ne "0x002370B8") {
    throw "Phase 5J retained 370B8 root mismatch"
}
if ($manifestJson.promoted_closure_13_members.Count -ne 1 -or
    $manifestJson.promoted_closure_13_members[0] -ne "0x002370B8") {
    throw "Phase 5J retained 370B8 member set must be exactly 0x002370B8"
}
if ($manifestJson.promoted_direct_frontier_target_14 -ne "0x0022BE8C") {
    throw "Phase 5J retained BE8C root mismatch"
}
if ($manifestJson.promoted_closure_14_members.Count -ne 1 -or
    $manifestJson.promoted_closure_14_members[0] -ne "0x0022BE8C") {
    throw "Phase 5J retained BE8C member set must be exactly 0x0022BE8C"
}
if ($manifestJson.promoted_direct_frontier_target_15 -ne "0x0022F026") {
    throw "Phase 5J manifest F026 root mismatch"
}
if ($manifestJson.promoted_closure_members.Count -ne 1 -or
    $manifestJson.promoted_closure_members[0] -ne "0x0022F026") {
    throw "Phase 5J safe-root member set must be exactly 0x0022F026"
}
if ($manifestJson.phase5_nt_create_file.target -ne "0x800000BE" -or
    [int]$manifestJson.phase5_nt_create_file.ordinal -ne 190 -or
    [int]$manifestJson.phase5_nt_create_file.arg_bytes -ne 36 -or
    [int]$manifestJson.phase5_nt_create_file.frame_bytes -ne 40 -or
    $manifestJson.phase5_nt_create_file.mode -ne "native-continuation") {
    throw "Phase 5J NtCreateFile contract mismatch"
}
if ($manifestJson.phase5_nt_read_file.target -ne "0x800000DB" -or
    [int]$manifestJson.phase5_nt_read_file.ordinal -ne 219 -or
    [int]$manifestJson.phase5_nt_read_file.arg_bytes -ne 32 -or
    [int]$manifestJson.phase5_nt_read_file.frame_bytes -ne 36 -or
    $manifestJson.phase5_nt_read_file.mode -ne "synchronous-native-continuation") {
    throw "Phase 5J NtReadFile contract mismatch"
}
if ($manifestJson.phase5_rtl_init_ansi_string.target -ne "0x80000121" -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.ordinal -ne 289 -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.arg_bytes -ne 8 -or
    [int]$manifestJson.phase5_rtl_init_ansi_string.frame_bytes -ne 12 -or
    $manifestJson.phase5_rtl_init_ansi_string.mode -ne "maintained-native-continuation") {
    throw "Phase 5J RtlInitAnsiString contract mismatch"
}
if ($manifestJson.continued_kernel_call_184.page_allocator -notlike "*top of 64 MiB guest RAM downward*") {
    throw "Phase 5J manifest page-backed allocator policy mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 0) {
    throw "Phase 5J manifest safe-root depth mismatch"
}
if ($manifestJson.continued_support_helper_memmove.name -ne "recomp_crt_memmove") {
    throw "Phase 5J manifest CRT memmove helper mismatch"
}
if ([int]$manifestJson.continued_support_helper_memmove.arg_bytes -ne 12 -or
    [int]$manifestJson.continued_support_helper_memmove.callee_cleanup_bytes -ne 4) {
    throw "Phase 5J manifest CRT memmove ABI mismatch"
}
Write-Host ""
Write-Host "[Phase5J] READY"
Write-Host "[Phase5J] Phase 5I evidence locked: TDATA/UDATA title-id setup and \\??\\T: mount passed before frontier 0x0022F026."
Write-Host "[Phase5J] New translated root: 0x0022F026"
Write-Host "[Phase5J] Promotion depth: 0; member set must be exactly one function."
Write-Host "[Phase5J] Retained storage stack: Partition1 + D:/T: mounts + NtCreateFile + NtClose + RtlInitAnsiString."
Write-Host "[Phase5J] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase5J]   $main"
Write-Host "[Phase5J]   $env"
Write-Host "[Phase5J] The 5J cookie must be 0x50354A31 (P5J1); stale 5I/5H environment objects must fail closed."
Write-Host "[Phase5J] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase5J] Expected build tag: P5J-DIRECTF026-20261020-A"
