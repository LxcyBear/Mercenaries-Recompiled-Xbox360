[CmdletBinding()]
param()
# Source-only staging of two exact original retail TLS functions into a copy
# of the V7I main. Never invokes the XDK or Xbox.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $parent=Join-Path $root 'k1_pixel_apc_iosb_v7i'
    $out=Join-Path $root 'k1_pixel_retail_tls_pair_v7u'
    $script=Join-Path $PSScriptRoot 'Stage-K1V7URetailTlsPair.py'
    $py=(Get-Command python.exe -ErrorAction Stop).Source
    & $py -m py_compile $script
    if($LASTEXITCODE -ne 0){throw '[K1-V7U] Python syntax gate failed'}
    & $py -u (Join-Path $PSScriptRoot 'Test-K1V7URetailTlsPair.py')
    if($LASTEXITCODE -ne 0){throw '[K1-V7U] Synthetic integration regression failed'}
    $argsList=@(
        '-u',$script,
        '--parent',(Join-Path $parent 'main.cpp'),
        '--manifest',(Join-Path $parent 'v7i-manifest.json'),
        '--abi',(Join-Path $root 'k1_v7n_ret_abi_batch\v7n_ret_abi_batch.json'),
        '--phase2e',(Join-Path $repo 'ports\mercenaries\xbox360\phase2e_execution_env_xex\main.cpp'),
        '--out',(Join-Path $out 'main.cpp'),
        '--out-manifest',(Join-Path $out 'v7u-manifest.json')
    )
    & $py @argsList
    if($LASTEXITCODE -ne 0){throw '[K1-V7U] Hard fence: original source or ABI diverged'}
    Write-Host '[K1-V7U] PASS: exact retail TLS pair staged, no XDK or Xbox invoked.'
} finally {Pop-Location}
