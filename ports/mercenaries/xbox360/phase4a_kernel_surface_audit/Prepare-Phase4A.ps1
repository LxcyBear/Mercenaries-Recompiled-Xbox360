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
$abiTest = Join-Path $repoRoot "tools\recomp\test_kernel_bridge_abi_metadata.py"
$generatedDir = Join-Path $repoRoot "build\phase3n_final_abi_scale\runtime\gen"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python. Run ports\mercenaries\scripts\Setup-Python.ps1 first."
}
if (-not (Test-Path -LiteralPath $xbePath -PathType Leaf)) {
    throw "Supported retail default.xbe not found at: $xbePath"
}
if (-not (Test-Path -LiteralPath $audit -PathType Leaf)) {
    throw "Phase 4A audit script missing: $audit"
}
if (-not (Test-Path -LiteralPath $abiTest -PathType Leaf)) {
    throw "Phase 4A ABI regression test missing: $abiTest"
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null

Write-Host "[Phase4A] NATIVE PLATFORM/KERNEL SURFACE AUDIT"
Write-Host "[Phase4A] This does NOT recompile the game."
Write-Host "[Phase4A] Verifying canonical guest-kernel stack cleanup metadata..."
Write-Host ""

Push-Location $repoRoot
try {
    & $python $abiTest
    if ($LASTEXITCODE -ne 0) {
        throw "Guest-kernel ABI metadata regression failed with exit code $LASTEXITCODE."
    }

    Write-Host ""
    Write-Host "[Phase4A] Auditing the exact 111 retail imports against the translated-game guest bridge..."

    $auditArgs = @(
        $audit,
        "--repo-root", $repoRoot,
        "--xbe", $xbePath,
        "--json", $jsonOut,
        "--text", $textOut
    )

    if (Test-Path -LiteralPath $generatedDir -PathType Container) {
        Write-Host "[Phase4A] Scanning preserved Phase-3N generated tree for thunk references..."
        $auditArgs += @("--generated-dir", $generatedDir)
    }
    else {
        Write-Host "[Phase4A] NOTE: preserved Phase-3N generated tree not found; static thunk-reference counts will be omitted."
    }

    & $python @auditArgs
    if ($LASTEXITCODE -ne 0) {
        throw "Phase 4A audit failed with exit code $LASTEXITCODE."
    }

    Write-Host ""
    Write-Host "[Phase4A] DONE"
    Write-Host "[Phase4A] No recompilation was performed."
    Write-Host "[Phase4A] Send this report back:"
    Write-Host "[Phase4A]   $textOut"
}
finally {
    Pop-Location
}
