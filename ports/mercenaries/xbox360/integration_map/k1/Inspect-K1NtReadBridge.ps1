[CmdletBinding()]
param()
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$build=Join-Path $root "build\phase6_integration_map"
$main=Join-Path $build "k1_ntread44_frame_evidence_r8\main.cpp"
$shards=Join-Path $build "k1_d3d_six_cases_r3\translated_shards"
$script=Join-Path $PSScriptRoot "Inspect-K1NtReadBridge.py"
$python=(Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $script
if($LASTEXITCODE -ne 0){throw "[K1-BRIDGE] Python syntax failed"}
& $python -u $script --main $main --shards $shards
if($LASTEXITCODE -ne 0){throw "[K1-BRIDGE] Source inspection stopped"}
