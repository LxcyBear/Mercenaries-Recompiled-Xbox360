[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$inspector = Join-Path $PSScriptRoot "inspect_phase6ak_caller_0023a3ce.py"
$prep6aj = Join-Path $PSScriptRoot "Prepare-Phase6AJ.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6ak_caller_0023a3ce_forensic"
$log = Join-Path $root "build\phase6_native_graphics\phase6ak-caller-forensic.log"

$manifest = Join-Path $baseDir "phase6aj-manifest.json"
$main = Join-Path $baseDir "main_monolithic.cpp"
$env = Join-Path $baseDir "phase5_env.cpp"

foreach ($path in @($python,$baseEmitter,$inspector,$prep6aj)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AK input: $path"
    }
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $main -PathType Leaf) -or
    -not (Test-Path -LiteralPath $env -PathType Leaf)) {
    Write-Host "[Phase6AK] Cached Phase 6AJ-A source output is missing."
    Write-Host "[Phase6AK] Regenerating 6AJ-A sources only; VS2017 will remain skipped."
    & $prep6aj -SkipSolutionBuild
}

foreach ($path in @($manifest,$main,$env)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AK could not obtain cached Phase 6AJ-A input: $path"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AK cached Phase 6AJ-A baseline identity mismatch"
}

$aj = $m.phase6aj_d3d_orange_source_probe
if (-not [bool]$aj.probe_only -or
    [bool]$aj.guest_semantics_changed -or
    $aj.phase6ai_hardware.next_boundary.guest -ne "0x80000004") {
    throw "Phase 6AK inherited Phase 6AJ probe model drift"
}

Write-Host "[Phase6AK] CALLER 0023A3CE FORENSIC PREP"
Write-Host "[Phase6AK] Hardware proof : 6AJ-A reached D3D return-path step 10"
Write-Host "[Phase6AK] Boundary caller: 0023A3CE"
Write-Host "[Phase6AK] Boundary read  : READ32 80000004"
Write-Host "[Phase6AK] Target root    : 0028E700 returned before the boundary"
Write-Host "[Phase6AK] Build policy   : no Visual Studio/XEX build in this forensic pass"
Write-Host ""

& $python -m py_compile $inspector
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AK inspector Python syntax check failed"
}
Write-Host "[Phase6AK] Inspector syntax: PASS"

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
    Write-Host "[Phase6AK] FORENSIC PREP FAILED."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 220 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AK caller forensic failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6ak-caller-0023a3ce.txt"
$json = Join-Path $outDir "phase6ak-caller-0023a3ce.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AK forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AK-A" -or
    $r.baseline -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A" -or
    $r.caller -ne "0x0023A3CE" -or
    $r.root -ne "0x0028E700" -or
    $r.hardware.fault -ne "READ32 0x80000004" -or
    [int]$r.hardware.probe_step -ne 10) {
    throw "Phase 6AK forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AK] CALLER FORENSIC PREP: PASS"
Write-Host ("[Phase6AK] Root mentions      : {0}" -f @($r.root_mentions).Count)
Write-Host ("[Phase6AK] Direct call hits   : {0}" -f @($r.direct_call_hits).Count)
Write-Host ("[Phase6AK] EAX+4 read hits    : {0}" -f @($r.eax_plus4_reads).Count)
Write-Host ("[Phase6AK] EAX=80000000 hits  : {0}" -f @($r.eax_80000000_assignments).Count)
Write-Host ("[Phase6AK] Report             : {0}" -f $txt)
Write-Host "[Phase6AK] No XEX was built."
Write-Host "[Phase6AK] SEND/PASTE THE CONSOLE OUTPUT FROM 'CALLER WINDOW 1 BEGIN' THROUGH 'END'."
