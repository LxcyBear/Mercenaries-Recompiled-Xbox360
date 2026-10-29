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
$script=Join-Path $PSScriptRoot "quickpatch_phase6r71_fc4a_object_abi.py"
$builder=Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"
$rocket=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk"
$tu=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$r62=Join-Path $root "build\phase6_native_graphics\r62_fast_dsound_alloc"
$r63=Join-Path $root "build\phase6_native_graphics\r63_fast_dsound_hresult"
$r66=Join-Path $root "build\phase6_native_graphics\r66_fast_dsound_pool"
$r69=Join-Path $root "build\phase6_native_graphics\r69_fast_dsound_seed"
$r71=Join-Path $root "build\phase6_native_graphics\r71_fast_fc4a_object_abi"
$xex=Join-Path $r71 "Merc.xex"
foreach($f in @($script,$builder,(Join-Path $rocket "phase5_env.cpp"),
  (Join-Path $tu "main.cpp"),(Join-Path $tu "phase6tu-manifest.json"),
  (Join-Path $r62 "quick-shard-overlay.json"),
  (Join-Path $r63 "quick-shard-overlay.json"),
  (Join-Path $r66 "quick-shard-overlay.json"),
  (Join-Path $r69 "quick-shard-overlay.json"))){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R71 input missing: $f"}
}
New-Item -ItemType Directory -Path $r71 -Force | Out-Null
$log=Join-Path $r71 "r71-quickpatch-preflight.log"
Write-Host "[Phase6R71] ===================================================="
Write-Host "[Phase6R71]  FC4A -> A19FC DSOUND OBJECT POINTER / X86 ABI REPAIR"
Write-Host "[Phase6R71] ===================================================="
Write-Host "[Phase6R71] R70: A19FC had null object, seeded low guest addr 0x78"
Write-Host "[Phase6R71] FC4A has valid object stored in [outer+0xC]"
Write-Host "[Phase6R71] R59: A19FC corrupted guest EBX/ESI/EDI on return"
Write-Host "[Phase6R71] Single-shard repair, R62/R63/R66/R69 overlays retained"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R71 Python preflight failed"}
$old=$ErrorActionPreference
$ErrorActionPreference="Continue"
try {
    & $python -u $script --tu-dir $tu --r62-dir $r62 --r63-dir $r63 --r66-dir $r66 --r69-dir $r69 --out-dir $r71 2>&1 |
        Tee-Object -FilePath $log
    $exit=$LASTEXITCODE
} finally { $ErrorActionPreference=$old }
if($exit-ne0){
    $tail=@(Get-Content -LiteralPath $log -Tail 16) -join [Environment]::NewLine
    throw ("R71 failed before build: {0}{1}{2}{1}{3}" -f $exit,[Environment]::NewLine,$tail,$log)
}
if($SkipSolutionBuild) {
    Write-Host "[Phase6R71] Preflight PASS. Xbox build skipped."
    exit 0
}
$args=@{
  GeneratedMain=(Join-Path $tu "main.cpp")
  GeneratedEnv=(Join-Path $rocket "phase5_env.cpp")
  GeneratedShardDir=(Join-Path $tu "translated_shards")
  ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
  ExpectedEnvCookie="phase6dq_env_build_cookie"
  SolutionRoot=$SolutionRoot
  Configuration="Release"
  Platform="Xbox 360"
  CleanLog=(Join-Path $r71 "xdk-clean.log")
  BuildLog=(Join-Path $r71 "xdk-build.log")
  PublishedXex=$xex
  ShadowBuildRoot=$FastBuildRoot
  SkipClean=$true
}
& $builder @args
if($LASTEXITCODE-ne0){throw "R71 Xbox build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){throw "R71 output XEX missing"}
Write-Host "[Phase6R71] BUILD PASS"
Write-Host "[Phase6R71] PUBLISH: $xex"
Write-Host "[Phase6R71] Send R71 OBJECT ABI and R69 SEED, R66 POOL, final XACT/fault/ticks"
