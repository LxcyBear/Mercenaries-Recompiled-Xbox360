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
$base=Join-Path $root "build\phase6_native_graphics\dsound_arg_lineage_xdk"
$out=Join-Path $root "build\phase6_native_graphics\dsound_fbe2_caller_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6db_dsound_fbe2_caller.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DB input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6da-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6da=Join-Path $PSScriptRoot "Prepare-Phase6DA.ps1"
  if(-not(Test-Path -LiteralPath $prep6da)){
    throw "Phase 6DB baseline missing and Phase 6DA regeneration script not found"
  }
  Write-Host "[Phase6DB] Cached 6DA output missing; regenerating 6DA without solution build..."
  & $prep6da -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DB could not regenerate 6DA baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6da-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6DA"-or$m.build_tag-ne"P6DA-DSOUND-ARG-LINEAGE-00041D88-20261026-A"){
  throw "Phase 6DB baseline identity mismatch"
}
$da=$m.phase6da_dsound_argument_lineage
if($da.probe_only-ne$true-or
   $da.guest_memory_semantics_changed-ne$false-or
   $da.value_fabrication-ne$false-or
   $da.address_range_widened-ne$false-or
   $da.execution_budget_inherited-ne64000000-or
   $da.hard_fences_weakened-ne$false){
  throw "Phase 6DB inherited 6DA policy mismatch"
}

Write-Host "[Phase6DB] DSOUND FBE2 CALLER PROVENANCE"
Write-Host "[Phase6DB] Hardware: F992 arg1=00041D88 arg2=008BF924 arg3=01B5DE7C arg4=00000000"
Write-Host "[Phase6DB] Static relation: F992.arg1 = FBE2.arg1 - 8 when nonzero"
Write-Host "[Phase6DB] Therefore failing FBE2 arg1 must be 00041D90"
Write-Host "[Phase6DB] Probe: every direct caller immediately before dummy-return push"
Write-Host "[Phase6DB] Pointer substitution: NONE"
Write-Host "[Phase6DB] Fault suppression: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DB emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DB-R1"')){
  throw "Phase 6DB stale emitter detected; expected revision 6DB-R1"
}
Write-Host "[Phase6DB] Emitter revision       : 6DB-R1"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6dbEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DB] EMITTER OUTPUT:"
  $phase6dbEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DB emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6db-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DB output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DB"-or$r.build_tag-ne"P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A"){
  throw "Phase 6DB manifest identity mismatch"
}

$db=$r.phase6db_dsound_fbe2_caller
if($db.hardware_proof.f992_arg1-ne"0x00041D88"-or
   $db.static_relation.expected_fbe2_arg1-ne"0x00041D90"-or
   $db.probe_only-ne$true-or
   $db.guest_memory_semantics_changed-ne$false-or
   $db.value_fabrication-ne$false-or
   $db.fault_suppression-ne$false-or
   $db.address_range_widened-ne$false-or
   $db.execution_budget_inherited-ne64000000-or
   $db.hard_fences_weakened-ne$false){
  throw "Phase 6DB manifest gate failed"
}

if(@($db.direct_caller_audit).Count-lt1){
  throw "Phase 6DB direct caller audit is empty"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A",
  "phase6db_env_build_cookie",
  "P6DB FBE2 ENTRY:",
  "P6DB FBE2 CALLER:",
  "P6DB FBE2 PROVENANCE:",
  "P6DB DSOUND ARG: stage=1 func=0029F992",
  "P6DB PREFAULT ROUTER READ32:",
  "PASS: Phase 6DB ExFreePool ITAIL",
  "PASS: Phase 6DB manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6DB APU CORE:",
  "P6DB AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DB source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DB translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DB] READY"
Write-Host "[Phase6DB] Expected failing FBE2 arg1     : 00041D90"
Write-Host "[Phase6DB] Direct caller audit:"
foreach($row in @($db.direct_caller_audit)){
  Write-Host ("[Phase6DB]   site={0} caller={1} name={2}" -f $row.site,$row.caller_va,$row.caller_name)
}
Write-Host "[Phase6DB] Money line: P6DB FBE2 CALLER: ... arg1=00041D90 ..."
Write-Host "[Phase6DB] Guest-memory semantics         : unchanged"
Write-Host "[Phase6DB] Pointer fabrication            : NO"
Write-Host "[Phase6DB] Fault suppression              : NO"
Write-Host ("[Phase6DB] Generated shards               : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DB-DSOUND-FBE2-CALLER-00041D90-20261026-A"
    ExpectedEnvCookie="phase6db_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6db-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6db-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DB-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6DB] BUILD PASS"
  Write-Host ("[Phase6DB] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DB-A.xex"))
}
