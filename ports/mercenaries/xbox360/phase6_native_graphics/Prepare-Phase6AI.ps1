[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$inspector = Join-Path $PSScriptRoot "inspect_phase6ai_e7ae_orange_boundary.py"
$prep6ah = Join-Path $PSScriptRoot "Prepare-Phase6AH.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_saturation_0028e700_xdk"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6ai_e7ae_forensic"
$log = Join-Path $root "build\phase6_native_graphics\phase6ai-e7ae-forensic.log"
$manifest = Join-Path $baseDir "phase6ah-manifest.json"
$main = Join-Path $baseDir "main_monolithic.cpp"

foreach ($path in @($python,$baseEmitter,$inspector,$prep6ah)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AI input: $path"
    }
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $main -PathType Leaf)) {
    Write-Host "[Phase6AI] Cached Phase 6AH-D sources are missing."
    Write-Host "[Phase6AI] Regenerating 6AH-D sources only; VS2017 will remain skipped."
    & $prep6ah -SkipSolutionBuild
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $main -PathType Leaf)) {
    throw "Phase 6AI could not obtain cached Phase 6AH-D monolithic source"
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AH" -or
    $m.build_tag -ne "P6AH-D3D-SYNC-0028E700-20261023-D") {
    throw "Phase 6AI cached Phase 6AH-D baseline identity mismatch"
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AI] ORANGE BOUNDARY FORENSIC PREP"
Write-Host "[Phase6AI] Hardware proof : 6AH-D PASS then READ32 80000004"
Write-Host "[Phase6AI] Root           : 0028E700"
Write-Host "[Phase6AI] Focus label    : 0028E7AE"
Write-Host "[Phase6AI] Safety policy  : DO NOT map the 80000000-80000FFF fence"
Write-Host "[Phase6AI] Build policy   : no Visual Studio/XEX build in this forensic pass"
Write-Host ""

$emitArgs = @(
    "--base-dir",$baseDir,
    "--base-emitter",$baseEmitter,
    "--out-dir",$outDir
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $inspector @emitArgs 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AI] FORENSIC PREP FAILED."
    if (Test-Path -LiteralPath $log) {
        Get-Content -LiteralPath $log -Tail 160 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AI orange-boundary forensic failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6ai-e7ae-context.txt"
$json = Join-Path $outDir "phase6ai-e7ae-context.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AI forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AI-B" -or
    $r.root -ne "0x0028E700" -or
    $r.label -ne "0x0028E7AE" -or
    $r.hardware.guest -ne "0x80000004" -or
    $r.hardware.eax -ne "0x80000000" -or
    [int]$r.hardware.last_sync_phase -ne 3) {
    throw "Phase 6AI forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AI] FORENSIC PREP: PASS"
Write-Host ("[Phase6AI] Classification : {0}" -f [string]$r.classification)
Write-Host ("[Phase6AI] Report         : {0}" -f $txt)
Write-Host "[Phase6AI] SEND/PASTE THE CONSOLE OUTPUT FROM 'PRE-E7AE WINDOW BEGIN' THROUGH 'END'."
Write-Host "[Phase6AI] No XEX was built. This pass only identifies the exact orange-fault instruction."
