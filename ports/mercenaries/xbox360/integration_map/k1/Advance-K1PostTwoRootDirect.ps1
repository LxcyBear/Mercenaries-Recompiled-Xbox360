[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# One original retail .text function at 002228C0, source-only by default.
# Preserve hardware-good r4 main, two original functions, six-case D3D patch
# and its 64 existing TrueTUs. XDK only upon explicit -Build.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$stage = Join-Path $PSScriptRoot "Stage-K1PostTwoRootDirect.py"
$post = Join-Path $PSScriptRoot "Plan-K1PostTwoRootDirect.py"
$previousPlanner = Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$previousStage = Join-Path $PSScriptRoot "Stage-K1NextICallBatch.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$bb = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$bc = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bc_broad_sweep.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$functions = Join-Path $original "analysis\disasm\functions.json"
$generated = Join-Path $original "runtime\gen"
$parentDir = Join-Path $root "build\phase6_integration_map\k1_next_icall_1f7620_two_roots_r4"
$parentMain = Join-Path $parentDir "main.cpp"
$parentManifest = Join-Path $parentDir "k1-next-icall-two-root-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$outDir = Join-Path $root "build\phase6_integration_map\k1_direct_2228c0_r5"
$outMain = Join-Path $outDir "main.cpp"
$outManifest = Join-Path $outDir "k1-direct-2228c0-original-manifest.json"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk = Join-Path $outDir "xdk"
$xex = Join-Path $xdk "Merc-K1Direct-2228C0-r5.xex"
foreach($file in @($stage,$post,$previousPlanner,$previousStage,$base,$bb,$bc,$functions,$parentMain,$parentManifest)) {
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "[K1-DIRECT-R5] Required original retail source or tested r4 artifact absent: $file"
    }
}
foreach($folder in @($generated,$shards)){
    if(-not(Test-Path -LiteralPath $folder -PathType Container)){
        throw "[K1-DIRECT-R5] Original retail disassembly/64 TrueTU corpus missing: $folder"
    }
}
& $pythonExe -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1-DIRECT-R5] Source syntax gate failed, NO XDK"}
& $pythonExe -u $stage --self-test --previous-stage $previousStage --previous-planner $previousPlanner
if($LASTEXITCODE -ne 0){throw "[K1-DIRECT-R5] Original r4 source/one-root fixtures failed, NO XDK"}
$sourceArgs = @(
    "--base-module",$base,
    "--bb-module",$bb,
    "--bc-module",$bc,
    "--post-planner",$post,
    "--previous-planner",$previousPlanner,
    "--previous-stage",$previousStage,
    "--functions",$functions,
    "--generated",$generated,
    "--parent",$parentMain,
    "--parent-manifest",$parentManifest,
    "--shards",$shards,
    "--output",$outMain,
    "--manifest",$outManifest
)
& $pythonExe -u $stage @sourceArgs
if($LASTEXITCODE -ne 0){
    throw "[K1-DIRECT-R5] Exact original .text root/support graph/r4 SHA guard failed. NO XDK"
}
$doc = Get-Content -LiteralPath $outManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$hash = (Get-FileHash -LiteralPath $outMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($doc.status -ne "K1_TEXT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY_NO_XDK" -or
    $doc.marker -ne "K1-TEXT-DIRECT-002228C0-20261103" -or
    $doc.original_retail_xbe_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
    $doc.original_function_address -ne "0x002228C0" -or
    $doc.original_generated_c -ne "recomp_0011.c" -or
    $doc.new_main_sha256 -ne $hash -or
    [int]$doc.source_only_staged_new_functions -ne 1 -or
    [int]$doc.true_tu_count -ne 64 -or
    $doc.original_true_tus_unchanged -ne $true -or
    $doc.runtime_header_unchanged -ne $true -or
    $doc.original_graph_truncated -ne $false -or
    @($doc.original_graph_missing_addresses).Count -ne 1 -or
    @($doc.original_graph_missing_addresses)[0] -ne "0x002228C0" -or
    $doc.six_case_verified_owner -ne "translated_052.cpp" -or
    $doc.main_pack_lookup_original_root_present -ne $true -or
    $doc.native_xenos_reset_source_preserved -ne $true -or
    $doc.unknown_direct_and_indirect_hard_fences_preserved -ne $true -or
    $doc.dummy_guest_data -ne $false -or
    $doc.new_xdk_verified -ne $false -or
    $doc.new_hardware_verified -ne $false) {
    throw "[K1-DIRECT-R5] Source-only original .text + r4 guest safety contract mismatch; NO XDK"
}
Write-Host "[K1-DIRECT-R5] =========================================="
Write-Host "[K1-DIRECT-R5] ORIGINAL RETAIL 002228C0 SOURCE-ONLY STAGE PASS"
Write-Host "[K1-DIRECT-R5] r4 two-body source, real six-case D3D, Xenos Reset retained"
Write-Host "[K1-DIRECT-R5] Original 64 TrueTUs unchanged, one new original .text function"
Write-Host "[K1-DIRECT-R5] Source-only manifest: $outManifest"
if(-not $Build){
    Write-Host "[K1-DIRECT-R5] NO XDK. Use -Build for exactly one incremental Xbox360 compilation."
    exit 0
}
foreach($file in @($builder,$envFile)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-DIRECT-R5] Original builder/env source missing: $file"
    }
}
New-Item -ItemType Directory -Force -Path $xdk | Out-Null
$buildArgs = @{
    GeneratedMain = $outMain
    GeneratedEnv = $envFile
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
Write-Host "[K1-DIRECT-R5] ONE INCREMENTAL BUILD: original 002228C0 only, 64 TrueTUs reused"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1-DIRECT-R5] XDK build failure. Log: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1-DIRECT-R5] XDK builder claimed success without a published XEX"
}
Write-Host "[K1-DIRECT-R5] BUILD PASS: $xex"
Write-Host "[K1-DIRECT-R5] Pixels/hardware progress unverified until a new Xbox run"
