[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
Push-Location $repo
try {
    $root=Join-Path $repo "build\phase6_integration_map"
    $tool=Join-Path $PSScriptRoot "Investigate-K1V7WOriginalCaller.py"
    $py=(Get-Command python.exe -ErrorAction Stop).Source
    & $py -m py_compile $tool
    if($LASTEXITCODE -ne 0){throw "[K1-V7W] Python syntax failed"}
    & $py -u $tool `
       --main (Join-Path $root "k1_pixel_retail_tls_pair_v7u\main.cpp") `
       --shards (Join-Path $root "k1_pixel_ntread_apc_stream_v6b\translated_shards") `
       --generated (Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen") `
       --output (Join-Path $root "k1_v7w_original_caller\LOCAL_ONLY_0023A3CE_owners.txt")
    if($LASTEXITCODE -ne 0){throw "[K1-V7W] Local owner scan failed"}
} finally {Pop-Location}
