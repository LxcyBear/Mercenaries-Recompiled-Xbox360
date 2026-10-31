[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
# Offline source gates first; -PreflightOnly does not start Visual Studio/XDK.
# ASCII-only for Windows PowerShell 5.1. Avoid reserved automatic $Host/$HOME.
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$old=Join-Path $repo "build\phase6_integration_map\xpp_d559b_batch"
$new=Join-Path $repo "build\phase6_integration_map\xpp_d5272_batch"
$shards=Join-Path $old "translated_shards"
$parentMain=Join-Path $old "main.cpp"
$parentManifest=Join-Path $old "xpp-d559b-batch-manifest.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$stage=Join-Path $PSScriptRoot "Stage-XppD5272.py"
$targetShards=Join-Path $new "translated_shards"
$targetMain=Join-Path $new "main.cpp"
$targetManifest=Join-Path $new "xpp-d5272-batch-manifest.json"
$metaReport=Join-Path $new "xpp_d5272_source_audit.txt"
$privateSource=Join-Path $new "xpp_d5272_original_source_LOCAL_ONLY.txt"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$generatedEnv=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$buildDir=Join-Path $new "xdk"
$publishedXex=Join-Path $buildDir "Merc-XPP-D5272.xex"
foreach($file in @($parentMain,$parentManifest,$functions,$emitter,$stage,$builder,$generatedEnv)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[XPP-D5272] Required preexisting working file missing: $file"
    }
}
foreach($dir in @($shards,$generated)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "[XPP-D5272] Required original source tree missing: $dir"
    }
}
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[XPP-D5272] ======================================================="
Write-Host "[XPP-D5272]   REAL RETAIL XINPUTOPEN: NEXT HARDWARE FRONTIER"
Write-Host "[XPP-D5272] ======================================================="
Write-Host "[XPP-D5272] Current hardware: D559B and D5579 pass; D5272 at tick 27,107,599"
Write-Host "[XPP-D5272] Original XInputOpen: real Xbox 360 port query, handle=port+1"
Write-Host "[XPP-D5272] Verify source/stack/callee ABI before any XDK build"
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[XPP-D5272] Python syntax failure: no XDK build"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[XPP-D5272] Source guard self-test failed: no XDK"}
$stageArgs=@("--shards",$shards,
    "--parent-main",$parentMain,
    "--parent-manifest",$parentManifest,
    "--generated",$generated,
    "--functions",$functions,
    "--emitter",$emitter,
    "--out",$targetShards,
    "--out-main",$targetMain,
    "--manifest",$targetManifest,
    "--audit",$metaReport,
    "--private",$privateSource)
& $python -u $stage @stageArgs
if($LASTEXITCODE -ne 0){
    if(Test-Path -LiteralPath $metaReport -PathType Leaf){
        Write-Host "[XPP-D5272] LOCAL SOURCE AUDIT:"
        Get-Content -LiteralPath $metaReport -Encoding UTF8 -TotalCount 70
    }
    Write-Host "[XPP-D5272] Audit: $metaReport"
    Write-Host "[XPP-D5272] Private source to review: $privateSource"
    throw "[XPP-D5272] Source/ABI/closure unproven. NO XDK BUILD."
}
$meta=Get-Content -LiteralPath $targetManifest -Encoding UTF8 -Raw | ConvertFrom-Json
if($meta.marker -ne "XPP-D5272-NATIVE-XINPUTOPEN-20261031" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   $meta.hardware_target -ne "0x002D5272" -or
   [int]$meta.hardware_seed_ticks -ne 27107599 -or
   $meta.native_bridge -ne "XPP-D5272-NATIVE-XINPUTOPEN-20261031" -or
   $meta.native_real_input -ne $true -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[XPP-D5272] Original XInputOpen provenance/hard-fence gate mismatch"
}
$all=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File)
if($all.Count -ne 64){throw "[XPP-D5272] 64-TrueTU inventory incomplete"}
if((Get-FileHash (Join-Path $shards "translated_runtime.h") -Algorithm SHA256).Hash -ne
   (Get-FileHash (Join-Path $targetShards "translated_runtime.h") -Algorithm SHA256).Hash){
    throw "[XPP-D5272] Shared runtime header changed; refuse expensive full rebuild"
}
$beforeD559B=@($all | Select-String -Pattern "XPP 002D559B ENTRY" -List)
$beforeD5574=@($all | Select-String -Pattern "XPP D5574 ENTRY" -List)
$nativeD5272=@($all | Select-String -Pattern "XPP-D5272-NATIVE-XINPUTOPEN-20261031" -List)
$newEntry=@($all | Select-String -Pattern "XPP D5272 ENTRY" -List)
if($beforeD559B.Count -ne 1 -or $beforeD5574.Count -ne 1 -or
   $nativeD5272.Count -ne 1 -or $newEntry.Count -ne 1){
    throw "[XPP-D5272] Native input chain or exact original entry instrumentation missing"
}
$nativeCode=Get-Content -LiteralPath $nativeD5272[0].Path -Encoding UTF8 -Raw
if($nativeCode -notmatch 'XInputGetState\s*\(' -or
   $nativeCode -notmatch 'return port\+1u' -or
   $nativeCode -notmatch 'port >= 4u'){
    throw "[XPP-D5272] Source-backed real-controller/handle encoding changed"
}
$changed=@($meta.modified_true_tus)
if($changed.Count -lt 1 -or $changed.Count -gt 12){
    throw "[XPP-D5272] Unexpected incremental TrueTU footprint"
}
foreach($file in $changed){
    $actual=(Get-FileHash (Join-Path $targetShards $file) -Algorithm SHA256).Hash
    $expected=$meta.new_owner_hashes.PSObject.Properties[$file].Value
    if($actual -ne $expected){
        throw "[XPP-D5272] Staged changed TrueTU SHA mismatch: $file"
    }
}
Write-Host "[XPP-D5272] PREFLIGHT PASS: D5272 original return/ESP retained"
Write-Host "[XPP-D5272] Source-backed XInputOpen real hardware, handle port+1"
Write-Host "[XPP-D5272] Preserved 64 TrueTUs, D5574, D559B, D5579, K1S and all MMIO/VP hard fences"
Write-Host "[XPP-D5272] Changed TrueTUs: $($changed -join ', ')"
Write-Host "[XPP-D5272] Local-only source: $privateSource"
if($PreflightOnly){
    Write-Host "[XPP-D5272] PREFLIGHT ONLY: NO XDK BUILD"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$buildArgs=@{
    GeneratedMain=$targetMain
    GeneratedEnv=$generatedEnv
    GeneratedShardDir=$targetShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildDir "xdk-clean.log")
    BuildLog=(Join-Path $buildDir "xdk-build.log")
    PublishedXex=$publishedXex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[XPP-D5272] One incremental VS2017 Release Xbox 360 build (SKIP CLEAN)"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[XPP-D5272] Xbox XDK build failed; see xdk-build.log"}
if(-not(Test-Path -LiteralPath $publishedXex -PathType Leaf)){
    throw "[XPP-D5272] XDK returned without published XEX"
}
Write-Host "[XPP-D5272] BUILD PASS: $publishedXex"
Write-Host "[XPP-D5272] Xbox: verify XPP D5272 ENTRY, native open port, next genuine frontier"
Write-Host "[XPP-D5272] Do not infer a first frame from a blue background."
