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
$out = Join-Path $root "build\phase6_native_graphics\frontier_harvest_00150e40_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6f-emitter.log"

$paths = @{
    base6b = Join-Path $p6 "emit_phase6b_first_graphics_touch.py"
    base6c = Join-Path $p6 "emit_phase6c_graphics_frontier.py"
    base6d = Join-Path $p6 "emit_phase6d_graphics_frontier.py"
    base6e = Join-Path $p6 "emit_phase6e_graphics_frontier.py"
    emitter = Join-Path $p6 "emit_phase6f_frontier_harvest.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
    bd = Join-Path $p5 "emit_phase5bd_regional_sweep.py"
    be = Join-Path $p5 "emit_phase5be_forward_sweep.py"
    bf = Join-Path $p5 "emit_phase5bf_forward_sweep.py"
    bg = Join-Path $p5 "emit_phase5bg_text_tail_sweep.py"
    bh = Join-Path $p5 "emit_phase5bh_direct_frontier_mop.py"
    bi = Join-Path $p5 "emit_phase5bi_low_text_sweep.py"
    bj = Join-Path $p5 "emit_phase5bj_deep_low_text_sweep.py"
    bk = Join-Path $p5 "emit_phase5bk_diagnostic_mop.py"
    bl = Join-Path $p5 "emit_phase5bl_high_tail_sweep.py"
    bm = Join-Path $p5 "emit_phase5bm_low_text_sweep.py"
    bn = Join-Path $p5 "emit_phase5bn_deep_low_sweep.py"
    bo = Join-Path $p5 "emit_phase5bo_mid_text_sweep.py"
    bp = Join-Path $p5 "emit_phase5bp_low_text_sweep.py"
    bq = Join-Path $p5 "emit_phase5bq_low_text_sweep.py"
    br = Join-Path $p5 "emit_phase5br_low_text_sweep.py"
    bs = Join-Path $p5 "emit_phase5bs_low_text_sweep.py"
    bt = Join-Path $p5 "emit_phase5bt_mid_text_sweep.py"
    bu = Join-Path $p5 "emit_phase5bu_mid_text_sweep.py"
    bv = Join-Path $p5 "emit_phase5bv_repeatability.py"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6F input: $v" }
}

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6F] BATCHED FRONTIER HARVEST"
Write-Host "[Phase6F] Phase 6E hardware boundary: 0023A3CE -> 00150E40, fault=0"
Write-Host "[Phase6F] Batch: root + direct closure + forward-biased regional exact generated targets"
Write-Host "[Phase6F] Cap: 256 new support-clean translated members"
Write-Host "[Phase6F] Purple remains reserved for genuine NV2A MMIO/VRAM boundary"

$args = @(
 "--base-phase6e-emitter",$paths.base6e,
 "--base-phase6d-emitter",$paths.base6d,
 "--base-phase6c-emitter",$paths.base6c,
 "--base-phase6b-emitter",$paths.base6b,
 "--base-phase5bv-emitter",$paths.bv,"--base-phase5bu-emitter",$paths.bu,
 "--base-phase5bt-emitter",$paths.bt,"--base-phase5bs-emitter",$paths.bs,
 "--base-phase5br-emitter",$paths.br,"--base-phase5bq-emitter",$paths.bq,
 "--base-phase5bp-emitter",$paths.bp,"--base-phase5bo-emitter",$paths.bo,
 "--base-phase5bn-emitter",$paths.bn,"--base-phase5bm-emitter",$paths.bm,
 "--base-phase5bl-emitter",$paths.bl,"--base-phase5bk-emitter",$paths.bk,
 "--base-phase5bj-emitter",$paths.bj,"--base-phase5bi-emitter",$paths.bi,
 "--base-phase5bh-emitter",$paths.bh,"--base-phase5bg-emitter",$paths.bg,
 "--base-phase5bf-emitter",$paths.bf,"--base-phase5be-emitter",$paths.be,
 "--base-phase5bd-emitter",$paths.bd,"--base-phase5bc-emitter",$paths.bc,
 "--base-phase5bb-emitter",$paths.bb,"--base-emitter",$paths.base,
 "--generated-root",(Join-Path $stage3 "runtime\gen"),
 "--functions",(Join-Path $stage3 "analysis\disasm\functions.json"),
 "--entry-report",(Join-Path $root "build\phase4c_native_startup\phase4c-startup-closure.json"),
 "--thread-report",(Join-Path $root "build\phase4c_native_startup\phase4c-thread-routine.json"),
 "--phase3n-template",(Join-Path $root "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"),
 "--phase2e-source",(Join-Path $root "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"),
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
    Get-Content $log -Tail 160
    throw "Phase 6F emission failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6f-manifest.json"
foreach ($f in @($main,$env,$manifest)) {
    if (-not (Test-Path $f)) { throw "Phase 6F missing output: $f" }
}

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6F" -or $m.build_tag -ne "P6F-FRONTIER-HARVEST-00150E40-20261021-A") {
    throw "Phase 6F manifest identity mismatch"
}
$g = $m.phase6f_frontier_harvest
if ($g.root -ne "0x00150E40" -or -not [bool]$g.phase6e_hardware_pass -or [int]$g.packed_new_members -lt 1) {
    throw "Phase 6F manifest gate mismatch"
}

Write-Host ""
Write-Host "[Phase6F] READY"
Write-Host ("[Phase6F] Candidate new members : {0}" -f [int]$g.candidate_new_members)
Write-Host ("[Phase6F] Pruned unsafe members  : {0}" -f [int]$g.pruned_members)
Write-Host ("[Phase6F] Packed new members    : {0}" -f [int]$g.packed_new_members)
Write-Host ("[Phase6F] Expanded pack members : {0}" -f [int]$g.expanded_pack_members)
Write-Host "[Phase6F] Root                  : 0x00150E40"
Write-Host "[Phase6F] Build BOTH fresh sources:"
Write-Host "[Phase6F]   $main"
Write-Host "[Phase6F]   $env"
Write-Host "[Phase6F] Keep d3d9.lib linked."
Write-Host "[Phase6F] Expected tag: P6F-FRONTIER-HARVEST-00150E40-20261021-A"
Write-Host "[Phase6F] Hardware goal: cross multiple exact packed direct targets in one run."
Write-Host "[Phase6F] Purple = genuine NV2A MMIO/VRAM boundary. Send the full xbWatson log."
