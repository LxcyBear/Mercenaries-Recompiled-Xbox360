[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    & $python (Join-Path $here 'Stage-K1V6iOriginalBatch.py')
    if ($LASTEXITCODE -ne 0) { throw 'V6i original source batch staging BLOCKED. No XDK build attempted.' }
    $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_camera_batch_v6i'
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'v6i-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.stage -ne 'V6I_ORIGINAL_SOURCE_ONLY_HARDWARE_UNTESTED' -or
        $manifest.hardware_seed -ne '0x001FA000' -or
        $manifest.true_tu_count -ne 64 -or
        $manifest.dispatch_count -lt 1) { throw 'V6i source/TrueTU/frontier manifest mismatch' }
    $src = Join-Path $stage 'main.cpp'
    if ((Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
        throw 'V6i main.cpp SHA mismatch'
    }
    $shards = Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards'
    $envSource = Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp'
    $builder = Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1'
    $out = Join-Path $stage 'xdk'
    $xex = Join-Path $out 'Merc-K1-V6i-OriginalBatch.xex'
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
    Write-Host ('[K1-V6i] XDK BUILD original source functions=' + $manifest.dispatch_count) -ForegroundColor Cyan
    & $builder @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'V6i XDK compilation failed' }
    if (!(Test-Path -LiteralPath $xex)) { throw 'V6i XEX not published' }
    Write-Host '[K1-V6i] XDK BUILD PASS; HARDWARE UNTESTED' -ForegroundColor Green
    Get-Item -LiteralPath $xex | Select-Object FullName,Length,LastWriteTime | Format-List
    Get-FileHash -LiteralPath $xex -Algorithm SHA256 | Format-List
} finally { Pop-Location }
