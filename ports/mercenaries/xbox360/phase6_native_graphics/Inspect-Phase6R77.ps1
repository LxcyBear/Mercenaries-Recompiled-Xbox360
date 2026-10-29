[CmdletBinding()]
param([switch]$CopyToClipboard)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){
  $cmd=Get-Command python -ErrorAction SilentlyContinue
  if($null -eq $cmd){throw "Python unavailable"}
  $python=$cmd.Source
}
$script=Join-Path $PSScriptRoot "inspect_phase6r77_kernel_time128.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$main=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$report=Join-Path $root "build\phase6_native_graphics\phase6r77-kernel-time128.txt"
foreach($f in @($script,$source,$main)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R77 input missing: $f"}
}
Write-Host "[Phase6R77] ZERO-BUILD: ordinal 128 KeQuerySystemTime kernel dispatch ABI"
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "R77 Python syntax preflight failed"}
$prior=$ErrorActionPreference
$ErrorActionPreference="Continue"
try {
  & $python -u $script --source $source --cached-main $main 2>&1 |
    Tee-Object -FilePath $report
  $code=$LASTEXITCODE
} finally {$ErrorActionPreference=$prior}
if($code -ne 0){
  $tail=@(Get-Content -LiteralPath $report -Tail 24) -join [Environment]::NewLine
  throw ("R77 audit failed: exit {0}{1}{2}{1}Report: {3}" -f $code,[Environment]::NewLine,$tail,$report)
}
Write-Host "[Phase6R77] REPORT: $report"
if($CopyToClipboard){
  Get-Content -LiteralPath $report -Raw | Set-Clipboard
  Write-Host "[Phase6R77] Full report copied to clipboard."
}
