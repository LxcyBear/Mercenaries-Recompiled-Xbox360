[CmdletBinding()]
param(
  [string]$RetailXbe = "",
  [string[]]$HardwareLog = @(),
  [switch]$CopySummary
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\.."))
$python=Join-Path $root ".venv\Scripts\python.exe"
if(-not(Test-Path -LiteralPath $python -PathType Leaf)){
  $command=Get-Command python -ErrorAction SilentlyContinue
  if($null -eq $command){throw "Python is unavailable"}
  $python=$command.Source
}
$main=Join-Path $root "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$source=Join-Path $root "build\phase6_native_graphics\r59_fc4a_abi_repair\main_monolithic_r59.cpp"
$script=Join-Path $PSScriptRoot "Build-IntegrationMap.py"
$out=Join-Path $root "build\phase6_integration_map"
foreach($path in @($script,$main,$source)){
  if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
    throw "Integration map prerequisite missing: $path"
  }
}
New-Item -ItemType Directory -Force -Path $out | Out-Null
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "Integration map Python syntax check failed"}
$scanArgs=@("--main",$main,"--source",$source,"--out",$out)
if($RetailXbe){
  if(-not(Test-Path -LiteralPath $RetailXbe -PathType Leaf)){throw "Retail XBE file missing: $RetailXbe"}
  $scanArgs+=@("--retail-xbe",$RetailXbe)
}
foreach($path in $HardwareLog){
  if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw "Xbox log file missing: $path"}
  $scanArgs+=@("--hardware-log",$path)
}
Write-Host "[IntegrationMap] Phase 6DQ diagnostic baseline frozen, building source coverage map"
Write-Host "[IntegrationMap] No XDK build, no mutation to guest runtime or TrueTU shards"
$oldPreference=$ErrorActionPreference
$ErrorActionPreference="Continue"
try {
  & $python -u $script @scanArgs 2>&1 |
    Tee-Object -FilePath (Join-Path $out "run.log")
  $code=$LASTEXITCODE
} finally {$ErrorActionPreference=$oldPreference}
if($code -ne 0){
  $tail=@(Get-Content -LiteralPath (Join-Path $out "run.log") -Tail 30) -join [Environment]::NewLine
  throw ("Integration map exited {0}{1}{2}{1}Report: {3}" -f $code,[Environment]::NewLine,$tail,(Join-Path $out "run.log"))
}
if($CopySummary){
  Get-Content -LiteralPath (Join-Path $out "PHASE6_MAP.md") -Raw | Set-Clipboard
  Write-Host "[IntegrationMap] Summary copied to clipboard"
}
Write-Host "[IntegrationMap] OUTPUT: $out"
Write-Host "[IntegrationMap] User XBE and raw logs remain private/local"
