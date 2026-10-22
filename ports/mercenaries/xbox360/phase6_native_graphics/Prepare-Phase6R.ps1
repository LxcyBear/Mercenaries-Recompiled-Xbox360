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
$baseDir = Join-Path $root "build\phase6_native_graphics\safe_saturation_001f9fd0_xdk"
$out = Join-Path $root "build\phase6_native_graphics\xpp_frontier_002d66a2_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6r-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6r_xpp_frontier.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6R input: $v" }
}

$baseManifestPath = Join-Path $baseDir "phase6q-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6R fast baseline missing: $f. Keep the successful Phase 6Q generated output."
    }
}

$baseManifest = Get-Content $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6Q" -or $baseManifest.build_tag -ne "P6Q-SAFE-TEXT-SATURATION-001F9FD0-20261022-A") {
    throw "Phase 6R cached Phase 6Q baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6R] EXACT XPP FRONTIER RESOLVER"
Write-Host "[Phase6R] Phase 6Q hardware boundary: ICALL_SAFE 0023A3CE -> 002D66A2, fault=0"
Write-Host "[Phase6R] Target section: XPP 002D4300-002DBCC8"
Write-Host "[Phase6R] FAST BASE: reusing hardware-proven Phase 6Q saturation cache"
Write-Host "[Phase6R] Scope: exact 002D66A2 + generated depth-2/cap-64 closure only"
Write-Host "[Phase6R] Support: inherited native cos()/sin(); all other unresolved support fenced"
Write-Host "[Phase6R] Interior XPP entries are NOT redirected to function starts"
Write-Host "[Phase6R] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6R emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6r-manifest.json"
foreach ($f in @($main,$monolithic,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6R missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6R" -or $m.build_tag -ne "P6R-XPP-FRONTIER-002D66A2-20261022-A") {
    throw "Phase 6R manifest identity mismatch"
}
$g = $m.phase6r_xpp_frontier
if ($g.root -ne "0x002D66A2" -or $g.target_section -ne "XPP" -or -not [bool]$g.phase6q_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6R manifest gate mismatch"
}
$crtSupport = @($g.phase_owned_crt_support)
if ($crtSupport.Count -ne 2 -or $crtSupport[0] -ne "cos" -or $crtSupport[1] -ne "sin") {
    throw "Phase 6R CRT support gate mismatch"
}

if ($null -eq $g.source_layout -or [int]$g.source_layout.shard_count -lt 1) {
    throw "Phase 6R source-shard manifest gate mismatch"
}
$shardDir = Join-Path $out ([string]$g.source_layout.shard_directory)
if (-not (Test-Path -LiteralPath $shardDir)) {
    throw "Phase 6R translated shard directory missing: $shardDir"
}

Write-Host ""
Write-Host "[Phase6R] READY"
Write-Host ("[Phase6R] XPP root                  : {0}" -f [string]$g.root)
Write-Host ("[Phase6R] Root name                 : {0}" -f [string]$g.root_name)
Write-Host ("[Phase6R] Candidate new members     : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6R] Pruned unsafe members     : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6R] Packed new members        : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6R] Expanded pack members     : {0}" -f [int]$g.expanded_pack_members)
Write-Host ("[Phase6R] VS wrapper lines          : {0}" -f [int]$g.source_layout.wrapper_lines)
Write-Host ("[Phase6R] Translated body lines     : {0}" -f [int]$g.source_layout.body_lines)
Write-Host ("[Phase6R] Generated .inl shards     : {0}" -f [int]$g.source_layout.shard_count)
Write-Host "[Phase6R] Build BOTH fresh sources:"
Write-Host "[Phase6R]   $main   (small VS-friendly wrapper)"
Write-Host "[Phase6R]   $env"
Write-Host "[Phase6R] DO NOT add/compile main_monolithic.cpp; emitter cache only:"
Write-Host "[Phase6R]   $monolithic"
Write-Host "[Phase6R] Keep translated_shards beside main.cpp and d3d9.lib linked."
Write-Host "[Phase6R] Expected tag: P6R-XPP-FRONTIER-002D66A2-20261022-A"
Write-Host "[Phase6R] Hardware goal: cross the first post-saturation XPP call safely and expose the next real subsystem boundary."
Write-Host "[Phase6R] Purple = genuine NV2A MMIO/VRAM boundary."
