[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$inspector = Join-Path $PSScriptRoot "inspect_phase6am_0028bc60_read32.py"
$prep6al = Join-Path $PSScriptRoot "Prepare-Phase6AL.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\read32_site_probe_xdk"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6am_0028bc60_read32_forensic"
$log = Join-Path $root "build\phase6_native_graphics\phase6am-0028bc60-read32.log"

$manifest = Join-Path $baseDir "phase6al-manifest.json"
$shardDir = Join-Path $baseDir "translated_shards"

foreach ($path in @($python,$baseEmitter,$inspector,$prep6al)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AM input: $path"
    }
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $shardDir -PathType Container)) {
    Write-Host "[Phase6AM] Cached Phase 6AL-A source output is missing."
    Write-Host "[Phase6AM] Regenerating 6AL-A sources only; VS2017 will remain skipped."
    & $prep6al -SkipSolutionBuild
}

foreach ($path in @($manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Phase 6AM could not obtain cached Phase 6AL-A input: $path"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AL" -or
    $m.build_tag -ne "P6AL-READ32-SITE-PROBE-20261023-A") {
    throw "Phase 6AM cached Phase 6AL-A baseline identity mismatch"
}

$al = $m.phase6al_read32_site_probe
if (-not [bool]$al.probe_only -or
    [bool]$al.guest_memory_semantics_changed) {
    throw "Phase 6AM inherited Phase 6AL probe model drift"
}

Write-Host "[Phase6AM] EXACT 0028BC60 READ32 SOURCE FORENSIC"
Write-Host "[Phase6AM] Hardware proof : 6AL-A last_func=0028BC60"
Write-Host "[Phase6AM] Hardware line  : 1957"
Write-Host "[Phase6AM] Boundary read  : READ32 80000004"
Write-Host "[Phase6AM] Build policy   : no Visual Studio/XEX build in this forensic pass"
Write-Host ""

& $python -m py_compile $inspector
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AM inspector Python syntax check failed"
}
Write-Host "[Phase6AM] Inspector syntax: PASS"

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
    Write-Host "[Phase6AM] FORENSIC PREP FAILED."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 260 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AM exact READ32 forensic failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6am-0028bc60-read32-site.txt"
$json = Join-Path $outDir "phase6am-0028bc60-read32-site.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AM forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AM-A" -or
    $r.baseline -ne "P6AL-READ32-SITE-PROBE-20261023-A" -or
    $r.hardware.fault -ne "READ32 0x80000004" -or
    $r.hardware.function -ne "0x0028BC60" -or
    [int]$r.hardware.line -ne 1957 -or
    $r.function -ne "sub_0028BC60") {
    throw "Phase 6AM forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AM] EXACT READ32 FORENSIC PREP: PASS"
Write-Host ("[Phase6AM] Shard        : {0}" -f $r.shard)
Write-Host ("[Phase6AM] Exact source : {0}" -f $r.exact_source)
Write-Host ("[Phase6AM] Report       : {0}" -f $txt)
Write-Host "[Phase6AM] No XEX was built."
Write-Host "[Phase6AM] SEND/PASTE THE CONSOLE OUTPUT FROM 'EXACT SITE WINDOW BEGIN' THROUGH 'TARGET FUNCTION END'."
