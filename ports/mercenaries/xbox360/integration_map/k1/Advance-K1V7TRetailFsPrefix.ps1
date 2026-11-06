[CmdletBinding()]
param([string]$RetailXbe='')
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    if([string]::IsNullOrWhiteSpace($RetailXbe)){
        $choices=@(
            (Join-Path $repo 'game_files\mercenaries-retail\default.xbe'),
            (Join-Path $env:USERPROFILE 'OneDrive\Desktop\My Xbox\default.xbe'),
            (Join-Path $env:USERPROFILE 'Desktop\My Xbox\default.xbe')
        )
        $hits=@($choices|Where-Object {Test-Path -LiteralPath $_ -PathType Leaf})
        if($hits.Count -eq 0){throw "[K1-V7T] Use -RetailXbe 'C:\path\to\default.xbe'"}
        $RetailXbe=$hits[0]
    }
    $root=Join-Path $repo 'build\phase6_integration_map'
    $tool=Join-Path $PSScriptRoot 'Verify-K1V7TRetailFsPrefix.py'
    $py=(Get-Command python.exe -ErrorAction Stop).Source
    & $py -m py_compile $tool
    if($LASTEXITCODE -ne 0){throw '[K1-V7T] Python syntax failed'}
    $argsList=@(
        '-u',$tool,
        '--xbe',$RetailXbe,
        '--v7i-main',(Join-Path $root 'k1_pixel_apc_iosb_v7i\main.cpp'),
        '--manifest',(Join-Path $root 'k1_pixel_apc_iosb_v7i\v7i-manifest.json'),
        '--generated',(Join-Path $repo 'build\phase3n_final_abi_scale\runtime\gen\recomp_0011.c'),
        '--out',(Join-Path $root 'k1_v7t_retail_fs_prefix\v7t_exact_fs_prefix.json')
    )
    & $py @argsList
    if($LASTEXITCODE -ne 0){throw '[K1-V7T] Retail FS evidence failed closed'}
    Write-Host '[K1-V7T] VERIFIED RETAIL FS PREFIX EVIDENCE; no XDK, no Xbox.'
} finally {Pop-Location}
