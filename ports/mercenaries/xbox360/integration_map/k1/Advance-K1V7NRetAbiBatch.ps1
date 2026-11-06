[CmdletBinding()]
param([string]$RetailXbe = "")
# Source-only retail ABI/indirect call batch. Does not build/run.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $tag='[K1-V7N]'
    $analysis=Join-Path $repo 'build\phase3n_final_abi_scale'
    $root=Join-Path $repo 'build\phase6_integration_map'
    $script=Join-Path $PSScriptRoot 'Audit-K1V7NRetAbiBatch.py'
    if([string]::IsNullOrWhiteSpace($RetailXbe)){
        $choices=@(
            (Join-Path $repo 'game_files\mercenaries-retail\default.xbe'),
            (Join-Path $env:USERPROFILE 'OneDrive\Desktop\My Xbox\default.xbe'),
            (Join-Path $env:USERPROFILE 'Desktop\My Xbox\default.xbe')
        )
        $hits=@($choices | Where-Object {Test-Path -LiteralPath $_ -PathType Leaf})
        if($hits.Count -eq 0){throw "$tag Supply -RetailXbe 'C:\path\to\default.xbe'."}
        $RetailXbe=$hits[0]
    }
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    & $python -m py_compile $script
    if($LASTEXITCODE -ne 0){throw "$tag Python syntax failed"}
    $argsList=@(
        '-u',$script,
        '--xbe',$RetailXbe,
        '--v7m',(Join-Path $root 'k1_v7m_retail_five_cfg_abi\v7m_abi_summary.json'),
        '--v7l',(Join-Path $root 'k1_v7l_retail_five_x86\v7l_retail_five_x86_metadata.json'),
        '--ranges',(Join-Path $analysis 'analysis\disasm\functions.json'),
        '--emitter',(Join-Path $repo 'ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py'),
        '--v7i-main',(Join-Path $root 'k1_pixel_apc_iosb_v7i\main.cpp'),
        '--v7i-manifest',(Join-Path $root 'k1_pixel_apc_iosb_v7i\v7i-manifest.json'),
        '--out',(Join-Path $root 'k1_v7n_ret_abi_batch\v7n_ret_abi_batch.json')
    )
    & $python @argsList
    if($LASTEXITCODE -ne 0){throw "$tag Batch review failed closed; no XDK"}
    Write-Host "$tag FINISHED: source evidence only, XDK and Xbox untouched."
} finally {Pop-Location}
