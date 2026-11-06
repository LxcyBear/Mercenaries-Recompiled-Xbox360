[CmdletBinding()]
param([switch]$BuildBatch)
# V7U source-only by default. BuildBatch intentionally compiles a fresh XEX.
# Xbox launch is manual and never triggered by this script.
$ErrorActionPreference='Stop'
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot '..\..\..\..\..'))
Push-Location $repo
try {
    $root=Join-Path $repo 'build\phase6_integration_map'
    $stage=Join-Path $root 'k1_pixel_retail_tls_pair_v7u'
    $parent=Join-Path $root 'k1_pixel_apc_iosb_v7i'
    $main=Join-Path $stage 'main.cpp'
    $manifest=Join-Path $stage 'v7u-manifest.json'
    $runner=Join-Path $PSScriptRoot 'Advance-K1V7URetailTlsPair.ps1'
    & $runner
    if($LASTEXITCODE -ne 0){throw '[K1-V7U-BUILD] Staging failed'}
    $m=Get-Content -LiteralPath $manifest -Raw | ConvertFrom-Json
    $v7i=Get-Content -LiteralPath (Join-Path $parent 'v7i-manifest.json') -Raw | ConvertFrom-Json
    $h=(Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash
    $parentHash=(Get-FileHash -LiteralPath (Join-Path $parent 'main.cpp') -Algorithm SHA256).Hash
    if($m.stage -ne 'V7U_RETAIL_X86_TLS_PAIR_IN_V7I_SOURCE_ONLY' -or
       $m.source_sha256.ToUpperInvariant() -ne $h -or
       $m.parent_v7i_sha256.ToUpperInvariant() -ne $parentHash -or
       $v7i.source_sha256.ToUpperInvariant() -ne $parentHash -or
       $m.replaced_two_exact_v7i_maintained_tls_shims -ne $true -or
       $m.original_lookup_routes_preserved -ne $true -or
       $m.apc_and_storage_fences_unchanged -ne $true -or
       $m.no_guest_abi_bypass -ne $true -or
       $m.remaining_duplicate_cases -ne 0 -or
       @($m.true_tu_sha256.PSObject.Properties).Count -ne 64 -or
       $m.xdk_compiled -ne $false -or
       $m.hardware_verified -ne $false) {
       throw '[K1-V7U-BUILD] Manifest/source/TrueTU identity mismatch'
    }
    $s=[IO.File]::ReadAllText($main)
    foreach($fragment in @(
       'K1-V7U-RETAIL-TLS-X86-PAIR-20261106',
       'void sub_0022B150(void)',
       'void sub_0022B178(void)',
       'case 0x0022B150u: return sub_0022B150;',
       'case 0x0022B178u: return sub_0022B178;'
    )){
        if(-not $s.Contains($fragment)){throw "[K1-V7U-BUILD] Missing runtime proof: $fragment"}
    }
    # A compatibility warning is intentional: existing callers may rely on
    # legacy last-error mirrors. This has not been proven equivalent.
    $oldCompatMatches=[regex]::Matches($s,'\bs_phase4cLastError\b').Count
    Write-Host '[K1-V7U-BUILD] V7U SHA / V7I parent SHA / 64 TrueTU identity PASS'
    Write-Host "[K1-V7U-BUILD] Legacy last-error variable references elsewhere in main=$oldCompatMatches"
    Write-Host '[K1-V7U-BUILD] WARNING: retail TLS storage versus legacy last-error mirrors not hardware proven.'
    if(-not $BuildBatch){
        Write-Host '[K1-V7U-BUILD] SOURCE-ONLY PASS. Use -BuildBatch to compile one XEX; no Xbox launch.'
        return
    }
    $out=Join-Path $stage 'xdk'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $buildArgs=@{
        GeneratedMain=$main
        GeneratedEnv=(Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp')
        GeneratedShardDir=(Join-Path $root 'k1_pixel_ntread_apc_stream_v6b\translated_shards')
        ExpectedBuildTag='P6DQ-R51-MM173-FRAME-20261029-A'
        ExpectedEnvCookie='phase6dq_env_build_cookie'
        Configuration='Release'
        Platform='Xbox 360'
        SkipClean=$true
        CleanLog=(Join-Path $out 'xdk-clean.log')
        BuildLog=(Join-Path $out 'xdk-build.log')
        PublishedXex=(Join-Path $out 'Merc-K1-V7U-RetailTlsBatch.xex')
    }
    foreach($candidate in @($buildArgs.GeneratedEnv,$buildArgs.GeneratedShardDir)){
        if(!(Test-Path -LiteralPath $candidate)){throw "[K1-V7U-BUILD] Missing required build input: $candidate"}
    }
    Write-Host '[K1-V7U-BUILD] Explicit Xbox 360 Release XDK compile requested; no Xbox launch.'
    & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @buildArgs
    if($LASTEXITCODE -ne 0){throw '[K1-V7U-BUILD] XDK build failed'}
    if(!(Test-Path -LiteralPath $buildArgs.PublishedXex -PathType Leaf)){
        throw '[K1-V7U-BUILD] No published fresh XEX'
    }
    Write-Host '[K1-V7U-BUILD] XDK BUILD RETURNED XEX. Guest ABI and hardware still UNVERIFIED.'
    Get-Item -LiteralPath $buildArgs.PublishedXex | Select-Object FullName,Length,LastWriteTime
}finally{Pop-Location}
