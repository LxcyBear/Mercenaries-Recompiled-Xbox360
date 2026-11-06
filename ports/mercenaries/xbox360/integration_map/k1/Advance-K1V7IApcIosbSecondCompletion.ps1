[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
    $stageScript = Join-Path $here 'Stage-K1V7IApcIosbSecondCompletion.py'
    & python.exe -m py_compile $stageScript
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7I] Python preflight failed; no XDK run' }
    & python.exe $stageScript
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7I] Retail batch staging failed; no XDK run' }
    $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_apc_iosb_v7i'
    $manifestPath = Join-Path $stage 'v7i-manifest.json'
    $src = Join-Path $stage 'main.cpp'
    if (!(Test-Path -LiteralPath $manifestPath) -or !(Test-Path -LiteralPath $src)) {
        throw '[K1-V7I] Missing batch source or manifest'
    }
    $m = Get-Content -LiteralPath $manifestPath -Raw | ConvertFrom-Json
    if ($m.stage -ne 'V7I_HARDWARE_OBSERVED_APC_IOSB_ALLOWLIST_SOURCE_ONLY' -or
        (@($m.apc_iosb_allowlist) -join ',') -ne '0x00424DA8,0x00424D58' -or
        $m.last_hardware_observed_read.iosb -ne '0x00424D58' -or
        $m.last_hardware_observed_read.bytes -ne 57344 -or
        $m.apc_pending_wait_guard_preserved -ne $true -or
        $m.completion_status_check_preserved -ne $true -or
        $m.completion_byte_count_check_preserved -ne $true -or
        $m.stack_range_check_preserved -ne $true -or
        $m.no_new_apc_synthesis -ne $true -or
        $m.no_guest_abi_bypass -ne $true -or
        $m.parent_v7e_sha256 -ne '54c8901b0024d3fa2da393944df9ffed337ff70950343af0b97a188088844042' -or
        $m.previous_duplicate_va -ne '0x0022F51C' -or
        $m.previous_duplicate_cases -ne 2 -or
        $m.remaining_duplicate_cases -ne 0 -or
        $m.selected_22f51c_route -ne 'sub_0022F51C' -or
        $m.retained_legacy_v6h_function_body -ne $true -or
        $m.original_197_opcodes_preserved -ne $true -or
        $m.retail_xbe_sha256 -ne 'AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7' -or
        @($m.functions).Count -ne 5 -or
        @($m.true_tu_sha256.PSObject.Properties).Count -ne 64 -or
        $m.native_summary_preserved -ne $true -or
        $m.seven_async_reads_preserved_in_source -ne $true -or
        $m.unknown_frontiers_fenced -ne $true -or
        $m.hardware_verified -ne $false -or
        $m.xdk_compiled -ne $false) {
        throw '[K1-V7I] Batch invariants failed'
    }
    $expected = @('0x0022F49E','0x0022F51C','0x0022F5A7','0x0022F6A5','0x0022F7C6')
    if ((@($m.functions) -join ',') -ne ($expected -join ',')) { throw '[K1-V7I] Function set drift' }
    $count = 0
    foreach ($prop in $m.original_opcode_counts.PSObject.Properties) { $count += [int]$prop.Value }
    if ($count -ne 197) { throw "[K1-V7I] Expected 197 original opcodes; found $count" }
    $actualSha = (Get-FileHash -LiteralPath $src -Algorithm SHA256).Hash
    if ($actualSha -ne $m.source_sha256.ToUpperInvariant()) {
        throw '[K1-V7I] main.cpp hash changed after staging'
    }
    Write-Host '[K1-V7I] SOURCE/RETAIL/TRUE-TU BATCH GATE PASS: five functions, 197 x86 instructions, 64 TrueTUs'
    if ($StageOnly) {
        Write-Host '[K1-V7I] STAGE ONLY; XDK not invoked'
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
        PublishedXex = (Join-Path $out 'Merc-K1-V7I-ApcIosbBatch.xex')
    }
    & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @buildArgs
    if ($LASTEXITCODE -ne 0) { throw '[K1-V7I] XDK build failed' }
    if (!(Test-Path -LiteralPath $buildArgs.PublishedXex)) {
        throw '[K1-V7I] Build returned but fresh published XEX not found'
    }
    Write-Host '[K1-V7I] APC IOSB + FIVE-FUNCTION BATCH BUILD PASS; Xbox behavior remains UNVERIFIED; do not launch until GPU safety review'
    Get-Item -LiteralPath $buildArgs.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
