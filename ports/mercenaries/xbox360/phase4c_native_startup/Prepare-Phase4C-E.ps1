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
$emitter = Join-Path $phaseRoot "emit_phase4c_first_thread_execution.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\thread_run_xdk"

foreach ($required in @(
    $python, $generatedRoot, $functionsPath, $entryReport, $threadReport,
    $baseEmitter, $emitter, $phase3nTemplate, $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 4C-E input is missing: $required"
    }
}

$thread = Get-Content -LiteralPath $threadReport -Raw | ConvertFrom-Json
if ($thread.phase -ne "4C-D" -or -not [bool]$thread.structural_pass) {
    throw "Phase 4C-D thread report is not a structural PASS."
}
if ($thread.hardware_observed.start_routine -ne "0x0022B43F") {
    throw "Unexpected live thread StartRoutine: $($thread.hardware_observed.start_routine)"
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-E] FIRST HARDWARE-OBSERVED TITLE-THREAD EXECUTION PACKAGE"
Write-Host "[Phase4C-E] StartRoutine=0x0022B43F ctx1=0x002295D6 ctx2=0x00000000"
Write-Host "[Phase4C-E] Building only the 4C-A entry closure + 4C-D live thread closure."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4C-E first-thread execution package emission failed."
}

Write-Host ""
Write-Host "[Phase4C-E] READY"
Write-Host "[Phase4C-E] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-E]   $(Join-Path $outDir "main.cpp")"
Write-Host "[Phase4C-E]   $(Join-Path $outDir "phase4c_env.cpp")"
Write-Host "[Phase4C-E] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-E] Expected build tag: P4C-THREADRUN-20261019-A"
