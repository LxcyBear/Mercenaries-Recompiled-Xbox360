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
$script=Join-Path $PSScriptRoot "inspect_phase6r48_audio_esi_chain.py"
$source=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\main_monolithic.cpp"
$log=Join-Path $root "build\phase6_native_graphics\phase6r48-esi-audit.txt"
foreach($f in @($script,$source)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "Missing R48 audit input: $f"}
}
Write-Host "[Phase6R48] SOURCE-ONLY ESI PROVENANCE AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE-ne0){throw "R48 audit syntax check failed"}
& $python $script --source $source 2>&1|Tee-Object -FilePath $log
if($LASTEXITCODE-ne0){throw "R48 audit failed"}
Write-Host "[Phase6R48] REPORT: $log"
if($CopyToClipboard){
 Get-Content -LiteralPath $log -Raw | Set-Clipboard
 Write-Host "[Phase6R48] Complete report copied to clipboard"
}
