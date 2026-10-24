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
$base=Join-Path $root "build\phase6_native_graphics\d3d_frontier_00290970_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xgrph_frontier_0029c8be_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bn_xgrph_frontier_0029c8be.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  (Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bm-manifest.json"),
  (Join-Path $stage3 "runtime\gen"),
  (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach($f in $required){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BN input: $f"}}

$m=Get-Content (Join-Path $base "phase6bm-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BM"-or$m.build_tag-ne"P6BM-D3D-FRONTIER-00290970-20261024-A"){
  throw "Phase 6BN baseline identity mismatch"
}

Write-Host "[Phase6BN] XGRPH FRONTIER 0029C8BE"
Write-Host "[Phase6BN] 6BM hardware: translated frontier 00290970 entered"
Write-Host "[Phase6BN] New boundary: DIRECT_FRONTIER 0029C8BE fault=0"
Write-Host "[Phase6BN] Target lies inside retail XGRPH section 0029B880-0029CB7C"
Write-Host "[Phase6BN] Exact-start proof is mandatory; interior entry will be refused"
Write-Host "[Phase6BN] Support-clean depth-4/cap-256 closure preflight enabled"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BN emitter syntax check failed"}

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
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bnEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BN] EMITTER OUTPUT:"
  $phase6bnEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BN emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bn-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6BN output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BN"-or$r.build_tag-ne"P6BN-XGRPH-FRONTIER-0029C8BE-20261024-A"){
  throw "Phase 6BN manifest identity mismatch"
}
$a=$r.phase6bn_xgrph_frontier_0029c8be
if($a.root-ne"0x0029C8BE"-or[int]$a.packed_new_members-lt1-or$a.phase6bm_hardware.next_boundary.fault-ne0){
  throw "Phase 6BN root/hardware-proof gate failed"
}
if($a.retail_section.name-ne"XGRPH"-or$a.retail_section.target_inside-ne$true){
  throw "Phase 6BN XGRPH section gate failed"
}
if($a.all_phase6bm_gpu_bridges_inherited-ne$true -or
   $a.nv2a_mmio_vram_policy_changed-ne$false){
  throw "Phase 6BN GPU inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 0x0029C8BEu:",
  "PASS: Phase 6BN entered translated XGRPH frontier 0029C8BE",
  "P6BN XGRPH FRONTIER 0029C8BE:",
  "phase6bn_env_build_cookie",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BN source gate missing: $marker"}
}

Write-Host "[Phase6BN] READY root=$($a.root) name=$($a.root_name) packed=$($a.packed_new_members) pruned=$($a.pruned_members)"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BN-XGRPH-FRONTIER-0029C8BE-20261024-A"
    ExpectedEnvCookie="phase6bn_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bn-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bn-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BN-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BN] BUILD PASS"
  Write-Host ("[Phase6BN] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BN-A.xex"))
}
