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
$emitter = Join-Path $phaseRoot "emit_phase5a_ntopenfile_capture.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\ntopenfile_capture_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 5A input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5A] FIRST LIVE STORAGE/CONTENT REQUEST CAPTURE"
Write-Host "[Phase5A] Phase 4C-AF hardware PASS completed the native-startup gate and reached ICALL_SAFE 0x800000CA with fault=0."
Write-Host "[Phase5A] 0x800000CA is ordinal 202 NtOpenFile; observed full frame is 28 bytes (return + six stdcall args)."
Write-Host "[Phase5A] This gate captures OBJECT_ATTRIBUTES / ANSI_STRING path plus access/share/options without fabricating storage I/O."
Write-Host "[Phase5A] Complete Phase-4 startup/kernel/VM state remains active and hardware-proven."
Write-Host "[Phase5A] Main/env build cookie is P5A1."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5a-emitter.log"
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
    $failedManifest = Join-Path $outDir "phase5a-manifest.json"
    if (Test-Path -LiteralPath $failedManifest) {
        try {
            $failedJson = Get-Content -LiteralPath $failedManifest -Raw | ConvertFrom-Json
            if ($failedJson.unknown_direct_helpers) {
                Write-Host ""
                Write-Host "[Phase5A] Remaining unresolved helper dependencies:"
                $failedJson.unknown_direct_helpers.PSObject.Properties | ForEach-Object {
                    Write-Host ("[Phase5A]   {0}: {1}" -f $_.Name, ($_.Value -join ", "))
                }
                Write-Host ""
            }
        } catch {
            Write-Host "[Phase5A] Could not decode failure manifest: $($_.Exception.Message)"
        }
    }
    throw "Phase 5A NtOpenFile capture package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5a-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P5A-NTOPEN202-CAPTURE-20261019-A",
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
    "PASS: Phase 5A ordinal 202 NtOpenFile capture armed",
    "NtOpenFile LIVE FRAME",
    "NtOpenFile OBJECT:",
    "PASS: Phase 5A captured ordinal 202 NtOpenFile request",
    "STORAGE_OPEN",
    "RtlInitializeCriticalSection LIVE FRAME",
    "PASS: ordinal 291 RtlInitializeCriticalSection matched maintained serialized-guest semantics",
    "NtAllocateVirtualMemory LIVE FRAME",
    "PASS: ordinal 184 NtAllocateVirtualMemory matched reserved/commit guest-VM semantics",
    "CRT memmove LIVE FRAME",
    "PASS: recomp_crt_memmove matched maintained cdecl semantics",
    "PASS: Phase 5A main/env build cookie matches",
    "PHASE 5A NTOPEN202 CAPTURE RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 5A main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-AF RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-AF EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-AF EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50354131",
    "PHASE 4C-AF RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 5A phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 5A manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.promoted_direct_frontier_target_7 -ne "0x00238C00") {
    throw "Phase 5A manifest 38C00 root mismatch"
}
if ($manifestJson.continued_kernel_call_184.target -ne "0x800000B8" -or
    [int]$manifestJson.continued_kernel_call_184.arg_bytes -ne 20 -or
    [int]$manifestJson.continued_kernel_call_184.frame_bytes -ne 24) {
    throw "Phase 5A manifest ordinal-184 ABI mismatch"
}
if ($manifestJson.continued_kernel_call_291.target -ne "0x80000123" -or
    [int]$manifestJson.continued_kernel_call_291.arg_bytes -ne 4 -or
    [int]$manifestJson.continued_kernel_call_291.frame_bytes -ne 8) {
    throw "Phase 5A manifest ordinal-291 ABI mismatch"
}
if ($manifestJson.phase5_storage_boundary.target -ne "0x800000CA" -or
    [int]$manifestJson.phase5_storage_boundary.ordinal -ne 202 -or
    [int]$manifestJson.phase5_storage_boundary.arg_bytes -ne 24 -or
    [int]$manifestJson.phase5_storage_boundary.frame_bytes -ne 28 -or
    $manifestJson.phase5_storage_boundary.mode -ne "capture-only") {
    throw "Phase 5A NtOpenFile capture contract mismatch"
}
if ($manifestJson.promoted_direct_frontier_target_8 -ne "0x0022D431") {
    throw "Phase 5A retained D431 root mismatch"
}
if ($manifestJson.promoted_closure_8_members.Count -ne 1 -or
    $manifestJson.promoted_closure_8_members[0] -ne "0x0022D431") {
    throw "Phase 5A retained D431 member set must be exactly 0x0022D431"
}
if ($manifestJson.promoted_direct_frontier_target_9 -ne "0x0022CA2B") {
    throw "Phase 5A retained CA2B root mismatch"
}
if ($manifestJson.promoted_closure_9_members.Count -ne 1 -or
    $manifestJson.promoted_closure_9_members[0] -ne "0x0022CA2B") {
    throw "Phase 5A retained CA2B member set must be exactly 0x0022CA2B"
}
if ($manifestJson.promoted_direct_frontier_target_10 -ne "0x0022C8EA") {
    throw "Phase 5A retained C8EA root mismatch"
}
if ($manifestJson.promoted_closure_10_members.Count -ne 1 -or
    $manifestJson.promoted_closure_10_members[0] -ne "0x0022C8EA") {
    throw "Phase 5A retained C8EA member set must be exactly 0x0022C8EA"
}
if ($manifestJson.promoted_direct_frontier_target_11 -ne "0x0022CEEE") {
    throw "Phase 5A manifest CEEE root mismatch"
}
if ($manifestJson.promoted_closure_members.Count -ne 1 -or
    $manifestJson.promoted_closure_members[0] -ne "0x0022CEEE") {
    throw "Phase 5A safe-root member set must be exactly 0x0022CEEE"
}
if ($manifestJson.continued_kernel_call_184.page_allocator -notlike "*top of 64 MiB guest RAM downward*") {
    throw "Phase 5A manifest page-backed allocator policy mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 0) {
    throw "Phase 5A manifest safe-root depth mismatch"
}
if ($manifestJson.continued_support_helper_memmove.name -ne "recomp_crt_memmove") {
    throw "Phase 5A manifest CRT memmove helper mismatch"
}
if ([int]$manifestJson.continued_support_helper_memmove.arg_bytes -ne 12 -or
    [int]$manifestJson.continued_support_helper_memmove.callee_cleanup_bytes -ne 4) {
    throw "Phase 5A manifest CRT memmove ABI mismatch"
}
Write-Host ""
Write-Host "[Phase5A] READY"
Write-Host "[Phase5A] Phase 4 hardware baseline retained: 60-member AF package + all proven kernel/VM continuations."
Write-Host "[Phase5A] Storage boundary: 0x800000CA ordinal 202 NtOpenFile"
Write-Host "[Phase5A] Expected frame: 24 argument bytes / 28 bytes including synthetic return."
Write-Host "[Phase5A] Capture policy: decode guest OBJECT_ATTRIBUTES + ANSI_STRING path; DO NOT perform file I/O yet."
Write-Host "[Phase5A] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase5A]   $main"
Write-Host "[Phase5A]   $env"
Write-Host "[Phase5A] The 5A cookie must be 0x50354131 (P5A1); stale Phase-4 environment objects must fail closed."
Write-Host "[Phase5A] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase5A] Expected build tag: P5A-NTOPEN202-CAPTURE-20261019-A"
