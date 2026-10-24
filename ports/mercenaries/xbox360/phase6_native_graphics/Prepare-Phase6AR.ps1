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
$python = Join-Path $root ".venv\Scripts\python.exe"
$baseEmitter = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$emitter = Join-Path $PSScriptRoot "emit_phase6ar_post_create_state_init.py"
$prep6aj = Join-Path $PSScriptRoot "Prepare-Phase6AJ.ps1"
$builder = Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\d3d_orange_source_probe_xdk"
$out = Join-Path $root "build\phase6_native_graphics\post_create_state_init_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6ar-emitter.log"

foreach ($path in @($python,$baseEmitter,$emitter,$prep6aj,$builder)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AR input: $path"
    }
}

$baseManifest = Join-Path $baseDir "phase6aj-manifest.json"
$baseMain = Join-Path $baseDir "main_monolithic.cpp"
$baseEnv = Join-Path $baseDir "phase5_env.cpp"

if (-not (Test-Path -LiteralPath $baseManifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseMain -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseEnv -PathType Leaf)) {
    Write-Host "[Phase6AR] Cached Phase 6AJ-A source output is missing."
    Write-Host "[Phase6AR] Regenerating 6AJ-A sources only; VS2017 remains skipped."
    & $prep6aj -SkipSolutionBuild
}

foreach ($path in @($baseManifest,$baseMain,$baseEnv)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AR could not obtain cached Phase 6AJ-A input: $path"
    }
}

$m = Get-Content -LiteralPath $baseManifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AJ" -or
    $m.build_tag -ne "P6AJ-D3D-ORANGE-SOURCE-PROBE-20261023-A") {
    throw "Phase 6AR cached Phase 6AJ-A baseline identity mismatch"
}

Write-Host "[Phase6AR] POST-CREATE D3D STATE INITIALIZER REPAIR"
Write-Host "[Phase6AR] 6AN hardware      : +1A10 count=0 -> backward underflow"
Write-Host "[Phase6AR] 6AO writer proof : sole +1A10 writer = sub_0028F9E0"
Write-Host "[Phase6AR] 6AP/6AQ ABI proof: retail 0028FF80 calls 0028F9E0 directly"
Write-Host "[Phase6AR] Repair ABI        : ECX=00299380, arg1=live CreateDevice pp"
Write-Host "[Phase6AR] Parent 0028FF80   : NOT restored (contains KSEG writes)"
Write-Host "[Phase6AR] KSEG/MMIO/VRAM    : unchanged / hard fenced"
Write-Host ""

& $python -m py_compile $emitter
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AR emitter Python syntax check failed"
}
Write-Host "[Phase6AR] Emitter syntax    : PASS"

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

$argsList = @(
    "--base-dir",$baseDir,
    "--base-emitter",$baseEmitter,
    "--out-dir",$out
)

$old = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    & $python $emitter @argsList 2>&1 | Tee-Object -FilePath $log
    $rc = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $old
}

if ($rc -ne 0) {
    Write-Host ""
    Write-Host "[Phase6AR] PREP STOPPED BEFORE BUILD."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 320 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AR emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$mono = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6ar-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($path in @($main,$mono,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Phase 6AR missing output: $path"
    }
}

$r = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($r.phase -ne "6AR" -or
    $r.build_tag -ne "P6AR-POST-CREATE-STATE-INIT-20261024-A") {
    throw "Phase 6AR manifest identity mismatch"
}

$ar = $r.phase6ar_post_create_state_init
if ($ar.repair.function -ne "sub_0028F9E0" -or
    $ar.repair.this -ne "0x00299380" -or
    [bool]$ar.repair.restore_parent_0x0028FF80 -or
    [bool]$ar.kseg_fence_relaxed -or
    [bool]$ar.nv2a_mmio_vram_policy_changed) {
    throw "Phase 6AR manifest repair gate mismatch"
}

$monoText = Get-Content -LiteralPath $mono -Raw
$envText = Get-Content -LiteralPath $env -Raw
foreach ($marker in @(
    "P6AR-POST-CREATE-STATE-INIT-20261024-A",
    "P6AR POST-CREATE D3D INIT:",
    "sub_0028F9E0();",
    "s_phase6arCountAfter == 0u",
    "s_phase6arSlot1After == 0u",
    "phase6ar_env_build_cookie"
)) {
    if (-not $monoText.Contains($marker)) {
        throw "Phase 6AR generated source gate missing: $marker"
    }
}

if ($monoText.Contains("phase6aj_env_build_cookie") -or
    $envText.Contains("phase6aj_env_build_cookie")) {
    throw "Phase 6AR stale Phase 6AJ cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AR translated shard output is empty"
}
$wrong = @($shards | Where-Object { -not $_.Name.StartsWith("phase6ar_") })
if ($wrong.Count -gt 0) {
    throw "Phase 6AR translated shard prefix gate failed: $($wrong[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AR] READY"
Write-Host ("[Phase6AR] Generated shards      : {0}" -f $shards.Count)
Write-Host "[Phase6AR] Direct helper audit   : PASS"
Write-Host "[Phase6AR] Parent 0028FF80       : NOT RESTORED"
Write-Host "[Phase6AR] Expected tag          : P6AR-POST-CREATE-STATE-INIT-20261024-A"
Write-Host "[Phase6AR] Hardware money line  : P6AR POST-CREATE D3D INIT: ..."

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AR] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AR-POST-CREATE-STATE-INIT-20261024-A"
        ExpectedEnvCookie = "phase6ar_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6ar-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6ar-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AR-A.xex")
    }

    & $builder @buildArgs

    Write-Host ""
    Write-Host "[Phase6AR] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AR] Hardware tag to verify: P6AR-POST-CREATE-STATE-INIT-20261024-A"
    Write-Host ("[Phase6AR] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AR-A.xex"))
}
else {
    Write-Host "[Phase6AR] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
