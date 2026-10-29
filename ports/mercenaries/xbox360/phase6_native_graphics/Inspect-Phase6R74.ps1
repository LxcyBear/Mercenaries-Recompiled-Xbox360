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
$script=Join-Path $PSScriptRoot "inspect_phase6r74_xgscnt_read_site.py"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$main=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$report=Join-Path $root "build\phase6_native_graphics\phase6r74-xgscnt-read-site.txt"
foreach($f in @($script,$source,$main)){
  if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "R74 missing: $f"}
}
Write-Host "[Phase6R74] ZERO-BUILD: FE80200C exact read site and MMIO handler provenance"
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "R74 Python preflight failed"}
# Native Python stderr becomes a PowerShell error record under 5.1.
# Keep it non-terminating during capture so the COMPLETE traceback lands
# in the report; fail explicitly using the native process exit code.
$previousErrorActionPreference=$ErrorActionPreference
$ErrorActionPreference="Continue"
try {
  & $python -u $script --source $source --cached-main $main 2>&1 |
    Tee-Object -FilePath $report
  $auditExitCode=$LASTEXITCODE
}
finally {
  $ErrorActionPreference=$previousErrorActionPreference
}
if($auditExitCode -ne 0){
  $tail=@(Get-Content -LiteralPath $report -Tail 24) -join [Environment]::NewLine
  throw ("R74 audit failed (exit {0}).{1}{2}{1}Report: {3}" -f $auditExitCode,[Environment]::NewLine,$tail,$report)
}
Write-Host "[Phase6R74] REPORT: $report"
if($CopyToClipboard){
  Get-Content -LiteralPath $report -Raw | Set-Clipboard
  Write-Host "[Phase6R74] Full report copied to clipboard."
}
