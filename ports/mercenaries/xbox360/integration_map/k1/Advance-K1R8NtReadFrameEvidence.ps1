[CmdletBinding()]
param(
    [switch]$SourceOnly,
    [string]$XboxLog = "",
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# One controlled experimental XEX: existing retail r7 guest code plus
# a read-only NtReadFile 44-byte call-frame probe. NEVER accepts 44 as 36.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$tag="[K1-R8]"
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$python=(Get-Command python -ErrorAction Stop).Source
$stage=Join-Path $PSScriptRoot "Stage-K1R8NtReadFrameEvidence.py"
$r7=Join-Path $root "build\phase6_integration_map\k1_direct_222190_r7_fingerprinted"
$r7Main=Join-Path $r7 "main.cpp"
$r7Manifest=Join-Path $r7 "k1-direct-222190-r7-manifest.json"
$shards=Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$r8=Join-Path $root "build\phase6_integration_map\k1_ntread44_frame_evidence_r8"
$r8Main=Join-Path $r8 "main.cpp"
$r8Manifest=Join-Path $r8 "k1-r8-ntread44-frame-evidence-manifest.json"
$builder=Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envMain=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk=Join-Path $r8 "xdk"
$xex=Join-Path $xdk "Merc-K1-R8-NtRead44-EVIDENCE.xex"
$buildReport=Join-Path $r8 "k1-r8-build-evidence.json"
$traceReport=Join-Path $r8 "k1-r8-hardware-probe-log.txt"

function Get-K1R8Manifest {
    if(-not(Test-Path -LiteralPath $r8Manifest -PathType Leaf)){
        throw "$tag No source manifest available: $r8Manifest"
    }
    $m=Get-Content -LiteralPath $r8Manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if($m.status -ne "K1_R8_NTREAD44_ABI_EVIDENCE_ONLY_NO_44_BYTE_BYPASS" -or
       $m.original_retail_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
       $m.original_64_true_tus_unchanged -ne $true -or
       $m.r7_22190_original_guest_function_preserved -ne $true -or
       $m.r7_streaming_patch_279_retail_branch_preserved -ne $true -or
       $m.r8_ntread_44_byte_frame_handled -ne $false -or
       $m.r8_ntread_36_byte_normal_path_unchanged -ne $true -or
       $m.fenced_mismatched_frames -ne $true -or
       $m.no_guest_stack_adjustment -ne $true -or
       $m.no_unknown_abi_bridge -ne $true -or
       $m.no_fake_pixels -ne $true -or
       $m.frame_evidence.capture_words -ne 11 -or
       $m.frame_evidence.guard_delta -ne 44 -or
       $m.frame_evidence.canonical_delta -ne 36 -or
       $m.frame_evidence.existing_kernel_frame_fence_untouched -ne $true -or
       -not ([string]$m.new_r8_hardware_fingerprint).StartsWith("K1-R8-NTREAD-44-PROOF-") -or
       $m.runtime_fingerprint_location -ne "P6DQ ROCKET HARD STOP kind= runtime format"){
        throw "$tag Original r7/64 TrueTU/canonical 36-byte NtReadFile/hard-stop/evidence contract invalid"
    }
    return $m
}

if($XboxLog){
    if(-not(Test-Path -LiteralPath $XboxLog -PathType Leaf)){
        throw "$tag Requested actual xbWatson log missing: $XboxLog"
    }
    $m=Get-K1R8Manifest
    $tagged=@(Select-String -LiteralPath $XboxLog -Pattern ([regex]::Escape([string]$m.new_r8_hardware_fingerprint)))
    if($tagged.Count -lt 1){
        throw "$tag WRONG XEX / NO R8 RUNTIME FINGERPRINT IN HARDWARE LOG"
    }
    $rawA=@(Select-String -LiteralPath $XboxLog -Pattern "K1-R8 NTREAD 44-RAW A:" -SimpleMatch)
    $rawB=@(Select-String -LiteralPath $XboxLog -Pattern "K1-R8 NTREAD 44-RAW B:" -SimpleMatch)
    $mismatch=@(Select-String -LiteralPath $XboxLog -Pattern "NtReadFile FRAME MISMATCH:" -SimpleMatch)
    $stop=@(Select-String -LiteralPath $XboxLog -Pattern "BOUNDARY: kind=KERNEL_FRAME" -SimpleMatch)
    @(
        "$tag HARDWARE FINGERPRINT CONFIRMED: $($m.new_r8_hardware_fingerprint)"
        "$tag 44-byte raw frames: A=$($rawA.Count) B=$($rawB.Count) retained_frame_fences=$($mismatch.Count)"
        "$tag NO 44-byte frame automatic bypass or guest stack adjustment"
    ) | Set-Content -LiteralPath $traceReport -Encoding UTF8
    $entries=@($rawA | Select-Object -Last 2)+@($rawB | Select-Object -Last 2)+@($mismatch | Select-Object -Last 2)+@($stop | Select-Object -Last 2)+@($tagged | Select-Object -Last 1)
    foreach($match in $entries){
        $line="$tag $($match.Line.Trim())"
        Write-Host $line
        Add-Content -LiteralPath $traceReport -Value $line -Encoding UTF8
    }
    if($rawA.Count -eq 0 -or $rawA.Count -ne $rawB.Count){
        Write-Warning "$tag No complete 44-byte evidence pair: NO ABI CONCLUSION"
    }
    Write-Host "$tag Hardware evidence report: $traceReport"
    return
}

foreach($file in @($stage,$r7Main,$r7Manifest)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "$tag Missing exact original r7 source/manifest: $file"
    }
}
if(-not(Test-Path -LiteralPath $shards -PathType Container)){
    throw "$tag Original 64 TrueTU directory absent"
}
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "$tag Python syntax gate failure; NO XDK."}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "$tag NtReadFile unchanged 36-byte + 44-frame evidence selftest failure; NO XDK."}
$stageArgs=@(
    "-u", $stage,
    "--parent",$r7Main,
    "--parent-manifest",$r7Manifest,
    "--shards",$shards,
    "--output",$r8Main,
    "--manifest",$r8Manifest
)
& $python @stageArgs
if($LASTEXITCODE -ne 0){throw "$tag Original r7 source or 44-byte evidence patch failed; NO XDK."}
$m=Get-K1R8Manifest
$mainSha=(Get-FileHash -LiteralPath $r8Main -Algorithm SHA256).Hash.ToLowerInvariant()
if($mainSha -ne $m.new_r8_main_sha256 -or
   $m.original_r7_main_sha256 -ne (Get-FileHash -LiteralPath $r7Main -Algorithm SHA256).Hash.ToLowerInvariant() -or
   -not (Select-String -LiteralPath $r8Main -Pattern ([regex]::Escape([string]$m.new_r8_hardware_fingerprint)) -Quiet)){
    throw "$tag Source SHA or hardware runtime fingerprint verification failed"
}
Write-Host "$tag R8 SOURCE PASS: original r7 plus read-only 44-byte NtReadFile raw frame probe"
Write-Host "$tag Native 36-byte NtReadFile unchanged. Unknown 44-byte ABI remains fenced."
Write-Host "$tag HARDWARE FINGERPRINT: $($m.new_r8_hardware_fingerprint)"
if($SourceOnly){
    Write-Host "$tag SOURCE ONLY, NO XDK AND NO NEW XEX."
    return
}

