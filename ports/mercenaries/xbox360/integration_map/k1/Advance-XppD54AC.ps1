[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. Exact 22-byte ORIGINAL XBOX XInputGetState.
# -PreflightOnly never builds an XEX and never communicates with the Xbox.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$old=Join-Path $repo "build\phase6_integration_map\xpp_d52d4_batch"
$new=Join-Path $repo "build\phase6_integration_map\xpp_d54ac_batch"
$shards=Join-Path $old "translated_shards"
$parentMain=Join-Path $old "main.cpp"
$parentManifest=Join-Path $old "xpp-d52d4-batch-manifest.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$stage=Join-Path $PSScriptRoot "Stage-XppD54AC.py"
$targetShards=Join-Path $new "translated_shards"
$targetMain=Join-Path $new "main.cpp"
$targetManifest=Join-Path $new "xpp-d54ac-batch-manifest.json"
$privateOriginal=Join-Path $new "xpp_d54ac_original_source_LOCAL_ONLY.txt"
$buildRoot=Join-Path $new "xdk"
$published=Join-Path $buildRoot "Merc-XPP-D54AC.xex"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
foreach($file in @($parentMain,$parentManifest,$functions,$emitter,$stage,$builder,$envSource)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[XPP-D54AC] Missing original source/stage prerequisite: $file"
    }
}
foreach($dir in @($shards,$generated)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "[XPP-D54AC] Missing original 64-TU or generated corpus: $dir"
    }
}
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[XPP-D54AC] =================================================="
Write-Host "[XPP-D54AC] ORIGINAL XINPUTGETSTATE - REAL NATIVE FRONTIER"
Write-Host "[XPP-D54AC] =================================================="
Write-Host "[XPP-D54AC] Hardware: D52D4 native GetCapabilities success; next direct=002D54AC at tick=27,107,620"
Write-Host "[XPP-D54AC] Original Xbox XINPUT_STATE = EXACT 22 bytes (not native Xbox360 XInput size)"
Write-Host "[XPP-D54AC] Native real XInputGetState, original analog-button/axis mapping, EAX/RET8 source-guarded"
Write-Host "[XPP-D54AC] No forced input, display, or unknown MMIO/VP relaxation"
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[XPP-D54AC] Python syntax refused XDK build"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[XPP-D54AC] Synthetic source/ABI validation refused XDK build"}
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
    Write-Host "[XPP-D54AC] Original source (PRIVATE) available at: $privateOriginal"
    throw "[XPP-D54AC] Original-source/ABI/guest-buffer staging failed. NO XDK"
}
$meta=Get-Content -LiteralPath $targetManifest -Encoding UTF8 -Raw|ConvertFrom-Json
if($meta.marker -ne "XPP-D54AC-NATIVE-GETSTATE-20261031" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   $meta.hardware_target -ne "0x002D54AC" -or
   [int]$meta.hardware_ticks -ne 27107620 -or
   $meta.original_function_sha256 -ne "48e4ccc7ccc0ae3bfa852d584996f6f1ed034d0491f05433722054038f42a0e2" -or
   $meta.source_return -ne "EAX/ESP_PLUS_12_RET8" -or
   [int]$meta.native_state_buffer_bytes -ne 22 -or
   $meta.native_struct_memcpy -ne $false -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[XPP-D54AC] Original source/ABI/22B guest state or safety manifest drift"
}
$all=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File)
if($all.Count -ne 64){throw "[XPP-D54AC] Expected 64 TrueTUs"}
$oldHeader=Join-Path $shards "translated_runtime.h"
$newHeader=Join-Path $targetShards "translated_runtime.h"
if((Get-FileHash $oldHeader -Algorithm SHA256).Hash -ne
   (Get-FileHash $newHeader -Algorithm SHA256).Hash){
    throw "[XPP-D54AC] Shared runtime header changed; refuse build"
}
$newEntry=@($all|Select-String -Pattern "XPP D54AC ENTRY" -List)
$newNative=@($all|Select-String -Pattern "XPP-D54AC-NATIVE-GETSTATE-20261031" -List)
$priorCapabilities=@($all|Select-String -Pattern "XPP D52D4 ENTRY" -List)
$priorOpen=@($all|Select-String -Pattern "XPP D5272 ENTRY" -List)
$priorChanges=@($all|Select-String -Pattern "XPP 002D559B ENTRY" -List)
if($newEntry.Count -ne 1 -or $newNative.Count -ne 1 -or
   $priorCapabilities.Count -ne 1 -or $priorOpen.Count -ne 1 -or
   $priorChanges.Count -ne 1){
    throw "[XPP-D54AC] New GetState or inherited controller chain not unique"
}
$nativeText=Get-Content -LiteralPath $newNative[0].Path -Raw -Encoding UTF8
if($nativeText -notmatch 'XInputGetState\(\(DWORD\)port,&native\)' -or
   $nativeText -notmatch 'GUEST_WRITE16\(state_address\+20u,' -or
   $nativeText -notmatch 'state_address<=0x04000000u-22u'){
    throw "[XPP-D54AC] Native hardware call or EXACT 22B state boundary not proved"
}
$changed=@($meta.changed_true_tus)
if($changed.Count -lt 1 -or $changed.Count -gt 12){
    throw "[XPP-D54AC] Changed TrueTU fanout exceeded bound"
}
foreach($file in $changed){
    $actual=(Get-FileHash (Join-Path $targetShards $file) -Algorithm SHA256).Hash
    $expect=$meta.new_owner_hashes.PSObject.Properties[$file].Value
    if($actual -ne $expect){throw "[XPP-D54AC] New TrueTU SHA mismatch: $file"}
}
Write-Host "[XPP-D54AC] PREFLIGHT PASS: exact original XInputGetState source/ABI/22B state"
Write-Host "[XPP-D54AC] Real native gamepad packet, digital+8 analog buttons, four signed axes"
Write-Host "[XPP-D54AC] Preserved native D52D4/D5272/D559B, original K1S, all MMIO/VP fences"
Write-Host ("[XPP-D54AC] Incremental changed TrueTUs: "+($changed -join ", "))
if($PreflightOnly){
    Write-Host "[XPP-D54AC] PREFLIGHT ONLY - NO XDK and NO Xbox run"
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
Write-Host "[XPP-D54AC] VS2017 Xbox 360 incremental Release build (SKIP CLEAN)"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[XPP-D54AC] XDK build failed; inspect xdk-build.log"}
if(-not(Test-Path -LiteralPath $published -PathType Leaf)){
    throw "[XPP-D54AC] Build success but XEX not published"
}
Write-Host "[XPP-D54AC] XDK BUILD PASS: $published"
Write-Host "[XPP-D54AC] Xbox test witness: XPP D54AC ENTRY, real XINPUT state and next direct frontier"
Write-Host "[XPP-D54AC] display_calls/framebuffer remain genuine-only, no forced pixels"
