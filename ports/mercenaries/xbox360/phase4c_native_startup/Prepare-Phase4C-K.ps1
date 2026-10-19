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
$emitter = Join-Path $phaseRoot "emit_phase4c_startup_data_fixup.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\startup_data_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-K input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-K] STARTUP KERNEL-DATA THUNK CONTINUATION PACKAGE"
Write-Host "[Phase4C-K] Hardware proved ordinal 322 / XboxHardwareInfo and ordinal 324 / XboxKrnlVersion are dereferenced as data."
Write-Host "[Phase4C-K] Phase-2E also initializes ordinal 156 / KeTickCount."
Write-Host "[Phase4C-K] Relocating exactly initialized DATA imports 156/322/324; all other import tokens remain untouched."
Write-Host "[Phase4C-K] Immediate first-fault provenance remains enabled."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-K startup data-thunk package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($requiredText in @(
    "P4C-KDATA3-20261019-A",
    "PASS: startup data imports 156/322/324 point at initialized guest kernel data",
    "PHASE 4C-K STARTUP DATA-THUNK PREP RESULT: PASS",
    "PHASE 4C-K STARTUP DATA-THUNK RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-K main.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-K] READY"
Write-Host "[Phase4C-K] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-K]   $main"
Write-Host "[Phase4C-K]   $env"
Write-Host "[Phase4C-K] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-K] Expected build tag: P4C-KDATA3-20261019-A"
