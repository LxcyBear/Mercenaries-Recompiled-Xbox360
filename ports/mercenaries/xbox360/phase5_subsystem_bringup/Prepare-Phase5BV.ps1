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
$basePhase5boEmitter = Join-Path $phaseRoot "emit_phase5bo_mid_text_sweep.py"
$basePhase5bpEmitter = Join-Path $phaseRoot "emit_phase5bp_low_text_sweep.py"
$basePhase5bqEmitter = Join-Path $phaseRoot "emit_phase5bq_low_text_sweep.py"
$basePhase5brEmitter = Join-Path $phaseRoot "emit_phase5br_low_text_sweep.py"
$basePhase5bsEmitter = Join-Path $phaseRoot "emit_phase5bs_low_text_sweep.py"
$basePhase5btEmitter = Join-Path $phaseRoot "emit_phase5bt_mid_text_sweep.py"
$basePhase5buEmitter = Join-Path $phaseRoot "emit_phase5bu_mid_text_sweep.py"
$emitter = Join-Path $phaseRoot "emit_phase5bv_repeatability.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\repeatability_gate_xdk"

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
    $basePhase5boEmitter,
    $basePhase5bpEmitter,
    $basePhase5bqEmitter,
    $basePhase5brEmitter,
    $basePhase5bsEmitter,
    $basePhase5btEmitter,
    $basePhase5buEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BV input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BV] FROZEN-PACK REPEATABILITY GATE"
Write-Host "[Phase5BV] 5BU hardware endpoint: DIRECT_FRONTIER 0023A3CE -> 0014CD30, fault=0."
Write-Host "[Phase5BV] 5BU evidence: ticks=73417 trace=7322 safe_icall_dispatches=1262 direct_dispatches=1002 msize_calls=395 realloc_calls=4."
Write-Host "[Phase5BV] Coverage policy: ZERO new translated members. Generate the exact 5BU pack, relabel only, and verify the same hardware endpoint three consecutive times."
Write-Host "[Phase5BV] Persistence policy: keep game:\merc360-partition0\partition0-config.bin unchanged across all three launches."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bv-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
        "--base-phase5bu-emitter", $basePhase5buEmitter,
        "--base-phase5bt-emitter", $basePhase5btEmitter,
        "--base-phase5bs-emitter", $basePhase5bsEmitter,
        "--base-phase5br-emitter", $basePhase5brEmitter,
        "--base-phase5bq-emitter", $basePhase5bqEmitter,
        "--base-phase5bp-emitter", $basePhase5bpEmitter,
        "--base-phase5bo-emitter", $basePhase5boEmitter,
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
    Write-Host "[Phase5BV] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 160 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 60) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BV repeatability package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bv-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BV emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BV-REPEATABILITY-20261021-A",
    "case 0x001462E0u: return sub_001462E0;",
    "s_phase5buMidTextRootEntered = 1;",
    "s_phase5buMidTextRootEntered &&",
    "PASS: Phase 5BV maintained CRT _msize",
    "PASS: Phase 5BV broad-sweep ICALL_SAFE",
    "PHASE 5BV REPEATABILITY RESULT",
    "PASS: Phase 5BV maintained RtlAllocateHeap",
    "PASS: Phase 5BV Partition0 backing LOADED",
    "freeze the exact Phase 5BU translated pack with zero new members"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BV main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BV RETAIL ENVIRONMENT PREP START",
    "PHASE 5BV EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BV EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bv_env_build_cookie",
    "50354256",
    "PHASE 5BV RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BV phase5_env.cpp is missing marker: $requiredText"
    }
}

$expectedPolicy = "Policy: freeze the exact Phase 5BU translated pack with zero new members; repeat the same retail boot path unchanged and require the fault-free stable endpoint candidate DIRECT_FRONTIER 0023A3CE -> 0014CD30 with identical translated dispatch/heap/trace invariants before Phase-5 exit reconnaissance; preserve all genuine subsystem/ABI/kernel hard stops"
if (-not $mainText.Contains($expectedPolicy)) {
    throw "Generated Phase 5BV main.cpp retained a stale policy string"
}

if ($manifestJson.phase -ne "5BV" -or
    $manifestJson.build_tag -ne "P5BV-REPEATABILITY-20261021-A") {
    throw "Phase 5BV manifest identity mismatch"
}

$gate = $manifestJson.phase5bv_repeatability_gate
if ($gate.source_phase -ne "5BU" -or
    -not [bool]$gate.frozen_pack -or
    [int]$gate.new_members -ne 0 -or
    [int]$gate.required_consecutive_hardware_runs -ne 3 -or
    $gate.expected_boundary_kind -ne "DIRECT_FRONTIER" -or
    $gate.expected_caller -ne "0x0023A3CE" -or
    $gate.expected_target -ne "0x0014CD30" -or
    $gate.expected_esp -ne "0x008BFF3C" -or
    $gate.expected_saved_esp -ne "0x008BFF3C" -or
    [int]$gate.expected_fault -ne 0 -or
    [int]$gate.expected_ticks -ne 73417 -or
    [int]$gate.expected_trace_count -ne 7322 -or
    [int]$gate.expected_icall_dispatches -ne 1262 -or
    [int]$gate.expected_direct_dispatches -ne 1002 -or
    [int]$gate.expected_msize_calls -ne 395 -or
    [int]$gate.expected_realloc_calls -ne 4 -or
    [int]$gate.expected_final_msize -ne 2048) {
    throw "Phase 5BV repeatability manifest contract mismatch"
}

$sourceSweep = $manifestJson.phase5bu_mid_text_sweep
if ($sourceSweep.root -ne "0x001462E0" -or
    $sourceSweep.observed_phase -ne "5BT" -or
    $sourceSweep.observed_caller -ne "0x0023A3CE" -or
    [int]$sourceSweep.observed_icall_dispatches -ne 1261 -or
    [int]$sourceSweep.observed_direct_dispatches -ne 1000) {
    throw "Phase 5BV lost inherited 5BU sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BV] READY"
Write-Host ("[Phase5BV] Frozen pack members      : {0}" -f [int]$manifestJson.pack_members)
Write-Host "[Phase5BV] New translated members   : 0"
Write-Host "[Phase5BV] Expected stable boundary : DIRECT_FRONTIER 0023A3CE -> 0014CD30"
Write-Host "[Phase5BV] Expected counters        : icall=1262 direct=1002 msize=395 realloc=4 ticks=73417 trace=7322 fault=0"
Write-Host "[Phase5BV] Hardware protocol        : use ONE freshly built XEX for THREE consecutive launches."
Write-Host "[Phase5BV] Do NOT rebuild between runs and do NOT delete/reset Partition0 backing."
Write-Host "[Phase5BV] Capture the COMPLETE xbWatson log for run 1, run 2, and run 3, including proof end + XAPI return."
Write-Host "[Phase5BV] Build BOTH freshly generated sources:"
Write-Host "[Phase5BV]   $main"
Write-Host "[Phase5BV]   $env"
Write-Host "[Phase5BV] Link-time cookie: phase5bv_env_build_cookie = 0x50354256 (P5BV)."
Write-Host "[Phase5BV] Expected build tag: P5BV-REPEATABILITY-20261021-A"
