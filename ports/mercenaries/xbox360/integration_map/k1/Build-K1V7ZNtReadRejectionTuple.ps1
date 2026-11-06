[CmdletBinding()]
param([switch]$BuildBatch)
# V7Z source-only default; -BuildBatch explicitly compiles one isolated XEX.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $parent=Join-Path $root 'k1_pixel_tls_ab_recovery_v7x'
    $target=Join-Path $root 'k1_pixel_ntread_reject_tuple_v7z'
    $source=Join-Path $target 'main.cpp'
    $meta=Join-Path $target 'v7z-manifest.json'
    $py=(Get-Command python.exe -ErrorAction Stop).Source
    $stage=Join-Path $PSScriptRoot 'Stage-K1V7ZNtReadRejectionTuple.py'
    $test=Join-Path $PSScriptRoot 'Test-K1V7ZNtReadRejectionTuple.py'
    & $py -m py_compile $stage $test
    if($LASTEXITCODE -ne 0){throw '[K1-V7Z] Python syntax failed'}
    & $py -u $test
    if($LASTEXITCODE -ne 0){throw '[K1-V7Z] Synthetic validation failed'}
    $stageArgs=@('-u',$stage,
        '--parent',(Join-Path $parent 'main.cpp'),
        '--manifest',(Join-Path $parent 'v7x-manifest.json'),
        '--out',$source,
        '--out-manifest',$meta)
    & $py @stageArgs
    if($LASTEXITCODE -ne 0){throw '[K1-V7Z] Source staging failed'}
    $m=Get-Content -LiteralPath $meta -Raw -Encoding UTF8 | ConvertFrom-Json
    $h=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $ph=(Get-FileHash -LiteralPath (Join-Path $parent 'main.cpp') -Algorithm SHA256).Hash.ToLowerInvariant()
    if($m.stage -ne 'V7Z_NTREAD_APC_REJECTION_TUPLE_EVIDENCE_SOURCE_ONLY' -or
       $m.source_sha256 -ne $h -or $m.parent_v7x_sha256 -ne $ph -or
       $m.runtime_fingerprint -ne 'K1-V7Z-NTREAD-REJECT-TUPLE-20261106' -or
       $m.no_new_apc_forms_admitted -ne $true -or
       $m.ntread_frame_guard_unchanged -ne $true -or
       $m.ntread_storage_io_hard_fence_unchanged -ne $true -or
       @($m.true_tu_sha256.PSObject.Properties).Count -ne 64){
        throw '[K1-V7Z] Source/ABI/64 TrueTU guard failed'
    }
    Write-Host '[K1-V7Z] SOURCE PASS: one-shot rejected request tuple, no ABI changes.'
    if(-not $BuildBatch){
        Write-Host '[K1-V7Z] SOURCE-ONLY. Use -BuildBatch for explicit Xbox 360 Release XEX.'
        return
    }
    $out=Join-Path $target 'xdk'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $args=@{
        GeneratedMain=$source
        GeneratedEnv=(Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp')
        GeneratedShardDir=(Join-Path $root 'k1_pixel_ntread_apc_stream_v6b\translated_shards')
        ExpectedBuildTag='P6DQ-R51-MM173-FRAME-20261029-A'
        ExpectedEnvCookie='phase6dq_env_build_cookie'
        Configuration='Release'
        Platform='Xbox 360'
        SkipClean=$true
        CleanLog=(Join-Path $out 'xdk-clean.log')
        BuildLog=(Join-Path $out 'xdk-build.log')
        PublishedXex=(Join-Path $out 'Merc-K1-V7Z-NtReadRejectTuple.xex')
    }
    foreach($p in @($args.GeneratedEnv,$args.GeneratedShardDir)){
        if(!(Test-Path -LiteralPath $p)){throw "[K1-V7Z] Missing XDK build input: $p"}
    }
    $start=Get-Date
    Write-Host '[K1-V7Z] Explicit XDK compile; Xbox deployment stays manual.'
    & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
    if($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $args.PublishedXex -PathType Leaf)){
        throw '[K1-V7Z] XDK build/publish failed'
    }
    $log=Get-Content -LiteralPath $args.BuildLog
    if(-not ($log | Select-String '========== Build: 1 succeeded')){
        throw '[K1-V7Z] Successful XDK compile not proven'
    }
    $xex=Get-Item -LiteralPath $args.PublishedXex
    if($xex.Length -lt 1000000 -or $xex.LastWriteTime -lt $start.AddSeconds(-2)){
        throw '[K1-V7Z] Fresh XEX publish not proven'
    }
    Write-Host '[K1-V7Z] XDK BUILD PASS, HARDWARE UNVERIFIED.'
    Get-Item -LiteralPath $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
    Get-FileHash -LiteralPath $args.PublishedXex -Algorithm SHA256
    Write-Host '[K1-V7Z] Watch for: K1-V7Z-NTREAD-REJECT-TUPLE-20261106 BOOT'
    Write-Host '[K1-V7Z] Watch for: K1-V7Z NTREAD REJECT: ...'
} finally {Pop-Location}
