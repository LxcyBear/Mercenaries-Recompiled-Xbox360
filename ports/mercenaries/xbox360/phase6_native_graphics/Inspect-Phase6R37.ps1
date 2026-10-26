[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6r37_dsound_nodriver.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6R37 audit input: $f"}
}

Write-Host "[Phase6R37] ZERO-BUILD DIRECTSOUND NODRIVER AUDIT"
Write-Host "[Phase6R37] R36 hardware proof: sub_0029FDF0 returned 88780078 (DSERR_NODRIVER)"
Write-Host "[Phase6R37] Goal: identify the exact branch/callee that decides no audio driver exists"
Write-Host "[Phase6R37] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6R37 audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6R37 source audit failed"}

Write-Host ""
Write-Host "[Phase6R37] DONE - paste this output back into ChatGPT."
