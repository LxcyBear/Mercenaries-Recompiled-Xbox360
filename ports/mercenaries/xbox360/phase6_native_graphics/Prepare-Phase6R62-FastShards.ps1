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
    $command=Get-Command python -ErrorAction SilentlyContinue
    if($null-eq$command){throw "Python unavailable"}
    $python=$command.Source
}
$patcher=Join-Path $PSScriptRoot "quickpatch_phase6r62_dsound_alloc.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocket=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tu=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r59=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\Merc.xex"
$out=Join-Path $root "build\phase6_native_graphics\r62_fast_dsound_alloc"
$xex=Join-Path $out "Merc.xex"
foreach($file in @($patcher,$builder,(Join-Path $tu "main.cpp"),(Join-Path $tu "phase6tu-manifest.json"),(Join-Path $rocket "phase5_env.cpp"))){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "R62 missing input: $file"}
}
if(-not(Test-Path -LiteralPath $r59 -PathType Leaf)){
    Write-Host "[Phase6R62] WARNING: R59 baseline XEX not found (patch only works on validated R59 shards)"
}
New-Item -Path $out -ItemType Directory -Force|Out-Null
Write-Host "[Phase6R62] ========================================================"
Write-Host "[Phase6R62]    FAST 1-2 SHARD DSOUND ALLOCATION TRACE"
Write-Host "[Phase6R62] ========================================================"
Write-Host "[Phase6R62] R59 TrueTU cache reused. No 13,517-function regenerate/re-shard."
Write-Host "[Phase6R62] R59 published XEX preserved. Allocator/status unchanged."
& $python -m py_compile $patcher
if($LASTEXITCODE-ne0){throw "R62 Python syntax error"}
$patchLog=Join-Path $out "r62-quickpatch-preflight.log"
Write-Host "[Phase6R62] Preflight log: $patchLog"
$previousPreference=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
    & $python -u $patcher --tu-dir $tu --out-dir $out 2>&1 | Tee-Object -FilePath $patchLog
    $patchExit=$LASTEXITCODE
}finally{
    $ErrorActionPreference=$previousPreference
}
if($patchExit-ne0){
    $last=@(Get-Content -LiteralPath $patchLog -Tail 15) -join [Environment]::NewLine
    throw ("R62 quick-shard patch failed (exit={0}). Details:{1}{2}{1}Full log: {3}" -f $patchExit,[Environment]::NewLine,$last,$patchLog)
}
if($SkipSolutionBuild){
    Write-Host "[Phase6R62] Probe only applied; skipped XEX build."
    exit 0
}
$main=Join-Path $tu "main.cpp"
$shards=Join-Path $tu "translated_shards"
$envFile=Join-Path $rocket "phase5_env.cpp"
$args=@{
    GeneratedMain=$main
    GeneratedEnv=$envFile
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $out "xdk-clean.log")
    BuildLog=(Join-Path $out "xdk-build.log")
    PublishedXex=$xex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
& $builder @args
if($LASTEXITCODE-ne0){throw "R62 Xbox build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){throw "R62 XEX did not publish"}
Write-Host "[Phase6R62] BUILD PASS"
Write-Host "[Phase6R62] COPY THIS XEX: $xex"
Write-Host "[Phase6R62] Capture P6DQ R62 DSOUND ALLOC markers, XACT INIT, final ticks, crash registers"
Write-Host "[Phase6R62] R59 baseline XEX remains at: $r59"
