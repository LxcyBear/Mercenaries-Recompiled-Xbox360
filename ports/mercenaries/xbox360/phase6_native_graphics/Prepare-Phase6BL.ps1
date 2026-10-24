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
$base=Join-Path $root "build\phase6_native_graphics\d3d_pfifo_dma_push_clear_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_frontier_0028b180_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  (Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6bk-manifest.json"),
  (Join-Path $stage3 "runtime\gen"),
  (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach($f in $required){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6BL input: $f"}}

$m=Get-Content (Join-Path $base "phase6bk-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6BK"-or$m.build_tag-ne"P6BK-PFIFO-DMA-PUSH-CLEAR-20261024-A"){
  throw "Phase 6BL baseline identity mismatch"
}

Write-Host "[Phase6BL] D3D FRONTIER 0028B180"
Write-Host "[Phase6BL] 6BK hardware: later PFIFO zero-clear PASS"
Write-Host "[Phase6BL] 6BK hardware: D3D root 00290895 + internal device + sync all PASS"
Write-Host "[Phase6BL] New boundary: DIRECT_FRONTIER 0028B180 fault=0"
Write-Host "[Phase6BL] Exact-start + support-clean depth-4/cap-256 closure preflight enabled"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6BL emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",(Join-Path $p4 "emit_phase4c_startup_slice.py"),
  "--base-phase5bb-emitter",(Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  "--base-phase5bc-emitter",(Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  "--generated-root",(Join-Path $stage3 "runtime\gen"),
  "--functions",(Join-Path $stage3 "analysis\disasm\functions.json"),
  "--out-dir",$out
)
& $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6blEmitOutput
if($LASTEXITCODE-ne0){
  Write-Host "[Phase6BL] EMITTER OUTPUT:"
  $phase6blEmitOutput | ForEach-Object { Write-Host $_ }
  throw "Phase 6BL emission/preflight failed; see emitter output above"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6bl-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6BL output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6BL"-or$r.build_tag-ne"P6BL-D3D-FRONTIER-0028B180-20261024-A"){
  throw "Phase 6BL manifest identity mismatch"
}
$a=$r.phase6bl_d3d_frontier_0028b180
if($a.root-ne"0x0028B180"-or[int]$a.packed_new_members-lt1-or$a.phase6bk_hardware.next_boundary.fault-ne0){
  throw "Phase 6BL root/hardware-proof gate failed"
}
if($a.all_phase6bk_gpu_bridges_inherited-ne$true -or
   $a.nv2a_mmio_vram_policy_changed-ne$false){
  throw "Phase 6BL GPU inheritance/fence gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 0x0028B180u:",
  "PASS: Phase 6BL entered translated D3D frontier 0028B180",
  "P6BL D3D FRONTIER 0028B180:",
  "phase6bl_env_build_cookie",
  "phase6be_pfifo_idle_write32(address, value)",
  "phase6bj_pfb_zcomp_write32",
  "phase6bg_pfb_tile_write32",
  "phase6bh_pgraph_scoped_write32",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6BL source gate missing: $marker"}
}

Write-Host "[Phase6BL] READY root=$($a.root) name=$($a.root_name) packed=$($a.packed_new_members) pruned=$($a.pruned_members)"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6BL-D3D-FRONTIER-0028B180-20261024-A"
    ExpectedEnvCookie="phase6bl_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6bl-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6bl-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6BL-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6BL] BUILD PASS"
  Write-Host ("[Phase6BL] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6BL-A.xex"))
}
