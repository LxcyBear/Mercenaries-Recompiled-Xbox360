[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6r38_dsound_driver_gate.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6R38 audit input: $f"}
}

Write-Host "[Phase6R38] ZERO-BUILD DSOUND DRIVER-PRESENT GATE AUDIT"
Write-Host "[Phase6R38] R36: XACT stage1 0029FDF0 returned 88780078"
Write-Host "[Phase6R38] R37: sole 88780078 literal is at 002A7B89"
Write-Host "[Phase6R38] Goal: reconstruct 0029FC4A -> NODRIVER owner and expose exact gate"
Write-Host "[Phase6R38] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6R38 audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6R38 source audit failed"}

Write-Host ""
Write-Host "[Phase6R38] DONE - paste this output back into ChatGPT."
