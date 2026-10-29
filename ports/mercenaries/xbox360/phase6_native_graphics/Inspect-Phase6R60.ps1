[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python not found"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r60_dsound_oom_source.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$report=Join-Path $root "build\phase6_native_graphics\phase6r60-dsound-oom-source-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R60 missing source input: $f"}
}
Write-Host "[Phase6R60] ZERO-BUILD F495 / 8007000E PRODUCER AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R60 Python syntax validation failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $report
if($LASTEXITCODE-ne0){throw "R60 source investigation failed"}
Write-Host "[Phase6R60] REPORT: $report"
if($CopyToClipboard){
  Get-Content -LiteralPath $report -Raw|Set-Clipboard
  Write-Host "[Phase6R60] Copied complete report to clipboard; paste in chat."
}
