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
$emitter = Join-Path $phaseRoot "emit_phase4c_promoted_f128.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\promoted_f128_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-O input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-O] PROMOTED F128 CONTINUATION PACKAGE"
Write-Host "[Phase4C-O] Phase 4C-N hardware PASS handled ordinal 47 and reached DIRECT_FRONTIER 0x0022F128 with fault=0."
Write-Host "[Phase4C-O] Promoting only 0x0022F128 beyond the N pack."
Write-Host "[Phase4C-O] All prior DATA relocations, kernel-header modeling, ordinal-47 continuation, and first-fault provenance remain active."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-O promoted-F128 package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($requiredText in @(
    "P4C-DIRECTF128-20261019-A",
    "PASS: hardware-observed direct target 0022F128 is packed for translated execution",
    "HalRegisterShutdownNotification LIVE FRAME:",
    "PHASE 4C-O PROMOTED F128 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-O main.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-O] READY"
Write-Host "[Phase4C-O] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-O]   $main"
Write-Host "[Phase4C-O]   $env"
Write-Host "[Phase4C-O] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-O] Expected build tag: P4C-DIRECTF128-20261019-A"
