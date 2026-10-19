[CmdletBinding()]
param(
    [string]$GameDirectory
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"

if (-not $GameDirectory) {
    $GameDirectory = Join-Path $repoRoot "game_files\mercenaries-retail"
}

$xbePath = Join-Path ([System.IO.Path]::GetFullPath($GameDirectory)) "default.xbe"
$buildRoot = Join-Path $repoRoot "build\phase4a_kernel_surface"
$jsonOut = Join-Path $buildRoot "phase4a-kernel-surface.json"
$textOut = Join-Path $buildRoot "phase4a-kernel-surface.txt"
$audit = Join-Path $phaseRoot "audit_phase4a_kernel_surface.py"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Run ports\mercenaries\scripts\Setup-Python.ps1 first."
}
if (-not (Test-Path -LiteralPath $xbePath -PathType Leaf)) {
    throw "Supported retail default.xbe not found at: $xbePath"
}
if (-not (Test-Path -LiteralPath $audit -PathType Leaf)) {
    throw "Phase 4A audit script missing: $audit"
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null

Write-Host "[Phase4A] NATIVE PLATFORM/KERNEL SURFACE AUDIT"
Write-Host "[Phase4A] This does NOT recompile the game."
Write-Host "[Phase4A] Auditing exact retail imports against the current kernel bridge..."
Write-Host ""

Push-Location $repoRoot
try {
    & $python $audit --repo-root $repoRoot --xbe $xbePath --json $jsonOut --text $textOut

    if ($LASTEXITCODE -ne 0) {
        throw "Phase 4A audit failed with exit code $LASTEXITCODE."
    }

    Write-Host ""
    Write-Host "[Phase4A] DONE"
    Write-Host "[Phase4A] Send this report back:"
    Write-Host "[Phase4A]   $textOut"
}
finally {
    Pop-Location
}
