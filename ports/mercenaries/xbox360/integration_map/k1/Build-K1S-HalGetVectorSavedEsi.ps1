[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$previous = Join-Path $PSScriptRoot "Build-K1R-A6B98A7B73StackPath.ps1"
$rootK1R = Join-Path $repo "build\phase6_integration_map\k1r_a6b98_a7b73_stack_path"
$baseline = Join-Path $rootK1R "translated_shards"
$baselineManifest = Join-Path $rootK1R "k1r-a6b98-a7b73-manifest.json"
$k1q = Join-Path $repo "build\phase6_integration_map\k1q_a6b98_nested_stack.txt"
$root = Join-Path $repo "build\phase6_integration_map\k1s_halgetvector44_saved_esi"
$staged = Join-Path $root "translated_shards"
$manifest = Join-Path $root "k1s-halgetvector44-saved-esi-manifest.json"
$buildDir = Join-Path $root "xdk"
$newXex = Join-Path $buildDir "Merc-K1S-HalGetVectorSavedEsi.xex"
$main = Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$envFile = Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder = Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$stager = Join-Path $PSScriptRoot "Stage-K1S-HalGetVectorSavedEsi.py"
$tester = Join-Path $PSScriptRoot "Test-K1S-HalGetVectorSavedEsi.py"

foreach($file in @($previous,$baselineManifest,$k1q,$main,$envFile,$builder,$stager,$tester)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1S] Missing required K1R/K1Q source or builder: $file"
    }
}
$py = (Get-Command python -ErrorAction Stop).Source

Write-Host "[K1S] Verify K1R/P/J/G/E baseline SHA and source contracts"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $previous -PreflightOnly
if($LASTEXITCODE -ne 0) { throw "[K1S] K1R provenance preflight failed (no build)" }

Write-Host "[K1S] Test one-slot correction against original K1Q source + reconstructed K1R instrumentation"
& $py -u $tester --k1q-report $k1q
if($LASTEXITCODE -ne 0) { throw "[K1S] Real-source regression test failed (no build)" }

Write-Host "[K1S] Stage only translated_044.cpp, preserving 63 TUs and all headers"
& $py -u $stager --k1r-shards $baseline --k1r-manifest $baselineManifest --k1q-report $k1q --out $staged
if($LASTEXITCODE -ne 0) { throw "[K1S] SHA/provenance staging failed (no build)" }

$m = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$owner = "translated_044.cpp"
if($m.marker -ne "K1S-HALGETVECTOR44-SAVED-ESI-20261030" -or
   $m.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   [int]$m.translated_shards -ne 64 -or
   [int]$m.unchanged_from_k1r -ne 63 -or
   @($m.modified_from_k1r).Count -ne 1 -or
   $m.modified_from_k1r[0] -ne $owner -or
   [int]$m.guest_memory_ops_added -ne 0 -or
   [int]$m.guest_register_writes_added -ne 1 -or
   $m.hard_fences -ne "UNCHANGED" -or
   $m.preserved_k1r_k1p_k1j_k1g_k1e_watchers -ne $true){
    throw "[K1S] Guest stack policy or manifest provenance differs"
}
$baseFiles = @(Get-ChildItem -LiteralPath $baseline -File)
$targetFiles = @(Get-ChildItem -LiteralPath $staged -File)
if(@($baseFiles | Where-Object Name -like "translated_*.cpp").Count -ne 64 -or
   @($targetFiles | Where-Object Name -like "translated_*.cpp").Count -ne 64 -or
   $baseFiles.Count -ne $targetFiles.Count){
    throw "[K1S] TrueTU/header file set changed"
}
foreach($file in $baseFiles){
    $dest = Join-Path $staged $file.Name
    if(-not(Test-Path -LiteralPath $dest -PathType Leaf)){
        throw "[K1S] Missing staged source/header: $($file.Name)"
    }
    $oldSha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $newSha = (Get-FileHash -LiteralPath $dest -Algorithm SHA256).Hash
    if($file.Name -eq $owner){
        if($oldSha -ne $m.original_owner_sha256.ToUpperInvariant() -or
           $newSha -ne $m.staged_owner_sha256.ToUpperInvariant() -or
           $oldSha -eq $newSha) {
            throw "[K1S] Exact repaired owner SHA mismatch"
        }
        $source=Get-Content -LiteralPath $dest -Raw -Encoding UTF8
        if(([regex]::Matches($source,"K1S HALGETVECTOR44 ESI SLOT:")).Count -ne 1 -or
           ([regex]::Matches($source,"esp = k1s_saved_esi_slot;")).Count -ne 1 -or
           ([regex]::Matches($source,"K1R ICALL A7B73_ICALL_2:")).Count -ne 1) {
            throw "[K1S] One-slot correction / raw K1R telemetry not unique"
        }
    } elseif($oldSha -ne $newSha){
        throw "[K1S] A non-target TrueTU or header was modified: $($file.Name)"
    }
}
Write-Host "[K1S] PREFLIGHT PASS: exactly 1 guest ESP assignment in A7B73 after ordinal 44"
Write-Host "[K1S] K1R raw ESP witnesses remain; 63 other TrueTUs+headers unchanged"
Write-Host "[K1S] Zero guest memory ops/fence changes; only EBP-8 to EBP-12 when proven drift matches"
if($PreflightOnly){
    Write-Host "[K1S] PREFLIGHT ONLY: no XDK build or Xbox execution"
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
    PublishedXex = $newXex
    ShadowBuildRoot = $FastBuildRoot
    SkipClean = $true
}
Write-Host "[K1S] Incremental VS2017 Release Xbox 360, Clean skipped"
& $builder @args
if($LASTEXITCODE -ne 0){ throw "[K1S] Xbox build failed" }
if(-not(Test-Path -LiteralPath $newXex -PathType Leaf)){
    throw "[K1S] Built diagnostic XEX not present"
}
Write-Host "[K1S] BUILD PASS $newXex"
Write-Host "[K1S] Xbox capture: K1S HALGETVECTOR44 ESI SLOT, K1R CALL/PATH, K1P STACK EDGE, K1J EBX"
Write-Host "[K1S] Check first downstream hard stop, tick count, AV display calls and framebuffer"
