[CmdletBinding()]
param(
    [switch]$Build,
    [string]$SolutionRoot="C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot="C:\Merc360Build\Mercenaries-PPC-Port"
)
# Windows PowerShell 5.1. DEFAULT: source-only preflight / NO XDK.
# Explicit -Build compiles one incremental Xbox 360 XEX with real
# NtQueryDirectoryFile class-1 OCHAR enumeration. Not auto-deployed.
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$parent=Join-Path $repo "build\phase6_integration_map\k1_ntquerydirectory207"
$out=Join-Path $repo "build\phase6_integration_map\k1_ntquerydirectory207_native"
$parentShards=Join-Path $parent "translated_shards"
$parentMain=Join-Path $parent "main.cpp"
$parentManifest=Join-Path $parent "k1_ntquerydirectory207_manifest.json"
$shards=Join-Path $out "translated_shards"
$main=Join-Path $out "main.cpp"
$manifest=Join-Path $out "k1_ntquerydirectory207_native_manifest.json"
$stage=Join-Path $PSScriptRoot "Stage-K1Nt207Native.py"
$prior=Join-Path $PSScriptRoot "Advance-K1NtQueryDirectory207.ps1"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$envSource=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$xdk=Join-Path $out "xdk"
$xex=Join-Path $xdk "Merc-K1NT207-RealDirectory.xex"

