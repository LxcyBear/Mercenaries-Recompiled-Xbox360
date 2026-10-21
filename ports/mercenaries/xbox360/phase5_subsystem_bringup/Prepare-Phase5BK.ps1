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
$basePhase5biEmitter = Join-Path $phaseRoot "emit_phase5bi_low_text_sweep.py"
$basePhase5bjEmitter = Join-Path $phaseRoot "emit_phase5bj_deep_low_text_sweep.py"
$emitter = Join-Path $phaseRoot "emit_phase5bk_diagnostic_mop.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\diagnostic_mop_xdk"

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
    $basePhase5biEmitter,
    $basePhase5bjEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BK input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BK] DIAGNOSTIC CHECKPOINT + DIRECT-FRONTIER MOP"
Write-Host "[Phase5BK] Hardware seed: DIRECT_FRONTIER 0023A3CE -> 001F2A60, fault=0."
Write-Host "[Phase5BK] 5BJ evidence: ticks=18578 trace=1445 safe_icall_dispatches=77 direct_dispatches=107."
Write-Host "[Phase5BK] Strategy: inherit 5BJ, supply production-equivalent tracing-disabled support for four observational diagnostics, keep 001F2A60 mandatory, then mop accumulated exact generated direct frontiers under a 256-new-function cap."
Write-Host "[Phase5BK] The diagnostic helpers must remain observational-only; no XACT/gameplay behavior is fabricated."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bk-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
        "--base-phase5bj-emitter", $basePhase5bjEmitter,
        "--base-phase5bi-emitter", $basePhase5biEmitter,
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
    Write-Host "[Phase5BK] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 140 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 50) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BK diagnostic-mop package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bk-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BK emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BK-DIAGMOP1F2A60-20261021-A",
    "case 0x001F2A60u: return sub_001F2A60;",
    "s_phase5bkDiagnosticRootEntered = 1;",
    "s_phase5bkDiagnosticRootEntered &&",
    "static void recomp_xact_setup_checkpoint(",
    "static void recomp_teardown_call_checkpoint(",
    "static void recomp_teardown_item_checkpoint(",
    "static void recomp_collision_agent_recycle_range(",
    "PASS: Phase 5BK maintained CRT _msize",
    "PASS: Phase 5BK broad-sweep ICALL_SAFE",
    "PHASE 5BJ BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BK maintained RtlAllocateHeap",
    "PASS: Phase 5BK Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BK main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BJ RETAIL ENVIRONMENT PREP START",
    "PHASE 5BJ EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BJ EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bk_env_build_cookie",
    "5035424B",
    "PHASE 5BJ RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BK phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not $mainText.Contains(
    "Policy: retain the proven generic broad-sweep dispatcher, seed DIRECT 0023A3CE -> 001F2A60, supply maintained no-op support for production observational diagnostics, mop accumulated exact generated direct frontiers under a 256-new-function cap, and keep all genuine subsystem/ABI/kernel faults fenced")) {
    throw "Generated Phase 5BK main.cpp retained a stale sweep policy string"
}

if ($manifestJson.phase -ne "5BK" -or
    $manifestJson.build_tag -ne "P5BK-DIAGMOP1F2A60-20261021-A") {
    throw "Phase 5BK manifest identity mismatch"
}

$sweep = $manifestJson.phase5bk_diagnostic_mop
if ($sweep.observed_phase -ne "5BJ" -or
    $sweep.boundary_kind -ne "DIRECT_FRONTIER" -or
    $sweep.observed_caller -ne "0x0023A3CE" -or
    $sweep.root -ne "0x001F2A60" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFE94" -or
    $sweep.observed_saved_esp -ne "0x008BFE94" -or
    [int]$sweep.observed_ticks -ne 18578 -or
    [int]$sweep.observed_trace_count -ne 1445 -or
    [int]$sweep.observed_icall_dispatches -ne 77 -or
    [int]$sweep.observed_direct_dispatches -ne 107 -or
    [int]$sweep.root_direct_closure_depth -ne 6 -or
    [int]$sweep.root_direct_closure_cap -ne 256 -or
    [int]$sweep.fence_direct_closure_depth -ne 3 -or
    [int]$sweep.fence_direct_closure_cap -ne 48 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.observed_direct_fence_targets -lt 1 -or
    [int]$sweep.exact_generated_unpacked_fences -lt 1 -or
    [int]$sweep.candidate_new_members -lt 1 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BK diagnostic-mop manifest contract mismatch"
}

$requiredDiagnostics = @(
    "recomp_xact_setup_checkpoint",
    "recomp_teardown_call_checkpoint",
    "recomp_teardown_item_checkpoint",
    "recomp_collision_agent_recycle_range"
)
$maintainedDiagnostics = @($sweep.maintained_diagnostic_helpers)
foreach ($diagnostic in $requiredDiagnostics) {
    if ($maintainedDiagnostics -notcontains $diagnostic) {
        throw "Phase 5BK manifest is missing maintained diagnostic helper: $diagnostic"
    }
}

$newMembers = @($manifestJson.phase5bk_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x001F2A60")) {
    throw "Phase 5BK retained pack must contain 0x001F2A60 and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bj_deep_low_text_sweep.root -ne "0x00039B00" -or
    $manifestJson.phase5bj_deep_low_text_sweep.observed_caller -ne "0x0023A3CE" -or
    [int]$manifestJson.phase5bj_deep_low_text_sweep.observed_icall_dispatches -ne 76 -or
    [int]$manifestJson.phase5bj_deep_low_text_sweep.observed_direct_dispatches -ne 107) {
    throw "Phase 5BK lost inherited 5BJ deep-low-sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BK] READY"
Write-Host ("[Phase5BK] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BK] Observed direct fences : {0}" -f [int]$sweep.observed_direct_fence_targets)
Write-Host ("[Phase5BK] Exact unpacked fences  : {0}" -f [int]$sweep.exact_generated_unpacked_fences)
Write-Host ("[Phase5BK] Selected fence roots   : {0}" -f [int]$sweep.selected_fence_roots)
Write-Host ("[Phase5BK] Candidate new          : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BK] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BK] Newly packed           : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BK] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BK] Hardware goal: consume direct target 001F2A60, prove the tracing-disabled XACT setup checkpoint is harmless, and automatically clear as many accumulated exact direct frontiers as the widened pack permits."
Write-Host "[Phase5BK] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BK] Build BOTH freshly generated sources:"
Write-Host "[Phase5BK]   $main"
Write-Host "[Phase5BK]   $env"
Write-Host "[Phase5BK] Link-time cookie: phase5bk_env_build_cookie = 0x5035424B (P5BK)."
Write-Host "[Phase5BK] Expected build tag: P5BK-DIAGMOP1F2A60-20261021-A"
Write-Host "[Phase5BK] Send the complete xbWatson log after hardware test."
