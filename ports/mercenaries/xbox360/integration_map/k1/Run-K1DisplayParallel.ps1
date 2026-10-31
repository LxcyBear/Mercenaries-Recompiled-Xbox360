[CmdletBinding()]
param(
    [string]$Workspace=(Join-Path $env:LOCALAPPDATA "Merc360-Xboxrecomp-Recon")
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
# Offline only. Do not rerun disassembler, deploy XEX, or patch guest display.
# ASCII-only to parse reliably in Windows PowerShell 5.1.
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$run=Join-Path $PSScriptRoot "Audit-K1DisplayParallel.py"
$root=[IO.Path]::GetFullPath($Workspace)
$recon=Join-Path $root "Merc360_xboxrecomp_static_recon.zip"
$xrefs=Join-Path $root "xboxrecomp\tools\disasm\output\xrefs.json"
$ranges=Join-Path $repo "build\phase3n_final_abi_scale\analysis\disasm\functions.json"
$generated=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen"
$emitter=Join-Path $repo "ports\mercenaries\xbox360\phase4c_native_startup\emit_phase4c_startup_slice.py"
$xpp=Join-Path $repo "build\phase6_integration_map\xpp_d5574_batch"
$shards=Join-Path $xpp "translated_shards"
$generatedHostMain=Join-Path $xpp "main.cpp"
$manifest=Join-Path $xpp "xpp-d5574-batch-manifest.json"
$outDir=Join-Path $repo "build\phase6_integration_map\post_xpp_display_recon"
$out=Join-Path $outDir "display_parallel_audit.txt"
$excerpts=Join-Path $outDir "xpp_original_source_LOCAL_ONLY.txt"
foreach($f in @($run,$recon,$xrefs,$ranges,$emitter,$generatedHostMain,$manifest)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[DISPLAY-RECON] Missing cached or generated file: $f"
    }
}
foreach($d in @($generated,$shards)){
    if(-not(Test-Path -LiteralPath $d -PathType Container)){
        throw "[DISPLAY-RECON] Missing generated original source: $d"
    }
}
$meta=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($meta.marker -ne "XPP-D5574-DIRECT-CLOSURE-20261030" -or
   $meta.status -ne "SOURCE_CLOSED_STAGED_NO_XDK" -or
   $meta.native_xinput_init -ne "XINPUTGETSTATE_4PORTS_REAL_HARDWARE" -or
   $meta.guest_display_calls_injected -ne $false -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.hard_fences -ne "UNCHANGED"){
    throw "[DISPLAY-RECON] Working XPP D5574 provenance/hard fences changed"
}
$py=(Get-Command python -ErrorAction Stop).Source
Write-Host "[DISPLAY-RECON] OFFLINE: new XPP D559B frontier, 7 graphics roots, AvSetDisplayMode"
Write-Host "[DISPLAY-RECON] Xbox proof: D5574 passed, controller mask=1, D559B at 27,107,590 ticks"
& $py -m py_compile $run
if($LASTEXITCODE -ne 0){throw "[DISPLAY-RECON] Python syntax failed"}
& $py -u $run --self-test
if($LASTEXITCODE -ne 0){throw "[DISPLAY-RECON] Offline synthetic check failed"}
New-Item -ItemType Directory -Path $outDir -Force | Out-Null
$params=@("--recon",$recon,
    "--xrefs",$xrefs,
    "--ranges",$ranges,
    "--generated",$generated,
    "--emitter",$emitter,
    "--shards",$shards,
    "--host",$generatedHostMain,
    "--out",$out,
    "--excerpts",$excerpts)
& $py -u $run @params
if($LASTEXITCODE -ne 0){throw "[DISPLAY-RECON] Cached source/xref audit failed - NO XDK"}
Write-Host "[DISPLAY-RECON] REPORT FIRST 80 LINES:"
Get-Content -LiteralPath $out -Encoding UTF8 -TotalCount 80
Write-Host "[DISPLAY-RECON] Upload summary: $out"
Write-Host "[DISPLAY-RECON] Upload local XPP source only for ABI review: $excerpts"
Write-Host "[DISPLAY-RECON] DONE. No XDK build, no source patch, no fabricated display calls."
