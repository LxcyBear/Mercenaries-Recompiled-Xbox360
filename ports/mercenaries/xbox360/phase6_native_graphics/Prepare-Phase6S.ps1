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
$baseDir = Join-Path $root "build\phase6_native_graphics\xpp_frontier_002d66a2_xdk"
$out = Join-Path $root "build\phase6_native_graphics\dsound_frontier_002a0159_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6s-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6s_dsound_frontier.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6S input: $v" }
}

$baseManifestPath = Join-Path $baseDir "phase6r-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6S fast baseline missing: $f. Keep the successful Phase 6R generated output."
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6R" -or $baseManifest.build_tag -ne "P6R-XPP-FRONTIER-002D66A2-20261022-A") {
    throw "Phase 6S cached Phase 6R baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6S] BATCHED DSOUND FRONTIER RESOLVER"
Write-Host "[Phase6S] Phase 6R hardware boundary: ICALL_SAFE 0023A3CE -> 002A0159, fault=0"
Write-Host "[Phase6S] Target section: DSOUND 0029CB80-002BB274"
Write-Host "[Phase6S] FAST BASE: reusing hardware-proven Phase 6R XPP cache"
Write-Host "[Phase6S] Scope: exact 002A0159 + generated depth-4/cap-256 closure"
Write-Host "[Phase6S] Support: inherited native cos()/sin(); all other unresolved support fenced"
Write-Host "[Phase6S] Interior DSOUND entries are NOT redirected to function starts"
Write-Host "[Phase6S] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6S emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6s-manifest.json"
foreach ($f in @($main,$monolithic,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6S missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6S" -or $m.build_tag -ne "P6S-DSOUND-FRONTIER-002A0159-20261022-A") {
    throw "Phase 6S manifest identity mismatch"
}
$g = $m.phase6s_dsound_frontier
if ($g.root -ne "0x002A0159" -or $g.target_section -ne "DSOUND" -or -not [bool]$g.phase6r_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6S manifest gate mismatch"
}
$crtSupport = @($g.phase_owned_crt_support)
if ($crtSupport.Count -ne 2 -or $crtSupport[0] -ne "cos" -or $crtSupport[1] -ne "sin") {
    throw "Phase 6S CRT support gate mismatch"
}

if ($null -eq $g.source_layout -or [int]$g.source_layout.shard_count -lt 1) {
    throw "Phase 6S source-shard manifest gate mismatch"
}
$shardDir = Join-Path $out ([string]$g.source_layout.shard_directory)
if (-not (Test-Path -LiteralPath $shardDir)) {
    throw "Phase 6S translated shard directory missing: $shardDir"
}

Write-Host ""
Write-Host "[Phase6S] READY"
Write-Host ("[Phase6S] DSOUND root                  : {0}" -f [string]$g.root)
Write-Host ("[Phase6S] Root name                 : {0}" -f [string]$g.root_name)
Write-Host ("[Phase6S] Candidate new members     : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6S] Pruned unsafe members     : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6S] Packed new members        : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6S] Expanded pack members     : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6S] VS wrapper lines          : {0}" -f [int]$g.source_layout.wrapper_lines)
Write-Host ("[Phase6S] Translated body lines     : {0}" -f [int]$g.source_layout.body_lines)
Write-Host ("[Phase6S] Generated .inl shards     : {0}" -f [int]$g.source_layout.shard_count)
Write-Host "[Phase6S] Build BOTH fresh sources:"
Write-Host "[Phase6S]   $main   (small VS-friendly wrapper)"
Write-Host "[Phase6S]   $env"
Write-Host "[Phase6S] DO NOT add/compile main_monolithic.cpp; emitter cache only:"
Write-Host "[Phase6S]   $monolithic"
Write-Host "[Phase6S] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6S] Expected tag: P6R-XPP-FRONTIER-002D66A2-20261022-A"
Write-Host "[Phase6S] Hardware goal: cross the first DSOUND frontier with a larger safe batch and expose the next real subsystem boundary."
Write-Host "[Phase6S] Purple = genuine NV2A MMIO/VRAM boundary."
