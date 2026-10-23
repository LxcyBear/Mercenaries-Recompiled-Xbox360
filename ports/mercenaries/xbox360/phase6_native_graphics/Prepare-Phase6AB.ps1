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
$baseDir = Join-Path $root "build\phase6_native_graphics\post_graphics_pool_frontier_0020fae0_xdk"
$out = Join-Path $root "build\phase6_native_graphics\hal_boot_video_mode_data_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ab-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6ab_hal_boot_video_mode_data.py"
    aaEmitter = Join-Path $p6 "emit_phase6aa_post_graphics_pool_frontier_0020fae0.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AB input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6aa-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    $baseManifestPath
)

$missingBaseFiles = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingBaseFiles.Count -gt 0) {
    $phase6aaPrep = Join-Path $p6 "Prepare-Phase6AA.ps1"
    if (-not (Test-Path -LiteralPath $phase6aaPrep)) {
        throw "Phase 6AB baseline is missing and Phase 6AA prep was not found: $phase6aaPrep"
    }

    Write-Host "[Phase6AB] Cached Phase 6AA output is missing."
    Write-Host "[Phase6AB] Regenerating Phase 6AA-B without rebuilding the external solution..."
    & $phase6aaPrep -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AB required baseline input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content -LiteralPath $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6AA" -or
    $baseManifest.build_tag -ne "P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B") {
    throw "Phase 6AB Phase 6AA baseline identity mismatch"
}

$a = $baseManifest.phase6aa_post_graphics_pool_frontier
if ($a.root -ne "0x0020FAE0" -or
    -not [bool]$a.graphics_pool_model_inherited_unchanged) {
    throw "Phase 6AB inherited Phase 6AA proof mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AB] HAL BOOT VIDEO MODE DATA EXPORT"
Write-Host "[Phase6AB] Phase 6AA hardware: sub_0020FAE0 crossed successfully"
Write-Host "[Phase6AB] Next boundary: GUEST_FAULT READ32 80000164 caller=0023A3CE"
Write-Host "[Phase6AB] 80000164 = kernel ordinal 356 = HalBootSMCVideoMode DATA export"
Write-Host "[Phase6AB] Upstream kernel-data base/offset: 0087E000 + 00000098 = 0087E098"
Write-Host "[Phase6AB] Canonical initial value: 00000000"
Write-Host "[Phase6AB] Preserve 6AA renderer closure, recovery helpers and 02880000-03EFFFFF graphics pool unchanged"
Write-Host "[Phase6AB] Purple remains reserved for genuine NV2A MMIO/VRAM"

$args = @(
    "--base-dir",$baseDir,
    "--phase6aa-emitter",$paths.aaEmitter,
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
    Write-Host "[Phase6AB] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AB] Emitter log tail:"
    $tail = @(Get-Content -LiteralPath $log -Tail 140)
    $tail | ForEach-Object { Write-Host $_ }

    $reason = @(
        $tail | Where-Object {
            ($_ -match "\[Phase6AB\]") -and
            ($_ -notmatch "CategoryInfo|FullyQualifiedErrorId")
        }
    )
    if (@($reason).Count -gt 0) {
        $primary = [string]@($reason)[@($reason).Count - 1]
    }
    else {
        $primary = "see $log"
    }
    throw ("Phase 6AB emission/preflight failed (exit {0}); PRIMARY: {1}" -f $rc, $primary)
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ab-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AB missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AB" -or
    $m.build_tag -ne "P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A") {
    throw "Phase 6AB manifest identity mismatch"
}

$z = $m.phase6ab_hal_boot_video_mode
if (-not [bool]$z.phase6aa_hardware_pass -or
    [int]$z.data_export.ordinal -ne 356 -or
    $z.data_export.name -ne "HalBootSMCVideoMode" -or
    $z.data_export.guest_va -ne "0x0087E098" -or
    $z.data_export.initial_value -ne "0x00000000" -or
    [int]$z.expected_retail_import_count -ne 1 -or
    -not [bool]$z.graphics_pool_model_inherited_unchanged -or
    -not [bool]$z.phase6aa_renderer_support_inherited_unchanged) {
    throw "Phase 6AB manifest data-export gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A",
    "case 356u: return 0x0087E098u; /* HalBootSMCVideoMode ULONG */",
    "GUEST_WRITE32(0x0087E098u, 0u);",
    "DWORD seen356 = 0u;",
    "if (ordinal == 356u) ++seen356;",
    "seen356 != 1u",
    "relocated != (7u + seen41 + seen42)",
    "GUEST_READ32(0x0087E098u) != 0u",
    "PASS: Phase 6AB HalBootSMCVideoMode initialized ordinal=356 va=0087E098 value=00000000",
    "startup data imports 40/41/42(optional)/156/164/322/324/326/356 relocated",
    "case 0x0020FAE0u:",
    "s_phase6aaRootEntered = 1;",
    "PASS: Phase 6AB retail graphics pool claim",
    "static uint32_t recomp_renderer_test_oom(uint32_t multisample)",
    "static void recomp_renderer_recovery_report(uint32_t result, uint32_t stage)",
    "PHASE4C_BOUNDARY_RENDERER_FATAL = 19",
    "P6AB HALDATA SUMMARY:",
    "PHASE 6AB HAL BOOT VIDEO MODE RESULT",
    "phase6ab_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AB generated monolithic gate missing: $marker"
    }
}

if ($envText -notmatch "phase6ab_env_build_cookie") {
    throw "Phase 6AB env cookie gate missing"
}
if ($monolithicText -match "phase6aa_env_build_cookie" -or
    $envText -match "phase6aa_env_build_cookie") {
    throw "Phase 6AB stale Phase 6AA cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AB translated shard output is empty"
}

# The translated 6AA root remains inside the shards; prove it survived the
# minimal data-export delta unchanged.
$rootMarkerFoundInShard = $false
foreach ($shard in $shards) {
    if ((Get-Content -LiteralPath $shard.FullName -Raw).Contains("s_phase6aaRootEntered = 1;")) {
        $rootMarkerFoundInShard = $true
        break
    }
}
if (-not $rootMarkerFoundInShard) {
    throw "Phase 6AB inherited translated-root shard marker missing"
}

Write-Host ""
Write-Host "[Phase6AB] READY"
Write-Host "[Phase6AB] Data export                   : ordinal 356 HalBootSMCVideoMode"
Write-Host "[Phase6AB] Guest VA                      : 0087E098"
Write-Host "[Phase6AB] Initial value                 : 00000000"
Write-Host "[Phase6AB] Expected retail import count  : 1"
Write-Host ("[Phase6AB] Generated shards             : {0}" -f $shards.Count)
Write-Host "[Phase6AB] Graphics pool                 : inherited 02880000-03EFFFFF"
Write-Host "[Phase6AB] Renderer root                 : inherited exact 0020FAE0"
Write-Host "[Phase6AB] Expected tag                  : P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AB] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A"
        ExpectedEnvCookie = "phase6ab_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ab-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ab-vs2017-build.log")
    }

    & $paths.build @buildArgs
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Phase 6AB Visual Studio 2017/Xbox 360 build failed (exit $LASTEXITCODE)"
    }

    Write-Host ""
    Write-Host "[Phase6AB] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AB] Hardware tag to verify: P6AB-HAL-BOOT-VIDEO-MODE-DATA-20261023-A"
}
else {
    Write-Host "[Phase6AB] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
