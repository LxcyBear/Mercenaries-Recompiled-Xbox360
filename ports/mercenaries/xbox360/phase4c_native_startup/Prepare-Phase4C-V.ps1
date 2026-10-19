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
$baseEmitter = Join-Path $phaseRoot "emit_phase4c_startup_slice.py"
$emitter = Join-Path $phaseRoot "emit_phase4c_f0fb_closure.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\f0fb_closure_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-V input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-V] BOUNDED DIRECT CLOSURE PACKAGE"
Write-Host "[Phase4C-V] Phase 4C-U hardware PASS continued ordinal 301 and reached DIRECT_FRONTIER 0x0022F0FB with fault=0."
Write-Host "[Phase4C-V] Promoting a bounded depth-2 translated closure rooted at 0x0022F0FB (cap 16 members)."
Write-Host "[Phase4C-V] All previously proven startup invariants and kernel continuations remain active."
Write-Host "[Phase4C-V] Main/env build cookie is rotated to the V pair."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-V bounded direct-closure package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$manifest = Join-Path $outDir "phase4c-v-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-F0FB-CLOSURE-20261019-A",
    "PASS: ordinal 301 RtlNtStatusToDosError continuation armed",
    "PASS: bounded direct closure rooted at 0022F0FB is packed for translated execution",
    "PASS: Phase 4C-V main/env build cookie matches",
    "PHASE 4C-V DIRECT-CLOSURE F0FB RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-V main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-V RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-V EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-V EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435631",
    "PHASE 4C-V RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-V phase4c_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 4C-V manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.promoted_direct_frontier_target_5 -ne "0x0022F0FB") {
    throw "Phase 4C-V manifest root mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 2) {
    throw "Phase 4C-V manifest depth mismatch"
}
if ($manifestJson.promoted_closure_members.Count -lt 1 -or $manifestJson.promoted_closure_members.Count -gt 16) {
    throw "Phase 4C-V promoted closure member count is out of bounds"
}

Write-Host ""
Write-Host "[Phase4C-V] READY"
Write-Host "[Phase4C-V] Promoted closure members: $($manifestJson.promoted_closure_members.Count)"
Write-Host "[Phase4C-V]   $($manifestJson.promoted_closure_members -join ', ')"
Write-Host "[Phase4C-V] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-V]   $main"
Write-Host "[Phase4C-V]   $env"
Write-Host "[Phase4C-V] The V cookie must be 0x50435631 (PCV1); stale U/T environment objects must fail closed."
Write-Host "[Phase4C-V] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-V] Expected build tag: P4C-F0FB-CLOSURE-20261019-A"
