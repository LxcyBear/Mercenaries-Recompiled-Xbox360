[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild,
  [switch]$FullClean,
  [switch]$RefreshRocket
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
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6R47 TrueTU input: $f"}
}

Write-Host "[Phase6R47] ========================================================"
Write-Host "[Phase6R47]            AUDIO PROVENANCE + TRUE TU"
Write-Host "[Phase6R47] ========================================================"
Write-Host "[Phase6R47] R47: five 002A76FE callers + target entry + lookup tagged"
Write-Host "[Phase6R47] R47: exact 00040000/00000400 poison signature contained"
Write-Host "[Phase6R47] R47: NO channel-index clamp; NO AC97 table rewrite"
Write-Host "[Phase6R47] TU : 64 real compiled translated_###.cpp units"
Write-Host "[Phase6R47] TU : stable guest-VA ownership + content-stable writes"
Write-Host "[Phase6R47] TU : persistent output directory (timestamps preserved)"
Write-Host "[Phase6R47] Rocket: validated cache reused by default; -RefreshRocket forces regeneration"
Write-Host "[Phase6R47] Build: local shadow required for generated project items"
Write-Host "[Phase6R47] Build mode: $(if($FullClean){'FULL CLEAN'}else{'INCREMENTAL'})"

# Reuse a validated R47 Rocket output by default. Rocket generation is the
# expensive closure/pruning/monolithic stage and should not rerun while we are
# iterating only on the True-TU splitter/build plumbing.
$mono=Join-Path $rocketOut "main_monolithic.cpp"
$env=Join-Path $rocketOut "phase5_env.cpp"
$rocketManifest=Join-Path $rocketOut "phase6dq-manifest.json"

function Test-R47RocketCache {
  if(-not(Test-Path -LiteralPath $mono -PathType Leaf)){return $false}
  if(-not(Test-Path -LiteralPath $env -PathType Leaf)){return $false}
  if(-not(Test-Path -LiteralPath $rocketManifest -PathType Leaf)){return $false}
  try{
    $cached=Get-Content -LiteralPath $rocketManifest -Raw|ConvertFrom-Json
    if($cached.phase-ne"6DQ"){return $false}
    if($cached.build_tag-ne"P6DQ-R47-AUDIO-PROVENANCE-20261027-A"){return $false}
    if($cached.phase6dq_rocket_frontier_journal.emitter_revision-ne"6DQ-R47"){return $false}
    if($null-eq$cached.phase6dq_rocket_frontier_journal.r45_bad_audio_object_provenance){return $false}
    if($null-eq$cached.phase6dq_rocket_frontier_journal.r47_audio_producer_and_cleanup){return $false}
    return $true
  }catch{
    return $false
  }
}

$rocketCacheValid=Test-R47RocketCache
if($RefreshRocket-or(-not$rocketCacheValid)){
  Write-Host ("[Phase6R47] Rocket cache: {0}" -f $(if($RefreshRocket){"REFRESH REQUESTED"}else{"MISS/INVALID"}))
  $rocketStart=Get-Date
  & $rocket -SolutionRoot $SolutionRoot -FastBuildRoot $FastBuildRoot -SkipSolutionBuild
  if($LASTEXITCODE-ne0){throw "Phase 6R47 Rocket emission failed"}
  $rocketElapsed=(Get-Date)-$rocketStart
  Write-Host ("[Phase6R47] Rocket generation elapsed: {0}" -f $rocketElapsed)

  if(-not(Test-R47RocketCache)){
    throw "Phase 6R47 Rocket output failed cache identity validation"
  }
}else{
  Write-Host "[Phase6R47] Rocket cache: HIT -- expensive Rocket regeneration skipped"
  Write-Host "[Phase6R47] Rocket cache policy: use -RefreshRocket after changing Rocket/audio pack inputs"
}

$rm=Get-Content -LiteralPath $rocketManifest -Raw|ConvertFrom-Json
if($rm.phase-ne"6DQ"-or
   $rm.build_tag-ne"P6DQ-R47-AUDIO-PROVENANCE-20261027-A"-or
   $rm.phase6dq_rocket_frontier_journal.emitter_revision-ne"6DQ-R47"){
  throw "Phase 6R47 Rocket identity mismatch"
}
if($null-eq$rm.phase6dq_rocket_frontier_journal.r45_bad_audio_object_provenance -or
   $null-eq$rm.phase6dq_rocket_frontier_journal.r47_audio_producer_and_cleanup -or
   $rm.phase6dq_rocket_frontier_journal.r47_audio_producer_and_cleanup.contained_branch_cleanup-ne"0x002A7765"){
  throw "Phase 6R47 manifest missing audio-object provenance contract"
}

& $python -m py_compile $tuEmitter
if($LASTEXITCODE-ne0){throw "Phase 6 TrueTU emitter syntax check failed"}

$tuEmitterText=Get-Content -LiteralPath $tuEmitter -Raw
$expectedTuRevision='6TU-R15-UNIFIED-SHARD-CALL-SURFACE-20261027'
if(-not$tuEmitterText.Contains('TRUE_TU_EMITTER_REVISION = "'+$expectedTuRevision+'"')){
  throw "Stale TrueTU emitter detected; expected $expectedTuRevision"
}
Write-Host ("[Phase6R47] TrueTU emitter revision: {0}" -f $expectedTuRevision)

# IMPORTANT: do not delete $tuOut. emit_phase6_true_tu.py performs content-stable
# writes so unchanged shards keep their mtimes across runs.
New-Item -ItemType Directory -Force -Path $tuOut|Out-Null

