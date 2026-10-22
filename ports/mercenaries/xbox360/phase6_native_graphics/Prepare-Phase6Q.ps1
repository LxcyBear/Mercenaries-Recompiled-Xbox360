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
$baseDir = Join-Path $root "build\phase6_native_graphics\budget600k_xdk"
$out = Join-Path $root "build\phase6_native_graphics\safe_saturation_001f9fd0_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6q-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6q_safe_text_saturation.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6O input: $v" }
}

$baseManifestPath = Join-Path $baseDir "phase6p-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6O fast baseline missing: $f. Keep the successful Phase 6P generated output."
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6P" -or $baseManifest.build_tag -ne "P6P-BUDGET600K-20261022-A") {
    throw "Phase 6O cached Phase 6P baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6Q] CACHED SAFE-TEXT SATURATION"
Write-Host "[Phase6Q] Phase 6P hardware boundary: DIRECT_FRONTIER 0023A3CE -> 001F9FD0, fault=0"
Write-Host "[Phase6Q] FAST BASE: reusing existing Phase 6P 600k-budget monolithic cache"
Write-Host "[Phase6Q] Coverage: mandatory 001F9FD0 + caller/root closures + every remaining support-clean generated .text member"
Write-Host "[Phase6Q] Safety cap: 4096 candidate members; unresolved support still pruned"
Write-Host "[Phase6Q] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6O emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6q-manifest.json"
foreach ($f in @($main,$monolithic,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6O missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6Q" -or $m.build_tag -ne "P6Q-SAFE-TEXT-SATURATION-001F9FD0-20261022-A") {
    throw "Phase 6O manifest identity mismatch"
}
$g = $m.phase6q_safe_text_saturation
if ($g.root -ne "0x001F9FD0" -or -not [bool]$g.phase6p_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6O manifest gate mismatch"
}

if ($null -eq $g.source_layout -or [int]$g.source_layout.shard_count -lt 1) {
    throw "Phase 6O source-shard manifest gate mismatch"
}
$shardDir = Join-Path $out ([string]$g.source_layout.shard_directory)
if (-not (Test-Path -LiteralPath $shardDir)) {
    throw "Phase 6O translated shard directory missing: $shardDir"
}

Write-Host ""
Write-Host "[Phase6Q] READY"
Write-Host ("[Phase6Q] Unpacked caller targets : {0}" -f [int]$g.caller_direct_targets_unpacked)
Write-Host ("[Phase6Q] Remaining generated text: {0}" -f [int]$g.remaining_generated_text_members)
Write-Host ("[Phase6Q] Remaining safe candidates: {0}" -f [int]$g.remaining_after_support_clean)
Write-Host ("[Phase6Q] Candidate new members    : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6Q] Pruned unsafe members     : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6Q] Packed new members        : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6Q] Expanded pack members     : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6Q] VS wrapper lines          : {0}" -f [int]$g.source_layout.wrapper_lines)
Write-Host ("[Phase6Q] Translated body lines     : {0}" -f [int]$g.source_layout.body_lines)
Write-Host ("[Phase6Q] Generated .inl shards     : {0}" -f [int]$g.source_layout.shard_count)
Write-Host "[Phase6Q] Root                     : 0x001F9FD0"
Write-Host "[Phase6Q] Build BOTH fresh sources:"
Write-Host "[Phase6Q]   $main   (small VS-friendly wrapper)"
Write-Host "[Phase6Q]   $env"
Write-Host "[Phase6Q] DO NOT add/compile main_monolithic.cpp; it is emitter cache only:"
Write-Host "[Phase6Q]   $monolithic"
Write-Host "[Phase6Q] Keep the translated_shards folder beside main.cpp."
Write-Host "[Phase6Q] Keep d3d9.lib linked."
Write-Host "[Phase6Q] Expected tag: P6Q-SAFE-TEXT-SATURATION-001F9FD0-20261022-A"
Write-Host "[Phase6Q] Hardware goal: eliminate ordinary generated-body coverage and expose the next semantic/platform boundary."
Write-Host "[Phase6Q] Purple = genuine NV2A MMIO/VRAM boundary."
