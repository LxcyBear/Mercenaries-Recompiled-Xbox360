[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [int]$MaxNewFunctions=24,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$base=Join-Path $repo "build\phase6_integration_map\pixel_a3a5a_batch"
$shards=Join-Path $base "translated_shards"
$main=Join-Path $base "main.cpp"
$baselineManifest=Join-Path $base "pixel-a3a5a-batch-manifest.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$target=Join-Path $repo "build\phase6_integration_map\xpp_d5574_batch"
$targetShards=Join-Path $target "translated_shards"
$targetMain=Join-Path $target "main.cpp"
$report=Join-Path $target "xpp_d5574_source_audit.txt"
$manifest=Join-Path $target "xpp-d5574-batch-manifest.json"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$env=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$stage=Join-Path $PSScriptRoot "Stage-XppD5574.py"
$test=Join-Path $PSScriptRoot "Test-XppD5574.py"
$output=Join-Path $target "xdk\Merc-XPP-D5574.xex"
foreach($path in @($main,$baselineManifest,$functions,$emitter,$builder,$env,$stage,$test)){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[XPP] Missing existing PIXEL / tool source: $path"
    }
}
foreach($folder in @($shards,$generated)){
    if(-not(Test-Path -LiteralPath $folder -PathType Container)){
        throw "[XPP] Missing original local generated source: $folder"
    }
}
if($MaxNewFunctions -lt 1 -or $MaxNewFunctions -gt 32){
    throw "[XPP] MaxNewFunctions must be between 1 and 32"
}
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[XPP] ======================================================="
Write-Host "[XPP]   POST-PIXEL ORIGINAL XPP DIRECT FRONTIER 002D5574"
Write-Host "[XPP] ======================================================="
Write-Host "[XPP] Hardware seed: 27,107,567 ticks; DIRECT 0023A3CE -> 002D5574; fault=0"
Write-Host "[XPP] Preserve successful 002A3A5A and original K1S stack fix"
Write-Host "[XPP] Offline syntax and direct-call/TrueTU ABI tests (NO XDK)"
& $python -m py_compile $stage $test
if($LASTEXITCODE -ne 0){throw "[XPP] Python syntax gate refused XDK"}
& $python -u $test
if($LASTEXITCODE -ne 0){throw "[XPP] XPP staging tests refused XDK"}
New-Item -ItemType Directory -Force -Path $target | Out-Null
$args1=@("--shards",$shards,
    "--manifest",$baselineManifest,
    "--main",$main,
    "--generated-root",$generated,
    "--functions",$functions,
    "--emitter",$emitter,
    "--out",$targetShards,
    "--out-main",$targetMain,
    "--report",$report,
    "--max-new",$MaxNewFunctions)
Write-Host "[XPP] Scan REAL ORIGINAL local XPP functions, direct-call closure and shared helper ABI"
& $python -u $stage @args1
if($LASTEXITCODE -ne 0){
    if(Test-Path -LiteralPath $report -PathType Leaf){
        Write-Host "[XPP] SOURCE AUDIT REQUIRES REVIEW (first 85 lines; includes original signature):"
        Get-Content -LiteralPath $report -Encoding UTF8 -TotalCount 85
        Write-Host "[XPP] Upload this local audit report: $report"
    }
    throw "[XPP] Source closure/ABI not proven, so NO XDK build was attempted"
}
if(-not(Test-Path -LiteralPath $manifest -PathType Leaf)){
    throw "[XPP] Expected source-staging manifest missing"
}
$meta=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8|ConvertFrom-Json
if($meta.marker -ne "XPP-D5574-DIRECT-CLOSURE-20261030" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   $meta.hardware_target -ne "0x002D5574" -or
   [int]$meta.previous_ticks -ne 27107567 -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED" -or
   $meta.guest_display_calls_injected -ne $false){
    throw "[XPP] Safety/identity proof manifest does not match this hardware result"
}
$sourceManifest=Get-Content -LiteralPath $baselineManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($sourceManifest.marker -ne "PIXEL-A3A5A-DIRECT-APU-20261030" -or
   [int]$sourceManifest.translated_shards -ne 64 -or
   $sourceManifest.preserved_k1s_esi_fix -ne $true -or
   $sourceManifest.mmio_fences -ne "UNCHANGED"){
    throw "[XPP] Previous successful PIXEL/64-TU baseline changed"
}
$trueTUs=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File)
if($trueTUs.Count -ne 64){
    throw "[XPP] TrueTU count drifted from 64"
}
if((Get-FileHash (Join-Path $shards "translated_runtime.h") -Algorithm SHA256).Hash -ne
   (Get-FileHash (Join-Path $targetShards "translated_runtime.h") -Algorithm SHA256).Hash){
    throw "[XPP] Runtime header changed (would force full rebuild)"
}
$modified=@($meta.modified_true_tus)
if($modified.Count -lt 1 -or $modified.Count -gt 12){
    throw "[XPP] Unexpectedly broad compile change footprint"
}
$bodyMatches=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File |
    Select-String -Pattern "XPP D5574 ENTRY" -List)