$tuStart=Get-Date
$phase6tuStdout=Join-Path $tuOut "phase6tu-emitter.stdout.log"
$phase6tuStderr=Join-Path $tuOut "phase6tu-emitter.stderr.log"
foreach($p in @($phase6tuStdout,$phase6tuStderr)){
  if(Test-Path -LiteralPath $p){Remove-Item -LiteralPath $p -Force}
}

$tuArgs=@(
  $tuEmitter,
  "--source",$mono,
  "--out-dir",$tuOut,
  "--shards","64"
)

$psi=New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName=$python
$psi.UseShellExecute=$false
$psi.CreateNoWindow=$true
$psi.RedirectStandardOutput=$true
$psi.RedirectStandardError=$true
# VS2017/XDK hosts Windows PowerShell on .NET Framework, where
# ProcessStartInfo.ArgumentList is not available. Build one quoted command line.
$escaped=@($tuArgs|ForEach-Object{
  '"' + ([string]$_).Replace('"','\"') + '"'
})
$psi.Arguments=$escaped -join ' '

$proc=New-Object System.Diagnostics.Process
$proc.StartInfo=$psi
$null=$proc.Start()
$stdout=$proc.StandardOutput.ReadToEnd()
$stderr=$proc.StandardError.ReadToEnd()
$proc.WaitForExit()
$tuEmitRc=$proc.ExitCode

[System.IO.File]::WriteAllText(
  $phase6tuStdout,
  $stdout,
  (New-Object System.Text.UTF8Encoding($false))
)
[System.IO.File]::WriteAllText(
  $phase6tuStderr,
  $stderr,
  (New-Object System.Text.UTF8Encoding($false))
)

$phase6tuEmitOutput=@()
if(-not[string]::IsNullOrWhiteSpace($stdout)){
  $phase6tuEmitOutput+=@($stdout -split "\r?\n"|Where-Object{$_ -ne ''})
}
if(-not[string]::IsNullOrWhiteSpace($stderr)){
  $phase6tuEmitOutput+=@($stderr -split "\r?\n"|Where-Object{$_ -ne ''})
}
if($tuEmitRc-ne0){
  Write-Host "[Phase6R47] TRUE TU EMITTER OUTPUT:"
  $phase6tuEmitOutput|ForEach-Object{Write-Host $_}
  Write-Host ("[Phase6R47] STOP: TrueTU emission failed (exit {0})" -f $tuEmitRc)
  exit $tuEmitRc
}
$tuElapsed=(Get-Date)-$tuStart
Write-Host ("[Phase6R47] TrueTU emission elapsed: {0}" -f $tuElapsed)

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

# Internal-linkage sub_* validation is performed by the Python emitter against
# comment/string-masked source. Avoid a second raw-text regex here because
# documentation/comments can legitimately contain the spelling "static void sub_".

foreach($shard in $cppShards){
  $st=Get-Content -LiteralPath $shard.FullName -Raw
  if(-not$st.Contains('#include "translated_runtime.h"')){
    throw "TrueTU shard missing runtime header: $($shard.Name)"
  }
  # The emitter already proves masked shard source contains no internal-linkage
  # sub_XXXXXXXX declarations/definitions before this file is written.
}

Write-Host ""
Write-Host "[Phase6R47] ================= TRUE TU READY ================="
Write-Host ("[Phase6R47] Translated functions : {0}" -f [int]$tm.translated_functions)
Write-Host ("[Phase6R47] Compiled TU shards   : {0}" -f @($cppShards).Count)
Write-Host ("[Phase6R47] Runtime helpers ext  : {0}" -f [int]$tm.runtime_helpers_externalized)
Write-Host ("[Phase6R47] Runtime globals ext  : {0}" -f [int]$tm.runtime_globals_externalized)
Write-Host ("[Phase6R47] Shard sub linkage ext : {0}" -f [int]$tm.shard_sub_symbols_externalized)
Write-Host ("[Phase6R47] Changed files        : {0}" -f @($tm.changed_files).Count)
Write-Host ("[Phase6R47] Unchanged files      : {0}" -f @($tm.unchanged_files).Count)
Write-Host "[Phase6R47] Content-stable writes: PASS"

if($SkipSolutionBuild){
  Write-Host "[Phase6R47] Solution build skipped by request."
  exit 0
}

$buildArgs=@{
  GeneratedMain=$main
  GeneratedEnv=$env
  GeneratedShardDir=$shards
  ExpectedBuildTag="P6DQ-R47-AUDIO-PROVENANCE-20261027-A"
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $root "build\phase6_native_graphics\phase6r45-tu-vs2017-clean.log")
  BuildLog=(Join-Path $root "build\phase6_native_graphics\phase6r45-tu-vs2017-build.log")
  PublishedXex=(Join-Path $tuOut "Merc.xex")
  ShadowBuildRoot=$FastBuildRoot
}
if(-not$FullClean){$buildArgs["SkipClean"]=$true}

$buildStart=Get-Date
& $builder @buildArgs
$buildElapsed=(Get-Date)-$buildStart
Write-Host ("[Phase6R47] VS/XDK build elapsed: {0}" -f $buildElapsed)
if($LASTEXITCODE-ne0){throw "Phase 6R47 TrueTU Xbox 360 build failed"}

Write-Host ""
Write-Host "[Phase6R47] BUILD PASS"
Write-Host ("[Phase6R47] COPY THIS XEX: {0}" -f (Join-Path $tuOut "Merc.xex"))
Write-Host "[Phase6R47] On Xbox, capture P6DQ R45 AUDIO OBJECT / AUDIO CONTAIN, first hard stop, and max ticks."
