[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$py=Get-Command python -ErrorAction SilentlyContinue
if($null -eq $py){ throw "[K1B] Python missing" }
$python=$py.Source
$r76=Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$old=Join-Path $repo "build\phase6_integration_map\k1a_dsobject_writer_watch"
$oldMain=Join-Path $old "main.cpp"
$oldManifest=Join-Path $old "k1a-dsound-writer-watch-manifest.json"
$shards=Join-Path $old "translated_shards"
$dsindex=Join-Path $repo "build\phase6_integration_map\k1a_dsindex_probe\k1a-dsound-index-trace-manifest.json"
$stage=Join-Path $repo "build\phase6_integration_map\k1b_central_write_watch"
$newMain=Join-Path $stage "main.cpp"
$newManifest=Join-Path $stage "k1b-central-writer-manifest.json"
$buildDir=Join-Path $stage "xdk"
$xex=Join-Path $buildDir "Merc-K1B-CentralWriter.xex"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$buildWrapper=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$test=Join-Path $PSScriptRoot "Test-K1A-CentralGuestWriteWatch.py"
$stager=Join-Path $PSScriptRoot "Stage-K1A-CentralGuestWriteWatch.py"
$expectedR76="A6A2493EC8F31F70165FEE3E3A8DBC72B02679E763DCC514F131FA3E04959C90"
foreach($file in @($r76,$oldMain,$oldManifest,$dsindex,$envFile,$buildWrapper,$test,$stager)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1B] Missing frozen prerequisite: $file"
    }
}
if((Get-FileHash -LiteralPath $r76 -Algorithm SHA256).Hash -ne $expectedR76){
    throw "[K1B] R76 original source SHA mismatch"
}
$oldDoc=Get-Content -LiteralPath $oldManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$oldSha=(Get-FileHash -LiteralPath $oldMain -Algorithm SHA256).Hash
if($oldDoc.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $oldDoc.main_staged_sha256.ToUpperInvariant() -ne $oldSha -or
   [int]$oldDoc.generated_cpp_count -ne 64 -or
   [int]$oldDoc.changed_cpp_count -ne 0 -or
   $oldDoc.guest_write_semantics -ne "PRESERVED" -or
   $oldDoc.unknown_memory_fences -ne "PRESERVED" -or
   [string]$oldDoc.writer_owner -ne "main.cpp"){
    throw "[K1B] K1A DSOBJECT main manifest mismatch; do not stack against unproven source"
}
$dsDoc=Get-Content -LiteralPath $dsindex -Raw -Encoding UTF8 | ConvertFrom-Json
$actualCpp=@(Get-ChildItem -LiteralPath $shards -Filter "translated_*.cpp" -File)
$actualHeaders=@(Get-ChildItem -LiteralPath $shards -Filter "*.h" -File)
if($actualCpp.Count -ne 64 -or
   $actualHeaders.Count -ne [int]$oldDoc.generated_header_count -or
   @($actualHeaders | Where-Object Name -eq "translated_runtime.h").Count -ne 1 -or
   [int]$dsDoc.unchanged_shards -ne 63 -or
   @($dsDoc.modified_shards).Count -ne 1){
    throw "[K1B] Existing 64 TrueTU + DSINDEX/header provenance not valid"
}
$modified=[string]$dsDoc.modified_shards[0]
foreach($file in $actualCpp){
    $sha=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if($file.Name -eq $modified){
        if($sha -ne $dsDoc.staged_modified_shard_sha256.ToUpperInvariant()){
            throw "[K1B] Instrumented DSINDEX TrueTU SHA drift: $($file.Name)"
        }
    }
}
foreach($header in $actualHeaders){
    if($header.Name -eq "translated_runtime.h" -and
        (Get-FileHash -LiteralPath $header.FullName -Algorithm SHA256).Hash -ne
        $oldDoc.runtime_header_staged_sha256.ToUpperInvariant()){
        throw "[K1B] Frozen generated runtime-header SHA mismatch"
    }
}
Write-Host "[K1B] R76 hash PASS, K1A clock & DSINDEX & DSOBJECT source identity PASS"
Write-Host "[K1B] Running synthetic 5-writer regression (NO Xbox build yet)"
& $python -u $test
if($LASTEXITCODE -ne 0){throw "[K1B] Synthetic test FAILED before XDK"}
& $python -u $stager --main $oldMain --shards $shards --out $newMain
if($LASTEXITCODE -ne 0){throw "[K1B] Source stage FAILED before XDK"}
$doc=Get-Content -LiteralPath $newManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$newSha=(Get-FileHash -LiteralPath $newMain -Algorithm SHA256).Hash
if($doc.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $doc.old_main_sha256.ToUpperInvariant() -ne $oldSha -or
   $doc.new_main_sha256.ToUpperInvariant() -ne $newSha -or
   $doc.marker -ne "P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030" -or
   $doc.shard_count -ne 64 -or
   $doc.instrumented_guest_writer_widths.Count -ne 5 -or
   $doc.guest_memory_writes_added -ne 0 -or
   $doc.hard_fence_policy -ne "UNCHANGED"){
    throw "[K1B] New staged source manifest identity mismatch"
}
Write-Host "[K1B] PREFLIGHT PASS: one modified main, 5 central writer widths, 64 frozen TrueTUs"
Write-Host "[K1B] BOOT MARKER: P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030"
if($PreflightOnly){
    Write-Host "[K1B] PREFLIGHT ONLY - no XDK build"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$buildArgs=@{
    GeneratedMain=$newMain
    GeneratedEnv=$envFile
    GeneratedShardDir=$shards
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
Write-Host "[K1B] Incremental VS2017 XDK build, no clean, no new TrueTU generation"
& $buildWrapper @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1B] XDK build failed"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1B] No diagnostic XEX published"
}
if((Get-FileHash -LiteralPath $oldMain -Algorithm SHA256).Hash -ne $oldSha){
    throw "[K1B] Original K1A DSOBJECT source changed; refusing PASS"
}
Write-Host "[K1B] BUILD PASS: $xex"
Write-Host "[K1B] Xbox: check P6K1B boot watermark and K1B CENTRAL WRITE messages"
Write-Host "[K1B] Old K1A XEX preserved; no EFEE0EC4 memory bypass or fake display claims"
