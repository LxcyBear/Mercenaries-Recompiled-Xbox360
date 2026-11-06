[CmdletBinding()]
param([switch]$BuildBatch)
# V7V: source-only default, deliberate single XDK build with -BuildBatch.
# Hardware deployment is always manual. No guest memory behavior changes.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $parent=Join-Path $root 'k1_pixel_retail_tls_pair_v7u'
    $target=Join-Path $root 'k1_pixel_orange_witness_v7v'
    $source=Join-Path $target 'main.cpp'
    $manifest=Join-Path $target 'v7v-manifest.json'
    $stage=Join-Path $PSScriptRoot 'Stage-K1V7VOrangeWitness.py'
    $test=Join-Path $PSScriptRoot 'Test-K1V7VOrangeWitness.py'
    $python=(Get-Command python.exe -ErrorAction Stop).Source
    & $python -m py_compile $stage $test
    if($LASTEXITCODE -ne 0){throw '[K1-V7V] Syntax gate failed'}
    & $python -u $test
    if($LASTEXITCODE -ne 0){throw '[K1-V7V] Synthetic selftest failed'}
    $a=@('-u',$stage,'--parent',(Join-Path $parent 'main.cpp'),
         '--manifest',(Join-Path $parent 'v7u-manifest.json'),
         '--out',$source,'--out-manifest',$manifest)
    & $python @a
    if($LASTEXITCODE -ne 0){throw '[K1-V7V] Stage failed'}
    $m=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
    $hash=(Get-FileHash -LiteralPath $source -Algorithm SHA256).Hash.ToLowerInvariant()
    $parentHash=(Get-FileHash -LiteralPath (Join-Path $parent 'main.cpp') -Algorithm SHA256).Hash.ToLowerInvariant()
    $marker='K1-V7V-ORANGE-EARLY-FAULT-WITNESS-20261106'
    if($m.stage -ne 'V7V_UNIQUE_XEX_AND_TLS_ENTRY_WITNESSES_SOURCE_ONLY' -or
       $m.source_sha256 -ne $hash -or
       $m.parent_v7u_sha256 -ne $parentHash -or
       $m.runtime_fingerprint -ne $marker -or
       $m.all_guest_logic_unchanged -ne $true -or
       @($m.true_tu_sha256.PSObject.Properties).Count -ne 64) {
        throw '[K1-V7V] Source/parent/TrueTU identity failure'
    }
    Write-Host '[K1-V7V] Source witness PASS, unchanged guest behavior and 64 TrueTUs.'
    if(-not $BuildBatch) {
        Write-Host '[K1-V7V] SOURCE-ONLY PASS; -BuildBatch compiles separate diagnostic XEX.'
        return
    }
    $out=Join-Path $target 'xdk'
    New-Item -ItemType Directory -Path $out -Force | Out-Null
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
        PublishedXex=(Join-Path $out 'Merc-K1-V7V-OrangeWitness.xex')
    }
    foreach($p in @($args.GeneratedEnv,$args.GeneratedShardDir)) {
        if(!(Test-Path -LiteralPath $p)) {throw "[K1-V7V] Missing XDK build input: $p"}
    }
    Write-Host '[K1-V7V] Compiling distinct Xbox 360 Release XEX. No automatic Xbox launch.'
    & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
    if($LASTEXITCODE -ne 0 -or !(Test-Path -LiteralPath $args.PublishedXex -PathType Leaf)) {
        throw '[K1-V7V] XDK compile/publish failed'
    }
    $log=Get-Content -LiteralPath $args.BuildLog
    if(-not ($log | Select-String '========== Build: 1 succeeded')) {
        throw '[K1-V7V] Compile success absent from log'
    }
    Write-Host '[K1-V7V] XDK BUILD PASS. HARDWARE UNVERIFIED.'
    Get-Item -LiteralPath $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
    Get-FileHash -LiteralPath $args.PublishedXex -Algorithm SHA256
    Write-Host "[K1-V7V] On Xbox verify: $marker BOOT"
    Write-Host '[K1-V7V] TLS_GET_ENTER and TLS_SET_ENTER show whether those functions execute.'
} finally {Pop-Location}
