[CmdletBinding()]
param()
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $python = (Get-Command python.exe -ErrorAction Stop).Source
    & $python (Join-Path $here 'Stage-K1V6hRetailVec3.py')
    if ($LASTEXITCODE -ne 0) { throw 'V6h retail SSE source audit/staging blocked. No XDK build attempted.' }
    $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_camera_vec3_v6h'
    $manifest = Get-Content -LiteralPath (Join-Path $stage 'v6h-manifest.json') -Raw | ConvertFrom-Json
    if ($manifest.stage -ne 'V6H_RETAIL_SSE_SOURCE_ONLY_HARDWARE_UNTESTED') { throw 'V6h stage marker mismatch' }
    if ($manifest.retail_function_va -ne '0x0022F51C') { throw 'Retail guest VA mismatch' }
    if ($manifest.true_tu_count -ne 64 -or $manifest.retail_ret_immediate -ne 12 -or $manifest.guest_return_stack_delta -ne 16) { throw 'Guest ABI/TrueTU evidence mismatch' }
    $src = Join-Path $stage 'main.cpp'
    $hash = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    if ($hash -ne $manifest.source_sha256.ToUpperInvariant()) { throw 'V6h staged source SHA mismatch' }
    $shards = Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards'
    $envSource = Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp'
    $builder = Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1'
    $out = Join-Path $stage 'xdk'
    $xex = Join-Path $out 'Merc-K1-V6h-RetailVec3.xex'
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
    Write-Host '[K1-V6h] XDK BUILD: SHA-pinned original retail SSE vec3 0x0022F51C' -ForegroundColor Cyan
    & $builder @buildArgs
    if ($LASTEXITCODE -ne 0) { throw 'V6h XDK compilation failed' }
    if (!(Test-Path -LiteralPath $xex)) { throw 'V6h XEX not published' }
    Write-Host '[K1-V6h] XDK BUILD PASS; HARDWARE UNTESTED' -ForegroundColor Green
    Get-Item -LiteralPath $xex | Select-Object FullName,Length,LastWriteTime | Format-List
    Get-FileHash -LiteralPath $xex -Algorithm SHA256 | Format-List
}
finally { Pop-Location }
