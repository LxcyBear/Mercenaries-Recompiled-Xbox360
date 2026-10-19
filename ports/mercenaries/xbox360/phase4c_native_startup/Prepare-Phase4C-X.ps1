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
$emitter = Join-Path $phaseRoot "emit_phase4c_d980_closure.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\d980_closure_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-X input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-X] BOUNDED D980 DIRECT-CLOSURE PACKAGE"
Write-Host "[Phase4C-X] Phase 4C-W hardware PASS continued ordinal 149 and reached DIRECT_FRONTIER 0x0022D980 with fault=0."
Write-Host "[Phase4C-X] Promoting a bounded depth-2 translated closure rooted at 0x0022D980 (cap 16 members), while retaining the proven 0x0022F0FB closure."
Write-Host "[Phase4C-X] All previously proven startup invariants and kernel continuations remain active."
Write-Host "[Phase4C-X] Main/env build cookie is rotated to the X pair."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-X bounded D980 direct-closure package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$manifest = Join-Path $outDir "phase4c-x-manifest.json"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-D980-CLOSURE-20261019-A",
    "PASS: ordinal 149 KeSetTimer continuation armed",
    "PASS: bounded direct closure rooted at 0022D980 is packed for translated execution",
    "PASS: Phase 4C-X main/env build cookie matches",
    "PHASE 4C-X DIRECT-CLOSURE D980 RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-X main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-X RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-X EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-X EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435831",
    "PHASE 4C-X RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-X phase4c_env.cpp is missing marker: $requiredText"
    }
}

if (-not (Test-Path -LiteralPath $manifest)) {
    throw "Generated Phase 4C-X manifest is missing: $manifest"
}
$manifestJson = Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
if ($manifestJson.promoted_direct_frontier_target_6 -ne "0x0022D980") {
    throw "Phase 4C-X manifest D980 root mismatch"
}
if ([int]$manifestJson.promoted_closure_depth -ne 2) {
    throw "Phase 4C-X manifest depth mismatch"
}
if ($manifestJson.promoted_closure_members.Count -lt 1 -or $manifestJson.promoted_closure_members.Count -gt 16) {
    throw "Phase 4C-X promoted D980 closure member count is out of bounds"
}

Write-Host ""
Write-Host "[Phase4C-X] READY"
Write-Host "[Phase4C-X] Promoted D980 closure members: $($manifestJson.promoted_closure_members.Count)"
Write-Host "[Phase4C-X]   $($manifestJson.promoted_closure_members -join ', ')"
Write-Host "[Phase4C-X] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-X]   $main"
Write-Host "[Phase4C-X]   $env"
Write-Host "[Phase4C-X] The X cookie must be 0x50435831 (PCX1); stale W/V environment objects must fail closed."
Write-Host "[Phase4C-X] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-X] Expected build tag: P4C-D980-CLOSURE-20261019-A"
