[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$inspector = Join-Path $PSScriptRoot "inspect_phase6ap_retail_d3d_init_path.py"
$prep6aj = Join-Path $PSScriptRoot "Prepare-Phase6AJ.ps1"

$currentDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$phase6BuildRoot = Join-Path $root "build\phase6_native_graphics"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6ap_retail_d3d_init_path"
$log = Join-Path $root "build\phase6_native_graphics\phase6ap-retail-d3d-init-path.log"

$manifest = Join-Path $currentDir "phase6aj-manifest.json"
$main = Join-Path $currentDir "main_monolithic.cpp"
$env = Join-Path $currentDir "phase5_env.cpp"

foreach ($path in @($python,$baseEmitter,$inspector,$prep6aj)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AP input: $path"
    }
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $main -PathType Leaf) -or
    -not (Test-Path -LiteralPath $env -PathType Leaf)) {
    Write-Host "[Phase6AP] Cached Phase 6AJ-A source output is missing."
    Write-Host "[Phase6AP] Regenerating 6AJ-A sources only; VS2017 remains skipped."
    & $prep6aj -SkipSolutionBuild
}

foreach ($path in @($manifest,$main,$env)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AP could not obtain cached Phase 6AJ-A input: $path"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AP cached Phase 6AJ-A baseline identity mismatch"
}

Write-Host "[Phase6AP] RETAIL D3D INITIALIZER PATH AUDIT"
Write-Host "[Phase6AP] 6AN-B hardware     : +1A10 count=0 -> underflow"
Write-Host "[Phase6AP] 6AO writer proof  : only D3D +1A10 writer is sub_0028F9E0"
Write-Host "[Phase6AP] Audit goal         : recover pre-6AF CreateDevice/init path"
Write-Host "[Phase6AP] Build policy       : PC-only, no Visual Studio/XEX build"
Write-Host ""

& $python -m py_compile $inspector
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AP inspector Python syntax check failed"
}
Write-Host "[Phase6AP] Inspector syntax   : PASS"

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

$argsList = @(
    "--current-dir",$currentDir,
    "--phase6-build-root",$phase6BuildRoot,
    "--base-emitter",$baseEmitter,
    "--out-dir",$outDir
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $inspector @argsList 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AP] FORENSIC AUDIT FAILED."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 320 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AP retail D3D initializer audit failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6ap-retail-d3d-init-path.txt"
$json = Join-Path $outDir "phase6ap-retail-d3d-init-path.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AP forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AP-A" -or
    $r.baseline -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A" -or
    $r.initializer.function -ne "sub_0028F9E0") {
    throw "Phase 6AP forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AP] RETAIL D3D INIT PATH AUDIT: PASS"
Write-Host ("[Phase6AP] Current refs       : {0}" -f @($r.current_initializer_refs).Count)
Write-Host ("[Phase6AP] Cached 0028CAA0   : {0}" -f [int]$r.create_device_cache_candidates)
Write-Host ("[Phase6AP] Distinct bodies   : {0}" -f [int]$r.create_device_distinct_bodies)
Write-Host ("[Phase6AP] Retail-like       : {0}" -f [int]$r.retail_like_bodies)
Write-Host ("[Phase6AP] Bridge-like       : {0}" -f [int]$r.bridge_like_bodies)
Write-Host ("[Phase6AP] Report            : {0}" -f $txt)
Write-Host "[Phase6AP] No XEX was built."
Write-Host "[Phase6AP] SEND/PASTE FROM 'INIT CALL SURFACE BEGIN' THROUGH 'RETAIL-LIKE CREATEDEVICE BODIES END'."
