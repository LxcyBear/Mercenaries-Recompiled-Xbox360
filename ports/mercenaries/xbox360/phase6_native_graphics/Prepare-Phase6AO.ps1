[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$inspector = Join-Path $PSScriptRoot "inspect_phase6ao_d3d_stack_writers.py"
$prep6aj = Join-Path $PSScriptRoot "Prepare-Phase6AJ.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6ao_d3d_stack_writer_audit"
$log = Join-Path $root "build\phase6_native_graphics\phase6ao-d3d-stack-writer-audit.log"

$manifest = Join-Path $baseDir "phase6aj-manifest.json"
$main = Join-Path $baseDir "main_monolithic.cpp"
$env = Join-Path $baseDir "phase5_env.cpp"

foreach ($path in @($python,$baseEmitter,$inspector,$prep6aj)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AO input: $path"
    }
}

if (-not (Test-Path -LiteralPath $manifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $main -PathType Leaf) -or
    -not (Test-Path -LiteralPath $env -PathType Leaf)) {
    Write-Host "[Phase6AO] Cached Phase 6AJ-A source output is missing."
    Write-Host "[Phase6AO] Regenerating 6AJ-A sources only; VS2017 remains skipped."
    & $prep6aj -SkipSolutionBuild
}

foreach ($path in @($manifest,$main,$env)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AO could not obtain cached Phase 6AJ-A input: $path"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AO cached Phase 6AJ-A baseline identity mismatch"
}

Write-Host "[Phase6AO] EXACT D3D +1A10 STACK WRITER AUDIT"
Write-Host "[Phase6AO] 6AN-B hardware     : count=0, loop underflow, sentinel hit"
Write-Host "[Phase6AO] Fault source       : sub_0028BC60 -> GUEST_READ32(eax + 4)"
Write-Host "[Phase6AO] Audit goal         : find exact stack initialization/writers"
Write-Host "[Phase6AO] Build policy       : PC-only, no Visual Studio/XEX build"
Write-Host ""

& $python -m py_compile $inspector
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AO inspector Python syntax check failed"
}
Write-Host "[Phase6AO] Inspector syntax   : PASS"

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
    Write-Host "[Phase6AO] FORENSIC AUDIT FAILED."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 300 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AO D3D stack writer audit failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6ao-d3d-stack-writer-audit.txt"
$json = Join-Path $outDir "phase6ao-d3d-stack-writer-audit.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AO forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AO-A" -or
    $r.baseline -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A" -or
    $r.hardware.device -ne "0x00299380" -or
    $r.hardware.target -ne "0x0028BC60" -or
    $r.hardware.fault -ne "READ32 0x80000004" -or
    [int]$r.hardware.count -ne 0) {
    throw "Phase 6AO forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AO] D3D STACK WRITER AUDIT: PASS"
Write-Host ("[Phase6AO] References      : {0}" -f @($r.references).Count)
Write-Host ("[Phase6AO] Stack writes    : {0}" -f @($r.stack_writes).Count)
Write-Host ("[Phase6AO] Direct callers  : {0}" -f @($r.direct_callers).Count)
Write-Host ("[Phase6AO] Report          : {0}" -f $txt)
Write-Host "[Phase6AO] No XEX was built."
Write-Host "[Phase6AO] SEND/PASTE FROM 'STACK WRITES BEGIN' THROUGH THE FINAL 'WINDOW ... END'."
