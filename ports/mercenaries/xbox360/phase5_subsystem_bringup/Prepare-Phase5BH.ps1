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
$emitter = Join-Path $phaseRoot "emit_phase5bh_direct_frontier_mop.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\direct_frontier_mop_xdk"

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
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BH input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BH] ACCUMULATED DIRECT-FRONTIER MOP SWEEP"
Write-Host "[Phase5BH] Hardware seed: DIRECT_FRONTIER 0023776D -> 0023BE3C, fault=0."
Write-Host "[Phase5BH] Strategy: inherit 5BG, harvest all currently fenced exact generated direct targets, add bounded closures, and pack the largest support-clean subset under the 256-new-function cap."
Write-Host "[Phase5BH] The mandatory 0023BE3C seed may not be pruned or guessed."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bh-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
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
    Write-Host "[Phase5BH] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 120 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 40) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BH direct-frontier-mop package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bh-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BH emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BH-DIRECTMOP23BE3C-20261021-B",
    "case 0x0023BE3Cu: return sub_0023BE3C;",
    "PASS: Phase 5BH maintained CRT _msize",
    "s_phase5bhDirectRootEntered = 1;",
    "s_phase5bhDirectRootEntered &&",
    "PASS: Phase 5BH broad-sweep ICALL_SAFE",
    "PHASE 5BH BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BH maintained RtlAllocateHeap",
    "PASS: Phase 5BH Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BH main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BH RETAIL ENVIRONMENT PREP START",
    "PHASE 5BH EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BH EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bh_env_build_cookie",
    "50354248",
    "PHASE 5BH RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BH phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not $mainText.Contains(
    "Policy: retain the proven generic broad-sweep dispatcher, seed DIRECT 0023776D -> 0023BE3C, harvest exact generated targets from all inherited direct-frontier fences, add bounded translated closures within a 256-new-function cap, and keep unsupported branches fenced")) {
    throw "Generated Phase 5BH main.cpp retained a stale sweep policy string"
}

if ($manifestJson.phase -ne "5BH" -or
    $manifestJson.build_tag -ne "P5BH-DIRECTMOP23BE3C-20261021-B") {
    throw "Phase 5BH manifest identity mismatch"
}

$sweep = $manifestJson.phase5bh_direct_frontier_mop
if ($sweep.observed_phase -ne "5BG" -or
    $sweep.boundary_kind -ne "DIRECT_FRONTIER" -or
    $sweep.observed_caller -ne "0x0023776D" -or
    $sweep.root -ne "0x0023BE3C" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFF24" -or
    $sweep.observed_saved_esp -ne "0x008BFF24" -or
    [int]$sweep.root_direct_closure_depth -ne 6 -or
    [int]$sweep.root_direct_closure_cap -ne 256 -or
    [int]$sweep.fence_direct_closure_depth -ne 3 -or
    [int]$sweep.fence_direct_closure_cap -ne 48 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.translated_new_cap -ne 255 -or
    $sweep.support_owned_manual_root -ne "0x0023BE3C" -or
    $sweep.support_owned_manual_name -ne "Xbox CRT _msize" -or
    [int]$sweep.support_owned_new_members -ne 1 -or
    [int]$sweep.observed_direct_fence_targets -lt 1 -or
    [int]$sweep.exact_generated_unpacked_fences -lt 1 -or
    [int]$sweep.candidate_new_members -lt 0 -or
    [int]$sweep.translated_new_members -lt 0 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BH direct-frontier-mop manifest contract mismatch"
}

$newMembers = @($manifestJson.phase5bh_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x0023BE3C")) {
    throw "Phase 5BH retained pack must contain 0x0023BE3C and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bg_text_tail_sweep.root -ne "0x002471C0" -or
    $manifestJson.phase5bg_text_tail_sweep.observed_caller -ne "0x0022B3F1") {
    throw "Phase 5BH lost inherited 5BG text-tail-sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BH] READY"
Write-Host ("[Phase5BH] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BH] Observed direct fences : {0}" -f [int]$sweep.observed_direct_fence_targets)
Write-Host ("[Phase5BH] Exact unpacked fences  : {0}" -f [int]$sweep.exact_generated_unpacked_fences)
Write-Host ("[Phase5BH] Selected fence roots   : {0}" -f [int]$sweep.selected_fence_roots)
Write-Host ("[Phase5BH] Candidate translated   : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BH] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BH] Translated newly packed: {0}" -f [int]$sweep.translated_new_members)
Write-Host ("[Phase5BH] Support-owned new      : {0} ({1})" -f [int]$sweep.support_owned_new_members, $sweep.support_owned_manual_name)
Write-Host ("[Phase5BH] Newly packed total     : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BH] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BH] Hardware goal: consume direct target 0023BE3C and automatically clear as many accumulated exact translated direct-frontier fences as the support-clean pack permits."
Write-Host "[Phase5BH] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BH] Build BOTH freshly generated sources:"
Write-Host "[Phase5BH]   $main"
Write-Host "[Phase5BH]   $env"
Write-Host "[Phase5BH] Link-time cookie: phase5bh_env_build_cookie = 0x50354248 (P5BH)."
Write-Host "[Phase5BH] Expected build tag: P5BH-DIRECTMOP23BE3C-20261021-B"
Write-Host "[Phase5BH] Send the complete xbWatson log after hardware test."
