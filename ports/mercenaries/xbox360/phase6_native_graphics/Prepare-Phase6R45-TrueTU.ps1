[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild,
  [switch]$FullClean
)

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python not found"}
  $python=$cmd.Source
}

$rocket=Join-Path $PSScriptRoot "Prepare-Phase6DQ-Rocket.ps1"
$tuEmitter=Join-Path $PSScriptRoot "emit_phase6_true_tu.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$rocketOut=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tuOut=Join-Path $root "build\phase6_native_graphics\r45_audio_true_tu_xdk"

foreach($f in @($rocket,$tuEmitter,$builder)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6R45 TrueTU input: $f"}
}

Write-Host "[Phase6R45] ========================================================"
Write-Host "[Phase6R45]            AUDIO PROVENANCE + TRUE TU"
Write-Host "[Phase6R45] ========================================================"
Write-Host "[Phase6R45] R45: five 002A76FE callers + target entry + lookup tagged"
Write-Host "[Phase6R45] R45: exact 00040000/00000400 poison signature contained"
Write-Host "[Phase6R45] R45: NO channel-index clamp; NO AC97 table rewrite"
Write-Host "[Phase6R45] TU : 64 real compiled translated_###.cpp units"
Write-Host "[Phase6R45] TU : stable guest-VA ownership + content-stable writes"
Write-Host "[Phase6R45] TU : persistent output directory (timestamps preserved)"
Write-Host "[Phase6R45] Build: local shadow required for generated project items"
Write-Host "[Phase6R45] Build mode: $(if($FullClean){'FULL CLEAN'}else{'INCREMENTAL'})"

# Always regenerate the R45 monolithic truth source, but do not build it.
& $rocket -SolutionRoot $SolutionRoot -FastBuildRoot $FastBuildRoot -SkipSolutionBuild
if($LASTEXITCODE-ne0){throw "Phase 6R45 Rocket emission failed"}

$mono=Join-Path $rocketOut "main_monolithic.cpp"
$env=Join-Path $rocketOut "phase5_env.cpp"
$rocketManifest=Join-Path $rocketOut "phase6dq-manifest.json"
foreach($f in @($mono,$env,$rocketManifest)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing R45 Rocket output: $f"}
}

$rm=Get-Content -LiteralPath $rocketManifest -Raw|ConvertFrom-Json
if($rm.phase-ne"6DQ"-or
   $rm.build_tag-ne"P6DQ-R45-AUDIO-PROVENANCE-20261026-A"-or
   $rm.phase6dq_rocket_frontier_journal.emitter_revision-ne"6DQ-R45"){
  throw "Phase 6R45 Rocket identity mismatch"
}
if($null-eq$rm.phase6dq_rocket_frontier_journal.r45_bad_audio_object_provenance){
  throw "Phase 6R45 manifest missing audio-object provenance contract"
}

& $python -m py_compile $tuEmitter
if($LASTEXITCODE-ne0){throw "Phase 6 TrueTU emitter syntax check failed"}

# IMPORTANT: do not delete $tuOut. emit_phase6_true_tu.py performs content-stable
# writes so unchanged shards keep their mtimes across runs.
New-Item -ItemType Directory -Force -Path $tuOut|Out-Null

$oldErrorActionPreference=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python $tuEmitter "--source" $mono "--out-dir" $tuOut "--shards" "64" 2>&1 |
    Tee-Object -Variable phase6tuEmitOutput
  $tuEmitRc=$LASTEXITCODE
}finally{
  $ErrorActionPreference=$oldErrorActionPreference
}

if($tuEmitRc-ne0){
  Write-Host "[Phase6R45] TRUE TU EMITTER OUTPUT:"
  $phase6tuEmitOutput|ForEach-Object{Write-Host $_}
  throw "Phase 6 TrueTU emission failed (exit $tuEmitRc)"
}

$main=Join-Path $tuOut "main.cpp"
$shards=Join-Path $tuOut "translated_shards"
$tuManifest=Join-Path $tuOut "phase6tu-manifest.json"
$runtimeHeader=Join-Path $shards "translated_runtime.h"
foreach($f in @($main,$shards,$tuManifest,$runtimeHeader)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6 TrueTU output: $f"}
}

