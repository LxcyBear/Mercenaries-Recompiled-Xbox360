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
$emitter = Join-Path $PSScriptRoot "emit_phase6at_d3d_dual_frontier_continue.py"
$prep6ar = Join-Path $PSScriptRoot "Prepare-Phase6AR.ps1"
$builder = Join-Path $PSScriptRoot "Invoke-VS17Xbox360Build.ps1"

$baseDir = Join-Path $root "build\phase6_native_graphics\post_create_state_init_xdk"
$out = Join-Path $root "build\phase6_native_graphics\d3d_dual_frontier_continue_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6at-emitter.log"

foreach ($path in @($python,$baseEmitter,$emitter,$prep6ar,$builder)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Missing Phase 6AT input: $path"
    }
}

$baseManifest = Join-Path $baseDir "phase6ar-manifest.json"
$baseMain = Join-Path $baseDir "main_monolithic.cpp"
$baseEnv = Join-Path $baseDir "phase5_env.cpp"

if (-not (Test-Path -LiteralPath $baseManifest -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseMain -PathType Leaf) -or
    -not (Test-Path -LiteralPath $baseEnv -PathType Leaf)) {
    Write-Host "[Phase6AT] Cached Phase 6AR-A output is missing."
    Write-Host "[Phase6AT] Regenerating 6AR-A sources only; VS2017 remains skipped."
    & $prep6ar -SkipSolutionBuild
}

foreach ($path in @($baseManifest,$baseMain,$baseEnv)) {
    if (-not (Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "Phase 6AT could not obtain cached Phase 6AR-A input: $path"
    }
}

$m = Get-Content -LiteralPath $baseManifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AR" -or
    $m.build_tag -ne "P6AR-POST-CREATE-STATE-INIT-20261024-A") {
    throw "Phase 6AT cached Phase 6AR-A baseline identity mismatch"
}

Write-Host "[Phase6AT] D3D DUAL-FRONTIER CONTINUATION REPAIR"
Write-Host "[Phase6AT] 6AR hardware        : old orange fault eliminated"
Write-Host "[Phase6AT] 6AR D3D state      : +1A10 count 0 -> 2"
Write-Host "[Phase6AT] 6AS allocator proof: fixed heap-end check rejects every later page allocation"
Write-Host "[Phase6AT] Repair scope        : active sub_0028F9E0 only"
Write-Host "[Phase6AT] Normal allocator    : always attempted first"
Write-Host "[Phase6AT] Tail fallback       : exact current free heap tail only"
Write-Host "[Phase6AT] KSEG/MMIO/VRAM      : unchanged / hard fenced"
Write-Host ""

& $python -m py_compile $emitter
if ($LASTEXITCODE -ne 0) {
    throw "Phase 6AT emitter Python syntax check failed"
}
Write-Host "[Phase6AT] Emitter syntax      : PASS"

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
    Write-Host "[Phase6AT] PREP STOPPED BEFORE BUILD."
    if (Test-Path -LiteralPath $log -PathType Leaf) {
        Get-Content -LiteralPath $log -Tail 320 | ForEach-Object { Write-Host $_ }
    }
    throw "Phase 6AT emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$mono = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6at-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($path in @($main,$mono,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $path)) {
        throw "Phase 6AT missing output: $path"
    }
}

$r = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($r.phase -ne "6AT" -or
    $r.build_tag -ne "P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-A") {
    throw "Phase 6AT manifest identity mismatch"
}

$at = $r.phase6at_d3d_dual_frontier_continue
if (-not [bool]$at.repair.normal_allocator_first -or
    $at.repair.scope -ne "only while sub_0028F9E0 is active" -or
    [int]$at.repair.ordinal -ne 166 -or
    -not [bool]$at.repair.claim_only_current_free_heap_tail -or
    -not [bool]$at.repair.reject_live_heap_overlap -or
    -not [bool]$at.repair.require_unmanaged_pages -or
    [bool]$at.kseg_fence_relaxed -or
    [bool]$at.nv2a_mmio_vram_policy_changed) {
    throw "Phase 6AT manifest repair gate mismatch"
}

$monoText = Get-Content -LiteralPath $mono -Raw
$envText = Get-Content -LiteralPath $env -Raw
foreach ($marker in @(
    "P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-A",
    "phase6at_claim_post_create_tail(",
    "s_phase6atPostCreateInitActive = 1u;",
    "post_init_tail_claim=%u",
    "P6AT D3D TAIL CLAIM:",
    "P6AT POST-CREATE D3D INIT:",
    "phase6at_env_build_cookie"
)) {
    if (-not $monoText.Contains($marker)) {
        throw "Phase 6AT generated source gate missing: $marker"
    }
}

if ($monoText.Contains("phase6ar_env_build_cookie") -or
    $envText.Contains("phase6ar_env_build_cookie")) {
    throw "Phase 6AT stale Phase 6AR cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AT translated shard output is empty"
}
$wrong = @($shards | Where-Object { -not $_.Name.StartsWith("phase6at_") })
if ($wrong.Count -gt 0) {
    throw "Phase 6AT translated shard prefix gate failed: $($wrong[0].Name)"
}

Write-Host ""
Write-Host "[Phase6AT] READY"
Write-Host ("[Phase6AT] Generated shards      : {0}" -f $shards.Count)
Write-Host "[Phase6AT] Normal allocator      : FIRST"
Write-Host "[Phase6AT] Tail fallback scope   : active sub_0028F9E0 only"
Write-Host "[Phase6AT] Heap safety           : free-tail only / no live overlap"
Write-Host "[Phase6AT] Expected tag          : P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-A"
Write-Host "[Phase6AT] Hardware money line 1 : PASS: Phase 6AT post-create tail claim ..."
Write-Host "[Phase6AT] Hardware money line 2 : P6AT POST-CREATE D3D INIT: ..."

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AT] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-A"
        ExpectedEnvCookie = "phase6at_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6at-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6at-vs2017-build.log")
        PublishedXex = (Join-Path $out "Mercenaries-PPC-Port-P6AT-A.xex")
    }

    & $builder @buildArgs

    Write-Host ""
    Write-Host "[Phase6AT] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AT] Hardware tag to verify: P6AT-D3D-DUAL-FRONTIER-CONTINUE-20261024-A"
    Write-Host ("[Phase6AT] COPY THIS XEX: {0}" -f (Join-Path $out "Mercenaries-PPC-Port-P6AT-A.xex"))
}
else {
    Write-Host "[Phase6AT] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
