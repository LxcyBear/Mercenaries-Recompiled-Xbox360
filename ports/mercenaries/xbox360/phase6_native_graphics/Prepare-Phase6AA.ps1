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
$p5 = Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup"
$p4 = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup"
$python = Join-Path $root ".venv\Scripts\python.exe"
$stage3 = Join-Path $root "build\phase3n_final_abi_scale"
$baseDir = Join-Path $root "build\phase6_native_graphics\graphics_pool_dual_frontier_xdk"
$out = Join-Path $root "build\phase6_native_graphics\post_graphics_pool_frontier_0020fae0_xdk"
$log = Join-Path $root "build\phase6_native_graphics\phase6aa-emitter.log"

$paths = @{
    emitter = Join-Path $p6 "emit_phase6aa_post_graphics_pool_frontier_0020fae0.py"
    base = Join-Path $p4 "emit_phase4c_startup_slice.py"
    bb = Join-Path $p5 "emit_phase5bb_frontier22dda4.py"
    bc = Join-Path $p5 "emit_phase5bc_broad_sweep.py"
    build = Join-Path $p6 "Invoke-VS17Xbox360Build.ps1"
}
foreach ($v in $paths.Values + @($python)) {
    if (-not (Test-Path -LiteralPath $v)) {
        throw "Missing Phase 6AA input: $v"
    }
}

$baseManifestPath = Join-Path $baseDir "phase6z-manifest.json"
$baseFiles = @(
    (Join-Path $baseDir "main.cpp"),
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    (Join-Path $baseDir "translated_shards"),
    $baseManifestPath
)

$missingBaseFiles = @($baseFiles | Where-Object { -not (Test-Path -LiteralPath $_) })
if ($missingBaseFiles.Count -gt 0) {
    $phase6zPrep = Join-Path $p6 "Prepare-Phase6Z.ps1"
    if (-not (Test-Path -LiteralPath $phase6zPrep)) {
        throw "Phase 6AA baseline is missing and Phase 6Z prep was not found: $phase6zPrep"
    }

    Write-Host "[Phase6AA] Cached Phase 6Z output is missing."
    Write-Host "[Phase6AA] Regenerating the proven Phase 6Z source baseline without rebuilding..."
    & $phase6zPrep -SkipSolutionBuild
}

foreach ($f in @(
    (Join-Path $baseDir "main_monolithic.cpp"),
    (Join-Path $baseDir "phase5_env.cpp"),
    $baseManifestPath,
    (Join-Path $stage3 "runtime\gen"),
    (Join-Path $stage3 "analysis\disasm\functions.json")
)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AA required input missing after baseline regeneration: $f"
    }
}

$baseManifest = Get-Content -LiteralPath $baseManifestPath -Raw | ConvertFrom-Json
if ($baseManifest.phase -ne "6Z" -or
    $baseManifest.build_tag -ne "P6Z-GFXPOOL-DUAL-FRONTIER-20261023-A") {
    throw "Phase 6AA Phase 6Z baseline identity mismatch"
}

$z = $baseManifest.phase6z_graphics_pool_dual_frontier
if ($z.memory_model.expected_pool_base -ne "0x02880000" -or
    $z.memory_model.retail_pool_size -ne "0x01680000" -or
    $z.memory_model.old_page_next -ne "0x03F00000" -or
    $z.memory_model.free_title_heap_tail_trim -ne "0x00040000") {
    throw "Phase 6AA inherited Phase 6Z graphics-pool manifest drift"
}

