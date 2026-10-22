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
$baseDir = Join-Path $root "build\phase6_native_graphics\dsound_frontier_002a0159_xdk"
$out = Join-Path $root "build\phase6_native_graphics\dsound_sibling_sweep_002a0164_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6t-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6t_dsound_sibling_sweep.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6S input: $v" }
}

$baseManifestPath = Join-Path $baseDir "phase6s-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6S fast baseline missing: $f. Keep the successful Phase 6S generated output."
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6S" -or $baseManifest.build_tag -ne "P6S-DSOUND-FRONTIER-002A0159-20261022-A") {
    throw "Phase 6S cached Phase 6S baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6T] BROAD DSOUND SIBLING SWEEP"
Write-Host "[Phase6T] Phase 6S hardware boundary: ICALL_SAFE 0023A3CE -> 002A0164, fault=0"
Write-Host "[Phase6T] Target section: DSOUND 0029CB80-002BB274"
Write-Host "[Phase6T] FAST BASE: reusing hardware-proven Phase 6S DSOUND cache"
Write-Host "[Phase6T] Scope: exact generated DSOUND sibling starts from 002A0164 forward, cap=1024"
Write-Host "[Phase6T] Support: inherited native cos()/sin(); all other unresolved support fenced"
Write-Host "[Phase6T] Interior DSOUND entries are NOT redirected; unsupported siblings are pruned"
Write-Host "[Phase6T] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6T emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6t-manifest.json"
foreach ($f in @($main,$monolithic,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6T missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6T" -or $m.build_tag -ne "P6T-DSOUND-SIBLING-SWEEP-002A0164-20261022-A") {
    throw "Phase 6T manifest identity mismatch"
}
$g = $m.phase6t_dsound_sibling_sweep
if ($g.root -ne "0x002A0164" -or $g.target_section -ne "DSOUND" -or -not [bool]$g.phase6s_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6T manifest gate mismatch"
}
$crtSupport = @($g.phase_owned_crt_support)
if ($crtSupport.Count -ne 2 -or $crtSupport[0] -ne "cos" -or $crtSupport[1] -ne "sin") {
    throw "Phase 6T CRT support gate mismatch"
}

if ($null -eq $g.source_layout -or [int]$g.source_layout.shard_count -lt 1) {
    throw "Phase 6T source-shard manifest gate mismatch"
}
$shardDir = Join-Path $out ([string]$g.source_layout.shard_directory)
if (-not (Test-Path -LiteralPath $shardDir)) {
    throw "Phase 6T translated shard directory missing: $shardDir"
}

Write-Host ""
Write-Host "[Phase6T] READY"
Write-Host ("[Phase6T] DSOUND root                  : {0}" -f [string]$g.root)
Write-Host ("[Phase6T] Root name                 : {0}" -f [string]$g.root_name)
Write-Host ("[Phase6T] Generated DSOUND members    : {0}" -f [int]$g.total_generated_dsound_members)
Write-Host ("[Phase6T] Remaining DSOUND members    : {0}" -f [int]$g.remaining_generated_dsound_members)
Write-Host ("[Phase6T] Selected sibling candidates : {0}" -f [int]$g.selected_candidate_members)
Write-Host ("[Phase6T] Truncated by 1024 cap       : {0}" -f [int]$g.truncated_candidate_members)
Write-Host ("[Phase6T] Candidate new members       : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6T] Pruned unsafe members     : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6T] Packed new members        : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6T] Expanded pack members     : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6T] VS wrapper lines          : {0}" -f [int]$g.source_layout.wrapper_lines)
Write-Host ("[Phase6T] Translated body lines     : {0}" -f [int]$g.source_layout.body_lines)
Write-Host ("[Phase6T] Generated .inl shards     : {0}" -f [int]$g.source_layout.shard_count)
Write-Host "[Phase6T] Build BOTH fresh sources:"
Write-Host "[Phase6T]   $main   (small VS-friendly wrapper)"
Write-Host "[Phase6T]   $env"
Write-Host "[Phase6T] DO NOT add/compile main_monolithic.cpp; emitter cache only:"
Write-Host "[Phase6T]   $monolithic"
Write-Host "[Phase6T] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6T] Expected tag: P6T-DSOUND-SIBLING-SWEEP-002A0164-20261022-A"
Write-Host "[Phase6T] Hardware goal: sweep a broad support-clean batch of DSOUND sibling entrypoints and expose the next real subsystem boundary."
Write-Host "[Phase6T] Purple = genuine NV2A MMIO/VRAM boundary."
