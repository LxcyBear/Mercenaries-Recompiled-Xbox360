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
  if($null -eq $cmd){throw "Python unavailable"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "quickpatch_phase6r75_xgscnt_direct_read.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocket=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tu=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r62=Join-Path $root "build\phase6_native_graphics\r62_fast_dsound_alloc"
$r63=Join-Path $root "build\phase6_native_graphics\r63_fast_dsound_hresult"
$r66=Join-Path $root "build\phase6_native_graphics\r66_fast_dsound_pool"
$r69=Join-Path $root "build\phase6_native_graphics\r69_fast_dsound_seed"
$r71=Join-Path $root "build\phase6_native_graphics\r71_fast_fc4a_object_abi"
$r72=Join-Path $root "build\phase6_native_graphics\r72_fast_a19fc_nested_esi"
$r75=Join-Path $root "build\phase6_native_graphics\r75_fast_xgscnt_route"
$xex=Join-Path $r75 "Merc.xex"
foreach($file in @($script,$builder,(Join-Path $rocket "phase5_env.cpp"),
  (Join-Path $tu "main.cpp"),(Join-Path $tu "phase6tu-manifest.json"),
  (Join-Path $r62 "quick-shard-overlay.json"),
  (Join-Path $r63 "quick-shard-overlay.json"),
  (Join-Path $r66 "quick-shard-overlay.json"),
  (Join-Path $r69 "quick-shard-overlay.json"),
  (Join-Path $r71 "quick-shard-overlay.json"),
  (Join-Path $r72 "quick-shard-overlay.json"))){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "R75 prerequisite missing: $file"}
}
New-Item -ItemType Directory -Force -Path $r75 | Out-Null
$log=Join-Path $r75 "r75-quickpatch-preflight.log"
Write-Host "[Phase6R75] ===================================================="
Write-Host "[Phase6R75]  ONE-SHARD EXACT XGSCNT DIRECT READ ROUTE"
Write-Host "[Phase6R75] ===================================================="
Write-Host "[Phase6R75] R74: sub_002DA923 GUEST_READ32(FE80200C) bypasses APU"
Write-Host "[Phase6R75] Use existing APU 0x200C shadow; no timer fabrication"
Write-Host "[Phase6R75] Retain R72 pool fix and 64 cached TrueTU hashes"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R75 syntax validation failed"}
$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try {
    & $python -u $script --tu-dir $tu --r62-dir $r62 --r63-dir $r63 --r66-dir $r66 --r69-dir $r69 --r71-dir $r71 --r72-dir $r72 --out-dir $r75 2>&1 |
      Tee-Object -FilePath $log
    $code=$LASTEXITCODE
} finally {$ErrorActionPreference=$old}
if($code-ne0){
    $tail=@(Get-Content -LiteralPath $log -Tail 18) -join [Environment]::NewLine
    throw ("R75 prebuild failed exit={0}{1}{2}{1}{3}" -f $code,[Environment]::NewLine,$tail,$log)
}
if($SkipSolutionBuild){
  Write-Host "[Phase6R75] Preflight PASS. No Xbox build."
  exit 0
}
$buildArgs=@{
  GeneratedMain=(Join-Path $tu "main.cpp")
  GeneratedEnv=(Join-Path $rocket "phase5_env.cpp")
  GeneratedShardDir=(Join-Path $tu "translated_shards")
  ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $r75 "xdk-clean.log")
  BuildLog=(Join-Path $r75 "xdk-build.log")
  PublishedXex=$xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @buildArgs
if($LASTEXITCODE-ne0){throw "R75 Xbox build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){throw "R75 output XEX missing"}
Write-Host "[Phase6R75] BUILD PASS"
Write-Host "[Phase6R75] PUBLISH: $xex"
Write-Host "[Phase6R75] Capture R75 APU XGSCNT + XACT INIT + next fault/display/ticks"