if (Test-Path -LiteralPath $out) {
    Remove-Item -LiteralPath $out -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
New-Item -ItemType Directory -Force -Path (Split-Path $log -Parent) | Out-Null

Write-Host "[Phase6AA] POST-GRAPHICS-POOL FRONTIER 0020FAE0"
Write-Host "[Phase6AA] Phase 6Z hardware graphics pool: 02880000-03EFFFFF (01680000 bytes)"
Write-Host "[Phase6AA] Phase 6Z trim: 00040000 free heap-tail bytes"
Write-Host "[Phase6AA] Hardware boundary: DIRECT_FRONTIER 0023A3CE -> 0020FAE0"
Write-Host "[Phase6AA] Boundary state: ticks=670788 trace=179924 fault=0 eax=00000001"
Write-Host "[Phase6AA] Corrected inference: 0020FAE0 is reached after SUCCESSFUL graphics-pool allocation"
Write-Host "[Phase6AA] Preflight requires 0020FAE0 to be an exact generated function start/body"
Write-Host "[Phase6AA] Pack root + bounded depth-4/cap-256 support-clean closure"
Write-Host "[Phase6AA] Preserve Phase 6Z dual-frontier allocator and Mm166 repair unchanged"
Write-Host "[Phase6AA] Purple remains reserved for genuine NV2A MMIO/VRAM"

$args = @(
    "--base-dir",$baseDir,
    "--base-emitter",$paths.base,
    "--base-phase5bb-emitter",$paths.bb,
    "--base-phase5bc-emitter",$paths.bc,
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
    Write-Host "[Phase6AA] PREP STOPPED BEFORE BUILD."
    Write-Host "[Phase6AA] Exact-start/body validation or support-clean closure audit failed."
    Write-Host "[Phase6AA] Emitter log tail:"

    $tail = @(Get-Content -LiteralPath $log -Tail 140)
    $tail | ForEach-Object { Write-Host $_ }

    $dependencyLines = @(
        $tail | Where-Object {
            $_ -match "sweep root .* unresolved support dependencies:" -or
            $_ -match "broad-sweep seed requires real support implementation:"
        }
    )
    $reasonLines = @(
        $tail | Where-Object {
            ($_ -match "\[Phase6AA\]|\[Phase5BC\]") -and
            ($_ -notmatch "CategoryInfo|FullyQualifiedErrorId") -and
            ($_ -match "missing|not an exact|absent|unresolved|requires|refusing|lost|changed|failed|drift|expected|already present")
        }
    )
    if (@($dependencyLines).Count -gt 0) {
        $primary = [string]@($dependencyLines)[0]
    }
    elseif (@($reasonLines).Count -gt 0) {
        $primary = [string]@($reasonLines)[0]
    }
    else {
        $primary = "see $log"
    }

    Write-Host ("[Phase6AA] PRIMARY FAILURE: {0}" -f $primary)
    throw ("Phase 6AA emission/preflight failed (exit {0}); PRIMARY: {1}" -f $rc, $primary)
}

$main = Join-Path $out "main.cpp"
$monolithic = Join-Path $out "main_monolithic.cpp"
$env = Join-Path $out "phase5_env.cpp"
$manifest = Join-Path $out "phase6aa-manifest.json"
$shardDir = Join-Path $out "translated_shards"

foreach ($f in @($main,$monolithic,$env,$manifest,$shardDir)) {
    if (-not (Test-Path -LiteralPath $f)) {
        throw "Phase 6AA missing output: $f"
    }
}

$m = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($m.phase -ne "6AA" -or
    $m.build_tag -ne "P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B") {
    throw "Phase 6AA manifest identity mismatch"
}

$a = $m.phase6aa_post_graphics_pool_frontier
if (-not [bool]$a.phase6z_hardware_pass -or
    $a.root -ne "0x0020FAE0" -or
    $a.frontier_caller -ne "0x0023A3CE" -or
    -not [bool]$a.graphics_pool_model_inherited_unchanged -or
    [int]$a.execution_budget_inherited -ne 2000000 -or
    [int]$a.packed_new_members -lt 1) {
    throw "Phase 6AA manifest gate mismatch"
}

if ($a.phase6z_hardware.graphics_pool.base -ne "0x02880000" -or
    $a.phase6z_hardware.graphics_pool.size -ne "0x01680000" -or
    $a.phase6z_hardware.next_boundary.target -ne "0x0020FAE0" -or
    [int]$a.phase6z_hardware.next_boundary.fault -ne 0) {
    throw "Phase 6AA hardware evidence gate mismatch"
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($marker in @(
    "P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B",
    "case 0x0020FAE0u:",
    "s_phase6aaRootEntered = 1;",
    "PASS: Phase 6AA retail graphics pool claim",
    "base != 0x02880000u",
    "oldPageNext != 0x03F00000u",
    "P6AA POST-GFXPOOL SUMMARY:",
    "PHASE 6AA POST-GFXPOOL FRONTIER RESULT",
    "P6AA FIRST GRAPHICS TOUCH: NV2A MMIO boundary reached",
    "P6AA FIRST GRAPHICS TOUCH: NV2A VRAM aperture boundary reached",
    "static uint32_t recomp_renderer_test_oom(uint32_t multisample)",
    "static void recomp_renderer_recovery_report(uint32_t result, uint32_t stage)",
    "PHASE4C_BOUNDARY_RENDERER_FATAL = 19",
    "#define PHASE4C_EXEC_BUDGET 2000000u",
    "phase6aa_env_build_cookie"
)) {
    if (-not $mainText.Contains($marker)) {
        throw "Phase 6AA generated main gate missing: $marker"
    }
}

if ($envText -notmatch "phase6aa_env_build_cookie") {
    throw "Phase 6AA env cookie gate missing"
}
if ($mainText -match "phase6z_env_build_cookie" -or
    $envText -match "phase6z_env_build_cookie") {
    throw "Phase 6AA stale Phase 6Z cookie remains"
}

$shards = @(Get-ChildItem -LiteralPath $shardDir -Filter "*.inl" -File)
if ($shards.Count -lt 1) {
    throw "Phase 6AA translated shard output is empty"
}

Write-Host ""
Write-Host "[Phase6AA] READY"
Write-Host ("[Phase6AA] Root                         : {0}" -f [string]$a.root)
Write-Host ("[Phase6AA] Root name                    : {0}" -f [string]$a.root_name)
Write-Host ("[Phase6AA] Candidate new members        : {0}" -f [int]$a.candidate_new_members)
Write-Host ("[Phase6AA] Pruned unsafe members        : {0}" -f [int]$a.pruned_members)
Write-Host ("[Phase6AA] Packed new members           : {0}" -f [int]$a.packed_new_members)
Write-Host ("[Phase6AA] Expanded pack members        : {0}" -f [int]$a.expanded_pack_members)
Write-Host ("[Phase6AA] Generated shards             : {0}" -f $shards.Count)
Write-Host "[Phase6AA] Graphics pool                 : inherited 02880000-03EFFFFF"
Write-Host "[Phase6AA] Old 0020FAE0 OOM-only theory : disproven by Phase 6Z hardware"
Write-Host "[Phase6AA] Expected tag                  : P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B"

if (-not $SkipSolutionBuild) {
    Write-Host ""
    Write-Host "[Phase6AA] AUTO-BUILD: sync + clean + Release|Xbox 360 using Visual Studio 2017"

    $buildArgs = @{
        GeneratedMain = $main
        GeneratedEnv = $env
        GeneratedShardDir = $shardDir
        ExpectedBuildTag = "P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B"
        ExpectedEnvCookie = "phase6aa_env_build_cookie"
        SolutionRoot = $SolutionRoot
        Configuration = $Configuration
        Platform = $Platform
        CleanLog = (Join-Path $root "build\phase6_native_graphics\phase6aa-vs2017-clean.log")
        BuildLog = (Join-Path $root "build\phase6_native_graphics\phase6aa-vs2017-build.log")
    }

    & $paths.build @buildArgs
    if ($LASTEXITCODE -ne 0 -and $null -ne $LASTEXITCODE) {
        throw "Phase 6AA Visual Studio 2017/Xbox 360 build failed (exit $LASTEXITCODE)"
    }

    Write-Host ""
    Write-Host "[Phase6AA] PREP + SOURCE SYNC + RELEASE BUILD: PASS"
    Write-Host "[Phase6AA] Hardware tag to verify: P6AA-POST-GFXPOOL-FRONTIER-0020FAE0-20261023-B"
}
else {
    Write-Host "[Phase6AA] AUTO-BUILD skipped because -SkipSolutionBuild was supplied."
}
