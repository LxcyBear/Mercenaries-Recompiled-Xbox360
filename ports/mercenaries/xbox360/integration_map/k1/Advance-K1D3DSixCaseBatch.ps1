[CmdletBinding()]
param(
    [switch]$Build,
    [string]$XbePath = "C:\Users\jorda\OneDrive\Desktop\My Xbox\default.xbe",
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. Six original D3D case branches, one
# incremental XDK build only if requested, no edited parent source.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$stage = Join-Path $PSScriptRoot "Stage-K1D3DSixCaseBatch.py"
$audit = Join-Path $PSScriptRoot "Audit-K1D3DSwitchCases.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$generated = Join-Path $original "runtime\gen"
$functions = Join-Path $original "analysis\disasm\functions.json"
$parentRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_direct_289e20_r2"
$parentMain = Join-Path $parentRoot "main.cpp"
$parentManifest = Join-Path $parentRoot "k1-d3d-direct-289e20-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_second_create_r2\translated_shards"
$outRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3"
$nextMain = Join-Path $outRoot "main.cpp"
$nextShards = Join-Path $outRoot "translated_shards"
$manifest = Join-Path $outRoot "k1-d3d-six-cases-manifest.json"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk = Join-Path $outRoot "xdk"
$xex = Join-Path $xdk "Merc-K1D3D-SixCases-r3.xex"

foreach($path in @($stage,$audit,$base,$functions,$parentMain,$parentManifest,$XbePath)){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1D3D-SIX] Missing required local source: $path"
    }
}
foreach($path in @($generated,$shards)){
    if(-not(Test-Path -LiteralPath $path -PathType Container)){
        throw "[K1D3D-SIX] Missing original recomp-generated corpus / 64 TrueTUs: $path"
    }
}
$python = (Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){ throw "[K1D3D-SIX] Python syntax invalid" }
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){ throw "[K1D3D-SIX] Six-case stage safety fixture failed" }
& $python -u $audit --self-test
if($LASTEXITCODE -ne 0){ throw "[K1D3D-SIX] Original x86 decoder fixture failed" }
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null

$argsList = @(
    "--xbe", $XbePath,
    "--audit-module", $audit,
    "--base-module", $base,
    "--parent-main", $parentMain,
    "--parent-manifest", $parentManifest,
    "--shards", $shards,
    "--generated-root", $generated,
    "--functions", $functions,
    "--out-main", $nextMain,
    "--out-shards", $nextShards,
    "--manifest", $manifest
)
& $python -u $stage @argsList
if($LASTEXITCODE -ne 0){
    throw "[K1D3D-SIX] Retail XBE/source ABI preflight failed. No XDK build."
}
$doc = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$nextHash = (Get-FileHash -LiteralPath $nextMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($doc.status -ne "K1_D3D_SIX_CASES_SOURCE_ONLY_NO_XDK" -or
   $doc.marker -ne "K1D3D-296550-SIXCASES-ONEBUILD-20261103" -or
   $doc.original_retail_xbe_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
   $doc.staged_main_sha256 -ne $nextHash -or
   [int]$doc.original_true_tus -ne 64 -or
   [int]$doc.changed_true_tu_count -gt 1 -or
   $doc.modified_runtime_header -ne $false -or
   $doc.preserves_unknown_tail_hard_fence -ne $true -or
   $doc.xenos_reset_source_unchanged -ne $true -or
   $doc.synthetic_guest_pixels -ne $false -or
   $doc.proof.machine_opcode_fingerprint_sha256 -ne "16cf010d3ac3a3db719ed76a153309897744e638bdcef0b99a3bf8f40083e191" -or
   [int]$doc.proof.machine_instruction_count -ne 41 -or
   $doc.proof.all_paths_reach_original_002965D0_ret -ne $true -or
   $doc.xdk_verified -ne $false -or $doc.hardware_verified -ne $false){
    throw "[K1D3D-SIX] Original source/retail opcode/guest hard-fence contract mismatch"
}
Write-Host "[K1D3D-SIX] SOURCE PREFLIGHT PASS: all six original x86 cases joined to shared 002965A8"
Write-Host ("[K1D3D-SIX] Compiled source unit = {0}, updated translated .cpp TUs = {1}/64" -f $doc.source_root_owner, [int]$doc.changed_true_tu_count)
Write-Host "[K1D3D-SIX] Unknown/unsafe tail index remains fenced; original native Xenos Reset intact."
if(-not $Build){
    Write-Host "[K1D3D-SIX] SOURCE ONLY. For one real incremental XDK build, rerun with -Build."
    exit 0
}

foreach($path in @($builder,$envFile)){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1D3D-SIX] XDK build input missing; cannot build: $path"
    }
}
New-Item -ItemType Directory -Force -Path $xdk | Out-Null
$buildArgs = @{
    GeneratedMain = $nextMain
    GeneratedEnv = $envFile
    GeneratedShardDir = $nextShards
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
Write-Host "[K1D3D-SIX] ONE INCREMENTAL XDK BUILD: all six original switch paths together"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){
    throw "[K1D3D-SIX] XDK build failed, see $($buildArgs.BuildLog)"
}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1D3D-SIX] Builder did not publish expected XEX"
}
Write-Host "[K1D3D-SIX] XDK BUILD PASS: $xex"
Write-Host "[K1D3D-SIX] Hardware still unverified: require authentic 0029655D crossing, real display_calls/Swap."
