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
if($null -eq $py){ throw "[K1C] Python missing" }
$python=$py.Source

$k1b=Join-Path $repo "build\phase6_integration_map\k1b_central_write_watch_c3861fix"
$baseMain=Join-Path $k1b "main.cpp"
$baseManifest=Join-Path $k1b "k1b-central-writer-manifest.json"
$baseXex=Join-Path $k1b "xdk\Merc-K1B-CentralWriter-C3861Fix.xex"
$dsroot=Join-Path $repo "build\phase6_integration_map\k1a_dsobject_writer_watch"
$shards=Join-Path $dsroot "translated_shards"
$dsManifest=Join-Path $dsroot "k1a-dsound-writer-watch-manifest.json"
$dsindexManifest=Join-Path $repo "build\phase6_integration_map\k1a_dsindex_probe\k1a-dsound-index-trace-manifest.json"
$stage=Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va"
$main=Join-Path $stage "main.cpp"
$manifest=Join-Path $stage "k1c-write-site-manifest.json"
$buildDir=Join-Path $stage "xdk"
$xex=Join-Path $buildDir "Merc-K1C-GuestWriteSiteVA.xex"

$r76Main=Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$r76Sha="A6A2493EC8F31F70165FEE3E3A8DBC72B02679E763DCC514F131FA3E04959C90"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$stager=Join-Path $PSScriptRoot "Stage-K1C-ExactGuestWriteSite.py"
$tests=Join-Path $PSScriptRoot "Test-K1C-ExactGuestWriteSite.py"

foreach($p in @($baseMain,$baseManifest,$baseXex,$dsManifest,$dsindexManifest,
    $r76Main,$envFile,$builder,$stager,$tests)){
    if(-not(Test-Path -LiteralPath $p -PathType Leaf)){
        throw "[K1C] Missing frozen prerequisite: $p"
    }
}
if((Get-FileHash -LiteralPath $r76Main -Algorithm SHA256).Hash -ne $r76Sha){
    throw "[K1C] original R76 SHA drift"
}
$prev=Get-Content -LiteralPath $baseManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$oldHash=(Get-FileHash -LiteralPath $baseMain -Algorithm SHA256).Hash
if($prev.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $prev.new_main_sha256.ToUpperInvariant() -ne $oldHash -or
   $prev.marker -ne "P6K1B-CENTRAL-GUEST-WRITE-WATCH-20261030" -or
   [int]$prev.shard_count -ne 64 -or
   $prev.hard_fence_policy -ne "UNCHANGED"){
    throw "[K1C] K1B baseline main / XDK build provenance mismatch"
}
$ds=Get-Content -LiteralPath $dsManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$dsindex=Get-Content -LiteralPath $dsindexManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$files=@(Get-ChildItem -LiteralPath $shards -Filter "translated_*.cpp" -File)
$headers=@(Get-ChildItem -LiteralPath $shards -Filter "*.h" -File)
if($files.Count -ne 64 -or
   $headers.Count -ne [int]$ds.generated_header_count -or
   [int]$dsindex.unchanged_shards -ne 63 -or
   @($dsindex.modified_shards).Count -ne 1){
    throw "[K1C] frozen DSINDEX TrueTU set mismatch"
}
$modified=[string]$dsindex.modified_shards[0]
foreach($f in $files){
    if($f.Name -eq $modified -and
       (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -ne
       $dsindex.staged_modified_shard_sha256.ToUpperInvariant()){
        throw "[K1C] modified DSINDEX TrueTU hash mismatch"
    }
}
if(@($headers | Where-Object Name -eq "translated_runtime.h").Count -ne 1){
    throw "[K1C] runtime header missing"
}
foreach($f in $headers){
    $expected=[string]$prev.source_header_shas.($f.Name)
    if([string]::IsNullOrEmpty($expected) -or
       (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -ne $expected.ToUpperInvariant()){
        throw "[K1C] header SHA drift: $($f.Name)"
    }
}

Write-Host "[K1C] R76 + K1B XEX + DSINDEX 64 TrueTU/header hashes verified"
& $python -u $tests
if($LASTEXITCODE -ne 0){ throw "[K1C] synthetic regression failed; NO XDK build" }
& $python -u $stager --main $baseMain --shards $shards --out $main
if($LASTEXITCODE -ne 0){ throw "[K1C] stage failed; NO XDK build" }
$doc=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$newHash=(Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash
if($doc.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $doc.boot_marker -ne "P6K1C-EXACT-WRITE-SITE-VA-20261030" -or
   $doc.original_main_sha256.ToUpperInvariant() -ne $oldHash -or
   $doc.staged_main_sha256.ToUpperInvariant() -ne $newHash -or
   [int]$doc.translated_cpp_count -ne 64 -or
   [int]$doc.generated_header_count -ne $headers.Count -or
   [int]$doc.extra_guest_memory_writes -ne 0 -or
   $doc.guest_memory_hard_fence -ne "UNCHANGED"){
    throw "[K1C] generated source identity mismatch"
}
$content=Get-Content -LiteralPath $main -Raw -Encoding UTF8
$siteCount=([regex]::Matches($content,'K1C WRITE SITE: width=%u')).Count
$vaCount=([regex]::Matches($content,'\(unsigned\)k1c_read_guest_va\(\),')).Count
$helperDeclarationCount=([regex]::Matches($content,'static DWORD k1c_read_guest_va\(void\);')).Count
$helperBodyCount=([regex]::Matches($content,'static DWORD k1c_read_guest_va\(void\)\s*\{\s*return s_phase6cpCurrentVa;\s*\}')).Count
$trackerCount=([regex]::Matches($content,'static DWORD s_phase6cpCurrentVa = 0u;')).Count
$bootCount=([regex]::Matches($content,'P6K1C-EXACT-WRITE-SITE-VA-20261030')).Count
if($siteCount -ne 5 -or $vaCount -ne 5 -or $bootCount -ne 1 -or
   $helperDeclarationCount -ne 1 -or $helperBodyCount -ne 1 -or $trackerCount -ne 1){
    throw "[K1C] pre-XDK source gate FAILED site=$siteCount va=$vaCount boot=$bootCount prototype=$helperDeclarationCount helper=$helperBodyCount tracker=$trackerCount"
}
Write-Host "[K1C] PREFLIGHT PASS: 5 guest-VA helper witnesses, one boot tag, untouched tracker and 64 TrueTUs"
if($PreflightOnly){
    Write-Host "[K1C] PREFLIGHT ONLY - XDK build skipped"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$buildArgs=@{
    GeneratedMain=$main
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
Write-Host "[K1C] XDK incremental build: ONLY generated main changed, no Clean"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){ throw "[K1C] XDK build failed" }
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1C] expected distinct K1C XEX not published"
}
if((Get-FileHash -LiteralPath $baseMain -Algorithm SHA256).Hash -ne $oldHash){
    throw "[K1C] K1B baseline source modified; refusing success"
}
Write-Host "[K1C] BUILD PASS: $xex"
Write-Host "[K1C] Xbox: verify P6K1C boot mark and K1C WRITE SITE address=00041D70"
Write-Host "[K1C] guest_va is last translated VA tracker, NOT necessarily exact store PC"
Write-Host "[K1C] No guest pointer repair, unknown-MMIO bypass or altered hard fence"
