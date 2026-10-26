[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$script = Join-Path $PSScriptRoot "inspect_phase6r42_write8_fault.py"
$source = Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"

$python = Join-Path $root ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python)) {
    $cmd = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $cmd) { throw "Python not found (.venv missing and no python on PATH)" }
    $python = $cmd.Source
}

foreach ($f in @($script, $source)) {
    if (-not (Test-Path -LiteralPath $f)) { throw "Missing Phase 6R42 audit input: $f" }
}

Write-Host "[Phase6R42] ZERO-BUILD WRITE8 FAULT AUDIT"
Write-Host "[Phase6R42] R41 crossed AC97 BDBAR and faulted WRITE8 DEA85111"
Write-Host "[Phase6R42] Goal: exact translated write site + AC97 offset-table provenance"
Write-Host "[Phase6R42] No source mutation. No build. No hardware run."
Write-Host ""

& $python -m py_compile $script
if ($LASTEXITCODE -ne 0) { throw "Phase 6R42 audit script syntax check failed" }

& $python $script "--source" $source
if ($LASTEXITCODE -ne 0) { throw "Phase 6R42 source audit failed" }

Write-Host ""
Write-Host "[Phase6R42] DONE - paste this output back into ChatGPT."
