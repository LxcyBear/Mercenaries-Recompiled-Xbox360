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
$base=Join-Path $root "build\phase6_native_graphics\prefault_ccccccd0_provenance_xdk"
$out=Join-Path $root "build\phase6_native_graphics\dsound_arg_lineage_xdk"
$emitter=Join-Path $PSScriptRoot "emit_phase6da_dsound_arg_lineage.py"
$baseEmitter=Join-Path $p4 "emit_phase4c_startup_slice.py"
$p6bl=Join-Path $PSScriptRoot "emit_phase6bl_d3d_frontier_0028b180.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

foreach($f in @($python,$emitter,$baseEmitter,$p6bl,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DA input: $f"}
}

$baseFiles=@(
  (Join-Path $base "main.cpp"),
  (Join-Path $base "main_monolithic.cpp"),
  (Join-Path $base "phase5_env.cpp"),
  (Join-Path $base "phase6cz-manifest.json"),
  (Join-Path $base "translated_shards")
)
$missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
if($missing.Count-gt0){
  $prep6cz=Join-Path $PSScriptRoot "Prepare-Phase6CZ.ps1"
  if(-not(Test-Path -LiteralPath $prep6cz)){
    throw "Phase 6DA baseline missing and Phase 6CZ regeneration script not found"
  }
  Write-Host "[Phase6DA] Cached 6CZ output missing; regenerating 6CZ without solution build..."
  & $prep6cz -SkipSolutionBuild
  $missing=@($baseFiles|Where-Object{-not(Test-Path -LiteralPath $_)})
  if($missing.Count-gt0){
    throw ("Phase 6DA could not regenerate 6CZ baseline. Missing: "+($missing-join", "))
  }
}

$m=Get-Content (Join-Path $base "phase6cz-manifest.json") -Raw|ConvertFrom-Json
if($m.phase-ne"6CZ"-or$m.build_tag-ne"P6CZ-PREFAULT-CCCCCCD0-PROVENANCE-20261026-A"){
  throw "Phase 6DA baseline identity mismatch"
}
$cz=$m.phase6cz_prefault_ccccccd0_provenance
if($cz.guest_memory_semantics_changed-ne$false-or
   $cz.value_fabrication-ne$false-or
   $cz.address_range_widened-ne$false-or
   $cz.execution_budget_inherited-ne64000000-or
   $cz.hard_fences_weakened-ne$false){
  throw "Phase 6DA inherited 6CZ policy mismatch"
}

Write-Host "[Phase6DA] DSOUND ARGUMENT LINEAGE"
Write-Host "[Phase6DA] Hardware: sub_002A41EE received object arg 00041D88"
Write-Host "[Phase6DA] Hardware: [00041D88]=CCCCCCCC -> [CCCCCCD0] fault"
Write-Host "[Phase6DA] Static proof: 0029F992 forwards incoming arg1 through 0029EBEA -> 0029EA79 -> 002A41EE"
Write-Host "[Phase6DA] Probe: entry args + prior VA at each stage"
Write-Host "[Phase6DA] Pointer substitution: NONE"
Write-Host "[Phase6DA] Fault suppression: NONE"

& $python -m py_compile $emitter
if($LASTEXITCODE-ne0){throw "Phase 6DA emitter syntax check failed"}

$emitterText=Get-Content $emitter -Raw
if(-not$emitterText.Contains('EMITTER_REVISION = "6DA-R2"')){
  throw "Phase 6DA stale emitter detected; expected revision 6DA-R2"
}
Write-Host "[Phase6DA] Emitter revision       : 6DA-R2"

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
  & $python $emitter @emitArgs 2>&1 | Tee-Object -Variable phase6daEmitOutput
  $emitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$old
}

if($emitRc-ne0){
  Write-Host "[Phase6DA] EMITTER OUTPUT:"
  $phase6daEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6DA emission/preflight failed (exit $emitRc)"
}

