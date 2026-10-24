[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python = Join-Path $root ".venv\Scripts\python.exe"
$inspector = Join-Path $PSScriptRoot "inspect_phase6as_contiguous_allocator.py"
$baseDir = Join-Path $root "build\phase6_native_graphics\post_create_state_init_xdk"
$outDir = Join-Path $root "build\phase6_native_graphics\phase6as_contiguous_allocator_audit"
$log = Join-Path $root "build\phase6_native_graphics\phase6as-contiguous-allocator-audit.log"

$manifest = Join-Path $baseDir "phase6ar-manifest.json"
$main = Join-Path $baseDir "main_monolithic.cpp"

foreach ($path in @($python,$inspector,$manifest,$main)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AS input: $path"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AR" -or
    $m.build_tag -ne "P6AR-POST-CREATE-STATE-INIT-20261024-A") {
    throw "Phase 6AS cached Phase 6AR-A identity mismatch"
}

Write-Host "[Phase6AS] CONTIGUOUS ALLOCATOR POLICY AUDIT"
Write-Host "[Phase6AS] 6AR hardware       : orange READ32 gone, state count 0 -> 2"
Write-Host "[Phase6AS] New boundary       : renderer fatal hr=8007000E"
Write-Host "[Phase6AS] Graphics claim     : 02880000 + 01680000 -> 03F00000"
Write-Host "[Phase6AS] Follow-up request  : 00258000 bytes -> base 00000000"
Write-Host "[Phase6AS] Build policy       : PC-only, no Visual Studio/XEX build"
Write-Host ""

& $python -m py_compile $inspector
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AS inspector Python syntax check failed"
}
Write-Host "[Phase6AS] Inspector syntax   : PASS"

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

$argsList = @(
    "--base-dir",$baseDir,
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
    Write-Host "[Phase6AS] FORENSIC AUDIT FAILED."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 320 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AS contiguous allocator audit failed (exit $rc)"
}

$txt = Join-Path $outDir "phase6as-contiguous-allocator-audit.txt"
$json = Join-Path $outDir "phase6as-contiguous-allocator-audit.json"
foreach ($path in @($txt,$json)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AS forensic output missing: $path"
    }
}

$r = Get-Content -LiteralPath $json -Raw | ConvertFrom-Json
if ($r.phase -ne "6AS-A" -or
    $r.baseline -ne "P6AR-POST-CREATE-STATE-INIT-20261024-A" -or
    $r.hardware.initializer_hresult -ne "0x8007000E" -or
    [int]$r.hardware.count_after -ne 2) {
    throw "Phase 6AS forensic report identity mismatch"
}

Write-Host ""
Write-Host "[Phase6AS] CONTIGUOUS ALLOCATOR AUDIT: PASS"
Write-Host ("[Phase6AS] Marker hits       : {0}" -f @($r.marker_hits).Count)
Write-Host ("[Phase6AS] Window groups     : {0}" -f @($r.window_groups).Count)
Write-Host ("[Phase6AS] Allocator symbols : {0}" -f @($r.allocator_symbols).Count)
Write-Host ("[Phase6AS] Report            : {0}" -f $txt)
Write-Host "[Phase6AS] No XEX was built."
Write-Host "[Phase6AS] SEND/PASTE FROM 'MARKER SUMMARY BEGIN' THROUGH 'STATE SYMBOLS END'."
