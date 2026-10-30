[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pythonCmd=Get-Command python -ErrorAction SilentlyContinue
if($null -eq $pythonCmd){throw "[K1G] Python missing"}
$python=$pythonCmd.Source

# First re-run all already-hardware-proven K1E input, SHA and synthetic
# source gates. That script MUST stop before the XDK build.
$k1eBuilder=Join-Path $PSScriptRoot "Build-K1E-XactListTailWatch.ps1"
if(-not(Test-Path -LiteralPath $k1eBuilder -PathType Leaf)){
    throw "[K1G] Missing K1E guarded preflight"
}
Write-Host "[K1G] Rechecking K1E source/XEX/R76/64-TU provenance (no XDK)"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $k1eBuilder -PreflightOnly
if($LASTEXITCODE -ne 0){throw "[K1G] K1E preflight FAILED; no XDK build"}

$baseRoot=Join-Path $repo "build\phase6_integration_map\k1e_xact_list_tail"
$baseShards=Join-Path $baseRoot "translated_shards"
$baseManifest=Join-Path $baseRoot "k1e-xact-tail-manifest.json"
$stageRoot=Join-Path $repo "build\phase6_integration_map\k1g_xact_register_provenance"
$stageShards=Join-Path $stageRoot "translated_shards"
$stageManifest=Join-Path $stageRoot "k1g-register-provenance-manifest.json"
$buildDir=Join-Path $stageRoot "xdk"
$newXex=Join-Path $buildDir "Merc-K1G-XactRegisterProvenance.xex"
$main=Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$env=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$test=Join-Path $PSScriptRoot "Test-K1G-XactRegisterProvenance.py"
$stager=Join-Path $PSScriptRoot "Stage-K1G-XactRegisterProvenance.py"
foreach($file in @($baseManifest,$main,$env,$builder,$test,$stager)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1G] Missing required input: $file"
    }
}

& $python -u $test
if($LASTEXITCODE -ne 0){throw "[K1G] Synthetic regression failed; no XDK build"}
& $python -u $stager --k1e-shards $baseShards --k1e-manifest $baseManifest --out $stageShards
if($LASTEXITCODE -ne 0){throw "[K1G] One-TU stage failed; no XDK build"}

$k1e=Get-Content -LiteralPath $baseManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$k1g=Get-Content -LiteralPath $stageManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($k1g.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $k1g.marker -ne "K1G-XACT-REGISTER-PROVENANCE-20261030" -or
   [int]$k1g.original_shards -ne 64 -or [int]$k1g.unchanged_shards -ne 63 -or
   @($k1g.modified_shards).Count -ne 1 -or $k1g.modified_shards[0] -ne "translated_029.cpp" -or
   @($k1g.probe_stages).Count -ne 8 -or
   [int]$k1g.guest_reads_added -ne 0 -or [int]$k1g.guest_writes_added -ne 0 -or
   [int]$k1g.guest_register_writes_added -ne 0 -or
   $k1g.memory_hard_fences -ne "UNCHANGED" -or
   $k1g.preserved_k1e_witness -ne $true){
    throw "[K1G] Manifest/source policy failed before XDK"
}
$oldOwner=Join-Path $baseShards "translated_029.cpp"
$newOwner=Join-Path $stageShards "translated_029.cpp"
if($k1g.old_owner_sha256.ToUpperInvariant() -ne
   (Get-FileHash -LiteralPath $oldOwner -Algorithm SHA256).Hash -or
   $k1g.staged_owner_sha256.ToUpperInvariant() -ne
   (Get-FileHash -LiteralPath $newOwner -Algorithm SHA256).Hash){
    throw "[K1G] Source-owner digest does not match stage manifest"
}
$oldText=Get-Content -LiteralPath $oldOwner -Raw -Encoding UTF8
$newText=Get-Content -LiteralPath $newOwner -Raw -Encoding UTF8
if(([regex]::Matches($newText,'K1G XACT ABI ')).Count -ne 8 -or
   ([regex]::Matches($newText,'K1E XACT LIST PRE:')).Count -ne 1 -or
   ([regex]::Matches($oldText,'GUEST_READ(?:8|16|32|64|128)\(')).Count -ne
      ([regex]::Matches($newText,'GUEST_READ(?:8|16|32|64|128)\(')).Count -or
   ([regex]::Matches($oldText,'GUEST_WRITE(?:8|16|32|64|128)\(')).Count -ne
      ([regex]::Matches($newText,'GUEST_WRITE(?:8|16|32|64|128)\(')).Count){
    throw "[K1G] Original guest operations / K1E writer witness drifted"
}
$baseFiles=@(Get-ChildItem -LiteralPath $baseShards -File)
$stageFiles=@(Get-ChildItem -LiteralPath $stageShards -File)
if(@($baseFiles | Where-Object Name -like 'translated_*.cpp').Count -ne 64 -or
   @($stageFiles | Where-Object Name -like 'translated_*.cpp').Count -ne 64 -or
   $baseFiles.Count -ne $stageFiles.Count){
    throw "[K1G] Required 64-TU/header set missing"
}
foreach($file in $baseFiles){
    if($file.Name -eq "translated_029.cpp"){continue}
    $staged=Join-Path $stageShards $file.Name
    if(-not(Test-Path -LiteralPath $staged -PathType Leaf) -or
       (Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash -ne
       (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash){
        throw "[K1G] Unmodified TrueTU/header SHA drift: $($file.Name)"
    }
}
Write-Host "[K1G] PREFLIGHT PASS: 8 XACT entry/post-call register probes and K1E tail witness"
Write-Host "[K1G] 63 other TUs + all headers SHA-identical; no guest ops or hard fences changed"
if($PreflightOnly){
    Write-Host "[K1G] PREFLIGHT ONLY - NO XDK BUILD"
    exit 0
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$env
    GeneratedShardDir=$stageShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildDir "xdk-clean.log")
    BuildLog=(Join-Path $buildDir "xdk-build.log")
    PublishedXex=$newXex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[K1G] Incremental VS2017 Xbox 360 build: K1C main/env preserved, one modified TrueTU; CLEAN SKIPPED"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1G] XDK build failed"}
if(-not(Test-Path -LiteralPath $newXex -PathType Leaf)){
    throw "[K1G] Diagnostic XEX not published"
}
Write-Host "[K1G] BUILD PASS: $newXex"
Write-Host "[K1G] Xbox: capture K1G XACT ABI ENTRY / POST_COPY / AFTER_* / BEFORE_LIST, then K1E XACT LIST PRE"
Write-Host "[K1G] K1C boot marker preserved; do not use old XEX or change guest memory fences"
