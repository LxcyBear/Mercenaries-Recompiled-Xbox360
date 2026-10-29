[CmdletBinding()]
param(
  [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
  [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port",
  [switch]$SkipSolutionBuild
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
$overlayScript=Join-Path $PSScriptRoot "instrument_phase6r58_dsound_returns.py"
$tuEmitter=Join-Path $PSScriptRoot "emit_phase6_true_tu.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocketOut=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$baseMono=Join-Path $rocketOut "main_monolithic.cpp"
$envSource=Join-Path $rocketOut "phase5_env.cpp"
$rocketManifest=Join-Path $rocketOut "phase6dq-manifest.json"
$tuOut=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r58Out=Join-Path $root "build\phase6_native_graphics\r58_dsound_status_trace"
$r58Mono=Join-Path $r58Out "main_monolithic_r58.cpp"
$r58Xex=Join-Path $r58Out "Merc.xex"
$r51Original=Join-Path $tuOut "Merc.xex"
$r51Backup=Join-Path $r58Out "Merc-R51-known-good.xex"
$expectedTag="P6DQ-R51-MM173-FRAME-20261029-A"
foreach($f in @($overlayScript,$tuEmitter,$builder,$baseMono,$envSource,$rocketManifest)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "Phase6R58 missing input: $f"}
}
$manifest=Get-Content -LiteralPath $rocketManifest -Raw|ConvertFrom-Json
if($manifest.phase-ne"6DQ" -or $manifest.build_tag-ne$expectedTag -or
   $manifest.phase6dq_rocket_frontier_journal.emitter_revision-ne"6DQ-R51"){
   throw "R58 requires validated R51 Rocket cache; run R51 setup first"
}
$tuEmitterText=Get-Content -LiteralPath $tuEmitter -Raw
if(-not$tuEmitterText.Contains('TRUE_TU_EMITTER_REVISION = "6TU-R15-UNIFIED-SHARD-CALL-SURFACE-20261027"')){
  throw "R58 TrueTU revision mismatch"
}
Write-Host "[Phase6R58] ========================================================"
Write-Host "[Phase6R58]       DIRECTSOUND STAGE-ONE STATUS TRACE"
Write-Host "[Phase6R58] ========================================================"
Write-Host "[Phase6R58] Proven R51 stage1 failure: 81AEC546"
Write-Host "[Phase6R58] R51 Rocket: CACHE REUSED -- no regeneration"
Write-Host "[Phase6R58] True TU : existing 64-shard output reused incrementally"
Write-Host "[Phase6R58] No refcount/status/guest-memory-fence change"
New-Item -ItemType Directory -Path $r58Out -Force|Out-Null

# The known-good R51 Xbox artifact is retained if it is present. Do not
# overwrite it on repeated R58 diagnostic builds.
if((Test-Path -LiteralPath $r51Original -PathType Leaf) -and
   (-not(Test-Path -LiteralPath $r51Backup -PathType Leaf))){
  Copy-Item -LiteralPath $r51Original -Destination $r51Backup
  Write-Host "[Phase6R58] R51 baseline backed up: $r51Backup"
}
if(-not(Test-Path -LiteralPath $r51Backup)){
  Write-Host "[Phase6R58] Note: R51 XEX not available for local backup; original Rocket source still preserved"
}

& $python -m py_compile $overlayScript $tuEmitter
if($LASTEXITCODE-ne0){throw "R58 Python syntax preflight failed"}
& $python $overlayScript --source $baseMono --out $r58Mono
if($LASTEXITCODE-ne0){throw "R58 targeted overlay failed"}
$overlayText=Get-Content -LiteralPath $r58Mono -Raw
if(-not$overlayText.Contains("P6DQ R58 DSOUND STATUS:")){
  throw "R58 overlay missing bounded trace marker"
}
$overlayText=$null
Write-Host "[Phase6R58] Emit 64 TrueTU files (content-stable)"
New-Item -ItemType Directory -Path $tuOut -Force|Out-Null
$stdoutLog=Join-Path $r58Out "true-tu-emitter.stdout.log"
$stderrLog=Join-Path $r58Out "true-tu-emitter.stderr.log"
$tuArgs=@($tuEmitter,"--source",$r58Mono,"--out-dir",$tuOut,"--shards","64")
$psi=New-Object System.Diagnostics.ProcessStartInfo
$psi.FileName=$python
$psi.UseShellExecute=$false
$psi.CreateNoWindow=$true
$psi.RedirectStandardOutput=$true
$psi.RedirectStandardError=$true
$psi.Arguments=(@($tuArgs|ForEach-Object{'"'+([string]$_).Replace('"','\"')+'"'}) -join ' ')
$proc=New-Object System.Diagnostics.Process
$proc.StartInfo=$psi
$null=$proc.Start()
$stdout=$proc.StandardOutput.ReadToEnd()
$stderr=$proc.StandardError.ReadToEnd()
$proc.WaitForExit()
[IO.File]::WriteAllText($stdoutLog,$stdout)
[IO.File]::WriteAllText($stderrLog,$stderr)
if($proc.ExitCode-ne0){
  Write-Host "[Phase6R58] TRUE TU FAILURE:"
  Write-Host $stdout
  Write-Host $stderr
  throw "R58 True TU emission failed (exit $($proc.ExitCode))"
}
Write-Host $stdout
$main=Join-Path $tuOut "main.cpp"
$shards=Join-Path $tuOut "translated_shards"
$tuManifest=Join-Path $tuOut "phase6tu-manifest.json"
foreach($f in @($main,$shards,$tuManifest)){
  if(-not(Test-Path -LiteralPath $f)){throw "R58 TrueTU missing output: $f"}
}
$tm=Get-Content -LiteralPath $tuManifest -Raw|ConvertFrom-Json
$cppShards=@(Get-ChildItem -LiteralPath $shards -Filter "translated_*.cpp" -File)
if($tm.phase-ne"6TU" -or [int]$tm.shard_count-ne64 -or
   [int]$tm.translated_functions-lt13000 -or $cppShards.Count-ne64){
  throw "R58 TrueTU manifest/shard count invalid"
}
$r58MarkerFound=$false
foreach($shard in $cppShards){
  if(Select-String -LiteralPath $shard.FullName -Pattern "P6DQ R58 DSOUND STATUS:" -Quiet){
    $r58MarkerFound=$true
    break
  }
}
if(-not$r58MarkerFound){throw "R58 probe did not survive True TU sharding"}
Write-Host "[Phase6R58] Changed TrueTU files   : $(@($tm.changed_files).Count)"
Write-Host "[Phase6R58] Unchanged TrueTU files : $(@($tm.unchanged_files).Count)"
Write-Host "[Phase6R58] 64 compiled TU source units retained; R58 status probe present"

if($SkipSolutionBuild){
  Write-Host "[Phase6R58] Solution build skipped. No XEX produced by this invocation."
  exit 0
}
$buildArgs=@{
  GeneratedMain=$main
  GeneratedEnv=$envSource
  GeneratedShardDir=$shards
  ExpectedBuildTag=$expectedTag
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $r58Out "xdk-clean.log")
  BuildLog=(Join-Path $r58Out "xdk-build.log")
  PublishedXex=$r58Xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @buildArgs
if($LASTEXITCODE-ne0){throw "Phase 6R58 XDK build failed"}
if(-not(Test-Path -LiteralPath $r58Xex -PathType Leaf)){throw "R58 Xbox build did not publish an XEX"}
Write-Host "[Phase6R58] BUILD PASS"
Write-Host "[Phase6R58] COPY THIS XEX: $r58Xex"
Write-Host "[Phase6R58] Capture: P6DQ R58 DSOUND STATUS lines, XACT INIT, first hard stop, max ticks"
Write-Host "[Phase6R58] R51 original Rocket source preserved; R51 XEX backup: $r51Backup"
