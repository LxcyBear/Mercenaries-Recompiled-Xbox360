[CmdletBinding()]
param(
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$Configuration = "Release",
    [string]$Platform = "Xbox 360",
    [switch]$SkipSolutionBuild
)

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [System.IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$p6 = $PSScriptRoot
$p4 = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseDir = Join-Path $root "build\phase6_native_graphics\av_saved_data_cleanup_xdk"
$out = Join-Path $root "build\phase6_native_graphics\av_family_display_handoff_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ae-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ae_av_family_display_handoff.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AE input: $v"
    }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    (Join-Path $baseDir "phase6ad-manifest.json")
)

$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6ad = Join-Path $p6 "Prepare-Phase6AD.ps1"
    if (-not (Test-Path -LiteralPath $prep6ad)) {
        throw "Phase 6AE baseline missing and Phase 6AD prep was not found: $prep6ad"
    }

    Write-Host "[Phase6AE] Cached Phase 6AD output is missing."
    Write-Host "[Phase6AE] Regenerating Phase 6AD without rebuilding the external solution..."
    & $prep6ad -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6ad-manifest.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AE required input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6ad-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AD" -or
    $baseManifest.build_tag -ne "P6AD-AV-SAVED-DATA-CLEANUP-20261023-A") {
    throw "Phase 6AE Phase 6AD baseline identity mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AE] AV FAMILY + DISPLAY HANDOFF"
Write-Host "[Phase6AE] Hardware proof   : ordinal 1 crossed, ordinal 2 exact +20 boundary"
Write-Host "[Phase6AE] Ordinal 2        : AvSendTVEncoderOption strict +20 continuation"
Write-Host "[Phase6AE] Ordinal 3        : AvSetDisplayMode strict +28 pre-armed"
Write-Host "[Phase6AE] Ordinals 1/4     : inherited saved-data get/set pair"
Write-Host "[Phase6AE] Physical display : native Xenos remains owner"
Write-Host "[Phase6AE] Xbox encoder     : logical state/query bridge only, no NV2A encoder writes"
Write-Host "[Phase6AE] Cleanup          : inherit 6AD _msize trace throttling unchanged"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $paths.emitter @args 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AE] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AE] Emitter log tail:"
    Get-Content -LiteralPath $log -Tail 180
    throw "Phase 6AE emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ae-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AE missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AE" -or
    $m.build_tag -ne "P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-A") {
    throw "Phase 6AE manifest identity mismatch"
}

$ae = $m.phase6ae_av_family_display_handoff
if (-not [bool]$ae.phase6ad_hardware_pass -or
    [int]$ae.phase6ad_hardware.next_boundary.ordinal -ne 2 -or
    [int]$ae.phase6ad_hardware.next_boundary.frame_bytes -ne 20 -or
    -not [bool]$ae.av_family.ordinal_2.hardware_observed -or
    -not [bool]$ae.av_family.ordinal_3.prearmed -or
    [int]$ae.av_family.ordinal_3.frame_bytes -ne 28 -or
    $ae.source_layout.shard_prefix -ne "phase6ae_") {
    throw "Phase 6AE manifest AV-family gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-A",
    "static void phase6ae_av_send_tv_encoder_option(uint32_t savedEsp)",
    "static void phase6ae_av_set_display_mode(uint32_t savedEsp)",
    "_phase4c_target == 0x80000002u",
    "_phase4c_target == 0x80000003u",
    "PASS: Phase 6AE ordinal 2 AvSendTVEncoderOption",
    "PASS: Phase 6AE ordinal 3 AvSetDisplayMode",
    "s_phase6aeAvEncoderCount != 0u &&",
    "P6AE AV FAMILY:",
    "P6AE AV/DISPLAY SUMMARY:",
    "PHASE 6AE AV FAMILY + DISPLAY HANDOFF RESULT",
    "PASS: Phase 6AE Mm166 wrapper provenance",
    "phase6ae_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AE generated source gate missing: $marker"
    }
}

if ($envText -notmatch "phase6ae_env_build_cookie") {
    throw "Phase 6AE env cookie gate missing"
}
if ($monolithicText -match "phase6ad_env_build_cookie" -or
    $envText -match "phase6ad_env_build_cookie") {
    throw "Phase 6AE stale Phase 6AD cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AE translated shard output is empty"
}
$wrongShards = @($shards | Where-Object { -not $_.Name.StartsWith("phase6ae_") })
if ($wrongShards.Count -gt 0) {
    throw "Phase 6AE translated shard prefix gate failed: $($wrongShards[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AE] READY"
Write-Host ("[Phase6AE] Generated shards : {0}" -f $shards.Count)
Write-Host "[Phase6AE] Ordinal 2         : strict +20 encoder-option bridge"
Write-Host "[Phase6AE] Ordinal 3         : strict +28 display-mode handoff pre-armed"
Write-Host "[Phase6AE] Xbox AV hardware  : no original-Xbox register writes"
Write-Host "[Phase6AE] Xenos             : inherited native display owner"
Write-Host "[Phase6AE] Expected tag      : P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-A"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AE] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-A"
        ExpectedEnvCookie = "phase6ae_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ae-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ae-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AE.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AE] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AE] Hardware tag to verify: P6AE-AV-FAMILY-DISPLAY-HANDOFF-20261023-A"
    Write-Host ("[Phase6AE] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AE.xex"))
}
else {
    Write-Host "[Phase6AE] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
