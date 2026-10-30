[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$previousBuilder = Join-Path $PSScriptRoot "Build-K1J-DsoundReturnEbxWatch.ps1"
$k1jRoot = Join-Path $repo "build\phase6_integration_map\k1j_dsound_register_edges"
$baseline = Join-Path $k1jRoot "translated_shards"
$baselineManifest = Join-Path $k1jRoot "k1j-dsound-register-manifest.json"
$k1o = Join-Path $repo "build\phase6_integration_map\k1o_a7322_tail_return.txt"
$stageRoot = Join-Path $repo "build\phase6_integration_map\k1p_a739f_a7322_stack_edges"
$staged = Join-Path $stageRoot "translated_shards"
$manifest = Join-Path $stageRoot "k1p-stack-return-edges-manifest.json"
$buildDir = Join-Path $stageRoot "xdk"
$newXex = Join-Path $buildDir "Merc-K1P-StackEdges.xex"
$main = Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$envFile = Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder = Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$stager = Join-Path $PSScriptRoot "Stage-K1P-A739F-A7322-StackEdges.py"
$test = Join-Path $PSScriptRoot "Test-K1P-A739F-A7322-StackEdges.py"
foreach($item in @($previousBuilder,$baselineManifest,$k1o,$main,$envFile,$builder,$stager,$test)){
    if(-not(Test-Path -LiteralPath $item -PathType Leaf)){
        throw "[K1P] Missing provenance or build input: $item"
    }
}
$py = (Get-Command python -ErrorAction Stop).Source
Write-Host "[K1P] Verify the earlier hardware-tested K1E/G/J source baseline"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $previousBuilder -PreflightOnly
if($LASTEXITCODE -ne 0) { throw "[K1P] Previous K1J source preflight failed; NO XDK build" }

Write-Host "[K1P] Test source-only call-edge probes before staging"
& $py -u $test
if($LASTEXITCODE -ne 0) { throw "[K1P] Synthetic checks failed; NO XDK build" }
& $py -u $stager --k1j-shards $baseline --k1j-manifest $baselineManifest --k1o-report $k1o --out $staged
if($LASTEXITCODE -ne 0) { throw "[K1P] Staging failed; NO XDK build" }

$m = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($m.marker -ne "K1P-DSOUND-STACK-EDGE-20261030" -or
   $m.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   [int]$m.translated_shards -ne 64 -or
   [int]$m.unchanged_from_k1j -ne 62 -or
   [int]$m.probe_count -ne 15 -or
   @($m.modified_from_k1j).Count -ne 2 -or
   @($m.modified_from_k1j)[0] -ne "translated_009.cpp" -or
   @($m.modified_from_k1j)[1] -ne "translated_057.cpp" -or
   [int]$m.guest_memory_ops_added -ne 0 -or
   [int]$m.guest_register_writes_added -ne 0 -or
   $m.hard_fences -ne "UNCHANGED" -or
   $m.preserved_k1e_k1g_k1j_watchers -ne $true){
    throw "[K1P] Manifest source/guest memory policy mismatch"
}
$baseFiles = @(Get-ChildItem -LiteralPath $baseline -File)
$stagedFiles = @(Get-ChildItem -LiteralPath $staged -File)
if(@($baseFiles | Where-Object Name -like "translated_*.cpp").Count -ne 64 -or
   @($stagedFiles | Where-Object Name -like "translated_*.cpp").Count -ne 64 -or
   $baseFiles.Count -ne $stagedFiles.Count) {
    throw "[K1P] Not exactly 64 TrueTUs or missing header"
}
$changedNames = @("translated_009.cpp","translated_057.cpp")
foreach($original in $baseFiles) {
    $candidate = Join-Path $staged $original.Name
    if(-not(Test-Path -LiteralPath $candidate -PathType Leaf)) {
        throw "[K1P] Missing staged source/header: $($original.Name)"
    }
    $oldHash = (Get-FileHash -LiteralPath $original.FullName -Algorithm SHA256).Hash
    $newHash = (Get-FileHash -LiteralPath $candidate -Algorithm SHA256).Hash
    if($original.Name -in $changedNames) {
        $record = $m.changed_owner_hashes.($original.Name)
        if($null -eq $record -or
           $record.original_sha256.ToUpperInvariant() -ne $oldHash -or
           $record.staged_sha256.ToUpperInvariant() -ne $newHash -or
           $oldHash -eq $newHash) {
            throw "[K1P] Source owner SHA mismatch: $($original.Name)"
        }
    } elseif($oldHash -ne $newHash) {
        throw "[K1P] Non-target source/header changed: $($original.Name)"
    }
}
Write-Host "[K1P] PREFLIGHT PASS: exactly 15 call-edge traces across 2 new TrueTUs"
Write-Host "[K1P] 62 other TrueTUs, headers, K1J/G/E watchers and fences untouched"
Write-Host "[K1P] Reports expected callsite argument-cleanup widths, not guesses"
if($PreflightOnly) {
    Write-Host "[K1P] PREFLIGHT ONLY: NO Xbox build or deploy"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$buildArgs = @{
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
    PublishedXex = $newXex
    ShadowBuildRoot = $FastBuildRoot
    SkipClean = $true
}
Write-Host "[K1P] Launch incremental VS2017 Xbox360 build (Clean skipped)"
& $builder @buildArgs
if($LASTEXITCODE -ne 0) { throw "[K1P] XDK build failed" }
if(-not(Test-Path -LiteralPath $newXex -PathType Leaf)) {
    throw "[K1P] Built XEX not present"
}
Write-Host "[K1P] BUILD PASS: $newXex"
Write-Host "[K1P] Xbox log: find 'K1P STACK EDGE' and identify FIRST delta != expected"
Write-Host "[K1P] No guest register/memory correction; previous hard fence remains"