Write-Host "[K1NT207-NATIVE] =================================================="
Write-Host "[K1NT207-NATIVE] REAL NtQueryDirectoryFile XBOX CLASS-1 ENUMERATION"
Write-Host "[K1NT207-NATIVE] =================================================="
Write-Host "[K1NT207-NATIVE] Hardware: 10 guest args, RET44; a7=1; a8=ANSI mask ptr"
Write-Host "[K1NT207-NATIVE] Real mounted directory ONLY; no hard-coded fake files."
if($Build){
    Write-Host "[K1NT207-NATIVE] EXPLICIT INCREMENTAL XDK BUILD requested"
}else{
    Write-Host "[K1NT207-NATIVE] PREFLIGHT ONLY. NO XDK, NO Xbox."
}
foreach($f in @($prior,$stage,$builder,$envSource)){
    if(-not (Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[K1NT207-NATIVE] Missing dependency: $f"
    }
}
$python=(Get-Command python -ErrorAction Stop).Source
$previousArgs=@("-NoProfile","-ExecutionPolicy","Bypass","-File",
               $prior,"-SolutionRoot",$SolutionRoot,"-FastBuildRoot",$FastBuildRoot)
& powershell.exe @previousArgs
if($LASTEXITCODE -ne 0){throw "[K1NT207-NATIVE] Parent frame-preflight failed; no build"}
foreach($f in @($parentMain,$parentManifest)){
    if(-not(Test-Path -LiteralPath $f -PathType Leaf)){
        throw "[K1NT207-NATIVE] Missing known hardware-capture parent: $f"
    }
}
& $python -m py_compile $stage
if($LASTEXITCODE -ne 0){throw "[K1NT207-NATIVE] Python parser failed"}
& $python -u $stage --self-test
if($LASTEXITCODE -ne 0){throw "[K1NT207-NATIVE] Static source/ABI self-tests failed"}
$argsList=@(
    "--parent-main",$parentMain,
    "--parent-manifest",$parentManifest,
    "--parent-shards",$parentShards,
    "--out-main",$main,
    "--out-shards",$shards,
    "--manifest",$manifest
)
& $python -u $stage @argsList
if($LASTEXITCODE -ne 0){throw "[K1NT207-NATIVE] Native enum source staging failed; no build"}
$meta=Get-Content -LiteralPath $manifest -Encoding UTF8 -Raw|ConvertFrom-Json
if($meta.marker -ne "K1NT207-REAL-DIRECTORY-ENUMERATION-20261102" -or
   $meta.status -ne "NATIVE_DIRECTORY_SOURCE_STAGED_NO_XDK" -or
   $meta.parent_marker -ne "K1NT207-DIRECTORY-FRAME-WITNESS-20261101" -or
   [int]$meta.xbox_original_stack_frame_bytes -ne 44 -or
   [int]$meta.xbox_guest_file_directory_information_class -ne 1 -or
   $meta.xbox_guest_filename_encoding -ne "OCHAR/ANSI" -or
   $meta.no_faked_files_or_success -ne $true -or
   $meta.hard_fences_unchanged_except_exact_original_207 -ne $true -or
   $meta.mmio_fences -ne "UNCHANGED" -or
   $meta.display_calls_injected -ne $false -or
   [int]$meta.xpp_guest_tus_unchanged -ne 64){
    throw "[K1NT207-NATIVE] Native source manifest/fences mismatch; no build"
}
$mainHash=(Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash.ToLowerInvariant()
if($mainHash -ne $meta.native_main_sha256){
    throw "[K1NT207-NATIVE] Source main SHA mismatch; no build"
}
$parentHeader=Join-Path $parentShards "translated_runtime.h"
$nativeHeader=Join-Path $shards "translated_runtime.h"
foreach($p in @($parentHeader,$nativeHeader)){
    if(-not (Test-Path -LiteralPath $p -PathType Leaf)){
        throw "[K1NT207-NATIVE] Missing cross-TU runtime header: $p"
    }
}
$beforeHeaderHash=(Get-FileHash -LiteralPath $parentHeader -Algorithm SHA256).Hash.ToLowerInvariant()
$afterHeaderHash=(Get-FileHash -LiteralPath $nativeHeader -Algorithm SHA256).Hash.ToLowerInvariant()
if($beforeHeaderHash -ne $meta.parent_runtime_header_sha256 -or
   $afterHeaderHash -ne $meta.native_runtime_header_sha256 -or
   $beforeHeaderHash -eq $afterHeaderHash -or
   $meta.changed_headers.Count -ne 1 -or
   $meta.changed_headers[0] -ne "translated_runtime.h"){
    throw "[K1NT207-NATIVE] Active TRUE TU dispatcher/header not staged correctly"
}
$nativeHeaderText=Get-Content -LiteralPath $nativeHeader -Encoding UTF8 -Raw
$originalHeaderText=Get-Content -LiteralPath $parentHeader -Encoding UTF8 -Raw
# K1NT207 now wraps the ORIGINAL ICALL_SAFE macro. The old
# '_phase4c_target == 0x800000CFu' anchor is NOT part of the wrapper.
# Require the exact CF guard, call, cross-TU declaration, and inherited
# hard-stop fallback. The parent header must not already handle CF.
$guardPattern='if\s*\(\s*\(uint32_t\)\s*\(xbox_va\)\s*==\s*0x800000CFu\s*\)\s*\{'
$callPattern='k1nt207_nt_query_directory_file\s*\(\s*\(uint32_t\)\s*\(saved_esp\)\s*\)\s*;'
$declPattern='void\s+k1nt207_nt_query_directory_file\s*\(\s*uint32_t\s+savedEsp\s*\)\s*;'
$fallbackPattern='phase4c_escape\s*\('
$guardMatches=[regex]::Matches($nativeHeaderText,$guardPattern).Count
$callMatches=[regex]::Matches($nativeHeaderText,$callPattern).Count
$declMatches=[regex]::Matches($nativeHeaderText,$declPattern).Count
if($guardMatches -ne 1 -or $callMatches -ne 1 -or $declMatches -ne 1 -or
   $nativeHeaderText -notmatch $fallbackPattern -or
   $originalHeaderText -match $guardPattern -or
   $originalHeaderText -match $callPattern){
    throw "[K1NT207-NATIVE] TrueTU CF wrapper/source provenance mismatch: guard=$guardMatches call=$callMatches decl=$declMatches; no build"
}
Write-Host "[K1NT207-NATIVE] TRUE TU HEADER PASS: exact ordinal207 guard=1, call=1, declaration=1, fallback preserved"
$all=@(Get-ChildItem -LiteralPath $shards -Filter "translated_???.cpp" -File)
if($all.Count -ne 64){throw "[K1NT207-NATIVE] Expected 64 unchanged TrueTUs"}
foreach($item in $all){
    $before=Join-Path $parentShards $item.Name
    if((Get-FileHash -LiteralPath $before -Algorithm SHA256).Hash -ne
       (Get-FileHash -LiteralPath $item.FullName -Algorithm SHA256).Hash){
        throw "[K1NT207-NATIVE] Changed inherited TrueTU: $($item.Name)"
    }
}
Write-Host "[K1NT207-NATIVE] SOURCE/ABI PREFLIGHT PASS: 64 byte-identical TrueTUs"
Write-Host "[K1NT207-NATIVE] SUCCESS!!! TrueTU translated_runtime.h carries live ordinal207 dispatch"
Write-Host "[K1NT207-NATIVE] Real Xbox directory enumeration staged in host main.cpp"
Write-Host "[K1NT207-NATIVE] No synthetic display calls, no input or VP/MMIO relaxation"
Write-Host "[K1NT207-NATIVE] Manifest: $manifest"
if(-not $Build){
    Write-Host "[K1NT207-NATIVE] NO XDK. After reviewing PASS, rerun with -Build."
    exit 0
}
New-Item -ItemType Directory -Force -Path $xdk | Out-Null
$buildArgs=@{
    GeneratedMain=$main
    GeneratedEnv=$envSource
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
Write-Host "[K1NT207-NATIVE] ONE incremental Release Xbox360 XDK build (SkipClean)"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[K1NT207-NATIVE] Build failed: $($buildArgs.BuildLog)"}
if(-not(Test-Path -LiteralPath $xex -PathType Leaf)){
    throw "[K1NT207-NATIVE] XDK did not publish expected XEX"
}
Write-Host "[K1NT207-NATIVE] XDK BUILD PASS: $xex"
Write-Host "[K1NT207-NATIVE] Xbox witness required: K1NT207 REAL ENUM START/RESULT"
Write-Host "[K1NT207-NATIVE] Genuine native status/rows/bytes, next hard stop, graphics"
Write-Host "[K1NT207-NATIVE] NOTE: build success != live Xbox native-enumeration proof"
