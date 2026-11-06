[CmdletBinding()]
param()
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $prefix='[K1-V7K]'
    $py=Join-Path $PSScriptRoot 'Audit-K1V7KFiveCandidates.py'
    $analysis=Join-Path $repo 'build\phase3n_final_abi_scale'
    $base=Join-Path $repo 'build\phase6_integration_map'
    $argsList=@(
        '-u',$py,
        '--report',(Join-Path $base 'k1_v7j_source_batch\v7j_batch_frontiers.json'),
        '--ranges',(Join-Path $analysis 'analysis\disasm\functions.json'),
        '--generated',(Join-Path $analysis 'runtime\gen'),
        '--emitter',(Join-Path $repo 'ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py'),
        '--current-main',(Join-Path $base 'k1_pixel_apc_iosb_v7i\main.cpp'),
        '--current-manifest',(Join-Path $base 'k1_pixel_apc_iosb_v7i\v7i-manifest.json'),
        '--output',(Join-Path $base 'k1_v7k_five_candidates\v7k_candidate_metadata.json')
    )
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    & $python -m py_compile $py
    if($LASTEXITCODE -ne 0){throw "$prefix Python source syntax failed"}
    & $python @argsList
    if($LASTEXITCODE -ne 0){throw "$prefix Verified original-source audit failed"}
    Write-Host "$prefix COMPLETE: no XDK, no XEX, no Xbox run."
} finally {Pop-Location}
