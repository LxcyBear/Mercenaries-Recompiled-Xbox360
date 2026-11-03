[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
# PowerShell 5.1. No original TrueTU is overwritten, and native Reset failure
# NEVER becomes guest success. -Build compiles main + at most one TrueTU.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$parentRunner = Join-Path $PSScriptRoot "Advance-K1TextDirectBatch.ps1"
$stage = Join-Path $PSScriptRoot "Stage-K1D3DSecondCreateDevice.py"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$parentRoot = Join-Path $root "build\phase6_integration_map\k1_text_direct_batch"
$parentMain = Join-Path $parentRoot "main.cpp"
$parentManifest = Join-Path $parentRoot "k1-text-direct-manifest.json"
$originalShards = Join-Path $root "build\phase6_integration_map\k1_ntquerydirectory207_native\translated_shards"
$outRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_second_create_r2"
$nextMain = Join-Path $outRoot "main.cpp"
$nextShards = Join-Path $outRoot "translated_shards"
$nextManifest = Join-Path $outRoot "k1-d3d-second-manifest.json"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk = Join-Path $outRoot "xdk"
$xex = Join-Path $xdk "Merc-K1D3D-SecondCreateDevice-r2.xex"
$python = (Get-Command python -ErrorAction Stop).Source

foreach($file in @($parentRunner,$stage,$builder,$envFile)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1D3D] Missing required source: $file"
    }
}
if(-not(Test-Path -LiteralPath $originalShards -PathType Container)){
    throw "[K1D3D] Missing 64 original TrueTU source directory"
}

New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
$inheritedLog = Join-Path $outRoot "k1-text-inherited-source.log"
$inherited = @(& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $parentRunner 2>&1)
$rc = $LASTEXITCODE
$inherited | Out-File -LiteralPath $inheritedLog -Encoding UTF8
if($rc -ne 0){
    $inherited | Select-Object -Last 35 | ForEach-Object { Write-Host $_ }
    throw "[K1D3D] Inherited TEXT source preflight failed; XDK blocked: $inheritedLog"
}
Write-Host "[K1D3D] INHERITED TEXT SOURCE: PASS (real 0017A0A0, PC checkpoint, hard fences)"
if(-not(Test-Path -LiteralPath $parentMain -PathType Leaf) -or
   -not(Test-Path -LiteralPath $parentManifest -PathType Leaf)){
    throw "[K1D3D] Parent K1 TEXT main/manifest missing"
}

$parent = Get-Content -LiteralPath $parentManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$parentHash = (Get-FileHash -LiteralPath $parentMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($parent.status -ne "K1_TEXT_DIRECT_SOURCE_ONLY_NO_XDK" -or
   $parent.new_main_sha256 -ne $parentHash -or
   [int]$parent.compiled_tus_unchanged -ne 64 -or
   @($parent.promoted_vas) -notcontains "0x0017A0A0" -or
   $parent.guest_state_write_replaced -ne $false -or
   $parent.unknown_mmio_fences_changed -ne $false){
    throw "[K1D3D] Exact K1 TEXT root/parent identity mismatch"
}

& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1D3D] Python syntax failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1D3D] Source fixtures failed; XDK blocked"}
& $python -u $stage --parent-main $parentMain --shards $originalShards --out-main $nextMain --out-shards $nextShards --manifest $nextManifest
if($LASTEXITCODE -ne 0){throw "[K1D3D] Exact native Reset source stage failed; XDK blocked"}

$doc = Get-Content -LiteralPath $nextManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$main = Get-Content -LiteralPath $nextMain -Raw -Encoding UTF8
$nextHash = (Get-FileHash -LiteralPath $nextMain -Algorithm SHA256).Hash.ToLowerInvariant()
if($doc.status -ne "K1_D3D_SECOND_SOURCE_ONLY_NO_XDK" -or
   $doc.parent_main_sha256 -ne $parentHash -or
   $doc.next_main_sha256 -ne $nextHash -or
   [int]$doc.shards_count -ne 64 -or
   @($doc.shards_changed).Count -gt 1 -or
   $doc.runtime_header_changed -ne $false -or
   $doc.guest_success_requires_native_reset_pass -ne $true -or
   $doc.unknown_configs_fenced -ne $true -or
   $doc.synthetic_guest_pixels -ne $false -or
   $doc.xdk_verified -ne $false -or
   -not $main.Contains("P6K1-D3D-SECOND-CREATE-20261103") -or
   -not $main.Contains("K1STATE MAIN CHECKPOINT:") -or
   -not $main.Contains("D3DDevice_Reset(") -or
   -not $main.Contains("P6DQ ROCKET HARD STOP")){
    throw "[K1D3D] Staged native reconfiguration or safety manifest mismatch"
}

Write-Host ("[K1D3D] PREFLIGHT PASS: owner={0}; originals=64; TU edits={1}" -f $doc.owner,@($doc.shards_changed).Count)
Write-Host "[K1D3D] Native 2-buffer / 2-sample reset required; unsupported modes and failed reset remain hard stops"
Write-Host "[K1D3D] Original 64 TrueTUs intact, all diagnostics preserved"
if(-not $Build){
    Write-Host "[K1D3D] SOURCE ONLY. Add -Build for one incremental XEX."
    exit 0
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
Write-Host "[K1D3D] ONE INCREMENTAL BUILD: updated main + at most one translated TU"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1D3D] XDK build failed: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1D3D] No published XEX after build"
}
Write-Host "[K1D3D] XDK BUILD PASS: $xex"
Write-Host "[K1D3D] Hardware NOT verified: look for K1D3D SECOND native Reset HRESULT and a new real boundary"
