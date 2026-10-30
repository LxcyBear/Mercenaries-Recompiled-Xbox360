[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$python=Join-Path $repo ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){
    $cmd=Get-Command python -ErrorAction SilentlyContinue
    if($null -eq $cmd){ throw "[K1A-DSINDEX] Python missing" }
    $python=$cmd.Source
}
$base=Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$main=Join-Path $base "main.cpp"
$shards=Join-Path $base "translated_shards"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$k1aMain=Join-Path $repo "build\phase6_integration_map\k1a_clock_staging\main.cpp"
$k1aManifest=Join-Path $repo "build\phase6_integration_map\k1a_clock_staging\k1a-stage-manifest.json"
$stageRoot=Join-Path $repo "build\phase6_integration_map\k1a_dsindex_probe"
$stageShards=Join-Path $stageRoot "translated_shards"
$stageManifest=Join-Path $stageRoot "k1a-dsound-index-trace-manifest.json"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$buildDir=Join-Path $stageRoot "xdk"
$xex=Join-Path $buildDir "Merc-K1A-DSIndex-Probe.xex"
$shaExpected="A6A2493EC8F31F70165FEE3E3A8DBC72B02679E763DCC514F131FA3E04959C90"
foreach($need in @($main,$k1aMain,$k1aManifest,$envFile,$builder,
    (Join-Path $PSScriptRoot "Test-K1A-DsoundIndexTrace.py"),
    (Join-Path $PSScriptRoot "Stage-K1A-DsoundIndexTrace.py"))){
    if(-not(Test-Path -LiteralPath $need -PathType Leaf)){
        throw "[K1A-DSINDEX] Missing prerequisite: $need"
    }
}
if(-not(Test-Path -LiteralPath $shards -PathType Container)){
    throw "[K1A-DSINDEX] Original TrueTU shards missing: $shards"
}
if((Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash -ne $shaExpected){
    throw "[K1A-DSINDEX] R76 source SHA drift: refusing build"
}
$manifest=Get-Content -LiteralPath $k1aManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$mainSha=(Get-FileHash -LiteralPath $k1aMain -Algorithm SHA256).Hash
if($manifest.status -ne "STAGED_NOT_BUILT" -or
    $manifest.original_main_sha256.ToUpperInvariant() -ne $shaExpected -or
    $manifest.staged_main_sha256.ToUpperInvariant() -ne $mainSha -or
    -not ((Get-Content -LiteralPath $k1aMain -Raw).Contains("P6K1A-BOOT-CLOCK128-304-305-20261029"))){
    throw "[K1A-DSINDEX] Existing K1A 3-clock staged main identity mismatch"
}
$original=@{}
$originalFiles=@(Get-ChildItem -LiteralPath $shards -Filter "translated_*.cpp" -File)
if($originalFiles.Count -ne 64){ throw "[K1A-DSINDEX] Expected 64 TrueTU files" }
foreach($f in $originalFiles){
    $original[$f.Name]=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
}
Write-Host "[K1A-DSINDEX] ================================================"
Write-Host "[K1A-DSINDEX] AUDIO TABLE/EBX/STACK ROOT CAUSE: ONE SHARD"
Write-Host "[K1A-DSINDEX] ================================================"
Write-Host "[K1A-DSINDEX] Stage uses frozen R76 TrueTU originals and already-tested K1A clock main"
& $python -u (Join-Path $PSScriptRoot "Test-K1A-DsoundIndexTrace.py")
if($LASTEXITCODE -ne 0){throw "[K1A-DSINDEX] synthetic tests FAILED"}
& $python -u (Join-Path $PSScriptRoot "Stage-K1A-DsoundIndexTrace.py") --shards $shards --out $stageShards
if($LASTEXITCODE -ne 0){throw "[K1A-DSINDEX] source stage FAILED"}
$record=Get-Content -LiteralPath $stageManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($record.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
    [int]$record.original_shards -ne 64 -or
    [int]$record.unchanged_shards -ne 63 -or
    @($record.modified_shards).Count -ne 1 -or
    [int]$record.guest_register_writes_added -ne 0 -or
    $record.hard_fences -ne "PRESERVED"){
    throw "[K1A-DSINDEX] stage SHA/ownership manifest invalid"
}
$target=[string]$record.modified_shards[0]
if(-not $original.ContainsKey($target)){throw "[K1A-DSINDEX] unknown staged shard"}
if($record.original_modified_shard_sha256.ToUpperInvariant() -ne $original[$target] -or
   $record.staged_modified_shard_sha256.ToUpperInvariant() -ne
       (Get-FileHash -LiteralPath (Join-Path $stageShards $target) -Algorithm SHA256).Hash){
    throw "[K1A-DSINDEX] staged modified shard SHA mismatch"
}
Write-Host ("[K1A-DSINDEX] PREFLIGHT PASS: exact one modified TU={0}" -f $target)
Write-Host "[K1A-DSINDEX] K1A 3-clock source reused; other 63 TUs byte-identical"
if($PreflightOnly){
    Write-Host "[K1A-DSINDEX] PREFLIGHT ONLY: no Xbox build"
    exit 0
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
$argsMap=@{
    GeneratedMain=$k1aMain
    GeneratedEnv=$envFile
    GeneratedShardDir=$stageShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildDir "xdk-clean.log")
    BuildLog=(Join-Path $buildDir "xdk-build.log")
    PublishedXex=$xex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[K1A-DSINDEX] Incremental VS17 XDK build: only single shard altered, no clean"
& $builder @argsMap
if($LASTEXITCODE -ne 0){throw "[K1A-DSINDEX] XDK builder failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1A-DSINDEX] XDK did not publish diagnostic XEX"
}
foreach($f in $originalFiles){
    if((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -ne $original[$f.Name]){
        throw "[K1A-DSINDEX] Original TrueTU shard mutated: $($f.Name)"
    }
}
if((Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash -ne $shaExpected){
    throw "[K1A-DSINDEX] Original R76 source mutated"
}
Write-Host "[K1A-DSINDEX] BUILD PASS: unique diagnostic XEX compiled"
Write-Host "[K1A-DSINDEX] OUTPUT: $xex"
Write-Host "[K1A-DSINDEX] On real hardware collect: K1A DSINDEX ENTRY/LEA/PRE173/POST173"
Write-Host "[K1A-DSINDEX] No synthetic success, no MMIO fence change, no display PASS claimed"
