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
$base=Join-Path $root "build\phase6_native_graphics\xact_to_display_00280141_xdk"
$out=Join-Path $root "build\phase6_native_graphics\pixel_chase_0027e780_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cs_pixel_chase_0027e780.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$phase5bbEmitter=Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
$phase5bcEmitter=Join-Path $p5 "emit_phase5bc_broad_sweep.py"
$phase6blEmitter=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$generatedRoot=Join-Path $stage3 "runtime\gen"
$functions=Join-Path $stage3 "analysis\disasm\functions.json"

foreach($f in @(
  $python,$emitter,$baseEmitter,$phase5bbEmitter,$phase5bcEmitter,
  $phase6blEmitter,$builder,$generatedRoot,$functions
)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CS input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cr-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cr=Join-Path $PSScriptRoot "Prepare-Phase6CR.ps1"
  if(-not(Test-Path -LiteralPath $prep6cr)){
    throw "Phase 6CS baseline missing and Phase 6CR regeneration script not found"
  }
  Write-Host "[Phase6CS] Cached 6CR output missing; regenerating 6CR without solution build..."
  & $prep6cr -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CS could not regenerate 6CR baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cr-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CR"-or$m.build_tag-ne"P6CR-XACT-TO-DISPLAY-00280141-20261025-A"){
  throw "Phase 6CS baseline identity mismatch"
}
$cr=$m.phase6cr_xact_to_display
if($cr.execution_budget_inherited-ne64000000-or
   $cr.kernel_itail_ordinal24_preserved-ne$true-or
   $cr.xact_sentinel_repair_preserved-ne$true-or
   $cr.hard_fences_changed-ne$false){
  throw "Phase 6CS inherited 6CR policy mismatch"
}

Write-Host "[Phase6CS] PIXEL CHASE: XACT STREAM -> DISPLAY"
Write-Host "[Phase6CS] 6CR hardware: 00280141 entered twice; XACT repairs healthy"
Write-Host "[Phase6CS] Retail music bank opened: game:\dataxbox\sound\music\shl_streams.xwb"
Write-Host "[Phase6CS] New clean frontier: DIRECT 0023A3CE -> 0027E780"
Write-Host "[Phase6CS] 6CR hardware: ticks=27019818 trace=1071495 fault=0"
Write-Host "[Phase6CS] Graphics state: Xenos ready, D3D device=00299380, display_calls=0"
Write-Host "[Phase6CS] Strategy: strip diagnostic-only XACT checkpoints + optional PS2 audio hooks"
Write-Host "[Phase6CS] Then: mandatory 0027E780 + depth-24 closure + remaining XACT/D3D/XGRPH"
Write-Host "[Phase6CS] Capacity: up to 4096 NEW support-clean functions"
Write-Host "[Phase6CS] Watchdog: preserve 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CS emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CS-R1"')){
  throw "Phase 6CS stale emitter detected; expected revision 6CS-R1"
}
Write-Host "[Phase6CS] Emitter revision       : 6CS-R1"

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
  & $python $emitter @emitArgs 2>&1 |
    Tee-Object -Variable phase6csEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CS] EMITTER OUTPUT:"
  $phase6csEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CS emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cs-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CS output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CS"-or$r.build_tag-ne"P6CS-PIXEL-CHASE-0027E780-20261025-A"){
  throw "Phase 6CS manifest identity mismatch"
}
$k=$r.phase6cs_pixel_chase
if($k.phase6cr_hardware.boundary_kind-ne"DIRECT_FRONTIER"-or
   $k.phase6cr_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6cr_hardware.target-ne"0x0027E780"-or
   $k.phase6cr_hardware.fault-ne0-or
   $k.phase6cr_hardware.root_00280141_entries-ne2-or
   $k.phase6cr_hardware.xenos_ready-ne1-or
   $k.phase6cr_hardware.d3d_calls-ne1-or
   $k.execution_budget_inherited-ne64000000-or
   $k.kernel_itail_ordinal24_preserved-ne$true-or
   $k.xact_continuity_repair_preserved-ne$true-or
   $k.xact_sentinel_repair_preserved-ne$true-or
   $k.graphics_bridge_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false){
  throw "Phase 6CS manifest gate failed"
}
if([int]$k.packed_new_members-lt1){
  throw "Phase 6CS did not pack mandatory 0027E780"
}

$norm=$k.retail_xact_normalization.diagnostic_only_helpers_removed
if($null-eq$norm-or
   [int]$norm.recomp_xact_list_checkpoint-lt1){
  throw "Phase 6CS did not remove the XACT list diagnostic that blocked 0027E780"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CS-PIXEL-CHASE-0027E780-20261025-A",
  "phase6cs_env_build_cookie",
  "case 0x0027E780u:",
  "PASS: Phase 6CS entered XACT stream frontier 0027E780",
  "P6CS PIXEL CHASE:",
  "P6CS PRESENT PROXIMITY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u",
  "PASS: Phase 6CS packed %s",
  "phase4c_ex_query_nonvolatile_setting",
  "P6CS AV FAMILY:"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CS source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CS translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CS] READY"
Write-Host ("[Phase6CS] Resolved root          : {0} {1}" -f $k.root,$k.root_name)
Write-Host ("[Phase6CS] Candidate members      : {0}" -f [int]$k.candidate_members)
Write-Host ("[Phase6CS] Pruned unsafe members  : {0}" -f [int]$k.pruned_members)
Write-Host ("[Phase6CS] Packed new members     : {0}" -f [int]$k.packed_new_members)
Write-Host ("[Phase6CS] Expanded pack members  : {0}" -f [int]$k.expanded_pack_members)
Write-Host ("[Phase6CS] Generated shards       : {0}" -f $shardCount)
Write-Host ("[Phase6CS] XACT list diagnostics  : removed {0}" -f [int]$norm.recomp_xact_list_checkpoint)
Write-Host "[Phase6CS] Semantic XACT fixes    : preserved"
Write-Host "[Phase6CS] Pixel telemetry        : ARMED"
Write-Host "[Phase6CS] 64M watchdog          : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CS-PIXEL-CHASE-0027E780-20261025-A"
    ExpectedEnvCookie="phase6cs_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cs-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cs-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CS-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CS] BUILD PASS"
  Write-Host ("[Phase6CS] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CS-A.xex"))
}
