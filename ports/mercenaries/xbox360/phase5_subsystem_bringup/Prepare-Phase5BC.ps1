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
$emitter = Join-Path $phaseRoot "emit_phase5bc_broad_sweep.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\broad_sweep_xdk"

foreach ($required in @(
    $python,
    $generatedRoot,
    $functionsPath,
    $entryReport,
    $threadReport,
    $baseEmitter,
    $basePhase5bbEmitter,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BC input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BC] BROAD TRANSLATED FRONTIER SWEEP"
Write-Host "[Phase5BC] Seed: hardware-proven ICALL_SAFE 0022C3FA -> 00237052, fault=0."
Write-Host "[Phase5BC] Strategy: retain the full 5BB proof, add a depth-6/cap-256 translated closure, then auto-dispatch only exact targets already present in the widened pack."
Write-Host "[Phase5BC] Hard stops remain for unknown indirect/kernel/device behavior, guest faults, ABI/frame anomalies, heap exhaustion, debug breaks, and execution budget."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bc-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
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
    Write-Host "[Phase5BC] Emitter log tail:"
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 120 | ForEach-Object {
            Write-Host $_
        }
    }
    Write-Host ""
    throw "Phase 5BC broad-sweep package emission failed (exit $emitExit). Full emitter output: $emitLog"
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bc-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BC emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P5BC-BROADSWEEP237052-20261020-A",
    "case 0x00237052u: return sub_00237052;",
    "s_phase5bcSweepRootEntered = 1;",
    "PASS: Phase 5BC broad-sweep ICALL_SAFE",
    "PASS: Phase 5BC broad-sweep DIRECT",
    "s_phase5bcPackedIcallDispatchCount > 0u",
    "PHASE 5BC BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BC maintained RtlAllocateHeap",
    "PASS: Phase 5BC Partition0 backing LOADED",
    "PASS: Phase 5BC ICALL_SAFE 0022C452 -> 0023D550 entering packed translated target"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BC main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BC RETAIL ENVIRONMENT PREP START",
    "PHASE 5BC EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BC EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bc_env_build_cookie",
    "50354243",
    "PHASE 5BC RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BC phase5_env.cpp is missing marker: $requiredText"
    }
}

$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.phase -ne "5BC" -or
    $manifestJson.build_tag -ne "P5BC-BROADSWEEP237052-20261020-A") {
    throw "Phase 5BC manifest identity mismatch"
}

$sweep = $manifestJson.phase5bc_broad_sweep
if ($sweep.observed_phase -ne "5BB" -or
    $sweep.boundary_kind -ne "ICALL_SAFE" -or
    $sweep.observed_caller -ne "0x0022C3FA" -or
    $sweep.root -ne "0x00237052" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFF48" -or
    $sweep.observed_saved_esp -ne "0x008BFF4C" -or
    [int]$sweep.direct_closure_depth -ne 6 -or
    [int]$sweep.direct_closure_cap -ne 256 -or
    [int]$sweep.execution_budget_blocks -ne 200000 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BC broad-sweep manifest contract mismatch"
}

if ($sweep.auto_dispatch.safe_icall -notlike "*exact target*phase4c_lookup_pack_func*" -or
    $sweep.auto_dispatch.previously_fenced_direct -notlike "*exact target*phase4c_lookup_pack_func*" -or
    $sweep.auto_dispatch.ordinary_icall -ne "fenced" -or
    $sweep.auto_dispatch.itail -ne "fenced" -or
    $sweep.auto_dispatch.itail_safe -ne "fenced") {
    throw "Phase 5BC auto-dispatch safety policy mismatch"
}

$members = @($manifestJson.phase5bc_sweep_members)
if ($members.Count -lt 1 -or
    $members.Count -gt 256 -or
    ($members -notcontains "0x00237052")) {
    throw "Phase 5BC sweep closure must contain 0x00237052 and stay within cap 256"
}

if ($manifestJson.phase5bb_manual_heap.allocate -ne "0x0022DDA4" -or
    $manifestJson.phase5bb_manual_heap.free -ne "0x0022E51F" -or
    $manifestJson.phase5bb_manual_heap.reallocate -ne "0x0022E713") {
    throw "Phase 5BC lost inherited Phase 5BB manual heap contract"
}

if ($manifestJson.phase5bb_partition0_persistence.backing_path -ne "game:\merc360-partition0\partition0-config.bin" -or
    -not [bool]$manifestJson.phase5bb_partition0_persistence.two_pass_hardware_test) {
    throw "Phase 5BC lost inherited Phase 5BB persistence contract"
}

Write-Host ""
Write-Host "[Phase5BC] READY"
Write-Host ("[Phase5BC] Base pack members : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BC] Sweep members     : {0}" -f [int]$sweep.sweep_members)
Write-Host ("[Phase5BC] Newly added       : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BC] Expanded pack     : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BC] Hardware goal: enter 00237052, then keep consuming exact packed translated targets until a genuinely unsupported boundary appears."
Write-Host "[Phase5BC] Do NOT delete game:\merc360-partition0\partition0-config.bin; the persisted second-boot path remains part of the gate."
Write-Host "[Phase5BC] Build BOTH freshly generated sources:"
Write-Host "[Phase5BC]   $main"
Write-Host "[Phase5BC]   $env"
Write-Host "[Phase5BC] Link-time cookie: phase5bc_env_build_cookie = 0x50354243 (P5BC)."
Write-Host "[Phase5BC] Expected build tag: P5BC-BROADSWEEP237052-20261020-A"
Write-Host "[Phase5BC] If hardware stops, send the complete xbWatson log; one run may now cross multiple old-style frontiers."
