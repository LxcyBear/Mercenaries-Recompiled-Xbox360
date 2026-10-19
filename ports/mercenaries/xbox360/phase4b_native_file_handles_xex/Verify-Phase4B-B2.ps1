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

Write-Host "[Phase4B-B2] Re-running exact retail guest-kernel surface audit..."
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
    host_surface_flagged = 2
    platform_surface_bound = 15
    fallback_referenced_imports = 0
    fallback_static_refs = 0
}

foreach ($name in $expected.Keys) {
    if ([int]$c.$name -ne [int]$expected[$name]) {
        throw "Phase 4B-B2 surface mismatch: $name expected $($expected[$name]), got $($c.$name)."
    }
}

Write-Host "[Phase4B-B2] Surface split PASS: 2 direct host-backed / 15 platform-bound."

Write-Host "[Phase4B-B2] Running timing/deadline regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_guest_wait_deadline_native.py")
if ($LASTEXITCODE -ne 0) {
    throw "timing/deadline regression failed"
}

Write-Host "[Phase4B-B2] Running guest kernel ABI regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_kernel_bridge_abi_metadata.py")
if ($LASTEXITCODE -ne 0) {
    throw "kernel ABI regression failed"
}

Write-Host "[Phase4B-B2] Running time/sync platform regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_phase4b_time_sync_platform_boundary.py")
if ($LASTEXITCODE -ne 0) {
    throw "time/sync platform regression failed"
}

Write-Host "[Phase4B-B2] Running file/handle platform regression..."
& $python (Join-Path $repoRoot "tools\recomp\test_phase4b_file_platform_boundary.py")
if ($LASTEXITCODE -ne 0) {
    throw "file/handle platform regression failed"
}

Write-Host ""
Write-Host "[Phase4B-B2] PASS"
Write-Host "[Phase4B-B2] Nine file/handle import paths are platform-bound."
Write-Host "[Phase4B-B2] Remaining direct semantic host surface: 2."
