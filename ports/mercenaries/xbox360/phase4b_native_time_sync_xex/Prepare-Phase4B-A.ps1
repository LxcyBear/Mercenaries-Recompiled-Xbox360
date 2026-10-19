[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$phase4aJson = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"
$source = Join-Path $phaseRoot "main.cpp"
$buildRoot = Join-Path $repoRoot "build\phase4b_native_time_sync"
$output = Join-Path $buildRoot "main.cpp"

if (-not (Test-Path -LiteralPath $phase4aJson -PathType Leaf)) {
    throw "Phase 4A report not found. Run Prepare-Phase4A.ps1 first."
}

$report = Get-Content -LiteralPath $phase4aJson -Raw | ConvertFrom-Json
$c = $report.counts

$expected = @{
    imports = 111
    guest_bridge_explicit = 74
    guest_data_exports = 11
    guest_fallback = 26
    guest_arg_metadata_missing = 0
    guest_arg_metadata_mismatch = 0
    fallback_referenced_imports = 0
    fallback_static_refs = 0
}

foreach ($name in $expected.Keys) {
    if ([int]$c.$name -ne [int]$expected[$name]) {
        throw "Phase 4A gate changed: $name expected $($expected[$name]), got $($c.$name). Rerun/review Phase 4A before Phase 4B."
    }
}

$hostSurface = [int]$c.host_surface_flagged
$platformBound = 0
if ($c.PSObject.Properties.Name -contains "platform_surface_bound") {
    $platformBound = [int]$c.platform_surface_bound
}
if (($hostSurface + $platformBound) -ne 17) {
    throw "Phase 4 surface accounting changed: expected host+platform = 17, got $hostSurface+$platformBound."
}

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Phase 4B-A source missing: $source"
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
Copy-Item -LiteralPath $source -Destination $output -Force

Write-Host "[Phase4B-A] NATIVE XENON TIME/SYNC HARDWARE GATE"
Write-Host "[Phase4B-A] Phase 4A lock verified: 111 imports / 74 bridges / 11 data / 26 fallbacks."
Write-Host "[Phase4B-A] Surface accounting: $hostSurface direct host-backed / $platformBound Phase4B platform-bound (17 total)."
Write-Host "[Phase4B-A] ABI metadata: 0 missing / 0 mismatched."
Write-Host "[Phase4B-A] Referenced fallbacks: 0."
Write-Host "[Phase4B-A] No retail code is executed by this gate."
Write-Host ""
Write-Host "[Phase4B-A] READY"
Write-Host "[Phase4B-A] XDK source: $output"
