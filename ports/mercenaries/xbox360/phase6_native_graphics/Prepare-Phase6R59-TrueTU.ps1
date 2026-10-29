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
  if($null-eq$cmd){throw "Python unavailable"}
  $python=$cmd.Source
}
$r58OverlayScript=Join-Path $PSScriptRoot "instrument_phase6r58_dsound_returns.py"
$r59OverlayScript=Join-Path $PSScriptRoot "instrument_phase6r59_fc4a_abi.py"
$tuEmitter=Join-Path $PSScriptRoot "emit_phase6_true_tu.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocketOut=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$rocketMono=Join-Path $rocketOut "main_monolithic.cpp"
$rocketEnv=Join-Path $rocketOut "phase5_env.cpp"
$rocketManifest=Join-Path $rocketOut "phase6dq-manifest.json"
$r58Out=Join-Path $root "build\phase6_native_graphics\r58_dsound_status_trace"
$r58Mono=Join-Path $r58Out "main_monolithic_r58.cpp"
$r59Out=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair"
$r59Mono=Join-Path $r59Out "main_monolithic_r59.cpp"
$tuOut=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$xex=Join-Path $r59Out "Merc.xex"
$tag="P6DQ-R51-MM173-FRAME-20261029-A"
foreach($f in @($r58OverlayScript,$r59OverlayScript,$tuEmitter,$builder,$rocketMono,$rocketEnv,$rocketManifest)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R59 missing input $f"}
}
$m=Get-Content -LiteralPath $rocketManifest -Raw|ConvertFrom-Json
if($m.phase-ne"6DQ" -or $m.build_tag-ne$tag -or
   $m.phase6dq_rocket_frontier_journal.emitter_revision-ne"6DQ-R51"){
  throw "R59 requires original validated R51 Rocket cache"
}
$tuText=Get-Content -LiteralPath $tuEmitter -Raw
if(-not$tuText.Contains('TRUE_TU_EMITTER_REVISION = "6TU-R15-UNIFIED-SHARD-CALL-SURFACE-20261027"')){
  throw "R59 TrueTU emitter revision mismatch"
}
Write-Host "[Phase6R59] ========================================================"
Write-Host "[Phase6R59]     EXACT FC4A x86 CALLER-SAVED ABI REPAIR"
Write-Host "[Phase6R59] ========================================================"
Write-Host "[Phase6R59] R58: 7FF8FFF2 + nested audio object 01B5C554 = 81AEC546"
Write-Host "[Phase6R59] R58: A19FC clobbers ESI/EDI; FF54 clobbers EDI"
Write-Host "[Phase6R59] R59: preserve EBX/ESI/EDI only around two exact calls"
Write-Host "[Phase6R59] No forced status, no fake objects, no guest fault bypass"
Write-Host "[Phase6R59] R51 Rocket: cache reused; 64 true TUs retained"
New-Item -ItemType Directory -Path $r59Out -Force|Out-Null

& $python -m py_compile $r58OverlayScript $r59OverlayScript $tuEmitter
if($LASTEXITCODE-ne0){throw "R59 Python preflight failed"}
# Regenerate R58 diagnostic source content-stably, without touching its XEX.
& $python $r58OverlayScript --source $rocketMono --out $r58Mono
if($LASTEXITCODE-ne0){throw "R59 preflight: R58 overlay source invalid"}
& $python $r59OverlayScript --source $r58Mono --out $r59Mono
if($LASTEXITCODE-ne0){throw "R59 ABI overlay preflight failed"}

Write-Host "[Phase6R59] Emit content-stable 64 TrueTU translation units"
New-Item -ItemType Directory -Force -Path $tuOut|Out-Null
$stdoutLog=Join-Path $r59Out "true-tu-emitter.stdout.log"
$stderrLog=Join-Path $r59Out "true-tu-emitter.stderr.log"
$tuArgs=@($tuEmitter,"--source",$r59Mono,"--out-dir",$tuOut,"--shards","64")
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
  Write-Host "[Phase6R59] TrueTU emission FAILED"
  Write-Host $stdout
  Write-Host $stderr
  throw "R59 TrueTU emitter returned $($proc.ExitCode)"
}
Write-Host $stdout
$main=Join-Path $tuOut "main.cpp"
$shards=Join-Path $tuOut "translated_shards"
$manifest=Join-Path $tuOut "phase6tu-manifest.json"
foreach($f in @($main,$shards,$manifest)){
  if(-not(Test-Path -LiteralPath $f)){throw "R59 missing TrueTU output $f"}
}
$tm=Get-Content -LiteralPath $manifest -Raw|ConvertFrom-Json
$units=@(Get-ChildItem -LiteralPath $shards -File -Filter "translated_*.cpp")
if($tm.phase-ne"6TU" -or [int]$tm.shard_count-ne64 -or $units.Count-ne64 -or
   [int]$tm.translated_functions-lt13000){
   throw "R59 true TU manifest/64-unit validation failed"
}
$probeUnits=@($units|Where-Object{
  Select-String -LiteralPath $_.FullName -Pattern "P6DQ R59 FC4A ABI RESTORE:" -Quiet
})
if($probeUnits.Count-lt1){
  throw "R59 repair marker not present in compiled TU"
}
Write-Host "[Phase6R59] Changed TU files=$(@($tm.changed_files).Count)"
Write-Host "[Phase6R59] Unchanged TU files=$(@($tm.unchanged_files).Count)"
Write-Host "[Phase6R59] Repair marker carried into $($probeUnits.Count) TU(s)"
if($SkipSolutionBuild){
  Write-Host "[Phase6R59] No Xbox build requested."
  exit 0
}
$buildArgs=@{
  GeneratedMain=$main
  GeneratedEnv=$rocketEnv
  GeneratedShardDir=$shards
  ExpectedBuildTag=$tag
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $r59Out "xdk-clean.log")
  BuildLog=(Join-Path $r59Out "xdk-build.log")
  PublishedXex=$xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @buildArgs
if($LASTEXITCODE-ne0){throw "R59 VS2017 XDK build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
  throw "R59 XEX did not publish"
}
Write-Host "[Phase6R59] BUILD PASS"
Write-Host "[Phase6R59] COPY THIS XEX: $xex"
Write-Host "[Phase6R59] Hardware: capture R59 ABI RESTORE, R58 DSOUND STATUS, XACT INIT, last boundary and ticks"
Write-Host "[Phase6R59] R51 Rocket baseline untouched; R58 and R59 XEX outputs separate"
