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
$baseDir = Join-Path $root "build\phase6_native_graphics\graphics_pool_mm166_xdk"
$out = Join-Path $root "build\phase6_native_graphics\graphics_pool_dual_frontier_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6z-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6z_graphics_pool_dual_frontier.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6Z input: $v"
    }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    (Join-Path $baseDir "phase6y-manifest.json")
)
$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6y = Join-Path $p6 "Prepare-Phase6Y.ps1"
    if (-not (Test-Path -LiteralPath $prep6y)) {
        throw "Phase 6Z baseline missing and Phase 6Y prep was not found: $prep6y"
    }
    Write-Host "[Phase6Z] Cached Phase 6Y output is missing."
    Write-Host "[Phase6Z] Regenerating Phase 6Y without building the external solution..."
    & $prep6y -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6y-manifest.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6Z required input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6y-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6Y" -or
    $baseManifest.build_tag -ne "P6Y-GFXPOOL-MM166-FRAME-20261023-B") {
    throw "Phase 6Z Phase 6Y baseline identity mismatch"
}

$proof = $baseManifest.phase6y_mm166_frame_repair.generated_wrapper_proof
if ([int]$proof.canonical_kernel_frame_bytes -ne 24 -or
    [int]$proof.wrapper_spill_bytes -ne 4 -or
    [int]$proof.observed_saved_esp_delta_proven -ne 28) {
    throw "Phase 6Z inherited Phase 6Y ABI proof mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6Z] RETAIL GRAPHICS-POOL DUAL-FRONTIER REPAIR"
Write-Host "[Phase6Z] Phase 6Y hardware: MmAllocateContiguousMemoryEx 01680000 -> NULL, error 8"
Write-Host "[Phase6Z] Phase 6Y next direct 0020FAE0 is treated as allocation-failure-path evidence and is NOT packed"
Write-Host "[Phase6Z] Existing VM page frontier     : 03F00000"
Write-Host "[Phase6Z] Retail graphics request       : 01680000 (22.5 MiB)"
Write-Host "[Phase6Z] Expected graphics-pool base   : 02880000"
Write-Host "[Phase6Z] Prior synthetic heap ceiling  : 028C0000"
Write-Host "[Phase6Z] Free title-heap tail to trim  : 00040000 (256 KiB)"
Write-Host "[Phase6Z] Policy: prove free tail + unmanaged pages before carving; never move live heap allocations"
Write-Host "[Phase6Z] Purple remains reserved for genuine NV2A MMIO/VRAM"

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
    Write-Host "[Phase6Z] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6Z] The Phase 6Y baseline or dual-frontier memory invariants changed."
    Write-Host "[Phase6Z] Emitter log tail:"
    Get-Content -LiteralPath $log -Tail 140
    throw "Phase 6Z emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6z-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6Z missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6Z" -or
    $m.build_tag -ne "P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A") {
    throw "Phase 6Z manifest identity mismatch"
}

$z = $m.phase6z_graphics_pool_dual_frontier
if ($z.memory_model.old_page_next -ne "0x03F00000" -or
    $z.memory_model.retail_pool_size -ne "0x01680000" -or
    $z.memory_model.expected_pool_base -ne "0x02880000" -or
    $z.memory_model.free_title_heap_tail_trim -ne "0x00040000" -or
    $z.failure_frontier_policy -notmatch "do not pack 0x0020FAE0") {
    throw "Phase 6Z manifest dual-frontier gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A",
    "PASS: Phase 6Z retail graphics pool claim",
    "oldPageNext != 0x03F00000u",
    "base != 0x02880000u",
    "PHASE4C_TITLE_HEAP_END - base",
    "prot==0x00000404u",
    "graphics_claim=%u",
    "resumeEsp=c+24u",
    "phase6z_env_build_cookie",
    "#define PHASE4C_EXEC_BUDGET 2000000u",
    "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)"
)) {
    if (-not $mainText.Contains($marker)) {
        throw "Phase 6Z generated main gate missing: $marker"
    }
}
if ($envText -notmatch "phase6z_env_build_cookie") {
    throw "Phase 6Z env cookie gate missing"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6Z translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6Z] READY"
Write-Host ("[Phase6Z] Generated shards              : {0}" -f $shards.Count)
Write-Host "[Phase6Z] Graphics pool target          : 02880000-03EFFFFF"
Write-Host "[Phase6Z] Existing VM reserve remains   : 03F00000-03FFFFFF"
Write-Host "[Phase6Z] Old failure frontier 0020FAE0 : NOT PACKED"
Write-Host "[Phase6Z] Expected tag                  : P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6Z] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A"
        ExpectedEnvCookie = "phase6z_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6z-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6z-vs2017-build.log")
    }
    & $paths.build @buildArgs
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Phase 6Z Visual Studio 2017/Xbox 360 build failed (exit $LASTEXITCODE)"
    }

    Write-Host ""
    Write-Host "[Phase6Z] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6Z] Hardware tag to verify: P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A"
}
else {
    Write-Host "[Phase6Z] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
