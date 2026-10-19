[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

$stage3Root = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$generatedRoot = Join-Path $stage3Root "runtime\gen"
$gateReport = Join-Path $stage3Root "phase3n-audit.json"
$functionsPath = Join-Path $stage3Root "analysis\disasm\functions.json"
$phase4Report = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"

$buildRoot = Join-Path $repoRoot "build\phase4c_native_startup"
$jsonOut = Join-Path $buildRoot "phase4c-startup-closure.json"
$textOut = Join-Path $buildRoot "phase4c-startup-closure.txt"
$analyzer = Join-Path $phaseRoot "analyze_startup_closure.py"

foreach ($required in @(
    $python,
    $generatedRoot,
    $gateReport,
    $functionsPath,
    $phase4Report,
    $analyzer
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 4C-A input is missing: $required"
    }
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null

Write-Host "[Phase4C-A] REAL RETAIL ENTRY-ROOTED STARTUP PREFLIGHT"
Write-Host "[Phase4C-A] Entry VA: 0x0022964A"
Write-Host "[Phase4C-A] Verifying locked Phase-3N-A tree and Phase-4B final service split..."
Write-Host ""

& $python $analyzer "--generated-root" $generatedRoot "--functions" $functionsPath "--gate-report" $gateReport "--phase4-report" $phase4Report "--json-out" $jsonOut "--text-out" $textOut
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4C-A startup closure preflight failed."
}

Write-Host ""
Write-Host "[Phase4C-A] DONE"
Write-Host "[Phase4C-A] No retail translated code was executed."
Write-Host "[Phase4C-A] Send this report back:"
Write-Host "[Phase4C-A]   $textOut"
