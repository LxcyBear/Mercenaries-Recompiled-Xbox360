[CmdletBinding()]
param([int]$MaxCandidates=192)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$k1s=Join-Path $repo "build\phase6_integration_map\k1s_halgetvector44_saved_esi"
$shards=Join-Path $k1s "translated_shards"
$manifest=Join-Path $k1s "k1s-halgetvector44-saved-esi-manifest.json"
$main=Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$generatedRoot=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$functions=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$base=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$p5bb=Join-Path $repo "ports\mercenaries\xbox360\phase5_subsystem_bringup\emit_phase5bb_frontier22dda4.py"
$audit=Join-Path $PSScriptRoot "Audit-PixelBatchClosure.py"
$test=Join-Path $PSScriptRoot "Test-PixelBatchClosure.py"
$outdir=Join-Path $repo "build\phase6_integration_map\pixel_batch"
$report=Join-Path $outdir "pixel_batch_closure.json"
$summary=Join-Path $outdir "pixel_batch_summary.txt"

foreach($input in @($manifest,$main,$functions,$base,$p5bb,$audit,$test)){
    if(-not(Test-Path -LiteralPath $input -PathType Leaf)){
        throw "[PIXEL] Missing required local K1S or translated-source input: $input"
    }
}
foreach($folder in @($shards,$generatedRoot)){
    if(-not(Test-Path -LiteralPath $folder -PathType Container)){
        throw "[PIXEL] Missing generated translation folder: $folder"
    }
}
$py=(Get-Command python -ErrorAction Stop).Source
Write-Host "[PIXEL] Check live-frontier selection logic (NO XDK)"
& $py -u $test
if($LASTEXITCODE -ne 0){throw "[PIXEL] Static synthetic tests failed"}

New-Item -ItemType Directory -Force -Path $outdir | Out-Null
Write-Host "[PIXEL] Scan K1S 64-TU baseline and original DSOUND/D3D/present source..."
$auditArgs=@("--shards",$shards,"--manifest",$manifest,"--main",$main,
    "--generated-root",$generatedRoot,"--functions",$functions,
    "--base-emitter",$base,"--phase5bb-emitter",$p5bb,
    "--max-candidates",$MaxCandidates,"--out",$report)
& $py -u $audit @auditArgs
if($LASTEXITCODE -ne 0){throw "[PIXEL] Offline source closure audit failed"}

$data=Get-Content -LiteralPath $report -Raw -Encoding UTF8 | ConvertFrom-Json
if($data.marker -ne "PIXEL-BATCH-ROOTED-CLOSURE-20261030" -or
   $data.intent -ne "AUTHENTIC_GUEST_DISPLAY_CALL_ONLY" -or
   $data.status -ne "OFFLINE_SOURCE_AUDIT_NOT_BUILD_READY" -or
   $data.hardware_seed.hard_fences_relaxed -ne $false -or
   [int]$data.verified_baseline.shards -ne 64 -or
   $data.verified_baseline.marker -ne "K1S-HALGETVECTOR44-SAVED-ESI-20261030" -or
   $null -eq $data.frontier -or
   $data.frontier.va -ne "0x002A3A5A"){
    throw "[PIXEL] Report source/guest-display policy gate failed"
}

$lines=New-Object 'System.Collections.Generic.List[string]'
$lines.Add("PIXEL BATCH: REAL GUEST FRAME TARGET")
$lines.Add("K1S Xbox: ESI stack repaired; DIRECT_FRONTIER 002A3A5A at 27031807 ticks")
$lines.Add("Xenos ready, guest display_calls=0, framebuffer=00000000")
$lines.Add(("Frontier classification: {0}" -f $data.frontier.classification))
$lines.Add(("Frontier source status: {0}" -f $data.frontier.status))
if($data.frontier.containing_function){
    $lines.Add(("Enclosing source function: {0}" -f $data.frontier.containing_function.name))
    $lines.Add(("Mid-function original label: {0}" -f $data.frontier.containing_function.label_present))
}
if($data.frontier.unknown_helper_symbols){
    $lines.Add(("Unresolved support: {0}" -f (($data.frontier.unknown_helper_symbols) -join ", ")))
}
$lines.Add(("Rooted batch: {0} candidates; {1} exact source; {2} lexical-clean; {3} need review" -f $data.selected_candidate_count,$data.exact_source_candidate_count,$data.lexical_support_clean_count,$data.needs_source_or_support_count))
foreach($root in @($data.roots.PSObject.Properties)){
    $v=$root.Value
    $lines.Add(("Root {0}: nodes={1}, packed={2}, generated={3}, no-body={4}" -f $root.Name,$v.nodes_scanned,$v.already_packed,$v.exact_generated,$v.missing_generated))
}
$lines.Add("")
$lines.Add("TOP LIVE AND GRAPHICS PRIORITIES (source-only; not a compile claim):")
foreach($row in @($data.candidate_order | Select-Object -First 48)){
    $lines.Add(("{0} depth={1} roots={2} class={3} support={4}" -f $row.va,$row.min_depth,($row.root_reachability -join ","),$row.classification,$row.status))
}
$lines.Add("")
$lines.Add("NO XDK build. Preserve every unknown VP/MMIO hard fence.")
$lines.Add("Do NOT increment display_calls except through real guest display/presentation.")
$lines | Set-Content -LiteralPath $summary -Encoding UTF8
Write-Host ""
Write-Host "[PIXEL] AUDIT COMPLETE. First findings:"
Get-Content -LiteralPath $summary -TotalCount 11
Write-Host ""
Write-Host "[PIXEL] SUMMARY: $summary"
Write-Host "[PIXEL] COMPLETE PLAN: $report"
Write-Host "[PIXEL] NO XDK build or translated-source mutation performed"
