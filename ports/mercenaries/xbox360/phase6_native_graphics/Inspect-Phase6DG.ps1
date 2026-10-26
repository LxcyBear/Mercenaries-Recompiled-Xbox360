[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\xact_global_0028836c_write_site_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6dg_xact_teardown_0027f194.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DG audit input: $f"}
}

Write-Host "[Phase6DG] ZERO-BUILD XACT TEARDOWN AUDIT"
Write-Host "[Phase6DG] Hardware culprit: sub_0027F194 -> WRITE32(0028836C, 0)"
Write-Host "[Phase6DG] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6DG audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6DG source audit failed"}

Write-Host ""
Write-Host "[Phase6DG] DONE - paste this output back into ChatGPT."
