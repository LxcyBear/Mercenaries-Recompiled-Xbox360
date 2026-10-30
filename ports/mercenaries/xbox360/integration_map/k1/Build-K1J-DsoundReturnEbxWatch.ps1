[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$py = Get-Command python -ErrorAction SilentlyContinue
if ($null -eq $py) { throw "[K1J] Python is missing" }
$python = $py.Source

$k1gBuilder = Join-Path $PSScriptRoot "Build-K1G-XactRegisterProvenance.ps1"
if (-not(Test-Path -LiteralPath $k1gBuilder -PathType Leaf)) {
    throw "[K1J] K1G proven-base preflight unavailable"
}
Write-Host "[K1J] Rechecking K1E/K1G original 64-TU/R76/K1C source provenance"
& powershell.exe -NoProfile -ExecutionPolicy Bypass -File $k1gBuilder -PreflightOnly
if ($LASTEXITCODE -ne 0) { throw "[K1J] K1G preflight failed; no XDK build" }

$k1gRoot = Join-Path $repo "build\phase6_integration_map\k1g_xact_register_provenance"
$baseline = Join-Path $k1gRoot "translated_shards"
$baselineManifest = Join-Path $k1gRoot "k1g-register-provenance-manifest.json"
$k1iReport = Join-Path $repo "build\phase6_integration_map\k1i_dsound_nested_ebx.txt"
$stageRoot = Join-Path $repo "build\phase6_integration_map\k1j_dsound_register_edges"
$staged = Join-Path $stageRoot "translated_shards"
$manifest = Join-Path $stageRoot "k1j-dsound-register-manifest.json"
$buildDir = Join-Path $stageRoot "xdk"
$newXex = Join-Path $buildDir "Merc-K1J-DsoundRegisterEdges.xex"
$main = Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$envPath = Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder = Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$test = Join-Path $PSScriptRoot "Test-K1J-DsoundReturnEbxWatch.py"
$stager = Join-Path $PSScriptRoot "Stage-K1J-DsoundReturnEbxWatch.py"

foreach ($path in @($baselineManifest,$k1iReport,$main,$envPath,$builder,$test,$stager)) {
    if (-not(Test-Path -LiteralPath $path -PathType Leaf)) {
        throw "[K1J] Missing required input: $path"
    }
}
$k1i = Get-Content -LiteralPath $k1iReport -Raw -Encoding UTF8
if (-not ($k1i.Contains("Source bodies indexed=13510") -and
           $k1i.Contains("Reachable named functions=29; missing bodies=0") -and
           $k1i.Contains("SUB_0029FDF0 -> SUB_0029FD83 -> SUB_0029FC4A") -and
           $k1i.Contains("K1I READ-ONLY DSOUND NESTED EBX PROVENANCE"))) {
    throw "[K1J] K1I source-only evidence gates failed; no XDK build"
}

& $python -u $test
if ($LASTEXITCODE -ne 0) { throw "[K1J] Synthetic source checks failed; no XDK build" }
& $python -u $stager --k1g-shards $baseline --k1g-manifest $baselineManifest --out $staged
if ($LASTEXITCODE -ne 0) { throw "[K1J] Staging failed; no XDK build" }

$doc = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
if ($doc.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
    $doc.marker -ne "K1J-DSOUND-RETURN-EBX-20261030" -or
    $doc.baseline_marker -ne "K1G-XACT-REGISTER-PROVENANCE-20261030" -or
    [int]$doc.translated_shards -ne 64 -or [int]$doc.unchanged_from_k1g -ne 62 -or
    @($doc.modified_from_k1g).Count -ne 2 -or
    @($doc.modified_from_k1g)[0] -ne "translated_017.cpp" -or
    @($doc.modified_from_k1g)[1] -ne "translated_041.cpp" -or
    @($doc.probe_stages).Count -ne 10 -or
    $doc.preserved_k1g_owner -ne $true -or
    $doc.preserved_k1e_witness -ne $true -or
    [int]$doc.guest_memory_ops_added -ne 0 -or
    [int]$doc.guest_register_writes_added -ne 0 -or
    $doc.unknown_memory_fences -ne "UNCHANGED") {
    throw "[K1J] Manifest/source policy failed; no XDK build"
}
$baselineFiles = @(Get-ChildItem -LiteralPath $baseline -File)
$stagedFiles = @(Get-ChildItem -LiteralPath $staged -File)
if (@($baselineFiles | Where-Object Name -like 'translated_*.cpp').Count -ne 64 -or
    @($stagedFiles | Where-Object Name -like 'translated_*.cpp').Count -ne 64 -or
    $baselineFiles.Count -ne $stagedFiles.Count) {
    throw "[K1J] TrueTU/header file count drift"
}
foreach ($file in $baselineFiles) {
    $newFile = Join-Path $staged $file.Name
    if (-not(Test-Path -LiteralPath $newFile -PathType Leaf)) {
        throw "[K1J] Missing staged input: $($file.Name)"
    }
    $oldSha = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    $newSha = (Get-FileHash -LiteralPath $newFile -Algorithm SHA256).Hash
    if ($file.Name -in @('translated_017.cpp','translated_041.cpp')) {
        $identity = $doc.changed_owner_hashes.($file.Name)
        if ($identity.old_sha256.ToUpperInvariant() -ne $oldSha -or
            $identity.new_sha256.ToUpperInvariant() -ne $newSha -or
            $oldSha -eq $newSha) {
            throw "[K1J] Changed owner SHA mismatch: $($file.Name)"
        }
        $oldText = Get-Content -LiteralPath $file.FullName -Raw -Encoding UTF8
        $newText = Get-Content -LiteralPath $newFile -Raw -Encoding UTF8
        $oldGuest = [regex]::Matches($oldText,'\bGUEST_(?:READ|WRITE)(?:8|16|32|64|128)\(')
        $newGuest = [regex]::Matches($newText,'\bGUEST_(?:READ|WRITE)(?:8|16|32|64|128)\(')
        if ($oldGuest.Count -ne $newGuest.Count) {
            throw "[K1J] Guest memory operation count drift: $($file.Name)"
        }
    }
    elseif ($oldSha -ne $newSha) {
        throw "[K1J] Non-target TrueTU/header changed: $($file.Name)"
    }
}
$old029 = Get-FileHash -LiteralPath (Join-Path $baseline 'translated_029.cpp') -Algorithm SHA256
$new029 = Get-FileHash -LiteralPath (Join-Path $staged 'translated_029.cpp') -Algorithm SHA256
if ($old029.Hash -ne $new029.Hash) {
    throw "[K1J] Prior K1G/K1E hardware witnesses changed"
}
Write-Host "[K1J] PREFLIGHT PASS: K1H/K1I narrowed 29FDF0/FD83 nested-ABI corruption boundary"
Write-Host "[K1J] Two changed DSOUND TrueTUs, 62 untouched TrueTUs, every header identical"
Write-Host "[K1J] K1G/K1E telemetry preserved, no guest CPU/memory changes, hard fences intact"
if ($PreflightOnly) {
    Write-Host "[K1J] PREFLIGHT ONLY - NO XDK BUILD"
    exit 0
}

New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$buildArgs = @{
    GeneratedMain     = $main
    GeneratedEnv      = $envPath
    GeneratedShardDir = $staged
    ExpectedBuildTag  = "P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie = "phase6dq_env_build_cookie"
    SolutionRoot      = $SolutionRoot
    Configuration     = "Release"
    Platform          = "Xbox 360"
    CleanLog          = (Join-Path $buildDir "xdk-clean.log")
    BuildLog          = (Join-Path $buildDir "xdk-build.log")
    PublishedXex      = $newXex
    ShadowBuildRoot   = $FastBuildRoot
    SkipClean         = $true
}
Write-Host "[K1J] VS2017 incremental Xbox build, only 2 DSOUND TrueTUs newly changed, CLEAN SKIPPED"
& $builder @buildArgs
if ($LASTEXITCODE -ne 0) { throw "[K1J] XDK build failed" }
if (-not(Test-Path -LiteralPath $newXex -PathType Leaf)) {
    throw "[K1J] XEX missing after reported build"
}
Write-Host "[K1J] BUILD PASS: $newXex"
Write-Host "[K1J] Xbox: look for 'K1J DSOUND ABI' + original 'K1G XACT ABI' + K1E list prewrite"
Write-Host "[K1J] NO register-repair guess; READ32 EFEE0EC4 hard stop is still intentional"
