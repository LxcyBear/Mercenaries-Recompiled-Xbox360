[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$emitter = Join-Path $phaseRoot "emit_phase5_exit_recon.py"
$generatedRoot = Join-Path $repoRoot "build\phase3n_final_abi_scale\runtime\gen"
$outDir = Join-Path $repoRoot "build\phase5_subsystem_bringup\exit_recon"

foreach ($required in @(
    $python,
    $emitter,
    $generatedRoot,
    (Join-Path $repoRoot "SUBSYSTEMS.md"),
    (Join-Path $phaseRoot "PHASE5_EXIT_RECON.md")
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 5 exit-recon input is missing: $required"
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase5Exit] FINAL PHASE-5 SUBSYSTEM EXPOSURE & RECONNAISSANCE"
Write-Host "[Phase5Exit] Hardware baseline: Phase 5BV repeatability 3/3 PASS."
Write-Host "[Phase5Exit] Stable endpoint: DIRECT_FRONTIER 0023A3CE -> 0014CD30."
Write-Host "[Phase5Exit] This is observe-only/static handoff work. No subsystem backend success is fabricated."
Write-Host ""

$emitArgs = @(
    "--repo-root", $repoRoot,
    "--generated-root", $generatedRoot,
    "--out-dir", $outDir
)
& $python $emitter @emitArgs

if ($LASTEXITCODE -ne 0) {
    throw "Phase 5 exit reconnaissance artifact generation failed"
}

$surfaceJson = Join-Path $outDir "phase5-exit-subsystem-surface.json"
$surfaceMd = Join-Path $outDir "phase5-exit-subsystem-surface.md"
$firstTouch = Join-Path $outDir "phase5-exit-first-touch.txt"
$riskMap = Join-Path $outDir "phase6-risk-map.json"
$handoff = Join-Path $outDir "phase6-handoff.md"

foreach ($required in @($surfaceJson, $surfaceMd, $firstTouch, $riskMap, $handoff)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Phase 5 exit reconnaissance missing required output: $required"
    }
}

$surface = Get-Content -LiteralPath $surfaceJson -Raw | ConvertFrom-Json
$risk = Get-Content -LiteralPath $riskMap -Raw | ConvertFrom-Json
$handoffText = Get-Content -LiteralPath $handoff -Raw
$firstTouchText = Get-Content -LiteralPath $firstTouch -Raw

if ($surface.phase -ne "5-exit" -or
    $surface.repeatability.runs -ne 3 -or
    -not [bool]$surface.repeatability.all_passed -or
    $surface.repeatability.endpoint -ne "DIRECT_FRONTIER 0x0023A3CE -> 0x0014CD30" -or
    [int]$surface.repeatability.icall -ne 1262 -or
    [int]$surface.repeatability.direct -ne 1002 -or
    [int]$surface.repeatability.msize -ne 395 -or
    [int]$surface.repeatability.realloc -ne 4 -or
    [int]$surface.repeatability.final_msize -ne 2048 -or
    [int]$surface.repeatability.ticks -ne 73417 -or
    [int]$surface.repeatability.trace -ne 7322 -or
    [int]$surface.repeatability.fault -ne 0 -or
    [int]$surface.repeatability.xapi_return -ne 0) {
    throw "Phase 5 exit recon lost the proven Phase 5BV hardware baseline"
}

if ($surface.stable_endpoint_classification.status -ne "exact_generated_title_function" -or
    $surface.stable_endpoint_classification.address -ne "0x0014CD30") {
    throw "Phase 5 exit recon failed to classify stable endpoint 0x0014CD30"
}

$subsystems = @($surface.surfaces | ForEach-Object { $_.subsystem } | Sort-Object -Unique)
foreach ($requiredSubsystem in @(
    "graphics/display",
    "audio",
    "movies/video",
    "input",
    "cross-cutting"
)) {
    if ($subsystems -notcontains $requiredSubsystem) {
        throw "Phase 5 exit recon missing required subsystem: $requiredSubsystem"
    }
}

if ($surface.exit_gate.result -ne "PASS" -or
    -not [bool]$surface.exit_gate.repeatability_complete -or
    -not [bool]$surface.exit_gate.stable_endpoint_classified -or
    -not [bool]$surface.exit_gate.subsystem_inventory_complete -or
    -not [bool]$surface.exit_gate.hardware_first_touch_baseline_complete -or
    -not [bool]$surface.exit_gate.risk_map_complete -or
    -not [bool]$surface.exit_gate.ordered_handoff_complete -or
    [bool]$surface.exit_gate.backend_functionality_claimed) {
    throw "Phase 5 exit-recon gate contract mismatch"
}

if ($risk.phase -ne "6" -or @($risk.risks).Count -lt 5) {
    throw "Phase 6 risk map is incomplete"
}

foreach ($requiredText in @(
    "Phase 5 exit gate: **PASS**",
    "0x0014CD30",
    "First pixels",
    "Menu input",
    "Startup media",
    "Audio at/menu",
    "Gameplay hardening",
    "Phase 6 may begin"
)) {
    if (-not $handoffText.Contains($requiredText)) {
        throw "Phase 6 handoff is missing required text: $requiredText"
    }
}

foreach ($requiredText in @(
    "Hardware repeatability: 3/3 PASS",
    "XBE section XMV loaded",
    "XBE section XACTENG loaded",
    "XBE section D3D loaded",
    "XBE section XGRPH loaded",
    "XBE section DSOUND loaded",
    "XBE section WMADEC loaded",
    "caller=0x0023A3CE target=0x0014CD30"
)) {
    if (-not $firstTouchText.Contains($requiredText)) {
        throw "Phase 5 first-touch baseline is missing required evidence: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase5Exit] READY / PASS"
Write-Host ("[Phase5Exit] Endpoint classification : {0}" -f $surface.stable_endpoint_classification.status)
Write-Host ("[Phase5Exit] Endpoint generated body : {0}" -f $surface.stable_endpoint_classification.source)
Write-Host ("[Phase5Exit] Endpoint original end   : {0}" -f $surface.stable_endpoint_classification.original_end)
Write-Host ("[Phase5Exit] Subsystem families      : {0}" -f @($subsystems).Count)
Write-Host ("[Phase5Exit] Phase-6 risks           : {0}" -f @($risk.risks).Count)
Write-Host "[Phase5Exit] Required artifacts:"
Write-Host "[Phase5Exit]   $surfaceJson"
Write-Host "[Phase5Exit]   $surfaceMd"
Write-Host "[Phase5Exit]   $firstTouch"
Write-Host "[Phase5Exit]   $riskMap"
Write-Host "[Phase5Exit]   $handoff"
Write-Host ""
Write-Host "[Phase5Exit] If this command reports READY / PASS, no new Phase-5 XEX build is required."
Write-Host "[Phase5Exit] Phase 5 may be closed and Phase 6 implementation can begin."
