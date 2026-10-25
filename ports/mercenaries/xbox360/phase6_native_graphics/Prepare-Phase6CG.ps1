[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\expool_family_xdk"
$out=Join-Path $root "build\phase6_native_graphics\kfraiseirql160_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6cg_kfraiseirql160.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CG input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cf-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cf=Join-Path $PSScriptRoot "Prepare-Phase6CF.ps1"
  if(-not(Test-Path -LiteralPath $prep6cf)){
    throw "Phase 6CG baseline missing and Phase 6CF regeneration script not found"
  }
  Write-Host "[Phase6CG] Cached 6CF output missing; regenerating 6CF without solution build..."
  & $prep6cf -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6CG could not regenerate 6CF baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cf-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CF"-or$m.build_tag-ne"P6CF-EXPOOL-FAMILY-20261025-A"){
  throw "Phase 6CG baseline identity mismatch"
}
if($m.phase6cf_executive_pool_family.execution_budget_inherited-ne32000000-or
   $m.phase6cf_executive_pool_family.translated_membership_changed-ne$false-or
   $m.phase6cf_executive_pool_family.hard_fences_changed-ne$false){
  throw "Phase 6CG inherited 6CF policy mismatch"
}

Write-Host "[Phase6CG] KFRAISEIRQL160 GUEST-IRQL CONTINUATION"
Write-Host "[Phase6CG] 6CF hardware: executive pool family PASS (3 tagged alloc + 3 query)"
Write-Host "[Phase6CG] Next boundary: ICALL_SAFE 0023A3CE -> 800000A0"
Write-Host "[Phase6CG] Ordinal 160: KfRaiseIrql(KIRQL NewIrql)"
Write-Host "[Phase6CG] Live frame: esp=008BF86C saved=008BF870 delta=4 fault=0"
Write-Host "[Phase6CG] ECX=008BF802 -> CL=2; maintained guest IRQL before=0"
Write-Host "[Phase6CG] Semantics: guest-only raise, old IRQL returned in EAX"
Write-Host "[Phase6CG] 32M watchdog and all hard fences preserved"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6CG emitter syntax check failed"}

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter "--base-dir" $base "--out-dir" $out 2>&1 |
    Tee-Object -Variable phase6cgEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}
if($emitRc-ne0){
  Write-Host "[Phase6CG] EMITTER OUTPUT:"
  $phase6cgEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6CG emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6cg-manifest.json"
$shards=Join-Path $out "translated_shards"
foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6CG output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6CG"-or$r.build_tag-ne"P6CG-KFRAISEIRQL160-20261025-A"){
  throw "Phase 6CG manifest identity mismatch"
}
$a=$r.phase6cg_kf_raise_irql
if($a.phase6cf_hardware.boundary_kind-ne"ICALL_SAFE"-or
   $a.phase6cf_hardware.caller-ne"0x0023A3CE"-or
   $a.phase6cf_hardware.target-ne"0x800000A0"-or
   $a.phase6cf_hardware.ordinal-ne160-or
   $a.phase6cf_hardware.frame_delta-ne4-or
   $a.phase6cf_hardware.ticks-ne26711301-or
   $a.phase6cf_hardware.fault-ne0-or
   $a.phase6cf_hardware.new_irql_from_cl-ne2-or
   $a.phase6cf_hardware.guest_irql_before-ne0-or
   $a.phase6cf_hardware.xapi_return-ne0-or
   $a.semantics.host_xenon_irql_changed-ne$false-or
   $a.translated_membership_changed-ne$false-or
   $a.xacteng_membership_changed-ne$false-or
   $a.executive_pool_semantics_changed-ne$false-or
   $a.execution_budget_inherited-ne32000000-or
   $a.dispatch_log_stride_inherited-ne4096-or
   $a.hard_fences_changed-ne$false){
  throw "Phase 6CG hardware/IRQL manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "_phase4c_target == 0x800000A0u",
  "phase6cg_kf_raise_irql",
  "KfRaiseIrql LIVE FRAME:",
  "PASS: Phase 6CG KfRaiseIrql guest continuation",
  "P6CG KFRAISEIRQL160:",
  "P6CG KFLOWERIRQL161:",
  "P6CG EXPOOL:",
  "#define PHASE4C_EXEC_BUDGET 32000000u",
  "phase6cg_env_build_cookie"
)){
  if(-not$text.Contains($marker)){throw "Phase 6CG source gate missing: $marker"}
}

$statePos=$text.IndexOf("static uint32_t s_phase6cgKfRaiseIrqlCallCount = 0u;")
$summaryPos=$text.IndexOf("P6CG KFRAISEIRQL160:")
if($statePos-lt0-or$summaryPos-lt0-or$statePos-gt$summaryPos){
  throw "Phase 6CG declaration-order gate failed"
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
$baseShardCount=@(Get-ChildItem -LiteralPath (Join-Path $base "translated_shards") -Filter "*.inl" -File).Count
if($shardCount-ne$baseShardCount){
  throw "Phase 6CG translated shard count mismatch: base=$baseShardCount out=$shardCount"
}

Write-Host "[Phase6CG] READY"
Write-Host "[Phase6CG] KfRaiseIrql guest model  : 0 -> CL (2), old returned in EAX"
Write-Host "[Phase6CG] Host Xenon IRQL          : untouched"
Write-Host ("[Phase6CG] Reused translated shards : {0}" -f $shardCount)
Write-Host "[Phase6CG] Translation changes      : 0"
Write-Host "[Phase6CG] XACTENG/pool changes     : 0"

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6CG-KFRAISEIRQL160-20261025-A"
    ExpectedEnvCookie="phase6cg_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6cg-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6cg-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6CG-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6CG] BUILD PASS"
  Write-Host ("[Phase6CG] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6CG-A.xex"))
}
