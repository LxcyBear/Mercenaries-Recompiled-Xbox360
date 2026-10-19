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
$emitter = Join-Path $phaseRoot "emit_phase4c_timer149_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\timer149_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-W input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-W] ORDINAL 149 KESETTIMER CONTINUATION PACKAGE"
Write-Host "[Phase4C-W] Phase 4C-V hardware PASS executed 0x0022F0FB and reached ICALL_SAFE 0x80000095 with fault=0."
Write-Host "[Phase4C-W] Ordinal 149 is KeSetTimer; validate its 16-byte stdcall arguments / 20-byte full frame and continue with guest-KTIMER semantics."
Write-Host "[Phase4C-W] All previously proven startup invariants and continuations remain active."
Write-Host "[Phase4C-W] Main/env build cookie is rotated to the W pair."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-W ordinal-149 package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$manifest = Join-Path $outDir "phase4c-w-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-TIMER149-20261019-A",
    "PASS: ordinal 149 KeSetTimer continuation armed",
    "KeSetTimer LIVE FRAME",
    "PASS: ordinal 149 KeSetTimer matched guest-KTIMER semantics",
    "PASS: Phase 4C-W main/env build cookie matches",
    "PHASE 4C-W KESETTIMER149 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-W main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-W RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-W EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-W EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435731",
    "PHASE 4C-W RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-W phase4c_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 4C-W manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.continued_kernel_call_149.target -ne "0x80000095") {
    throw "Phase 4C-W manifest ordinal-149 target mismatch"
}
if ([int]$manifestJson.continued_kernel_call_149.arg_bytes -ne 16) {
    throw "Phase 4C-W manifest ordinal-149 argument-byte mismatch"
}
if ([int]$manifestJson.continued_kernel_call_149.frame_bytes -ne 20) {
    throw "Phase 4C-W manifest ordinal-149 frame-byte mismatch"
}

Write-Host ""
Write-Host "[Phase4C-W] READY"
Write-Host "[Phase4C-W] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-W]   $main"
Write-Host "[Phase4C-W]   $env"
Write-Host "[Phase4C-W] The W cookie must be 0x50435731 (PCW1); stale V/U environment objects must fail closed."
Write-Host "[Phase4C-W] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-W] Expected build tag: P4C-TIMER149-20261019-A"
