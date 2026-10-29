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
$script=Join-Path $PSScriptRoot "inspect_phase6r53_callback_object.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r53-callback-object-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "Missing R53 audit input: $f"}
}
Write-Host "[Phase6R53] ZERO-BUILD CALLBACK / OBJECT PROVENANCE"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R53 audit Python preflight failed"}
& $python $script --source $source 2>&1 | Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R53 source audit failed"}
Write-Host "[Phase6R53] REPORT: $log"
if($CopyToClipboard){
  Get-Content -LiteralPath $log -Raw | Set-Clipboard
  Write-Host "[Phase6R53] Complete report copied to clipboard"
}
