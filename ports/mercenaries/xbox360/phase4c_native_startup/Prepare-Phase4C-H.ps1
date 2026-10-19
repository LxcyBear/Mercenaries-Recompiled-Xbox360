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
$emitter = Join-Path $phaseRoot "emit_phase4c_callback_frontier.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\callback_frontier_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-H input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-H] HARDWARE-CONFIRMED STARTUP CALLBACK FRONTIER PACKAGE"
Write-Host "[Phase4C-H] Callback: 0x002295D6"
Write-Host "[Phase4C-H] Hardware-proven call frame: 8 bytes (one dword argument + synthetic CALL return)."
Write-Host "[Phase4C-H] Callback packing policy: direct depth 1, cap 64 bodies."
Write-Host "[Phase4C-H] Deeper translated direct calls become deterministic DIRECT_FRONTIER boundaries."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-H callback-frontier package emission failed." }

Write-Host ""
Write-Host "[Phase4C-H] READY"
Write-Host "[Phase4C-H] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-H]   $(Join-Path $outDir "main.cpp")"
Write-Host "[Phase4C-H]   $(Join-Path $outDir "phase4c_env.cpp")"
Write-Host "[Phase4C-H] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-H] Expected build tag: P4C-CALLBACK-20261019-A"
