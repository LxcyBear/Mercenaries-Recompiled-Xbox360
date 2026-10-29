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
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python unavailable"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "quickpatch_phase6r69_dsound_seed.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocket=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tu=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r62=Join-Path $root "build\phase6_native_graphics\r62_fast_dsound_alloc"
$r63=Join-Path $root "build\phase6_native_graphics\r63_fast_dsound_hresult"
$r66=Join-Path $root "build\phase6_native_graphics\r66_fast_dsound_pool"
$r69=Join-Path $root "build\phase6_native_graphics\r69_fast_dsound_seed"
$xex=Join-Path $r69 "Merc.xex"
foreach($file in @($script,$builder,(Join-Path $rocket "phase5_env.cpp"),(Join-Path $tu "main.cpp"),
    (Join-Path $tu "phase6tu-manifest.json"),(Join-Path $r62 "quick-shard-overlay.json"),
    (Join-Path $r63 "quick-shard-overlay.json"),(Join-Path $r66 "quick-shard-overlay.json"))){
  if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "R69 input missing: $file"}
}
New-Item -ItemType Directory -Path $r69 -Force | Out-Null
$preflight=Join-Path $r69 "r69-quickpatch-preflight.log"
Write-Host "[Phase6R69] ====================================================="
Write-Host "[Phase6R69]  TWO-SHARD DSOUND PAGE-POOL CONSTRUCTOR TRACE"
Write-Host "[Phase6R69] ====================================================="
Write-Host "[Phase6R69] R68: FC4A -> A19FC -> A2A16 -> FF54 -> A2977"
Write-Host "[Phase6R69] R66: pool+0x18 = 0 at A2AA1; A5309=8007000E"
Write-Host "[Phase6R69] Target translated_008.cpp + translated_042.cpp"
Write-Host "[Phase6R69] R66 markers retained; 64 shard SHA-256 checks"
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "R69 Python syntax failed"}
$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
  & $python -u $script --tu-dir $tu --r62-dir $r62 --r63-dir $r63 --r66-dir $r66 --out-dir $r69 2>&1 |
      Tee-Object -FilePath $preflight
  $code=$LASTEXITCODE
}finally{$ErrorActionPreference=$old}
if($code -ne 0){
  $tail=@(Get-Content -LiteralPath $preflight -Tail 16) -join [Environment]::NewLine
  throw ("R69 preflight failed: {0}{1}{2}{1}Log: {3}" -f $code,[Environment]::NewLine,$tail,$preflight)
}
if($SkipSolutionBuild){
  Write-Host "[Phase6R69] Preflight PASS; Xbox build skipped."
  exit 0
}
$params=@{
  GeneratedMain=(Join-Path $tu "main.cpp")
  GeneratedEnv=(Join-Path $rocket "phase5_env.cpp")
  GeneratedShardDir=(Join-Path $tu "translated_shards")
  ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $r69 "xdk-clean.log")
  BuildLog=(Join-Path $r69 "xdk-build.log")
  PublishedXex=$xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @params
if($LASTEXITCODE -ne 0){throw "R69 Xbox build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){throw "R69 output XEX missing: $xex"}
Write-Host "[Phase6R69] BUILD PASS"
Write-Host "[Phase6R69] PUBLISH: $xex"
Write-Host "[Phase6R69] Send R69 DSOUND SEED and R66 DSOUND POOL lines, XACT init/fault/ticks"
