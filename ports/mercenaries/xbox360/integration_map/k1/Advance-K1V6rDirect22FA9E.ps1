[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
  # Fail early with an explicit parser gate before any source staging or XDK call.
  & python.exe -m py_compile (Join-Path $here 'Stage-K1V6rDirect22FA9E.py') (Join-Path $here 'Stage-K1V6qNativeWatson.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6r Python syntax preflight failed. No XDK invoked.' }
  Write-Host '[K1-V6r] PYTHON SYNTAX PREFLIGHT PASS'
  & python.exe (Join-Path $here 'Stage-K1V6rDirect22FA9E.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6r retail frontier or native summary proof blocked the build' }
  $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_direct_22fa9e_v6r'
  $manifest = Get-Content (Join-Path $stage 'v6r-manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.stage -ne 'V6R_RETAIL_DIRECT_0022FA9E_SOURCE_UNTESTED' -or
      $manifest.target -ne '0x0022FA9E' -or
      $manifest.hardware_ticks_before -ne 61948779 -or
      $manifest.unknown_frontiers_fenced -ne $true -or
      $manifest.apc_reads_7_preserved_in_source -ne $true -or
      $manifest.hardware_tested -ne $false -or
      @($manifest.true_tu_sha256.PSObject.Properties).Count -ne 64 -or
      @($manifest.original_generated_functions).Count -lt 1 -or
      @($manifest.original_generated_functions).Count -gt 16) {
    throw 'V6r retail 22FA9E / 64 TrueTU / APC manifest guard failed'
  }
  $src = Join-Path $stage 'main.cpp'
  if ((Get-FileHash $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
    throw 'V6r main.cpp SHA-256 mismatch'
  }
  Write-Host ('[K1-V6r] Retail 0022FA9E: '+(@($manifest.original_generated_functions) -join ', '))
  Write-Host ('[K1-V6r] Hardware baseline ticks: '+$manifest.hardware_ticks_before)
  Write-Host '[K1-V6r] End summary: old/new ticks, blocker difficulty, guest display calls'
  if ($StageOnly) { Write-Host '[K1-V6r] STAGE PASS, XDK not invoked'; return }
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
    PublishedXex = (Join-Path $out 'Merc-K1-V6r-Direct22FA9E.xex')
  }
  & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
  if ($LASTEXITCODE -ne 0) { throw 'V6r build failed' }
  if (!(Test-Path $args.PublishedXex)) { throw 'V6r XEX not published' }
  Write-Host '[K1-V6r] BUILD PASS - Xbox run still unverified'
  Get-Item $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
