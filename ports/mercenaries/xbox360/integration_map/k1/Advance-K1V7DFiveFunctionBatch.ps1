[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $stageScript = Join-Path $here 'Stage-K1V7DFiveFunctionBatch.py'
    & python.exe -m py_compile $stageScript
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7D] Python preflight failed; no XDK run' }
    & python.exe $stageScript
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7D] Retail batch staging failed; no XDK run' }
    $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_retail_five_batch_v7d'
    $manifestPath = Join-Path $stage 'v7d-manifest.json'
    $src = Join-Path $stage 'main.cpp'
    if (!(Test-Path -LiteralPath $manifestPath) -or !(Test-Path -LiteralPath $src)) {
        throw '[K1-V7D] Missing batch source or manifest'
    }
    $m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($m.stage -ne 'V7D_FIVE_RETAIL_FUNCTIONS_SOURCE_ONLY_UNTESTED' -or
        $m.retail_xbe_sha256 -ne 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7' -or
        @($m.functions).Count -ne 5 -or
        @($m.true_tu_sha256.PSObject.Properties).Count -ne 64 -or
        $m.native_summary_preserved -ne $true -or
        $m.seven_async_reads_preserved_in_source -ne $true -or
        $m.unknown_frontiers_fenced -ne $true -or
        $m.hardware_verified -ne $false -or
        $m.xdk_compiled -ne $false) {
        throw '[K1-V7D] Batch invariants failed'
    }
    $expected = @('0x0022F49E','0x0022F51C','0x0022F5A7','0x0022F6A5','0x0022F7C6')
    if ((@($m.functions) -join ',') -ne ($expected -join ',')) { throw '[K1-V7D] Function set drift' }
    $count = 0
    foreach ($prop in $m.original_opcode_counts.PSObject.Properties) { $count += [int]$prop.Value }
    if ($count -ne 197) { throw "[K1-V7D] Expected 197 original opcodes; found $count" }
    $actualSha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    if ($actualSha -ne $m.source_sha256.ToUpperInvariant()) {
        throw '[K1-V7D] main.cpp hash changed after staging'
    }
    Write-Host '[K1-V7D] SOURCE/RETAIL/TRUE-TU BATCH GATE PASS: five functions, 197 x86 instructions, 64 TrueTUs'
    if ($StageOnly) {
        Write-Host '[K1-V7D] STAGE ONLY; XDK not invoked'
        return
    }
    $out = Join-Path $stage 'xdk'
    New-Item -ItemType Directory -Force -Path $out | Out-Null
    $buildArgs = @{
        GeneratedMain = $src
        GeneratedEnv = (Join-Path $repo 'build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp')
        GeneratedShardDir = (Join-Path $repo 'build\phase6_integration_map\k1_pixel_ntread_apc_stream_v6b\translated_shards')
        ExpectedBuildTag = 'P6DQ-R51-MM173-FRAME-20261029-A'
        ExpectedEnvCookie = 'phase6dq_env_build_cookie'
        Configuration = 'Release'
        Platform = 'Xbox 360'
        SkipClean = $true
        CleanLog = (Join-Path $out 'xdk-clean.log')
        BuildLog = (Join-Path $out 'xdk-build.log')
        PublishedXex = (Join-Path $out 'Merc-K1-V7D-FiveFunctionBatch.xex')
    }
    & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @buildArgs
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7D] XDK build failed' }
    if (!(Test-Path -LiteralPath $buildArgs.PublishedXex)) {
        throw '[K1-V7D] Build returned but fresh published XEX not found'
    }
    Write-Host '[K1-V7D] FIVE-FUNCTION BATCH BUILD PASS; Xbox behavior remains UNVERIFIED'
    Get-Item -LiteralPath $buildArgs.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
