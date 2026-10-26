[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p4=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python=Join-Path $root ".venv\Scripts\python.exe"
$base=Join-Path $root "build\phase6_native_graphics\xact_global_0028836c_write_site_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_final_release_caller_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6di_xact_final_release.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DI input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6df-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6df=Join-Path $PSScriptRoot "Prepare-Phase6DF.ps1"
  if(-not(Test-Path -LiteralPath $prep6df)){
    throw "Phase 6DI baseline missing and Phase 6DF regeneration script not found"
  }

  Write-Host "[Phase6DI] Cached 6DF output missing; regenerating 6DF without solution build..."
  & $prep6df -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DI could not regenerate 6DF baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6df-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DF"-or$m.build_tag-ne"P6DF-XACT-GLOBAL-0028836C-WRITE-SITE-20261026-A"){
  throw "Phase 6DI baseline identity mismatch"
}

Write-Host "[Phase6DI] XACT FINAL RELEASE CALLER PROBE"
Write-Host "[Phase6DI] Proven Release: 0027F2C2 --refcount; zero -> 0027F282 -> 0027F194"
Write-Host "[Phase6DI] Candidate caller site 1: 00280062"
Write-Host "[Phase6DI] Candidate caller site 2: 00282A9B"
Write-Host "[Phase6DI] Refcount modification by probe: NONE"
Write-Host "[Phase6DI] Destructor suppression: NONE"
Write-Host "[Phase6DI] Free suppression: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DI emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DI-R1"')){
  throw "Phase 6DI stale emitter detected; expected revision 6DI-R1"
}
Write-Host "[Phase6DI] Emitter revision       : 6DI-R1"

if(Test-Path $out){Remove-Item $out -Recurse -Force}
New-Item -ItemType Directory -Force -Path $out|Out-Null

$emitArgs=@(
  "--base-dir",$base,
  "--base-emitter",$baseEmitter,
  "--phase6bl-emitter",$p6bl,
  "--out-dir",$out
)

$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6diEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DI] EMITTER OUTPUT:"
  $phase6diEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DI emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6di-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DI output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DI"-or$r.build_tag-ne"P6DI-XACT-FINAL-RELEASE-CALLER-20261026-A"){
  throw "Phase 6DI manifest identity mismatch"
}

$di=$r.phase6di_xact_final_release
if($di.release_function-ne"0x0027F2C2"-or
   $di.deleting_destructor-ne"0x0027F282"-or
   $di.destructor-ne"0x0027F194"-or
   $di.global-ne"0x0028836C"-or
   $di.probe_only-ne$true-or
   $di.refcount_changed_by_probe-ne$false-or
   $di.destructor_suppressed-ne$false-or
   $di.free_suppressed-ne$false-or
   $di.guest_memory_semantics_changed-ne$false-or
   $di.execution_budget_inherited-ne64000000-or
   $di.hard_fences_weakened-ne$false){
  throw "Phase 6DI manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DI-XACT-FINAL-RELEASE-CALLER-20261026-A",
  "phase6di_env_build_cookie",
  "P6DI XACT RELEASE CALLER:",
  "P6DI XACT RELEASE ENTRY:",
  "P6DI XACT RELEASE AFTER:",
  "P6DI XACT FINAL RELEASE:",
  "phase6di_release_callsite(1u, 0x00280062u",
  "phase6di_release_callsite(2u, 0x00282A9Bu",
  "phase6di_release_before(ecx",
  "P6DI XACT GLOBAL WRITE SITE:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DI source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DI translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DI] READY"
Write-Host "[Phase6DI] Money line:"
Write-Host "[Phase6DI]   P6DI XACT RELEASE AFTER: site=... caller=... object=01B5C320 ref_after=0"
Write-Host "[Phase6DI] Refcount semantics     : unchanged"
Write-Host "[Phase6DI] Destructor semantics   : unchanged"
Write-Host "[Phase6DI] Free semantics         : unchanged"
Write-Host ("[Phase6DI] Generated shards      : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DI-XACT-FINAL-RELEASE-CALLER-20261026-A"
    ExpectedEnvCookie="phase6di_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6di-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6di-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DI-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DI] BUILD PASS"
  Write-Host ("[Phase6DI] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DI-A.xex"))
}
