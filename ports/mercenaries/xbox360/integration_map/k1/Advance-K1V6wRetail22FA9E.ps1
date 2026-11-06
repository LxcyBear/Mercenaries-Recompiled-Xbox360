[CmdletBinding()]
param([switch]$StageOnly)
$ErrorActionPreference = 'Stop'
$here = Split-Path -Parent $MyInvocation.MyCommand.Path
$repo = (Resolve-Path (Join-Path $here '..\..\..\..\..')).Path
Push-Location $repo
try {
  # Fail early with an explicit parser gate before any source staging or XDK call.
  & python.exe -m py_compile (Join-Path $here 'Stage-K1V6wRetail22FA9E.py') (Join-Path $here 'Stage-K1V6qNativeWatson.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6w Python syntax preflight failed. No XDK invoked.' }
  Write-Host '[K1-V6w] PYTHON SYNTAX PREFLIGHT PASS'
  & python.exe (Join-Path $here 'Stage-K1V6wRetail22FA9E.py')
  if ($LASTEXITCODE -ne 0) { throw 'V6w retail 22FA9E translation/ABI/source proof blocked the build' }
  $stage = Join-Path $repo 'build\phase6_integration_map\k1_pixel_retail_22fa9e_v6w'
  $manifest = Get-Content (Join-Path $stage 'v6w-manifest.json') -Raw | ConvertFrom-Json
  if ($manifest.stage -ne 'V6W_ORIGINAL_RETAIL_22FA9E_X87_TRANSLATION_SOURCE_UNTESTED' -or
      $manifest.root_entry -ne '0x0022FA9E' -or
      $manifest.root_end_exclusive -ne '0x0022FB1F' -or
      $manifest.original_instruction_count -ne 56 -or
      $manifest.original_ret_esp -ne 8 -or
      $manifest.native_summary_preserved -ne $true -or
      $manifest.unknown_frontiers_fenced -ne $true -or
      $manifest.seven_async_reads_preserved_in_source -ne $true -or
      @($manifest.true_tu_sha256.PSObject.Properties).Count -ne 64 -or
      @($manifest.direct_compiled_callees).Count -ne 3) {
    throw 'V6w original x87 / ABI / source-integrity manifest guard failed'
  }
  $src = Join-Path $stage 'main.cpp'
  if ((Get-FileHash $src -Algorithm SHA256).Hash -ne $manifest.source_sha256.ToUpperInvariant()) {
    throw 'V6w main.cpp SHA-256 mismatch'
  }
  Write-Host '[K1-V6w] RETAIL 0022FA9E SOURCE: 56 instructions, ret8, 3 original compiled callees'
  Write-Host '[K1-V6w] V6rLOG native summary and all original 64 TrueTUs preserved'
  if ($StageOnly) { Write-Host '[K1-V6w] STAGE PASS, XDK not invoked'; return }
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
    PublishedXex = (Join-Path $out 'Merc-K1-V6w-Retail22FA9E.xex')
  }
  & (Join-Path $repo 'ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1') @args
  if ($LASTEXITCODE -ne 0) { throw 'V6w build failed' }
  if (!(Test-Path $args.PublishedXex)) { throw 'V6w XEX not published' }
  Write-Host '[K1-V6w] BUILD PASS - Xbox run still unverified'
  Get-Item $args.PublishedXex | Select-Object FullName,Length,LastWriteTime
} finally { Pop-Location }
