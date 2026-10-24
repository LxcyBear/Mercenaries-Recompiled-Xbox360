[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p5=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python=Join-Path $root ".venv\Scripts\python.exe"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$base=Join-Path $root "build\phase6_native_graphics\volume_a3ce_frame_repair_xdk"
$out=Join-Path $root "build\phase6_native_graphics\post_pbl_frontier_00209a70_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6br_post_pbl_frontier_00209a70.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  (Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bq-manifest.json"),
  (Join-Path $stage3 "runtime\gen"),
  (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach($f in $required){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BR input: $f"}}

$m=Get-Content (Join-Path $base "phase6bq-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BQ"-or$m.build_tag-ne"P6BQ-VOLUME-A3CE-FRAME-REPAIR-20261024-A"){
  throw "Phase 6BR baseline identity mismatch"
}

Write-Host "[Phase6BR] POST-PBL .TEXT FRONTIER 00209A70"
Write-Host "[Phase6BR] 6BQ hardware: ordinal-218 28->24 repair PASS"
Write-Host "[Phase6BR] PBL checkpoint advanced to phase1=1 phase2=1"
Write-Host "[Phase6BR] New boundary: DIRECT_FRONTIER caller=0023A3CE target=00209A70 fault=0"
Write-Host "[Phase6BR] Exact-start + support-clean depth-4/cap-256 closure preflight enabled"
Write-Host "[Phase6BR] Both ABI repairs and all GPU/allocator/8M-budget invariants preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BR emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--phase6bl-emitter",$phase6blEmitter,
  "--base-phase5bb-emitter",(Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  "--base-phase5bc-emitter",(Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  "--generated-root",(Join-Path $stage3 "runtime\gen"),
  "--functions",(Join-Path $stage3 "analysis\disasm\functions.json"),
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6brEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BR] EMITTER OUTPUT:"
  $phase6brEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6BR emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6br-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6BR output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BR"-or$r.build_tag-ne"P6BR-POST-PBL-FRONTIER-00209A70-20261024-A"){
  throw "Phase 6BR manifest identity mismatch"
}
$a=$r.phase6br_post_pbl_frontier_00209a70
if($a.root-ne"0x00209A70"-or[int]$a.packed_new_members-lt1-or
   $a.phase6bq_hardware.next_boundary.fault-ne0-or
   $a.phase6bq_hardware.pbl_checkpoint_phase2-ne1){
  throw "Phase 6BR root/hardware-proof gate failed"
}
if($a.retail_section.name-ne".text"-or$a.retail_section.target_inside-ne$true){
  throw "Phase 6BR .text section gate failed"
}
if($a.all_phase6bq_abi_repairs_inherited-ne$true-or
   $a.all_phase6bq_gpu_bridges_inherited-ne$true-or
   $a.nv2a_mmio_vram_policy_changed-ne$false-or
   $a.allocator_changed-ne$false){
  throw "Phase 6BR inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 0x00209A70u:",
  "PASS: Phase 6BR entered translated post-PBL frontier 00209A70",
  "P6BR POST-PBL FRONTIER 00209A70:",
  "P6BR PBL CHECKPOINT:",
  "NtQueryVolumeInformationFile SAVEDESP REPAIR PROBE:",
  "RtlInitAnsiString SAVEDESP REPAIR PROBE:",
  "phase6br_env_build_cookie",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BR source gate missing: $marker"}
}

Write-Host "[Phase6BR] READY root=$($a.root) name=$($a.root_name) packed=$($a.packed_new_members) pruned=$($a.pruned_members)"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BR-POST-PBL-FRONTIER-00209A70-20261024-A"
    ExpectedEnvCookie="phase6br_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6br-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6br-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BR-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BR] BUILD PASS"
  Write-Host ("[Phase6BR] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BR-A.xex"))
}
