[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$phase4aJson = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"
$source = Join-Path $phaseRoot "main.cpp"
$buildRoot = Join-Path $repoRoot "build\phase4b_native_memory_protection"
$output = Join-Path $buildRoot "main.cpp"

if (-not (Test-Path -LiteralPath $phase4aJson -PathType Leaf)) {
    throw "Phase 4B-B2 report not found. Run Verify-Phase4B-B2.ps1 first."
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
    host_surface_flagged = 2
    platform_surface_bound = 15
    fallback_referenced_imports = 0
    fallback_static_refs = 0
}

foreach ($name in $expected.Keys) {
    if ([int]$c.$name -ne [int]$expected[$name]) {
        throw "Phase 4B-C baseline changed: $name expected $($expected[$name]), got $($c.$name)."
    }
}

if (-not (Test-Path -LiteralPath $source -PathType Leaf)) {
    throw "Phase 4B-C source missing: $source"
}

New-Item -ItemType Directory -Force -Path $buildRoot | Out-Null
Copy-Item -LiteralPath $source -Destination $output -Force

Write-Host "[Phase4B-C] GUEST MEMORY/PROTECTION HARDWARE GATE"
Write-Host "[Phase4B-C] Baseline verified: 111 imports / 2 direct host-backed / 15 platform-bound."
Write-Host "[Phase4B-C] ABI metadata: 0 missing / 0 mismatched."
Write-Host "[Phase4B-C] Referenced fallbacks: 0."
Write-Host "[Phase4B-C] No retail code is executed by this gate."
Write-Host ""
Write-Host "[Phase4B-C] READY"
Write-Host "[Phase4B-C] XDK source: $output"
