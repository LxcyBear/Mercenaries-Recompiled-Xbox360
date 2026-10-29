[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python not installed or unavailable in PATH"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r57_dsound_status_producer.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r57-dsound-status-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R57 missing input: $f"}
}
Write-Host "[Phase6R57] ZERO-BUILD DIRECTSOUND STATUS PRODUCER AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R57 Python syntax preflight failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R57 audit failed"}
Write-Host "[Phase6R57] REPORT: $log"
if($CopyToClipboard){
  Get-Content -LiteralPath $log -Raw | Set-Clipboard
  Write-Host "[Phase6R57] Copied to clipboard; paste into ChatGPT. No need to browse for the .txt file."
}
