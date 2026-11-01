[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. Default = SOURCE/ABI PREFLIGHT ONLY (NO XDK).
# Explicit -Build compiles one combined native GetState/Close/SetState XEX.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$parent=Join-Path $repo "build\phase6_integration_map\xpp_d54ac_batch"
$batch=Join-Path $repo "build\phase6_integration_map\xpp_input_family_batch"
$shards=Join-Path $parent "translated_shards"
$parentMain=Join-Path $parent "main.cpp"
$parentManifest=Join-Path $parent "xpp-d54ac-batch-manifest.json"
$outShards=Join-Path $batch "translated_shards"
$outMain=Join-Path $batch "main.cpp"
$outManifest=Join-Path $batch "xpp-input-family-manifest.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$stage=Join-Path $PSScriptRoot "Stage-XppInputFamily.py"
$previous=Join-Path $PSScriptRoot "Advance-XppD54AC.ps1"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk=Join-Path $batch "xdk"
$xex=Join-Path $xdk "Merc-XPP-InputFamily.xex"

Write-Host "[XPP-FAMILY] =================================================="
Write-Host "[XPP-FAMILY] ONE-BUILD XPP INPUT FAMILY (D54AC + D551F + D52C8)"
Write-Host "[XPP-FAMILY] =================================================="
Write-Host "[XPP-FAMILY] Hardware proven only through D52D4; next D54AC tick 27,107,620"
if($Build){
    Write-Host "[XPP-FAMILY] EXPLICIT INCREMENTAL XDK BUILD REQUESTED"
}else{
    Write-Host "[XPP-FAMILY] PREFLIGHT ONLY / NO XDK"
}
foreach($f in @($previous,$stage,$builder,$emitter,$functions,$envSource)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[XPP-FAMILY] Missing required source/build dependency: $f"
    }
}
if(-not(Test-Path -LiteralPath $generated -PathType Container)){
    throw "[XPP-FAMILY] Missing original generated C corpus: $generated"
}
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[XPP-FAMILY] Revalidate exact inherited D54AC GetState ABI (NO XDK)"
$prevArgs=@("-NoProfile","-ExecutionPolicy","Bypass","-File",$previous,
            "-PreflightOnly","-SolutionRoot",$SolutionRoot,"-FastBuildRoot",$FastBuildRoot)
& powershell.exe @prevArgs
if($LASTEXITCODE -ne 0){throw "[XPP-FAMILY] D54AC parent preflight failed; NO XDK"}
foreach($f in @($parentMain,$parentManifest)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[XPP-FAMILY] Missing verified D54AC parent: $f"
    }
}
if(-not(Test-Path -LiteralPath $shards -PathType Container)){
    throw "[XPP-FAMILY] Missing 64-TU parent"
}
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[XPP-FAMILY] Python compile failed; NO XDK"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[XPP-FAMILY] Synthetic ABI test failed; NO XDK"}
$stageArgs=@(
    "--shards",$shards,
    "--parent-main",$parentMain,
    "--parent-manifest",$parentManifest,
    "--generated",$generated,
    "--functions",$functions,
    "--emitter",$emitter,
    "--out",$outShards,
    "--out-main",$outMain,
    "--manifest",$outManifest
)
& $python -u $stage @stageArgs
if($LASTEXITCODE -ne 0){throw "[XPP-FAMILY] Original source/ABI stage failed. NO XDK"}

$meta=Get-Content -LiteralPath $outManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($meta.marker -ne "K1-XPP-INPUT-FAMILY-ONE-BUILD-20261031" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   [int]$meta.translated_shards -ne 64 -or
   [int]$meta.native_feedback_bytes -ne 70 -or
   $meta.native_close_noop -ne $true -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[XPP-FAMILY] Manifest/guest feedback/hard fence drift"
}
$changes=@($meta.changed_true_tus)
$expected=@("translated_005.cpp","translated_027.cpp",[string]$meta.parent_input_owner)
$diff=@(Compare-Object -ReferenceObject ($changes|Sort-Object) -DifferenceObject ($expected|Sort-Object))
if($changes.Count -ne 3 -or $diff.Count -ne 0){
    throw "[XPP-FAMILY] Expected only two caller TrueTUs + original native input owner"
}
$all=@(Get-ChildItem -LiteralPath $outShards -Filter "translated_???.cpp" -File)
if($all.Count -ne 64){throw "[XPP-FAMILY] Expected exactly 64 compiled TrueTU sources"}
if((Get-FileHash (Join-Path $shards "translated_runtime.h") -Algorithm SHA256).Hash -ne
   (Get-FileHash (Join-Path $outShards "translated_runtime.h") -Algorithm SHA256).Hash){
    throw "[XPP-FAMILY] Shared runtime header unexpectedly changed"
}
foreach($name in $changes){
    $actual=(Get-FileHash (Join-Path $outShards $name) -Algorithm SHA256).Hash.ToLowerInvariant()
    $want=[string]$meta.new_owner_hashes.PSObject.Properties[$name].Value
    if($actual -ne $want){throw "[XPP-FAMILY] Output shard SHA drift: $name"}
}
$ownerText=Get-Content -LiteralPath (Join-Path $outShards $meta.parent_input_owner) -Raw -Encoding UTF8
if($ownerText -notmatch "XPP D52C8 ENTRY" -or
   $ownerText -notmatch "XPP D551F ENTRY" -or
   $ownerText -notmatch "XPP D54AC ENTRY" -or
   $ownerText -notmatch "XInputSetState\(\(DWORD\)port,&vibration\)" -or
   $ownerText -notmatch "GUEST_READ16\(feedback_address\+0x42u\)" -or
   $ownerText -notmatch "GUEST_READ16\(feedback_address\+0x44u\)"){
    throw "[XPP-FAMILY] Native controller call, guest feedback or entry markers missing"
}
Write-Host "[XPP-FAMILY] PREFLIGHT PASS: original retail Close/SetState wrappers, unchanged parent GetState"
Write-Host ("[XPP-FAMILY] Incremental changed TrueTUs: "+($changes -join ", "))
Write-Host "[XPP-FAMILY] No synthetic Swap, forced frame counter, extra MMIO or VP relaxations."
Write-Host "[XPP-FAMILY] Manifest: $outManifest"
if(-not $Build){
    Write-Host "[XPP-FAMILY] NO XDK BUILD. To compile after reviewing PASS, rerun with -Build."
    exit 0
}

New-Item -ItemType Directory -Force -Path $xdk|Out-Null
$buildArgs=@{
    GeneratedMain=$outMain
    GeneratedEnv=$envSource
    GeneratedShardDir=$outShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $xdk "xdk-clean.log")
    BuildLog=(Join-Path $xdk "xdk-build.log")
    PublishedXex=$xex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[XPP-FAMILY] ONE VS2017 Xbox 360 Release build; SKIP CLEAN"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[XPP-FAMILY] XDK build failed: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[XPP-FAMILY] XDK returned but combined XEX missing"
}
Write-Host "[XPP-FAMILY] BUILD PASS: $xex"
Write-Host "[XPP-FAMILY] Hardware proof required: GetState ENTRY/status, actual next frontier,"
Write-Host "[XPP-FAMILY] Close/SetState if reached, real D3D/Swap and display counters."
Write-Host "[XPP-FAMILY] XEX NOT automatically deployed; stage is not hardware proof."
