[CmdletBinding()]
param(
    [switch]$Build,
    [string]$HardwareLog = "",
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1, source preflight DEFAULT. XDK only with -Build.
# Three independent lanes: exactly one PFIFO register + performance clock +
# first Swap/Persist frontier attempt tracing. Only main.cpp recompiled.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$quietRoot = Join-Path $root "build\phase6_integration_map\k1_nv2a_dac_palette_quiet"
$parentMain = Join-Path $quietRoot "main.cpp"
$parentManifest = Join-Path $quietRoot "k1dq-quiet-manifest.json"
$nextRoot = Join-Path $root "build\phase6_integration_map\k1_three_lane"
$nextMain = Join-Path $nextRoot "main.cpp"
$nextManifest = Join-Path $nextRoot "k1-three-lane-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_ntquerydirectory207_native\translated_shards"
$header = Join-Path $shards "translated_runtime.h"
$envFile = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$stage = Join-Path $PSScriptRoot "Stage-K1ThreeLaneMain.py"
$parentRunner = Join-Path $PSScriptRoot "Advance-K1NV2ADacPalette.ps1"
$auditRunner = Join-Path $PSScriptRoot "Run-K1ThreeLanePreflight.ps1"
$builder = Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$xdk = Join-Path $nextRoot "xdk"
$xex = Join-Path $xdk "Merc-K1-ThreeLane-PFIFO-PERF-PRESENT.xex"
$python = (Get-Command python -ErrorAction Stop).Source

foreach($path in @($parentRunner, $auditRunner, $stage, $envFile, $header, $builder)){
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1-3LANE] Missing proven input: $path"
    }
}
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $parentRunner
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] DAC + quiet inherited preflight failed"}
$auditArgs = @{}
if($HardwareLog){$auditArgs.HardwareLog = $HardwareLog}
& $auditRunner @auditArgs
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Source/XBE/Swap/hot audit failed"}

foreach($path in @($parentMain, $parentManifest)){
    if(-not (Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1-3LANE] Missing quiet parent output: $path"
    }
}
$parent = Get-Content -LiteralPath $parentManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($parent.marker -ne "P6K1DQ-QUIET-LOG-20261103" -or
   $parent.new_main_sha256 -ne (Get-FileHash -LiteralPath $parentMain -Algorithm SHA256).Hash.ToLowerInvariant() -or
   $parent.guest_execution_changed -ne $false -or
   $parent.mmio_fences_changed -ne $false -or
   [int]$parent.translated_tus_changed -ne 0 -or
   [int]$parent.runtime_headers_changed -ne 0){
    throw "[K1-3LANE] DAC/quiet parent identity or preserved fences drift"
}
$trueTus = @(Get-ChildItem -LiteralPath $shards -Filter "translated_???.cpp" -File)
if($trueTus.Count -ne 64){throw "[K1-3LANE] Need exactly 64 original TrueTUs"}

& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Stage syntax failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Three-lane stage selftest failed"}
& $python -u $stage --parent $parentMain --out $nextMain --manifest $nextManifest
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] Derived main staging failed"}

$doc = Get-Content -LiteralPath $nextManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($doc.marker -ne "P6K1-THREELANE-20261103" -or
   $doc.status -ne "K1_THREE_LANE_SOURCE_STAGED_NO_XDK" -or
   $doc.parent_main_sha256 -ne $parent.new_main_sha256 -or
   $doc.new_main_sha256 -ne (Get-FileHash -LiteralPath $nextMain -Algorithm SHA256).Hash.ToLowerInvariant() -or
   $doc.pfifo_initial_read_site -ne "0x0028ED6B" -or
   $doc.pfifo_address -ne "0xFD003240" -or
   [int]$doc.pfifo_reset_value -ne 0 -or
   $doc.unknown_mmio_still_fenced -ne $true -or
   $doc.present_attempts_only_no_fake_swap -ne $true -or
   $doc.synthetic_pixels -ne $false -or
   [int]$doc.translated_tus_changed -ne 0 -or
   [int]$doc.runtime_headers_changed -ne 0){
    throw "[K1-3LANE] Multi-lane manifest provenance mismatch; XDK blocked"
}
$mainText = Get-Content -LiteralPath $nextMain -Raw -Encoding UTF8
$traceExportPattern = '(?m)^[ \t]*void[ \t]+trace[ \t]*\([ \t]*const[ \t]+char[ \t]*\*[ \t]*line[ \t]*\)[ \t\r\n]*\{'
if([regex]::Matches($mainText, $traceExportPattern).Count -ne 1 -or
   [regex]::Matches($mainText, '(?m)^[ \t]*static[ \t]+void[ \t]+trace\s*\(').Count -ne 0){
    throw "[K1-3LANE] Cross-TU global trace ABI not preserved"
}
foreach($marker in @("K1PFIFO DMA_PUT READ32:", "K1PFIFO DMA_PUT WRITE32:",
                     "K1PERF WINDOW:", "K1PRESENT FRONTIER ROUTE:",
                     "P6DQ ROCKET HARD STOP", "K1NV2A DAC PALETTE COMMIT:")){
    if(-not $mainText.Contains($marker)){
        throw "[K1-3LANE] Missing source-stage witness $marker"
    }
}
Write-Host "[K1-3LANE] PREFLIGHT PASS: exact PFIFO, 001E perf, Swap/Persist probes"
Write-Host "[K1-3LANE] 64 TrueTUs unchanged; original DAC, quiet and hard fences retained"
if(-not $Build){
    Write-Host "[K1-3LANE] SOURCE ONLY. Add -Build to make one incremental XEX."
    exit 0
}

New-Item -ItemType Directory -Force -Path $xdk | Out-Null
$buildArgs = @{
    GeneratedMain=$nextMain
    GeneratedEnv=$envFile
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
Write-Host "[K1-3LANE] ONE INCREMENTAL XDK BUILD; 64 previously compiled TrueTUs reused"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1-3LANE] XDK build failed; see $($buildArgs.BuildLog)"}
if(-not (Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1-3LANE] XDK build did not publish expected XEX"
}
Write-Host "[K1-3LANE] BUILD PASS: $xex"
Write-Host "[K1-3LANE] Hardware witnesses: K1PFIFO, K1PERF, K1PRESENT + real DAC/fault/Swap"
