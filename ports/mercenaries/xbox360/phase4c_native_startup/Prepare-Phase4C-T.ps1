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
$emitter = Join-Path $phaseRoot "emit_phase4c_nv24_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\nv24_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-T input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-T] ORDINAL 24 EXQUERYNONVOLATILESETTING CONTINUATION PACKAGE"
Write-Host "[Phase4C-T] Phase 4C-S hardware PASS executed 0x00230060 and reached ITAIL 0x80000018 with fault=0."
Write-Host "[Phase4C-T] Ordinal 24 is ExQueryNonVolatileSetting; continue its 5-argument stdcall tail frame using guest EEPROM/XConfig semantics."
Write-Host "[Phase4C-T] All previously proven startup invariants and continuations remain active."
Write-Host "[Phase4C-T] Main/env build cookie is rotated to the T pair."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-T ordinal-24 package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-NV24-20261019-A",
    "PASS: hardware-observed direct target 00230060 is packed for translated execution",
    "PASS: ordinal 24 ExQueryNonVolatileSetting tail continuation armed",
    "ExQueryNonVolatileSetting LIVE TAIL FRAME",
    "PASS: Phase 4C-T main/env build cookie matches",
    "PHASE 4C-T EXQUERYNONVOLATILESETTING RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-T main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-T RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-T EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-T EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435431",
    "PHASE 4C-T RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-T phase4c_env.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-T] READY"
Write-Host "[Phase4C-T] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-T]   $main"
Write-Host "[Phase4C-T]   $env"
Write-Host "[Phase4C-T] The T cookie must be 0x50435431 (PCT1); stale S/R environment objects must fail closed."
Write-Host "[Phase4C-T] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-T] Expected build tag: P4C-NV24-20261019-A"