foreach($file in @($builder,$envMain)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "$tag Native Xbox 360 XDK builder/phase5 env absent: $file"
    }
}
New-Item -ItemType Directory -Path $xdk -Force | Out-Null
$argsForXdk=@{
    GeneratedMain=$r8Main
    GeneratedEnv=$envMain
    GeneratedShardDir=$shards
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
$start=Get-Date
Write-Host "$tag ONE FRESH R8 INCREMENTAL XDK BUILD (11-word evidence, NO 44-byte bypass)"
& $builder @argsForXdk
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "$tag XDK compilation/XEX creation failed; inspect $($argsForXdk.BuildLog)"
}
$buildLines=Get-Content -LiteralPath $argsForXdk.BuildLog -Encoding Default
$success=@($buildLines | Where-Object {$_ -match "(?i)========== Build:\s*[1-9][0-9]* succeeded"})
if($success.Count -lt 1){
    throw "$tag XDK reused an up-to-date XEX! No fresh compilation proven."
}
$xexFile=Get-Item -LiteralPath $xex
if($xexFile.Length -lt 1000000 -or $xexFile.LastWriteTime -lt $start.AddSeconds(-2)){
    throw "$tag Stale/unexpected XEX output; refusing test-ready claim"
}
$sha=(Get-FileHash -LiteralPath $xex -Algorithm SHA256).Hash.ToLowerInvariant()
[ordered]@{
    status="K1_R8_FRESH_XDK_PROBE_REQUIRES_HARDWARE_LOG"
    original_r7_main_sha256=$m.original_r7_main_sha256
    r8_main_sha256=$mainSha
    new_hardware_fingerprint=$m.new_r8_hardware_fingerprint
    xex_path=$xex
    xex_sha256=$sha
    xex_bytes=$xexFile.Length
    fresh_xdk_compile_success=$true
    already_working_36_byte_reads_unchanged=$true
    unknown_44_byte_frame_still_fenced=$true
    r8_hardware_run_verified=$false
    first_guest_pixels_verified=$false
} | ConvertTo-Json -Depth 5 | Set-Content -LiteralPath $buildReport -Encoding UTF8
Write-Host "$tag ========================================================"
Write-Host "$tag NEW XDK BUILD PASS (ABI evidence only, no speculative 44-byte recovery)"
Write-Host "$tag XEX: $xex"
Write-Host "$tag SHA256: $sha"
Write-Host "$tag Expect R8 fingerprint in xbWatson: $($m.new_r8_hardware_fingerprint)"
Write-Host "$tag After hardware test: rerun this script -XboxLog '<xbWatson.log>'"
Write-Host "$tag Build report: $buildReport"
