[CmdletBinding()]
param()
# Retail source-only classification of next hardware DIRECT_FRONTIER 002228C0.
# Real Windows PowerShell 5.1. NO XDK, no new XEX, no parent overwrite.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$script = Join-Path $PSScriptRoot "Plan-K1PostTwoRootDirect.py"
$previous = Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$functions = Join-Path $original "analysis\disasm\functions.json"
$generated = Join-Path $original "runtime\gen"
$parentDir = Join-Path $root "build\phase6_integration_map\k1_next_icall_1f7620_two_roots_r4"
$parent = Join-Path $parentDir "main.cpp"
$parentManifest = Join-Path $parentDir "k1-next-icall-two-root-manifest.json"
$shards = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3\translated_shards"
$out = Join-Path $parentDir "k1-post-two-root-direct-2228c0-original-source-plan.json"
foreach($file in @($script,$previous,$base,$functions,$parent,$parentManifest)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-DIRECT-NEXT] Original-hardware-parent source missing: $file"
    }
}
foreach($folder in @($generated,$shards)){
    if(-not(Test-Path -LiteralPath $folder -PathType Container)){
        throw "[K1-DIRECT-NEXT] Original retail compiled corpus missing: $folder"
    }
}
& $pythonExe -m py_compile $script
if($LASTEXITCODE -ne 0){throw "[K1-DIRECT-NEXT] Python syntax failure; NO XDK"}
& $pythonExe -u $script --self-test
if($LASTEXITCODE -ne 0){throw "[K1-DIRECT-NEXT] Hardware-parent/TrueTU source fixture failed; NO XDK"}
$runArgs = @(
    "--base-module",$base,
    "--previous-planner",$previous,
    "--functions",$functions,
    "--generated",$generated,
    "--parent",$parent,
    "--parent-manifest",$parentManifest,
    "--shards",$shards,
    "--out",$out
)
& $pythonExe -u $script @runArgs
if($LASTEXITCODE -ne 0){
    throw "[K1-DIRECT-NEXT] Retail XBE/owner/compiled lookup proof failed. NO XDK"
}
$report = Get-Content -LiteralPath $out -Raw -Encoding UTF8 | ConvertFrom-Json
if($report.status -ne "K1_POST_TWO_ROOT_DIRECT_2228C0_ORIGINAL_SOURCE_ONLY" -or
    $report.safe_to_build -ne $false -or
    $report.safe_to_insert_function_at_unknown_va -ne $false -or
    $report.xdk_invoked -ne $false -or
    $report.original_64_true_tus_verified -ne $true -or
    [int]$report.hardware.ticks_advanced -ne 476 -or
    $report.hardware.new_boundary.kind -ne "DIRECT_FRONTIER" -or
    $report.hardware.new_boundary.target -ne "0x002228C0" -or
    $report.hardware.display_calls -ne 0){
    throw "[K1-DIRECT-NEXT] Original 002228C0 source-only hard-stop witness contract mismatch"
}
Write-Host "[K1-DIRECT-NEXT] ========================================="
Write-Host "[K1-DIRECT-NEXT] RETAIL SOURCE BATCH CLASSIFICATION PASS"
Write-Host ("[K1-DIRECT-NEXT] target_class={0} owner={1} lookup={2}" -f $report.target.original_classification.kind, $report.target.original_classification.owner, $report.target.in_main_pack_lookup)
Write-Host ("[K1-DIRECT-NEXT] missing original C candidates={0}, compiled original functions={1}" -f @($report.missing_source_candidates).Count, [int]$report.compiled_original_function_count)
Write-Host "[K1-DIRECT-NEXT] No XDK build, XEX change, or Xbox run."
Write-Host "[K1-DIRECT-NEXT] Report: $out"
