[CmdletBinding()]
param()

$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$phaseRoot = [System.IO.Path]::GetFullPath($PSScriptRoot)
$repoRoot = [System.IO.Path]::GetFullPath((Join-Path $phaseRoot "..\..\..\.."))
$python = Join-Path $repoRoot ".venv\Scripts\python.exe"
$phase4a = Join-Path $repoRoot "ports\mercenaries\xbox360\phase4a_kernel_surface_audit\Prepare-Phase4A.ps1"
$reportPath = Join-Path $repoRoot "build\phase4a_kernel_surface\phase4a-kernel-surface.json"

if (-not (Test-Path -LiteralPath $python -PathType Leaf)) {
    throw "Python environment not found at $python."
}

Write-Host "[Phase4B-A2] Re-running exact retail guest-kernel surface audit..."
powershell -ExecutionPolicy Bypass -File $phase4a
if ($LASTEXITCODE -ne 0) {
    throw "Phase 4A audit failed with exit code $LASTEXITCODE."
}

$report = Get-Content -LiteralPath $reportPath -Raw | ConvertFrom-Json
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
        throw "Phase 4B-A2 surface mismatch: $name expected $($expected[$name]), got $($c.$name)."
    }
}

Write-Host "[Phase4B-A2] Surface split PASS: 11 direct host-backed / 6 platform-bound."
Write-Host "[Phase4B-A2] Running wait deadline regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_guest_wait_deadline_native.py")
if ($LASTEXITCODE -ne 0) { throw "wait deadline regression failed" }

Write-Host "[Phase4B-A2] Running guest kernel ABI regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_kernel_bridge_abi_metadata.py")
if ($LASTEXITCODE -ne 0) { throw "kernel ABI regression failed" }

Write-Host "[Phase4B-A2] Running platform-boundary regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_phase4b_time_sync_platform_boundary.py")
if ($LASTEXITCODE -ne 0) { throw "Phase 4B platform-boundary regression failed" }

Write-Host ""
Write-Host "[Phase4B-A2] PASS"
Write-Host "[Phase4B-A2] Six timing/synchronization import paths are platform-bound."
Write-Host "[Phase4B-A2] Remaining direct semantic host surface: 11."
