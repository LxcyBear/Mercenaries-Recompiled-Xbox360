[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
# Windows PowerShell 5.1; ASCII-only, no read-only $Host variable.
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$old=Join-Path $repo "build\phase6_integration_map\xpp_d5574_batch"
$new=Join-Path $repo "build\phase6_integration_map\xpp_d559b_batch"
$shards=Join-Path $old "translated_shards"
$parentMain=Join-Path $old "main.cpp"
$parentManifest=Join-Path $old "xpp-d5574-batch-manifest.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$stage=Join-Path $PSScriptRoot "Stage-XppD559B.py"
$test=Join-Path $PSScriptRoot "Test-XppD559B.py"
$targetShards=Join-Path $new "translated_shards"
$targetMain=Join-Path $new "main.cpp"
$targetManifest=Join-Path $new "xpp-d559b-batch-manifest.json"
$buildRoot=Join-Path $new "xdk"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$generatedEnv=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xex=Join-Path $buildRoot "Merc-XPP-D559B.xex"
foreach($file in @($parentManifest,$parentMain,$functions,$emitter,$stage,$test,$builder,$generatedEnv)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[XPP-D559B] Required known-good file missing: $file"
    }
}
foreach($folder in @($shards,$generated)){
    if(-not(Test-Path -LiteralPath $folder -PathType Container)){
        throw "[XPP-D559B] Original generated directory missing: $folder"
    }
}
$python=(Get-Command python -ErrorAction Stop).Source
Write-Host "[XPP-D559B] =================================================="
Write-Host "[XPP-D559B]   NEXT ORIGINAL XPP CONTROLLER FRONTIER"
Write-Host "[XPP-D559B] =================================================="
Write-Host "[XPP-D559B] Hardware: D5574 passed; native port-0 controller; D559B at 27,107,590 ticks"
Write-Host "[XPP-D559B] Original XPP D559B GetDeviceChanges, D5579 GetDevices"
Write-Host "[XPP-D559B] Python syntax and synthetic source guards (NO XDK)"
& $python -m py_compile $stage $test
if($LASTEXITCODE -ne 0){throw "[XPP-D559B] Python syntax gate failed"}
& $python -u $test
if($LASTEXITCODE -ne 0){throw "[XPP-D559B] Synthetic regression test failed"}
$stageArgs=@("--shards",$shards,"--parent-manifest",$parentManifest,
    "--parent-main",$parentMain,"--generated",$generated,"--functions",$functions,
    "--emitter",$emitter,"--out",$targetShards,"--out-main",$targetMain,
    "--manifest",$targetManifest)
& $python -u $stage @stageArgs
if($LASTEXITCODE -ne 0){throw "[XPP-D559B] Original source/ABI proof refused XDK"}
$meta=Get-Content -LiteralPath $targetManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($meta.marker -ne "XPP-D559B-DEVICE-CHANGES-20261030" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   [int]$meta.hardware_seed_ticks -ne 27107590 -or
   $meta.hardware_target -ne "0x002D559B" -or
   $meta.native_input_backend -ne "XPP-D559B-NATIVE-DEVICE-CHANGES-20261030" -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[XPP-D559B] Unexpected source provenance/hard-fence gate"
}
$all=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File)
if($all.Count -ne 64){throw "[XPP-D559B] Expected 64 TrueTUs"}
if((Get-FileHash (Join-Path $shards "translated_runtime.h") -Algorithm SHA256).Hash -ne
   (Get-FileHash (Join-Path $targetShards "translated_runtime.h") -Algorithm SHA256).Hash){
    throw "[XPP-D559B] Shared runtime header changed - no incremental build"
}
$entries=@($all|Select-String -Pattern "XPP 002D559B ENTRY" -List)
$native=@($all|Select-String -Pattern "XPP-D559B-NATIVE-DEVICE-CHANGES-20261030" -List)
$prior=@($all|Select-String -Pattern "XPP D5574 ENTRY" -List)
if($entries.Count -ne 1 -or $native.Count -ne 1 -or $prior.Count -ne 1){
    throw "[XPP-D559B] Controller entry/native backend or working init missing/duplicated"
}
$nativeCode=Get-Content -LiteralPath $native[0].Path -Raw -Encoding UTF8
if($nativeCode -notmatch 'XInputGetState\(' -or
   $nativeCode -notmatch 'GUEST_WRITE32\(insertions_address,inserted\)' -or
   $nativeCode -notmatch 'GUEST_WRITE32\(removals_address,removed\)' -or
   $nativeCode -notmatch 'xpp_native_previous_device_mask=current'){
    throw "[XPP-D559B] Native four-port scan/state/fenced guest outputs not proven"
}
$changed=@($meta.changed_true_tus)
if($changed.Count -lt 1 -or $changed.Count -gt 12){
    throw "[XPP-D559B] Incremental TU footprint exceeds bound"
}
foreach($filename in $changed){
    $actual=(Get-FileHash (Join-Path $targetShards $filename) -Algorithm SHA256).Hash
    $expected=$meta.new_owner_hashes.PSObject.Properties[$filename].Value
    if($actual -ne $expected){
        throw "[XPP-D559B] Modified TrueTU SHA mismatch: $filename"
    }
}
Write-Host "[XPP-D559B] PREFLIGHT PASS: exact original EAX, ESP+16 and ESP+8"
Write-Host "[XPP-D559B] REAL XINPUT: persisted port masks, bounded GUEST_WRITE32"
Write-Host "[XPP-D559B] Preserved D5574, K1S, A3A5A, MMIO and VP fences"
Write-Host "[XPP-D559B] Changed TrueTUs: $($changed -join ', ')"
if($PreflightOnly){
    Write-Host "[XPP-D559B] PREFLIGHT ONLY - NO XDK BUILD"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildRoot|Out-Null
$buildArgs=@{
    GeneratedMain=$targetMain
    GeneratedEnv=$generatedEnv
    GeneratedShardDir=$targetShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildRoot "xdk-clean.log")
    BuildLog=(Join-Path $buildRoot "xdk-build.log")
    PublishedXex=$xex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[XPP-D559B] BUILD: VS2017 Release Xbox 360, incremental SKIP CLEAN"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[XPP-D559B] XDK failed; inspect xdk-build.log"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[XPP-D559B] Published XEX missing after XDK build"
}
Write-Host "[XPP-D559B] XDK BUILD PASS: $xex"
Write-Host "[XPP-D559B] Xbox proof: D559B ENTRY, real mask changes and next guest frontier"
Write-Host "[XPP-D559B] Guest display call must be real, never synthesized"
