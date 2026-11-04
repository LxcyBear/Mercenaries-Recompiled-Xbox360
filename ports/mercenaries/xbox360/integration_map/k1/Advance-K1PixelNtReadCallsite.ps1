[CmdletBinding()]
param(
    [switch]$SourceOnly,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$base=Join-Path $root "build\phase6_integration_map"
$r8=Join-Path $base "k1_ntread44_frame_evidence_r8"
$outDir=Join-Path $base "k1_pixel_ntread_callsite"
$stage=Join-Path $PSScriptRoot "Stage-K1PixelNtReadCallsite.py"
$main=Join-Path $outDir "main.cpp"
$report=Join-Path $outDir "source-evidence.json"
$shards=Join-Path $base "k1_d3d_six_cases_r3\translated_shards"
$python=(Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1-PIXEL] Python syntax failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1-PIXEL] Selftest failed"}
& $python -u $stage --parent (Join-Path $r8 "main.cpp") --manifest (Join-Path $r8 "k1-r8-ntread44-frame-evidence-manifest.json") --shards $shards --output $main --report $report
if($LASTEXITCODE -ne 0){throw "[K1-PIXEL] Verified stage failed closed"}
if($SourceOnly){Write-Host "[K1-PIXEL] SOURCE ONLY. No XDK/XEX/Xbox.";return}
$builder=Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envMain=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk=Join-Path $outDir "xdk"
New-Item -ItemType Directory -Path $xdk -Force | Out-Null
$xex=Join-Path $xdk "Merc-K1-Pixel-NtRead-Callsite.xex"
$buildLog=Join-Path $xdk "xdk-build.log"
$started=Get-Date
& $builder -GeneratedMain $main -GeneratedEnv $envMain -GeneratedShardDir $shards `
    -ExpectedBuildTag "P6DQ-R51-MM173-FRAME-20261029-A" -ExpectedEnvCookie "phase6dq_env_build_cookie" `
    -SolutionRoot $SolutionRoot -Configuration "Release" -Platform "Xbox 360" `
    -CleanLog (Join-Path $xdk "xdk-clean.log") -BuildLog $buildLog -PublishedXex $xex `
    -ShadowBuildRoot $FastBuildRoot -SkipClean
if($LASTEXITCODE -ne 0 -or -not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1-PIXEL] Fresh XDK build failed"
}
$buildMatches=@(Select-String -LiteralPath $buildLog -Pattern '========== Build:\s*[1-9]\d* succeeded')
if($buildMatches.Count -lt 1){throw "[K1-PIXEL] No compilation success in build log"}
$f=Get-Item -LiteralPath $xex
if($f.Length -lt 1000000 -or $f.LastWriteTime -lt $started.AddSeconds(-2)){
    throw "[K1-PIXEL] Stale or implausibly small XEX"
}
$sha=(Get-FileHash -LiteralPath $xex -Algorithm SHA256).Hash
Write-Host "[K1-PIXEL] FRESH BUILD PASS: $xex" -ForegroundColor Green
Write-Host "[K1-PIXEL] SHA256: $sha"
Write-Host "[K1-PIXEL] On Xbox, look for K1-PIXEL NTREAD FRAME SOURCE and original KERNEL_FRAME hard stop"
Write-Host "[K1-PIXEL] This build diagnoses the storage boundary; game pixels are NOT yet proven"
