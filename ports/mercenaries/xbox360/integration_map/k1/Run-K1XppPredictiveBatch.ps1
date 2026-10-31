[CmdletBinding()]
param(
    [switch]$SkipExistingPreflight
)
# Windows PowerShell 5.1; predict the next safe input batch from independent
# TGP482/XboxXBERecomp + xboxrecomp + retail generated source.
# NOT AN XDK BUILD, no Xbox execution, no guest source exported.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$python=(Get-Command python -ErrorAction Stop).Source
$planner=Join-Path $PSScriptRoot "Plan-XppPredictiveBatch.py"
$previous=Join-Path $PSScriptRoot "Advance-XppD54AC.ps1"
$stage=Join-Path $repo "build\phase6_integration_map\xpp_d54ac_batch"
$shards=Join-Path $stage "translated_shards"
$main=Join-Path $stage "main.cpp"
$parent=Join-Path $stage "xpp-d54ac-batch-manifest.json"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$ranges=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$recon=Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon\Merc360_xboxrecomp_static_recon.zip"
$tgp=Join-Path $env:LOCALAPPDATA "Merc360-TGP482-XBERecomp\private\mercenaries.toml"
$outDir=Join-Path $repo "build\phase6_integration_map\xpp_predictive_batch"
$report=Join-Path $outDir "xpp_input_candidate_report.txt"
$json=Join-Path $outDir "xpp_input_candidate_manifest.json"

Write-Host "[XPP-PREDICT] ====================================================="
Write-Host "[XPP-PREDICT] MULTI-RECOMPILER PREDICTIVE XPP INPUT FRONTIERS"
Write-Host "[XPP-PREDICT] ====================================================="
Write-Host "[XPP-PREDICT] Scope: original XPP input wrappers, source/ABI gates, caller map"
Write-Host "[XPP-PREDICT] NO XDK, NO Xbox test, NO raw game code leaves your PC"
if(-not $SkipExistingPreflight){
    & powershell.exe -NoProfile -ExecutionPolicy Bypass -File $previous -PreflightOnly
    if($LASTEXITCODE -ne 0){throw "[XPP-PREDICT] Proven D54AC preflight prerequisite failed"}
}
foreach($file in @($planner,$main,$parent,$emitter,$ranges,$recon)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[XPP-PREDICT] Missing local original/cache prerequisite: $file"
    }
}
foreach($dir in @($generated,$shards)){
    if(-not(Test-Path -LiteralPath $dir -PathType Container)){
        throw "[XPP-PREDICT] Missing local original/64-TU stage: $dir"
    }
}
& $python -m py_compile $planner
if($LASTEXITCODE -ne 0){throw "[XPP-PREDICT] Python syntax gate failed"}
& $python -u $planner --self-test
if($LASTEXITCODE -ne 0){throw "[XPP-PREDICT] Planner selftest failed"}
$argsList=@(
    "--parent-manifest",$parent,
    "--parent-main",$main,
    "--shards",$shards,
    "--recon",$recon,
    "--emitter",$emitter,
    "--ranges",$ranges,
    "--generated",$generated,
    "--report",$report,
    "--json",$json
)
if(Test-Path -LiteralPath $tgp -PathType Leaf){
    $argsList+=@("--tgp-config",$tgp)
}else{
    Write-Host "[XPP-PREDICT] Optional TGP482 scan not present; original/source crosswalk still active"
}
& $python -u $planner @argsList
if($LASTEXITCODE -ne 0){throw "[XPP-PREDICT] Source crosswalk rejected an unproven function"}
if(-not(Test-Path -LiteralPath $report -PathType Leaf) -or
   -not(Test-Path -LiteralPath $json -PathType Leaf)){
    throw "[XPP-PREDICT] Report missing"
}
Write-Host "[XPP-PREDICT] PASS. No build or deployment."
Write-Host "[XPP-PREDICT] SHARE METADATA REPORT: $report"
Write-Host "[XPP-PREDICT] Candidate manifest: $json"
Write-Host "[XPP-PREDICT] NEXT: verify exact Close/SetState and any other direct-site wrappers"
Write-Host "[XPP-PREDICT] Then pack all individually source-closed entries into ONE incremental XDK build."
