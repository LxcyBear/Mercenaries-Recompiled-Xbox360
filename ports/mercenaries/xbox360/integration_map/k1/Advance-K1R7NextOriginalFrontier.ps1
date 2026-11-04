[CmdletBinding()]
param(
    [switch]$SourceOnly,
    [string]$XboxLog = "",
    [string]$RetailXbe = "$env:USERPROFILE\OneDrive\Desktop\My Xbox\default.xbe",
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# Original retail 00222190 hardware frontier -> exact .text generated C,
# direct dependency class, fingerprint in existing hard-stop logger, ONE
# real XDK incremental build. Will NOT publish an up-to-date old binary.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$tag = "[K1-R7]"
$python = (Get-Command python -ErrorAction Stop).Source
$stage = Join-Path $PSScriptRoot "Stage-K1R7NextOriginalFrontier.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$bb = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$bc = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bc_broad_sweep.py"
$previous = Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$packer = Join-Path $PSScriptRoot "Stage-K1NextICallBatch.py"
$retailAuditor = Join-Path $PSScriptRoot "Audit-K1D3DSwitchCases.py"
$pcReference = Join-Path $root ".deps\mercenaries-pc-reference"
$pcRetail = Join-Path $PSScriptRoot "Audit-K1PCRetailSource.py"
$streamRetail = Join-Path $PSScriptRoot "Audit-K1R7RetailStreamingPatch.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$functions = Join-Path $original "analysis\disasm\functions.json"
$generated = Join-Path $original "runtime\gen"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$r5 = Join-Path $root "build\phase6_integration_map\k1_direct_2228c0_r5"
$parent = Join-Path $r5 "main.cpp"
$parentManifest = Join-Path $r5 "k1-direct-2228c0-original-manifest.json"
$outDir = Join-Path $root "build\phase6_integration_map\k1_direct_222190_r7_fingerprinted"
$outMain = Join-Path $outDir "main.cpp"
$outManifest = Join-Path $outDir "k1-direct-222190-r7-manifest.json"
$trace = Join-Path $PSScriptRoot "Audit-K1GraphicsMilestoneTrace.py"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk = Join-Path $outDir "xdk"
$xex = Join-Path $xdk "Merc-K1-R7-222190-FINGERPRINTED.xex"
$report = Join-Path $outDir "k1-r7-build-and-hardware-report.json"
$traceReport = Join-Path $outDir "k1-r7-hardware-vs-pc.json"

function Read-Manifest {
    if(-not(Test-Path -LiteralPath $outManifest -PathType Leaf)){
        throw "$tag r7 original-source manifest absent: $outManifest"
    }
    $m = Get-Content -LiteralPath $outManifest -Raw -Encoding UTF8 | ConvertFrom-Json
    if($m.status -ne "K1_R7_222190_REAL_ORIGINAL_DIRECT_SOURCE_FINGERPRINT_NO_XDK" -or
       $m.retail_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
       $m.original_entry_proof.guest_entry -ne "0x00222190" -or
       $m.original_64_true_tus_unchanged -ne $true -or
       $m.previous_r4_hardware_fences_preserved -ne $true -or
       $m.retail_002228F0_branch_restoration_preserved -ne $true -or
       $m.no_dummy_abi_or_pc_helper_stubs -ne $true -or
       $m.pc_stream_idle_patch_279_restored_to_retail.status -ne "PINNED_PC_PATCH_279_RESTORED_TO_ORIGINAL_RETAIL" -or
       [int]$m.pc_stream_idle_patch_279_restored_to_retail.pc_patch_index -ne 279 -or
       $m.pc_stream_idle_patch_279_restored_to_retail.x86_retail_proof.original_002221cd_mov_add_cmp_jge -ne $true -or
       $m.pc_stream_idle_patch_279_restored_to_retail.x86_retail_proof.jge_target -ne "0x00222236" -or
       $m.pc_stream_idle_patch_279_restored_to_retail.pc_only_host_helper_removed -ne $true -or
       $m.pc_stream_idle_patch_279_restored_to_retail.mock_host_helper_or_guest_abi_used -ne $false -or
       $m.hard_stop_for_unproven_guest_targets_preserved -ne $true -or
       $m.runtime_xex_fingerprint_location -ne "P6DQ ROCKET HARD STOP kind= runtime format" -or
       @($m.new_original_generated_C).Count -lt 1 -or
       @($m.new_original_generated_C).Count -gt 16 -or
       @($m.new_original_generated_C)[0] -ne "0x00222190" -or
       $m.safe_to_claim_guest_pixels -ne $false){
        throw "$tag r5 retail/64 TrueTU/real original 222190/diagnostic source contract failed"
    }
    return $m
}

if($XboxLog){
    if(-not(Test-Path -LiteralPath $XboxLog -PathType Leaf)){
        throw "$tag Actual xbWatson log not found: $XboxLog"
    }
    $m = Read-Manifest
    $lineHits = @(Select-String -LiteralPath $XboxLog -Pattern ([regex]::Escape([string]$m.runtime_xex_fingerprint)) -ErrorAction Stop)
    if(@($lineHits).Count -eq 0){
        throw "$tag WRONG XEX / MISSING R7 RUNTIME FINGERPRINT. Do not claim progress: $($m.runtime_xex_fingerprint)"
    }
    $eventLines = @(Select-String -LiteralPath $XboxLog -Pattern "DIRECT FRONTIER:","P6DQ ROCKET HARD STOP kind=","P6DQ PIXEL CHASE:","P6DQ AV FAMILY:" -ErrorAction Stop)
    Write-Host "$tag EXACT XBOX HARDWARE XEX FINGERPRINT FOUND: $($m.runtime_xex_fingerprint)"
    foreach($entry in ($eventLines | Select-Object -Last 12)){
        Write-Host "$tag $($entry.Line.Trim())"
    }
    if(Test-Path -LiteralPath $trace -PathType Leaf){
        & $python -u $trace --xbox-log $XboxLog --output $traceReport
        if($LASTEXITCODE -ne 0){throw "$tag Hardware trace analysis failed"}
    }
    Write-Host "$tag HARDWARE LOG MATCHED fingerprint. New pixels or tick gain must be checked in log."
    return
}

foreach($file in @($stage,$base,$bb,$bc,$previous,$packer,$retailAuditor,$pcRetail,$streamRetail,$functions,$RetailXbe,$parent,$parentManifest)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "$tag Original retail evidence or source-only r5 absent: $file"
    }
}
foreach($dir in @($generated,$shards,$pcReference)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "$tag Original generated C/64 TrueTU directory missing: $dir"
    }
}
& $python -m py_compile $stage $streamRetail
if($LASTEXITCODE -ne 0){throw "$tag Python syntax failed. NO XDK."}
& $python -u $streamRetail
if($LASTEXITCODE -ne 0){throw "$tag Original retail streaming patch 279 proof self-test failed. NO XDK."}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "$tag Retail r5/ABI/diagnostic fixtures failed. NO XDK."}
$stageArgs = @(
    "--parent",$parent,
    "--parent-manifest",$parentManifest,
    "--shards",$shards,
    "--base",$base,
    "--bb",$bb,
    "--bc",$bc,
    "--previous",$previous,
    "--packer",$packer,
    "--retail-xbe",$RetailXbe,
    "--retail-auditor",$retailAuditor,
    "--pc-reference",$pcReference,
    "--pc-retail-module",$pcRetail,
    "--streaming-retail-module",$streamRetail,
    "--functions",$functions,
    "--generated",$generated,
    "--output",$outMain,
    "--manifest",$outManifest
)
& $python -u $stage @stageArgs
if($LASTEXITCODE -ne 0){throw "$tag Original retail 222190 cannot be proven/support-packed; NO XDK."}
$m = Read-Manifest
$sourceSha = (Get-FileHash -LiteralPath $outMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($m.r7_source_sha256 -ne $sourceSha -or
   $m.r5_source_sha256 -ne (Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant() -or
   -not (Select-String -LiteralPath $outMain -Pattern ([regex]::Escape([string]$m.runtime_xex_fingerprint)) -Quiet)){
    throw "$tag Original r5/r7 hash or run-on-Xbox fingerprint source mismatch"
}
Write-Host "$tag ORIGINAL RETAIL SOURCE STAGE PASS new funcs=$(@($m.new_original_generated_C).Count)"
Write-Host "$tag PC patch 279 -> retail CMP/JGE RESTORED at 0x002221CD (no PC-only streaming helper)"
Write-Host "$tag Hardware fingerprint that MUST appear in xbWatson: $($m.runtime_xex_fingerprint)"
Write-Host "$tag Original 64 TrueTUs untouched. No speculative PC helper."
if($SourceOnly){
    Write-Host "$tag SOURCE-ONLY mode. NO XDK, NO XEX."
    return
}

foreach($file in @($builder,$envSource)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "$tag Original XDK builder or phase5 env missing: $file"
    }
}
New-Item -ItemType Directory -Path $xdk -Force | Out-Null
$buildArgs = @{
    GeneratedMain = $outMain
    GeneratedEnv = $envSource
    GeneratedShardDir = $shards
    ExpectedBuildTag = "P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie = "phase6dq_env_build_cookie"
    SolutionRoot = $SolutionRoot
    Configuration = "Release"
    Platform = "Xbox 360"
    CleanLog = (Join-Path $xdk "xdk-clean.log")
    BuildLog = (Join-Path $xdk "xdk-build.log")
    PublishedXex = $xex
    ShadowBuildRoot = $FastBuildRoot
    SkipClean = $true
}
$start = Get-Date
Write-Host "$tag ONE INCREMENTAL XDK BUILD with changed main.cpp + HARDWARE FINGERPRINT"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "$tag XDK builder failed: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "$tag XDK produced no output XEX"
}
$buildLines = Get-Content -LiteralPath $buildArgs.BuildLog -Encoding Default
$buildResults = @($buildLines | Where-Object {
    $_ -match '(?i)========== Build:\s*\d+ succeeded'
})
$actuallyBuilt = @($buildResults | Where-Object {
    $_ -match '(?i)========== Build:\s*[1-9]\d* succeeded'
})
if(@($actuallyBuilt).Count -lt 1){
    throw "$tag XDK did NOT compile a new binary (VS up-to-date!). Refusing reused XEX. Result: $($buildResults -join '; ')"
}
$published = Get-Item -LiteralPath $xex
if($published.LastWriteTime -lt $start.AddSeconds(-2) -or
   $published.Length -lt 1000000){
    throw "$tag Published XEX is stale/suspicious. NO HARDWARE TEST CLAIM."
}
$sha=(Get-FileHash -LiteralPath $xex -Algorithm SHA256).Hash.ToLowerInvariant()
$doc=[ordered]@{
    status="K1_R7_FRESH_XDK_BINARY_REQUIRES_XBOX_FINGERPRINT"
    new_retail_guest_functions=@($m.new_original_generated_C)
    new_count=[int]$m.new_original_generated_C_count
    genuine_original_r5_parent_sha256=$m.r5_source_sha256
    staged_original_r7_source_sha256=$sourceSha
    hardware_fingerprint_required=[string]$m.runtime_xex_fingerprint
    true_tu_count=64
    vs2017_build_compiled_new_binary=$true
    published_xex=$xex
    published_xex_sha256=$sha
    published_xex_bytes=$published.Length
    published_xex_utc=$published.LastWriteTimeUtc.ToString("o")
    previous_hardware_frontier="0x00222190"
    previous_hardware_ticks=58613034
    previous_hardware_display_calls=0
    hardware_executed_new_binary_proven=$false
    new_hardware_pixels_proven=$false
    next_action="Test this exact XEX on Xbox 360, collect xbWatson, run this script -XboxLog <file>, and require the runtime fingerprint."
}
$doc | ConvertTo-Json -Depth 6 | Set-Content -LiteralPath $report -Encoding UTF8
Write-Host "$tag ============================================================="
Write-Host "$tag FRESH R7 XDK COMPILE PASS: source=original Xbox 00222190 plus verified direct closure"
Write-Host "$tag XEX: $xex"
Write-Host "$tag XEX SHA256: $sha"
Write-Host "$tag Expect xbWatson exact fingerprint: $($m.runtime_xex_fingerprint)"
Write-Host "$tag Hardware verification: NOT YET. display_calls/tick gain UNPROVEN."
Write-Host "$tag To verify hardware use: -XboxLog 'C:\path\to\xbWatson.log'"
Write-Host "$tag Build report: $report"
