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
$base=Join-Path $root "build\phase6_native_graphics\xact_field8_sentinel_xdk"
$out=Join-Path $root "build\phase6_native_graphics\itail_saturation64m_0010d1a0_xdk"

$emitter=Join-Path $PSScriptRoot "emit_phase6cq_itail_saturation64m.py"
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
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CQ input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cp-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cp=Join-Path $PSScriptRoot "Prepare-Phase6CP.ps1"
  if(-not(Test-Path -LiteralPath $prep6cp)){
    throw "Phase 6CQ baseline missing and Phase 6CP regeneration script not found"
  }
  Write-Host "[Phase6CQ] Cached 6CP output missing; regenerating 6CP without solution build..."
  & $prep6cp -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CQ could not regenerate 6CP baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cp-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CP"-or$m.build_tag-ne"P6CP-XACT-FIELD8-SENTINEL-20261025-A"){
  throw "Phase 6CQ baseline identity mismatch"
}
$cp=$m.phase6cp_xact_field8_sentinel
if($cp.phase6co_hardware.fault_address-ne"0x782E657F"-or
   $cp.sentinel_value-ne"0xFFFFFFFF"-or
   $cp.hard_fences_changed-ne$false-or
   $cp.execution_budget_inherited-ne32000000){
  throw "Phase 6CQ inherited 6CP policy mismatch"
}

Write-Host "[Phase6CQ] ROCKET MODE: 64M ITAIL SATURATION"
Write-Host "[Phase6CQ] 6CP hardware: XACT sentinel exit PASS; old 782E657F fault gone"
Write-Host "[Phase6CQ] New clean frontier: ITAIL 0023A3CE -> 0010D1A0, fault=0, ticks=26811021"
Write-Host "[Phase6CQ] Coverage: exact root + deep root closure + caller closure + local/global text saturation"
Write-Host "[Phase6CQ] Capacity: up to 4096 NEW support-clean generated .text functions"
Write-Host "[Phase6CQ] ITAIL policy: auto-dispatch exact packed ITAIL/ITAIL_SAFE only"
Write-Host "[Phase6CQ] Unknown/mid-function/unsupported/ABI/MMIO/guest-fault targets remain hard stops"
Write-Host "[Phase6CQ] Watchdog: 64,000,000 translated blocks"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CQ emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6CQ-R7"')){
  throw "Phase 6CQ stale emitter detected; expected revision 6CQ-R7"
}
Write-Host "[Phase6CQ] Emitter revision       : 6CQ-R7"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--base-phase5bb-emitter",$phase5bbEmitter,
  "--base-phase5bc-emitter",$phase5bcEmitter,
  "--phase6bl-emitter",$phase6blEmitter,
  "--generated-root",$generatedRoot,
  "--functions",$functions,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 |
    Tee-Object -Variable phase6cqEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CQ] EMITTER OUTPUT:"
  $phase6cqEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CQ emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cq-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CQ output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CQ"-or$r.build_tag-ne"P6CQ-ITAIL-SATURATION64M-0010D1A0-20261025-A"){
  throw "Phase 6CQ manifest identity mismatch"
}
$k=$r.phase6cq_itail_saturation64m
if($k.phase6cp_hardware.boundary_kind-ne"ITAIL"-or
   $k.phase6cp_hardware.caller-ne"0x0023A3CE"-or
   $k.phase6cp_hardware.target-ne"0x0010D1A0"-or
   $k.phase6cp_hardware.fault-ne0-or
   $k.phase6cp_hardware.xact_sentinel_exits-ne1-or
   $k.phase6cp_hardware.display_calls-ne0-or
   $k.execution_budget-ne64000000-or
   $k.allocator_policy_changed-ne$false-or
   $k.apu_semantics_changed-ne$false-or
   $k.guest_irql_semantics_changed-ne$false-or
   $k.graphics_semantics_changed-ne$false-or
   $k.null_page_semantics_changed-ne$false-or
   $k.seh_terminator_semantics_changed-ne$false-or
   $k.hard_fences_changed-ne$false){
  throw "Phase 6CQ manifest gate failed"
}
if([int]$k.packed_new_members-lt0-or[int]$k.expanded_members-lt1){
  throw "Phase 6CQ pack accounting gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6CQ-ITAIL-SATURATION64M-0010D1A0-20261025-A",
  "phase6cq_env_build_cookie",
  "P6CQ ITAIL SATURATION:",
  "PASS: Phase 6CQ packed %s",
  "#define PHASE4C_EXEC_BUDGET 64000000u",
  "PASS: Phase 6CQ XACT field8 sentinel exit",
  "P6CQ XACT FIELD8:"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CQ source gate missing: $marker"}
}

$rootHex=([string]$k.resolved_root).Substring(2)
$rootName=[string]$k.resolved_root_name
$lookupMarker=("case 0x{0}u: return {1};" -f $rootHex,$rootName)
if(-not$text.Contains($lookupMarker)){
  throw "Phase 6CQ resolved ITAIL root lookup missing: $lookupMarker"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6CQ translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6CQ] READY"
Write-Host ("[Phase6CQ] Resolved root          : {0} {1}" -f $k.resolved_root,$k.resolved_root_name)
Write-Host ("[Phase6CQ] Base packed members    : {0}" -f [int]$k.base_members)
Write-Host ("[Phase6CQ] Remaining text before  : {0}" -f [int]$k.remaining_generated_text)
Write-Host ("[Phase6CQ] Candidate new members  : {0}" -f [int]$k.candidate_new_members)
Write-Host ("[Phase6CQ] Pruned unsafe members  : {0}" -f [int]$k.pruned_members)
Write-Host ("[Phase6CQ] Packed new members     : {0}" -f [int]$k.packed_new_members)
if([bool]$k.all_remaining_candidates_support_fenced){
  Write-Host "[Phase6CQ] Remaining candidates   : all support-fenced; inherited pack will run"
}
Write-Host ("[Phase6CQ] Expanded pack members  : {0}" -f [int]$k.expanded_members)
Write-Host ("[Phase6CQ] Generated shards       : {0}" -f $shardCount)
Write-Host "[Phase6CQ] ITAIL auto-dispatch    : exact packed targets only"
Write-Host "[Phase6CQ] Execution budget       : 64M"
Write-Host "[Phase6CQ] XACT sentinel repair   : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CQ-ITAIL-SATURATION64M-0010D1A0-20261025-A"
    ExpectedEnvCookie="phase6cq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cq-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cq-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CQ-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CQ] BUILD PASS"
  Write-Host ("[Phase6CQ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CQ-A.xex"))
}
