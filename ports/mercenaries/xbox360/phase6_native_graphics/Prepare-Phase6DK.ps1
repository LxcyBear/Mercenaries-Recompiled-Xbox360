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
$base=Join-Path $root "build\phase6_native_graphics\xact_indirect_release_caller_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_release_pretrace_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6dk_xact_release_pretrace.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DK input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6dj-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6dj=Join-Path $PSScriptRoot "Prepare-Phase6DJ.ps1"
  if(-not(Test-Path -LiteralPath $prep6dj)){
    throw "Phase 6DK baseline missing and Phase 6DJ regeneration script not found"
  }

  Write-Host "[Phase6DK] Cached 6DJ output missing; regenerating 6DJ without solution build..."
  & $prep6dj -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DK could not regenerate 6DJ baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6dj-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DJ"-or$m.build_tag-ne"P6DJ-XACT-INDIRECT-RELEASE-CALLER-20261026-A"){
  throw "Phase 6DK baseline identity mismatch"
}

$dj=$m.phase6dj_xact_indirect_release
if($dj.target-ne"0x0027F2C2"-or
   $dj.probe_only-ne$true-or
   $dj.dispatch_semantics_changed-ne$false-or
   $dj.refcount_changed_by_probe-ne$false-or
   $dj.destructor_suppressed-ne$false-or
   $dj.free_suppressed-ne$false){
  throw "Phase 6DK inherited 6DJ policy mismatch"
}

Write-Host "[Phase6DK] XACT RELEASE PRETRACE / PACK-LOOKUP PROBE"
Write-Host "[Phase6DK] 6DI hardware: 01B5C320 refcount 1 -> 0 in 0027F2C2"
Write-Host "[Phase6DK] 6DJ hardware: 9035 translated ICALL_SAFE sites, zero hits to 0027F2C2"
Write-Host "[Phase6DK] New: capture prior traced VA BEFORE 0027F2C2 records itself"
Write-Host "[Phase6DK] New: log packed lookup requests for 0027F2C2"
Write-Host "[Phase6DK] Refcount/destructor/free/dispatch semantics: UNCHANGED"
Write-Host "[Phase6DK] C4146 generated-code cleanup: inherited"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DK emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DK-R1"')){
  throw "Phase 6DK stale emitter detected; expected revision 6DK-R1"
}
Write-Host "[Phase6DK] Emitter revision       : 6DK-R1"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dkEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DK] EMITTER OUTPUT:"
  $phase6dkEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DK emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dk-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DK output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DK"-or$r.build_tag-ne"P6DK-XACT-RELEASE-PRETRACE-20261026-A"){
  throw "Phase 6DK manifest identity mismatch"
}

$dk=$r.phase6dk_xact_release_pretrace
if($dk.target-ne"0x0027F2C2"-or
   $dk.phase6di_hardware.object-ne"0x01B5C320"-or
   $dk.phase6di_hardware.ref_before-ne1-or
   $dk.phase6di_hardware.ref_after-ne0-or
   $dk.phase6dj_hardware.instrumented_icall_sites-ne9035-or
   $dk.phase6dj_hardware.indirect_release_reports-ne0-or
   $dk.pretrace_probe-ne$true-or
   $dk.pack_lookup_probe-ne$true-or
   $dk.probe_only-ne$true-or
   $dk.dispatch_semantics_changed-ne$false-or
   $dk.refcount_changed_by_probe-ne$false-or
   $dk.destructor_suppressed-ne$false-or
   $dk.free_suppressed-ne$false-or
   $dk.guest_memory_semantics_changed-ne$false-or
   $dk.generated_c4146_scope_inherited-ne$true-or
   $dk.execution_budget_inherited-ne64000000-or
   $dk.hard_fences_weakened-ne$false){
  throw "Phase 6DK manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DK-XACT-RELEASE-PRETRACE-20261026-A",
  "phase6dk_env_build_cookie",
  "P6DK XACT RELEASE PRETRACE:",
  "P6DK XACT RELEASE PACK LOOKUP:",
  "P6DK XACT RELEASE ORIGIN:",
  "P6DK XACT RELEASE ENTRY:",
  "P6DK XACT RELEASE AFTER:",
  "#pragma warning(disable:4146)",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DK source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DK translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DK] READY"
Write-Host "[Phase6DK] Money line:"
Write-Host "[Phase6DK]   P6DK XACT RELEASE PRETRACE: previous=... target=0027F2C2 object=01B5C320 ref=1"
Write-Host "[Phase6DK] Secondary line:"
Write-Host "[Phase6DK]   P6DK XACT RELEASE PACK LOOKUP: caller=... target=0027F2C2 ..."
Write-Host "[Phase6DK] C4146 scope             : inherited generated translated body only"
Write-Host ("[Phase6DK] Generated shards        : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DK-XACT-RELEASE-PRETRACE-20261026-A"
    ExpectedEnvCookie="phase6dk_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6dk-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6dk-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DK-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DK] BUILD PASS"
  Write-Host ("[Phase6DK] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DK-A.xex"))
}
