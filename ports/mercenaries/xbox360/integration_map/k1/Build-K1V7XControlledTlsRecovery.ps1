[CmdletBinding()]
param([switch]$BuildBatch)
# V7X source-only default. A/B recovery of known V7I last-error handlers.
# The retail TLS replacement remains unresolved; never call this a final fix.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $v7i=Join-Path $root 'k1_pixel_apc_iosb_v7i'
    $v7u=Join-Path $root 'k1_pixel_retail_tls_pair_v7u'
    $target=Join-Path $root 'k1_pixel_tls_ab_recovery_v7x'
    $source=Join-Path $target 'main.cpp'
    $manifest=Join-Path $target 'v7x-manifest.json'
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    $stage=Join-Path $PSScriptRoot 'Stage-K1V7XControlledTlsRecovery.py'
    $test=Join-Path $PSScriptRoot 'Test-K1V7XControlledTlsRecovery.py'
    $v7uModule=Join-Path $PSScriptRoot 'Stage-K1V7URetailTlsPair.py'
    & $python -m py_compile $stage $test $v7uModule
    if($LASTEXITCODE -ne 0){throw '[K1-V7X] Python syntax failure'}
    & $python -u $test
    if($LASTEXITCODE -ne 0){throw '[K1-V7X] Synthetic source selftest failed'}
    $stageArgs=@('-u',$stage,
        '--v7i',(Join-Path $v7i 'main.cpp'),
        '--v7i-manifest',(Join-Path $v7i 'v7i-manifest.json'),
        '--v7u',(Join-Path $v7u 'main.cpp'),
        '--v7u-manifest',(Join-Path $v7u 'v7u-manifest.json'),
        '--module',$v7uModule,
        '--out',$source,
        '--out-manifest',$manifest)
    & $python @stageArgs
    if($LASTEXITCODE -ne 0){throw '[K1-V7X] Staging/provenance failure'}
    $m=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $sha=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $viSha=(Get-FileHash -LiteralPath (Join-Path $v7i 'main.cpp') -Algorithm SHA256).Hash.ToLowerInvariant()
    $vuSha=(Get-FileHash -LiteralPath (Join-Path $v7u 'main.cpp') -Algorithm SHA256).Hash.ToLowerInvariant()
    if($m.stage -ne 'V7X_CONTROLLED_REVERT_V7U_TLS_TO_V7I_AB_SOURCE_ONLY' -or
       $m.source_sha256 -ne $sha -or $m.parent_v7i_sha256 -ne $viSha -or
       $m.parent_v7u_sha256 -ne $vuSha -or
       $m.retail_tls_replacement_active -ne $false -or
       $m.maintained_v7i_last_error_handlers_active -ne $true -or
       $m.apc_and_storage_fences_unchanged -ne $true -or
       @($m.true_tu_sha256.PSObject.Properties).Count -ne 64) {
        throw '[K1-V7X] A/B manifest or TrueTU integrity mismatch'
    }
    Write-Host '[K1-V7X] SOURCE PASS: exact V7I behavior + unique V7X boot marker.'
    Write-Host '[K1-V7X] Original 64 TrueTUs and all APC/GPU/storage fences untouched.'
    if(-not $BuildBatch) {
        Write-Host '[K1-V7X] NO XDK. Add -BuildBatch for deliberate single Release XEX compile.'
        return
    }
    $out=Join-Path $target 'xdk'
    New-Item -ItemType Directory -Path $out -Force | Out-Null
    $buildArgs=@{
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
        PublishedXex=(Join-Path $out 'Merc-K1-V7X-TlsABRecovery.xex')
    }
    foreach($p in @($buildArgs.GeneratedEnv,$buildArgs.GeneratedShardDir)){
        if(!(Test-Path -LiteralPath $p)){throw "[K1-V7X] Missing build input: $p"}
    }
    $start=Get-Date
    Write-Host '[K1-V7X] Deliberate Xbox 360 Release build. No automatic Xbox deployment.'
    & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @buildArgs
    if($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $buildArgs.PublishedXex -PathType Leaf)){
        throw '[K1-V7X] XDK compile or publish failed'
    }
    $log=Get-Content -LiteralPath $buildArgs.BuildLog
    if(-not ($log | Select-String '========== Build: 1 succeeded')){
        throw '[K1-V7X] No fresh successful build recorded'
    }
    $outFile=Get-Item -LiteralPath $buildArgs.PublishedXex
    if($outFile.Length -lt 1000000 -or $outFile.LastWriteTime -lt $start.AddSeconds(-2)){
        throw '[K1-V7X] Published XEX does not look fresh'
    }
    Write-Host '[K1-V7X] XDK PASS. HARDWARE NOT YET TESTED.'
    Write-Host "[K1-V7X] XEX: $($outFile.FullName)"
    Write-Host "[K1-V7X] SHA256: $((Get-FileHash -LiteralPath $outFile.FullName -Algorithm SHA256).Hash)"
    Write-Host '[K1-V7X] On Xbox find: K1-V7X-TLS-AB-RECOVERY-20261106 BOOT'
    Write-Host '[K1-V7X] Compare first fault tick and stream reads against confirmed V7V.'
} finally {Pop-Location}
