[CmdletBinding()]
param()
# V7Y: identical NtReadFile callback guard provenance, source-only.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $v7i=Join-Path $root 'k1_pixel_apc_iosb_v7i'
    $v7x=Join-Path $root 'k1_pixel_tls_ab_recovery_v7x'
    $out=Join-Path $root 'k1_v7y_ntread_event_apc\LOCAL_ONLY_NtReadFile_CallbackSource.txt'
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    $audit=Join-Path $PSScriptRoot 'Audit-K1V7YNtReadEventApc.py'
    & $python -m py_compile $audit
    if($LASTEXITCODE -ne 0){throw '[K1-V7Y] Python compile failure'}
    $argsList=@('-u',$audit,
        '--v7i',(Join-Path $v7i 'main.cpp'),
        '--v7i-manifest',(Join-Path $v7i 'v7i-manifest.json'),
        '--v7x',(Join-Path $v7x 'main.cpp'),
        '--v7x-manifest',(Join-Path $v7x 'v7x-manifest.json'),
        '--output',$out)
    & $python @argsList
    if($LASTEXITCODE -ne 0){throw '[K1-V7Y] Evidence/source guard failure'}
    Write-Host '[K1-V7Y] No Xbox build. Share local forensic excerpt for ABI fix.'
} finally {Pop-Location}
