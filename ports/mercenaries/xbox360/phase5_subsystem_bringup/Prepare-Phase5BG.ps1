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
$emitter = Join-Path $phaseRoot "emit_phase5bg_text_tail_sweep.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\text_tail_sweep_xdk"

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
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5BG input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5BG] RETAIL TITLE .TEXT TAIL SWEEP"
Write-Host "[Phase5BG] Hardware seed: ICALL_SAFE 0022B3F1 -> 002471C0, fault=0."
Write-Host "[Phase5BG] Strategy: inherit 5BF and pre-pack support-clean exact generated targets across 00246000-0025561F, the remaining retail title .text tail, up to 256 additional functions."
Write-Host "[Phase5BG] The mandatory 002471C0 seed may not be pruned or guessed."
Write-Host ""

$emitLog = Join-Path $repoRoot "build\phase5_subsystem_bringup\phase5bg-emitter.log"
New-Item -ItemType Directory -Force -Path (Split-Path -Parent $emitLog) | Out-Null

$previousErrorActionPreference = $ErrorActionPreference
$ErrorActionPreference = "Continue"
try {
    $emitArgs = @(
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
    Write-Host "[Phase5BG] Emitter log tail:"
    $tailText = ""
    if (Test-Path -LiteralPath $emitLog) {
        Get-Content -LiteralPath $emitLog -Tail 120 | ForEach-Object {
            Write-Host $_
        }
        $tailText = (Get-Content -LiteralPath $emitLog -Tail 40) -join [Environment]::NewLine
    }
    Write-Host ""
    throw ("Phase 5BG text-tail-sweep package emission failed (exit {0}). Full emitter output: {1}{2}{3}" -f $emitExit, $emitLog, [Environment]::NewLine, $tailText)
}

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase5_env.cpp"
$manifest = Join-Path $outDir "phase5bg-manifest.json"

foreach ($generatedFile in @($main, $env, $manifest)) {
    if (-not (Test-Path -LiteralPath $generatedFile)) {
        throw "Phase 5BG emitter did not produce required file: $generatedFile"
    }
}

$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json

foreach ($requiredText in @(
    "P5BG-TEXTTAIL2471C0-20261020-A",
    "case 0x002471C0u: return sub_002471C0;",
    "s_phase5bgTailRootEntered = 1;",
    "s_phase5bgTailRootEntered &&",
    "PASS: Phase 5BG broad-sweep ICALL_SAFE",
    "PHASE 5BF BROAD TRANSLATED SWEEP RESULT",
    "PASS: Phase 5BG maintained RtlAllocateHeap",
    "PASS: Phase 5BG Partition0 backing LOADED"
)) {
    if (-not $mainText.Contains($requiredText)) {
        throw "Generated Phase 5BG main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 5BF RETAIL ENVIRONMENT PREP START",
    "PHASE 5BF EXACT RETAIL VERIFICATION: PASS",
    "PHASE 5BF EXECUTION ENVIRONMENT RESULT: PASS",
    "phase5bg_env_build_cookie",
    "50354247",
    "PHASE 5BF RETAIL ENVIRONMENT PREP END"
)) {
    if (-not $envText.Contains($requiredText)) {
        throw "Generated Phase 5BG phase5_env.cpp is missing marker: $requiredText"
    }
}

if (-not $mainText.Contains(
    "Policy: retain the proven generic broad-sweep dispatcher, seed ICALL_SAFE 0022B3F1 -> 002471C0, pre-pack support-clean exact generated entries across the remaining title .text tail 00246000-0025561F capped at 256 new functions")) {
    throw "Generated Phase 5BG main.cpp retained a stale sweep policy string"
}

if ($manifestJson.phase -ne "5BG" -or
    $manifestJson.build_tag -ne "P5BG-TEXTTAIL2471C0-20261020-A") {
    throw "Phase 5BG manifest identity mismatch"
}

$sweep = $manifestJson.phase5bg_text_tail_sweep
if ($sweep.observed_phase -ne "5BF" -or
    $sweep.boundary_kind -ne "ICALL_SAFE" -or
    $sweep.observed_caller -ne "0x0022B3F1" -or
    $sweep.root -ne "0x002471C0" -or
    [int]$sweep.observed_fault -ne 0 -or
    $sweep.observed_esp -ne "0x008BFF40" -or
    $sweep.observed_saved_esp -ne "0x008BFF44" -or
    $sweep.region_start -ne "0x00246000" -or
    $sweep.region_end_exclusive -ne "0x00255620" -or
    [int]$sweep.direct_closure_depth -ne 6 -or
    [int]$sweep.direct_closure_cap -ne 256 -or
    [int]$sweep.total_new_cap -ne 256 -or
    [int]$sweep.candidate_new_members -lt 1 -or
    [int]$sweep.new_members -lt 1 -or
    [int]$sweep.expanded_pack_members -le [int]$sweep.base_pack_members) {
    throw "Phase 5BG forward-sweep manifest contract mismatch"
}

$newMembers = @($manifestJson.phase5bg_new_members)
if ($newMembers.Count -lt 1 -or
    $newMembers.Count -gt 256 -or
    ($newMembers -notcontains "0x002471C0")) {
    throw "Phase 5BG retained pack must contain 0x002471C0 and stay within the 256-new-member cap"
}

if ($manifestJson.phase5bf_forward_sweep.root -ne "0x0023F22B" -or
    $manifestJson.phase5bf_forward_sweep.observed_caller -ne "0x0022DDA4") {
    throw "Phase 5BG lost inherited 5BF forward-sweep proof contract"
}

Write-Host ""
Write-Host "[Phase5BG] READY"
Write-Host ("[Phase5BG] Base pack members      : {0}" -f [int]$sweep.base_pack_members)
Write-Host ("[Phase5BG] Direct candidates      : {0}" -f [int]$sweep.direct_candidate_members)
Write-Host ("[Phase5BG] Regional candidates    : {0}" -f [int]$sweep.regional_generated_candidates)
Write-Host ("[Phase5BG] Candidate new          : {0}" -f [int]$sweep.candidate_new_members)
Write-Host ("[Phase5BG] Pruned/fenced          : {0}" -f [int]$sweep.pruned_members)
Write-Host ("[Phase5BG] Newly packed           : {0}" -f [int]$sweep.new_members)
Write-Host ("[Phase5BG] Expanded pack          : {0}" -f [int]$sweep.expanded_pack_members)
Write-Host "[Phase5BG] Hardware goal: consume 002471C0 and keep traversing exact packed targets through the remaining retail title .text tail up to 0025561F."
Write-Host "[Phase5BG] Keep game:\merc360-partition0\partition0-config.bin."
Write-Host "[Phase5BG] Build BOTH freshly generated sources:"
Write-Host "[Phase5BG]   $main"
Write-Host "[Phase5BG]   $env"
Write-Host "[Phase5BG] Link-time cookie: phase5bg_env_build_cookie = 0x50354247 (P5BF)."
Write-Host "[Phase5BG] Expected build tag: P5BG-TEXTTAIL2471C0-20261020-A"
Write-Host "[Phase5BG] Send the complete xbWatson log after hardware test."
