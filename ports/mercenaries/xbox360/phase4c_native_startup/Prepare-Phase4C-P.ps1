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
$emitter = Join-Path $phaseRoot "emit_phase4c_dpc107_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\dpc107_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-P input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-P] KEINITIALIZEDPC CONTINUATION PACKAGE"
Write-Host "[Phase4C-P] Phase 4C-O hardware PASS executed 0x0022F128 and reached ICALL_SAFE 0x8000006B with fault=0."
Write-Host "[Phase4C-P] Ordinal 107 = KeInitializeDpc; production ABI = 12 argument bytes."
Write-Host "[Phase4C-P] Validate the 16-byte live frame, initialize/read back the 32-byte guest KDPC exactly, return eax=0, and resume."
Write-Host "[Phase4C-P] All prior startup evidence remains active."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-P KeInitializeDpc continuation package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-DPC107-20261019-A",
    "PASS: ordinal 107 KeInitializeDpc continuation armed",
    "KeInitializeDpc LIVE FRAME:",
    "PHASE 4C-P KEINITIALIZEDPC RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-P main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-P RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-P EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-P EXECUTION ENVIRONMENT RESULT: PASS",
    "PHASE 4C-P RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-P phase4c_env.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-P] READY"
Write-Host "[Phase4C-P] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-P]   $main"
Write-Host "[Phase4C-P]   $env"
Write-Host "[Phase4C-P] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-P] Expected build tag: P4C-DPC107-20261019-A"
