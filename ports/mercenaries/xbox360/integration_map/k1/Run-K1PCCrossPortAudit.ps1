[CmdletBinding()]
param(
    [switch]$RefreshPinned
)
# Source-only: audit ALL retail function VAs against original translated
# corpus + actual r4 Xbox360 64 TrueTUs + pinned PC recomp patches.
# No XDK build, no XEX change, no PC executable launch.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$python = (Get-Command python -ErrorAction Stop).Source
$clone = Join-Path $PSScriptRoot "Prepare-K1PCReference.ps1"
$auditor = Join-Path $PSScriptRoot "Audit-K1PCCrossPortCoverage.py"
$retail = Join-Path $PSScriptRoot "Audit-K1PCRetailSource.py"
$planner = Join-Path $PSScriptRoot "Plan-K1PostTwoRootDirect.py"
$previous = Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$functions = Join-Path $root "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$gen = Join-Path $root "build\phase3n_final_abi_scale\runtime\gen"
$parentDir = Join-Path $root "build\phase6_integration_map\k1_next_icall_1f7620_two_roots_r4"
$parentMain = Join-Path $parentDir "main.cpp"
$manifest = Join-Path $parentDir "k1-next-icall-two-root-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$pc = Join-Path $root ".deps\mercenaries-pc-reference"
$output = Join-Path $root "build\phase6_integration_map\k1_pc_crossport_audit"
foreach($file in @($clone,$auditor,$retail,$planner,$previous,$base,$functions,$parentMain,$manifest)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-PC-AUDIT] Retail source/manifest missing: $file"
    }
}
foreach($dir in @($gen,$shards)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "[K1-PC-AUDIT] Generated source/64 TU directory missing: $dir"
    }
}
if($RefreshPinned){
    & $clone -Destination $pc -RefreshPinned
} else {
    & $clone -Destination $pc
}
if(-not $?) {throw "[K1-PC-AUDIT] Public PC reference clone/pin verification failed"}
& $python -m py_compile $auditor $retail
if($LASTEXITCODE -ne 0){throw "[K1-PC-AUDIT] Source syntax gate failed"}
& $python -u $auditor --self-test
if($LASTEXITCODE -ne 0){throw "[K1-PC-AUDIT] Source-only coverage fixtures failed"}
& $python -u $retail
if($LASTEXITCODE -ne 0){throw "[K1-PC-AUDIT] Developer patch/provenance synthetic fixture failed"}
$runArgs = @(
    "--pc-reference",$pc,
    "--pc-retail-module",$retail,
    "--base-module",$base,
    "--post-planner",$planner,
    "--previous-planner",$previous,
    "--functions",$functions,
    "--generated",$gen,
    "--parent",$parentMain,
    "--parent-manifest",$manifest,
    "--shards",$shards,
    "--outdir",$output
)
& $python -u $auditor @runArgs
if($LASTEXITCODE -ne 0){
    throw "[K1-PC-AUDIT] PC commit/inventory/XBE/64 TrueTU provenance mismatch. NO XDK"
}
$reportFile = Join-Path $output "pc-to-xbox360-retail-coverage.json"
$report = Get-Content -LiteralPath $reportFile -Raw -Encoding UTF8 | ConvertFrom-Json
if($report.status -ne "K1_PC_XBOX360_GLOBAL_ORIGINAL_FUNCTION_AND_PATCH_AUDIT_NO_XDK" -or
    $report.safe_to_build_from_report_alone -ne $false -or
    $report.xdk_invoked -ne $false -or
    $report.any_xex_modified -ne $false -or
    $report.provenance.pc_exact_commit_sha -ne "f513ae4e041401b7b032410016940971488d523b" -or
    [int]$report.coverage.compiled_original_functions_in_r4 -le 10000 -or
    [int]$report.coverage.pc_reference_patch_inventory_transformations -le 800){
    throw "[K1-PC-AUDIT] Cross-port whole-function coverage source contract violated"
}
Write-Host "[K1-PC-AUDIT] =========================================="
Write-Host "[K1-PC-AUDIT] FULL RETAIL VA COVERAGE / STATIC GRAPH / PC PATCH CENSUS PASS"
Write-Host ("[K1-PC-AUDIT] Original={0} generated={1} Xbox compiled={2} missing={3}" -f $report.coverage.retail_original_x86_inventory,$report.coverage.original_generated_C_functions,$report.coverage.compiled_original_functions_in_r4,$report.coverage.original_generated_C_missing_from_r4_binary)
Write-Host "[K1-PC-AUDIT] Read-only JSON/CSVs in $output"
Write-Host "[K1-PC-AUDIT] NO XDK OR XEX MODIFIED"
