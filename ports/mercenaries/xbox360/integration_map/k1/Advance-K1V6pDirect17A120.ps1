[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
  # Fail early with an explicit parser gate before any source staging or XDK call.
  & python.exe -m py_compile (Join-Path $here 'Stage-K1V6pDirect17A120.py') (Join-Path $here 'Audit-K1V6pRetailAssetCheckpoint.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6p Python syntax preflight failed. No XDK invoked.' }
  Write-Host '[K1-V6p] PYTHON SYNTAX PREFLIGHT PASS'
  & python.exe (Join-Path $here 'Stage-K1V6pDirect17A120.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6p retail source or dependency proof blocked the build' }
  $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_direct_17a120_v6p'
  $manifest = Get-Content (Join-Path $stage 'v6p-manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.stage -ne 'V6P_RETAIL_DIRECT_0017A120_SOURCE_UNTESTED' -or
      $manifest.original_true_tu_count -ne 64 -or
      $manifest.callback_delivery_unchanged -ne $true -or
      $manifest.unknown_apc_reads_fenced -ne $true) { throw 'V6p manifest guard failed' }
  $src = Join-Path $stage 'main.cpp'
  if ((Get-FileHash $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
    throw 'V6p main.cpp SHA-256 mismatch'
  }
  if ($manifest.target -ne '0x0017A120' -or @($manifest.original_generated_functions).Count -lt 1 -or @($manifest.original_generated_functions).Count -gt 16) { throw 'V6p original source closure guard failed' }\n  Write-Host ('[K1-V6p] Expected XEX fingerprint: '+$manifest.runtime_fingerprint)\n  if ($StageOnly) { Write-Host '[K1-V6p] STAGE PASS, XDK not invoked'; return }
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
    PublishedXex = (Join-Path $out 'Merc-K1-V6p-Direct17A120.xex')
  }
  & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
  if ($LASTEXITCODE -ne 0) { throw 'V6p build failed' }
  if (!(Test-Path $args.PublishedXex)) { throw 'V6p XEX not published' }
  Write-Host '[K1-V6p] BUILD PASS - Xbox run still unverified'
  Get-Item $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
