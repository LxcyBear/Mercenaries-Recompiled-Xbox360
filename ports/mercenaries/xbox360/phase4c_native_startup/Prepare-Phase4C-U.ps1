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
$emitter = Join-Path $phaseRoot "emit_phase4c_rtl301_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\rtl301_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-U input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-U] ORDINAL 301 RTLNTSTATUSTODOSERROR CONTINUATION PACKAGE"
Write-Host "[Phase4C-U] Phase 4C-T hardware PASS continued ordinal 24 and reached ICALL_SAFE 0x8000012D with fault=0."
Write-Host "[Phase4C-U] Ordinal 301 is RtlNtStatusToDosError; validate its 1-argument stdcall frame and continue using the locked runtime bridge mapping."
Write-Host "[Phase4C-U] All previously proven startup invariants and continuations remain active."
Write-Host "[Phase4C-U] Main/env build cookie is rotated to the U pair."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-U ordinal-301 package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-RTL301-20261019-A",
    "PASS: ordinal 24 ExQueryNonVolatileSetting tail continuation armed",
    "PASS: ordinal 301 RtlNtStatusToDosError continuation armed",
    "RtlNtStatusToDosError LIVE FRAME",
    "PASS: Phase 4C-U main/env build cookie matches",
    "PHASE 4C-U RTLNTSTATUSTODOSERROR RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-U main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-U RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-U EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-U EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435531",
    "PHASE 4C-U RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-U phase4c_env.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-U] READY"
Write-Host "[Phase4C-U] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-U]   $main"
Write-Host "[Phase4C-U]   $env"
Write-Host "[Phase4C-U] The U cookie must be 0x50435531 (PCU1); stale T/S environment objects must fail closed."
Write-Host "[Phase4C-U] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-U] Expected build tag: P4C-RTL301-20261019-A"
