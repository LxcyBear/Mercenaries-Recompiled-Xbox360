[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$phase4aJson = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"
$source = Join-Path $phaseRoot "main.cpp"
$buildRoot = Join-Path $repoRoot "build\phase4b_native_file_handles"
$output = Join-Path $buildRoot "main.cpp"

if (-not (Test-Path -LiteralPath $phase4aJson -PathType Leaf)) {
    throw "Phase 4A/A2 report not found. Run Verify-Phase4B-A2.ps1 first."
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
    host_surface_flagged = 11
    platform_surface_bound = 6
    fallback_referenced_imports = 0
    fallback_static_refs = 0
}

foreach ($name in $expected.Keys) {
    if ([int]$c.$name -ne [int]$expected[$name]) {
        throw "Phase 4B-B baseline changed: $name expected $($expected[$name]), got $($c.$name)."
    }
}

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Phase 4B-B source missing: $source"
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
Copy-Item -LiteralPath $source -Destination $output -Force

Write-Host "[Phase4B-B] NATIVE XENON FILE/HANDLE HARDWARE GATE"
Write-Host "[Phase4B-B] Baseline verified: 111 imports / 11 direct host-backed / 6 platform-bound."
Write-Host "[Phase4B-B] ABI metadata: 0 missing / 0 mismatched."
Write-Host "[Phase4B-B] Referenced fallbacks: 0."
Write-Host "[Phase4B-B] No retail code is executed by this gate."
Write-Host ""
Write-Host "[Phase4B-B] READY"
Write-Host "[Phase4B-B] XDK source: $output"
