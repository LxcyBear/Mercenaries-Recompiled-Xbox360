[CmdletBinding()]
param([string]$RetailXbe = "")
# Exact retail XBE five-candidate x86 analysis, never builds or runs Xbox.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $tag='[K1-V7L]'
    $root=Join-Path $repo 'build\phase6_integration_map'
    $analysis=Join-Path $repo 'build\phase3n_final_abi_scale'
    $script=Join-Path $PSScriptRoot 'Audit-K1V7LRetailFiveX86.py'
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    & $python -m py_compile $script
    if($LASTEXITCODE -ne 0){throw "$tag Python syntax gate failed"}
    if([string]::IsNullOrWhiteSpace($RetailXbe)){
        $choices=@(
            (Join-Path $repo 'game_files\mercenaries-retail\default.xbe'),
            (Join-Path $env:USERPROFILE 'OneDrive\Desktop\My Xbox\default.xbe'),
            (Join-Path $env:USERPROFILE 'Desktop\My Xbox\default.xbe')
        )
        $exists=@($choices | Where-Object {Test-Path -LiteralPath $_ -PathType Leaf})
        if($exists.Count -eq 0){
            throw "$tag Retail XBE not in known user-local paths. Rerun with -RetailXbe 'C:\path\to\default.xbe'."
        }
        # Let Python perform the non-negotiable retail SHA check.
        $RetailXbe=$exists[0]
    }
    $argsList=@(
        '-u',$script,
        '--xbe',$RetailXbe,
        '--v7k',(Join-Path $root 'k1_v7k_five_candidates\v7k_candidate_metadata.json'),
        '--ranges',(Join-Path $analysis 'analysis\disasm\functions.json'),
        '--generated',(Join-Path $analysis 'runtime\gen'),
        '--emitter',(Join-Path $repo 'ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py'),
        '--v7i-main',(Join-Path $root 'k1_pixel_apc_iosb_v7i\main.cpp'),
        '--v7i-manifest',(Join-Path $root 'k1_pixel_apc_iosb_v7i\v7i-manifest.json'),
        '--out',(Join-Path $root 'k1_v7l_retail_five_x86\v7l_retail_five_x86_metadata.json')
    )
    Write-Host "$tag Running 5 original XBE x86 witnesses; no build."
    & $python @argsList
    if($LASTEXITCODE -ne 0){throw "$tag Analysis blocked on source or original byte provenance"}
    Write-Host "$tag VERIFIED SOURCE-ONLY REPORT; XDK and Xbox untouched."
} finally {Pop-Location}
