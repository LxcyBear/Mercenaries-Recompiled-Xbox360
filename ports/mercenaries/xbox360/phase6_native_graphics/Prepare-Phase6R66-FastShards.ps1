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
$script=Join-Path $PSScriptRoot "quickpatch_phase6r66_dsound_pool.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocket=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tu=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r62=Join-Path $root "build\phase6_native_graphics\r62_fast_dsound_alloc"
$r63=Join-Path $root "build\phase6_native_graphics\r63_fast_dsound_hresult"
$r66=Join-Path $root "build\phase6_native_graphics\r66_fast_dsound_pool"
$xex=Join-Path $r66 "Merc.xex"
foreach($f in @($script,$builder,(Join-Path $rocket "phase5_env.cpp"),(Join-Path $tu "main.cpp"),(Join-Path $tu "phase6tu-manifest.json"),(Join-Path $r62 "quick-shard-overlay.json"),(Join-Path $r63 "quick-shard-overlay.json"))){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "R66 prerequisite missing: $f"
    }
}
New-Item -ItemType Directory -Force -Path $r66|Out-Null
$preflight=Join-Path $r66 "r66-quickpatch-preflight.log"
Write-Host "[Phase6R66] ==================================================="
Write-Host "[Phase6R66]  CACHED TRUE-TU DIRECTSOUND POOL STATUS PROVENANCE"
Write-Host "[Phase6R66] ==================================================="
Write-Host "[Phase6R66] R65: A5309 assigns 8007000E on A2E38 null"
Write-Host "[Phase6R66] R65: A0F98 returns a different negative status 88780032"
Write-Host "[Phase6R66] Instrument A545F, A5309, A2E38 and A2AA1"
Write-Host "[Phase6R66] Hash-verify every cached shard; no regeneration/re-sharding"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R66 Python syntax preflight failed"}
$oldPreference=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
    & $python -u $script --tu-dir $tu --r62-dir $r62 --r63-dir $r63 --out-dir $r66 2>&1 | Tee-Object -FilePath $preflight
    $code=$LASTEXITCODE
}finally{
    $ErrorActionPreference=$oldPreference
}
if($code-ne0){
    $tail=@(Get-Content -LiteralPath $preflight -Tail 20) -join [Environment]::NewLine
    throw ("R66 prebuild failed, exit={0}{1}{2}{1}Report: {3}" -f $code,[Environment]::NewLine,$tail,$preflight)
}
if($SkipSolutionBuild){
    Write-Host "[Phase6R66] Preflight PASS. No XEX build requested."
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
  CleanLog=(Join-Path $r66 "xdk-clean.log")
  BuildLog=(Join-Path $r66 "xdk-build.log")
  PublishedXex=$xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @buildArgs
if($LASTEXITCODE-ne0){throw "R66 XDK build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){throw "R66 XEX missing"}
Write-Host "[Phase6R66] BUILD PASS"
Write-Host "[Phase6R66] COPY THIS XEX: $xex"
Write-Host "[Phase6R66] Capture R66 DSOUND POOL, R63 DSOUND HRESULT, R62 DSOUND ALLOC, XACT INIT and final fault/ticks"
