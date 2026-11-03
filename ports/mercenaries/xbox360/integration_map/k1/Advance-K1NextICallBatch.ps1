[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. Compile original 001F7620 + 001F7520 in
# ONE derived main.cpp only, preserving parent 64 TrueTUs and real
# six-case D3D patch; defaults to NO XDK build.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$stage = Join-Path $PSScriptRoot "Stage-K1NextICallBatch.py"
$planner = Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$bb = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$bc = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bc_broad_sweep.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$functions = Join-Path $original "analysis\disasm\functions.json"
$generated = Join-Path $original "runtime\gen"
$parentDir = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3"
$parentMain = Join-Path $parentDir "main.cpp"
$parentManifest = Join-Path $parentDir "k1-d3d-six-cases-manifest.json"
$shards = Join-Path $parentDir "translated_shards"
$outDir = Join-Path $root "build\phase6_integration_map\k1_next_icall_1f7620_two_roots_r4"
$outMain = Join-Path $outDir "main.cpp"
$outManifest = Join-Path $outDir "k1-next-icall-two-root-manifest.json"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk = Join-Path $outDir "xdk"
$xex = Join-Path $xdk "Merc-K1NextICall-1F7620-1F7520-r4.xex"

foreach($file in @($stage,$planner,$base,$bb,$bc,$functions,$parentMain,$parentManifest)) {
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "[K1-NEXT-PACK] Required source artifact absent: $file"
    }
}
foreach($dir in @($generated,$shards)) {
    if(-not(Test-Path -LiteralPath $dir -PathType Container)) {
        throw "[K1-NEXT-PACK] Required original 64-TU/original C corpus absent: $dir"
    }
}

& $pythonExe -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1-NEXT-PACK] Python syntax error; XDK blocked"}
& $pythonExe -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1-NEXT-PACK] Source-only, no-XDK safety test failed"}
$srcArgs = @(
    "--base-module",$base,
    "--bb-module",$bb,
    "--bc-module",$bc,
    "--planner",$planner,
    "--functions",$functions,
    "--generated",$generated,
    "--parent",$parentMain,
    "--parent-manifest",$parentManifest,
    "--shards",$shards,
    "--output",$outMain,
    "--manifest",$outManifest
)
& $pythonExe -u $stage @srcArgs
if($LASTEXITCODE -ne 0) {
    throw "[K1-NEXT-PACK] Source provenance, support-clean pack or 64-TU guard rejected; NO XDK build"
}
$doc = Get-Content -LiteralPath $outManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$hash = (Get-FileHash -LiteralPath $outMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($doc.status -ne "K1_NEXT_ICALL_TWO_SOURCE_AUTHENTIC_BODIES_NO_XDK" -or
    $doc.marker -ne "K1-TEXT-ICALL-1F7620-1F7520-20261103" -or
    $doc.original_retail_xbe_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
    $doc.new_main_sha256 -ne $hash -or
    [int]$doc.original_true_tus -ne 64 -or
    [int]$doc.new_members_count -ne 2 -or
    $doc.original_true_tus_reused_not_modified -ne $true -or
    $doc.original_runtime_header_unchanged -ne $true -or
    $doc.lookup_both_exact_original_entries -ne $true -or
    $doc.preserves_six_case_graphics_dispatch -ne $true -or
    $doc.native_xenos_reset_source_unchanged -ne $true -or
    $doc.unknown_indirect_hard_fence_unchanged -ne $true -or
    $doc.dummy_guest_data -ne $false -or
    $doc.xdk_verified -ne $false -or
    $doc.hardware_verified -ne $false) {
    throw "[K1-NEXT-PACK] Exact two-function original source/guest safety gate changed. No XDK."
}
Write-Host "[K1-NEXT-PACK] =========================================="
Write-Host "[K1-NEXT-PACK] SOURCE ONLY PASS: 001F7620 + 001F7520"
Write-Host "[K1-NEXT-PACK] Original six-case graphics path + native Reset retained"
Write-Host "[K1-NEXT-PACK] Exact original 64 TrueTUs reused unchanged"
Write-Host "[K1-NEXT-PACK] Original guest ICALL_SAFE fallback remains fenced"
Write-Host "[K1-NEXT-PACK] Manifest: $outManifest"
if(-not $Build) {
    Write-Host "[K1-NEXT-PACK] NO XDK. Rerun with -Build for one incremental XEX."
    exit 0
}

foreach($file in @($builder,$envFile)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-NEXT-PACK] Exact XDK build input missing: $file"
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
Write-Host "[K1-NEXT-PACK] SINGLE INCREMENTAL XDK BUILD: exactly 2 original .text functions in main"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1-NEXT-PACK] XDK build failed. Log: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1-NEXT-PACK] Build claimed success without XEX"
}
Write-Host "[K1-NEXT-PACK] XDK BUILD PASS: $xex"
Write-Host "[K1-NEXT-PACK] Hardware unknown until Xbox proves next dispatch/pixels; no fake output"
