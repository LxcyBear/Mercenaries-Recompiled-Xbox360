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
$base=Join-Path $root "build\phase6_native_graphics\d3d_frontier_0028b180_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_frontier_00290970_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bm_d3d_frontier_00290970.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase6blEmitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  (Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bl-manifest.json"),
  (Join-Path $stage3 "runtime\gen"),
  (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach($f in $required){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BM input: $f"}}

$m=Get-Content (Join-Path $base "phase6bl-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BL"-or$m.build_tag-ne"P6BL-D3D-FRONTIER-0028B180-20261024-A"){
  throw "Phase 6BM baseline identity mismatch"
}

Write-Host "[Phase6BM] D3D FRONTIER 00290970"
Write-Host "[Phase6BM] 6BL hardware: translated frontier 0028B180 entered"
Write-Host "[Phase6BM] New boundary: DIRECT_FRONTIER 00290970 fault=0"
Write-Host "[Phase6BM] Exact-start + support-clean depth-4/cap-256 closure preflight enabled"
Write-Host "[Phase6BM] All 6BL PFIFO/PFB/ZCOMP/PGRAPH semantics and hard fences preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BM emitter syntax check failed"}

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
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6bmEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BM] EMITTER OUTPUT:"
  $phase6bmEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BM emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bm-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6BM output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BM"-or$r.build_tag-ne"P6BM-D3D-FRONTIER-00290970-20261024-A"){
  throw "Phase 6BM manifest identity mismatch"
}
$a=$r.phase6bm_d3d_frontier_00290970
if($a.root-ne"0x00290970"-or[int]$a.packed_new_members-lt1-or$a.phase6bl_hardware.next_boundary.fault-ne0){
  throw "Phase 6BM root/hardware-proof gate failed"
}
if($a.all_phase6bl_gpu_bridges_inherited-ne$true -or
   $a.nv2a_mmio_vram_policy_changed-ne$false){
  throw "Phase 6BM GPU inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 0x00290970u:",
  "PASS: Phase 6BM entered translated D3D frontier 00290970",
  "P6BM D3D FRONTIER 00290970:",
  "phase6bm_env_build_cookie",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BM source gate missing: $marker"}
}

Write-Host "[Phase6BM] READY root=$($a.root) name=$($a.root_name) packed=$($a.packed_new_members) pruned=$($a.pruned_members)"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BM-D3D-FRONTIER-00290970-20261024-A"
    ExpectedEnvCookie="phase6bm_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bm-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bm-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BM-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BM] BUILD PASS"
  Write-Host ("[Phase6BM] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BM-A.xex"))
}
