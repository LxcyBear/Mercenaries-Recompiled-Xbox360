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
$base=Join-Path $root "build\phase6_native_graphics\xact_global_0028836c_provenance_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_global_0028836c_write_site_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6df_xact_global_write_site.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DF input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6de-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6de=Join-Path $PSScriptRoot "Prepare-Phase6DE.ps1"
  if(-not(Test-Path -LiteralPath $prep6de)){
    throw "Phase 6DF baseline missing and Phase 6DE regeneration script not found"
  }

  Write-Host "[Phase6DF] Cached 6DE output missing; regenerating 6DE without solution build..."
  & $prep6de -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DF could not regenerate 6DE baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6de-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DE"-or$m.build_tag-ne"P6DE-XACT-GLOBAL-0028836C-PROVENANCE-20261026-A"){
  throw "Phase 6DF baseline identity mismatch"
}

$de=$m.phase6de_xact_global_0028836c
if($de.central_write_watch-ne$true-or
   $de.probe_only-ne$true-or
   $de.guest_memory_semantics_changed-ne$false-or
   $de.value_fabrication-ne$false-or
   $de.fault_suppression-ne$false-or
   $de.address_range_widened-ne$false-or
   $de.execution_budget_inherited-ne64000000-or
   $de.hard_fences_weakened-ne$false){
  throw "Phase 6DF inherited 6DE policy mismatch"
}

Write-Host "[Phase6DF] XACT GLOBAL 0028836C EXACT WRITE-SITE ATTRIBUTION"
Write-Host "[Phase6DF] 6DE hardware proved: 01B5C320 -> global, then global -> 0, then 01B5C320 freed"
Write-Host "[Phase6DF] New probe: exact translated function VA + source line for writes to 0028836C"
Write-Host "[Phase6DF] Value substitution: NONE"
Write-Host "[Phase6DF] Write suppression: NONE"
Write-Host "[Phase6DF] Fault suppression: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DF emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DF-R1"')){
  throw "Phase 6DF stale emitter detected; expected revision 6DF-R1"
}
Write-Host "[Phase6DF] Emitter revision       : 6DF-R1"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dfEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DF] EMITTER OUTPUT:"
  $phase6dfEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DF emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6df-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DF output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DF"-or$r.build_tag-ne"P6DF-XACT-GLOBAL-0028836C-WRITE-SITE-20261026-A"){
  throw "Phase 6DF manifest identity mismatch"
}

$df=$r.phase6df_xact_global_write_site
if($df.phase6de_hardware.global_address-ne"0x0028836C"-or
   $df.phase6de_hardware.first_value-ne"0x01B5C320"-or
   $df.phase6de_hardware.second_value-ne"0x00000000"-or
   $df.phase6de_hardware.freed_object-ne"0x01B5C320"-or
   $df.probe_only-ne$true-or
   $df.guest_memory_semantics_changed-ne$false-or
   $df.value_fabrication-ne$false-or
   $df.write_suppression-ne$false-or
   $df.fault_suppression-ne$false-or
   $df.address_range_widened-ne$false-or
   $df.execution_budget_inherited-ne64000000-or
   $df.hard_fences_weakened-ne$false){
  throw "Phase 6DF manifest gate failed"
}

if($df.instrumented_write32_sites-lt1-or$df.instrumented_functions-lt1){
  throw "Phase 6DF translated WRITE32 instrumentation is empty"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DF-XACT-GLOBAL-0028836C-WRITE-SITE-20261026-A",
  "phase6df_env_build_cookie",
  "P6DF XACT GLOBAL WRITE SITE:",
  "P6DF XACT GLOBAL WRITE SITE SUMMARY:",
  "phase6df_write32_site(phase6df_function_va",
  "P6DF XACT GLOBAL WRITE32:",
  "P6DF XACT GLOBAL 0028836C:",
  "P6DF 280C39 READ32:",
  "P6DF PREFAULT ROUTER READ32:",
  "PASS: Phase 6DF ExFreePool ITAIL",
  "PASS: Phase 6DF manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DF source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DF translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DF] READY"
Write-Host ("[Phase6DF] Instrumented WRITE32 sites : {0}" -f $df.instrumented_write32_sites)
Write-Host ("[Phase6DF] Instrumented functions    : {0}" -f $df.instrumented_functions)
Write-Host "[Phase6DF] Money lines:"
Write-Host "[Phase6DF]   P6DF XACT GLOBAL WRITE SITE: func=... line=... value=01B5C320"
Write-Host "[Phase6DF]   P6DF XACT GLOBAL WRITE SITE: func=... line=... value=00000000"
Write-Host "[Phase6DF] Guest-memory semantics : unchanged"
Write-Host "[Phase6DF] Value fabrication      : NO"
Write-Host "[Phase6DF] Write suppression      : NO"
Write-Host "[Phase6DF] Fault suppression      : NO"
Write-Host ("[Phase6DF] Generated shards       : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DF-XACT-GLOBAL-0028836C-WRITE-SITE-20261026-A"
    ExpectedEnvCookie="phase6df_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6df-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6df-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DF-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DF] BUILD PASS"
  Write-Host ("[Phase6DF] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DF-A.xex"))
}
