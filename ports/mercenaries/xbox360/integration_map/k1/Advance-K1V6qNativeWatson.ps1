[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
  # Fail early with an explicit parser gate before any source staging or XDK call.
  & python.exe -m py_compile (Join-Path $here 'Stage-K1V6qNativeWatson.py') (Join-Path $here 'Stage-K1V6pDirect17A120.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6q Python syntax preflight failed. No XDK invoked.' }
  Write-Host '[K1-V6q] PYTHON SYNTAX PREFLIGHT PASS'
  & python.exe (Join-Path $here 'Stage-K1V6qNativeWatson.py') --self-test
  if ($LASTEXITCODE -ne 0) { throw 'V6q native filter self-test failed' }
  & python.exe (Join-Path $here 'Stage-K1V6qNativeWatson.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6q native trace signature/source proof blocked the build' }
  $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_native_watson_v6q'
  $manifest = Get-Content (Join-Path $stage 'v6q-manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.stage -ne 'V6Q_NATIVE_WATSON_FILTER_SOURCE_UNTESTED' -or
      $manifest.native_verbose -ne $false -or
      $manifest.changed_guest_instruction_logic -ne $false -or
      $manifest.retail_17a120_preserved -ne $true -or
      $manifest.apc_seven_read_source_preserved -ne $true -or
      @($manifest.true_tu_sha256.PSObject.Properties).Count -ne 64) {
    throw 'V6q source integrity manifest guard failed'
  }
  $src = Join-Path $stage 'main.cpp'
  if ((Get-FileHash $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
    throw 'V6q main.cpp SHA-256 mismatch'
  }
  Write-Host '[K1-V6q] Native log mode: milestones / hard stops / summary (verbose opt-in in source)'
  if ($StageOnly) { Write-Host '[K1-V6q] STAGE PASS, XDK not invoked'; return }
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
    PublishedXex = (Join-Path $out 'Merc-K1-V6q-NativeWatson.xex')
  }
  & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
  if ($LASTEXITCODE -ne 0) { throw 'V6q build failed' }
  if (!(Test-Path $args.PublishedXex)) { throw 'V6q XEX not published' }
  Write-Host '[K1-V6q] BUILD PASS - Xbox run still unverified'
  Get-Item $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
