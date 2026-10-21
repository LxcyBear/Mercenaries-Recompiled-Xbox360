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
$out = Join-Path $root "build\phase6_native_graphics\graphics_frontier_0014d820_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6c-emitter.log"

$paths = @{
    base6b = Join-Path $p6 "emit_phase6b_first_graphics_touch.py"
    emitter = Join-Path $p6 "emit_phase6c_graphics_frontier.py"
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
foreach ($v in $paths.Values + @($python)) { if (-not (Test-Path -LiteralPath $v)) { throw "Missing Phase 6C input: $v" } }

if (Test-Path $out) { Remove-Item $out -Recurse -Force }
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6C] CONTINUE LIVE GRAPHICS FRONTIER"
Write-Host "[Phase6C] Phase 6B hardware boundary: 0023A3CE -> 0014D820, fault=0"
Write-Host "[Phase6C] Root: 0x0014D820; Xenos remains live; purple=NV2A boundary, dark blue=another frontier"

$args = @(
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

$old = $ErrorActionPreference; $ErrorActionPreference = "Continue"
try { & $python $paths.emitter @args 2>&1 | Tee-Object -FilePath $log; $rc=$LASTEXITCODE }
finally { $ErrorActionPreference = $old }
if ($rc -ne 0) { Get-Content $log -Tail 120; throw "Phase 6C emission failed (exit $rc)" }

$main = Join-Path $out "main.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6c-manifest.json"
foreach ($f in @($main,$env,$manifest)) { if (-not (Test-Path $f)) { throw "Phase 6C missing output: $f" } }

$m = Get-Content $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6C" -or $m.build_tag -ne "P6C-GRAPHICS-FRONTIER-0014D820-20261021-A") { throw "Phase 6C manifest identity mismatch" }
$g = $m.phase6c_graphics_frontier
if ($g.root -ne "0x0014D820" -or -not [bool]$g.phase6b_hardware_pass -or [int]$g.packed_new_members -lt 1) { throw "Phase 6C manifest gate mismatch" }

Write-Host ""
Write-Host "[Phase6C] READY"
Write-Host ("[Phase6C] New translated members : {0}" -f [int]$g.packed_new_members)
Write-Host "[Phase6C] Root                   : 0x0014D820"
Write-Host "[Phase6C] Build BOTH fresh sources:"
Write-Host "[Phase6C]   $main"
Write-Host "[Phase6C]   $env"
Write-Host "[Phase6C] Keep d3d9.lib linked."
Write-Host "[Phase6C] Expected tag: P6C-GRAPHICS-FRONTIER-0014D820-20261021-A"
Write-Host "[Phase6C] Send the full xbWatson log + capture result."
