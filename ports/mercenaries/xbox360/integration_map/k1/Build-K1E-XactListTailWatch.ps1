[CmdletBinding()]
param(
    [switch]$PreflightOnly,
    [string]$SolutionRoot = "C:\Users\jorda\OneDrive\Desktop\My Xbox\My Projects\Mercenaries - Xbox 360\Mercenaries-PPC-Port",
    [string]$FastBuildRoot = "C:\Merc360Build\Mercenaries-PPC-Port"
)
$ErrorActionPreference="Stop"
Set-StrictMode -Version Latest

$repo=[IO.Path]::GetFullPath((Join-Path $PSScriptRoot "..\..\..\..\.."))
$py=Get-Command python -ErrorAction SilentlyContinue
if($null -eq $py){throw "[K1E] Python missing"}
$python=$py.Source

$k1cRoot=Join-Path $repo "build\phase6_integration_map\k1c_guest_write_site_va"
$main=Join-Path $k1cRoot "main.cpp"
$k1cManifest=Join-Path $k1cRoot "k1c-write-site-manifest.json"
$k1cXex=Join-Path $k1cRoot "xdk\Merc-K1C-GuestWriteSiteVA.xex"
$originalRoot=Join-Path $repo "build\phase6_integration_map\k1a_dsobject_writer_watch\translated_shards"
$k1dReport=Join-Path $repo "build\phase6_integration_map\k1d_xact_write_site\k1d-source-window.txt"
$stageRoot=Join-Path $repo "build\phase6_integration_map\k1e_xact_list_tail"
$stageShards=Join-Path $stageRoot "translated_shards"
$stageManifest=Join-Path $stageRoot "k1e-xact-tail-manifest.json"
$buildDir=Join-Path $stageRoot "xdk"
$newXex=Join-Path $buildDir "Merc-K1E-XactListTail.xex"

$r76=Join-Path $repo "build\phase6_native_graphics\r51_mm173_true_tu_xdk\main.cpp"
$r76Sha="A6A2493EC8F31F70165FEE3E3A8DBC72B02679E763DCC514F131FA3E04959C90"
$envFile=Join-Path $repo "build\phase6_native_graphics\rocket_frontier_journal_xdk\phase5_env.cpp"
$builder=Join-Path $repo "ports\mercenaries\xbox360\phase6_native_graphics\Invoke-VS17Xbox360Build.ps1"
$stager=Join-Path $PSScriptRoot "Stage-K1E-XactListTailWatch.py"
$test=Join-Path $PSScriptRoot "Test-K1E-XactListTailWatch.py"

