[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$stage3Root = Join-Path $repoRoot "build\phase3n_final_abi_scale"
$generatedRoot = Join-Path $stage3Root "runtime\gen"
$functionsPath = Join-Path $stage3Root "analysis\disasm\functions.json"
$entryReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-startup-closure.json"
$threadReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-thread-routine.json"
$baseEmitter = Join-Path $phaseRoot "..\phase4c_native_startup\emit_phase4c_startup_slice.py"
$basePhase5bbEmitter = Join-Path $phaseRoot "emit_phase5bb_frontier22dda4.py"
$basePhase5bcEmitter = Join-Path $phaseRoot "emit_phase5bc_broad_sweep.py"
$emitter = Join-Path $phaseRoot "emit_phase5bd_regional_sweep.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\regional_sweep_xdk"

foreach ($required in @(
    $python,
    $generatedRoot,
    $functionsPath,
    $entryReport,
    $threadReport,
    $baseEmitter,
    $basePhase5bbEmitter,
    $basePhase5bcEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BD input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BD] REGIONAL BROAD TRANSLATED SWEEP"
Write-Host "[Phase5BD] Hardware seed: ICALL_SAFE 0023701A -> 00237801, fault=0."
Write-Host "[Phase5BD] Strategy: inherit the proven 5BC dispatcher, keep 00237801 mandatory, and pre-pack support-clean generated functions in 00236000-00238FFF up to 256 new members."
Write-Host "[Phase5BD] This is intentionally broader than a one-address promotion."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bd-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
        "--base-phase5bc-emitter", $basePhase5bcEmitter,
        "--base-phase5bb-emitter", $basePhase5bbEmitter,
        "--base-emitter", $baseEmitter,
        "--generated-root", $generatedRoot,
        "--functions", $functionsPath,
        "--entry-report", $entryReport,
        "--thread-report", $threadReport,
        "--phase3n-template", $phase3nTemplate,
        "--phase2e-source", $phase2eSource,
        "--out-dir", $outDir
    )
    & $python $emitter @emitArgs 2>&1 | Tee-Object -FilePath $emitLog
    $emitExit = $LASTEXITCODE
}
finally {
    $ErrorActionPreference = $previousErrorActionPreference
}

if ($emitExit -ne 0) {
    Write-Host ""
    Write-Host "[Phase5BD] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 120 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 40) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BD regional-sweep package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bd-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BD emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BD-REGIONALSWEEP237801-20261020-A",
    "case 0x00237801u: return sub_00237801;",
    "s_phase5bdRegionalRootEntered = 1;",
    "s_phase5bdRegionalRootEntered &&",
    "PASS: Phase 5BD broad-sweep ICALL_SAFE",
    "PHASE 5BD BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BD maintained RtlAllocateHeap",
    "PASS: Phase 5BD Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BD main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BD RETAIL ENVIRONMENT PREP START",
    "PHASE 5BD EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BD EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bd_env_build_cookie",
    "50354244",
    "PHASE 5BD RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BD phase5_env.cpp is missing marker: $requiredText"
    }
}

if ($manifestJson.phase -ne "5BD" -or
    $manifestJson.build_tag -ne "P5BD-REGIONALSWEEP237801-20261020-A") {
    throw "Phase 5BD manifest identity mismatch"
}

$sweep = $manifestJson.phase5bd_regional_sweep
if ($sweep.observed_phase -ne "5BC" -or
    $sweep.boundary_kind -ne "ICALL_SAFE" -or
    $sweep.observed_caller -ne "0x0023701A" -or
    $sweep.root -ne "0x00237801" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFF40" -or
    $sweep.observed_saved_esp -ne "0x008BFF44" -or
    $sweep.region_start -ne "0x00236000" -or
    $sweep.region_end_exclusive -ne "0x00239000" -or
    [int]$sweep.direct_closure_depth -ne 6 -or
    [int]$sweep.direct_closure_cap -ne 256 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.candidate_new_members -lt 1 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BD regional-sweep manifest contract mismatch"
}

$newMembers = @($manifestJson.phase5bd_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x00237801")) {
    throw "Phase 5BD retained pack must contain 0x00237801 and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bc_broad_sweep.root -ne "0x00237052" -or
    $manifestJson.phase5bc_broad_sweep.observed_caller -ne "0x0022C3FA") {
    throw "Phase 5BD lost inherited 5BC broad-sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BD] READY"
Write-Host ("[Phase5BD] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BD] Direct candidates      : {0}" -f [int]$sweep.direct_candidate_members)
Write-Host ("[Phase5BD] Regional candidates    : {0}" -f [int]$sweep.regional_generated_candidates)
Write-Host ("[Phase5BD] Candidate new          : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BD] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BD] Newly packed           : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BD] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BD] Hardware goal: consume 00237801 and as many subsequent exact 00236xxx-00238xxx indirect/direct targets as the regional pack permits."
Write-Host "[Phase5BD] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BD] Build BOTH freshly generated sources:"
Write-Host "[Phase5BD]   $main"
Write-Host "[Phase5BD]   $env"
Write-Host "[Phase5BD] Link-time cookie: phase5bd_env_build_cookie = 0x50354244 (P5BD)."
Write-Host "[Phase5BD] Expected build tag: P5BD-REGIONALSWEEP237801-20261020-A"
Write-Host "[Phase5BD] Send the complete xbWatson log after hardware test."
