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
$baseDir = Join-Path $root "build\phase6_native_graphics\global_harvest_00179850_xdk"
$out = Join-Path $root "build\phase6_native_graphics\global_harvest_00222b20_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6n-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6n_global_harvest.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6N input: $v" }
}

$baseManifestPath = Join-Path $baseDir "phase6m-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6N fast baseline missing: $f. Keep the successful Phase 6M generated output."
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6M" -or $baseManifest.build_tag -ne "P6M-GLOBAL-HARVEST-00179850-20261022-A") {
    throw "Phase 6N cached Phase 6M baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6N] CACHED GLOBAL-GAP HARVEST"
Write-Host "[Phase6N] Phase 6M hardware boundary: 0023A3CE -> 00222B20, fault=0"
Write-Host "[Phase6N] FAST BASE: reusing existing Phase 6M monolithic cache"
Write-Host "[Phase6N] Coverage: caller/root closures + stratified global .text reserve"
Write-Host "[Phase6N] Cap: 1536 new support-clean translated members"
Write-Host "[Phase6N] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    Get-Content $log -Tail 200
    throw "Phase 6N emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6n-manifest.json"
foreach ($f in @($main,$monolithic,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6N missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6N" -or $m.build_tag -ne "P6N-GLOBAL-HARVEST-00222B20-20261022-A") {
    throw "Phase 6N manifest identity mismatch"
}
$g = $m.phase6n_global_harvest
if ($g.root -ne "0x00222B20" -or -not [bool]$g.phase6m_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6N manifest gate mismatch"
}

if ($null -eq $g.source_layout -or [int]$g.source_layout.shard_count -lt 1) {
    throw "Phase 6N source-shard manifest gate mismatch"
}
$shardDir = Join-Path $out ([string]$g.source_layout.shard_directory)
if (-not (Test-Path -LiteralPath $shardDir)) {
    throw "Phase 6N translated shard directory missing: $shardDir"
}

Write-Host ""
Write-Host "[Phase6N] READY"
Write-Host ("[Phase6N] Unpacked caller targets : {0}" -f [int]$g.caller_direct_targets_unpacked)
Write-Host ("[Phase6N] Remaining generated text: {0}" -f [int]$g.remaining_generated_text_members)
Write-Host ("[Phase6N] Global reserve added     : {0}" -f [int]$g.global_reserve_added)
Write-Host ("[Phase6N] Local reserve added      : {0}" -f [int]$g.local_reserve_added)
Write-Host ("[Phase6N] Candidate new members    : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6N] Pruned unsafe members     : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6N] Packed new members        : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6N] Expanded pack members     : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6N] VS wrapper lines          : {0}" -f [int]$g.source_layout.wrapper_lines)
Write-Host ("[Phase6N] Translated body lines     : {0}" -f [int]$g.source_layout.body_lines)
Write-Host ("[Phase6N] Generated .inl shards     : {0}" -f [int]$g.source_layout.shard_count)
Write-Host "[Phase6N] Root                     : 0x00222B20"
Write-Host "[Phase6N] Build BOTH fresh sources:"
Write-Host "[Phase6N]   $main   (small VS-friendly wrapper)"
Write-Host "[Phase6N]   $env"
Write-Host "[Phase6N] DO NOT add/compile main_monolithic.cpp; it is emitter cache only:"
Write-Host "[Phase6N]   $monolithic"
Write-Host "[Phase6N] Keep the translated_shards folder beside main.cpp."
Write-Host "[Phase6N] Keep d3d9.lib linked."
Write-Host "[Phase6N] Expected tag: P6N-GLOBAL-HARVEST-00222B20-20261022-A"
Write-Host "[Phase6N] Hardware goal: catch multiple dynamic table targets before the next real boundary."
Write-Host "[Phase6N] Purple = genuine NV2A MMIO/VRAM boundary."
