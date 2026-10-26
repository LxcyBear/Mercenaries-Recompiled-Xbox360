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
$base=Join-Path $root "build\phase6_native_graphics\xact_final_release_caller_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_indirect_release_caller_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6dj_xact_indirect_release_caller.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DJ input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6di-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6di=Join-Path $PSScriptRoot "Prepare-Phase6DI.ps1"
  if(-not(Test-Path -LiteralPath $prep6di)){
    throw "Phase 6DJ baseline missing and Phase 6DI regeneration script not found"
  }

  Write-Host "[Phase6DJ] Cached 6DI output missing; regenerating 6DI without solution build..."
  & $prep6di -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DJ could not regenerate 6DI baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6di-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DI"-or$m.build_tag-ne"P6DI-XACT-FINAL-RELEASE-CALLER-20261026-A"){
  throw "Phase 6DJ baseline identity mismatch"
}

$di=$m.phase6di_xact_final_release
if($di.release_function-ne"0x0027F2C2"-or
   $di.probe_only-ne$true-or
   $di.refcount_changed_by_probe-ne$false-or
   $di.destructor_suppressed-ne$false-or
   $di.free_suppressed-ne$false){
  throw "Phase 6DJ inherited 6DI policy mismatch"
}

Write-Host "[Phase6DJ] XACT INDIRECT FINAL-RELEASE CALLER PROBE"
Write-Host "[Phase6DJ] 6DI hardware: 01B5C320 refcount 1 -> 0 in 0027F2C2"
Write-Host "[Phase6DJ] 6DI direct-site tag: 0 => final Release arrived through indirect dispatch"
Write-Host "[Phase6DJ] Target: log translated ICALL owner only when runtime target == 0027F2C2"
Write-Host "[Phase6DJ] Refcount/destructor/free/dispatch semantics: UNCHANGED"
Write-Host "[Phase6DJ] C4146 cleanup: warning disabled ONLY around generated translated body"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DJ emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DJ-R1"')){
  throw "Phase 6DJ stale emitter detected; expected revision 6DJ-R1"
}
Write-Host "[Phase6DJ] Emitter revision       : 6DJ-R1"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6djEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DJ] EMITTER OUTPUT:"
  $phase6djEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DJ emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dj-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DJ output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DJ"-or$r.build_tag-ne"P6DJ-XACT-INDIRECT-RELEASE-CALLER-20261026-A"){
  throw "Phase 6DJ manifest identity mismatch"
}

$dj=$r.phase6dj_xact_indirect_release
if($dj.target-ne"0x0027F2C2"-or
   $dj.phase6di_hardware.object-ne"0x01B5C320"-or
   $dj.phase6di_hardware.ref_before-ne1-or
   $dj.phase6di_hardware.ref_after-ne0-or
   $dj.phase6di_hardware.direct_site-ne0-or
   $dj.probe_only-ne$true-or
   $dj.dispatch_semantics_changed-ne$false-or
   $dj.refcount_changed_by_probe-ne$false-or
   $dj.destructor_suppressed-ne$false-or
   $dj.free_suppressed-ne$false-or
   $dj.guest_memory_semantics_changed-ne$false-or
   $dj.generated_c4146_scope_only-ne$true-or
   $dj.native_c4146_still_enabled-ne$true-or
   $dj.execution_budget_inherited-ne64000000-or
   $dj.hard_fences_weakened-ne$false){
  throw "Phase 6DJ manifest gate failed"
}

if($dj.instrumented_icall_sites-lt1){
  throw "Phase 6DJ translated ICALL instrumentation is empty"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DJ-XACT-INDIRECT-RELEASE-CALLER-20261026-A",
  "phase6dj_env_build_cookie",
  "P6DJ XACT INDIRECT RELEASE CALLER:",
  "P6DJ XACT INDIRECT RELEASE:",
  "PHASE6DJ_ICALL_SAFE(phase6df_function_va,",
  "#pragma warning(disable:4146)",
  "P6DJ XACT RELEASE ENTRY:",
  "P6DJ XACT RELEASE AFTER:",
  "P6DJ XACT GLOBAL WRITE SITE:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DJ source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DJ translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DJ] READY"
Write-Host ("[Phase6DJ] Instrumented ICALL sites : {0}" -f $dj.instrumented_icall_sites)
Write-Host "[Phase6DJ] Money line:"
Write-Host "[Phase6DJ]   P6DJ XACT INDIRECT RELEASE CALLER: caller=... target=0027F2C2 object=01B5C320 ref=1"
Write-Host "[Phase6DJ] C4146 scope             : generated translated body only"
Write-Host "[Phase6DJ] Native warning coverage : unchanged"
Write-Host ("[Phase6DJ] Generated shards        : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DJ-XACT-INDIRECT-RELEASE-CALLER-20261026-A"
    ExpectedEnvCookie="phase6dj_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6dj-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6dj-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DJ-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DJ] BUILD PASS"
  Write-Host ("[Phase6DJ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DJ-A.xex"))
}
