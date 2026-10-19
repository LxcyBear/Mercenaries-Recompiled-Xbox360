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
$emitter = Join-Path $phaseRoot "emit_phase4c_hardware_info_fixup.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\hardware_info_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-J input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-J] XBOXHARDWAREINFO DATA-THUNK CONTINUATION PACKAGE"
Write-Host "[Phase4C-J] Phase 4C-I proved READ32 0x80000142 = ordinal 322 / XboxHardwareInfo."
Write-Host "[Phase4C-J] Relocating only that DATA import to guest kernel data VA 0x0087E000."
Write-Host "[Phase4C-J] Callable ordinal tokens remain untouched."
Write-Host "[Phase4C-J] Build-B immediate first-fault provenance remains enabled."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-J XboxHardwareInfo data-thunk package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($requiredText in @(
    "P4C-HWINFO-20261019-A",
    "DATA THUNK FIXUP: ordinal=322 XboxHardwareInfo",
    "PHASE 4C-J DATA-THUNK PREP RESULT: PASS",
    "PHASE 4C-J XBOXHARDWAREINFO DATA-THUNK RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-J main.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-J] READY"
Write-Host "[Phase4C-J] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-J]   $main"
Write-Host "[Phase4C-J]   $env"
Write-Host "[Phase4C-J] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-J] Expected build tag: P4C-HWINFO-20261019-A"
