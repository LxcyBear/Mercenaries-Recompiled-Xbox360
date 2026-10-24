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
$base=Join-Path $root "build\phase6_native_graphics\d3d_dual_frontier_continue_xdk"
$out=Join-Path $root "build\phase6_native_graphics\d3d_frontier_00292586_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6au_d3d_frontier_00292586.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$builder,
  (Join-Path $p4 "emit_phase4c_startup_slice.py"),
  (Join-Path $p5 "emit_phase5bb_frontier22dda4.py"),
  (Join-Path $p5 "emit_phase5bc_broad_sweep.py"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6at-manifest.json"),
  (Join-Path $stage3 "runtime\gen"),
  (Join-Path $stage3 "analysis\disasm\functions.json")
)
foreach($f in $required){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6AU input: $f"}}

$m=Get-Content (Join-Path $base "phase6at-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6AT"-or$m.build_tag-ne"P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-B"){
  throw "Phase 6AU baseline identity mismatch"
}

Write-Host "[Phase6AU] D3D FRONTIER 00292586"
Write-Host "[Phase6AU] 6AT hardware: allocation 00258000 -> 02628000 PASS"
Write-Host "[Phase6AU] New boundary: DIRECT_FRONTIER 00292586 fault=0"
Write-Host "[Phase6AU] Exact-start + support-clean closure preflight enabled"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6AU emitter syntax check failed"}
Write-Host "[Phase6AU] Emitter syntax: PASS"

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
& $python $emitter @emitArgs
if($LASTEXITCODE-ne0){throw "Phase 6AU emission/preflight failed"}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6au-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){if(-not(Test-Path $f)){throw "Missing Phase 6AU output: $f"}}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6AU"-or$r.build_tag-ne"P6AU-D3D-FRONTIER-00292586-20261024-A"){
  throw "Phase 6AU manifest identity mismatch"
}
$a=$r.phase6au_d3d_frontier_00292586
if($a.root-ne"0x00292586"-or[int]$a.packed_new_members-lt1){throw "Phase 6AU root gate failed"}

$text=Get-Content $mono -Raw
foreach($marker in @(
 "case 0x00292586u:",
 "PASS: Phase 6AU entered translated D3D frontier 00292586",
 "P6AU X360DBG PPC2:",
 "P6AU D3D FRONTIER 00292586:",
 "phase6au_env_build_cookie"
)){if(-not$text.Contains($marker)){throw "Phase 6AU source gate missing: $marker"}}

Write-Host "[Phase6AU] READY root=$($a.root) name=$($a.root_name) packed=$($a.packed_new_members) pruned=$($a.pruned_members)"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6AU-D3D-FRONTIER-00292586-20261024-A"
    ExpectedEnvCookie="phase6au_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6au-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6au-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6AU-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6AU] BUILD PASS"
  Write-Host ("[Phase6AU] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AU-A.xex"))
}
