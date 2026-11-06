[CmdletBinding()]
param([string]$RetailXbe = "")
# V7M: one offline batch: exact XBE spans + CFG/ABI metadata; no XDK/Xbox.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $tag='[K1-V7M]'
    $root=Join-Path $repo 'build\phase6_integration_map'
    $analysis=Join-Path $repo 'build\phase3n_final_abi_scale'
    $tool=Join-Path $PSScriptRoot 'Audit-K1V7MFiveCfgAbi.py'
    if([string]::IsNullOrWhiteSpace($RetailXbe)){
        $options=@(
            (Join-Path $repo 'game_files\mercenaries-retail\default.xbe'),
            (Join-Path $env:USERPROFILE 'OneDrive\Desktop\My Xbox\default.xbe'),
            (Join-Path $env:USERPROFILE 'Desktop\My Xbox\default.xbe')
        )
        $found=@($options | Where-Object {Test-Path -LiteralPath $_ -PathType Leaf})
        if($found.Count -eq 0){throw "$tag Supply -RetailXbe 'C:\path\to\default.xbe'"}
        $RetailXbe=$found[0]
    }
    $out=Join-Path $root 'k1_v7m_retail_five_cfg_abi'
    $argsList=@(
        '-u',$tool,
        '--xbe',$RetailXbe,
        '--v7l',(Join-Path $root 'k1_v7l_retail_five_x86\v7l_retail_five_x86_metadata.json'),
        '--ranges',(Join-Path $analysis 'analysis\disasm\functions.json'),
        '--generated',(Join-Path $analysis 'runtime\gen'),
        '--emitter',(Join-Path $repo 'ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py'),
        '--v7i-main',(Join-Path $root 'k1_pixel_apc_iosb_v7i\main.cpp'),
        '--v7i-manifest',(Join-Path $root 'k1_pixel_apc_iosb_v7i\v7i-manifest.json'),
        '--metadata',(Join-Path $out 'v7m_abi_summary.json'),
        '--local-dossier',(Join-Path $out 'LOCAL_ONLY_original_x86_and_generated_C.txt')
    )
    $py=(Get-Command python.exe -ErrorAction Stop).Source
    & $py -m py_compile $tool
    if($LASTEXITCODE -ne 0){throw "$tag Python syntax gate failed"}
    & $py @argsList
    if($LASTEXITCODE -ne 0){throw "$tag Retail XBE batch audit failed closed"}
    Write-Host "$tag COMPLETE: source-only, no XDK, no Xbox run."
} finally {Pop-Location}
