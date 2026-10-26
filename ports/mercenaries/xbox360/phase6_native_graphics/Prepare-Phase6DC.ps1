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
$base=Join-Path $root "build\phase6_native_graphics\dsound_fbe2_caller_xdk"
$out=Join-Path $root "build\phase6_native_graphics\xact_00280c39_provenance_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6dc_xact_00280c39_provenance.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DC input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6db-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6db=Join-Path $PSScriptRoot "Prepare-Phase6DB.ps1"
  if(-not(Test-Path -LiteralPath $prep6db)){
    throw "Phase 6DC baseline missing and Phase 6DB regeneration script not found"
  }
  Write-Host "[Phase6DC] Cached 6DB output missing; regenerating 6DB without solution build..."
  & $prep6db -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DC could not regenerate 6DB baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6db-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DB"-or$m.build_tag-ne"P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A"){
  throw "Phase 6DC baseline identity mismatch"
}
$db=$m.phase6db_dsound_fbe2_caller
if($db.probe_only-ne$true-or
   $db.guest_memory_semantics_changed-ne$false-or
   $db.value_fabrication-ne$false-or
   $db.fault_suppression-ne$false-or
   $db.address_range_widened-ne$false-or
   $db.execution_budget_inherited-ne64000000-or
   $db.hard_fences_weakened-ne$false){
  throw "Phase 6DC inherited 6DB policy mismatch"
}

Write-Host "[Phase6DC] XACT 00280C39 UPSTREAM PROVENANCE"
Write-Host "[Phase6DC] Hardware: 00280C39 passes 00041D90 to FBE2"
Write-Host "[Phase6DC] Probe: target source audit + target entry args + direct callers"
Write-Host "[Phase6DC] Pointer substitution: NONE"
Write-Host "[Phase6DC] Fault suppression: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DC emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DC-R1"')){
  throw "Phase 6DC stale emitter detected; expected revision 6DC-R1"
}
Write-Host "[Phase6DC] Emitter revision       : 6DC-R1"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dcEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DC] EMITTER OUTPUT:"
  $phase6dcEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DC emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6dc-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DC output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DC"-or$r.build_tag-ne"P6DC-XACT-00280C39-PROVENANCE-20261026-A"){
  throw "Phase 6DC manifest identity mismatch"
}

$dc=$r.phase6dc_xact_00280c39_provenance
if($dc.hardware_proof.fbe2_caller-ne"0x00280C39"-or
   $dc.hardware_proof.fbe2_arg1-ne"0x00041D90"-or
   $dc.probe_only-ne$true-or
   $dc.guest_memory_semantics_changed-ne$false-or
   $dc.value_fabrication-ne$false-or
   $dc.fault_suppression-ne$false-or
   $dc.address_range_widened-ne$false-or
   $dc.execution_budget_inherited-ne64000000-or
   $dc.hard_fences_weakened-ne$false){
  throw "Phase 6DC manifest gate failed"
}

if(@($dc.target_source_lines).Count-lt1){
  throw "Phase 6DC target source audit is empty"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DC-XACT-00280C39-PROVENANCE-20261026-A",
  "phase6dc_env_build_cookie",
  "P6DC XACT 00280C39 ENTRY:",
  "P6DC XACT 00280C39 PROVENANCE:",
  "P6DC FBE2 CALLER:",
  "P6DC PREFAULT ROUTER READ32:",
  "PASS: Phase 6DC ExFreePool ITAIL",
  "PASS: Phase 6DC manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "#define PHASE4C_EXEC_BUDGET 64000000u",
  "P6DC APU CORE:",
  "P6DC AV/DISPLAY SUMMARY:"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DC source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DC translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DC] READY"
Write-Host "[Phase6DC] Target                     : sub_00280C39"
Write-Host "[Phase6DC] Hardware-proven FBE2 arg1 : 00041D90"
Write-Host ("[Phase6DC] Target source lines        : {0}" -f @($dc.target_source_lines).Count)
Write-Host ("[Phase6DC] Literal references         : {0}" -f @($dc.literal_reference_audit).Count)
Write-Host ("[Phase6DC] Direct caller sites        : {0}" -f @($dc.direct_caller_audit).Count)
foreach($row in @($dc.direct_caller_audit)){
  Write-Host ("[Phase6DC]   site={0} caller={1} name={2}" -f $row.site,$row.caller_va,$row.caller_name)
}
Write-Host "[Phase6DC] Money line: P6DC XACT 00280C39 ENTRY: ..."
Write-Host "[Phase6DC] Guest-memory semantics      : unchanged"
Write-Host "[Phase6DC] Pointer fabrication         : NO"
Write-Host "[Phase6DC] Fault suppression           : NO"
Write-Host ("[Phase6DC] Generated shards            : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DC-XACT-00280C39-PROVENANCE-20261026-A"
    ExpectedEnvCookie="phase6dc_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6dc-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6dc-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DC-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6DC] BUILD PASS"
  Write-Host ("[Phase6DC] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DC-A.xex"))
}
