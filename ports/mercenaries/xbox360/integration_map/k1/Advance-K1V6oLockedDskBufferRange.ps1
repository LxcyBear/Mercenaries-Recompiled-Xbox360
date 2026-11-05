[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
  & python.exe (Join-Path $here 'Stage-K1V6oLockedDskBufferRange.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6o exact nested APC source guard blocked the build' }
  $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_locked_dsk_apc_range_v6o'
  $manifest = Get-Content (Join-Path $stage 'v6o-manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.stage -ne 'V6O_EXACT_APC_BUFFER_RANGE_SOURCE_UNTESTED' -or
      $manifest.original_true_tu_count -ne 64 -or
      $manifest.callback_delivery_unchanged -ne $true -or
      $manifest.unknown_apc_reads_fenced -ne $true) { throw 'V6o manifest guard failed' }
  $src = Join-Path $stage 'main.cpp'
  if ((Get-FileHash $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
    throw 'V6o main.cpp SHA-256 mismatch'
  }
  if ($StageOnly) { Write-Host '[K1-V6o] STAGE PASS, XDK not invoked'; return }
  $out = Join-Path $stage 'xdk'
  New-Item -ItemType Directory -Force -Path $out | Out-Null
  $args = @{
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
    PublishedXex = (Join-Path $out 'Merc-K1-V6o-LockedDskRange.xex')
  }
  & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
  if ($LASTEXITCODE -ne 0) { throw 'V6o build failed' }
  if (!(Test-Path $args.PublishedXex)) { throw 'V6o XEX not published' }
  Write-Host '[K1-V6o] BUILD PASS - Xbox run still unverified'
  Get-Item $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
