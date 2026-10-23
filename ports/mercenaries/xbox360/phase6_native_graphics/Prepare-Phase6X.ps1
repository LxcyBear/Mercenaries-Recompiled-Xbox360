[CmdletBinding()]
param()
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p6 = $PSScriptRoot
$p5 = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$p4 = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python = Join-Path $root ".venv\Scripts\python.exe"
$stage3 = Join-Path $root "build\phase3n_final_abi_scale"
$baseDir = Join-Path $root "build\phase6_native_graphics\frontier_0017fe90_xdk"
$out = Join-Path $root "build\phase6_native_graphics\graphics_pool_frontier_0020f9c0_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6x-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6x_graphics_pool_frontier_0020f9c0.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6X input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6w-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    $baseManifestPath
)

$missingBaseFiles = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingBaseFiles.Count -gt 0) {
    $phase6wPrep = Join-Path $p6 "Prepare-Phase6W.ps1"
    if (-not (Test-Path -LiteralPath $phase6wPrep)) {
        throw "Phase 6X baseline is missing and Phase 6W regeneration script was not found: $phase6wPrep"
    }

    Write-Host "[Phase6X] Cached Phase 6W generated output is missing."
    Write-Host "[Phase6X] Regenerating the exact Phase 6W baseline automatically..."
    & $phase6wPrep

    $missingAfterRegen = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
    if ($missingAfterRegen.Count -gt 0) {
        throw ("Phase 6X could not regenerate the Phase 6W baseline. Still missing: " +
            ($missingAfterRegen -join ", "))
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6W" -or
    $baseManifest.build_tag -ne "P6W-DIRECT-FRONTIER-0017FE90-20261023-A") {
    throw "Phase 6X cached/regenerated Phase 6W baseline identity mismatch"
}

$stage3Files = @(
    (Join-Path $stage3 "runtime\gen"),
    (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach ($f in $stage3Files) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6X generated-code analysis input missing: $f"
    }
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6X] GRAPHICS-POOL FRONTIER 0020F9C0"
Write-Host "[Phase6X] Phase 6W hardware: DIRECT_FRONTIER 0023A3CE -> 0020F9C0"
Write-Host "[Phase6X] Hardware boundary: ticks=670776 trace=179920 fault=0"
Write-Host "[Phase6X] Upstream role: sub_0020F9C0 initializes the retail graphics pool"
Write-Host "[Phase6X] Upstream optional extended-graphics patch sites: 0020F9C0 / 0020F9D3"
Write-Host "[Phase6X] Local generated body remains authoritative; unresolved support still hard-stops"
Write-Host "[Phase6X] Pack root + bounded depth-4/cap-256 generated closure"
Write-Host "[Phase6X] Inherit Phase 6W timing helpers + 2M budget + 32 MiB title heap"
Write-Host "[Phase6X] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--base-phase5bb-emitter",$paths.bb,
    "--base-phase5bc-emitter",$paths.bc,
    "--generated-root",(Join-Path $stage3 "runtime\gen"),
    "--functions",(Join-Path $stage3 "analysis\disasm\functions.json"),
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $paths.emitter @args 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6X] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6X] This means exact-start failure or a real unresolved support dependency."
    Write-Host "[Phase6X] Emitter log tail:"
    Get-Content $log -Tail 100
    throw "Phase 6X emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6x-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6X missing output: $f"
    }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6X" -or
    $m.build_tag -ne "P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A") {
    throw "Phase 6X manifest identity mismatch"
}

$g = $m.phase6x_graphics_pool_frontier
if (-not [bool]$g.phase6w_hardware_pass -or
    $g.root -ne "0x0020F9C0" -or
    $g.frontier_caller -ne "0x0023A3CE" -or
    [int]$g.execution_budget_inherited -ne 2000000 -or
    -not [bool]$g.reviewed_phase6w_timing_support_inherited -or
    [int]$g.packed_new_members -lt 1) {
    throw "Phase 6X manifest gate mismatch"
}

$mainText = Get-Content $main -Raw
$envText = Get-Content $env -Raw

if (-not $mainText.Contains("P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A")) {
    throw "Phase 6X build-tag source gate mismatch"
}
if (-not $mainText.Contains("case 0x0020F9C0u:")) {
    throw "Phase 6X graphics-pool root dispatch gate missing"
}
if (-not $mainText.Contains("static double recomp_frame_ticks_with_remainder(double ticks)")) {
    throw "Phase 6X inherited fractional frame-tick support missing"
}
if (-not $mainText.Contains("static uint32_t recomp_freecam_game_ticks(uint32_t ticks)")) {
    throw "Phase 6X inherited retail/default freecam tick support missing"
}
if (-not $mainText.Contains("#define PHASE4C_EXEC_BUDGET 2000000u")) {
    throw "Phase 6X inherited 2M budget gate mismatch"
}
if (-not $mainText.Contains("#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)")) {
    throw "Phase 6X inherited 32 MiB heap gate mismatch"
}
if ($mainText -notmatch "phase6x_env_build_cookie" -or
    $envText -notmatch "phase6x_env_build_cookie") {
    throw "Phase 6X main/env cookie-symbol gate mismatch"
}
if ($mainText -match "phase6w_env_build_cookie" -or
    $envText -match "phase6w_env_build_cookie") {
    throw "Phase 6X stale Phase 6W cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl")
if ($shards.Count -lt 1) {
    throw "Phase 6X translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6X] READY"
Write-Host ("[Phase6X] Root                         : {0}" -f [string]$g.root)
Write-Host ("[Phase6X] Root name                    : {0}" -f [string]$g.root_name)
Write-Host ("[Phase6X] Candidate new members        : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6X] Pruned unsafe members        : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6X] Packed new members           : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6X] Expanded pack members        : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6X] Generated .inl shards        : {0}" -f $shards.Count)
Write-Host "[Phase6X] Upstream role                 : retail graphics-pool initialization"
Write-Host "[Phase6X] Reviewed Phase 6W support     : inherited unchanged"
Write-Host "[Phase6X] Build BOTH fresh sources:"
Write-Host "[Phase6X]   $main"
Write-Host "[Phase6X]   $env"
Write-Host "[Phase6X] DO NOT compile main_monolithic.cpp:"
Write-Host "[Phase6X]   $monolithic"
Write-Host "[Phase6X] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6X] Expected tag: P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A"
Write-Host "[Phase6X] Hardware goal: cross graphics-pool init and expose the next real renderer/platform boundary."
