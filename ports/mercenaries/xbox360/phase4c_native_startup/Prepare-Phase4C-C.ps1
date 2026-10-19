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
$closureReport = Join-Path $repoRoot "build\phase4c_native_startup\phase4c-startup-closure.json"
$phase4Report = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"

$baseEmitter = Join-Path $phaseRoot "emit_phase4c_startup_slice.py"
$threadEmitter = Join-Path $phaseRoot "emit_phase4c_thread_handoff.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\thread_xdk"

foreach ($required in @(
    $python,
    $generatedRoot,
    $functionsPath,
    $closureReport,
    $phase4Report,
    $baseEmitter,
    $threadEmitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 4C-C input is missing: $required"
    }
}

$closure = Get-Content -LiteralPath $closureReport -Raw | ConvertFrom-Json
if ($closure.phase -ne "4C-A" -or -not [bool]$closure.structural_pass) {
    throw "Phase 4C-A closure report is not a structural PASS."
}
if ($closure.entry -ne "0x0022964A") {
    throw "Unexpected Phase 4C-A entry: $($closure.entry)"
}

$phase4 = Get-Content -LiteralPath $phase4Report -Raw | ConvertFrom-Json
$c = $phase4.counts
$expected = @{
    imports = 111
    guest_bridge_explicit = 74
    guest_data_exports = 11
    guest_fallback = 26
    guest_arg_metadata_missing = 0
    guest_arg_metadata_mismatch = 0
    host_surface_flagged = 0
    platform_surface_bound = 15
    guest_native_bound = 2
    fallback_referenced_imports = 0
    fallback_static_refs = 0
}
foreach ($name in $expected.Keys) {
    if ([int]$c.$name -ne [int]$expected[$name]) {
        throw "Phase 4C-C service baseline changed: $name expected $($expected[$name]), got $($c.$name)."
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-C] FIRST STARTUP-THREAD HANDOFF PACKAGE"
Write-Host "[Phase4C-C] Phase 4C-B hardware boundary: 0x0022B4D7 -> 0x800000FF (PsCreateSystemThreadEx)."
Write-Host "[Phase4C-C] Expected ordinal-255 frame: 40 argument bytes + 4-byte synthetic CALL return."
Write-Host "[Phase4C-C] Reusing the exact 40-body 4C-B entry closure; no guessed thread routine is packed."
Write-Host ""

& $python $threadEmitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--closure-report" $closureReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4C-C thread-handoff package emission failed."
}

Write-Host ""
Write-Host "[Phase4C-C] READY"
Write-Host "[Phase4C-C] Build BOTH generated sources in the same XDK diagnostic project:"
Write-Host "[Phase4C-C]   $(Join-Path $outDir "main.cpp")"
Write-Host "[Phase4C-C]   $(Join-Path $outDir "phase4c_env.cpp")"
Write-Host "[Phase4C-C] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-C] Expected build tag: P4C-THREAD-20261019-B"
Write-Host "[Phase4C-C] Runtime validates ordinal 255, logs the actual StartRoutine/contexts, and stops successfully at THREAD_TARGET."
