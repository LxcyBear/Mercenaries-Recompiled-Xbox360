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
$script=Join-Path $PSScriptRoot "inspect_phase6r73_apu_xgscnt.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$cached=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$out=Join-Path $root "build\phase6_native_graphics\phase6r73-xgscnt-read-audit.txt"
foreach($f in @($script,$source,$cached)){
  if(-not (Test-Path -LiteralPath $f -PathType Leaf)){
    throw "R73 input missing: $f"
  }
}
Write-Host "[Phase6R73] ZERO-BUILD APU SAMPLE COUNTER REGISTER READ AUDIT"
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "R73 Python syntax preflight failed"}
& $python -u $script --source $source --cached-main $cached 2>&1 |
  Tee-Object -FilePath $out
if($LASTEXITCODE -ne 0){throw "R73 audit failed; report: $out"}
Write-Host "[Phase6R73] REPORT: $out"
if($CopyToClipboard){
  Get-Content -LiteralPath $out -Raw | Set-Clipboard
  Write-Host "[Phase6R73] Full report copied to clipboard."
}
