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

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$out = Join-Path $root "build\phase6_native_graphics\read32_site_probe_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6al-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6al_read32_site_probe.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    prep6aj = Join-Path $p6 "Prepare-Phase6AJ.ps1"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v -PathType Leaf)) {
        throw "Missing Phase 6AL input: $v"
    }
}

$baseManifest = Join-Path $baseDir "phase6aj-manifest.json"
$baseMain = Join-Path $baseDir "main_monolithic.cpp"
$baseEnv = Join-Path $baseDir "phase5_env.cpp"

if (-not (Test-Path -LiteralPath $baseManifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseMain -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseEnv -PathType Leaf)) {
    Write-Host "[Phase6AL] Cached Phase 6AJ-A sources are missing."
    Write-Host "[Phase6AL] Regenerating 6AJ-A source cache without VS2017..."
    & $paths.prep6aj -SkipSolutionBuild
}

foreach ($f in @($baseManifest,$baseMain,$baseEnv)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
        throw "Phase 6AL required Phase 6AJ-A input missing: $f"
    }
}

$bm = Get-Content -LiteralPath $baseManifest -Raw | ConvertFrom-Json
if ($bm.phase -ne "6AJ" -or
    $bm.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AL Phase 6AJ-A baseline identity mismatch"
}

$aj = $bm.phase6aj_d3d_orange_source_probe
if (-not [bool]$aj.probe_only -or
    [bool]$aj.guest_semantics_changed -or
    $aj.phase6ai_hardware.next_boundary.guest -ne "0x80000004") {
    throw "Phase 6AL inherited Phase 6AJ model drift"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AL] EXACT TRANSLATED READ32 SITE PROBE"
Write-Host "[Phase6AL] 6AJ-A hardware      : return-path step 10 then READ32 80000004"
Write-Host "[Phase6AL] 6AK-A forensic      : deferred caller 0023A3CE has no 0028E700 call"
Write-Host "[Phase6AL] Probe policy         : wrap translated GUEST_READ32 sites only"
Write-Host "[Phase6AL] Fault behavior       : log exact function/site then escape immediately"
Write-Host "[Phase6AL] KSEG/MMIO/VRAM       : unchanged / still hard fenced"
Write-Host ""

& $python -m py_compile $paths.emitter
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AL emitter Python syntax check failed"
}
Write-Host "[Phase6AL] Emitter syntax       : PASS"

$emitArgs = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $paths.emitter @emitArgs 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AL] PREP STOPPED BEFORE BUILD."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 220 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AL emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6al-manifest.json"
$siteMap = Join-Path $out "phase6al-read32-site-map.txt"
$siteMapJson = Join-Path $out "phase6al-read32-site-map.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$siteMap,$siteMapJson,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AL missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AL" -or
    $m.build_tag -ne "P6AL-READ32-SITE-PROBE-20261023-A") {
    throw "Phase 6AL manifest identity mismatch"
}

$al = $m.phase6al_read32_site_probe
if (-not [bool]$al.probe_only -or
    [bool]$al.guest_memory_semantics_changed -or
    -not [bool]$al.boundary_timing_changed -or
    [int]$al.instrumented_read32_sites -lt 1 -or
    $al.source_layout.shard_prefix -ne "phase6al_") {
    throw "Phase 6AL manifest probe gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AL-READ32-SITE-PROBE-20261023-A",
    "P6AL READ32 FAULT SITE:",
    "phase6al_read32_site(",
    "phase6al_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AL generated source gate missing: $marker"
    }
}

if ($monolithicText.Contains("phase6aj_env_build_cookie") -or
    $envText.Contains("phase6aj_env_build_cookie")) {
    throw "Phase 6AL stale Phase 6AJ cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AL translated shard output is empty"
}
$wrong = @($shards | Where-Object { -not $_.Name.StartsWith("phase6al_") })
if ($wrong.Count -gt 0) {
    throw "Phase 6AL translated shard prefix gate failed: $($wrong[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AL] READY"
Write-Host ("[Phase6AL] Instrumented READ32 sites : {0}" -f [int]$al.instrumented_read32_sites)
Write-Host ("[Phase6AL] Generated shards          : {0}" -f $shards.Count)
Write-Host "[Phase6AL] Guest memory semantics    : UNCHANGED"
Write-Host "[Phase6AL] Boundary timing           : IMMEDIATE ON FIRST LATCHED READ32 FAULT"
Write-Host "[Phase6AL] Expected tag              : P6AL-READ32-SITE-PROBE-20261023-A"
Write-Host "[Phase6AL] Hardware money line       : P6AL READ32 FAULT SITE: func=... line=... address=..."
Write-Host ("[Phase6AL] Site map                  : {0}" -f $siteMap)

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AL] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AL-READ32-SITE-PROBE-20261023-A"
        ExpectedEnvCookie = "phase6al_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6al-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6al-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AL-A.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AL] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AL] Hardware tag to verify: P6AL-READ32-SITE-PROBE-20261023-A"
    Write-Host ("[Phase6AL] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AL-A.xex"))
    Write-Host ("[Phase6AL] KEEP THIS SITE MAP: {0}" -f $siteMap)
}
else {
    Write-Host "[Phase6AL] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
