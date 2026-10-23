[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p6 = $PSScriptRoot
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseDir = Join-Path $root "build\phase6_native_graphics\title_heap32m_xdk"
$out = Join-Path $root "build\phase6_native_graphics\budget2m_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6v-emitter.log"
$emitter = Join-Path $p6 "emit_phase6v_budget2m.py"

foreach ($v in @($python,$emitter)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6V input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6u-manifest.json"
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
    $phase6uPrep = Join-Path $p6 "Prepare-Phase6U.ps1"
    if (-not (Test-Path -LiteralPath $phase6uPrep)) {
        throw "Phase 6V baseline is missing and Phase 6U regeneration script was not found: $phase6uPrep"
    }

    Write-Host "[Phase6V] Cached Phase 6U generated output is missing."
    Write-Host "[Phase6V] Regenerating the exact Phase 6U baseline automatically..."
    & $phase6uPrep

    $missingAfterRegen = @(
        $baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) }
    )
    if ($missingAfterRegen.Count -gt 0) {
        throw ("Phase 6V could not regenerate the Phase 6U baseline. Still missing: " +
            ($missingAfterRegen -join ", "))
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6U" -or
    $baseManifest.build_tag -ne "P6U-TITLE-HEAP32M-20261023-A") {
    throw "Phase 6V cached/regenerated Phase 6U baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6V] 2,000,000-TICK DEEP EXECUTION PASS"
Write-Host "[Phase6V] Phase 6U hardware: 18.6 MiB heap allocation succeeded; next stop=BUDGET at 600001, fault=0"
Write-Host "[Phase6V] Exact Phase 6U translated pack, shards, and 32 MiB heap are reused unchanged"
Write-Host "[Phase6V] Only change: PHASE4C_EXEC_BUDGET 600000 -> 2000000"
Write-Host "[Phase6V] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6V emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6v-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6V missing output: $f"
    }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6V" -or
    $m.build_tag -ne "P6V-BUDGET2M-20261023-A") {
    throw "Phase 6V manifest identity mismatch"
}

$g = $m.phase6v_deep_budget
if (-not [bool]$g.phase6u_hardware_pass -or
    -not [bool]$g.translated_pack_unchanged -or
    -not [bool]$g.heap_geometry_unchanged -or
    [int]$g.old_budget_ticks -ne 600000 -or
    [int]$g.new_budget_ticks -ne 2000000) {
    throw "Phase 6V manifest gate mismatch"
}

$mainText = Get-Content $main -Raw
$envText = Get-Content $env -Raw

if (-not $mainText.Contains("P6V-BUDGET2M-20261023-A")) {
    throw "Phase 6V main build tag gate mismatch"
}
if (-not $mainText.Contains("#define PHASE4C_EXEC_BUDGET 2000000u")) {
    throw "Phase 6V execution-budget source gate mismatch"
}
if (-not $mainText.Contains("#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)")) {
    throw "Phase 6V inherited 32 MiB heap gate mismatch"
}
if ($mainText -notmatch "phase6v_env_build_cookie" -or
    $envText -notmatch "phase6v_env_build_cookie") {
    throw "Phase 6V main/env cookie-symbol gate mismatch"
}
if ($mainText -match "phase6u_env_build_cookie" -or
    $envText -match "phase6u_env_build_cookie") {
    throw "Phase 6V stale Phase 6U cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl")
if ($shards.Count -lt 1) {
    throw "Phase 6V translated shard copy is empty"
}

Write-Host ""
Write-Host "[Phase6V] READY"
Write-Host ("[Phase6V] Prior boundary               : {0}" -f [string]$g.phase6u_observed_boundary.kind)
Write-Host ("[Phase6V] Prior target                 : {0}" -f [string]$g.phase6u_observed_boundary.target)
Write-Host ("[Phase6V] Old budget                   : {0}" -f [int]$g.old_budget_ticks)
Write-Host ("[Phase6V] New budget                   : {0}" -f [int]$g.new_budget_ticks)
Write-Host ("[Phase6V] Large heap allocation result : {0}" -f [string]$g.phase6u_large_heap_request.result)
Write-Host ("[Phase6V] Reused translated shards     : {0}" -f $shards.Count)
Write-Host "[Phase6V] Build BOTH fresh sources:"
Write-Host "[Phase6V]   $main"
Write-Host "[Phase6V]   $env"
Write-Host "[Phase6V] DO NOT compile main_monolithic.cpp:"
Write-Host "[Phase6V]   $monolithic"
Write-Host "[Phase6V] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6V] Expected tag: P6V-BUDGET2M-20261023-A"
Write-Host "[Phase6V] Hardware goal: let the post-allocation translated initialization finish and expose the next real boundary."
