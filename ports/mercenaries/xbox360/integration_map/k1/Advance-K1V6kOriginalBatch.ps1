[CmdletBinding()]
param(
    [switch]$StageOnly
)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    & $python (Join-Path $here 'Stage-K1V6kOriginalBatch.py')
    if ($LASTEXITCODE -ne 0) { throw 'V6k source/authenticity gate BLOCKED; no XDK build attempted.' }
    $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_world_source_batch_v6k'
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'v6k-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.stage -ne 'V6K_RETAIL_SOURCE_BATCH_HARDWARE_UNTESTED' -or
        $manifest.hardware_frontier -ne '0x002033E0' -or
        $manifest.true_tu_count -ne 64 -or
        $manifest.dispatch_count -lt 1 -or
        $manifest.dispatch_count -gt 192) {
        throw 'V6k guest code / hardware frontier / cap / TrueTU gate failed'
    }
    $src = Join-Path $stage 'main.cpp'
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
        throw 'V6k generated main.cpp integrity mismatch'
    }
    Write-Host "[K1-V6k] SOURCE READY: $($manifest.dispatch_count) real functions across $($manifest.generated_files_scanned) generated C files" -ForegroundColor Green
    Write-Host "[K1-V6k] OPTIONAL REJECTED: $($manifest.optional_rejected.PSObject.Properties.Count)" -ForegroundColor Yellow
    if ($StageOnly) {
        Write-Host '[K1-V6k] STAGE ONLY. No XDK build/hardware run.' -ForegroundColor Cyan
        return
    }
    $shards = Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards'
    $envSource = Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp'
    $builder = Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1'
    $out = Join-Path $stage 'xdk'
    $xex = Join-Path $out 'Merc-K1-V6k-OriginalBatch.xex'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $buildArgs = @{
        GeneratedMain = $src
        GeneratedEnv = $envSource
        GeneratedShardDir = $shards
        ExpectedBuildTag = 'P6DQ-R51-MM173-FRAME-20261029-A'
        ExpectedEnvCookie = 'phase6dq_env_build_cookie'
        Configuration = 'Release'
        Platform = 'Xbox 360'
        SkipClean = $true
        CleanLog = (Join-Path $out 'xdk-clean.log')
        BuildLog = (Join-Path $out 'xdk-build.log')
        PublishedXex = $xex
    }
    Write-Host '[K1-V6k] BUILD: Release | Xbox 360' -ForegroundColor Cyan
    & $builder @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'V6k XDK compilation failed' }
    if (!(Test-Path -LiteralPath $xex)) { throw 'V6k XEX was not published' }
    Write-Host '[K1-V6k] BUILD PASS — hardware execution remains UNTESTED' -ForegroundColor Green
    Get-Item -LiteralPath $xex | Select-Object FullName,Length,LastWriteTime | Format-List
    Get-FileHash -LiteralPath $xex -Algorithm SHA256 | Format-List
} finally { Pop-Location }
