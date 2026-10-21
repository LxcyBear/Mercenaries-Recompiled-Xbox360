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
$basePhase5bdEmitter = Join-Path $phaseRoot "emit_phase5bd_regional_sweep.py"
$basePhase5beEmitter = Join-Path $phaseRoot "emit_phase5be_forward_sweep.py"
$basePhase5bfEmitter = Join-Path $phaseRoot "emit_phase5bf_forward_sweep.py"
$basePhase5bgEmitter = Join-Path $phaseRoot "emit_phase5bg_text_tail_sweep.py"
$basePhase5bhEmitter = Join-Path $phaseRoot "emit_phase5bh_direct_frontier_mop.py"
$emitter = Join-Path $phaseRoot "emit_phase5bi_low_text_sweep.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\low_text_sweep_xdk"

foreach ($required in @(
    $python,
    $generatedRoot,
    $functionsPath,
    $entryReport,
    $threadReport,
    $baseEmitter,
    $basePhase5bbEmitter,
    $basePhase5bcEmitter,
    $basePhase5bdEmitter,
    $basePhase5beEmitter,
    $basePhase5bfEmitter,
    $basePhase5bgEmitter,
    $basePhase5bhEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BI input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BI] LOW-.TEXT RUNTIME FAMILY SWEEP"
Write-Host "[Phase5BI] Hardware seed: ICALL_SAFE 0023A3CE -> 000B5E50, fault=0."
Write-Host "[Phase5BI] 5BH evidence: ticks=15406 trace=1190 safe_icall_dispatches=53 direct_dispatches=94."
Write-Host "[Phase5BI] Strategy: inherit 5BH, prioritize a depth-6 closure from 000B5E50, then pre-pack nearest support-clean exact generated targets across 000A0000-0011FFFF under a 256-new-function cap."
Write-Host "[Phase5BI] The mandatory 000B5E50 root may not be pruned or guessed."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bi-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
        "--base-phase5bh-emitter", $basePhase5bhEmitter,
        "--base-phase5bg-emitter", $basePhase5bgEmitter,
        "--base-phase5bf-emitter", $basePhase5bfEmitter,
        "--base-phase5be-emitter", $basePhase5beEmitter,
        "--base-phase5bd-emitter", $basePhase5bdEmitter,
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
    Write-Host "[Phase5BI] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 140 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 50) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BI low-text-sweep package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bi-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BI emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BI-LOWTEXTB5E50-20261021-A",
    "case 0x000B5E50u: return sub_000B5E50;",
    "s_phase5biLowTextRootEntered = 1;",
    "s_phase5biLowTextRootEntered &&",
    "PASS: Phase 5BI maintained CRT _msize",
    "PASS: Phase 5BI broad-sweep ICALL_SAFE",
    "PHASE 5BI BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BI maintained RtlAllocateHeap",
    "PASS: Phase 5BI Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BI main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BI RETAIL ENVIRONMENT PREP START",
    "PHASE 5BI EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BI EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bi_env_build_cookie",
    "50354249",
    "PHASE 5BI RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BI phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not $mainText.Contains(
    "Policy: retain the proven generic broad-sweep dispatcher, seed ICALL_SAFE 0023A3CE -> 000B5E50, pre-pack a support-clean 000A0000-0011FFFF low-.text neighborhood capped at 256 new functions, and continue only through exact targets already present in the widened pack")) {
    throw "Generated Phase 5BI main.cpp retained a stale sweep policy string"
}

if ($manifestJson.phase -ne "5BI" -or
    $manifestJson.build_tag -ne "P5BI-LOWTEXTB5E50-20261021-A") {
    throw "Phase 5BI manifest identity mismatch"
}

$sweep = $manifestJson.phase5bi_low_text_sweep
if ($sweep.observed_phase -ne "5BH" -or
    $sweep.boundary_kind -ne "ICALL_SAFE" -or
    $sweep.observed_caller -ne "0x0023A3CE" -or
    $sweep.root -ne "0x000B5E50" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFEF4" -or
    $sweep.observed_saved_esp -ne "0x008BFEF8" -or
    [int]$sweep.observed_ticks -ne 15406 -or
    [int]$sweep.observed_trace_count -ne 1190 -or
    [int]$sweep.observed_icall_dispatches -ne 53 -or
    [int]$sweep.observed_direct_dispatches -ne 94 -or
    $sweep.region_start -ne "0x000A0000" -or
    $sweep.region_end_exclusive -ne "0x00120000" -or
    [int]$sweep.direct_closure_depth -ne 6 -or
    [int]$sweep.direct_closure_cap -ne 256 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.candidate_new_members -lt 1 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BI low-text-sweep manifest contract mismatch"
}

$newMembers = @($manifestJson.phase5bi_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x000B5E50")) {
    throw "Phase 5BI retained pack must contain 0x000B5E50 and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bh_direct_frontier_mop.root -ne "0x0023BE3C" -or
    $manifestJson.phase5bh_direct_frontier_mop.observed_caller -ne "0x0023776D" -or
    $manifestJson.phase5bh_direct_frontier_mop.support_owned_manual_name -ne "Xbox CRT _msize") {
    throw "Phase 5BI lost inherited 5BH direct-mop/manual-_msize proof contract"
}

Write-Host ""
Write-Host "[Phase5BI] READY"
Write-Host ("[Phase5BI] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BI] Direct candidates      : {0}" -f [int]$sweep.direct_candidate_members)
Write-Host ("[Phase5BI] Regional candidates    : {0}" -f [int]$sweep.regional_generated_candidates)
Write-Host ("[Phase5BI] Candidate new          : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BI] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BI] Newly packed           : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BI] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BI] Hardware goal: consume 000B5E50 and keep traversing exact packed targets through the low-.text runtime family until the next genuine boundary."
Write-Host "[Phase5BI] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BI] Build BOTH freshly generated sources:"
Write-Host "[Phase5BI]   $main"
Write-Host "[Phase5BI]   $env"
Write-Host "[Phase5BI] Link-time cookie: phase5bi_env_build_cookie = 0x50354249 (P5BI)."
Write-Host "[Phase5BI] Expected build tag: P5BI-LOWTEXTB5E50-20261021-A"
Write-Host "[Phase5BI] Send the complete xbWatson log after hardware test."
