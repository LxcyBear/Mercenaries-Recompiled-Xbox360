[CmdletBinding()]
param([string]$RetailXbe="$env:USERPROFILE\OneDrive\Desktop\My Xbox\default.xbe")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$dir=Join-Path $root "build\phase6_integration_map\k1_ntread44_frame_evidence_r8"
$r10=Join-Path $dir "k1-r10-retail-ntread-imports.json"
$out=Join-Path $dir "k1-r11-retail-ntread-slot-xrefs.json"
$py=Join-Path $PSScriptRoot "Audit-K1R11RetailNtReadSlotXrefs.py"
foreach($path in @($RetailXbe,$r10,$py)){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){throw "[K1-R11] Required input missing: $path"}
}
$python=(Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $py
if($LASTEXITCODE -ne 0){throw "[K1-R11] Python syntax check failed"}
& $python -u $py --retail-xbe $RetailXbe --r10-report $r10 --output $out
if($LASTEXITCODE -ne 0){throw "[K1-R11] Retail audit failed closed"}
