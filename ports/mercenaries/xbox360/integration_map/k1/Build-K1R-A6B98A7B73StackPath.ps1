[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$k1pBuild = Join-Path $PSScriptRoot "Build-K1P-A739F-A7322-StackEdges.ps1"
$k1pDir = Join-Path $repo "build\phase6_integration_map\k1p_a739f_a7322_stack_edges"
$baseline = Join-Path $k1pDir "translated_shards"
$baselineManifest = Join-Path $k1pDir "k1p-stack-return-edges-manifest.json"
$original = Join-Path $repo "build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards"
$k1qReport = Join-Path $repo "build\phase6_integration_map\k1q_a6b98_nested_stack.txt"
$stageRoot = Join-Path $repo "build\phase6_integration_map\k1r_a6b98_a7b73_stack_path"
$staged = Join-Path $stageRoot "translated_shards"
$manifest = Join-Path $stageRoot "k1r-a6b98-a7b73-manifest.json"
$buildDir = Join-Path $stageRoot "xdk"
$xex = Join-Path $buildDir "Merc-K1R-A6B98-A7B73-StackPath.xex"
$main = Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$envFile = Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder = Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$stager = Join-Path $PSScriptRoot "Stage-K1R-A6B98A7B73StackPath.py"
$tester = Join-Path $PSScriptRoot "Test-K1R-A6B98A7B73StackPath.py"
foreach($file in @($k1pBuild,$baselineManifest,$k1qReport,$main,$envFile,$builder,$stager,$tester)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1R] Missing required verified input: $file"
    }
}
$py = (Get-Command python -ErrorAction Stop).Source
Write-Host "[K1R] Preflight K1P, including its K1J/G/E TrueTU source identities"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $k1pBuild -PreflightOnly
if($LASTEXITCODE -ne 0) { throw "[K1R] K1P source provenance preflight failed" }

Write-Host "[K1R] Verify probes against the exact user K1Q frozen-source report"
& $py -u $tester --k1q-report $k1qReport
if($LASTEXITCODE -ne 0) { throw "[K1R] K1Q real-source probe test failed; NO XDK" }

Write-Host "[K1R] Stage two new TrueTUs, retaining all 15 K1P call-edge witnesses"
& $py -u $stager --k1p-shards $baseline --k1p-manifest $baselineManifest --original-shards $original --k1q-report $k1qReport --out $staged
if($LASTEXITCODE -ne 0) { throw "[K1R] Staging failed; NO XDK" }

$m = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$targetNames = @("translated_005.cpp","translated_044.cpp")
if($m.marker -ne "K1R-A6B98-A7B73-STACK-PATH-20261030" -or
   $m.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   [int]$m.translated_shards -ne 64 -or
   [int]$m.unchanged_from_k1p -ne 62 -or
   [int]$m.probe_count -ne 21 -or
   @($m.modified_from_k1p).Count -ne 2 -or
   @($m.modified_from_k1p)[0] -ne $targetNames[0] -or
   @($m.modified_from_k1p)[1] -ne $targetNames[1] -or
   [int]$m.guest_memory_ops_added -ne 0 -or
   [int]$m.guest_register_writes_added -ne 0 -or
   $m.hard_fences -ne "UNCHANGED" -or
   $m.preserved_k1p_k1j_k1g_k1e_watchers -ne $true){
    throw "[K1R] Source-integrity or guest-mutation manifest gate failed"
}
$baseFiles = @(Get-ChildItem -LiteralPath $baseline -File)
$stagedFiles = @(Get-ChildItem -LiteralPath $staged -File)
if(@($baseFiles | Where-Object Name -like "translated_*.cpp").Count -ne 64 -or
   @($stagedFiles | Where-Object Name -like "translated_*.cpp").Count -ne 64 -or
   $baseFiles.Count -ne $stagedFiles.Count){
    throw "[K1R] Shard/header set changed"
}
foreach($file in $baseFiles){
    $stagedPath = Join-Path $staged $file.Name
    if(-not(Test-Path -LiteralPath $stagedPath -PathType Leaf)){
        throw "[K1R] Missing staged source $($file.Name)"
    }
    $oldSha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $newSha = (Get-FileHash -LiteralPath $stagedPath -Algorithm SHA256).Hash
    if($file.Name -in $targetNames) {
        $record = $m.owner_hashes.($file.Name)
        if($null -eq $record -or
           $record.original_sha256.ToUpperInvariant() -ne $oldSha -or
           $record.staged_sha256.ToUpperInvariant() -ne $newSha -or
           $oldSha -eq $newSha){
            throw "[K1R] Owner SHA mismatch: $($file.Name)"
        }
    } elseif ($oldSha -ne $newSha){
        throw "[K1R] Non-target TrueTU/header changed: $($file.Name)"
    }
}
Write-Host "[K1R] PREFLIGHT PASS: 9 A6B98 call, 4 A7B73 direct, 5 indirect, 3 branch checkpoints"
Write-Host "[K1R] 62/64 existing TrueTUs + all headers unchanged from K1P"
Write-Host "[K1R] No guest CPU/stack/memory modifications; hard fences unchanged"
if($PreflightOnly){
    Write-Host "[K1R] PREFLIGHT ONLY: NO XDK build or Xbox deployment"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$args = @{
    GeneratedMain = $main
    GeneratedEnv = $envFile
    GeneratedShardDir = $staged
    ExpectedBuildTag = "P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie = "phase6dq_env_build_cookie"
    SolutionRoot = $SolutionRoot
    Configuration = "Release"
    Platform = "Xbox 360"
    CleanLog = (Join-Path $buildDir "xdk-clean.log")
    BuildLog = (Join-Path $buildDir "xdk-build.log")
    PublishedXex = $xex
    ShadowBuildRoot = $FastBuildRoot
    SkipClean = $true
}
Write-Host "[K1R] VS2017 Release Xbox 360 incremental build, Clean skipped"
& $builder @args
if($LASTEXITCODE -ne 0) { throw "[K1R] XDK build failed" }
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1R] Compiled XEX not present"
}
Write-Host "[K1R] BUILD PASS: $xex"
Write-Host "[K1R] Xbox: capture K1R CALL / ICALL / PATH, K1P, R49, and K1J EBX"
Write-Host "[K1R] No stack/register repair or MMIO fence relaxation has been applied"
