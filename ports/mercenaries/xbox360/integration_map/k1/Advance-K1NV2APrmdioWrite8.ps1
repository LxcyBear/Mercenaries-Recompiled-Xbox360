[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$native=Join-Path $repo "build\phase6_integration_map\k1_ntquerydirectory207_native"
$nativeMain=Join-Path $native "main.cpp"
$nativeShards=Join-Path $native "translated_shards"
$nativeManifest=Join-Path $native "k1_ntquerydirectory207_native_manifest.json"
$nativeXex=Join-Path $native "xdk\Merc-K1NT207-RealDirectory.xex"
$stageRoot=Join-Path $repo "build\phase6_integration_map\k1_nv2a_prmdio_write8"
$newMain=Join-Path $stageRoot "main.cpp"
$newManifest=Join-Path $stageRoot "k1nv2a-prmdio-manifest.json"
$audit=Join-Path $PSScriptRoot "Audit-K1NV2ASource.py"
$stage=Join-Path $PSScriptRoot "Stage-K1NV2APrmdioWrite8.py"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$outXdk=Join-Path $stageRoot "xdk"
$outXex=Join-Path $outXdk "Merc-K1NV2A-PRMDIO-Write8-Witness.xex"
$python=(Get-Command python -ErrorAction Stop).Source
foreach($file in @($nativeMain,$nativeManifest,$nativeXex,$stage,$audit,$envFile,$builder)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){ throw "[K1NV2A] Missing input: $file" }
}
if(-not(Test-Path -LiteralPath $nativeShards -PathType Container)){
    throw "[K1NV2A] Original 64 TrueTUs missing"
}
$meta=Get-Content -LiteralPath $nativeManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($meta.marker -ne "K1NT207-REAL-DIRECTORY-ENUMERATION-20261102" -or
    $meta.status -ne "NATIVE_DIRECTORY_SOURCE_STAGED_NO_XDK" -or
    $meta.mmio_fences -ne "UNCHANGED" -or
    $meta.native_directory_service_staged -ne $true -or
    [int]$meta.xpp_guest_tus_unchanged -ne 64 -or
    $meta.native_main_sha256 -ne (Get-FileHash -LiteralPath $nativeMain -Algorithm SHA256).Hash.ToLowerInvariant() -or
    $meta.native_runtime_header_sha256 -ne (Get-FileHash -LiteralPath (Join-Path $nativeShards "translated_runtime.h") -Algorithm SHA256).Hash.ToLowerInvariant()){
    throw "[K1NV2A] K1NT207 native provenance mismatch, refuse diagnostic"
}
$shards=@(Get-ChildItem -LiteralPath $nativeShards -Filter "translated_???.cpp" -File)
if($shards.Count -ne 64){throw "[K1NV2A] Exactly 64 existing TrueTUs required"}
Write-Host "[K1NV2A] ==========================================================="
Write-Host "[K1NV2A] NV2A PRMDIO+03C8 WRITE8 FIRST-FAULT PROVENANCE"
Write-Host "[K1NV2A] Hardware: tick=56902779 target=FD6813C8 size=1"
Write-Host "[K1NV2A] NO MMIO BYPASS. Original fault must remain."
Write-Host "[K1NV2A] Main-only incremental stage; 64 TrueTUs reused"
Write-Host "[K1NV2A] ==========================================================="
& $python -m py_compile $stage $audit
if($LASTEXITCODE -ne 0){throw "[K1NV2A] Python parser failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1NV2A] Synthetic probe fixtures failed"}
& $python -u $stage --main $nativeMain --out $newMain --manifest $newManifest
if($LASTEXITCODE -ne 0){throw "[K1NV2A] Observation stage failed"}
$doc=Get-Content -LiteralPath $newManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($doc.marker -ne "P6K1NV2A-PRMDIO-WRITE8-20261103" -or
   $doc.status -ne "MAIN_ONLY_DIAGNOSTIC_STAGED_NO_XDK" -or
   $doc.source_main_sha256 -ne $meta.native_main_sha256 -or
   $doc.new_main_sha256 -ne (Get-FileHash -LiteralPath $newMain -Algorithm SHA256).Hash.ToLowerInvariant() -or
   [int]$doc.translated_tus_changed -ne 0 -or
   [int]$doc.runtime_headers_changed -ne 0 -or
   $doc.access_fences_changed -ne $false -or
   $doc.unknown_nv2a_address_handled -ne $false){
    throw "[K1NV2A] Derived diagnostic manifest mismatch"
}
$oldHashes=@{}
foreach($f in $shards){$oldHashes[$f.Name]=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash}
$auditOutput=Join-Path $stageRoot "k1nv2a-source-candidates.txt"
$xbe=Join-Path $repo "game_files\mercenaries-retail\default.xbe"
if(Test-Path -LiteralPath $xbe -PathType Leaf){
    & $python -u $audit --shards $nativeShards --xbe $xbe --out $auditOutput --max 32
}else{
    & $python -u $audit --shards $nativeShards --out $auditOutput --max 32
}
if($LASTEXITCODE -ne 0){throw "[K1NV2A] Original translated-source audit failed; no XDK"}
foreach($f in $shards){
    if($oldHashes[$f.Name] -ne (Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash){
        throw "[K1NV2A] Inherited TrueTU modified: $($f.Name)"
    }
}
Write-Host "[K1NV2A] SOURCE AUDIT: $auditOutput"
Write-Host "[K1NV2A] PREFLIGHT PASS: one-host-only fault-value witness, all original hard fences remain"
if(-not $Build){
    Write-Host "[K1NV2A] NO XDK. Add -Build to compile isolated PRMDIO diagnostic XEX."
    exit 0
}
New-Item -ItemType Directory -Force -Path $outXdk|Out-Null
$buildArgs=@{
    GeneratedMain=$newMain
    GeneratedEnv=$envFile
    GeneratedShardDir=$nativeShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $outXdk "xdk-clean.log")
    BuildLog=(Join-Path $outXdk "xdk-build.log")
    PublishedXex=$outXex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[K1NV2A] ONE incremental XDK Release build. Main changed; 64 shards unchanged."
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1NV2A] XDK build failed: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $outXex -PathType Leaf)){
    throw "[K1NV2A] Output XEX missing"
}
Write-Host "[K1NV2A] XDK BUILD PASS: $outXex"
Write-Host "[K1NV2A] On Xbox capture P6K1NV2A boot tag and K1NV2A EXACT WRITE8 record"
Write-Host "[K1NV2A] Expect original FD6813C8 hard fence to remain after the witness"
