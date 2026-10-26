[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$script=Join-Path $PSScriptRoot "inspect_phase6_true_tu.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python not found"}
  $python=$cmd.Source
}
foreach($f in @($script,$source)){if(-not(Test-Path -LiteralPath $f)){throw "Missing Phase6TU input: $f"}}
Write-Host "[Phase6TU] TRUE COMPILATION-UNIT SHARDING READINESS AUDIT"
Write-Host "[Phase6TU] No source mutation. No VS build."
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "Phase6TU syntax check failed"}
& $python $script "--source" $source
if($LASTEXITCODE-ne0){throw "Phase6TU audit failed"}
