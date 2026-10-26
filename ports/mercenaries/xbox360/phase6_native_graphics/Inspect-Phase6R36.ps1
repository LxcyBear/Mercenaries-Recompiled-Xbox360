[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6r36_xact_init_failure.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6R36 audit input: $f"}
}

Write-Host "[Phase6R36] ZERO-BUILD XACT INIT FAILURE AUDIT"
Write-Host "[Phase6R36] Proven owner: sub_0027F3DC releases only after sub_0027DC5B returns failure"
Write-Host "[Phase6R36] Goal: isolate the exact 0027DC5B failing call/status path"
Write-Host "[Phase6R36] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6R36 audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6R36 source audit failed"}

Write-Host ""
Write-Host "[Phase6R36] DONE - paste this output back into ChatGPT."
