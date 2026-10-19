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

$emitter = Join-Path $phaseRoot "emit_phase4c_startup_slice.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\xdk"

foreach ($required in @(
    $python,
    $generatedRoot,
    $functionsPath,
    $closureReport,
    $phase4Report,
    $emitter,
    $phase3nTemplate,
    $phase2eSource
)) {
    if (-not (Test-Path -LiteralPath $required)) {
        throw "Required Phase 4C-B input is missing: $required"
    }
}

$closure = Get-Content -LiteralPath $closureReport -Raw | ConvertFrom-Json
if ($closure.phase -ne "4C-A" -or -not [bool]$closure.structural_pass) {
    throw "Phase 4C-A closure report is not a structural PASS."
}
if ($closure.entry -ne "0x0022964A") {
    throw "Unexpected Phase 4C-A entry: $($closure.entry)"
}
if ($closure.entry_resolution.kind -ne "exact_function") {
    throw "Phase 4C-B requires an exact translated entry function."
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
        throw "Phase 4C-B service baseline changed: $name expected $($expected[$name]), got $($c.$name)."
    }
}

if (Test-Path -LiteralPath $outDir) {
    Remove-Item -LiteralPath $outDir -Recurse -Force
}
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-B] FIRST REAL TRANSLATED STARTUP PACKAGE"
Write-Host "[Phase4C-B] 4C-A structural PASS confirmed."
Write-Host "[Phase4C-B] Phase 4B final split confirmed: 0 direct / 15 platform-bound / 2 guest-native."
Write-Host "[Phase4C-B] Emitting local retail-derived closure; no generated retail C is committed."
Write-Host ""

& $python $emitter "--generated-root" $generatedRoot "--functions" $functionsPath "--closure-report" $closureReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4C-B startup package emission failed."
}

Write-Host ""
Write-Host "[Phase4C-B] READY"
Write-Host "[Phase4C-B] Add BOTH generated sources to the known-good XDK diagnostic project:"
Write-Host "[Phase4C-B]   $(Join-Path $outDir "main.cpp")"
Write-Host "[Phase4C-B]   $(Join-Path $outDir "phase4c_env.cpp")"
Write-Host "[Phase4C-B] Keep your supported retail default.xbe beside the resulting XEX as game:\default.xbe."
Write-Host "[Phase4C-B] Expected build tag: P4C-STARTUP-20261019-A"
Write-Host "[Phase4C-B] Runtime stops at the first live ICALL/ITAIL boundary by design."
