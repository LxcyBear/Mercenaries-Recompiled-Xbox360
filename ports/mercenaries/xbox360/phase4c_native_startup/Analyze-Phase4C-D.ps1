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
$gateReport = Join-Path $stage3Root "phase3n-audit.json"
$phase4Report = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"
$closureAnalyzer = Join-Path $phaseRoot "analyze_startup_closure.py"
$baseEmitter = Join-Path $phaseRoot "emit_phase4c_startup_slice.py"
$analyzer = Join-Path $phaseRoot "analyze_phase4c_thread_routine.py"
$buildRoot = Join-Path $repoRoot "build\phase4c_native_startup"
$jsonOut = Join-Path $buildRoot "phase4c-thread-routine.json"
$textOut = Join-Path $buildRoot "phase4c-thread-routine.txt"

foreach ($required in @(
    $python, $generatedRoot, $functionsPath, $gateReport, $phase4Report,
    $closureAnalyzer, $baseEmitter, $analyzer
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 4C-D input is missing: $required"
    }
}

Write-Host "[Phase4C-D] HARDWARE-OBSERVED STARTUP THREAD PREFLIGHT"
Write-Host "[Phase4C-D] StartRoutine: 0x0022B43F"
Write-Host "[Phase4C-D] Context1:     0x002295D6"
Write-Host "[Phase4C-D] Context2:     0x00000000"
Write-Host ""

& $python $analyzer "--closure-analyzer" $closureAnalyzer "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--gate-report" $gateReport "--phase4-report" $phase4Report "--json-out" $jsonOut "--text-out" $textOut
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4C-D startup-thread preflight failed."
}

Write-Host ""
Write-Host "[Phase4C-D] DONE"
Write-Host "[Phase4C-D] No additional retail translated code was executed."
Write-Host "[Phase4C-D] Send this report back:"
Write-Host "[Phase4C-D]   $textOut"
