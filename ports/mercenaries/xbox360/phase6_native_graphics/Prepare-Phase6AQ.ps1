[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$inspector = Join-Path $PSScriptRoot "inspect_phase6aq_retail_init_graph.py"
$prep6aj = Join-Path $PSScriptRoot "Prepare-Phase6AJ.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6aq_retail_init_graph"
$log = Join-Path $root "build\phase6_native_graphics\phase6aq-retail-init-graph.log"

$manifest = Join-Path $baseDir "phase6aj-manifest.json"
$main = Join-Path $baseDir "main_monolithic.cpp"
$env = Join-Path $baseDir "phase5_env.cpp"

foreach ($path in @($python,$baseEmitter,$inspector,$prep6aj)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AQ input: $path"
    }
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $main -PathType Leaf) -or
    -not (Test-Path -LiteralPath $env -PathType Leaf)) {
    Write-Host "[Phase6AQ] Cached Phase 6AJ-A source output is missing."
    Write-Host "[Phase6AQ] Regenerating 6AJ-A sources only; VS2017 remains skipped."
    & $prep6aj -SkipSolutionBuild
}

foreach ($path in @($manifest,$main,$env)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AQ could not obtain cached Phase 6AJ-A input: $path"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AQ cached Phase 6AJ-A baseline identity mismatch"
}

Write-Host "[Phase6AQ] RETAIL D3D INITIALIZER GRAPH AUDIT"
Write-Host "[Phase6AQ] 6AP provenance     : retail CreateDevice -> 0028FF80"
Write-Host "[Phase6AQ] 6AO writer proof  : sole +1A10 writer = 0028F9E0"
Write-Host "[Phase6AQ] Audit goal         : recover exact 0028FF80 -> 0028F9E0 path"
Write-Host "[Phase6AQ] Build policy       : PC-only, no Visual Studio/XEX build"
Write-Host ""

& $python -m py_compile $inspector
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AQ inspector Python syntax check failed"
}
Write-Host "[Phase6AQ] Inspector syntax   : PASS"

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

$argsList = @(
    "--base-dir",$baseDir,
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
    Write-Host "[Phase6AQ] FORENSIC AUDIT FAILED."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 320 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AQ retail init graph audit failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6aq-0028ff80-to-0028f9e0.txt"
$json = Join-Path $outDir "phase6aq-0028ff80-to-0028f9e0.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AQ forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AQ-A" -or
    $r.baseline -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A" -or
    $r.root -ne "sub_0028FF80" -or
    $r.target -ne "sub_0028F9E0") {
    throw "Phase 6AQ forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AQ] RETAIL INIT GRAPH AUDIT: PASS"
Write-Host ("[Phase6AQ] Target reached    : {0}" -f [bool]$r.target_reached)
Write-Host ("[Phase6AQ] Path              : {0}" -f (($r.shortest_path -join " -> ")))
Write-Host ("[Phase6AQ] Report            : {0}" -f $txt)
Write-Host "[Phase6AQ] No XEX was built."
Write-Host "[Phase6AQ] SEND/PASTE FROM 'PATH SUMMARY BEGIN' THROUGH 'PATH BODIES END'."
