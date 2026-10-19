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
$emitter = Join-Path $phaseRoot "emit_phase4c_kernel_header.py"
$phase3nTemplate = Join-Path $repoRoot "ports\mercenaries\xbox360\phase3n_xdk_scale_xex\main_template.cpp"
$phase2eSource = Join-Path $repoRoot "ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp"
$outDir = Join-Path $repoRoot "build\phase4c_native_startup\kernel_header_xdk"

foreach ($required in @($python,$generatedRoot,$functionsPath,$entryReport,$threadReport,$baseEmitter,$emitter,$phase3nTemplate,$phase2eSource)) {
    if (-not (Test-Path -LiteralPath $required)) { throw "Required Phase 4C-M input is missing: $required" }
}

if (Test-Path -LiteralPath $outDir) { Remove-Item -LiteralPath $outDir -Recurse -Force }
New-Item -ItemType Directory -Force -Path $outDir | Out-Null

Write-Host "[Phase4C-M] XBOXKRNL PE-HEADER CONTINUATION PACKAGE"
Write-Host "[Phase4C-M] Phase 4C-L hardware PASS reached READ32 0x8001003C inside translated 0x0022C47B."
Write-Host "[Phase4C-M] 0x80010000-0x80010FFF remains separate from title RAM."
Write-Host "[Phase4C-M] Supplying a minimal synthetic xboxkrnl PE header: MZ, e_lfanew=0x80, PE signature, I386, zero sections."
Write-Host "[Phase4C-M] Startup DATA relocations 156/322/324 and first-fault provenance remain active."
Write-Host ""

& $python $emitter "--base-emitter" $baseEmitter "--generated-root" $generatedRoot "--functions" $functionsPath "--entry-report" $entryReport "--thread-report" $threadReport "--phase3n-template" $phase3nTemplate "--phase2e-source" $phase2eSource "--out-dir" $outDir
if ($LASTEXITCODE -ne 0) { throw "Phase 4C-M kernel-header package emission failed." }

$main = Join-Path $outDir "main.cpp"
$env = Join-Path $outDir "phase4c_env.cpp"
$mainText = Get-Content -LiteralPath $main -Raw

foreach ($requiredText in @(
    "P4C-KHDR-20261019-A",
    "KERNEL HEADER MODEL: base=80010000 e_lfanew=00000080 sections=0 size=4096",
    "PHASE 4C-M KERNEL HEADER PREP RESULT: PASS",
    "PHASE 4C-M KERNEL HEADER RESULT"
)) {
    if ($mainText -notlike "*$requiredText*") {
        throw "Generated Phase 4C-M main.cpp is missing marker: $requiredText"
    }
}

Write-Host ""
Write-Host "[Phase4C-M] READY"
Write-Host "[Phase4C-M] Build BOTH generated sources in the same XDK project:"
Write-Host "[Phase4C-M]   $main"
Write-Host "[Phase4C-M]   $env"
Write-Host "[Phase4C-M] Keep the exact supported retail default.xbe beside the XEX."
Write-Host "[Phase4C-M] Expected build tag: P4C-KHDR-20261019-A"
