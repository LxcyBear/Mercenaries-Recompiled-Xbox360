[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\xact_global_0028836c_write_site_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6dh_xact_release_chain.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DH audit input: $f"}
}

Write-Host "[Phase6DH] ZERO-BUILD XACT RELEASE/DESTRUCTOR CHAIN AUDIT"
Write-Host "[Phase6DH] Targets: sub_0027F055 + sub_0027F282"
Write-Host "[Phase6DH] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6DH audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6DH source audit failed"}

Write-Host ""
Write-Host "[Phase6DH] DONE - paste this output back into ChatGPT."
