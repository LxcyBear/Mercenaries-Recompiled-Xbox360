[CmdletBinding()]
param()
# K1-V7S original runtime FS/TIB ABI evidence; no XDK, no Xbox.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $phase=Join-Path $repo 'build\phase3n_final_abi_scale\runtime\gen'
    $parent=Join-Path $root 'k1_pixel_apc_iosb_v7i'
    $out=Join-Path $root 'k1_v7s_original_fs_contract'
    $tool=Join-Path $PSScriptRoot 'Probe-K1V7SOriginalFsContract.py'
    $py=(Get-Command python.exe -ErrorAction Stop).Source
    & $py -m py_compile $tool
    if ($LASTEXITCODE -ne 0) {throw '[K1-V7S] Python syntax gate failed'}
    $argsList=@(
        '-u',$tool,
        '--main',(Join-Path $parent 'main.cpp'),
        '--manifest',(Join-Path $parent 'v7i-manifest.json'),
        '--generated',$phase,
        '--shard-header',(Join-Path $root 'k1_pixel_ntread_apc_stream_v6b\translated_shards\translated_runtime.h'),
        '--out',(Join-Path $out 'v7s_fs_binding_metadata.json'),
        '--local',(Join-Path $out 'LOCAL_ONLY_original_fs_runtime_excerpts.txt')
    )
    & $py @argsList
    if ($LASTEXITCODE -ne 0) {throw '[K1-V7S] Original FS/TIB evidence gate failed closed'}
    Write-Host '[K1-V7S] SOURCE SCAN COMPLETE; no main.cpp modification, no XDK or Xbox.'
} finally {Pop-Location}
