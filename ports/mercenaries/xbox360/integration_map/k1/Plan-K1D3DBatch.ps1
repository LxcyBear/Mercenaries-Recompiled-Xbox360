[CmdletBinding()]
param()
# Windows PowerShell 5.1. Zero XDK builds by design. Determine whether
# 0029655D is an original function entry or an interior translated label;
# batch source-authentic D3D/XGRPH functions in one report, not one XEX per VA.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest

$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$planner = Join-Path $PSScriptRoot "Plan-K1D3DBatch.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$generated = Join-Path $original "runtime\gen"
$functions = Join-Path $original "analysis\disasm\functions.json"
$cache = Join-Path $original "analysis\disasm\.disasm_cache.json"
$parentRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_direct_289e20_r2"
$parent = Join-Path $parentRoot "main.cpp"
$parentManifest = Join-Path $parentRoot "k1-d3d-direct-289e20-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_second_create_r2\translated_shards"
$outRoot = Join-Path $root "build\phase6_integration_map\k1_d3d_predictive_batch"
$out = Join-Path $outRoot "k1-d3d-itail-predictive-source-plan.json"

foreach($p in @($planner,$base,$functions,$cache,$parent,$parentManifest)) {
    if(-not(Test-Path -LiteralPath $p -PathType Leaf)) {
        throw "[K1D3D-BATCH] Missing exact original input: $p"
    }
}
if(-not(Test-Path -LiteralPath $generated -PathType Container) -or
   -not(Test-Path -LiteralPath $shards -PathType Container)) {
    throw "[K1D3D-BATCH] Missing original local translated source corpus or 64 TrueTUs"
}

$prior = Get-Content -LiteralPath $parentManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$actualHash = (Get-FileHash -LiteralPath $parent -Algorithm SHA256).Hash.ToLowerInvariant()
if($prior.status -ne "K1_D3D_DIRECT_289E20_SOURCE_ONLY_NO_XDK" -or
   $prior.new_main_sha256 -ne $actualHash -or
   $prior.original_xbe_sha256 -ne "AA08EA21D952AC35F49C02C7E2ED08AA25AD7535FBBBCCC95636775F37BE99D7" -or
   [int]$prior.original_true_tus -ne 64 -or
   [int]$prior.modified_true_tus -ne 0 -or
   $prior.native_xenos_reset_replaced -ne $false -or
   $prior.unknown_mmio_fences_changed -ne $false -or
   $prior.fake_guest_pixels -ne $false) {
    throw "[K1D3D-BATCH] Prior proven graphics stage/manifest changed; refusing plan"
}
Write-Host "[K1D3D-BATCH] R2 SOURCE CHAIN PASS: native Reset + 289E20 + hard fences preserved"

$python = (Get-Command python -ErrorAction Stop).Source
& $python -m py_compile $planner
if($LASTEXITCODE -ne 0) {
    throw "[K1D3D-BATCH] Python syntax invalid"
}
& $python -u $planner --self-test
if($LASTEXITCODE -ne 0) {
    throw "[K1D3D-BATCH] Predictive frontier source fixtures failed"
}
New-Item -ItemType Directory -Force -Path $outRoot | Out-Null
$argsList = @("--base-module", $base, "--functions", $functions,
    "--generated-root", $generated, "--parent", $parent,
    "--shards", $shards, "--output", $out)
& $python -u $planner @argsList
if($LASTEXITCODE -ne 0) {
    throw "[K1D3D-BATCH] Original-XBE identity or source audit failed; no build"
}

$report = Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json
if($report.status -ne "K1_D3D_BATCH_AUDIT_ONLY_NEVER_XDK" -or
   $report.hardware_witness.target -ne "0x0029655D" -or
   [int]$report.original_true_tus -ne 64 -or
   [int]$report.modified_true_tus -ne 0 -or
   $report.safe_to_build -ne $false) {
    throw "[K1D3D-BATCH] Unsafe or unexpected source plan manifest"
}
Write-Host ""
Write-Host "[K1D3D-BATCH] =================================================="
Write-Host "[K1D3D-BATCH] GRAPHICS SOURCE AUDIT DONE; NO XDK/XBOX RUN"
Write-Host ("[K1D3D-BATCH] ITAIL: {0} ({1}), owner={2}" -f $report.itail_analysis.address, $report.itail_analysis.classification, $report.itail_analysis.owner_va)
Write-Host ("[K1D3D-BATCH] Source-authentic batch candidates: {0}" -f [int]$report.batch_candidate_count)
Write-Host ("[K1D3D-BATCH] Next proof: {0}" -f $report.next_gate)
Write-Host "[K1D3D-BATCH] Report: $out"
Write-Host "[K1D3D-BATCH] =================================================="
Write-Host "[K1D3D-BATCH] Source only; original 64 TrueTUs and hardware-proven XEX preserved."
