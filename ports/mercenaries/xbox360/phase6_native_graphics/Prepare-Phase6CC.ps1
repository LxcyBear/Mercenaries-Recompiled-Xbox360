[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$p5=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$python=Join-Path $root ".venv\Scripts\python.exe"
$stage3=Join-Path $root "build\phase3n_final_abi_scale"
$base=Join-Path $root "build\phase6_native_graphics\obfderef250_sentinel_xdk"
$out=Join-Path $root "build\phase6_native_graphics\direct_frontier_001f9d70_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cc_direct_frontier_001f9d70.py"
$phase5bbEmitter=Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
$phase5bcEmitter=Join-Path $p5 "emit_phase5bc_broad_sweep.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$required=@(
  $python,$emitter,$phase5bbEmitter,$phase5bcEmitter,$phase6blEmitter,$baseEmitter,$builder
)
foreach($f in $required){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CC input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cb-manifest.json")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cb=Join-Path $PSScriptRoot "Prepare-Phase6CB.ps1"
  if(-not(Test-Path -LiteralPath $prep6cb)){
    throw "Phase 6CC baseline missing and Phase 6CB regeneration script not found"
  }
  Write-Host "[Phase6CC] Cached 6CB output missing; regenerating 6CB without solution build..."
  & $prep6cb -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CC could not regenerate 6CB baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cb-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CB"-or$m.build_tag-ne"P6CB-OBFDEREF250-SENTINEL-20261024-A"){
  throw "Phase 6CC baseline identity mismatch"
}

$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"
foreach($f in @($generatedRoot,$functions)){
  if(-not(Test-Path -LiteralPath $f)){throw "Phase 6CC generated-code analysis input missing: $f"}
}

Write-Host "[Phase6CC] DIRECT FRONTIER 001F9D70"
Write-Host "[Phase6CC] 6CB hardware: sentinel deref PASS, outstanding=0, NtClose PASS"
Write-Host "[Phase6CC] Boundary: DIRECT_FRONTIER 0023A3CE -> 001F9D70"
Write-Host "[Phase6CC] Frame: esp=saved=008BF988 fault=0 ticks=956060 trace=180293"
Write-Host "[Phase6CC] Policy: exact generated start + bounded depth-4/cap-256 support-clean closure"
Write-Host "[Phase6CC] Unknown root support hard-stops; no guessed shim"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CC emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase5bb-emitter",$phase5bbEmitter,
  "--phase5bc-emitter",$phase5bcEmitter,
  "--phase6bl-emitter",$phase6blEmitter,
  "--generated-root",$generatedRoot,
  "--functions",$functions,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6ccEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CC] EMITTER OUTPUT:"
  $phase6ccEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CC emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cc-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6CC output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CC"-or$r.build_tag-ne"P6CC-DIRECT-FRONTIER-001F9D70-20261024-A"){
  throw "Phase 6CC manifest identity mismatch"
}

$a=$r.phase6cc_direct_frontier
if($a.phase6cb_hardware.next_boundary_kind-ne"DIRECT_FRONTIER"-or
   $a.phase6cb_hardware.next_boundary_caller-ne"0x0023A3CE"-or
   $a.phase6cb_hardware.next_boundary_target-ne"0x001F9D70"-or
   $a.phase6cb_hardware.boundary_esp-ne"0x008BF988"-or
   $a.phase6cb_hardware.boundary_saved_esp-ne"0x008BF988"-or
   $a.phase6cb_hardware.fault-ne0-or
   $a.root-ne"0x001F9D70"-or
   $a.frontier_caller-ne"0x0023A3CE"-or
   $a.packed_new_members-lt1-or
   $a.execution_budget-ne8000000){
  throw "Phase 6CC hardware/root manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "case 0x001F9D70u:",
  "PASS: Phase 6CC entered translated direct frontier 001F9D70",
  "P6CC DIRECT FRONTIER 001F9D70:",
  "P6CC OBFDEREF250:",
  "phase6cc_env_build_cookie",
  "#define PHASE4C_EXEC_BUDGET 8000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CC source gate missing: $marker"}
}

Write-Host "[Phase6CC] READY"
Write-Host ("[Phase6CC] Root name             : {0}" -f [string]$a.root_name)
Write-Host ("[Phase6CC] Candidate new members : {0}" -f [int]$a.candidate_new_members)
Write-Host ("[Phase6CC] Pruned unsafe members : {0}" -f [int]$a.pruned_members)
Write-Host ("[Phase6CC] Packed new members    : {0}" -f [int]$a.packed_new_members)
Write-Host ("[Phase6CC] Total pack members    : {0}" -f [int]$a.expanded_pack_members)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CC-DIRECT-FRONTIER-001F9D70-20261024-A"
    ExpectedEnvCookie="phase6cc_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cc-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cc-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CC-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CC] BUILD PASS"
  Write-Host ("[Phase6CC] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CC-A.xex"))
}
