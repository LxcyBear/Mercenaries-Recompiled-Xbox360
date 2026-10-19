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
$emitter = Join-Path $phaseRoot "emit_phase4c_promoted_direct_frontier.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\promoted_direct_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-L input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-L] PROMOTED DIRECT-FRONTIER CONTINUATION PACKAGE"
Write-Host "[Phase4C-L] Phase 4C-K hardware PASS reached DIRECT_FRONTIER 0x0022C47B from caller 0x0022C4DF with fault=0."
Write-Host "[Phase4C-L] Promoting only 0x0022C47B into the translated pack."
Write-Host "[Phase4C-L] Deeper direct calls remain deterministic DIRECT_FRONTIER boundaries."
Write-Host "[Phase4C-L] Startup DATA relocations 156/322/324 and first-fault provenance remain active."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-L promoted-direct package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($requiredText in @(
    "P4C-DIRECTC47B-20261019-A",
    "PASS: hardware-observed direct target 0022C47B is packed for translated execution",
    "PHASE 4C-L STARTUP DATA-THUNK PREP RESULT: PASS",
    "PHASE 4C-L PROMOTED DIRECT-FRONTIER RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-L main.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-L] READY"
Write-Host "[Phase4C-L] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-L]   $main"
Write-Host "[Phase4C-L]   $env"
Write-Host "[Phase4C-L] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-L] Expected build tag: P4C-DIRECTC47B-20261019-A"
