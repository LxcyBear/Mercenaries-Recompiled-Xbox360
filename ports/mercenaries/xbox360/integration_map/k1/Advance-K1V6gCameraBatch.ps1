[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    & $python (Join-Path $here 'Stage-K1V6gCameraBatch.py')
    if ($LASTEXITCODE -ne 0) { throw 'V6g source staging BLOCKED. No XDK build attempted.' }
    $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_camera_batch_v6g_sinebridge'
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'v6g-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.stage -ne 'V6G_SOURCE_ONLY_NOT_BUILT_OR_HARDWARE_TESTED') { throw 'Stage marker mismatch' }
    if ($manifest.hardware_frontier -ne '0x001F8B30') { throw 'Frontier mismatch' }
    if ($manifest.true_tu_count -ne 64 -or $manifest.dispatch_count -lt 1) { throw 'TrueTU/dispatch mismatch' }
    $hash = (Get-FileHash -LiteralPath (Join-Path $stage 'main.cpp') -Algorithm SHA256).Hash
    if ($hash -ne $manifest.source_sha256.ToUpperInvariant()) { throw 'V6g staged source SHA256 mismatch' }
    $shards = Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards'
    $envSource = Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp'
    $builder = Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1'
    $out = Join-Path $stage 'xdk'
    $xex = Join-Path $out 'Merc-K1-V6g-SineBridge.xex'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $args = @{
        GeneratedMain = (Join-Path $stage 'main.cpp')
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
    Write-Host ('[K1-V6g] XDK BUILD: original camera function count=' + $manifest.dispatch_count) -ForegroundColor Cyan
    & $builder @args
    if ($LASTEXITCODE -ne 0) { throw 'V6g XDK compilation failed' }
    if (!(Test-Path -LiteralPath $xex)) { throw 'V6g XEX not published' }
    Write-Host '[K1-V6g] XDK BUILD PASS; HARDWARE UNTESTED' -ForegroundColor Green
    Get-Item -LiteralPath $xex | Select-Object FullName,Length,LastWriteTime | Format-List
    Get-FileHash -LiteralPath $xex -Algorithm SHA256 | Format-List
}
finally { Pop-Location }
