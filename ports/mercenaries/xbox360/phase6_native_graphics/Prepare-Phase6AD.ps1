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
$baseDir = Join-Path $root "build\phase6_native_graphics\mm166_wrapper_reuse_xdk"
$out = Join-Path $root "build\phase6_native_graphics\av_saved_data_cleanup_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ad-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ad_av_saved_data_cleanup.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AD input: $v"
    }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    (Join-Path $baseDir "phase6ac-manifest.json")
)

$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6ac = Join-Path $p6 "Prepare-Phase6AC.ps1"
    if (-not (Test-Path -LiteralPath $prep6ac)) {
        throw "Phase 6AD baseline missing and Phase 6AC prep was not found: $prep6ac"
    }

    Write-Host "[Phase6AD] Cached Phase 6AC output is missing."
    Write-Host "[Phase6AD] Regenerating Phase 6AC without rebuilding the external solution..."
    & $prep6ac -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6ac-manifest.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AD required input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6ac-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AC" -or
    $baseManifest.build_tag -ne "P6AC-MM166-WRAPPER-REUSE-20261023-A") {
    throw "Phase 6AD Phase 6AC baseline identity mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AD] AV SAVED-DATA + SAFE CLEANUP PASS 1"
Write-Host "[Phase6AD] Hardware boundary: ICALL_SAFE target=80000001 ordinal=1"
Write-Host "[Phase6AD] Hardware frame   : esp=008BF958 saved_esp=008BF95C delta=4 fault=0"
Write-Host "[Phase6AD] Ordinal 1        : AvGetSavedDataAddress, strict zero-arg continuation"
Write-Host "[Phase6AD] Ordinal 4        : paired AvSetSavedDataAddress, strict one-arg continuation"
Write-Host "[Phase6AD] Ordinals 2/3     : remain hard stops"
Write-Host "[Phase6AD] Cleanup          : throttle _msize trace spam only; no guest semantics change"
Write-Host "[Phase6AD] Shards           : fresh phase6ad_* names with reconstruction identity check"
Write-Host "[Phase6AD] Graphics/memory  : inherit Phase 6AC unchanged"

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
    Write-Host "[Phase6AD] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AD] Emitter log tail:"
    Get-Content -LiteralPath $log -Tail 180
    throw "Phase 6AD emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ad-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AD missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AD" -or
    $m.build_tag -ne "P6AD-AV-SAVED-DATA-CLEANUP-20261023-A") {
    throw "Phase 6AD manifest identity mismatch"
}

$ad = $m.phase6ad_av_saved_data_cleanup
if (-not [bool]$ad.phase6ac_hardware_pass -or
    [int]$ad.phase6ac_hardware.next_boundary.ordinal -ne 1 -or
    [int]$ad.phase6ac_hardware.next_boundary.frame_bytes -ne 4 -or
    -not [bool]$ad.av_saved_data.ordinal_1.hardware_observed -or
    -not [bool]$ad.av_saved_data.ordinal_4.prearmed -or
    -not [bool]$ad.av_saved_data.ordinals_2_3_remain_hard_stops -or
    [bool]$ad.safe_cleanup_pass_1.runtime_semantics_changed -or
    $ad.safe_cleanup_pass_1.translated_shard_prefix -ne "phase6ad_") {
    throw "Phase 6AD manifest AV/cleanup gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AD-AV-SAVED-DATA-CLEANUP-20261023-A",
    "static void phase6ad_av_get_saved_data_address(uint32_t savedEsp)",
    "static void phase6ad_av_set_saved_data_address(uint32_t savedEsp)",
    "_phase4c_target == 0x80000001u",
    "_phase4c_target == 0x80000004u",
    "PASS: Phase 6AD ordinal 1 AvGetSavedDataAddress",
    "PASS: Phase 6AD ordinal 4 AvSetSavedDataAddress",
    "s_phase6adAvGetCount != 0u &&",
    "s_phase6adMsizeLogCallCount <= 4u",
    "P6AD SAFE CLEANUP:",
    "P6AD AV/CLEAN SUMMARY:",
    "PHASE 6AD AV SAVED-DATA + CLEANUP RESULT",
    "PASS: Phase 6AD Mm166 wrapper provenance",
    "PASS: Phase 6AD retail graphics pool claim",
    "phase6ad_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AD generated source gate missing: $marker"
    }
}

if ($monolithicText.Contains("else if (_phase4c_target == 0x80000002u)")) {
    throw "Phase 6AD AV ordinal 2 unexpectedly became an automatic continuation"
}
if ($monolithicText.Contains("else if (_phase4c_target == 0x80000003u)")) {
    throw "Phase 6AD AV ordinal 3 unexpectedly became an automatic continuation"
}
if ($envText -notmatch "phase6ad_env_build_cookie") {
    throw "Phase 6AD env cookie gate missing"
}
if ($monolithicText -match "phase6ac_env_build_cookie" -or
    $envText -match "phase6ac_env_build_cookie") {
    throw "Phase 6AD stale Phase 6AC cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AD translated shard output is empty"
}
$wrongShards = @($shards | Where-Object { -not $_.Name.StartsWith("phase6ad_") })
if ($wrongShards.Count -gt 0) {
    throw "Phase 6AD translated shard prefix gate failed: $($wrongShards[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AD] READY"
Write-Host ("[Phase6AD] Generated shards : {0}" -f $shards.Count)
Write-Host "[Phase6AD] Ordinal 1         : strict +4 AvGetSavedDataAddress"
Write-Host "[Phase6AD] Ordinal 4         : strict +8 AvSetSavedDataAddress pre-armed"
Write-Host "[Phase6AD] Ordinals 2/3      : still fenced"
Write-Host "[Phase6AD] _msize logging    : first 4 + powers of two, semantics unchanged"
Write-Host "[Phase6AD] Graphics pool     : inherited 02880000-03EFFFFF"
Write-Host "[Phase6AD] Expected tag      : P6AD-AV-SAVED-DATA-CLEANUP-20261023-A"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AD] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AD-AV-SAVED-DATA-CLEANUP-20261023-A"
        ExpectedEnvCookie = "phase6ad_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ad-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ad-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AD.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AD] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AD] Hardware tag to verify: P6AD-AV-SAVED-DATA-CLEANUP-20261023-A"
    Write-Host ("[Phase6AD] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AD.xex"))
}
else {
    Write-Host "[Phase6AD] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
