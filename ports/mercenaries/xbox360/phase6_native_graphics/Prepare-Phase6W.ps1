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
$baseDir = Join-Path $root "build\phase6_native_graphics\budget2m_xdk"
$out = Join-Path $root "build\phase6_native_graphics\frontier_0017fe90_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6w-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6w_direct_frontier_0017fe90.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6W input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6v-manifest.json"
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
    $phase6vPrep = Join-Path $p6 "Prepare-Phase6V.ps1"
    if (-not (Test-Path -LiteralPath $phase6vPrep)) {
        throw "Phase 6W baseline is missing and Phase 6V regeneration script was not found: $phase6vPrep"
    }

    Write-Host "[Phase6W] Cached Phase 6V generated output is missing."
    Write-Host "[Phase6W] Regenerating the exact Phase 6V baseline automatically..."
    & $phase6vPrep

    $missingAfterRegen = @(
        $baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) }
    )
    if ($missingAfterRegen.Count -gt 0) {
        throw ("Phase 6W could not regenerate the Phase 6V baseline. Still missing: " +
            ($missingAfterRegen -join ", "))
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6V" -or
    $baseManifest.build_tag -ne "P6V-BUDGET2M-20261023-A") {
    throw "Phase 6W cached/regenerated Phase 6V baseline identity mismatch"
}

$stage3Files = @(
    (Join-Path $stage3 "runtime\gen"),
    (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach ($f in $stage3Files) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6W generated-code analysis input missing: $f"
    }
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6W] DIRECT FRONTIER 0017FE90"
Write-Host "[Phase6W] Phase 6V hardware: DIRECT_FRONTIER 0023A3CE -> 0017FE90"
Write-Host "[Phase6W] Hardware boundary: ticks=670295 trace=179827 fault=0"
Write-Host "[Phase6W] Preflight: inherited 6Q prune table must match exactly two reviewed host helpers"
Write-Host "[Phase6W] Support: canonical fractional frame-tick carry + retail/default freecam tick identity"
Write-Host "[Phase6W] Any changed/additional unresolved helper still hard-stops"
Write-Host "[Phase6W] Then pack root + bounded depth-4/cap-256 generated closure"
Write-Host "[Phase6W] 2M budget + 32 MiB heap remain unchanged"
Write-Host "[Phase6W] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    Write-Host "[Phase6W] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6W] This now means dependency drift, exact-start failure, or another real support blocker."
    Write-Host "[Phase6W] Emitter log tail:"
    Get-Content $log -Tail 80
    throw "Phase 6W emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6w-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6W missing output: $f"
    }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6W" -or
    $m.build_tag -ne "P6W-DIRECT-FRONTIER-0017FE90-20261023-A") {
    throw "Phase 6W manifest identity mismatch"
}

$g = $m.phase6w_direct_frontier
if (-not [bool]$g.phase6v_hardware_pass -or
    $g.root -ne "0x0017FE90" -or
    $g.frontier_caller -ne "0x0023A3CE" -or
    [int]$g.execution_budget_inherited -ne 2000000 -or
    [int]$g.packed_new_members -lt 1) {
    throw "Phase 6W manifest gate mismatch"
}

$mainText = Get-Content $main -Raw
$envText = Get-Content $env -Raw

if (-not $mainText.Contains("P6W-DIRECT-FRONTIER-0017FE90-20261023-A")) {
    throw "Phase 6W build-tag source gate mismatch"
}
if (-not $mainText.Contains("case 0x0017FE90u:")) {
    throw "Phase 6W root dispatch gate missing"
}
if (-not $mainText.Contains("static double recomp_frame_ticks_with_remainder(double ticks)")) {
    throw "Phase 6W fractional frame-tick support body missing"
}
if (-not $mainText.Contains("static uint32_t recomp_freecam_game_ticks(uint32_t ticks)")) {
    throw "Phase 6W retail/default freecam tick support body missing"
}
if (-not $mainText.Contains("#define PHASE4C_EXEC_BUDGET 2000000u")) {
    throw "Phase 6W inherited 2M budget gate mismatch"
}
if (-not $mainText.Contains("#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)")) {
    throw "Phase 6W inherited 32 MiB heap gate mismatch"
}
if ($mainText -notmatch "phase6w_env_build_cookie" -or
    $envText -notmatch "phase6w_env_build_cookie") {
    throw "Phase 6W main/env cookie-symbol gate mismatch"
}
if ($mainText -match "phase6v_env_build_cookie" -or
    $envText -match "phase6v_env_build_cookie") {
    throw "Phase 6W stale Phase 6V cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl")
if ($shards.Count -lt 1) {
    throw "Phase 6W translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6W] READY"
Write-Host ("[Phase6W] Root                         : {0}" -f [string]$g.root)
Write-Host ("[Phase6W] Root name                    : {0}" -f [string]$g.root_name)
Write-Host ("[Phase6W] Candidate new members        : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6W] Pruned unsafe members        : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6W] Packed new members           : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6W] Expanded pack members        : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6W] Generated .inl shards        : {0}" -f $shards.Count)
Write-Host "[Phase6W] Reviewed host support         : frame tick carry + freecam tick identity"
Write-Host "[Phase6W] Build BOTH fresh sources:"
Write-Host "[Phase6W]   $main"
Write-Host "[Phase6W]   $env"
Write-Host "[Phase6W] DO NOT compile main_monolithic.cpp:"
Write-Host "[Phase6W]   $monolithic"
Write-Host "[Phase6W] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6W] Expected tag: P6W-DIRECT-FRONTIER-0017FE90-20261023-A"
Write-Host "[Phase6W] Hardware goal: cross 0017FE90 and expose the next real boundary."
