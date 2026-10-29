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
$script=Join-Path $PSScriptRoot "inspect_phase6r55_xact_release_ownership.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r55-release-ownership-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R55 missing audit input: $f"}
}
Write-Host "[Phase6R55] ZERO-BUILD XACT RELEASE OWNERSHIP AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R55 syntax validation failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R55 audit failed"}
Write-Host "[Phase6R55] REPORT: $log"
if($CopyToClipboard){
  Get-Content -LiteralPath $log -Raw | Set-Clipboard
  Write-Host "[Phase6R55] Report copied to clipboard"
}
