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
$baseDir = Join-Path $root "build\phase6_native_graphics\caller_harvest_00015b30_xdk"
$out = Join-Path $root "build\phase6_native_graphics\caller_harvest_00202680_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6i-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6i_caller_harvest.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6I input: $v" }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6h-manifest.json")
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6I fast baseline missing: $f. Keep the successful Phase 6H generated output."
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6h-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6H" -or $baseManifest.build_tag -ne "P6H-CALLER-HARVEST-00015B30-20261022-A") {
    throw "Phase 6I cached Phase 6H baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6I] CACHED CALLER-CLOSURE HARVEST"
Write-Host "[Phase6I] Phase 6H hardware boundary: 0023A3CE -> 00202680, fault=0"
Write-Host "[Phase6I] FAST BASE: reusing existing Phase 6H generated output"
Write-Host "[Phase6I] HARVEST: remaining caller targets + caller/root closures + local reserve"
Write-Host "[Phase6I] Cap: 1024 new support-clean translated members"
Write-Host "[Phase6I] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6I emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6i-manifest.json"
foreach ($f in @($main,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6I missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6I" -or $m.build_tag -ne "P6I-CALLER-HARVEST-00202680-20261022-A") {
    throw "Phase 6I manifest identity mismatch"
}
$g = $m.phase6i_caller_harvest
if ($g.root -ne "0x00202680" -or -not [bool]$g.phase6h_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6I manifest gate mismatch"
}

Write-Host ""
Write-Host "[Phase6I] READY"
Write-Host ("[Phase6I] Caller direct targets   : {0}" -f [int]$g.caller_direct_targets_total)
Write-Host ("[Phase6I] Generated caller targets: {0}" -f [int]$g.caller_direct_targets_generated)
Write-Host ("[Phase6I] Unpacked caller targets : {0}" -f [int]$g.caller_direct_targets_unpacked)
Write-Host ("[Phase6I] Ungenerated targets     : {0}" -f [int]$g.caller_direct_targets_ungenerated)
Write-Host ("[Phase6I] Candidate new members   : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6I] Pruned unsafe members    : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6I] Packed new members       : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6I] Expanded pack members    : {0}" -f [int]$g.expanded_pack_members)
Write-Host "[Phase6I] Root                    : 0x00202680"
Write-Host "[Phase6I] Build BOTH fresh sources:"
Write-Host "[Phase6I]   $main"
Write-Host "[Phase6I]   $env"
Write-Host "[Phase6I] Keep d3d9.lib linked."
Write-Host "[Phase6I] Expected tag: P6I-CALLER-HARVEST-00202680-20261022-A"
Write-Host "[Phase6I] Hardware goal: keep harvesting until a real semantic boundary."
Write-Host "[Phase6I] Purple = genuine NV2A MMIO/VRAM boundary."
