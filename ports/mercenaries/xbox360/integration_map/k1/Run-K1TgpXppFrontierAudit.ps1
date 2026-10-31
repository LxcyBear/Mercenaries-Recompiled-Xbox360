[CmdletBinding()]
param(
    [string]$Workspace=(Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon"),
    [string]$StageShards=""
)
# Offline source audit only. Windows PowerShell 5.1 ASCII source.
# NO XDK build, XEX deployment, source patching or original game data in git.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$script=Join-Path $PSScriptRoot "Audit-K1TgpXppFrontier.py"
$recon=Join-Path $Workspace "Merc360_xboxrecomp_static_recon.zip"
$ranges=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$defaultStage=Join-Path $repo "build\phase6_integration_map\pixel_a3a5a_batch\translated_shards"
$reportDir=Join-Path $repo "build\phase6_integration_map\tgp482_d52d4_source_audit"
$out=Join-Path $reportDir "d52d4_source_abi_metadata.txt"
$excerpts=Join-Path $reportDir "d52d4_original_source_LOCAL_ONLY.txt"
$py=(Get-Command python -ErrorAction Stop).Source
foreach($file in @($script,$recon,$ranges,$emitter)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1-XPP] Prerequisite missing: $file"
    }
}
if(-not(Test-Path -LiteralPath $generated -PathType Container)){
    throw "[K1-XPP] Original user-local generated source not found: $generated"
}
& $py -u $script --self-test
if($LASTEXITCODE -ne 0){throw "[K1-XPP] Source-only self-test failed"}
$arguments=@(
    "--recon",$recon,
    "--ranges",$ranges,
    "--generated",$generated,
    "--emitter",$emitter,
    "--out",$out,
    "--excerpts",$excerpts
)
if(-not [string]::IsNullOrWhiteSpace($StageShards)){
    if(-not(Test-Path -LiteralPath $StageShards -PathType Container)){
        throw "[K1-XPP] Explicit TrueTU folder absent: $StageShards"
    }
    $arguments+=@("--stage-shards",[IO.Path]::GetFullPath($StageShards))
}else{
    $arguments+=@("--stage-shards",$defaultStage)
}
Write-Host "[K1-XPP] ORIGINAL XPP D52D4 ABI + real Swap references. NO XDK, NO Xbox run."
& $py -u $script @arguments
if($LASTEXITCODE -ne 0){throw "[K1-XPP] Original XPP source audit failed"}
if(-not(Test-Path -LiteralPath $out -PathType Leaf)){
    throw "[K1-XPP] Metadata file not written"
}
Write-Host "[K1-XPP] PASS: local ABI evidence generated. No guest/source/XEX mutation."
Write-Host "[K1-XPP] SHARE THIS METADATA REPORT: $out"
Write-Host "[K1-XPP] ORIGINAL GUEST CODE stays LOCAL ONLY: $excerpts"
