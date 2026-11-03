[CmdletBinding()]
param()
# r6 source-only derived main from the r5 ORIGINAL retail-restored source.
# No XDK stage, no XEX copy, no Xbox launch; hardware r5 first.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$py=(Get-Command python -ErrorAction Stop).Source
$stage=Join-Path $PSScriptRoot "Stage-K1BulkOriginalPackets.py"
$planner=Join-Path $PSScriptRoot "Plan-K1BulkGraphicsPackets.ps1"
$map=Join-Path $root "build\phase6_integration_map\k1_pc_crossport_audit"
$plan=Join-Path $map "k1-original-404-bounded-source-clean-packets.json"
$r5=Join-Path $root "build\phase6_integration_map\k1_direct_2228c0_r5"
$parent=Join-Path $r5 "main.cpp"
$parentMeta=Join-Path $r5 "k1-direct-2228c0-original-manifest.json"
$shards=Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$base=Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$bb=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$bc=Join-Path $root "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bc_broad_sweep.py"
$previous=Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$packer=Join-Path $PSScriptRoot "Stage-K1NextICallBatch.py"
$functions=Join-Path $root "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$generated=Join-Path $root "build\phase3n_final_abi_scale\runtime\gen"
$outDir=Join-Path $root "build\phase6_integration_map\k1_bulk_support_clean_r6"
$out=Join-Path $outDir "main.cpp"
$manifest=Join-Path $outDir "k1-bulk-source-only-r6-manifest.json"
foreach($file in @($stage,$planner,$plan,$parent,$parentMeta,$base,$bb,$bc,$previous,$packer,$functions)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-BULK-R6] Required actual r5 source/retail map absent: $file"
    }
}
foreach($dir in @($shards,$generated)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "[K1-BULK-R6] Original translated source/64 TrueTU corpus missing: $dir"
    }
}
& $py -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1-BULK-R6] Script syntax failure; NO XDK"}
& $py -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1-BULK-R6] Original r5 preservation fixture failure; NO XDK"}
$argsList=@(
    "--parent",$parent,"--parent-manifest",$parentMeta,
    "--shards",$shards,"--packet-plan",$plan,
    "--base",$base,"--bb",$bb,"--bc",$bc,
    "--previous",$previous,"--packer",$packer,
    "--functions",$functions,"--generated",$generated,
    "--out",$out,"--manifest",$manifest
)
& $py -u $stage @argsList
if($LASTEXITCODE -ne 0){throw "[K1-BULK-R6] Source packet not support clean; no XDK"}
$doc=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
$hash=(Get-FileHash -LiteralPath $out -Algorithm SHA256).Hash.ToLowerInvariant()
if($doc.status -ne "K1_ORIGINAL_BULK_GRAPHICS_R6_SOURCE_ONLY_XDK_BLOCKED" -or
    $doc.r6_derived_main_sha256 -ne $hash -or
    $doc.r4_hardware_proven_source_fences_preserved -ne $true -or
    $doc.original_r5_retail_branch_preserved -ne $true -or
    [int]$doc.unmodified_original_TrueTU_count -ne 64 -or
    [int]$doc.new_member_count -lt 1 -or
    $doc.zero_dummy_host_helpers -ne $true -or
    $doc.unproven_indirect_targets_remain_fenced -ne $true -or
    $doc.source_only -ne $true -or
    $doc.safe_to_deploy -ne $false -or
    $doc.r5_hardware_verified -ne $false -or
    $doc.r6_xdk_verified -ne $false){
    throw "[K1-BULK-R6] Retail source-only/64 TrueTU/guest safety contract changed"
}
Write-Host "[K1-BULK-R6] ORIGINAL RETAIL SOURCE-ONLY PACK STAGE PASS"
Write-Host ("[K1-BULK-R6] New original source members={0}" -f $doc.new_member_count)
Write-Host "[K1-BULK-R6] r5 parent unchanged, 64 TrueTUs untouched"
Write-Host "[K1-BULK-R6] NO XDK OR XEX. DO NOT DEPLOY WITHOUT NEW HARDWARE PROOF."
Write-Host "[K1-BULK-R6] Manifest: $manifest"
