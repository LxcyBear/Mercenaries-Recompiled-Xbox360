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
$baseEmitter = Join-Path $phaseRoot "emit_phase4c_startup_slice.py"
$emitter = Join-Path $phaseRoot "emit_phase4c_ntalloc184_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\vmalloc184_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-Z input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-Z] ORDINAL 184 NTALLOCATEVIRTUALMEMORY CONTINUATION PACKAGE"
Write-Host "[Phase4C-Z] Phase 4C-Y hardware PASS executed 0x00238C00 + maintained CRT memmove and reached ICALL_SAFE 0x800000B8 with fault=0."
Write-Host "[Phase4C-Z] Continuing ordinal 184 NtAllocateVirtualMemory with exact 20-byte stdcall args / 24-byte full frame."
Write-Host "[Phase4C-Z] Supported modes: reserve+commit via page-rounded bounded guest allocation, or commit inside an existing guest range."
Write-Host "[Phase4C-Z] Reserve-without-commit remains an explicit VM_UNSUPPORTED boundary."
Write-Host "[Phase4C-Z] All previously proven startup invariants, direct roots, helper continuations, and kernel continuations remain active."
Write-Host "[Phase4C-Z] Main/env build cookie is rotated to the Z pair."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-z-emitter.log"
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
    $failedManifest = Join-Path $outDir "phase4c-z-manifest.json"
    if (Test-Path -LiteralPath $failedManifest) {
        try {
            $failedJson = Get-Content -LiteralPath $failedManifest -Raw | ConvertFrom-Json
            if ($failedJson.unknown_direct_helpers) {
                Write-Host ""
                Write-Host "[Phase4C-Z] Remaining unresolved helper dependencies:"
                $failedJson.unknown_direct_helpers.PSObject.Properties | ForEach-Object {
                    Write-Host ("[Phase4C-Z]   {0}: {1}" -f $_.Name, ($_.Value -join ", "))
                }
                Write-Host ""
            }
        } catch {
            Write-Host "[Phase4C-Z] Could not decode failure manifest: $($_.Exception.Message)"
        }
    }
    throw "Phase 4C-Z ordinal-184 package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$manifest = Join-Path $outDir "phase4c-z-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-NTALLOC184-20261019-A",
    "PASS: ordinal 149 KeSetTimer continuation armed",
    "PASS: bounded direct closure rooted at 0022D980 is packed for translated execution",
    "PASS: hardware-observed direct root 00238C00 is packed for translated execution",
    "PASS: maintained recomp_crt_memmove cdecl support armed",
    "PASS: ordinal 184 NtAllocateVirtualMemory continuation armed",
    "NtAllocateVirtualMemory LIVE FRAME",
    "PASS: ordinal 184 NtAllocateVirtualMemory matched bounded bridge semantics",
    "CRT memmove LIVE FRAME",
    "PASS: recomp_crt_memmove matched maintained cdecl semantics",
    "PASS: Phase 4C-Z main/env build cookie matches",
    "PHASE 4C-Z NTALLOC184 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-Z main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-Z RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-Z EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-Z EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435A31",
    "PHASE 4C-Z RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-Z phase4c_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 4C-Z manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.promoted_direct_frontier_target_7 -ne "0x00238C00") {
    throw "Phase 4C-Z manifest 38C00 root mismatch"
}
if ($manifestJson.continued_kernel_call_184.target -ne "0x800000B8" -or
    [int]$manifestJson.continued_kernel_call_184.arg_bytes -ne 20 -or
    [int]$manifestJson.continued_kernel_call_184.frame_bytes -ne 24) {
    throw "Phase 4C-Z manifest ordinal-184 ABI mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 0) {
    throw "Phase 4C-Z manifest safe-root depth mismatch"
}
if ($manifestJson.continued_support_helper_memmove.name -ne "recomp_crt_memmove") {
    throw "Phase 4C-Z manifest CRT memmove helper mismatch"
}
if ([int]$manifestJson.continued_support_helper_memmove.arg_bytes -ne 12 -or
    [int]$manifestJson.continued_support_helper_memmove.callee_cleanup_bytes -ne 4) {
    throw "Phase 4C-Z manifest CRT memmove ABI mismatch"
}
if ($manifestJson.promoted_closure_members.Count -ne 1 -or $manifestJson.promoted_closure_members[0] -ne "0x00238C00") {
    throw "Phase 4C-Z safe-root member set must be exactly 0x00238C00"
}

Write-Host ""
Write-Host "[Phase4C-Z] READY"
Write-Host "[Phase4C-Z] Retained 38C00 safe-root members: $($manifestJson.promoted_closure_members.Count)"
Write-Host "[Phase4C-Z]   $($manifestJson.promoted_closure_members -join ', ')"
Write-Host "[Phase4C-Z] Continued kernel target: 0x800000B8 ordinal 184 NtAllocateVirtualMemory"
Write-Host "[Phase4C-Z] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-Z]   $main"
Write-Host "[Phase4C-Z]   $env"
Write-Host "[Phase4C-Z] The Z cookie must be 0x50435A31 (PCZ1); stale Y/X environment objects must fail closed."
Write-Host "[Phase4C-Z] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-Z] Expected build tag: P4C-NTALLOC184-20261019-A"
