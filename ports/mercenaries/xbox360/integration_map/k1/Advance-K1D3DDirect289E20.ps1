[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# PowerShell 5.1. Source-only by default; no original translated source changes.
# K1D3D R2 is independently rebuilt/validated before mandatory real retail
# 00289E20 direct-root promotion. Do not build any pruned/unsupported root.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$stage = Join-Path $PSScriptRoot "Stage-K1D3DDirect289E20.py"
$parentRunner = Join-Path $PSScriptRoot "Advance-K1D3DSecondCreateDevice.ps1"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$bb = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$bc = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bc_broad_sweep.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$generated = Join-Path $original "runtime\gen"
$functions = Join-Path $original "analysis\disasm\functions.json"
$cache = Join-Path $original "analysis\disasm\.disasm_cache.json"
$pcManual = Join-Path $root "ports\mercenaries\src\recomp_manual.c"
$parentRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_second_create_r2"
$parentMain = Join-Path $parentRoot "main.cpp"
$parentManifest = Join-Path $parentRoot "k1-d3d-second-manifest.json"
$shards = Join-Path $parentRoot "translated_shards"
$outRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_direct_289e20"
$nextMain = Join-Path $outRoot "main.cpp"
$nextManifest = Join-Path $outRoot "k1-d3d-direct-289e20-manifest.json"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk = Join-Path $outRoot "xdk"
$xex = Join-Path $xdk "Merc-K1D3D-Direct289E20.xex"

foreach($file in @($stage,$parentRunner,$base,$bb,$bc,$functions,$cache,$pcManual,$builder,$envFile)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1D3D-DIRECT] Missing required source: $file"
    }
}
if(-not(Test-Path -LiteralPath $generated -PathType Container)){
    throw "[K1D3D-DIRECT] Missing exact original xboxrecomp C corpus"
}

New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
$parentLog = Join-Path $outRoot "inherited-k1d3d-r2-source-preflight.log"
$parentOutput = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $parentRunner 2>&1)
$parentExit = $LASTEXITCODE
$parentOutput | Out-File -LiteralPath $parentLog -Encoding UTF8
if($parentExit -ne 0){
    $parentOutput | Select-Object -Last 35 | ForEach-Object { Write-Host $_ }
    throw "[K1D3D-DIRECT] K1D3D R2 source preflight failed; no XDK. See $parentLog"
}
Write-Host "[K1D3D-DIRECT] INHERITED R2 SOURCE PASS: authentic second Xenos Reset, 64 TrueTUs, existing hard fences"

foreach($file in @($parentMain,$parentManifest)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1D3D-DIRECT] Missing R2 parent artifacts: $file"
    }
}
if(-not(Test-Path -LiteralPath $shards -PathType Container)){
    throw "[K1D3D-DIRECT] R2 TrueTU source directory missing"
}
$prior = Get-Content -LiteralPath $parentManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$parentHash = (Get-FileHash -LiteralPath $parentMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($prior.status -ne "K1_D3D_SECOND_SOURCE_ONLY_NO_XDK" -or
   $prior.next_main_sha256 -ne $parentHash -or
   [int]$prior.shards_count -ne 64 -or
   $prior.guest_success_requires_native_reset_pass -ne $true -or
   $prior.unknown_configs_fenced -ne $true -or
   $prior.synthetic_guest_pixels -ne $false){
    throw "[K1D3D-DIRECT] K1D3D R2 exact source/guest contract mismatch"
}

$python = (Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){ throw "[K1D3D-DIRECT] Python syntax failed; XDK blocked" }
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){ throw "[K1D3D-DIRECT] Fail-closed source fixtures failed; XDK blocked" }
$argsList = @("--base-module",$base,"--p5bb-module",$bb,"--p5bc-module",$bc,
              "--parent",$parentMain,"--shards",$shards,"--functions",$functions,
              "--generated-root",$generated,"--pc-manual",$pcManual,"--output",$nextMain,"--manifest",$nextManifest)
& $python -u $stage @argsList
if($LASTEXITCODE -ne 0){ throw "[K1D3D-DIRECT] Exact original D3D source promotion failed; XDK blocked" }

$doc = Get-Content -LiteralPath $nextManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$hash = (Get-FileHash -LiteralPath $nextMain -Algorithm SHA256).Hash.ToLowerInvariant()
$txt = Get-Content -LiteralPath $nextMain -Raw -Encoding UTF8
if($doc.status -ne "K1_D3D_DIRECT_289E20_SOURCE_ONLY_NO_XDK" -or
   $doc.original_xbe_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
   $doc.root_va -ne "0x00289E20" -or
   $doc.parent_sha256 -ne $parentHash -or
   $doc.new_main_sha256 -ne $hash -or
   [int]$doc.original_true_tus -ne 64 -or
   [int]$doc.modified_true_tus -ne 0 -or
   $doc.pc_supported_texture_hook_implemented -ne $true -or
   $doc.pc_stage23_telemetry_implemented -ne $true -or
   $doc.pc_support_proof.movie_hook_scope -ne "stage-23 read-only 128-sample diagnostics only" -or
   -not ($doc.pc_support_proof.pc_texture_validator_sha256 -match '^[0-9a-f]{64}$') -or
   -not ($doc.pc_support_proof.pc_movie_stage_23_sha256 -match '^[0-9a-f]{64}$') -or
   -not $txt.Contains("static uint32_t recomp_validate_texture_bind(") -or
   -not $txt.Contains("static void recomp_movie_checkpoint(") -or
   $doc.native_xenos_reset_replaced -ne $false -or
   $doc.unknown_mmio_fences_changed -ne $false -or
   $doc.fake_guest_pixels -ne $false -or
   $doc.hardware_verified -ne $false -or
   @($doc.promoted_vas) -notcontains "0x00289E20" -or
   -not $txt.Contains("case 0x00289E20u: return sub_00289E20;") -or
   -not $txt.Contains("K1D3D SECOND: native Xenos Reset PASS") -or
   -not $txt.Contains("K1STATE MAIN CHECKPOINT:") -or
   -not $txt.Contains("P6DQ ROCKET HARD STOP")){
    throw "[K1D3D-DIRECT] Mandatory original function / inherited guest-safety manifest mismatch"
}
Write-Host ("[K1D3D-DIRECT] PREFLIGHT PASS: authentic retail D3D 00289E20; packed={0}; 64 TrueTUs intact" -f @($doc.promoted_vas).Count)
Write-Host "[K1D3D-DIRECT] Maintained PC hook implementations: texture validity preserved, movie stage-23 diagnostic-only, 64 TUs untouched"
Write-Host "[K1D3D-DIRECT] Native second CreateDevice/Xenos Reset unchanged. No guest result fabricated."
if(-not $Build){
    Write-Host "[K1D3D-DIRECT] SOURCE ONLY. Add -Build after source preflight succeeds."
    exit 0
}

New-Item -ItemType Directory -Force -Path $xdk | Out-Null
$buildArgs = @{
    GeneratedMain = $nextMain
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
Write-Host "[K1D3D-DIRECT] ONE INCREMENTAL XDK BUILD: new main; original 64 TrueTUs reused"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1D3D-DIRECT] XDK build failed. See $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1D3D-DIRECT] Build reported success without expected XEX"
}
Write-Host "[K1D3D-DIRECT] XDK BUILD PASS: $xex"
Write-Host "[K1D3D-DIRECT] Hardware unverified: require authentic 00289E20 crossing, real Swap/PersistDisplay evidence"
