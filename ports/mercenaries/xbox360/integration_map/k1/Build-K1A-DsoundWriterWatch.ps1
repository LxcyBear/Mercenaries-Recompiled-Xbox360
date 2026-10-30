[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pycmd=Get-Command python -ErrorAction SilentlyContinue
if($null -eq $pycmd){ throw "[K1A-DSOBJECT] Python not found" }
$python=$pycmd.Source
$base=Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk"
$originalMain=Join-Path $base "main.cpp"
$origShardDir=Join-Path $base "translated_shards"
$clockMain=Join-Path $repo "build\phase6_integration_map\k1a_clock_staging\main.cpp"
$clockManifest=Join-Path $repo "build\phase6_integration_map\k1a_clock_staging\k1a-stage-manifest.json"
$dsRoot=Join-Path $repo "build\phase6_integration_map\k1a_dsindex_probe"
$dsShardDir=Join-Path $dsRoot "translated_shards"
$dsManifest=Join-Path $dsRoot "k1a-dsound-index-trace-manifest.json"
$stageDir=Join-Path $repo "build\phase6_integration_map\k1a_dsobject_writer_watch"
$main=Join-Path $stageDir "main.cpp"
$manifestPath=Join-Path $stageDir "k1a-dsound-writer-watch-manifest.json"
$buildDir=Join-Path $stageDir "xdk"
$xex=Join-Path $buildDir "Merc-K1A-DSObjectWriter.xex"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$r76Hash="A6A2493EC8F31F70165FEE3E3A8DBC72B02679E763DCC514F131FA3E04959C90"
foreach($p in @($originalMain,$clockMain,$clockManifest,$dsManifest,$envFile,$builder,
    (Join-Path $PSScriptRoot "Test-K1A-DsoundWriterWatch.py"),
    (Join-Path $PSScriptRoot "Stage-K1A-DsoundWriterWatch.py"))){
    if(-not(Test-Path -LiteralPath $p -PathType Leaf)){
        throw "[K1A-DSOBJECT] Missing prerequisite: $p"
    }
}
if((Get-FileHash -LiteralPath $originalMain -Algorithm SHA256).Hash -ne $r76Hash){
    throw "[K1A-DSOBJECT] Original R76 main SHA changed"
}
$k1=Get-Content -LiteralPath $clockManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$clockSha=(Get-FileHash -LiteralPath $clockMain -Algorithm SHA256).Hash
if($k1.status -ne "STAGED_NOT_BUILT" -or
    $k1.original_main_sha256.ToUpperInvariant() -ne $r76Hash -or
    $k1.staged_main_sha256.ToUpperInvariant() -ne $clockSha -or
    $k1.boot_marker -ne "P6K1A-BOOT-CLOCK128-304-305-20261029"){
    throw "[K1A-DSOBJECT] Baseline 3-clock K1A main identity mismatch"
}
$ds=Get-Content -LiteralPath $dsManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($ds.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
    [int]$ds.unchanged_shards -ne 63 -or
    @($ds.modified_shards).Count -ne 1 -or
    $ds.hard_fences -ne "PRESERVED"){
    throw "[K1A-DSOBJECT] Baseline DSINDEX shard stage identity mismatch"
}
$originalFiles=@(Get-ChildItem -LiteralPath $origShardDir -Filter "translated_*.cpp" -File)
$stagedFiles=@(Get-ChildItem -LiteralPath $dsShardDir -Filter "translated_*.cpp" -File)
if($originalFiles.Count -ne 64 -or $stagedFiles.Count -ne 64){
    throw "[K1A-DSOBJECT] Missing original or staged 64-shard TrueTU set"
}
$target=[string]$ds.modified_shards[0]
$watchOriginal=@{}
foreach($f in $originalFiles){
    $watchOriginal[$f.Name]=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
    $stagedFile=Join-Path $dsShardDir $f.Name
    $got=(Get-FileHash -LiteralPath $stagedFile -Algorithm SHA256).Hash
    $want=if($f.Name -eq $target){$ds.staged_modified_shard_sha256.ToUpperInvariant()}else{$watchOriginal[$f.Name]}
    if($got -ne $want){
        throw "[K1A-DSOBJECT] Staged TrueTU SHA mismatch: $($f.Name)"
    }
}
$headers=@(Get-ChildItem -LiteralPath $origShardDir -Filter "*.h" -File)
if(-not (@($headers | Where-Object Name -eq "translated_runtime.h").Count -eq 1)){
    throw "[K1A-DSOBJECT] Missing original translated_runtime.h"
}
if((@(Get-ChildItem -LiteralPath $dsShardDir -Filter "*.h" -File)).Count -ne $headers.Count){
    throw "[K1A-DSOBJECT] Staged TrueTU header count mismatch"
}
foreach($header in $headers){
    $copy=Join-Path $dsShardDir $header.Name
    if(-not(Test-Path -LiteralPath $copy -PathType Leaf) -or
       (Get-FileHash -LiteralPath $copy -Algorithm SHA256).Hash -ne
       (Get-FileHash -LiteralPath $header.FullName -Algorithm SHA256).Hash){
        throw "[K1A-DSOBJECT] Staged header missing or SHA mismatch: $($header.Name)"
    }
}
Write-Host "[K1A-DSOBJECT] R76 main, K1A clock source, 64 TrueTUs and runtime headers verified"
& $python -u (Join-Path $PSScriptRoot "Test-K1A-DsoundWriterWatch.py")
if($LASTEXITCODE -ne 0){ throw "[K1A-DSOBJECT] Writer-watch synthetic tests failed" }
& $python -u (Join-Path $PSScriptRoot "Stage-K1A-DsoundWriterWatch.py") --main $clockMain --out $main
if($LASTEXITCODE -ne 0){ throw "[K1A-DSOBJECT] Failed to stage writer-watch main" }
$watched=Get-Content -LiteralPath $manifestPath -Raw -Encoding UTF8 | ConvertFrom-Json
if($watched.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $watched.original_main_sha256.ToUpperInvariant() -ne $clockSha -or
   $watched.staged_main_sha256.ToUpperInvariant() -ne
       (Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash -or
   $watched.guest_write_semantics -ne "PRESERVED" -or
   $watched.unknown_memory_fences -ne "PRESERVED"){
    throw "[K1A-DSOBJECT] Staged writer-watch manifest mismatch"
}
Write-Host "[K1A-DSOBJECT] PREFLIGHT PASS: write8/write16/write32 watch, one DSINDEX TU"
if($PreflightOnly){
    Write-Host "[K1A-DSOBJECT] PREFLIGHT ONLY: XDK build skipped"
    exit 0
}
New-Item -ItemType Directory -Path $buildDir -Force | Out-Null
$buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$envFile
    GeneratedShardDir=$dsShardDir
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
Write-Host "[K1A-DSOBJECT] Incremental XDK build: inherited K1A clocks, DSINDEX and guest object write watch"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){ throw "[K1A-DSOBJECT] XDK build wrapper failed" }
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1A-DSOBJECT] New diagnostic XEX missing"
}
Write-Host "[K1A-DSOBJECT] BUILD PASS: distinct diagnostic XEX created"
Write-Host "[K1A-DSOBJECT] OUTPUT: $xex"
Write-Host "[K1A-DSOBJECT] Xbox log search: K1A DSOBJECT WRITE and K1A DSINDEX ENTRY/LEA/PRE173/POST173"
Write-Host "[K1A-DSOBJECT] NO guest pointer repairs, no MMIO rule changes, no pixels claimed"
