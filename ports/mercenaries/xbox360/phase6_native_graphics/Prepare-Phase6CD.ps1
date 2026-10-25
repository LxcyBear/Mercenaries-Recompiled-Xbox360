[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\direct_frontier_001f9d70_xdk"
$out=Join-Path $root "build\phase6_native_graphics\longrun32m_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cd_longrun32m.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CD input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cc-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cc=Join-Path $PSScriptRoot "Prepare-Phase6CC.ps1"
  if(-not(Test-Path -LiteralPath $prep6cc)){
    throw "Phase 6CD baseline missing and Phase 6CC regeneration script not found"
  }
  Write-Host "[Phase6CD] Cached 6CC output missing; regenerating 6CC without solution build..."
  & $prep6cc -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CD could not regenerate 6CC baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cc-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CC"-or$m.build_tag-ne"P6CC-DIRECT-FRONTIER-001F9D70-20261024-A"){
  throw "Phase 6CD baseline identity mismatch"
}
if($m.phase6cc_direct_frontier.root-ne"0x001F9D70"-or
   $m.phase6cc_direct_frontier.root_is_declared_manual_function-ne$true-or
   $m.phase6cc_direct_frontier.translated_membership_changed-ne$false-or
   $m.phase6cc_direct_frontier.execution_budget-ne8000000){
  throw "Phase 6CD 6CC manual-root inheritance gate failed"
}

Write-Host "[Phase6CD] LONG-RUN 32M STARTUP PASS"
Write-Host "[Phase6CD] 6CC hardware stopped ONLY on artificial budget at 8,000,001; fault=0"
Write-Host "[Phase6CD] Budget: 8,000,000 -> 32,000,000 translated ticks"
Write-Host "[Phase6CD] Broad-sweep trace stride: 256 -> 4096 dispatches"
Write-Host "[Phase6CD] Samples: 4M/8M/12M/16M/20M/24M/28M/32M"
Write-Host "[Phase6CD] Goal: let title progress toward menu; preserve every genuine hard fence"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CD emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 |
    Tee-Object -Variable phase6cdEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CD] EMITTER OUTPUT:"
  $phase6cdEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CD emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cd-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path $f)){throw "Missing Phase 6CD output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CD"-or$r.build_tag-ne"P6CD-LONGRUN32M-20261025-A"){
  throw "Phase 6CD manifest identity mismatch"
}

$a=$r.phase6cd_longrun32m
if($a.phase6cc_hardware.boundary_kind-ne"BUDGET"-or
   $a.phase6cc_hardware.boundary_target-ne"0x001EF672"-or
   $a.phase6cc_hardware.ticks-ne8000001-or
   $a.phase6cc_hardware.fault-ne0-or
   $a.phase6cc_hardware.xapi_return-ne0-or
   $a.phase6cc_hardware.synthetic_outstanding-ne0-or
   $a.phase6cc_hardware.guest_irql_current-ne0-or
   $a.old_budget_ticks-ne8000000-or
   $a.new_budget_ticks-ne32000000-or
   $a.dispatch_log_stride_new-ne4096-or
   $a.translated_membership_changed-ne$false-or
   $a.manual_pbl_semantics_changed-ne$false-or
   $a.hard_fences_changed-ne$false){
  throw "Phase 6CD long-run manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "#define PHASE4C_EXEC_BUDGET 32000000u",
  "s_phase4cBlockTicks == 32000000u",
  "(s_phase5bcPackedIcallDispatchCount & 0xFFFu) == 0u",
  "(s_phase5bcPackedDirectDispatchCount & 0xFFFu) == 0u",
  "P6CD HOT PROFILE:",
  "phase6cd_dump_hot_profile();",
  "case 0x001F9D70u: return phase6cc_pbl_sin_001f9d70;",
  "phase6cd_env_build_cookie"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CD source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
$baseShardCount=@(Get-ChildItem -LiteralPath (Join-Path $base "translated_shards") -Filter "*.inl" -File).Count
if($shardCount-ne$baseShardCount){
  throw "Phase 6CD shard reuse count mismatch: base=$baseShardCount out=$shardCount"
}

Write-Host "[Phase6CD] READY"
Write-Host ("[Phase6CD] Reused translated shards : {0}" -f $shardCount)
Write-Host "[Phase6CD] Translation changes       : 0"
Write-Host "[Phase6CD] Runtime semantic changes : budget/logging/profiling only"
Write-Host "[Phase6CD] Hard fences              : preserved"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CD-LONGRUN32M-20261025-A"
    ExpectedEnvCookie="phase6cd_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cd-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cd-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CD-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CD] BUILD PASS"
  Write-Host ("[Phase6CD] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CD-A.xex"))
}
