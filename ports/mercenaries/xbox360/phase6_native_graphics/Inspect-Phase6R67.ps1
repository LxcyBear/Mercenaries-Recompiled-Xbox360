[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python unavailable"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r67_dsound_pool_seed.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$report=Join-Path $root "build\phase6_native_graphics\phase6r67-pool-seed-provenance.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R67 input missing: $f"}
}
Write-Host "[Phase6R67] ZERO-BUILD DSOUND FREE-LIST INITIALIZER AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R67 Python syntax preflight failed"}
& $python -u $script --source $source 2>&1 | Tee-Object -FilePath $report
if($LASTEXITCODE-ne0){throw "R67 zero-build audit failed; report: $report"}
Write-Host "[Phase6R67] REPORT: $report"
if($CopyToClipboard){
  Get-Content -LiteralPath $report -Raw | Set-Clipboard
  Write-Host "[Phase6R67] Full report copied to clipboard."
}
