[CmdletBinding()]
param([string]$RetailXbe = "$env:USERPROFILE\OneDrive\Desktop\My Xbox\default.xbe")
# K1-R10 retail import reference scan; read-only, no XDK/Xbox.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$script = Join-Path $PSScriptRoot "Audit-K1R10RetailNtReadImports.py"
$report = Join-Path $root "build\phase6_integration_map\k1_ntread44_frame_evidence_r8\k1-r10-retail-ntread-imports.json"
if(-not(Test-Path -LiteralPath $RetailXbe -PathType Leaf)){
    throw "[K1-R10] Original retail XBE missing: $RetailXbe"
}
$python = (Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "[K1-R10] Python syntax failed"}
& $python -u $script --retail-xbe $RetailXbe --output $report
if($LASTEXITCODE -ne 0){throw "[K1-R10] Retail import audit failed closed"}
Write-Host "[K1-R10] Finished. No new Xbox run or guest stack modification." -ForegroundColor Green
