[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try{
    $root=Join-Path $repo 'build\phase6_integration_map'
    $tool=Join-Path $PSScriptRoot 'Probe-K1V7RRuntimeBindings.py'
    $parent=Join-Path $root 'k1_pixel_apc_iosb_v7i'
    $out=Join-Path $root 'k1_v7r_guest_fs_flags'
    $shards=Join-Path $root 'k1_pixel_ntread_apc_stream_v6b\translated_shards'
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    & $python -m py_compile $tool
    if($LASTEXITCODE -ne 0){throw '[K1-V7R] Python syntax check failed'}
    $argsList=@(
        '-u',$tool,
        '--main',(Join-Path $parent 'main.cpp'),
        '--manifest',(Join-Path $parent 'v7i-manifest.json'),
        '--shards',$shards,
        '--output',(Join-Path $out 'v7r_runtime_binding_metadata.json'),
        '--private-excerpts',(Join-Path $out 'LOCAL_ONLY_guest_fs_flags_interfaces.txt')
    )
    & $python @argsList
    if($LASTEXITCODE -ne 0){throw '[K1-V7R] Runtime interface probe failed closed'}
    Write-Host '[K1-V7R] COMPLETE. No Xbox/XDK build.'
} finally{Pop-Location}
