[CmdletBinding()]
param()
# PS5.1 / retail original game-corpus source-only ICALL_SAFE audit.
# This NEVER invokes VS/XDK, mutates derived TrueTUs or writes an XEX.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root = [IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$pythonExe = (Get-Command python -ErrorAction Stop).Source
$scriptPath = Join-Path $PSScriptRoot "Plan-K1NextICallBatch.py"
$base = Join-Path $root "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$original = Join-Path $root "build\phase3n_final_abi_scale"
$functions = Join-Path $original "analysis\disasm\functions.json"
$generated = Join-Path $original "runtime\gen"
$parentDir = Join-Path $root "build\phase6_integration_map\k1_d3d_six_cases_r3"
$parentMain = Join-Path $parentDir "main.cpp"
$parentManifest = Join-Path $parentDir "k1-d3d-six-cases-manifest.json"
$shards = Join-Path $parentDir "translated_shards"
$output = Join-Path $parentDir "k1-next-icall-1f7620-source-only-plan.json"
foreach($path in @($scriptPath,$base,$functions,$parentMain,$parentManifest)){
    if(-not(Test-Path -LiteralPath $path -PathType Leaf)){
        throw "[K1-NEXT] Missing exact original/generated proof: $path"
    }
}
foreach($path in @($generated,$shards)){
    if(-not(Test-Path -LiteralPath $path -PathType Container)){
        throw "[K1-NEXT] Missing exact original/generated directory: $path"
    }
}
& $pythonExe -m py_compile $scriptPath
if($LASTEXITCODE -ne 0){ throw "[K1-NEXT] Python source syntax gate failed" }
& $pythonExe -u $scriptPath --self-test
if($LASTEXITCODE -ne 0){ throw "[K1-NEXT] No-XDK source graph fixtures failed" }
$argsList = @("--base-module",$base,"--functions",$functions,
    "--generated-root",$generated,"--parent",$parentMain,
    "--manifest",$parentManifest,"--shards",$shards,"--output",$output)
& $pythonExe -u $scriptPath @argsList
if($LASTEXITCODE -ne 0){
    throw "[K1-NEXT] Original retail ICALL_SAFE source-provenance gate failed; no XDK build"
}
$report = Get-Content -LiteralPath $output -Raw -Encoding UTF8 | ConvertFrom-Json
if($report.status -ne "K1_NEXT_ICALL_1F7620_SOURCE_ONLY_NO_XDK" -or
    $report.safe_to_build -ne $false -or
    $report.safe_to_insert_unknown_function -ne $false -or
    [int]$report.original_true_tu_count -ne 64 -or
    $report.hardware_witness.target -ne "0x001F7620" -or
    $report.hardware_witness.kind -ne "ICALL_SAFE" -or
    [int]$report.hardware_witness.net_more_ticks -ne 71407){
    throw "[K1-NEXT] Source-only safety/retail hardware witness contract failed"
}
Write-Host "[K1-NEXT] ========================================="
Write-Host "[K1-NEXT] SOURCE BATCH AUDIT COMPLETE"
Write-Host ("[K1-NEXT] class={0}; compiled owner={1}; lookup present={2}" -f
  $report.target.target_classification.kind,
  (@($report.target.compiled_owner_files) -join ","),
  $report.target.main_dispatch_lookup_entry_present)
Write-Host ("[K1-NEXT] Original missing .text candidates={0}; no-XDK decision={1}" -f
  @($report.bounded_missing_source_candidates).Count, $report.safe_to_build)
Write-Host "[K1-NEXT] No Visual Studio, no XEX changes, no Xbox test."
Write-Host "[K1-NEXT] Report: $output"
