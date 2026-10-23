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
$stage3 = Join-Path $root "build\phase3n_final_abi_scale"
$baseDir = Join-Path $root "build\phase6_native_graphics\graphics_pool_frontier_0020f9c0_xdk"
$out = Join-Path $root "build\phase6_native_graphics\graphics_pool_mm166_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6y-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6y_mm166_frame.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6Y input: $v"
    }
}

$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    (Join-Path $baseDir "phase6x-manifest.json")
)
$missing = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missing.Count -gt 0) {
    $prep6x = Join-Path $p6 "Prepare-Phase6X.ps1"
    if (-not (Test-Path -LiteralPath $prep6x)) {
        throw "Phase 6Y baseline missing and Phase 6X prep was not found: $prep6x"
    }
    Write-Host "[Phase6Y] Cached Phase 6X output is missing."
    Write-Host "[Phase6Y] Regenerating Phase 6X without building the external solution..."
    & $prep6x -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "phase6x-manifest.json"),
    (Join-Path $stage3 "runtime\gen"),
    (Join-Path $stage3 "analysis\disasm\functions.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6Y required input missing after regeneration: $f"
    }
}

$baseManifest = Get-Content (Join-Path $baseDir "phase6x-manifest.json") -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6X" -or
    $baseManifest.build_tag -ne "P6X-GFXPOOL-FRONTIER-0020F9C0-20261023-A") {
    throw "Phase 6Y Phase 6X baseline identity mismatch"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6Y] GRAPHICS-POOL MM166 ABI REPAIR"
Write-Host "[Phase6Y] Hardware: KERNEL_FRAME target=800000A6 ordinal=166"
Write-Host "[Phase6Y] Hardware frame: esp=008BF9E0 saved_esp=008BF9FC delta=28"
Write-Host "[Phase6Y] Hardware state: ECX=01680000, ticks=670780 trace=179922 fault=0"
Write-Host "[Phase6Y] Offline gate: sub_0022AEE9 must prove _icall_esp snapshot + saved ESI + five Mm166 args + dummy return"
Write-Host "[Phase6Y] Runtime gate: +28 repair only for retail size 01680000 with c+24 spill == live ESI"
Write-Host "[Phase6Y] Stack resume: consume canonical 24-byte Mm166 frame; preserve saved ESI for wrapper POP"
Write-Host "[Phase6Y] Purple remains reserved for genuine NV2A MMIO/VRAM"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--generated-root",(Join-Path $stage3 "runtime\gen"),
    "--functions",(Join-Path $stage3 "analysis\disasm\functions.json"),
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
    Write-Host "[Phase6Y] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6Y] The local generated wrapper did not prove the hardware-observed ABI shape, or another source gate changed."
    Write-Host "[Phase6Y] Emitter log tail:"
    Get-Content -LiteralPath $log -Tail 120
    throw "Phase 6Y emission/preflight failed (exit $rc)"
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6y-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6Y missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6Y" -or
    $m.build_tag -ne "P6Y-GFXPOOL-MM166-FRAME-20261023-B") {
    throw "Phase 6Y manifest identity mismatch"
}

$y = $m.phase6y_mm166_frame_repair
if ([int]$y.boundary.ordinal -ne 166 -or
    [int]$y.boundary.frame_bytes -ne 28 -or
    [int]$y.generated_wrapper_proof.observed_saved_esp_delta_proven -ne 28 -or
    $y.retail_pool_size -ne "0x01680000") {
    throw "Phase 6Y manifest ABI proof gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6Y-GFXPOOL-MM166-FRAME-20261023-B",
    "PASS: Phase 6Y ordinal 166 MmAllocateContiguousMemoryEx",
    "frameBytes!=24u && frameBytes!=28u",
    "size!=0x01680000u || extra!=g_esi",
    "resumeEsp=c+24u",
    "phase6y_env_build_cookie",
    "#define PHASE4C_EXEC_BUDGET 2000000u",
    "#define PHASE4C_TITLE_HEAP_END   (PHASE4C_TITLE_HEAP_BASE + 0x02000000u)"
)) {
    if (-not $mainText.Contains($marker)) {
        throw "Phase 6Y generated main gate missing: $marker"
    }
}
if ($envText -notmatch "phase6y_env_build_cookie") {
    throw "Phase 6Y env cookie gate missing"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6Y translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6Y] READY"
Write-Host ("[Phase6Y] Generated shards              : {0}" -f $shards.Count)
Write-Host "[Phase6Y] MM166 canonical frame         : +24"
Write-Host "[Phase6Y] Hardware-proven wrapper frame : +28 (= +24 Mm166 + 4-byte saved ESI)"
Write-Host "[Phase6Y] Repair scope                  : retail 01680000 + verified saved-ESI spill only"
Write-Host "[Phase6Y] Expected tag                  : P6Y-GFXPOOL-MM166-FRAME-20261023-B"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6Y] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6Y-GFXPOOL-MM166-FRAME-20261023-B"
        ExpectedEnvCookie = "phase6y_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6y-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6y-vs2017-build.log")
    }
    & $paths.build @buildArgs
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Phase 6Y Visual Studio 2017/Xbox 360 build failed (exit $LASTEXITCODE)"
    }

    Write-Host ""
    Write-Host "[Phase6Y] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6Y] Hardware tag to verify: P6Y-GFXPOOL-MM166-FRAME-20261023-B"
}
else {
    Write-Host "[Phase6Y] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
