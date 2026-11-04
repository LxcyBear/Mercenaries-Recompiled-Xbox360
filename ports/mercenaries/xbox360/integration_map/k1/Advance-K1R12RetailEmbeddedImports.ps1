[CmdletBinding()]
param([string]$RetailXbe="$env:USERPROFILE\OneDrive\Desktop\My Xbox\default.xbe")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$dir=Join-Path $root "build\phase6_integration_map\k1_ntread44_frame_evidence_r8"
$src=Join-Path $PSScriptRoot "Audit-K1R12RetailEmbeddedImports.py"
$r11=Join-Path $dir "k1-r11-retail-ntread-slot-xrefs.json"
$out=Join-Path $dir "k1-r12-retail-embedded-imports.json"
foreach($file in @($RetailXbe,$src,$r11)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "[K1-R12] Missing verified input: $file"}
}
$python=(Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $src
if($LASTEXITCODE -ne 0){throw "[K1-R12] Syntax gate failed"}
& $python -u $src --retail-xbe $RetailXbe --r11-report $r11 --output $out
if($LASTEXITCODE -ne 0){throw "[K1-R12] Embedded operand audit failed closed"}
