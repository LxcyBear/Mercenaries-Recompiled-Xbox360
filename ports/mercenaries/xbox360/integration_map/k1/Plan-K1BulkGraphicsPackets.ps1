[CmdletBinding()]
param()
# Use the successful r4 PC/global original function CSV map. Source ONLY.
# Defer any r6 stage/build until r5 XDK and Xbox hardware are proved.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$py=(Get-Command python -ErrorAction Stop).Source
$planner=Join-Path $PSScriptRoot "Plan-K1BulkGraphicsPackets.py"
$pcRetail=Join-Path $PSScriptRoot "Audit-K1PCRetailSource.py"
$pc=Join-Path $root ".deps\mercenaries-pc-reference"
$map=Join-Path $root "build\phase6_integration_map\k1_pc_crossport_audit"
$coverage=Join-Path $map "pc-to-xbox360-retail-coverage.json"
$csv=Join-Path $map "original-retail-va-coverage.csv"
$parent=Join-Path $root "build\phase6_integration_map\k1_next_icall_1f7620_two_roots_r4"
$main=Join-Path $parent "main.cpp"
$manifest=Join-Path $parent "k1-next-icall-two-root-manifest.json"
$shards=Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$previous=Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$base=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$bb=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$functions=Join-Path $root "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$generated=Join-Path $root "build\phase3n_final_abi_scale\runtime\gen"
$output=Join-Path $map "k1-original-404-bounded-source-clean-packets.json"
foreach($file in @($planner,$pcRetail,$coverage,$csv,$main,$manifest,$previous,$base,$bb,$functions)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){throw "[K1-BULK] Source evidence absent: $file"}
}
foreach($dir in @($pc,$shards,$generated)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){throw "[K1-BULK] Original source directory absent: $dir"}
}
& $py -m py_compile $planner
if($LASTEXITCODE -ne 0){throw "[K1-BULK] Syntax fail; no build"}
& $py -u $planner --self-test
if($LASTEXITCODE -ne 0){throw "[K1-BULK] Original C packet self-test fail; no build"}
$call=@(
    "--pc-retail-module",$pcRetail,
    "--pc-reference",$pc,
    "--coverage",$coverage,
    "--main",$main,
    "--manifest",$manifest,
    "--shards",$shards,
    "--previous",$previous,
    "--base",$base,
    "--bb",$bb,
    "--functions",$functions,
    "--generated",$generated,
    "--map-csv",$csv,
    "--output",$output
)
& $py -u $planner @call
if($LASTEXITCODE -ne 0){throw "[K1-BULK] Original graph/symbol/provenance failed. No XDK."}
$result=Get-Content -LiteralPath $output -Raw -Encoding UTF8 | ConvertFrom-Json
if($result.status -ne "K1_GLOBAL_MISSING_ORIGINAL_SOURCE_BATCH_PACKETS_NO_XDK" -or
    $result.safe_to_build_without_xdk_compiler_and_original_xbe_abi_checks -ne $false -or
    $result.safe_to_deploy_unverified_xex -ne $false -or
    $result.original_64_true_tus_modified -ne $false -or
    $result.xdk_invoked -ne $false -or
    $result.pinned_pc_commit -ne "f513ae4e041401b7b032410016940971488d523b" -or
    $result.missing_original_functions -ne 404){
    throw "[K1-BULK] Original 404/64 TrueTU/PC source audit contract changed"
}
Write-Host "[K1-BULK] Source-only 404 original functions packet plan PASS"
Write-Host ("[K1-BULK] Support-clean candidates selected={0}, block analyses={1}" -f $result.source_clean_eligible_count, $result.blocked_total)
Write-Host "[K1-BULK] NO XDK. NO XEX. r5 hardware parent unchanged."
Write-Host "[K1-BULK] Plan: $output"
