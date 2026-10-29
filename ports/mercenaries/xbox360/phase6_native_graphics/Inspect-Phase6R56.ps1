[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python interpreter unavailable"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r56_xact_stage1.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r56-stage1-failure-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R56 missing audit input: $f"}
}
Write-Host "[Phase6R56] ZERO-BUILD XACT STAGE-ONE FAILURE AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R56 audit syntax check failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R56 audit failed"}
Write-Host "[Phase6R56] REPORT: $log"
if($CopyToClipboard){
  Get-Content -LiteralPath $log -Raw | Set-Clipboard
  Write-Host "[Phase6R56] Clipboard contains the entire report. Pasting is sufficient; no need to find the saved text file."
}
