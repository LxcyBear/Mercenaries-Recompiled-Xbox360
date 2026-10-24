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

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_internal_device_global_xdk"
$out = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6aj-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6aj_d3d_orange_source_probe.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    prep6ai = Join-Path $p6 "Prepare-Phase6AI.ps1"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}

foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v -PathType Leaf)) {
        throw "Missing Phase 6AJ input: $v"
    }
}

$baseManifest = Join-Path $baseDir "phase6ai-manifest.json"
$baseMain = Join-Path $baseDir "main_monolithic.cpp"
$baseEnv = Join-Path $baseDir "phase5_env.cpp"

if (-not (Test-Path -LiteralPath $baseManifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseMain -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseEnv -PathType Leaf)) {
    Write-Host "[Phase6AJ] Cached Phase 6AI-D sources are missing."
    Write-Host "[Phase6AJ] Regenerating Phase 6AI-D source cache without VS2017..."
    & $paths.prep6ai -SkipSolutionBuild
}

foreach ($f in @($baseManifest,$baseMain,$baseEnv)) {
    if (-not (Test-Path -LiteralPath $f -PathType Leaf)) {
        throw "Phase 6AJ required Phase 6AI-D input missing: $f"
    }
}

$bm = Get-Content -LiteralPath $baseManifest -Raw | ConvertFrom-Json
if ($bm.phase -ne "6AI" -or
    $bm.build_tag -ne "P6AI-D3D-INTERNAL-DEVICE-GLOBAL-20261023-D") {
    throw "Phase 6AJ Phase 6AI-D baseline identity mismatch"
}

$ai = $bm.phase6ai_internal_d3d_device_global
if ($ai.forensic.root -ne "0x0028E700" -or
    $ai.repair.createdevice_internal_global -ne "0x00299378" -or
    $ai.repair.published_value -ne "0x00299380") {
    throw "Phase 6AJ inherited Phase 6AI model drift"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AJ] D3D ORANGE SOURCE PROBE"
Write-Host "[Phase6AJ] 6AI-D hardware      : internal device repair PASS"
Write-Host "[Phase6AJ] Remaining boundary  : READ32 80000004"
Write-Host "[Phase6AJ] Probe root          : 0028E700"
Write-Host "[Phase6AJ] Probe policy        : host-only step latch; NO guest semantic changes"
Write-Host "[Phase6AJ] KSEG/MMIO/VRAM      : unchanged / still hard fenced"
Write-Host ""

& $python -m py_compile $paths.emitter
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AJ emitter Python syntax check failed"
}
Write-Host "[Phase6AJ] Emitter syntax      : PASS"

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
    Write-Host "[Phase6AJ] PREP STOPPED BEFORE BUILD."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 220 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AJ emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6aj-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AJ missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AJ manifest identity mismatch"
}

$aj = $m.phase6aj_d3d_orange_source_probe
if (-not [bool]$aj.phase6ai_hardware_pass -or
    -not [bool]$aj.probe_only -or
    [bool]$aj.guest_semantics_changed -or
    $aj.phase6ai_hardware.root_this -ne "0x00299380" -or
    $aj.phase6ai_hardware.internal_device_global -ne "0x00299380" -or
    $aj.phase6ai_hardware.next_boundary.guest -ne "0x80000004" -or
    $aj.source_layout.shard_prefix -ne "phase6aj_") {
    throw "Phase 6AJ manifest probe gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$monolithicText = Get-Content -LiteralPath $monolithic -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A",
    "static DWORD s_phase6ajD3DProbeStep = 0u;",
    "P6AJ D3D FAULT PROBE: step=%u a=%08X b=%08X c=%08X",
    "P6AJ D3D SOURCE PROBE: root_calls=%u last_step=%u a=%08X b=%08X c=%08X",
    "s_phase6ajD3DProbeStep = 1u;",
    "s_phase6ajD3DProbeStep = 4u;",
    "s_phase6ajD3DProbeStep = 6u;",
    "s_phase6ajD3DProbeStep = 8u;",
    "s_phase6ajD3DProbeStep = 9u;",
    "phase6aj_env_build_cookie"
)) {
    if (-not $monolithicText.Contains($marker)) {
        throw "Phase 6AJ generated source gate missing: $marker"
    }
}

if ($monolithicText.Contains("phase6ai_env_build_cookie") -or
    $envText.Contains("phase6ai_env_build_cookie")) {
    throw "Phase 6AJ stale Phase 6AI cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AJ translated shard output is empty"
}
$wrong = @($shards | Where-Object { -not $_.Name.StartsWith("phase6aj_") })
if ($wrong.Count -gt 0) {
    throw "Phase 6AJ translated shard prefix gate failed: $($wrong[0].Name)"
}

$probeInShard = $false
foreach ($shard in $shards) {
    if ((Get-Content -LiteralPath $shard.FullName -Raw).Contains("s_phase6ajD3DProbeStep = 9u;")) {
        $probeInShard = $true
        break
    }
}
if (-not $probeInShard) {
    throw "Phase 6AJ root source probe did not survive sharding"
}

Write-Host ""
Write-Host "[Phase6AJ] READY"
Write-Host ("[Phase6AJ] Generated shards        : {0}" -f $shards.Count)
Write-Host "[Phase6AJ] Probe-only build         : YES"
Write-Host "[Phase6AJ] Guest semantics changed  : NO"
Write-Host "[Phase6AJ] Expected tag             : P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
Write-Host "[Phase6AJ] Hardware money line      : P6AJ D3D FAULT PROBE: step=..."

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AJ] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
        ExpectedEnvCookie = "phase6aj_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6aj-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6aj-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AJ-A.xex")
    }

    & $paths.build @buildArgs

    Write-Host ""
    Write-Host "[Phase6AJ] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AJ] Hardware tag to verify: P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A"
    Write-Host ("[Phase6AJ] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AJ-A.xex"))
}
else {
    Write-Host "[Phase6AJ] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
