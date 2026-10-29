[CmdletBinding()]
param(
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port",
    [switch]$PreflightOnly
)
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$repo = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$phase6 = Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics"
$main = Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$shards = Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk\translated_shards"
$envFile = Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$stageDir = Join-Path $repo "build\phase6_integration_map\k1a_clock_staging"
$staged = Join-Path $stageDir "main.cpp"
$manifest = Join-Path $stageDir "k1a-stage-manifest.json"
$buildDir = Join-Path $repo "build\phase6_integration_map\k1a_clock_build"
$published = Join-Path $buildDir "Merc-K1A-ClockBatch.xex"
$builder = Join-Path $phase6 "Invoke-VS17Xbox360Build.ps1"
$expectedR76 = "A6A2493EC8F31F70165FEE3E3A8DBC72B02679E763DCC514F131FA3E04959C90"
$bootMarker = "P6K1A-BOOT-CLOCK128-304-305-20261029"
$python = Join-Path $repo ".venv\Scripts\python.exe"
if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    $command = Get-Command python -ErrorAction SilentlyContinue
    if ($null -eq $command) { throw "[K1A] Python not found" }
    $python = $command.Source
}
foreach ($file in @($main, $envFile, $builder,
    (Join-Path $PSScriptRoot "Test-K1A-Audit.py"),
    (Join-Path $PSScriptRoot "Test-K1A-Stage.py"),
    (Join-Path $PSScriptRoot "Stage-K1A-ClockBatch.py"))) {
    if (-not (Test-Path -LiteralPath $file -PathType Leaf)) {
        throw "[K1A] Missing prerequisite: $file"
    }
}
if (-not (Test-Path -LiteralPath $shards -PathType Container)) {
    throw "[K1A] TrueTU shard folder missing: $shards"
}
$shardFiles = @(Get-ChildItem -LiteralPath $shards -Filter "translated_*.cpp" -File)
if ($shardFiles.Count -ne 64) {
    throw "[K1A] Expected exactly 64 TrueTU .cpp shards, got $($shardFiles.Count)"
}
$r76Hash = (Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash
if ($r76Hash -ne $expectedR76) {
    throw "[K1A] R76 main SHA mismatch. Expected $expectedR76, got $r76Hash"
}
$shardHashes = @{}
foreach ($file in $shardFiles) {
    $shardHashes[$file.Name] = (Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
}
Write-Host "[K1A] ========================================================"
Write-Host "[K1A]  KERNEL CLOCK BATCH: 128 + 304 + 305"
Write-Host "[K1A] ========================================================"
Write-Host "[K1A] R76 SHA verified; 64 TrueTU shards recorded"
foreach ($test in @("Test-K1A-Audit.py", "Test-K1A-Stage.py")) {
    & $python -u (Join-Path $PSScriptRoot $test)
    if ($LASTEXITCODE -ne 0) { throw "[K1A] Offline fixture FAILED: $test" }
}
New-Item -Path $stageDir -ItemType Directory -Force | Out-Null
& $python -u (Join-Path $PSScriptRoot "Stage-K1A-ClockBatch.py") --main $main --out $staged
if ($LASTEXITCODE -ne 0) { throw "[K1A] Staging FAILED; no XDK build" }
$doc = Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$stagedHash = (Get-FileHash -LiteralPath $staged -Algorithm SHA256).Hash
if ($doc.status -ne "STAGED_NOT_BUILT" -or
    $doc.original_main_sha256.ToUpperInvariant() -ne $expectedR76 -or
    $doc.staged_main_sha256.ToUpperInvariant() -ne $stagedHash -or
    @($doc.import_ordinals).Count -ne 3 -or
    [int]$doc.import_ordinals[0] -ne 128 -or
    [int]$doc.import_ordinals[1] -ne 304 -or
    [int]$doc.import_ordinals[2] -ne 305 -or
    $doc.boot_marker -ne $bootMarker) {
    throw "[K1A] Stage manifest hash, ordinal or boot marker mismatch"
}
$stagedText = Get-Content -LiteralPath $staged -Raw
if (-not $stagedText.Contains($bootMarker)) {
    throw "[K1A] Staged main is missing distinct runtime boot watermark"
}
if ((Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash -ne $expectedR76) {
    throw "[K1A] Original R76 main changed; refusing build"
}
Write-Host "[K1A] OFFLINE STAGE: PASS"
Write-Host "[K1A] K1A staged SHA: $stagedHash"
Write-Host "[K1A] R76 source unchanged; 64 TrueTU shards untouched"
if ($PreflightOnly) {
    Write-Host "[K1A] PREFLIGHT ONLY: VS2017/XDK build skipped"
    exit 0
}
New-Item -Path $buildDir -ItemType Directory -Force | Out-Null
$buildArgs = @{
    GeneratedMain = $staged
    GeneratedEnv = $envFile
    GeneratedShardDir = $shards
    ExpectedBuildTag = "P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie = "phase6dq_env_build_cookie"
    SolutionRoot = $SolutionRoot
    Configuration = "Release"
    Platform = "Xbox 360"
    CleanLog = (Join-Path $buildDir "xdk-clean.log")
    BuildLog = (Join-Path $buildDir "xdk-build.log")
    PublishedXex = $published
    ShadowBuildRoot = $FastBuildRoot
    SkipClean = $true
}
Write-Host "[K1A] Starting INCREMENTAL VS2017/XDK build (no clean)"
& $builder @buildArgs
if ($LASTEXITCODE -ne 0) { throw "[K1A] Xbox 360 build wrapper returned failure" }
if (-not (Test-Path -LiteralPath $published -PathType Leaf)) {
    throw "[K1A] Build claimed success but no separate K1A XEX was published"
}
if ((Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash -ne $expectedR76) {
    throw "[K1A] R76 main was modified during build"
}
foreach ($file in $shardFiles) {
    if ((Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash -ne $shardHashes[$file.Name]) {
        throw "[K1A] TrueTU shard SHA changed: $($file.Name)"
    }
}
Write-Host "[K1A] BUILD PASS: K1A clock batch compiled; original R76 files untouched"
Write-Host "[K1A] New XEX: $published"
Write-Host "[K1A] New boot marker: $bootMarker"
Write-Host "[K1A] Runtime/kernel ABI and rendering are NOT YET hardware-verified"
