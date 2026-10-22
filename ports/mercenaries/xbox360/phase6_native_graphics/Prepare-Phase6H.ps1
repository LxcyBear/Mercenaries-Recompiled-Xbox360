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
$baseDir = Join-Path $root "build\phase6_native_graphics\sibling_harvest_00150e20_xdk"
$out = Join-Path $root "build\phase6_native_graphics\caller_harvest_00015b30_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6h-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6h_caller_harvest.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6H input: $v" }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6g-manifest.json")
)
foreach ($f in $baseFiles) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6H fast baseline missing: $f. Keep the successful Phase 6G generated output; 6H intentionally does not regenerate the ancestry."
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6g-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6G" -or $baseManifest.build_tag -ne "P6G-SIBLING-HARVEST-00150E20-20261022-A") {
    throw "Phase 6H cached Phase 6G baseline identity mismatch"
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6H] CACHED CALLER-CLOSURE HARVEST"
Write-Host "[Phase6H] Phase 6G hardware: 00150E20 + 00153080 crossed; next frontier 0023A3CE -> 00015B30, fault=0"
Write-Host "[Phase6H] FAST BASE: reusing existing Phase 6G generated output (no recursive ancestry regeneration)"
Write-Host "[Phase6H] HARVEST: exact direct targets encoded by caller 0x0023A3CE + caller/root closures"
Write-Host "[Phase6H] Cap: 1024 new support-clean translated members"
Write-Host "[Phase6H] Watson: throttled proven DIRECT/ICALL spam, dense old-frontier window retained"
Write-Host "[Phase6H] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

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
    throw "Phase 6H emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6h-manifest.json"
foreach ($f in @($main,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6H missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6H" -or $m.build_tag -ne "P6H-CALLER-HARVEST-00015B30-20261022-A") {
    throw "Phase 6H manifest identity mismatch"
}
$g = $m.phase6h_caller_harvest
if ($g.root -ne "0x00015B30" -or -not [bool]$g.phase6g_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6H manifest gate mismatch"
}

Write-Host ""
Write-Host "[Phase6H] READY"
Write-Host ("[Phase6H] Caller direct targets   : {0}" -f [int]$g.caller_direct_targets_total)
Write-Host ("[Phase6H] Generated caller targets: {0}" -f [int]$g.caller_direct_targets_generated)
Write-Host ("[Phase6H] Unpacked caller targets : {0}" -f [int]$g.caller_direct_targets_unpacked)
Write-Host ("[Phase6H] Ungenerated targets     : {0}" -f [int]$g.caller_direct_targets_ungenerated)
Write-Host ("[Phase6H] Candidate new members   : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6H] Pruned unsafe members    : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6H] Packed new members       : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6H] Expanded pack members    : {0}" -f [int]$g.expanded_pack_members)
Write-Host "[Phase6H] Root                    : 0x00015B30"
Write-Host "[Phase6H] Build BOTH fresh sources:"
Write-Host "[Phase6H]   $main"
Write-Host "[Phase6H]   $env"
Write-Host "[Phase6H] Keep d3d9.lib linked."
Write-Host "[Phase6H] Expected tag: P6H-CALLER-HARVEST-00015B30-20261022-A"
Write-Host "[Phase6H] Hardware goal: exhaust generated direct holes from caller 0023A3CE in one run."
Write-Host "[Phase6H] Purple = genuine NV2A MMIO/VRAM boundary. Send the full xbWatson log."
