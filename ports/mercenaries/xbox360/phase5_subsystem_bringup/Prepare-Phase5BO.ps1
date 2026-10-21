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
$basePhase5bkEmitter = Join-Path $phaseRoot "emit_phase5bk_diagnostic_mop.py"
$basePhase5blEmitter = Join-Path $phaseRoot "emit_phase5bl_high_tail_sweep.py"
$basePhase5bmEmitter = Join-Path $phaseRoot "emit_phase5bm_low_text_sweep.py"
$basePhase5bnEmitter = Join-Path $phaseRoot "emit_phase5bn_deep_low_sweep.py"
$emitter = Join-Path $phaseRoot "emit_phase5bo_mid_text_sweep.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\mid_text_saturation_xdk"

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
    $basePhase5bkEmitter,
    $basePhase5blEmitter,
    $basePhase5bmEmitter,
    $basePhase5bnEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BO input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BO] MID-.TEXT GAP SATURATION SWEEP"
Write-Host "[Phase5BO] Hardware seed: DIRECT_FRONTIER 0023A3CE -> 00216BB0, fault=0."
Write-Host "[Phase5BO] 5BN evidence: ticks=64803 trace=5859 safe_icall_dispatches=843 direct_dispatches=626 msize_calls=299 realloc_calls=4."
Write-Host "[Phase5BO] Strategy: inherit 5BN, prioritize a depth-6 closure from 00216BB0, then fill the remaining 256-new-function budget with nearest still-unpacked support-clean exact generated targets across the previously unsaturated 00120000-00235FFF mid-.text gap."
Write-Host "[Phase5BO] The mandatory 00216BB0 root may not be pruned, guessed, or already present in the inherited 5BN pack."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bo-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
        "--base-phase5bn-emitter", $basePhase5bnEmitter,
        "--base-phase5bm-emitter", $basePhase5bmEmitter,
        "--base-phase5bl-emitter", $basePhase5blEmitter,
        "--base-phase5bk-emitter", $basePhase5bkEmitter,
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
    Write-Host "[Phase5BO] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 160 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 60) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BO mid-text-saturation package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bo-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BO emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BO-MIDTEXT216BB0-20261021-A",
    "case 0x00216BB0u: return sub_00216BB0;",
    "s_phase5boMidTextRootEntered = 1;",
    "s_phase5boMidTextRootEntered &&",
    "static void recomp_xact_setup_checkpoint(",
    "static void recomp_teardown_call_checkpoint(",
    "static void recomp_teardown_item_checkpoint(",
    "static void recomp_collision_agent_recycle_range(",
    "PASS: Phase 5BO maintained CRT _msize",
    "PASS: Phase 5BO broad-sweep ICALL_SAFE",
    "PHASE 5BO BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BO maintained RtlAllocateHeap",
    "PASS: Phase 5BO Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BO main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BO RETAIL ENVIRONMENT PREP START",
    "PHASE 5BO EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BO EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bo_env_build_cookie",
    "5035424F",
    "PHASE 5BO RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BO phase5_env.cpp is missing marker: $requiredText"
    }
}

$expectedPolicy = "Policy: retain the proven generic broad-sweep dispatcher and maintained diagnostic support, seed DIRECT_FRONTIER 0023A3CE -> 00216BB0, saturate the remaining support-clean mid-.text gap 00120000-00235FFF under a 256-new-function cap, and continue only through exact packed targets while preserving all genuine subsystem/ABI/kernel hard stops"
if (-not $mainText.Contains($expectedPolicy)) {
    throw "Generated Phase 5BO main.cpp retained a stale sweep policy string"
}

if ($manifestJson.phase -ne "5BO" -or
    $manifestJson.build_tag -ne "P5BO-MIDTEXT216BB0-20261021-A") {
    throw "Phase 5BO manifest identity mismatch"
}

$sweep = $manifestJson.phase5bo_mid_text_sweep
if ($sweep.observed_phase -ne "5BN" -or
    $sweep.boundary_kind -ne "DIRECT_FRONTIER" -or
    $sweep.observed_caller -ne "0x0023A3CE" -or
    $sweep.root -ne "0x00216BB0" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFF3C" -or
    $sweep.observed_saved_esp -ne "0x008BFF3C" -or
    [int]$sweep.observed_ticks -ne 64803 -or
    [int]$sweep.observed_trace_count -ne 5859 -or
    [int]$sweep.observed_icall_dispatches -ne 843 -or
    [int]$sweep.observed_direct_dispatches -ne 626 -or
    [int]$sweep.observed_msize_calls -ne 299 -or
    [int]$sweep.observed_realloc_calls -ne 4 -or
    $sweep.region_start -ne "0x00120000" -or
    $sweep.region_end_exclusive -ne "0x00236000" -or
    [int]$sweep.direct_closure_depth -ne 6 -or
    [int]$sweep.direct_closure_cap -ne 256 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.candidate_new_members -lt 1 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BO mid-text-sweep manifest contract mismatch"
}

$newMembers = @($manifestJson.phase5bo_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x00216BB0")) {
    throw "Phase 5BO retained pack must contain newly packed root 0x00216BB0 and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bn_deep_low_sweep.root -ne "0x00031080" -or
    $manifestJson.phase5bn_deep_low_sweep.observed_caller -ne "0x0023A3CE" -or
    [int]$manifestJson.phase5bn_deep_low_sweep.observed_icall_dispatches -ne 807 -or
    [int]$manifestJson.phase5bn_deep_low_sweep.observed_direct_dispatches -ne 622) {
    throw "Phase 5BO lost inherited 5BN deep-low-sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BO] READY"
Write-Host ("[Phase5BO] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BO] Direct candidates      : {0}" -f [int]$sweep.direct_candidate_members)
Write-Host ("[Phase5BO] Remaining mid-.text    : {0}" -f [int]$sweep.regional_generated_candidates)
Write-Host ("[Phase5BO] Candidate new          : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BO] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BO] Newly packed           : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BO] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BO] Hardware goal: consume 00216BB0 through generic packed direct dispatch, then keep traversing the previously unsaturated mid-.text gap until the next genuine frontier or subsystem boundary."
Write-Host "[Phase5BO] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BO] Build BOTH freshly generated sources:"
Write-Host "[Phase5BO]   $main"
Write-Host "[Phase5BO]   $env"
Write-Host "[Phase5BO] Link-time cookie: phase5bo_env_build_cookie = 0x5035424F (P5BO)."
Write-Host "[Phase5BO] Expected build tag: P5BO-MIDTEXT216BB0-20261021-A"
Write-Host "[Phase5BO] Send the complete xbWatson log after hardware test."
