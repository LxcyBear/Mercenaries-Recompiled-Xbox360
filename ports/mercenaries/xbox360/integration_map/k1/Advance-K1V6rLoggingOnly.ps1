[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
  # Fail early with an explicit parser gate before any source staging or XDK call.
  & python.exe -m py_compile (Join-Path $here 'Stage-K1V6rLoggingOnly.py') (Join-Path $here 'Stage-K1V6qNativeWatson.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6rLOG Python syntax preflight failed. No XDK invoked.' }
  Write-Host '[K1-V6rLOG] PYTHON SYNTAX PREFLIGHT PASS'
  & python.exe (Join-Path $here 'Stage-K1V6rLoggingOnly.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6rLOG retail frontier or native summary proof blocked the build' }
  $stage = Join-Path $repo 'build\phase6_integration_map\k1_native_end_summary_v6rlog'
  $manifest = Get-Content (Join-Path $stage 'v6rlog-manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.stage -ne 'V6R_LOGGING_ONLY_SOURCE_UNTESTED' -or
      $manifest.hardware_ticks_before -ne 61948779 -or
      $manifest.unknown_frontiers_fenced -ne $true -or
      $manifest.apc_reads_7_preserved_in_source -ne $true -or
      $manifest.guest_display_summary -ne $true -or
      $manifest.frontier_c_translation_available -ne $false -or
      $manifest.hardware_tested -ne $false -or
      @($manifest.true_tu_sha256.PSObject.Properties).Count -ne 64) {
    throw 'V6rLOG source-retail/APC/64 TrueTU guard failed'
  }
  $src = Join-Path $stage 'main.cpp'
  if ((Get-FileHash $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
    throw 'V6rLOG main.cpp SHA-256 mismatch'
  }
  Write-Host '[K1-V6rLOG] Native log end summary: old/new ticks, difficulty heuristic, guest displays'
  Write-Host '[K1-V6rLOG] 0022FA9E retail translation still missing; guest frontier unchanged'
  if ($StageOnly) { Write-Host '[K1-V6rLOG] STAGE PASS, XDK not invoked'; return }
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
    PublishedXex = (Join-Path $out 'Merc-K1-V6rLOG-EndSummary.xex')
  }
  & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
  if ($LASTEXITCODE -ne 0) { throw 'V6rLOG build failed' }
  if (!(Test-Path $args.PublishedXex)) { throw 'V6rLOG XEX not published' }
  Write-Host '[K1-V6rLOG] BUILD PASS - Xbox run still unverified'
  Get-Item $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
