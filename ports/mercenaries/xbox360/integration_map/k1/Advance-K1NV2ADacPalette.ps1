[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. DEFAULT: guarded source preflight only.
# -Build: reuse native K1NT207 64 TrueTUs & XDK intermediates; main-only delta.
$ErrorActionPreference = "Stop"
Set-StrictMode -Version Latest
$root=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$k1nt=Join-Path $root "build\phase6_integration_map\k1_ntquerydirectory207_native"
$parent=Join-Path $root "build\phase6_integration_map\k1_nv2a_prmdio_write8"
$next=Join-Path $root "build\phase6_integration_map\k1_nv2a_dac_palette"
$parentMain=Join-Path $parent "main.cpp"
$parentManifest=Join-Path $parent "k1nv2a-prmdio-manifest.json"
$sourceProof=Join-Path $parent "focused-0028ED48.txt"
$shards=Join-Path $k1nt "translated_shards"
$header=Join-Path $shards "translated_runtime.h"
$main=Join-Path $next "main.cpp"
$manifest=Join-Path $next "k1dac-palette-manifest.json"
$stage=Join-Path $PSScriptRoot "Stage-K1NV2ADacPalette.py"
$quietStage=Join-Path $PSScriptRoot "Stage-K1DQQuietLogging.py"
$quietRoot=Join-Path $root "build\phase6_integration_map\k1_nv2a_dac_palette_quiet"
$quietMain=Join-Path $quietRoot "main.cpp"
$quietManifest=Join-Path $quietRoot "k1dq-quiet-manifest.json"
$builder=Join-Path $root "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envFile=Join-Path $root "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk=Join-Path $quietRoot "xdk"
$xex=Join-Path $xdk "Merc-K1NV2A-DAC-Palette-Quiet.xex"
$python=(Get-Command python -ErrorAction Stop).Source
foreach($f in @($parentMain,$parentManifest,$sourceProof,$header,$stage,$quietStage,$builder,$envFile)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){throw "[K1DAC] Missing proven parent/tool: $f"}
}
$meta=Get-Content -LiteralPath $parentManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($meta.marker -ne "P6K1NV2A-PRMDIO-WRITE8-20261103" -or
   $meta.status -ne "MAIN_ONLY_DIAGNOSTIC_STAGED_NO_XDK" -or
   $meta.new_main_sha256 -ne (Get-FileHash -LiteralPath $parentMain -Algorithm SHA256).Hash.ToLowerInvariant() -or
   [int]$meta.translated_tus_changed -ne 0 -or
   [int]$meta.runtime_headers_changed -ne 0 -or
   $meta.access_fences_changed -ne $false){
    throw "[K1DAC] Diagnostic parent provenance drift; no build"
}
$source=Get-Content -LiteralPath $sourceProof -Raw -Encoding UTF8
foreach($proof in @(
    "Focus guest block VA: 0028ED48",
    "MATCH 1: translated_055.cpp:21654",
    "GUEST_WRITE8(ecx + 0x6813C8, 0);",
    "0028ED54  mov byte ptr [ecx + 0x6813c8], 0",
    "0028ED77  mov byte ptr [ecx + 0x6813c9], dl",
    "0028ED7F  mov byte ptr [ecx + 0x6813c9], dl",
    "0028ED8C  mov byte ptr [ecx + 0x6813c9], dl"
)){
    if(-not $source.Contains($proof)){
        throw "[K1DAC] Missing exact translated/XBE source proof: $proof"
    }
}
$files=@(Get-ChildItem -LiteralPath $shards -Filter "translated_???.cpp" -File)
if($files.Count -ne 64){throw "[K1DAC] Expected 64 byte-exact inherited TrueTUs"}
if(-not (Test-Path -LiteralPath $header -PathType Leaf)){
    throw "[K1DAC] Missing inherited runtime header"
}
Write-Host "[K1DAC] ======================================================"
Write-Host "[K1DAC] REAL XBE D3D 0028ED54 DAC PALETTE INDEX/DATA"
Write-Host "[K1DAC] Hardware proved 00 -> FD6813C8; XBE proves RGB writes C9"
Write-Host "[K1DAC] Indexed 256-entry RGB shadow; no pixels or palette fabricated"
Write-Host "[K1DAC] Exact 2 MMIO 8-bit addresses ONLY; all others HARD FENCE"
Write-Host "[K1DAC] ======================================================"
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1DAC] Python source syntax failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1DAC] DAC model or source selftests failed"}
& $python -u $stage --parent $parentMain --out $main --manifest $manifest
if($LASTEXITCODE -ne 0){throw "[K1DAC] Main-only palette stage failed"}
$doc=Get-Content -LiteralPath $manifest -Raw -Encoding UTF8|ConvertFrom-Json
if($doc.marker -ne "P6K1NV2A-DAC-PALETTE-20261103" -or
   $doc.status -ne "NV2A_DAC_PALETTE_SOURCE_STAGED_NO_XDK" -or
   $doc.parent_main_sha256 -ne $meta.new_main_sha256 -or
   $doc.new_main_sha256 -ne (Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash.ToLowerInvariant() -or
   $doc.unknown_mmio_hard_fence -ne $true -or
   $doc.unarmed_palette_data_hard_fence -ne $true -or
   [int]$doc.transl_tus_modified -ne 0 -or
   [int]$doc.runtime_headers_modified -ne 0 -or
   $doc.synthetic_pixels -ne $false){
    throw "[K1DAC] Bounded DAC manifest mismatch; no build"
}
# Quiet wrapper is built from the DAC source, not from a separate graphics
# build. Still a single main.cpp change to XDK and no TrueTU rebuild.
& $python -m py_compile $quietStage
if($LASTEXITCODE -ne 0){throw "[K1QUIET] Python parser failed"}
& $python -u $quietStage --self-test
if($LASTEXITCODE -ne 0){throw "[K1QUIET] Trace-filter model tests failed"}
& $python -u $quietStage --parent $main --out $quietMain --manifest $quietManifest
if($LASTEXITCODE -ne 0){throw "[K1QUIET] Central trace sink stage failed"}
$quiet=Get-Content -LiteralPath $quietManifest -Raw -Encoding UTF8|ConvertFrom-Json
if($quiet.marker -ne "P6K1DQ-QUIET-LOG-20261103" -or
   $quiet.status -ne "QUIET_SOURCE_STAGED_NO_XDK" -or
   $quiet.parent_main_sha256 -ne $doc.new_main_sha256 -or
   $quiet.new_main_sha256 -ne (Get-FileHash -LiteralPath $quietMain -Algorithm SHA256).Hash.ToLowerInvariant() -or
   $quiet.first_success_pair_logged -ne $true -or
   $quiet.all_other_logs_unchanged -ne $true -or
   $quiet.guest_execution_changed -ne $false -or
   $quiet.mmio_fences_changed -ne $false -or
   [int]$quiet.translated_tus_changed -ne 0 -or
   [int]$quiet.runtime_headers_changed -ne 0){
    throw "[K1QUIET] Source provenance or preserved safety gates mismatch"
}
# The 64 translated_???.obj files were compiled with an external C++
# trace(char const*) import. A static wrapper compiles main.cpp successfully
# but fails 64-way at LINK (LNK2001); fail now, before XDK.
$quietText=Get-Content -LiteralPath $quietMain -Raw -Encoding UTF8
$traceExportPattern='(?m)^[ \t]*void[ \t]+trace[ \t]*\([ \t]*const[ \t]+char[ \t]*\*[ \t]*line[ \t]*\)[ \t]*\{'
$traceStaticPattern='(?m)^[ \t]*static[ \t]+void[ \t]+trace[ \t]*\('
$globalCount=[regex]::Matches($quietText,$traceExportPattern).Count
$staticCount=[regex]::Matches($quietText,$traceStaticPattern).Count
if($globalCount -ne 1 -or $staticCount -ne 0){
    throw "[K1QUIET] LNK2001 PREVENTION: external C++ trace(char const*) global=$globalCount static=$staticCount; no XDK"
}
if($quietText -notmatch 'K1QUIET MILESTONE SUMMARY:' -or
   $quietText -notmatch 'K1NV2A DAC PALETTE COMMIT:'){
    throw "[K1QUIET] Staged quiet/DAC runtime message watermarks missing; no XDK"
}
Write-Host "[K1QUIET] CROSS-TU LINKAGE PREFLIGHT PASS: exactly one external C++ trace(const char*) and zero static wrappers"
Write-Host "[K1DAC] SOURCE+ABI PREFLIGHT PASS; reused 64 TrueTUs and original fences"
Write-Host "[K1QUIET] PREFLIGHT PASS: first frame/PASS + unusual/failures logged; repeats counted silently"
Write-Host "[K1QUIET] CPU/kernel guest operations unchanged; GPU faults/Swap/Present always visible"
if(-not $Build){
    Write-Host "[K1DAC] NO XDK. Add -Build for one incremental Release XEX."
    exit 0
}
New-Item -ItemType Directory -Force -Path $xdk|Out-Null
$buildArgs=@{
    GeneratedMain=$quietMain
    GeneratedEnv=$envFile
    GeneratedShardDir=$shards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $xdk "xdk-clean.log")
    BuildLog=(Join-Path $xdk "xdk-build.log")
    PublishedXex=$xex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[K1DAC] Main-only DAC palette + Phase 6DQ quiet logging, 64 TrueTUs unchanged"
Write-Host "[K1QUIET] Output GPU and fault provenance unmodified; quiet mode is LOG ONLY"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1DAC] Xbox build failed: $($buildArgs.BuildLog)"}
if(-not (Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1DAC] Missing expected XDK output XEX"
}
Write-Host "[K1DAC] BUILD PASS: $xex"
Write-Host "[K1DAC] Xbox witness: old PRMDIO + new DAC + quiet boot markers, palette summary, next hard stop/pixels"
Write-Host "[K1DAC] Do not assume display_calls > 0 until hardware proves guest present"
