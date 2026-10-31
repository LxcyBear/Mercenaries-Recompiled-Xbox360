[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest
$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$root=Join-Path $repo "build\phase6_integration_map\pixel_a3a5a_batch"
$targetShards=Join-Path $root "translated_shards"
$targetMain=Join-Path $root "main.cpp"
$targetManifest=Join-Path $root "pixel-a3a5a-batch-manifest.json"
$buildRoot=Join-Path $root "xdk"
$published=Join-Path $buildRoot "Merc-Pixel-A3A5A-Batch.xex"
$k1s=Join-Path $repo "build\phase6_integration_map\k1s_halgetvector44_saved_esi"
$sourceShards=Join-Path $k1s "translated_shards"
$sourceManifest=Join-Path $k1s "k1s-halgetvector44-saved-esi-manifest.json"
$sourceMain=Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va\main.cpp"
$originalC=Join-Path $repo "build\phase3n_final_abi_scale\runtime\gen\recomp_0013.c"
$proof=Join-Path $repo "build\phase6_integration_map\pixel_batch\pixel_apu_contracts.txt"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$stage=Join-Path $PSScriptRoot "Stage-PixelA3A5ABatch.py"
$test=Join-Path $PSScriptRoot "Test-PixelA3A5ABatch.py"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
foreach($inputFile in @($sourceManifest,$sourceMain,$originalC,$proof,$envFile,$stage,$test,$builder)){
    if(-not(Test-Path -LiteralPath $inputFile -PathType Leaf)){
        throw "[PIXEL-BUILD] Required previous K1S/proof/source input missing: $inputFile"
    }
}
if(-not(Test-Path -LiteralPath $sourceShards -PathType Container)){
    throw "[PIXEL-BUILD] K1S TrueTU cache missing: $sourceShards"
}
$py=(Get-Command python -ErrorAction Stop).Source
Write-Host "[PIXEL-BUILD] Validate real A3A5A 231-line source, ret8 and APUs"
& $py -m py_compile $stage $test
if($LASTEXITCODE -ne 0){throw "[PIXEL-BUILD] Stager or real-source test syntax error, NO XDK"}
& $py -u $test --proof $proof
if($LASTEXITCODE -ne 0){throw "[PIXEL-BUILD] Real-source A3A5A regression refused build"}

Write-Host "[PIXEL-BUILD] Stage exact original generated function in K1S 64-TU layout"
$stageArgs=@("--k1s-shards",$sourceShards,
    "--k1s-manifest",$sourceManifest,
    "--main",$sourceMain,
    "--generated",$originalC,
    "--proof",$proof,
    "--out",$targetShards,
    "--out-main",$targetMain)
& $py -u $stage @stageArgs
if($LASTEXITCODE -ne 0){throw "[PIXEL-BUILD] Source/provenance staging failed; NO XDK"}
if(-not(Test-Path -LiteralPath $targetManifest -PathType Leaf)){
    throw "[PIXEL-BUILD] Staged source manifest missing"
}
$m=Get-Content -LiteralPath $targetManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($m.marker -ne "PIXEL-A3A5A-DIRECT-APU-20261030" -or
   $m.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   [int]$m.translated_shards -ne 64 -or
   $m.new_guest_function -ne "0x002A3A5A" -or
   $m.headers_byte_identical -ne $true -or
   $m.preserved_k1s_esi_fix -ne $true -or
   $m.guest_display_call_injected -ne $false -or
   $m.guest_memory_fences -ne "UNCHANGED" -or
   $m.mmio_fences -ne "UNCHANGED" -or
   $m.applied_apu_bridge -ne "phase6ch_apu_read32/write32"){
    throw "[PIXEL-BUILD] Hard-fence/display/K1S provenance gate failed"
}
$changed=@($m.patched_true_tu_files)
if($changed.Count -lt 1 -or $changed.Count -gt 12){
    throw "[PIXEL-BUILD] Changed TrueTU fanout out of expected incremental bounds"
}
$files=@(Get-ChildItem -LiteralPath $targetShards -Filter "translated_*.cpp" -File)
if($files.Count -ne 64){throw "[PIXEL-BUILD] Staged TrueTU count no longer 64"}
if(-not(Test-Path -LiteralPath (Join-Path $targetShards "translated_runtime.h") -PathType Leaf)){
    throw "[PIXEL-BUILD] Inherited runtime header missing"
}
$mainText=Get-Content -LiteralPath $targetMain -Raw -Encoding UTF8
if(([regex]::Matches($mainText,"case 0x002A3A5Au: return sub_002A3A5A;")).Count -ne 1 -or
   ([regex]::Matches($mainText,"PIXEL-A3A5A-DIRECT-APU-20261030")).Count -ne 1 -or
   $mainText -notmatch "P6DQ-R51-MM173-FRAME-20261029-A"){
    throw "[PIXEL-BUILD] Exact native pack lookup or inherited startup tag missing"
}
$callerSites=[int]$m.caller_main_sites
foreach($prop in @($m.caller_tu_sites.PSObject.Properties)){
    $callerSites += [int]$prop.Value
}
if($callerSites -lt 1){throw "[PIXEL-BUILD] No original guest DIRECT_FRONTIER was restored"}
foreach($file in @($files | Where-Object { $changed -notcontains $_.Name })){
    $baseFile=Join-Path $sourceShards $file.Name
    $oldHash=(Get-FileHash -LiteralPath $baseFile -Algorithm SHA256).Hash
    $newHash=(Get-FileHash -LiteralPath $file.FullName -Algorithm SHA256).Hash
    if($oldHash -ne $newHash){throw "[PIXEL-BUILD] Untouched TrueTU drift: $($file.Name)"}
}
$originalHeader=Join-Path $sourceShards "translated_runtime.h"
$stagedHeader=Join-Path $targetShards "translated_runtime.h"
if((Get-FileHash $originalHeader -Algorithm SHA256).Hash -ne
   (Get-FileHash $stagedHeader -Algorithm SHA256).Hash){
    throw "[PIXEL-BUILD] Runtime header must remain byte-identical"
}
Write-Host "[PIXEL-BUILD] PREFLIGHT PASS: original translated guest function + exact lookup + $callerSites real caller edge(s)"
Write-Host ("[PIXEL-BUILD] Changed TrueTUs: "+($changed -join ", "))
Write-Host "[PIXEL-BUILD] K1S ESI fix, 64 TrueTUs, headers, MMIO/VP hard fences preserved"
Write-Host "[PIXEL-BUILD] display_calls NOT injected or fabricated"
if($PreflightOnly){
    Write-Host "[PIXEL-BUILD] PREFLIGHT ONLY: No XDK build or Xbox run"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildRoot|Out-Null
$buildArgs=@{
    GeneratedMain=$targetMain
    GeneratedEnv=$envFile
    GeneratedShardDir=$targetShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildRoot "xdk-clean.log")
    BuildLog=(Join-Path $buildRoot "xdk-build.log")
    PublishedXex=$published
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[PIXEL-BUILD] One incremental VS2017 Release Xbox 360 build; NO CLEAN"
& $builder @buildArgs
if($LASTEXITCODE -ne 0){throw "[PIXEL-BUILD] XDK build failed"}
if(-not(Test-Path -LiteralPath $published -PathType Leaf)){
    throw "[PIXEL-BUILD] Compiled XEX missing after builder"
}
Write-Host "[PIXEL-BUILD] BUILD PASS: $published"
Write-Host "[PIXEL-BUILD] Xbox: seek PIXEL A3A5A ENTRY + next DIRECT_FRONTIER/MMIO hard stop"
Write-Host "[PIXEL-BUILD] Pixel milestone: real display_calls>=1 and nonzero framebuffer"
Write-Host "[PIXEL-BUILD] No fake presentation or audio success"
