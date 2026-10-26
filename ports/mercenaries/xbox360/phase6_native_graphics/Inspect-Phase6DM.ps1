[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\xact_release_pretrace_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6dm_xact_direct_frontier_owner.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DM audit input: $f"}
}

Write-Host "[Phase6DM] ZERO-BUILD XACT DIRECT-FRONTIER OWNER AUDIT"
Write-Host "[Phase6DM] Proven source form: phase4c_direct_frontier(0x0027F2C2u)"
Write-Host "[Phase6DM] Goal: identify the translated function that owns the final Release call"
Write-Host "[Phase6DM] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6DM audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6DM source audit failed"}

Write-Host ""
Write-Host "[Phase6DM] DONE - paste this output back into ChatGPT."