$tm=Get-Content -LiteralPath $tuManifest -Raw|ConvertFrom-Json
$cppShards=@(Get-ChildItem -LiteralPath $shards -Filter "translated_*.cpp" -File|Sort-Object Name)
if($tm.phase-ne"6TU"-or
   [int]$tm.shard_count-ne64-or
   [int]$tm.translated_functions-lt13000-or
   $tm.content_stable_writes-ne$true-or
   @($cppShards).Count-ne64){
  throw "Phase 6 TrueTU manifest/layout gate failed"
}

$mainText=Get-Content -LiteralPath $main -Raw
if($mainText.Contains('#include "translated_shards/')){
  throw "TrueTU main.cpp still includes translated shard bodies"
}

$internalMainSubs=@(
  [regex]::Matches(
    $mainText,
    '(?m)^\s*static\s+void\s+sub_[0-9A-Fa-f]{8}\s*\('
  )
)
if(@($internalMainSubs).Count-gt0){
  Write-Host ("[Phase6R45] Internal-linkage runtime sub symbols remaining: {0}" -f @($internalMainSubs).Count)
  throw "TrueTU main.cpp still contains real internal-linkage sub_XXXXXXXX declarations/definitions"
}

foreach($shard in $cppShards){
  $st=Get-Content -LiteralPath $shard.FullName -Raw
  if(-not$st.Contains('#include "translated_runtime.h"')){
    throw "TrueTU shard missing runtime header: $($shard.Name)"
  }
  if([regex]::IsMatch($st,'(?m)^\s*static\s+void\s+sub_[0-9A-Fa-f]{8}\s*\(')){
    throw "TrueTU shard still contains a real static translated definition: $($shard.Name)"
  }
}

Write-Host ""
Write-Host "[Phase6R45] ================= TRUE TU READY ================="
Write-Host ("[Phase6R45] Translated functions : {0}" -f [int]$tm.translated_functions)
Write-Host ("[Phase6R45] Compiled TU shards   : {0}" -f @($cppShards).Count)
Write-Host ("[Phase6R45] Runtime helpers ext  : {0}" -f [int]$tm.runtime_helpers_externalized)
Write-Host ("[Phase6R45] Runtime globals ext  : {0}" -f [int]$tm.runtime_globals_externalized)
Write-Host ("[Phase6R45] Changed files        : {0}" -f @($tm.changed_files).Count)
Write-Host ("[Phase6R45] Unchanged files      : {0}" -f @($tm.unchanged_files).Count)
Write-Host "[Phase6R45] Content-stable writes: PASS"

if($SkipSolutionBuild){
  Write-Host "[Phase6R45] Solution build skipped by request."
  exit 0
}

$buildArgs=@{
  GeneratedMain=$main
  GeneratedEnv=$env
  GeneratedShardDir=$shards
  ExpectedBuildTag="P6DQ-R45-AUDIO-PROVENANCE-20261026-A"
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6r45-tu-vs2017-clean.log")
  BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6r45-tu-vs2017-build.log")
  PublishedXex=(Join-Path $tuOut "Mercenaries-PPC-Port-P6R45-AUDIO-TRUE-TU-A.xex")
  ShadowBuildRoot=$FastBuildRoot
}
if(-not$FullClean){$buildArgs["SkipClean"]=$true}

& $builder @buildArgs
if($LASTEXITCODE-ne0){throw "Phase 6R45 TrueTU Xbox 360 build failed"}

Write-Host ""
Write-Host "[Phase6R45] BUILD PASS"
Write-Host ("[Phase6R45] COPY THIS XEX: {0}" -f (Join-Path $tuOut "Mercenaries-PPC-Port-P6R45-AUDIO-TRUE-TU-A.xex"))
Write-Host "[Phase6R45] On Xbox, capture the first P6DQ R45 AUDIO OBJECT / AUDIO CONTAIN lines."
