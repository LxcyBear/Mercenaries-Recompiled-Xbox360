[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1 ASCII. Reuse D5272's 64 TrueTUs, no full clean.
# -PreflightOnly: local original-source gates, NEVER builds or deploys.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$old=Join-Path $repo "build\phase6_integration_map\xpp_d5272_batch"
$new=Join-Path $repo "build\phase6_integration_map\xpp_d52d4_batch"
$shards=Join-Path $old "translated_shards"
$parentMain=Join-Path $old "main.cpp"
$parentManifest=Join-Path $old "xpp-d5272-batch-manifest.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$stage=Join-Path $PSScriptRoot "Stage-XppD52D4.py"
$targetShards=Join-Path $new "translated_shards"
$targetMain=Join-Path $new "main.cpp"
$targetManifest=Join-Path $new "xpp-d52d4-batch-manifest.json"
$privateOriginal=Join-Path $new "xpp_d52d4_original_source_LOCAL_ONLY.txt"
$buildRoot=Join-Path $new "xdk"
$published=Join-Path $buildRoot "Merc-XPP-D52D4.xex"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
foreach($file in @($parentMain,$parentManifest,$functions,$emitter,$stage,$builder,$envSource)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[XPP-D52D4] Missing known-good original input: $file"
    }
}
foreach($dir in @($shards,$generated)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "[XPP-D52D4] Missing original 64-TU or generated corpus: $dir"
    }
}
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[XPP-D52D4] =================================================="
Write-Host "[XPP-D52D4] ORIGINAL XINPUTGETCAPABILITIES - REAL FRONTIER"
Write-Host "[XPP-D52D4] =================================================="
Write-Host "[XPP-D52D4] Hardware: XInputOpen port=0 handle=1; target 002D52D4 tick 27,107,602"
Write-Host "[XPP-D52D4] Original EAX helper + ESP += 12 => ret8 for two guest args"
Write-Host "[XPP-D52D4] Native XInputGetCapabilities + original-Xbox 28-byte guest layout"
Write-Host "[XPP-D52D4] No synthetic graphics, no fake controller connection, MMIO fences unchanged"
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[XPP-D52D4] Syntax gate failed; NO XDK"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[XPP-D52D4] Synthetic source/ABI test failed; NO XDK"}
$argsList=@(
    "--shards",$shards,
    "--parent-main",$parentMain,
    "--parent-manifest",$parentManifest,
    "--generated",$generated,
    "--functions",$functions,
    "--emitter",$emitter,
    "--out",$targetShards,
    "--out-main",$targetMain,
    "--manifest",$targetManifest,
    "--private",$privateOriginal
)
& $python -u $stage @argsList
if($LASTEXITCODE -ne 0){
    throw "[XPP-D52D4] Original-source/guest-memory/ABI staging failed. NO XDK"
}
$meta=Get-Content -LiteralPath $targetManifest -Encoding UTF8 -Raw|ConvertFrom-Json
if($meta.marker -ne "XPP-D52D4-NATIVE-CAPABILITIES-20261031" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   $meta.hardware_target -ne "0x002D52D4" -or
   [int]$meta.hardware_ticks -ne 27107602 -or
   $meta.original_function_sha256 -ne "80aa0150e3d680d11925e2b2c3465509930b557fc511f625bafbbdea39e09ed5" -or
   $meta.source_return -ne "EAX/ESP_PLUS_12_RET8" -or
   [int]$meta.native_capability_buffer_bytes -ne 28 -or
   $meta.native_struct_memcpy -ne $false -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[XPP-D52D4] Retail source/ABI/guest buffer or hard fence manifest drift"
}
$files=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File)
if($files.Count -ne 64){throw "[XPP-D52D4] Expected inherited 64 TrueTUs"}
$oldHeader=Join-Path $shards "translated_runtime.h"
$newHeader=Join-Path $targetShards "translated_runtime.h"
if((Get-FileHash $oldHeader -Algorithm SHA256).Hash -ne
   (Get-FileHash $newHeader -Algorithm SHA256).Hash){
    throw "[XPP-D52D4] Shared runtime header changed; fail closed"
}
$native=@($files | Select-String -Pattern "XPP-D52D4-NATIVE-CAPABILITIES-20261031" -List)
$entry=@($files | Select-String -Pattern "XPP D52D4 ENTRY" -List)
$prior=@($files | Select-String -Pattern "XPP D5272 ENTRY" -List)
$changes=@($files | Select-String -Pattern "XPP 002D559B ENTRY" -List)
if($native.Count -ne 1 -or $entry.Count -ne 1 -or
   $prior.Count -ne 1 -or $changes.Count -ne 1){
    throw "[XPP-D52D4] New entry/bridge or preceding controller chain not unique"
}
$bridge=Get-Content -LiteralPath $native[0].Path -Raw -Encoding UTF8
if($bridge -notmatch 'XInputGetCapabilities\(\(DWORD\)port,0u,&caps\)' -or
   $bridge -notmatch 'GUEST_WRITE32\(capabilities_address\+i,0u\)' -or
   $bridge -notmatch 'GUEST_WRITE32\(capabilities_address,first\)'){
    throw "[XPP-D52D4] Invalid native capability query/output ABI"
}
$changed=@($meta.changed_true_tus)
if($changed.Count -lt 1 -or $changed.Count -gt 12){
    throw "[XPP-D52D4] Unexpected rebuild fanout"
}
foreach($file in $changed){
    $real=(Get-FileHash (Join-Path $targetShards $file) -Algorithm SHA256).Hash
    $expect=$meta.new_owner_hashes.PSObject.Properties[$file].Value
    if($real -ne $expect){throw "[XPP-D52D4] Changed TrueTU SHA mismatch: $file"}
}
Write-Host "[XPP-D52D4] PREFLIGHT PASS: original 472-byte XPP function EAX/ret8 and native buffer"
Write-Host "[XPP-D52D4] Native real controller status, 28 guest bytes, no native struct copy"
Write-Host "[XPP-D52D4] Original D5272, D559B/D5579, K1S and MMIO/VP fences preserved"
Write-Host ("[XPP-D52D4] Incremental changed TUs: "+($changed -join ", "))
if($PreflightOnly){
    Write-Host "[XPP-D52D4] PREFLIGHT ONLY - no XDK build and no Xbox run"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildRoot|Out-Null
$buildArgs=@{
    GeneratedMain=$targetMain
    GeneratedEnv=$envSource
    GeneratedShardDir=$targetShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildRoot "xdk-clean.log")
    BuildLog=(Join-Path $buildRoot "xdk-build.log")
    PublishedXex=$published
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[XPP-D52D4] One VS2017 Xbox 360 incremental Release build: SKIP CLEAN"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[XPP-D52D4] XDK build failed; see xdk-build.log"}
if(-not(Test-Path -LiteralPath $published -PathType Leaf)){
    throw "[XPP-D52D4] XEX missing after build"
}
Write-Host "[XPP-D52D4] BUILD PASS: $published"
Write-Host "[XPP-D52D4] Xbox witness: XPP D52D4 ENTRY, XINPUT capabilities status, next hard frontier"
Write-Host "[XPP-D52D4] Real display_calls and framebuffer only; never force a present"
