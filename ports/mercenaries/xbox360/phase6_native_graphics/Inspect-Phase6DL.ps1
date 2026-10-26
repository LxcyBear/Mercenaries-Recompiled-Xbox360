[CmdletBinding()]
param()

$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
$source=Join-Path $root "build\phase6_native_graphics\xact_release_pretrace_xdk\main_monolithic.cpp"
$script=Join-Path $PSScriptRoot "inspect_phase6dl_xact_release_origin.py"

foreach($f in @($python,$source,$script)){
  if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase 6DL audit input: $f"}
}

Write-Host "[Phase6DL] ZERO-BUILD XACT FINAL-RELEASE ORIGIN AUDIT"
Write-Host "[Phase6DL] Hardware proof: packed lookup caller=0023A3CE target=0027F2C2 root=01B5C320 ref=1"
Write-Host "[Phase6DL] Targets: sub_0023A3CE + sub_0027F2C2"
Write-Host "[Phase6DL] No build. No generated-source mutation. No runtime changes."
Write-Host ""

& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase 6DL audit script syntax check failed"}

& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase 6DL source audit failed"}

Write-Host ""
Write-Host "[Phase6DL] DONE - paste this output back into ChatGPT."