foreach($file in @($main,$k1cManifest,$k1cXex,$k1dReport,$r76,
                    $envFile,$builder,$stager,$test)){
    if(-not(Test-Path -LiteralPath $file -PathType Leaf)){
        throw "[K1E] Missing required input: $file"
    }
}
if((Get-FileHash -LiteralPath $r76 -Algorithm SHA256).Hash -ne $r76Sha){
    throw "[K1E] Frozen original R76 SHA mismatch"
}
$k1c=Get-Content -LiteralPath $k1cManifest -Raw -Encoding UTF8 | ConvertFrom-Json
$mainSha=(Get-FileHash -LiteralPath $main -Algorithm SHA256).Hash
if($k1c.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $k1c.boot_marker -ne "P6K1C-EXACT-WRITE-SITE-VA-20261030" -or
   $k1c.staged_main_sha256.ToUpperInvariant() -ne $mainSha -or
   [int]$k1c.translated_cpp_count -ne 64 -or
   $k1c.guest_memory_hard_fence -ne "UNCHANGED"){
    throw "[K1E] K1C actual source/build provenance mismatch"
}
$report=Get-Content -LiteralPath $k1dReport -Raw -Encoding UTF8
if(-not($report.Contains("translated_029.cpp:15690 loc_0027DD0C") -and
        $report.Contains("GUEST_WRITE32(ecx, eax);") -and
        $report.Contains("void sub_0027DC5B(void)"))){
    throw "[K1E] K1D actual report does not support exact XACT list-tail target"
}
$originals=@(Get-ChildItem -LiteralPath $originalRoot -Filter "translated_*.cpp" -File)
$headers=@(Get-ChildItem -LiteralPath $originalRoot -Filter "*.h" -File)
if($originals.Count -ne 64 -or
    @($headers | Where-Object Name -eq "translated_runtime.h").Count -ne 1 -or
    $headers.Count -ne [int]$k1c.generated_header_count){
    throw "[K1E] K1C 64 TrueTU source set / generated headers drifted"
}
foreach($header in $headers){
    $expected=[string]$k1c.unchanged_header_sha256.($header.Name)
    if([string]::IsNullOrEmpty($expected) -or
       (Get-FileHash -LiteralPath $header.FullName -Algorithm SHA256).Hash -ne
       $expected.ToUpperInvariant()){
        throw "[K1E] K1C frozen header hash mismatch: $($header.Name)"
    }
}
$originalHashes=@{}
foreach($f in $originals){
    $originalHashes[$f.Name]=(Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash
}
Write-Host "[K1E] K1C Xbox main/XEX, R76, K1D report, 64 originals verified"
& $python -u $test
if($LASTEXITCODE -ne 0){throw "[K1E] Synthetic regression FAILED; NO Xbox build"}
& $python -u $stager --shards $originalRoot --out $stageShards
if($LASTEXITCODE -ne 0){throw "[K1E] Staging FAILED; NO Xbox build"}

$doc=Get-Content -LiteralPath $stageManifest -Raw -Encoding UTF8 | ConvertFrom-Json
if($doc.status -ne "STAGED_ONLY_NO_XDK_BUILD" -or
   $doc.marker -ne "K1E-XACT-TAIL-EDGE-20261030" -or
   [int]$doc.original_shards -ne 64 -or
   [int]$doc.unchanged_shards -ne 63 -or
   @($doc.modified_shards).Count -ne 1 -or
   [string]$doc.modified_shards[0] -ne "translated_029.cpp" -or
   [int]$doc.guest_store_statements_changed -ne 0 -or
   [int]$doc.guest_read_statements_changed -ne 0 -or
   [int]$doc.guest_register_writes_added -ne 0 -or
   $doc.unknown_memory_fences -ne "UNCHANGED"){
    throw "[K1E] K1E manifest/source policy FAILED before Xbox build"
}
$modified=Join-Path $stageShards "translated_029.cpp"
if($doc.staged_owner_sha256.ToUpperInvariant() -ne
   (Get-FileHash -LiteralPath $modified -Algorithm SHA256).Hash -or
   $doc.old_owner_sha256.ToUpperInvariant() -ne $originalHashes["translated_029.cpp"]){
    throw "[K1E] Exact target shard source hash FAILED"
}
foreach($f in $originals){
    $old=$originalHashes[$f.Name]
    if((Get-FileHash -LiteralPath $f.FullName -Algorithm SHA256).Hash -ne $old){
        throw "[K1E] Original TrueTU source was modified: $($f.Name)"
    }
    if($f.Name -ne "translated_029.cpp" -and
       (Get-FileHash -LiteralPath (Join-Path $stageShards $f.Name) -Algorithm SHA256).Hash -ne $old){
        throw "[K1E] Non-target source changed: $($f.Name)"
    }
}
$patched=Get-Content -LiteralPath $modified -Raw -Encoding UTF8
if(([regex]::Matches($patched, 'K1E XACT LIST PRE:')).Count -ne 1 -or
   ([regex]::Matches($patched, 'GUEST_WRITE32\(ecx, eax\);')).Count -ne 1){
    throw "[K1E] Exactly one original list-link site/witness required"
}
Write-Host "[K1E] PREFLIGHT PASS: XACT list-tail witness at 0027DD0C, only translated_029.cpp changed"
Write-Host "[K1E] 63 other TUs and every header SHA identical, guest stores/fences unchanged"
if($PreflightOnly){
    Write-Host "[K1E] PREFLIGHT ONLY - NO XDK BUILD"
    exit 0
}
New-Item -ItemType Directory -Force -Path $buildDir | Out-Null
$argsMap=@{
    GeneratedMain=$main
    GeneratedEnv=$envFile
    GeneratedShardDir=$stageShards
    ExpectedBuildTag="P6DQ-R51-MM173-FRAME-20261029-A"
    ExpectedEnvCookie="phase6dq_env_build_cookie"
    SolutionRoot=$SolutionRoot
    Configuration="Release"
    Platform="Xbox 360"
    CleanLog=(Join-Path $buildDir "xdk-clean.log")
    BuildLog=(Join-Path $buildDir "xdk-build.log")
    PublishedXex=$newXex
    ShadowBuildRoot=$FastBuildRoot
    SkipClean=$true
}
Write-Host "[K1E] Incremental VS17 XDK: 1 changed TrueTU, main/env unchanged; CLEAN SKIPPED"
& $builder @argsMap
if($LASTEXITCODE -ne 0){throw "[K1E] VS2017 Xbox build failed"}
if(-not(Test-Path -LiteralPath $newXex -PathType Leaf)){
    throw "[K1E] Xbox diagnostic XEX was not published"
}
Write-Host "[K1E] BUILD PASS: $newXex"
Write-Host "[K1E] Xbox: verify K1C boot marker and capture 'K1E XACT LIST PRE:'"
Write-Host "[K1E] No list-tail pointer substitution; READ32 EFEE0EC4 hard-fence preserved"
