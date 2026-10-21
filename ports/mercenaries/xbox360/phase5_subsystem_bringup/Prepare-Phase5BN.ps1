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
$emitter = Join-Path $phaseRoot "emit_phase5bn_deep_low_sweep.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\deep_low_saturation_xdk"

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
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BN input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BN] SECOND-PASS DEEP-LOW .TEXT SATURATION SWEEP"
Write-Host "[Phase5BN] Hardware seed: ICALL_SAFE 0023A3CE -> 00031080, fault=0."
Write-Host "[Phase5BN] 5BM evidence: ticks=64101 trace=5743 safe_icall_dispatches=807 direct_dispatches=622 msize_calls=295 realloc_calls=4."
Write-Host "[Phase5BN] Strategy: inherit 5BM, prioritize a depth-6 closure from 00031080, then fill the remaining 256-new-function budget with nearest still-unpacked support-clean exact generated targets across 00011000-0009FFFF."
Write-Host "[Phase5BN] The mandatory 00031080 root may not be pruned, guessed, or already present in the inherited 5BM pack."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bn-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
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
    Write-Host "[Phase5BN] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 160 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 60) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BN deep-low-saturation package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bn-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BN emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BN-DEEPLOW31080-20261021-A",
    "case 0x00031080u: return sub_00031080;",
    "s_phase5bnDeepLowRootEntered = 1;",
    "s_phase5bnDeepLowRootEntered &&",
    "static void recomp_xact_setup_checkpoint(",
    "static void recomp_teardown_call_checkpoint(",
    "static void recomp_teardown_item_checkpoint(",
    "static void recomp_collision_agent_recycle_range(",
    "PASS: Phase 5BN maintained CRT _msize",
    "PASS: Phase 5BN broad-sweep ICALL_SAFE",
    "PHASE 5BM BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BN maintained RtlAllocateHeap",
    "PASS: Phase 5BN Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BN main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BM RETAIL ENVIRONMENT PREP START",
    "PHASE 5BM EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BM EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bn_env_build_cookie",
    "5035424E",
    "PHASE 5BM RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BN phase5_env.cpp is missing marker: $requiredText"
    }
}

$expectedPolicy = "Policy: retain the proven generic broad-sweep dispatcher and maintained diagnostic support, seed ICALL_SAFE 0023A3CE -> 00031080, revisit the remaining support-clean deep-low .text band 00011000-0009FFFF under a 256-new-function cap, and continue only through exact packed targets while preserving all genuine subsystem/ABI/kernel hard stops"
if (-not $mainText.Contains($expectedPolicy)) {
    throw "Generated Phase 5BN main.cpp retained a stale sweep policy string"
}

if ($manifestJson.phase -ne "5BN" -or
    $manifestJson.build_tag -ne "P5BN-DEEPLOW31080-20261021-A") {
    throw "Phase 5BN manifest identity mismatch"
}

$sweep = $manifestJson.phase5bn_deep_low_sweep
if ($sweep.observed_phase -ne "5BM" -or
    $sweep.boundary_kind -ne "ICALL_SAFE" -or
    $sweep.observed_caller -ne "0x0023A3CE" -or
    $sweep.root -ne "0x00031080" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFEF4" -or
    $sweep.observed_saved_esp -ne "0x008BFEF8" -or
    [int]$sweep.observed_ticks -ne 64101 -or
    [int]$sweep.observed_trace_count -ne 5743 -or
    [int]$sweep.observed_icall_dispatches -ne 807 -or
    [int]$sweep.observed_direct_dispatches -ne 622 -or
    [int]$sweep.observed_msize_calls -ne 295 -or
    [int]$sweep.observed_realloc_calls -ne 4 -or
    $sweep.region_start -ne "0x00011000" -or
    $sweep.region_end_exclusive -ne "0x000A0000" -or
    [int]$sweep.direct_closure_depth -ne 6 -or
    [int]$sweep.direct_closure_cap -ne 256 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.candidate_new_members -lt 1 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BN deep-low-sweep manifest contract mismatch"
}

$newMembers = @($manifestJson.phase5bn_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x00031080")) {
    throw "Phase 5BN retained pack must contain newly packed root 0x00031080 and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bm_low_text_sweep.root -ne "0x000B20C0" -or
    $manifestJson.phase5bm_low_text_sweep.observed_caller -ne "0x0023A3CE" -or
    [int]$manifestJson.phase5bm_low_text_sweep.observed_icall_dispatches -ne 358 -or
    [int]$manifestJson.phase5bm_low_text_sweep.observed_direct_dispatches -ne 597 -or
    $manifestJson.phase5bm_low_text_sweep.root_inherited_from_reanalysis -ne $true -or
    $manifestJson.phase5bm_low_text_sweep.hardware_seed_promoted -ne $true) {
    throw "Phase 5BN lost inherited 5BM low-text-sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BN] READY"
Write-Host ("[Phase5BN] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BN] Direct candidates      : {0}" -f [int]$sweep.direct_candidate_members)
Write-Host ("[Phase5BN] Remaining deep-low     : {0}" -f [int]$sweep.regional_generated_candidates)
Write-Host ("[Phase5BN] Candidate new          : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BN] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BN] Newly packed           : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BN] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BN] Hardware goal: consume 00031080 through generic packed safe-ICALL dispatch, then keep traversing the expanded deep-low .text family until the next genuine frontier or subsystem boundary."
Write-Host "[Phase5BN] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BN] Build BOTH freshly generated sources:"
Write-Host "[Phase5BN]   $main"
Write-Host "[Phase5BN]   $env"
Write-Host "[Phase5BN] Link-time cookie: phase5bn_env_build_cookie = 0x5035424E (P5BN)."
Write-Host "[Phase5BN] Expected build tag: P5BN-DEEPLOW31080-20261021-A"
Write-Host "[Phase5BN] Send the complete xbWatson log after hardware test."