if($bodyMatches.Count -ne 1){
    throw "[XPP] Genuine XPP function entry marker not unique"
}
if($meta.native_xinput_init -ne "XINPUTGETSTATE_4PORTS_REAL_HARDWARE" -or
   $meta.native_xinput_bridge_marker -ne "XPP-D5574-NATIVE-XINPUT-INIT-20261030"){
    throw "[XPP] No verified real Xbox 360 XInput initializer was staged"
}
$nativeOwners=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File |
    Select-String -Pattern "XPP-D5574-NATIVE-XINPUT-INIT-20261030" -List)
if($nativeOwners.Count -ne 1){
    throw "[XPP] Native XInput initializer missing or duplicated across TrueTUs"
}
$nativeSource=Get-Content -LiteralPath $nativeOwners[0].Path -Raw -Encoding UTF8
if($nativeSource -notmatch 'XInputGetState\s*\(' -or
   $nativeSource -notmatch 'for \(port=0u; port<4u; \+\+port\)' -or
   $nativeSource -notmatch 'connected_mask\|=\(1u<<port\)'){
    throw "[XPP] Native XInput bridge was not a four-port hardware query"
}
Write-Host "[XPP] NATIVE XINPUT PROOF: real 4-port XInputGetState scan, original ESP+12 unchanged"
$oldHost=Get-Content -LiteralPath $main -Raw -Encoding UTF8
$newHost=Get-Content -LiteralPath $targetMain -Raw -Encoding UTF8
if($newHost -notmatch "P6DQ-R51-MM173-FRAME-20261029-A" -or
   ([regex]::Matches($newHost,"case 0x002D5574u:")).Count -ne
   ([regex]::Matches($oldHost,"case 0x002D5574u:")).Count){
    throw "[XPP] Original host lookup/dispatch not preserved"
}
Write-Host "[XPP] PREFLIGHT PASS: original XPP function + dependent source-closed XPP functions"
Write-Host ("[XPP] New original functions: "+(@($meta.new_guest_bodies) -join ", "))
Write-Host ("[XPP] Changed TrueTUs: "+($modified -join ", "))
Write-Host "[XPP] K1S, 64 TUs, A3A5A audio initialization and MMIO/VP fences preserved"
Write-Host "[XPP] Original guest display_calls is still 0, no fabricated pixels"
Write-Host "[XPP] Source/ABI report: $report"
if($PreflightOnly){
    Write-Host "[XPP] PREFLIGHT ONLY - no Xbox build"
    exit 0
}
$buildFolder=Join-Path $target "xdk"
New-Item -ItemType Directory -Force -Path $buildFolder | Out-Null
$buildArgs=@{
    GeneratedMain=$targetMain
    GeneratedEnv=$env
    GeneratedShardDir=$targetShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildFolder "xdk-clean.log")
    BuildLog=(Join-Path $buildFolder "xdk-build.log")
    PublishedXex=$output
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[XPP] Incremental VS2017 Release Xbox 360 build - SKIP CLEAN"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[XPP] Xbox compiler/linker failed; see xdk-build.log"}
if(-not(Test-Path -LiteralPath $output -PathType Leaf)){
    throw "[XPP] Expected compiled XEX not found: $output"
}
Write-Host "[XPP] XEX BUILD PASS: $output"
Write-Host "[XPP] Xbox: watch for XPP D5574 ENTRY, next original direct/indirect stop,"
Write-Host "[XPP] ticks > 27107567, genuine display_calls >= 1, and nonzero framebuffer"
