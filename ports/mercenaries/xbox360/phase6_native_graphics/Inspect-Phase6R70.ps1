[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not (Test-Path -LiteralPath $python -PathType Leaf)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null -eq $cmd){throw "Python unavailable"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r70_dsound_pool_pointer_abi.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$report=Join-Path $root "build\phase6_native_graphics\phase6r70-pool-pointer-abi.txt"
foreach($f in @($script,$source)){
  if(-not (Test-Path -LiteralPath $f -PathType Leaf)){throw "R70 required input missing: $f"}
}
Write-Host "[Phase6R70] ZERO-BUILD WRONG-POOL-POINTER ABI INVESTIGATION"
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "R70 Python preflight failed"}
& $python -u $script --source $source 2>&1 | Tee-Object -FilePath $report
if($LASTEXITCODE -ne 0){throw "R70 source audit failed; report: $report"}
Write-Host "[Phase6R70] REPORT: $report"
if($CopyToClipboard){
  Get-Content -LiteralPath $report -Raw | Set-Clipboard
  Write-Host "[Phase6R70] Copied report to clipboard."
}
