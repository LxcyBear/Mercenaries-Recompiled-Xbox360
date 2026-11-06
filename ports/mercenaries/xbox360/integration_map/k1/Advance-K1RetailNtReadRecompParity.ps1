[CmdletBinding()]
param([string]$RetailXbe="$env:USERPROFILE\OneDrive\Desktop\My Xbox\default.xbe")
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
$py=(Get-Command python.exe -ErrorAction Stop).Source
$script=Join-Path $PSScriptRoot 'Audit-K1RetailNtReadRecompParity.py'
$dep=Join-Path $PSScriptRoot 'Audit-K1R11RetailNtReadSlotXrefs.py'
$r11=Join-Path $repo 'build\phase6_integration_map\k1_ntread44_frame_evidence_r8\k1-r11-retail-ntread-slot-xrefs.json'
$v7z=Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_reject_tuple_v7z\main.cpp'
$shards=Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards'
$out=Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_reject_tuple_v7z\k1-retail-ntread-recomp-candidates.json'
foreach($f in @($RetailXbe,$script,$dep,$r11,$v7z)){
    if(!(Test-Path -LiteralPath $f -PathType Leaf)){throw "[K1-RECOMP] Missing input: $f"}
}
if(!(Test-Path -LiteralPath $shards -PathType Container)){throw "[K1-RECOMP] Missing TrueTU folder: $shards"}
& $py -m py_compile $script $dep
if($LASTEXITCODE -ne 0){throw '[K1-RECOMP] Python syntax gate failed'}
& $py -u $script --retail-xbe $RetailXbe --r11-report $r11 --main-cpp $v7z --shards $shards --output $out
if($LASTEXITCODE -ne 0){throw '[K1-RECOMP] Original retail x86/recomp parity audit failed'}
Write-Host '[K1-RECOMP] Retail x86 -> translated C comparison PASS; no XDK or Xbox run.'
