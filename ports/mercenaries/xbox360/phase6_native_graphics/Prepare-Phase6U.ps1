[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p6 = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseDir = Join-Path $root "build\phase6_native_graphics\dsound_sibling_sweep_002a0164_xdk"
$out = Join-Path $root "build\phase6_native_graphics\title_heap32m_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6u-emitter.log"
$emitter = Join-Path $p6 "emit_phase6u_title_heap32m.py"

foreach ($v in @($python,$emitter)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6U input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6t-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    $baseManifestPath
)

$missingBaseFiles = @(
    $baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) }
)
if ($missingBaseFiles.Count -gt 0) {
    $phase6tPrep = Join-Path $p6 "Prepare-Phase6T.ps1"
    if (-not (Test-Path -LiteralPath $phase6tPrep)) {
        throw "Phase 6U baseline is missing and Phase 6T regeneration script was not found: $phase6tPrep"
    }

    Write-Host "[Phase6U] Cached Phase 6T generated output is missing."
    Write-Host "[Phase6U] Regenerating the exact Phase 6T baseline automatically..."
    & $phase6tPrep

    $missingAfterRegen = @(
        $baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) }
    )
    if ($missingAfterRegen.Count -gt 0) {
        throw ("Phase 6U could not regenerate the Phase 6T baseline. Still missing: " +
            ($missingAfterRegen -join ", "))
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6T" -or
    $baseManifest.build_tag -ne "P6T-DSOUND-SIBLING-SWEEP-002A0164-20261022-A") {
    throw "Phase 6U cached/regenerated Phase 6T baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6U] 32 MiB TITLE-HEAP EXPANSION"
Write-Host "[Phase6U] Phase 6T hardware boundary: HEAP_EXHAUSTED request=012999A0 (~18.6 MiB), fault=0"
Write-Host "[Phase6U] Hardware-proven VM frontier: 03F00000"
Write-Host "[Phase6U] Old heap: 008C0000-009C0000 (1 MiB window)"
Write-Host "[Phase6U] New heap: 008C0000-028C0000 (32 MiB window)"
Write-Host "[Phase6U] Exact Phase 6T translated pack and shards are reused unchanged"
Write-Host "[Phase6U] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $emitter "--base-dir" $baseDir "--out-dir" $out 2>&1 |
        Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}
if ($rc -ne 0) {
    Get-Content $log -Tail 200
    throw "Phase 6U emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6u-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6U missing output: $f"
    }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6U" -or
    $m.build_tag -ne "P6U-TITLE-HEAP32M-20261023-A") {
    throw "Phase 6U manifest identity mismatch"
}

$g = $m.phase6u_title_heap_expansion
if (-not [bool]$g.phase6t_hardware_pass -or
    -not [bool]$g.translated_pack_unchanged -or
    -not [bool]$g.observed_request_fits -or
    $g.new_heap_end -ne "0x028C0000" -or
    $g.proven_vm_frontier -ne "0x03F00000") {
    throw "Phase 6U manifest gate mismatch"
}

$mainText = Get-Content $main -Raw
$envText = Get-Content $env -Raw

if ($mainText -notmatch "P6U-TITLE-HEAP32M-20261023-A") {
    throw "Phase 6U main build tag gate mismatch"
}
if (-not $mainText.Contains(
        "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)")) {
    throw "Phase 6U heap-size source gate mismatch"
}
if ($mainText -notmatch "phase6u_env_build_cookie" -or
    $envText -notmatch "phase6u_env_build_cookie") {
    throw "Phase 6U main/env cookie-symbol gate mismatch"
}
if ($mainText -match "phase6t_env_build_cookie" -or
    $envText -match "phase6t_env_build_cookie") {
    throw "Phase 6U stale Phase 6T cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl")
if ($shards.Count -lt 1) {
    throw "Phase 6U translated shard copy is empty"
}

Write-Host ""
Write-Host "[Phase6U] READY"
Write-Host ("[Phase6U] Observed request bytes       : {0}" -f [int64]$g.phase6t_observed_boundary.requested_bytes)
Write-Host ("[Phase6U] Old heap end                : {0}" -f [string]$g.old_heap_end)
Write-Host ("[Phase6U] New heap end                : {0}" -f [string]$g.new_heap_end)
Write-Host ("[Phase6U] VM frontier                 : {0}" -f [string]$g.proven_vm_frontier)
Write-Host ("[Phase6U] Gap below VM frontier       : {0} bytes" -f [int64]$g.vm_gap_bytes)
Write-Host ("[Phase6U] Reused translated shards    : {0}" -f $shards.Count)
Write-Host "[Phase6U] Build BOTH fresh sources:"
Write-Host "[Phase6U]   $main"
Write-Host "[Phase6U]   $env"
Write-Host "[Phase6U] DO NOT compile main_monolithic.cpp:"
Write-Host "[Phase6U]   $monolithic"
Write-Host "[Phase6U] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6U] Expected tag: P6U-TITLE-HEAP32M-20261023-A"
Write-Host "[Phase6U] Hardware goal: cross the artificial 1 MiB heap ceiling and expose the next real boundary."
