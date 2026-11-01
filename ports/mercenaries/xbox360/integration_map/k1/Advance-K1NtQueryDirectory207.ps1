[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. DEFAULT = NO XDK. Explicit -Build = one
# incremental diagnostic XEX that preserves original ordinal207 hard stop.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$old=Join-Path $repo "build\phase6_integration_map\xpp_input_family_batch"
$new=Join-Path $repo "build\phase6_integration_map\k1_ntquerydirectory207"
$parentShards=Join-Path $old "translated_shards"
$parentMain=Join-Path $old "main.cpp"
$parentManifest=Join-Path $old "xpp-input-family-manifest.json"
$outShards=Join-Path $new "translated_shards"
$outMain=Join-Path $new "main.cpp"
$outManifest=Join-Path $new "k1_ntquerydirectory207_manifest.json"
$stage=Join-Path $PSScriptRoot "Stage-K1NtQueryDirectory207Frame.py"
$prior=Join-Path $PSScriptRoot "Advance-XppInputFamily.ps1"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk=Join-Path $new "xdk"
$xex=Join-Path $xdk "Merc-K1NT207-FrameProbe.xex"

Write-Host "[K1NT207] ==================================================="
Write-Host "[K1NT207] RETAIL ORDINAL 207 NtQueryDirectoryFile FRAME WITNESS"
Write-Host "[K1NT207] ==================================================="
Write-Host "[K1NT207] Last Xbox: ICALL_SAFE -> 800000CF tick=27,108,191, caller=0023A3CE"
Write-Host "[K1NT207] Open directory: game:\dataxbox\ virtual token=48000001"
Write-Host "[K1NT207] Probe original 10-dword guest argument frame; NEVER fabricate success."
if($Build){Write-Host "[K1NT207] EXPLICIT INCREMENTAL XDK BUILD requested"}
else{Write-Host "[K1NT207] PREFLIGHT ONLY, NO XDK"}
foreach($f in @($stage,$prior,$builder,$envSource)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[K1NT207] Missing required file: $f"
    }
}
$python=(Get-Command python -ErrorAction Stop).Source
$priorArgs=@("-NoProfile","-ExecutionPolicy","Bypass","-File",$prior,
             "-SolutionRoot",$SolutionRoot,"-FastBuildRoot",$FastBuildRoot)
& powershell.exe @priorArgs
if($LASTEXITCODE -ne 0){
    throw "[K1NT207] Input family stage drift; refusing ordinal 207 probe"
}
foreach($f in @($parentMain,$parentManifest)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[K1NT207] Missing parent stage file: $f"
    }
}
if(-not(Test-Path -LiteralPath $parentShards -PathType Container)){
    throw "[K1NT207] Missing 64-TU parent directory"
}
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1NT207] Syntax preflight failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1NT207] Anti-fabrication tests failed"}
$stageArgs=@(
    "--parent-main",$parentMain,
    "--parent-manifest",$parentManifest,
    "--parent-shards",$parentShards,
    "--out-main",$outMain,
    "--out-shards",$outShards,
    "--manifest",$outManifest
)
& $python -u $stage @stageArgs
if($LASTEXITCODE -ne 0){throw "[K1NT207] Frame probe stage failed. NO XDK"}

$meta=Get-Content -LiteralPath $outManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($meta.marker -ne "K1NT207-DIRECTORY-FRAME-WITNESS-20261101" -or
   $meta.status -ne "FRAME_PROBE_STAGED_HARD_STOP_PRESERVED_NO_XDK" -or
   [int]$meta.retail_ordinal -ne 207 -or
   $meta.kernel_call_target -ne "0x800000CF" -or
   [int]$meta.expected_saved_esp_delta -ne 44 -or
   $meta.native_directory_service -ne $false -or
   $meta.hard_stop_preserved -ne $true -or
   $meta.guest_registers_modified -ne $false -or
   $meta.guest_memory_written -ne $false -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[K1NT207] Unsafe or unexpected manifest change"
}
$hash=(Get-FileHash -LiteralPath $outMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($hash -ne $meta.new_main_sha256){
    throw "[K1NT207] Staged host main SHA mismatch"
}
$src=Get-Content -LiteralPath $outMain -Raw -Encoding UTF8
if($src -notmatch "K1NT207 FRAME CAPTURED" -or
   $src -notmatch "K1NT207 PROBE ONLY" -or
   $src -notmatch "P6DQ ROCKET HARD STOP"){
    throw "[K1NT207] Expected runtime witness or original hard stop absent"
}
$files=@(Get-ChildItem -LiteralPath $outShards -File -Filter "translated_???.cpp")
if($files.Count -ne 64){throw "[K1NT207] Expected 64 unchanged TrueTUs"}
foreach($f in $files){
    $original=Join-Path $parentShards $f.Name
    if((Get-FileHash $original -Algorithm SHA256).Hash -ne
       (Get-FileHash $f.FullName -Algorithm SHA256).Hash){
        throw "[K1NT207] Unexpected TrueTU mutation: $($f.Name)"
    }
}
Write-Host "[K1NT207] PREFLIGHT PASS. Exactly main.cpp gains a frame-only witness."
Write-Host "[K1NT207] Original 64 TrueTUs, guest registers, MMIO/VP gates unchanged."
Write-Host "[K1NT207] Manifest: $outManifest"
if(-not $Build){
    Write-Host "[K1NT207] NO XDK BUILD. To capture LIVE argument words, rerun -Build."
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
Write-Host "[K1NT207] One VS2017 Xbox 360 incremental Release diagnostic build; no clean"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1NT207] XDK build failed: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1NT207] Build succeeded but diagnostic XEX missing"
}
Write-Host "[K1NT207] BUILD PASS: $xex"
Write-Host "[K1NT207] Xbox expected to stop at SAME ordinal 207 with detailed frame."
Write-Host "[K1NT207] Send the K1NT207 FRAME lines + boundary metadata from Watson."
Write-Host "[K1NT207] ABI capture, NOT native enumeration or graphics PASS."
