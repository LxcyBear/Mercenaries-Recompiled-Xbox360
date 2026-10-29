[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null-eq$cmd){throw "Python executable not found"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r54_xact_lifecycle.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r54-xact-lifecycle-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "Missing R54 input: $f"}
}
Write-Host "[Phase6R54] ZERO-BUILD XACT ROOT LIFECYCLE AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R54 audit Python syntax preflight failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R54 audit failed"}
Write-Host "[Phase6R54] REPORT: $log"
if($CopyToClipboard){
  Get-Content -LiteralPath $log -Raw | Set-Clipboard
  Write-Host "[Phase6R54] Complete report copied to clipboard"
}