$main=Join-Path $out "main.cpp"
$mono=Join-Path $out "main_monolithic.cpp"
$env=Join-Path $out "phase5_env.cpp"
$manifest=Join-Path $out "phase6da-manifest.json"
$shards=Join-Path $out "translated_shards"

foreach($f in @($main,$mono,$env,$manifest,$shards)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DA output: $f"}
}

$r=Get-Content $manifest -Raw|ConvertFrom-Json
if($r.phase-ne"6DA"-or$r.build_tag-ne"P6DA-DSOUND-ARG-LINEAGE-00041D88-20261026-A"){
  throw "Phase 6DA manifest identity mismatch"
}

$da=$r.phase6da_dsound_argument_lineage
if($da.phase6cz_hardware.fault_address-ne"0xCCCCCCD0"-or
   $da.phase6cz_hardware.fault_object_argument-ne"0x00041D88"-or
   $da.probe_only-ne$true-or
   $da.target_entry_count-ne4-or
   $da.guest_memory_semantics_changed-ne$false-or
   $da.value_fabrication-ne$false-or
   $da.address_range_widened-ne$false-or
   $da.execution_budget_inherited-ne64000000-or
   $da.exfreepool_itail_preserved-ne$true-or
   $da.manual_dsound_decrypt_preserved-ne$true-or
   $da.hard_fences_weakened-ne$false){
  throw "Phase 6DA manifest gate failed"
}

$text=Get-Content $mono -Raw
foreach($marker in @(
  "P6DA-DSOUND-ARG-LINEAGE-00041D88-20261026-A",
  "phase6da_env_build_cookie",
  "P6DA DSOUND ARG: stage=1 func=0029F992",
  "P6DA DSOUND ARG: stage=2 func=0029EBEA",
  "P6DA DSOUND ARG: stage=3 func=0029EA79",
  "P6DA DSOUND ARG: stage=4 func=002A41EE",
  "P6DA DSOUND ARG LINEAGE:",
  "P6DA PREFAULT ROUTER READ32:",
  "PASS: Phase 6DA ExFreePool ITAIL",
  "PASS: Phase 6DA manual DSOUND decrypt",
  "#define PHASE6CV_SHADOW_BASE 0xF0000000u",
  "P6DA APU CORE:",
  "P6DA AV/DISPLAY SUMMARY:",
  "#define PHASE4C_EXEC_BUDGET 64000000u"
)){
  if(-not$text.Contains($marker)){throw "Phase 6DA source gate missing: $marker"}
}

$shardCount=@(Get-ChildItem -LiteralPath $shards -Filter "*.inl" -File).Count
if($shardCount-lt1){throw "Phase 6DA translated shard output is empty"}

Write-Host ""
Write-Host "[Phase6DA] READY"
Write-Host "[Phase6DA] Target chain: 0029F992 -> 0029EBEA -> 0029EA79 -> 002A41EE"
Write-Host "[Phase6DA] Hardware bad object arg        : 00041D88"
Write-Host "[Phase6DA] Expected stage-1 money line    : prior_va=... arg1=00041D88"
Write-Host "[Phase6DA] Guest-memory semantics         : unchanged"
Write-Host "[Phase6DA] Pointer fabrication            : NO"
Write-Host "[Phase6DA] ExFreePool / DSOUND / APU/GPU  : preserved"
Write-Host ("[Phase6DA] Generated shards               : {0}" -f $shardCount)

if(-not$SkipSolutionBuild){
  $buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DA-DSOUND-ARG-LINEAGE-00041D88-20261026-A"
    ExpectedEnvCookie="phase6da_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6da-vs2017-clean.log")
    BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6da-vs2017-build.log")
    PublishedXex=(Join-Path $out "Mercenaries-PPC-Port-P6DA-A.xex")
  }
  & $builder @buildArgs
  Write-Host "[Phase6DA] BUILD PASS"
  Write-Host ("[Phase6DA] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6DA-A.xex"))
}
