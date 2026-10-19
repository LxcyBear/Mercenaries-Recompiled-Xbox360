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
$emitter = Join-Path $phaseRoot "emit_phase4c_promoted_c5a4.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\promoted_c5a4_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-R input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-R] PROMOTED C5A4 CONTINUATION PACKAGE"
Write-Host "[Phase4C-R] Phase 4C-Q hardware PASS handled ordinal 113 and reached DIRECT_FRONTIER 0x0022C5A4 with fault=0."
Write-Host "[Phase4C-R] Promoting only 0x0022C5A4 beyond the Q pack."
Write-Host "[Phase4C-R] All prior startup invariants and kernel continuations remain active."
Write-Host "[Phase4C-R] Main/env build cookie is rotated to the R pair."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-R promoted-C5A4 package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-DIRECTC5A4-20261019-A",
    "PASS: hardware-observed direct target 0022C5A4 is packed for translated execution",
    "PASS: Phase 4C-R main/env build cookie matches",
    "PHASE 4C-R PROMOTED C5A4 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-R main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-R RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-R EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-R EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435231",
    "PHASE 4C-R RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-R phase4c_env.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-R] READY"
Write-Host "[Phase4C-R] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-R]   $main"
Write-Host "[Phase4C-R]   $env"
Write-Host "[Phase4C-R] A stale environment project item should fail at link-time on phase4c_env_build_cookie."
Write-Host "[Phase4C-R] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-R] Expected build tag: P4C-DIRECTC5A4-20261019-A"
