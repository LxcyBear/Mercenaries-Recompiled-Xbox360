[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$main=Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$runtime=Join-Path $repo "build\phase6_integration_map\k1s_halgetvector44_saved_esi\translated_shards\translated_runtime.h"
$folder=Join-Path $repo "build\phase6_integration_map\pixel_batch"
$plan=Join-Path $folder "pixel_batch_closure.json"
$report=Join-Path $folder "pixel_apu_contracts.txt"
$probe=Join-Path $PSScriptRoot "Probe-PixelApuContracts.py"
$test=Join-Path $PSScriptRoot "Test-PixelApuContracts.py"
foreach($path in @($main,$runtime,$plan,$probe,$test)){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[PIXEL-BRIDGE] Required K1S source or prior planner JSON missing: $path"
    }
}
if(-not(Test-Path -LiteralPath $generated -PathType Container)){
    throw "[PIXEL-BRIDGE] Generated C corpus missing: $generated"
}
$py=(Get-Command python -ErrorAction Stop).Source
Write-Host "[PIXEL-BRIDGE] Synthetic source/ABI report checks (NO XDK)"
& $py -u $test
if($LASTEXITCODE -ne 0) {throw "[PIXEL-BRIDGE] Source-contract tests FAILED"}
Write-Host "[PIXEL-BRIDGE] Inspect exact original A3A5A and APU helper routes (NO XDK)"
& $py -u $probe --plan $plan --generated-root $generated --main $main --runtime $runtime --out $report
if($LASTEXITCODE -ne 0) {throw "[PIXEL-BRIDGE] Original source proof FAILED"}
if(-not(Test-Path -LiteralPath $report -PathType Leaf)){
    throw "[PIXEL-BRIDGE] Expected output is missing"
}
Write-Host "[PIXEL-BRIDGE] PASS. Send this report for the next bundled TrueTU build:"
Write-Host "    $report"
Write-Host "[PIXEL-BRIDGE] First findings:"
Get-Content -LiteralPath $report -TotalCount 14
Write-Host "[PIXEL-BRIDGE] NO Xbox build and no source changes"
