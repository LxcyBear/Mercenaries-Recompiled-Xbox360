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
$emitter = Join-Path $phaseRoot "emit_phase4c_hal47_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\hal47_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-N input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-N] HAL SHUTDOWN-REGISTRATION CONTINUATION PACKAGE"
Write-Host "[Phase4C-N] Phase 4C-M hardware PASS reached ICALL_SAFE 0x8000002F from translated 0x0022C28B."
Write-Host "[Phase4C-N] Ordinal 47 = HalRegisterShutdownNotification; production ABI = 8 argument bytes."
Write-Host "[Phase4C-N] Validate the 12-byte live frame, log registration VA/boolean, return eax=0, and resume translated startup."
Write-Host "[Phase4C-N] Startup DATA relocations, kernel-header model, promoted 0x0022C47B, and first-fault provenance remain active."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-N ordinal-47 continuation package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($requiredText in @(
    "P4C-HAL47-20261019-A",
    "PASS: ordinal 47 HalRegisterShutdownNotification continuation armed",
    "HalRegisterShutdownNotification LIVE FRAME:",
    "PHASE 4C-N HAL SHUTDOWN-REGISTRATION RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-N main.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-N] READY"
Write-Host "[Phase4C-N] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-N]   $main"
Write-Host "[Phase4C-N]   $env"
Write-Host "[Phase4C-N] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-N] Expected build tag: P4C-HAL47-20261019-A"
