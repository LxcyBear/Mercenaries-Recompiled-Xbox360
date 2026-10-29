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
    if($null-eq$cmd){throw "Python is not available"}
    $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "quickpatch_phase6r63_dsound_hresult.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocket=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tu=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r62=Join-Path $root "build\phase6_native_graphics\r62_fast_dsound_alloc"
$r63=Join-Path $root "build\phase6_native_graphics\r63_fast_dsound_hresult"
$xex=Join-Path $r63 "Merc.xex"
foreach($f in @($script,$builder,(Join-Path $rocket "phase5_env.cpp"),(Join-Path $tu "main.cpp"),(Join-Path $tu "phase6tu-manifest.json"),(Join-Path $r62 "quick-shard-overlay.json"))){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R63 missing validated input: $f"}
}
New-Item -ItemType Directory -Path $r63 -Force|Out-Null
$preflight=Join-Path $r63 "r63-quickpatch-preflight.log"
Write-Host "[Phase6R63] ======================================================="
Write-Host "[Phase6R63]   TWO-SHARD F03A / F0C6 STATUS PROVENANCE"
Write-Host "[Phase6R63] ======================================================="
Write-Host "[Phase6R63] R62 Xbox: primary FF54 failed once, fallback succeeded"
Write-Host "[Phase6R63] R62 Xbox: F03A->FF54 probe never executed; F495=8007000E"
Write-Host "[Phase6R63] Reuse R62 TrueTU output; modify only shards 022 and 055"
Write-Host "[Phase6R63] No Rocket re-emission or monolithic TrueTU regeneration"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R63 syntax preflight failed"}
$previous=$ErrorActionPreference
$ErrorActionPreference="Continue"
try{
    & $python -u $script --tu-dir $tu --r62-dir $r62 --out-dir $r63 2>&1 | Tee-Object -FilePath $preflight
    $code=$LASTEXITCODE
}finally{
    $ErrorActionPreference=$previous
}
if($code-ne0){
    $tail=@(Get-Content -LiteralPath $preflight -Tail 18) -join [Environment]::NewLine
    throw ("R63 quickpatch failed (exit={0}){1}{2}{1}Saved: {3}" -f $code,[Environment]::NewLine,$tail,$preflight)
}
if($SkipSolutionBuild){
    Write-Host "[Phase6R63] Preflight PASS. No Xbox build requested."
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
  CleanLog=(Join-Path $r63 "xdk-clean.log")
  BuildLog=(Join-Path $r63 "xdk-build.log")
  PublishedXex=$xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @buildArgs
if($LASTEXITCODE-ne0){throw "R63 XDK build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){throw "R63 XEX missing"}
Write-Host "[Phase6R63] BUILD PASS"
Write-Host "[Phase6R63] COPY THIS XEX: $xex"
Write-Host "[Phase6R63] Capture R63 DSOUND HRESULT, R62 DSOUND ALLOC, R58 DSOUND STATUS, XACT INIT and final ticks"
