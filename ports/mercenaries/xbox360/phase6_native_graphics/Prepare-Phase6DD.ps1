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
$base=Join-Path $root "build\phase6_native_graphics\xact_00280c39_provenance_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_280c39_arg1_internal_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6dd_xact_280c39_internal.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DD input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6dc-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6dc=Join-Path $PSScriptRoot "Prepare-Phase6DC.ps1"
  if(-not(Test-Path -LiteralPath $prep6dc)){
    throw "Phase 6DD baseline missing and Phase 6DC regeneration script not found"
  }

  Write-Host "[Phase6DD] Cached 6DC output missing; regenerating 6DC without solution build..."
  & $prep6dc -SkipSolutionBuild

  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DD could not regenerate 6DC baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6dc-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DC"-or$m.build_tag-ne"P6DC-XACT-00280C39-PROVENANCE-20261026-A"){
  throw "Phase 6DD baseline identity mismatch"
}

$dc=$m.phase6dc_xact_00280c39_provenance
if($dc.probe_only-ne$true-or
   $dc.guest_memory_semantics_changed-ne$false-or
   $dc.value_fabrication-ne$false-or
   $dc.fault_suppression-ne$false-or
   $dc.address_range_widened-ne$false-or
   $dc.execution_budget_inherited-ne64000000-or
   $dc.hard_fences_weakened-ne$false){
  throw "Phase 6DD inherited 6DC policy mismatch"
}

Write-Host "[Phase6DD] XACT 00280C39 INTERNAL ARG1 PRODUCER TRACE"
Write-Host "[Phase6DD] 6DC proved caller 0027ED57 enters 00280C39 with normal args"
Write-Host "[Phase6DD] 00280C39 itself later emits FBE2 arg1=00041D90"
Write-Host "[Phase6DD] New probe: every 00280C39 basic block + every READ32"
Write-Host "[Phase6DD] Ring dumps immediately before failing FBE2 handoff"
Write-Host "[Phase6DD] Pointer substitution: NONE"
Write-Host "[Phase6DD] Fault suppression: NONE"
Write-Host "[Phase6DD] Address widening: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DD emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DD-R1"')){
  throw "Phase 6DD stale emitter detected; expected revision 6DD-R1"
}
Write-Host "[Phase6DD] Emitter revision       : 6DD-R1"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6ddEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DD] EMITTER OUTPUT:"
  $phase6ddEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DD emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dd-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DD output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DD"-or$r.build_tag-ne"P6DD-XACT-280C39-ARG1-INTERNAL-20261026-A"){
  throw "Phase 6DD manifest identity mismatch"
}

$dd=$r.phase6dd_xact_280c39_internal
if($dd.hardware_proof.caller_of_280c39-ne"0x0027ED57"-or
   $dd.hardware_proof.fbe2_arg1-ne"0x00041D90"-or
   $dd.hardware_proof.downstream_bad_object-ne"0x00041D88"-or
   $dd.hardware_proof.fault_address-ne"0xCCCCCCD0"-or
   $dd.probe_only-ne$true-or
   $dd.guest_memory_semantics_changed-ne$false-or
   $dd.value_fabrication-ne$false-or
   $dd.fault_suppression-ne$false-or
   $dd.address_range_widened-ne$false-or
   $dd.execution_budget_inherited-ne64000000-or
   $dd.hard_fences_weakened-ne$false){
  throw "Phase 6DD manifest gate failed"
}

if($dd.basic_block_count-lt1-or$dd.read_site_count-lt1){
  throw "Phase 6DD target instrumentation is empty"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DD-XACT-280C39-ARG1-INTERNAL-20261026-A",
  "phase6dd_env_build_cookie",
  "P6DD 280C39 READ32:",
  "P6DD 280C39 RING BEGIN:",
  "P6DD 280C39 RING[",
  "P6DD 280C39 INTERNAL:",
  "P6DD XACT 00280C39 ENTRY:",
  "P6DD FBE2 CALLER:",
  "P6DD PREFAULT ROUTER READ32:",
  "PASS: Phase 6DD ExFreePool ITAIL",
  "PASS: Phase 6DD manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6DD APU CORE:",
  "P6DD AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DD source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DD translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DD] READY"
Write-Host ("[Phase6DD] 00280C39 basic blocks : {0}" -f $dd.basic_block_count)
Write-Host ("[Phase6DD] 00280C39 READ32 sites  : {0}" -f $dd.read_site_count)
Write-Host ("[Phase6DD] Ring capacity          : {0}" -f $dd.ring_capacity)
Write-Host "[Phase6DD] Money lines:"
Write-Host "[Phase6DD]   P6DD 280C39 READ32: ... value=00041D90 ..."
Write-Host "[Phase6DD]   P6DD 280C39 RING BEGIN: ..."
Write-Host "[Phase6DD]   P6DD 280C39 RING[..]: va=... registers..."
Write-Host "[Phase6DD] Guest-memory semantics : unchanged"
Write-Host "[Phase6DD] Pointer fabrication    : NO"
Write-Host "[Phase6DD] Fault suppression      : NO"
Write-Host ("[Phase6DD] Generated shards       : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DD-XACT-280C39-ARG1-INTERNAL-20261026-A"
    ExpectedEnvCookie="phase6dd_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6dd-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6dd-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DD-A.xex")
  }

  & $builder @buildArgs
  Write-Host "[Phase6DD] BUILD PASS"
  Write-Host ("[Phase6DD] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DD-A.xex"))
}
