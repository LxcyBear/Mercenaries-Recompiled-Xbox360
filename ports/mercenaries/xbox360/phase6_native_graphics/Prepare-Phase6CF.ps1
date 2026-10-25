[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\xacteng_sweep_0027db5c_xdk"
$out=Join-Path $root "build\phase6_native_graphics\expool_family_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cf_expool_family.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CF input: $f"
  }
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6ce-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6ce=Join-Path $PSScriptRoot "Prepare-Phase6CE.ps1"
  if(-not(Test-Path -LiteralPath $prep6ce)){
    throw "Phase 6CF baseline missing and Phase 6CE regeneration script not found"
  }
  Write-Host "[Phase6CF] Cached 6CE output missing; regenerating 6CE without solution build..."
  & $prep6ce -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CF could not regenerate 6CE baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6ce-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CE"-or$m.build_tag-ne"P6CE-XACTENG-SIBLING-SWEEP-0027DB5C-20261025-A"){
  throw "Phase 6CF baseline identity mismatch"
}
if($m.phase6ce_xacteng_sibling_sweep.root-ne"0x0027DB5C"-or
   $m.phase6ce_xacteng_sibling_sweep.execution_budget_inherited-ne32000000-or
   $m.phase6ce_xacteng_sibling_sweep.hard_fences_changed-ne$false){
  throw "Phase 6CF inherited 6CE policy mismatch"
}

Write-Host "[Phase6CF] EXECUTIVE POOL FAMILY"
Write-Host "[Phase6CF] 6CE hardware: XACTENG 0027DB5C PASS"
Write-Host "[Phase6CF] Next boundary: ICALL_SAFE target=8000000F ordinal=15"
Write-Host "[Phase6CF] API: ExAllocatePoolWithTag(NumberOfBytes, Tag)"
Write-Host "[Phase6CF] Live frame: esp=008BF908 saved=008BF914 delta=12 fault=0"
Write-Host "[Phase6CF] Batch: arm ordinals 14/15/17/23 with maintained guest-pool semantics"
Write-Host "[Phase6CF] 32M watchdog and all genuine hard fences preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){
  throw "Phase 6CF emitter syntax check failed"
}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 |
    Tee-Object -Variable phase6cfEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CF] EMITTER OUTPUT:"
  $phase6cfEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CF emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cf-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){
    throw "Missing Phase 6CF output: $f"
  }
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CF"-or$r.build_tag-ne"P6CF-EXPOOL-FAMILY-20261025-A"){
  throw "Phase 6CF manifest identity mismatch"
}
$a=$r.phase6cf_executive_pool_family
if($a.phase6ce_hardware.boundary_kind-ne"ICALL_SAFE"-or
   $a.phase6ce_hardware.caller-ne"0x0023A3CE"-or
   $a.phase6ce_hardware.target-ne"0x8000000F"-or
   $a.phase6ce_hardware.ordinal-ne15-or
   $a.phase6ce_hardware.frame_delta-ne12-or
   $a.phase6ce_hardware.ticks-ne26711208-or
   $a.phase6ce_hardware.fault-ne0-or
   $a.phase6ce_hardware.xapi_return-ne0-or
   $a.allocation_alignment-ne16-or
   $a.allocation_zero_fill-ne$true-or
   $a.translated_membership_changed-ne$false-or
   $a.xacteng_membership_changed-ne$false-or
   $a.execution_budget_inherited-ne32000000-or
   $a.dispatch_log_stride_inherited-ne4096-or
   $a.hard_fences_changed-ne$false){
  throw "Phase 6CF hardware/pool-family manifest gate failed"
}

$ordNames=@{}
$a.armed_ordinals.psobject.Properties|ForEach-Object{$ordNames[$_.Name]=[string]$_.Value}
if($ordNames["14"]-ne"ExAllocatePool"-or
   $ordNames["15"]-ne"ExAllocatePoolWithTag"-or
   $ordNames["17"]-ne"ExFreePool"-or
   $ordNames["23"]-ne"ExQueryPoolBlockSize"){
  throw "Phase 6CF ordinal family gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x8000000Eu",
  "_phase4c_target == 0x8000000Fu",
  "_phase4c_target == 0x80000011u",
  "_phase4c_target == 0x80000017u",
  "PASS: Phase 6CF ExAllocatePoolWithTag",
  "P6CF EXPOOL:",
  "phase4c_heap_allocate(PHASE4C_HEAP_ZERO_MEMORY, size)",
  "#define PHASE4C_EXEC_BUDGET 32000000u",
  "case 0x0027DB5Cu:",
  "phase6cf_env_build_cookie"
)){
  if(-not$text.Contains($marker)){
    throw "Phase 6CF source gate missing: $marker"
  }
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
$baseShardCount=@(Get-ChildItem -LiteralPath (Join-Path $base "translated_shards") -Filter "*.inl" -File).Count
if($shardCount-ne$baseShardCount){
  throw "Phase 6CF translated shard count mismatch: base=$baseShardCount out=$shardCount"
}

Write-Host "[Phase6CF] READY"
Write-Host "[Phase6CF] Executive pool ordinals : 14 / 15 / 17 / 23"
Write-Host "[Phase6CF] Backing                 : existing guest title heap"
Write-Host "[Phase6CF] Alignment               : 16 bytes"
Write-Host "[Phase6CF] Zero fill               : yes"
Write-Host ("[Phase6CF] Reused translated shards: {0}" -f $shardCount)
Write-Host "[Phase6CF] Translation changes     : 0"
Write-Host "[Phase6CF] XACTENG sweep changes   : 0"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CF-EXPOOL-FAMILY-20261025-A"
    ExpectedEnvCookie="phase6cf_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cf-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cf-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CF-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CF] BUILD PASS"
  Write-Host ("[Phase6CF] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CF-A.xex"))
}
