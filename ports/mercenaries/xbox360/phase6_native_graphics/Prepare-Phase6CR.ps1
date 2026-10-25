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
$base=Join-Path $root "build\phase6_native_graphics\itail_saturation64m_0010d1a0_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_to_display_00280141_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cr_xact_to_display_00280141.py"
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
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CR input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cq-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cq=Join-Path $PSScriptRoot "Prepare-Phase6CQ.ps1"
  if(-not(Test-Path -LiteralPath $prep6cq)){
    throw "Phase 6CR baseline missing and Phase 6CQ regeneration script not found"
  }
  Write-Host "[Phase6CR] Cached 6CQ output missing; regenerating 6CQ without solution build..."
  & $prep6cq -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CR could not regenerate 6CQ baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cq-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CQ"-or$m.build_tag-ne"P6CQ-ITAIL-SATURATION64M-0010D1A0-20261025-A"){
  throw "Phase 6CR baseline identity mismatch"
}
$cq=$m.phase6cq_itail_saturation64m
if($cq.execution_budget-ne64000000-or
   $cq.hard_fences_changed-ne$false-or
   $cq.allocator_policy_changed-ne$false-or
   $cq.graphics_semantics_changed-ne$false){
  throw "Phase 6CR inherited 6CQ policy mismatch"
}

Write-Host "[Phase6CR] XACT -> DISPLAY ACCELERATION"
Write-Host "[Phase6CR] 6CQ hardware: packed ITAIL 0010D1A0 consumed 3x"
Write-Host "[Phase6CR] New clean frontier: DIRECT 0023A3CE -> 00280141"
Write-Host "[Phase6CR] 6CQ hardware: ticks=26814224 trace=1035503 fault=0"
Write-Host "[Phase6CR] 6CQ display state: display_calls=0 framebuffer=00000000"
Write-Host "[Phase6CR] Strategy: mandatory 00280141 + deep closure + remaining XACTENG/D3D/XGRPH"
Write-Host "[Phase6CR] Capacity: up to 4096 NEW support-clean generated functions"
Write-Host "[Phase6CR] Telemetry: root + Xenos + D3D device + AvSetDisplayMode/framebuffer"
Write-Host "[Phase6CR] Watchdog: preserve 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CR emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CR-R1"')){
  throw "Phase 6CR stale emitter detected; expected revision 6CR-R1"
}
Write-Host "[Phase6CR] Emitter revision       : 6CR-R1"

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
    Tee-Object -Variable phase6crEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CR] EMITTER OUTPUT:"
  $phase6crEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CR emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cr-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CR output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CR"-or$r.build_tag-ne"P6CR-XACT-TO-DISPLAY-00280141-20261025-A"){
  throw "Phase 6CR manifest identity mismatch"
}
$k=$r.phase6cr_xact_to_display
if($k.phase6cq_hardware.boundary_kind-ne"DIRECT_FRONTIER"-or
   $k.phase6cq_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6cq_hardware.target-ne"0x00280141"-or
   $k.phase6cq_hardware.fault-ne0-or
   $k.phase6cq_hardware.packed_itail_dispatches-ne3-or
   $k.phase6cq_hardware.display_calls-ne0-or
   $k.execution_budget_inherited-ne64000000-or
   $k.kernel_itail_ordinal24_preserved-ne$true-or
   $k.xact_sentinel_repair_preserved-ne$true-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.graphics_bridge_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false){
  throw "Phase 6CR manifest gate failed"
}
if([int]$k.packed_new_members-lt1){
  throw "Phase 6CR did not pack the mandatory frontier"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CR-XACT-TO-DISPLAY-00280141-20261025-A",
  "phase6cr_env_build_cookie",
  "case 0x00280141u:",
  "PASS: Phase 6CR entered XACTENG frontier 00280141",
  "P6CR PRESENT PROXIMITY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u",
  "PASS: Phase 6CR packed %s",
  "0x80000018u",
  "phase4c_ex_query_nonvolatile_setting",
  "P6CR AV FAMILY:"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CR source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CR translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CR] READY"
Write-Host ("[Phase6CR] Resolved root          : {0} {1}" -f $k.root,$k.root_name)
Write-Host ("[Phase6CR] Candidate members      : {0}" -f [int]$k.candidate_members)
Write-Host ("[Phase6CR] Pruned unsafe members  : {0}" -f [int]$k.pruned_members)
Write-Host ("[Phase6CR] Packed new members     : {0}" -f [int]$k.packed_new_members)
Write-Host ("[Phase6CR] Expanded pack members  : {0}" -f [int]$k.expanded_pack_members)
Write-Host ("[Phase6CR] Generated shards       : {0}" -f $shardCount)
Write-Host "[Phase6CR] Present proximity      : ARMED"
Write-Host "[Phase6CR] 64M watchdog          : preserved"
Write-Host "[Phase6CR] 6CP/6CQ repairs       : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CR-XACT-TO-DISPLAY-00280141-20261025-A"
    ExpectedEnvCookie="phase6cr_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cr-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cr-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CR-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CR] BUILD PASS"
  Write-Host ("[Phase6CR] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CR-A.xex"))
}
