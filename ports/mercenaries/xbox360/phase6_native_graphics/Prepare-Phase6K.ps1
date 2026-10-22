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
$baseDir = Join-Path $root "build\phase6_native_graphics\caller_harvest_00063f80_xdk"
$out = Join-Path $root "build\phase6_native_graphics\global_harvest_000d4a30_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6k-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6k_global_harvest.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6K input: $v" }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6j-manifest.json")
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6K fast baseline missing: $f. Keep the successful Phase 6J generated output."
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6j-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6J" -or $baseManifest.build_tag -ne "P6J-CALLER-HARVEST-00063F80-20261022-A") {
    throw "Phase 6K cached Phase 6J baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6K] CACHED GLOBAL-GAP HARVEST"
Write-Host "[Phase6K] Phase 6J hardware boundary: 0023A3CE -> 000D4A30, fault=0"
Write-Host "[Phase6K] FAST BASE: reusing existing Phase 6J generated output"
Write-Host "[Phase6K] Coverage: caller/root closures + stratified global .text reserve"
Write-Host "[Phase6K] Cap: 1536 new support-clean translated members"
Write-Host "[Phase6K] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6K emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6k-manifest.json"
foreach ($f in @($main,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6K missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6K" -or $m.build_tag -ne "P6K-GLOBAL-HARVEST-000D4A30-20261022-A") {
    throw "Phase 6K manifest identity mismatch"
}
$g = $m.phase6k_global_harvest
if ($g.root -ne "0x000D4A30" -or -not [bool]$g.phase6j_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6K manifest gate mismatch"
}

Write-Host ""
Write-Host "[Phase6K] READY"
Write-Host ("[Phase6K] Unpacked caller targets : {0}" -f [int]$g.caller_direct_targets_unpacked)
Write-Host ("[Phase6K] Remaining generated text: {0}" -f [int]$g.remaining_generated_text_members)
Write-Host ("[Phase6K] Global reserve added     : {0}" -f [int]$g.global_reserve_added)
Write-Host ("[Phase6K] Local reserve added      : {0}" -f [int]$g.local_reserve_added)
Write-Host ("[Phase6K] Candidate new members    : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6K] Pruned unsafe members     : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6K] Packed new members        : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6K] Expanded pack members     : {0}" -f [int]$g.expanded_pack_members)
Write-Host "[Phase6K] Root                     : 0x000D4A30"
Write-Host "[Phase6K] Build BOTH fresh sources:"
Write-Host "[Phase6K]   $main"
Write-Host "[Phase6K]   $env"
Write-Host "[Phase6K] Keep d3d9.lib linked."
Write-Host "[Phase6K] Expected tag: P6K-GLOBAL-HARVEST-000D4A30-20261022-A"
Write-Host "[Phase6K] Hardware goal: catch multiple dynamic table targets before the next real boundary."
Write-Host "[Phase6K] Purple = genuine NV2A MMIO/VRAM boundary."
