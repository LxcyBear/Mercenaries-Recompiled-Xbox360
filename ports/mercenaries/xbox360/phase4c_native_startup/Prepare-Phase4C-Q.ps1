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
$emitter = Join-Path $phaseRoot "emit_phase4c_timer113_continue.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\timer113_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-Q input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-Q] KEINITIALIZETIMEREX CONTINUATION PACKAGE"
Write-Host "[Phase4C-Q] Phase 4C-P hardware PASS handled ordinal 107 and reached ICALL_SAFE 0x80000071 with fault=0."
Write-Host "[Phase4C-Q] Ordinal 113 = KeInitializeTimerEx; production ABI = 8 argument bytes."
Write-Host "[Phase4C-Q] Validate the 12-byte frame, initialize/read back the 40-byte guest KTIMER, return eax=0, and resume."
Write-Host "[Phase4C-Q] A link-time main/env build cookie is required so a stale phase4c_env.cpp cannot link silently."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-Q KeInitializeTimerEx continuation package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw
$envText = Get-Content -LiteralPath $env -Raw

foreach ($requiredText in @(
    "P4C-TIMER113-20261019-A",
    "PASS: ordinal 113 KeInitializeTimerEx continuation armed",
    "KeInitializeTimerEx LIVE FRAME:",
    "PASS: Phase 4C-Q main/env build cookie matches",
    "PHASE 4C-Q KEINITIALIZETIMEREX RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-Q main.cpp is missing marker: $requiredText"
    }
}

foreach ($requiredText in @(
    "PHASE 4C-Q RETAIL ENVIRONMENT PREP START",
    "PHASE 4C-Q EXACT RETAIL VERIFICATION: PASS",
    "PHASE 4C-Q EXECUTION ENVIRONMENT RESULT: PASS",
    "phase4c_env_build_cookie",
    "50435131",
    "PHASE 4C-Q RETAIL ENVIRONMENT PREP END"
)) {
    if ($envText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-Q phase4c_env.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-Q] READY"
Write-Host "[Phase4C-Q] Build BOTH freshly generated sources in the same XDK project:"
Write-Host "[Phase4C-Q]   $main"
Write-Host "[Phase4C-Q]   $env"
Write-Host "[Phase4C-Q] If the project still references an older env source, the build should now fail at link-time on phase4c_env_build_cookie."
Write-Host "[Phase4C-Q] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-Q] Expected build tag: P4C-TIMER113-20261019-A"
